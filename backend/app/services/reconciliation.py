import asyncio
import logging
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import AsyncSessionLocal
from backend.app.db.models import Case, Order, PaymentAttempt, CaseEvent
from backend.app.paypal.orders import get_order, get_capture
from backend.app.paypal.client import ProviderSnapshot
from backend.app.policy.engine import evaluate
from backend.app.policy.states import PaymentState
from backend.app.services.stream_bus import event_bus

logger = logging.getLogger(__name__)


async def reconcile_case(case_id: str, session: AsyncSession) -> Optional[Dict[str, Any]]:
    """Reconcile a single case against PayPal authoritative state."""
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        return None

    # Load order and attempts
    order_res = await session.execute(select(Order).where(Order.id == case.order_id))
    order = order_res.scalar_one_or_none()
    if not order:
        return None

    attempts_res = await session.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
    )
    attempts = list(attempts_res.scalars().all())

    # Get authoritative snapshot from PayPal
    try:
        capture_id = next((a.paypal_capture_id for a in attempts if a.paypal_capture_id), None)
        if capture_id:
            snapshot = await get_capture(capture_id)
        else:
            snapshot = await get_order(order.paypal_order_id)
    except Exception as exc:
        logger.warning("Reconciliation query failed for case %s: %s", case_id, exc)
        return None

    # Evaluate authoritative policy
    events_res = await session.execute(
        select(CaseEvent).where(CaseEvent.case_id == case.id)
    )
    events = list(events_res.scalars().all())

    decision = evaluate(snapshot=snapshot, attempts=attempts, events=events)

    # Check if state or capture status changed
    old_state = case.current_policy_state
    new_state = decision.state.value

    # Update attempt statuses if snapshot gave us terminal capture
    if snapshot.capture_status in ("COMPLETED", "DENIED"):
        for a in attempts:
            if a.status in ("PENDING", "UNKNOWN", "CREATED"):
                a.status = snapshot.capture_status
                if snapshot.capture_id and not a.paypal_capture_id:
                    a.paypal_capture_id = snapshot.capture_id

    state_changed = old_state != new_state
    if state_changed:
        case.current_policy_state = new_state
        case.status = new_state
        case.permitted_actions = decision.permitted_actions

        event = CaseEvent(
            case_id=case.id,
            source="RECONCILER",
            event_type="CASE_STATE_RECONCILED",
            description=f"Reconciled state changed from {old_state} to {new_state} via authoritative PayPal query.",
            is_simulated=snapshot.is_simulated,
        )
        session.add(event)
        await session.commit()

        # Emit SSE notification
        await event_bus.broadcast(case.id, {
            "type": "reconciliation_update",
            "case_id": case.id,
            "old_state": old_state,
            "new_state": new_state,
            "rule_fired": decision.rule_fired,
        })
    else:
        await session.commit()

    return {
        "case_id": case.id,
        "state_changed": state_changed,
        "current_state": new_state,
        "decision": decision.to_dict(),
    }


async def run_reconciliation_cycle() -> None:
    """Find all cases in PENDING or UNKNOWN state and reconcile each with PayPal."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Case).where(
                Case.current_policy_state.in_([PaymentState.PENDING.value, PaymentState.UNKNOWN.value])
            )
        )
        cases = result.scalars().all()
        for c in cases:
            try:
                await reconcile_case(c.id, session)
            except Exception as exc:
                logger.error("Error reconciling case %s: %s", c.id, exc)


async def reconciler_background_loop(interval_seconds: int = 30) -> None:
    """Continuous background worker loop for periodic reconciliation."""
    logger.info("Starting background reconciliation loop (interval=%ds)...", interval_seconds)
    while True:
        try:
            await run_reconciliation_cycle()
        except asyncio.CancelledError:
            logger.info("Reconciliation background loop cancelled.")
            break
        except Exception as exc:
            logger.exception("Unexpected error in reconciliation loop: %s", exc)

        await asyncio.sleep(interval_seconds)
