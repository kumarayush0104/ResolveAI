from typing import List, Dict, Any, Optional

from backend.app.policy.states import PaymentState
from backend.app.policy.rules import (
    PolicyDecision,
    R01_COMPLETED_BLOCKS_RETRY,
    R02_PENDING_BLOCKS_RETRY,
    R03_UNKNOWN_FAILS_CLOSED,
    R04_DENIED_ALLOWS_RETRY,
    R05_REFUND_ONLY_COMPLETED,
    R06_VOID_ONLY_UNCAPTURED_AUTH,
    R07_ONE_ACTIVE_ATTEMPT,
    R08_AI_IS_ADVISORY,
    R09_REFUND_REQUESTED_NE_COMPLETED,
)
from backend.app.paypal.client import ProviderSnapshot


def _get_status_from_attempt(attempt: Any) -> str:
    """Helper to extract status string from an attempt dict or ORM object."""
    if isinstance(attempt, dict):
        return attempt.get("status", "UNKNOWN").upper()
    return getattr(attempt, "status", "UNKNOWN").upper()


def _get_event_type(event: Any) -> str:
    """Helper to extract event_type from event dict or ORM object."""
    if isinstance(event, dict):
        return event.get("event_type", "").upper()
    return getattr(event, "event_type", "").upper()


