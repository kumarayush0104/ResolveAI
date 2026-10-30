import pytest
from backend.app.policy.engine import evaluate
from backend.app.policy.states import PaymentState
from backend.app.policy.rules import (
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


def test_r01_completed_blocks_retry():
    """R01: Capture COMPLETED blocks RETRY and ALLOW_RETRY actions."""
    snapshot = ProviderSnapshot(
        order_status="COMPLETED",
        capture_status="COMPLETED",
        capture_id="CAP-12345",
        order_id="ORD-12345",
    )
    decision = evaluate(snapshot=snapshot, attempts=[], events=[])
    assert decision.state == PaymentState.COMPLETED
    assert decision.rule_fired == R01_COMPLETED_BLOCKS_RETRY
    assert "RETRY" not in decision.permitted_actions
    assert "ALLOW_RETRY" not in decision.permitted_actions
    assert any(b["action"] == "RETRY" and b["rule_id"] == R01_COMPLETED_BLOCKS_RETRY for b in decision.blocked_actions)
    assert "REFUND" in decision.permitted_actions


def test_r02_pending_blocks_retry():
    """R02: Any attempt PENDING blocks retry, sets permitted action to RECONCILE."""
    snapshot = ProviderSnapshot(
        order_status="APPROVED",
        capture_status="PENDING",
        order_id="ORD-12345",
    )
    decision = evaluate(snapshot=snapshot, attempts=[{"status": "PENDING"}], events=[])
    assert decision.state == PaymentState.PENDING
    assert decision.rule_fired == R02_PENDING_BLOCKS_RETRY
    assert "RETRY" not in decision.permitted_actions
    assert "RECONCILE" in decision.permitted_actions
    assert any(b["action"] == "RETRY" and b["rule_id"] == R02_PENDING_BLOCKS_RETRY for b in decision.blocked_actions)


def test_r03_unknown_fails_closed():
    """R03: Timeout or missing evidence causes state=UNKNOWN and fails closed."""
    snapshot = ProviderSnapshot(
        order_status="UNKNOWN",
        capture_status="UNKNOWN",
        order_id="ORD-12345",
    )
    decision = evaluate(snapshot=snapshot, attempts=[{"status": "UNKNOWN"}], events=[])
    assert decision.state == PaymentState.UNKNOWN
    assert decision.rule_fired == R03_UNKNOWN_FAILS_CLOSED
    # Fails closed: retry, void, and refund are all blocked
    assert "RETRY" not in decision.permitted_actions
    assert "REFUND" not in decision.permitted_actions
    assert "VOID" not in decision.permitted_actions
    assert "RECONCILE" in decision.permitted_actions
    blocked_act_names = [b["action"] for b in decision.blocked_actions]
    assert "RETRY" in blocked_act_names
    assert "REFUND" in blocked_act_names
    assert "VOID" in blocked_act_names


def test_r04_denied_allows_retry_after_approval():
    """R04: Verified DENIED allows retry after user/merchant approval."""
    snapshot = ProviderSnapshot(
        order_status="DENIED",
        capture_status="DENIED",
        order_id="ORD-12345",
    )
    decision = evaluate(snapshot=snapshot, attempts=[{"status": "DENIED"}], events=[])
    assert decision.state == PaymentState.DENIED
    assert decision.rule_fired == R04_DENIED_ALLOWS_RETRY
    assert "ALLOW_RETRY" in decision.permitted_actions
    assert decision.requires_approval is True
    # Cannot refund a denied transaction
    assert "REFUND" not in decision.permitted_actions


def test_r05_refund_only_completed():
    """R05: Refund requires COMPLETED capture; otherwise blocked."""
    # Denied or Pending cannot be refunded
    snap_pending = ProviderSnapshot(capture_status="PENDING")
    dec_pending = evaluate(snapshot=snap_pending, attempts=[])
    assert "REFUND" not in dec_pending.permitted_actions
    assert any(b["action"] == "REFUND" and b["rule_id"] == R05_REFUND_ONLY_COMPLETED for b in dec_pending.blocked_actions)

    # Completed CAN be refunded
    snap_completed = ProviderSnapshot(capture_status="COMPLETED")
    dec_completed = evaluate(snapshot=snap_completed, attempts=[])
    assert "REFUND" in dec_completed.permitted_actions


def test_r06_void_only_uncaptured_auth():
    """R06: Void requires uncaptured auth, blocked on completed or settled captures."""
    snapshot = ProviderSnapshot(capture_status="COMPLETED")
    decision = evaluate(snapshot=snapshot, attempts=[])
    assert "VOID" not in decision.permitted_actions
    assert any(b["action"] == "VOID" and b["rule_id"] == R06_VOID_ONLY_UNCAPTURED_AUTH for b in decision.blocked_actions)


def test_r07_one_active_attempt():
    """R07: Multiple active attempts trigger R07 blocking retry."""
    attempts = [
        {"id": "att-1", "status": "PENDING"},
        {"id": "att-2", "status": "PENDING"},
    ]
    decision = evaluate(snapshot=None, attempts=attempts, events=[])
    assert decision.rule_fired == R07_ONE_ACTIVE_ATTEMPT
    assert "RETRY" not in decision.permitted_actions
    assert any(b["action"] == "RETRY" and b["rule_id"] == R07_ONE_ACTIVE_ATTEMPT for b in decision.blocked_actions)


def test_r08_ai_is_advisory():
    """R08: If AI proposal recommends an illegal action, policy engine overrides it."""
    snapshot = ProviderSnapshot(capture_status="COMPLETED")
    # AI mistakenly recommends retry on completed capture
    ai_proposal = {"recommended_action": "ALLOW_RETRY"}
    decision = evaluate(snapshot=snapshot, attempts=[], events=[], ai_proposal=ai_proposal)
    assert decision.state == PaymentState.COMPLETED
    assert "ALLOW_RETRY" not in decision.permitted_actions
    assert decision.rule_fired == R08_AI_IS_ADVISORY
    assert any(b["action"] == "ALLOW_RETRY" and b["rule_id"] == R08_AI_IS_ADVISORY for b in decision.blocked_actions)


def test_r09_refund_requested_ne_completed():
    """R09: Refund request accepted transitions state to REFUND_PENDING, not REFUNDED."""
    events = [{"event_type": "REFUND_REQUESTED"}]
    decision = evaluate(snapshot=None, attempts=[], events=events)
    assert decision.state == PaymentState.REFUND_PENDING
    assert decision.rule_fired == R09_REFUND_REQUESTED_NE_COMPLETED
    assert "RETRY" not in decision.permitted_actions
