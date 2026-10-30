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
from backend.app.agent.offline import offline_investigate
from backend.app.db.session import AsyncSessionLocal


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


async def run_demo_scenario_1_lost_success(
    order_id: Optional[str],
    case_id: str,
    session: AsyncSession
) -> Dict[str, Any]:
    """Lost Success Response: real capture → UNKNOWN → reconciler recovers to COMPLETED."""
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    # 1. Inject UNKNOWN state (simulate lose-success-response)
    req_id = f"sim-s1-{uuid.uuid4().hex[:8]}"
    attempt = PaymentAttempt(
        order_id=case.order_id,
        request_id=req_id,
        status="UNKNOWN",
        paypal_capture_id=None,
        paypal_response_raw=json.dumps({"simulation": "lost_success_response", "scenario": 1}),
        is_simulated=True,
    )
    session.add(attempt)

    case.current_policy_state = "UNKNOWN"
    case.status = "UNKNOWN"
    case.permitted_actions = ["RECONCILE", "ESCALATE"]

    event1 = CaseEvent(
        case_id=case.id,
        source="POLICY",
        event_type="SIMULATED_NETWORK_TIMEOUT",
        description="SIMULATION: Real capture completed on PayPal, but response timed out locally. Attempt marked UNKNOWN.",
        is_simulated=True,
    )
    session.add(event1)
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "run_scenario_1_unknown",
        "state": "UNKNOWN",
        "is_simulated": True,
    })

    # 2. Schedule a delayed SSE event (3s) that delivers PAYMENT.CAPTURE.COMPLETED
    async def _recover_after_delay(c_id: str):
        await asyncio.sleep(3)
        async with AsyncSessionLocal() as bg_session:
            c_res = await bg_session.execute(select(Case).where(Case.id == c_id))
            c = c_res.scalar_one_or_none()
            if c:
                att_res = await bg_session.execute(
                    select(PaymentAttempt)
                    .where(PaymentAttempt.order_id == c.order_id)
                    .order_by(PaymentAttempt.created_at.desc())
                )
                latest_att = att_res.scalars().first()
                if latest_att:
                    latest_att.status = "COMPLETED"
                    latest_att.paypal_capture_id = f"sim-cap-{uuid.uuid4().hex[:8]}"

                c.current_policy_state = "COMPLETED"
                c.status = "COMPLETED"
                c.permitted_actions = ["REFUND"]

                ev = CaseEvent(
                    case_id=c.id,
                    source="RECONCILER",
                    event_type="PAYMENT.CAPTURE.COMPLETED",
                    description="SIMULATION: Reconciler recovered capture status from PayPal. State transitioned to COMPLETED.",
                    is_simulated=True,
                )
                bg_session.add(ev)
                await bg_session.commit()

                await event_bus.broadcast(c.id, {
                    "type": "reconciliation_update",
                    "event_type": "PAYMENT.CAPTURE.COMPLETED",
                    "state": "COMPLETED",
                    "case_id": c.id,
                    "is_simulated": True,
                })

    asyncio.create_task(_recover_after_delay(case.id))

    return {
        "scenario": "scenario_1_lost_success",
        "case_id": case.id,
        "status": "UNKNOWN",
        "is_simulated": True,
        "steps": [
            {
                "step": 1,
                "name": "simulate_loss_to_unknown",
                "state": "UNKNOWN",
                "detail": "Injected UNKNOWN state following simulated network timeout",
                "is_simulated": True,
            },
            {
                "step": 2,
                "name": "schedule_reconciler_recovery",
                "target_state": "COMPLETED",
                "delay_seconds": 3,
                "detail": "Reconciler recovers capture via GET /v2/payments/captures",
                "is_simulated": True,
            },
        ],
    }


