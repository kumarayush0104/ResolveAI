import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import AsyncSessionLocal
from backend.app.db.models import Case, Order, PaymentAttempt, CaseEvent, WebhookEvent
from backend.app.policy.engine import evaluate
from backend.app.policy.states import PaymentState
from backend.app.services.status_check import StatusReport, check_payment_status
from backend.app.services.stream_bus import event_bus

logger = logging.getLogger(__name__)

NON_TERMINAL = ("PENDING", "UNKNOWN", "CREATED")


async def _load_attempts(session: AsyncSession, order_id: str) -> List[PaymentAttempt]:
    res = await session.execute(select(PaymentAttempt).where(PaymentAttempt.order_id == order_id))
    return list(res.scalars().all())


async def _load_webhooks(session: AsyncSession, paypal_order_id: str, capture_id: Optional[str]) -> List[WebhookEvent]:
    ids = [i for i in (paypal_order_id, capture_id) if i]
    res = await session.execute(select(WebhookEvent).where(WebhookEvent.resource_id.in_(ids)))
    return list(res.scalars().all())


def apply_report(order: Order, attempts: List[PaymentAttempt], report: StatusReport) -> bool:
    """Write what PayPal told us onto the order and its attempts. Returns True if anything changed.

    Only terminal PayPal evidence closes an attempt. A timeout, an unreachable source or a conflict
    never marks anything failed.
    """
    snap = report.snapshot
    changed = False
    status = snap.capture_status

    if status == "COMPLETED":
        for a in attempts:
            if a.status in NON_TERMINAL:
                a.status = "COMPLETED"
                changed = True
            if snap.capture_id and not a.paypal_capture_id and a.status == "COMPLETED":
                a.paypal_capture_id = snap.capture_id
                changed = True
        if order.status != "COMPLETED":
            order.status = "COMPLETED"
            changed = True

    elif status == "DENIED":
        for a in attempts:
            if a.status in NON_TERMINAL:
                a.status = "DENIED"
                changed = True
        if order.status != "DENIED":
            order.status = "DENIED"
            changed = True

    elif status == "PENDING" and not report.conflicts:
        # PayPal positively reports a pending capture. If our only record is "UNKNOWN" and nothing
        # else is active, we now know more: promote it (respects the one-active-attempt index).
        active = [a for a in attempts if a.status in ("PENDING", "CREATED")]
        unknown = [a for a in attempts if a.status == "UNKNOWN"]
        if not active and unknown and snap.capture_id:
            latest = max(unknown, key=lambda a: a.created_at)
            latest.status = "PENDING"
            latest.paypal_capture_id = latest.paypal_capture_id or snap.capture_id
            changed = True

    return changed


async def reconcile_order(
    session: AsyncSession,
    order: Order,
    *,
    commit: bool = True,
) -> Tuple[StatusReport, bool]:
    """Check PayPal for one order and apply the result. Works with or without a case."""
    attempts = await _load_attempts(session, order.id)
    capture_id = next((a.paypal_capture_id for a in attempts if a.paypal_capture_id), None)
    webhooks = await _load_webhooks(session, order.paypal_order_id, capture_id)

    report = await check_payment_status(order, attempts, webhooks)
    changed = apply_report(order, attempts, report)
    if commit:
        await session.commit()
    return report, changed


