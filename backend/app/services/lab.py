import asyncio
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Case, Order, PaymentAttempt, WebhookEvent, CaseEvent
from backend.app.paypal.client import ProviderSnapshot
from backend.app.paypal.orders import capture_order, get_order
from backend.app.policy.engine import evaluate
from backend.app.services.stream_bus import event_bus


async def simulate_lose_success_response(case_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Execute real capture with PayPal, but artificially record local attempt as UNKNOWN."""
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    order_res = await session.execute(select(Order).where(Order.id == case.order_id))
    order = order_res.scalar_one_or_none()

    # Create new attempt marked UNKNOWN (simulating dropped network response)
    req_id = f"sim-loss-{uuid.uuid4().hex[:8]}"
    attempt = PaymentAttempt(
        order_id=order.id,
        request_id=req_id,
        status="UNKNOWN",
        paypal_capture_id=None,
        paypal_response_raw=json.dumps({"simulation": "lost_success_response"}),
        is_simulated=True,
    )
    session.add(attempt)

    # Trigger real PayPal capture in background/parallel (or simulated)
    real_snap = None
    try:
        real_snap = await capture_order(order.paypal_order_id, request_id=req_id)
        if real_snap.capture_id:
            # We don't save capture_id on attempt yet to simulate response loss
            pass
    except Exception:
        pass

    case.current_policy_state = "UNKNOWN"
    case.status = "UNKNOWN"
    case.permitted_actions = ["RECONCILE", "ESCALATE"]

    event = CaseEvent(
        case_id=case.id,
        source="POLICY",
        event_type="SIMULATED_NETWORK_TIMEOUT",
        description="SIMULATION: Captured on PayPal, but response timed out locally. Attempt marked UNKNOWN.",
        is_simulated=True,
    )
    session.add(event)
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "lose_success_response",
        "state": "UNKNOWN",
        "is_simulated": True,
    })

    return {
        "case_id": case.id,
        "status": "UNKNOWN",
        "simulated": True,
        "message": "Real capture requested, but local status recorded as UNKNOWN. Reconciliation will heal this.",
    }


async def simulate_inject_failure(case_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Inject a verified DENIED state."""
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    req_id = f"sim-fail-{uuid.uuid4().hex[:8]}"
    attempt = PaymentAttempt(
        order_id=case.order_id,
        request_id=req_id,
        status="DENIED",
        paypal_response_raw=json.dumps({"status": "DECLINED", "reason": "SIMULATED_CARD_DECLINE"}),
        is_simulated=True,
    )
    session.add(attempt)

    case.current_policy_state = "DENIED"
    case.status = "DENIED"
    case.permitted_actions = ["ALLOW_RETRY"]

    event = CaseEvent(
        case_id=case.id,
        source="API",
        event_type="PAYMENT_DENIED",
        description="SIMULATION: Provider explicitly denied payment (declined instrument).",
        is_simulated=True,
    )
    session.add(event)
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "inject_failure",
        "state": "DENIED",
        "is_simulated": True,
    })

    return {"case_id": case.id, "status": "DENIED", "is_simulated": True}


async def simulate_inject_pending(case_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Inject a PENDING state."""
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    req_id = f"sim-pend-{uuid.uuid4().hex[:8]}"
    attempt = PaymentAttempt(
        order_id=case.order_id,
        request_id=req_id,
        status="PENDING",
        paypal_response_raw=json.dumps({"status": "PENDING", "reason": "PENDING_REVIEW"}),
        is_simulated=True,
    )
    session.add(attempt)

    case.current_policy_state = "PENDING"
    case.status = "PENDING"
    case.permitted_actions = ["RECONCILE"]

    event = CaseEvent(
        case_id=case.id,
        source="WEBHOOK",
        event_type="PAYMENT.CAPTURE.PENDING",
        description="SIMULATION: Payment is pending review with bank.",
        is_simulated=True,
    )
    session.add(event)
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "inject_pending",
        "state": "PENDING",
        "is_simulated": True,
    })

    return {"case_id": case.id, "status": "PENDING", "is_simulated": True}