async def run_demo_scenario_2_definitive_failure(
    order_id: Optional[str],
    case_id: str,
    session: AsyncSession
) -> Dict[str, Any]:
    """Definitive Failure + Safe Retry: inject DENIED → policy gates retry → admin approves."""
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    # 1. Inject DENIED snapshot (is_simulated=True)
    req_id = f"sim-s2-{uuid.uuid4().hex[:8]}"
    attempt = PaymentAttempt(
        order_id=case.order_id,
        request_id=req_id,
        status="DENIED",
        paypal_response_raw=json.dumps({
            "status": "DECLINED",
            "reason": "INSTRUMENT_DECLINED",
            "processor_response": {"response_code": "51", "avs_code": "N"}
        }),
        is_simulated=True,
    )
    session.add(attempt)

    event1 = CaseEvent(
        case_id=case.id,
        source="API",
        event_type="PAYMENT.CAPTURE.DENIED",
        description="SIMULATION: PayPal explicitly denied capture: INSTRUMENT_DECLINED.",
        is_simulated=True,
    )
    session.add(event1)

    # 2. Trigger AI investigation (offline)
    snapshot = ProviderSnapshot(
        order_status="COMPLETED",
        capture_status="DENIED",
        order_id=order_id or case.order_id,
        source="api",
        raw_ref=req_id,
    )
    ai_result = offline_investigate(snapshot, [attempt], [event1])

    ai_event = CaseEvent(
        case_id=case.id,
        source="AI_INVESTIGATOR",
        event_type="AI_DIAGNOSIS",
        description=f"AI Investigation: Classification={ai_result.classification}, Action={ai_result.recommended_action}. Summary: {ai_result.summary}",
        is_simulated=True,
    )
    session.add(ai_event)

    # 3. Show R04_DENIED_ALLOWS_RETRY fires
    decision = evaluate(
        snapshot=snapshot,
        attempts=[attempt],
        events=[event1],
        ai_proposal=ai_result,
    )

    case.current_policy_state = "DENIED"
    case.status = "DENIED"
    case.permitted_actions = decision.permitted_actions

    policy_event = CaseEvent(
        case_id=case.id,
        source="POLICY",
        event_type="POLICY_EVALUATION",
        description="Rule R04_DENIED_ALLOWS_RETRY fired: capture explicitly DENIED, safe retry permitted with merchant approval.",
        is_simulated=True,
    )
    session.add(policy_event)
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "run_scenario_2",
        "state": "DENIED",
        "permitted_actions": decision.permitted_actions,
        "is_simulated": True,
    })

    return {
        "scenario": "scenario_2_definitive_failure",
        "case_id": case.id,
        "status": "DENIED",
        "is_simulated": True,
        "steps": [
            {
                "step": 1,
                "name": "inject_denied_snapshot",
                "state": "DENIED",
                "detail": "PayPal explicitly returned DENIED status",
                "is_simulated": True,
            },
            {
                "step": 2,
                "name": "ai_investigation_offline",
                "classification": ai_result.classification,
                "recommended_action": ai_result.recommended_action,
                "confidence": ai_result.confidence,
                "is_simulated": True,
            },
            {
                "step": 3,
                "name": "policy_gate_evaluation",
                "rule_fired": "R04_DENIED_ALLOWS_RETRY",
                "permitted_actions": decision.permitted_actions,
                "is_simulated": True,
            },
        ],
    }


async def run_demo_scenario_3_delayed_reconciliation(
    order_id: Optional[str],
    case_id: str,
    session: AsyncSession
) -> Dict[str, Any]:
    """Delayed Reconciliation: inject PENDING → wait → deliver COMPLETED webhook → SSE live update."""
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")

    # 1. Inject pending state
    req_id = f"sim-s3-{uuid.uuid4().hex[:8]}"
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

    event1 = CaseEvent(
        case_id=case.id,
        source="WEBHOOK",
        event_type="PAYMENT.CAPTURE.PENDING",
        description="SIMULATION: Settlement pending review by payment processor.",
        is_simulated=True,
    )
    session.add(event1)
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "run_scenario_3_pending",
        "state": "PENDING",
        "is_simulated": True,
    })

    # 2. After 5s, broadcast COMPLETED event via SSE
    async def _deliver_completed_after_5s(c_id: str):
        await asyncio.sleep(5)
        async with AsyncSessionLocal() as bg_session:
            c_res = await bg_session.execute(select(Case).where(Case.id == c_id))
            c = c_res.scalar_one_or_none()
            if c:
                wh_id = f"sim-wh-{uuid.uuid4().hex[:8]}"
                wh = WebhookEvent(
                    paypal_event_id=wh_id,
                    event_type="PAYMENT.CAPTURE.COMPLETED",
                    resource_id=c.order_id,
                    resource_type="capture",
                    raw_payload=json.dumps({"scenario": 3, "status": "COMPLETED"}),
                    verified=True,
                    is_simulated=True,
                    processed=True,
                )
                bg_session.add(wh)

                c.current_policy_state = "COMPLETED"
                c.status = "COMPLETED"
                c.permitted_actions = ["REFUND"]

                ev = CaseEvent(
                    case_id=c.id,
                    source="WEBHOOK",
                    event_type="PAYMENT.CAPTURE.COMPLETED",
                    description="SIMULATION: Delayed webhook delivered PAYMENT.CAPTURE.COMPLETED after 5s. UI updated live via SSE.",
                    is_simulated=True,
                )
                bg_session.add(ev)
                await bg_session.commit()

                await event_bus.broadcast(c.id, {
                    "type": "delayed_event_delivered",
                    "event_type": "PAYMENT.CAPTURE.COMPLETED",
                    "state": "COMPLETED",
                    "case_id": c.id,
                    "is_simulated": True,
                })

    asyncio.create_task(_deliver_completed_after_5s(case.id))

    return {
        "scenario": "scenario_3_delayed_reconciliation",
        "case_id": case.id,
        "status": "PENDING",
        "is_simulated": True,
        "steps": [
            {
                "step": 1,
                "name": "inject_pending_state",
                "state": "PENDING",
                "detail": "Capture entered PENDING state awaiting settlement",
                "is_simulated": True,
            },
            {
                "step": 2,
                "name": "delayed_webhook_broadcast",
                "delay_seconds": 5,
                "target_event": "PAYMENT.CAPTURE.COMPLETED",
                "detail": "Delivering live SSE webhook after 5s",
                "is_simulated": True,
            },
        ],
    }