async def reconcile_case(
    case_id: str,
    session: AsyncSession,
    *,
    record_evidence: bool = False,
) -> Optional[Dict[str, Any]]:
    """Reconcile a case against PayPal's authoritative state.

    record_evidence=True (a person asked) always writes a timeline entry showing what each source said.
    The background loop passes False so it only writes when the state actually changes.
    """
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        return None

    order_res = await session.execute(select(Order).where(Order.id == case.order_id))
    order = order_res.scalar_one_or_none()
    if not order:
        return None

    report, _ = await reconcile_order(session, order, commit=False)
    attempts = await _load_attempts(session, order.id)

    events_res = await session.execute(select(CaseEvent).where(CaseEvent.case_id == case.id))
    events = list(events_res.scalars().all())

    decision = evaluate(snapshot=report.snapshot, attempts=attempts, events=events)

    old_state = case.current_policy_state
    new_state = decision.state.value
    state_changed = old_state != new_state

    case.current_policy_state = new_state
    case.status = new_state
    case.permitted_actions = decision.permitted_actions

    if state_changed:
        session.add(CaseEvent(
            case_id=case.id,
            source="RECONCILER",
            event_type="CASE_STATE_RECONCILED",
            description=f"Reconciled state changed from {old_state} to {new_state}. {report.summary_line()}",
            is_simulated=report.snapshot.is_simulated,
        ))
    elif record_evidence:
        session.add(CaseEvent(
            case_id=case.id,
            source="API",
            event_type="PAYMENT_STATUS_CHECKED",
            description=report.summary_line(),
            is_simulated=report.snapshot.is_simulated,
        ))

    if report.conflicts and (state_changed or record_evidence):
        session.add(CaseEvent(
            case_id=case.id,
            source="POLICY",
            event_type="EVIDENCE_CONFLICT",
            description="PayPal sources disagree, so retry, refund and fulfillment stay locked until it is resolved. "
                        + " ".join(report.conflicts),
            is_simulated=False,
        ))

    await session.commit()

    if state_changed:
        await event_bus.broadcast(case.id, {
            "type": "reconciliation_update",
            "case_id": case.id,
            "old_state": old_state,
            "new_state": new_state,
            "rule_fired": decision.rule_fired,
        })

    return {
        "case_id": case.id,
        "state_changed": state_changed,
        "current_state": new_state,
        "decision": decision.to_dict(),
        "report": report.to_dict(),
    }


# ---- background worker -----------------------------------------------------------------------

BASE_INTERVAL = 30
MAX_BACKOFF = 600
_backoff: Dict[str, Tuple[int, float]] = {}   # key -> (consecutive failures, next allowed time)


def _due(key: str) -> bool:
    entry = _backoff.get(key)
    return entry is None or time.monotonic() >= entry[1]


def _note_result(key: str, reachable: bool) -> None:
    if reachable:
        _backoff.pop(key, None)
        return
    failures = _backoff.get(key, (0, 0.0))[0] + 1
    delay = min(BASE_INTERVAL * (2 ** failures), MAX_BACKOFF)
    _backoff[key] = (failures, time.monotonic() + delay)


async def run_reconciliation_cycle() -> None:
    """Reconcile every unresolved case, plus unresolved orders that never got a case.

    A buyer whose capture response was lost may not have opened a case yet, so we also look at
    orders that have an UNKNOWN or PENDING attempt. Unreachable PayPal triggers exponential backoff.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Case).where(
                Case.current_policy_state.in_([PaymentState.PENDING.value, PaymentState.UNKNOWN.value])
            )
        )
        cases = result.scalars().all()
        case_order_ids = set()
        for c in cases:
            case_order_ids.add(c.order_id)
            key = f"case:{c.id}"
            if not _due(key):
                continue
            try:
                out = await reconcile_case(c.id, session)
                _note_result(key, bool(out and out["report"]["reachable"]))
            except Exception as exc:  # noqa: BLE001
                logger.error("Error reconciling case %s: %s", c.id, exc)
                _note_result(key, False)

        orphan_res = await session.execute(
            select(Order)
            .join(PaymentAttempt, PaymentAttempt.order_id == Order.id)
            .where(PaymentAttempt.status.in_(["UNKNOWN", "PENDING"]))
        )
        for order in {o.id: o for o in orphan_res.scalars().all()}.values():
            if order.id in case_order_ids:
                continue
            key = f"order:{order.id}"
            if not _due(key):
                continue
            try:
                report, _ = await reconcile_order(session, order)
                _note_result(key, report.reachable)
            except Exception as exc:  # noqa: BLE001
                logger.error("Error reconciling order %s: %s", order.id, exc)
                _note_result(key, False)


async def reconciler_background_loop(interval_seconds: int = BASE_INTERVAL) -> None:
    """Continuous background worker loop for periodic reconciliation."""
    logger.info("Starting background reconciliation loop (interval=%ds)...", interval_seconds)
    while True:
        try:
            await run_reconciliation_cycle()
        except asyncio.CancelledError:
            logger.info("Reconciliation background loop cancelled.")
            break
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error in reconciliation loop: %s", exc)

        await asyncio.sleep(interval_seconds)