def evaluate(
    snapshot: Optional[ProviderSnapshot] = None,
    attempts: Optional[List[Any]] = None,
    events: Optional[List[Any]] = None,
    ai_proposal: Optional[Dict[str, Any]] = None,
) -> PolicyDecision:
    """Authoritative deterministic policy engine evaluating payment state and allowed actions.
    Rules R01-R09 are strictly enforced here.
    """
    attempts = attempts or []
    events = events or []

    # 1. Inspect events for refund progress (R09 / R05)
    has_refund_completed = any(
        _get_event_type(e) in ("PAYMENT.CAPTURE.REFUNDED", "REFUND_COMPLETED")
        for e in events
    )
    has_refund_requested = any(
        _get_event_type(e) in ("REFUND_REQUESTED", "REFUND_PENDING", "PAYMENT.CAPTURE.REFUND.PENDING")
        for e in events
    )

    # 2. Check for active attempts concurrency (R07)
    active_attempts = [
        a for a in attempts
        if _get_status_from_attempt(a) not in ("COMPLETED", "DENIED", "UNKNOWN")
    ]
    has_duplicate_active_attempts = len(active_attempts) > 1

    # 3. Determine base capture status from snapshot and history
    cap_status = snapshot.capture_status.upper() if snapshot else None

    # Check attempt statuses
    attempt_statuses = [_get_status_from_attempt(a) for a in attempts]
    any_completed = (cap_status == "COMPLETED") or ("COMPLETED" in attempt_statuses)
    any_unknown = (cap_status == "UNKNOWN") or ("UNKNOWN" in attempt_statuses)
    any_pending = (cap_status == "PENDING") or ("PENDING" in attempt_statuses)
    all_denied = (cap_status == "DENIED") and (len(attempts) == 0 or all(s == "DENIED" for s in attempt_statuses))

    blocked_actions: List[Dict[str, Any]] = []

    # R07 check: multiple active attempts
    if has_duplicate_active_attempts:
        return PolicyDecision(
            state=PaymentState.PENDING,
            permitted_actions=["RECONCILE"],
            blocked_actions=[
                {
                    "action": "RETRY",
                    "rule_id": R07_ONE_ACTIVE_ATTEMPT,
                    "reason": "Only one active payment attempt permitted per order. Race condition blocked.",
                    "evidence_refs": ["attempts"],
                }
            ],
            requires_approval=False,
            rule_fired=R07_ONE_ACTIVE_ATTEMPT,
        )

    # R09 & R05: Refund evaluation
    if has_refund_completed:
        return PolicyDecision(
            state=PaymentState.REFUNDED,
            permitted_actions=["VIEW_DETAILS"],
            blocked_actions=[
                {
                    "action": "RETRY",
                    "rule_id": R01_COMPLETED_BLOCKS_RETRY,
                    "reason": "Transaction has already been refunded.",
                    "evidence_refs": ["events.REFUND_COMPLETED"],
                },
                {
                    "action": "REFUND",
                    "rule_id": R05_REFUND_ONLY_COMPLETED,
                    "reason": "Already refunded in full.",
                    "evidence_refs": ["events.REFUND_COMPLETED"],
                },
            ],
            requires_approval=False,
            rule_fired=R05_REFUND_ONLY_COMPLETED,
        )

    if has_refund_requested:
        return PolicyDecision(
            state=PaymentState.REFUND_PENDING,
            permitted_actions=["RECONCILE"],
            blocked_actions=[
                {
                    "action": "RETRY",
                    "rule_id": R09_REFUND_REQUESTED_NE_COMPLETED,
                    "reason": "Refund has been requested and is currently pending processing. Never claim money received.",
                    "evidence_refs": ["events.REFUND_REQUESTED"],
                }
            ],
            requires_approval=False,
            rule_fired=R09_REFUND_REQUESTED_NE_COMPLETED,
        )

    # R01: COMPLETED blocks retry
    if any_completed:
        decision = PolicyDecision(
            state=PaymentState.COMPLETED,
            permitted_actions=["REFUND", "VIEW_DETAILS"],
            blocked_actions=[
                {
                    "action": "RETRY",
                    "rule_id": R01_COMPLETED_BLOCKS_RETRY,
                    "reason": "Payment confirmed. Capture already COMPLETED. Retrying would cause duplicate charge.",
                    "evidence_refs": ["snapshot.capture_status" if cap_status == "COMPLETED" else "attempts.status"],
                },
                {
                    "action": "ALLOW_RETRY",
                    "rule_id": R01_COMPLETED_BLOCKS_RETRY,
                    "reason": "Payment confirmed. Capture already COMPLETED.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
                {
                    "action": "VOID",
                    "rule_id": R06_VOID_ONLY_UNCAPTURED_AUTH,
                    "reason": "Capture has already settled. Void applies only to uncaptured authorizations. Use refund instead.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
            ],
            requires_approval=True,  # Refunding requires explicit merchant approval
            rule_fired=R01_COMPLETED_BLOCKS_RETRY,
        )
        return _apply_ai_guard(decision, ai_proposal)

    # R02: PENDING blocks retry
    if any_pending and not any_unknown:
        decision = PolicyDecision(
            state=PaymentState.PENDING,
            permitted_actions=["RECONCILE"],
            blocked_actions=[
                {
                    "action": "RETRY",
                    "rule_id": R02_PENDING_BLOCKS_RETRY,
                    "reason": "An active payment attempt is currently PENDING. Retry is blocked to prevent double charge.",
                    "evidence_refs": ["snapshot.capture_status" if cap_status == "PENDING" else "attempts.status"],
                },
                {
                    "action": "ALLOW_RETRY",
                    "rule_id": R02_PENDING_BLOCKS_RETRY,
                    "reason": "An active payment attempt is currently PENDING.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
                {
                    "action": "REFUND",
                    "rule_id": R05_REFUND_ONLY_COMPLETED,
                    "reason": "Cannot refund a pending, uncaptured transaction.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
                {
                    "action": "VOID",
                    "rule_id": R06_VOID_ONLY_UNCAPTURED_AUTH,
                    "reason": "No uncaptured authorization found.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
            ],
            requires_approval=False,
            rule_fired=R02_PENDING_BLOCKS_RETRY,
        )
        return _apply_ai_guard(decision, ai_proposal)

    # R03: UNKNOWN fails closed (network timeout, missing or conflicting evidence)
    if any_unknown or (cap_status == "UNKNOWN"):
        decision = PolicyDecision(
            state=PaymentState.UNKNOWN,
            permitted_actions=["RECONCILE", "ESCALATE"],
            blocked_actions=[
                {
                    "action": "RETRY",
                    "rule_id": R03_UNKNOWN_FAILS_CLOSED,
                    "reason": "Payment status is UNKNOWN (e.g. timeout or unverified). System fails closed to prevent duplicate capture.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
                {
                    "action": "ALLOW_RETRY",
                    "rule_id": R03_UNKNOWN_FAILS_CLOSED,
                    "reason": "Payment status is UNKNOWN. System fails closed.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
                {
                    "action": "REFUND",
                    "rule_id": R03_UNKNOWN_FAILS_CLOSED,
                    "reason": "Cannot refund transaction in UNKNOWN state until reconciled.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
                {
                    "action": "VOID",
                    "rule_id": R03_UNKNOWN_FAILS_CLOSED,
                    "reason": "Cannot void transaction in UNKNOWN state until reconciled.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
            ],
            requires_approval=False,
            rule_fired=R03_UNKNOWN_FAILS_CLOSED,
        )
        return _apply_ai_guard(decision, ai_proposal)

    # R04: DENIED allows retry after user approval
    if all_denied or cap_status == "DENIED":
        decision = PolicyDecision(
            state=PaymentState.DENIED,
            permitted_actions=["ALLOW_RETRY"],
            blocked_actions=[
                {
                    "action": "REFUND",
                    "rule_id": R05_REFUND_ONLY_COMPLETED,
                    "reason": "Cannot refund a failed or denied payment.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
                {
                    "action": "VOID",
                    "rule_id": R06_VOID_ONLY_UNCAPTURED_AUTH,
                    "reason": "No valid authorization exists to void.",
                    "evidence_refs": ["snapshot.capture_status"],
                },
            ],
            requires_approval=True,  # explicit confirmation before retrying
            rule_fired=R04_DENIED_ALLOWS_RETRY,
        )
        return _apply_ai_guard(decision, ai_proposal)

    # Default / CREATED state
    return PolicyDecision(
        state=PaymentState.CREATED,
        permitted_actions=["CAPTURE"],
        blocked_actions=[
            {
                "action": "REFUND",
                "rule_id": R05_REFUND_ONLY_COMPLETED,
                "reason": "Order created but not captured yet.",
                "evidence_refs": ["order.status"],
            }
        ],
        requires_approval=False,
        rule_fired="ORDER_CREATED",
    )


def _apply_ai_guard(decision: PolicyDecision, ai_proposal: Optional[Dict[str, Any]]) -> PolicyDecision:
    """R08_AI_IS_ADVISORY: Validate AI proposal against authoritative policy.
    If the AI suggests an action that is blocked by the policy engine,
    override the proposal and log/flag the mismatch.
    """
    if not ai_proposal:
        return decision

    rec_action = ai_proposal.get("recommended_action")
    if not rec_action:
        return decision

    # Map AI actions to policy actions
    # e.g., AI recommended 'ALLOW_RETRY' or 'RETRY'
    is_blocked = any(b["action"] == rec_action for b in decision.blocked_actions)
    if is_blocked or (rec_action not in decision.permitted_actions and rec_action != "ESCALATE" and rec_action != "RECONCILE"):
        # Policy wins! Override AI recommendation
        decision.blocked_actions.append({
            "action": rec_action,
            "rule_id": R08_AI_IS_ADVISORY,
            "reason": f"AI recommendation '{rec_action}' overridden: violates policy rule {decision.rule_fired}.",
            "evidence_refs": ["ai_proposal.recommended_action"],
        })
        decision.rule_fired = R08_AI_IS_ADVISORY

    return decision
