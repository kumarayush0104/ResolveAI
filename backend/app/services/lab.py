import asyncio
import json
import uuid
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Case, Order, PaymentAttempt, WebhookEvent, CaseEvent
from backend.app.paypal.client import ProviderSnapshot
from backend.app.policy.engine import evaluate
from backend.app.services.stream_bus import event_bus
from backend.app.agent.offline import offline_investigate
from backend.app.db.session import AsyncSessionLocal

DELAYED_SCENARIO_SECONDS = 5


async def _simulate_lost_response(session: AsyncSession, case: Case, order: Order) -> Dict[str, Any]:
    """Create a local-only UNKNOWN attempt without contacting PayPal."""
    attempt = PaymentAttempt(
        order_id=order.id,
        request_id=f"sim-lost-{uuid.uuid4().hex[:12]}",
        status="UNKNOWN",
        paypal_response_raw=json.dumps({"simulation": "lost_success_response"}),
        is_simulated=True,
    )
    session.add(attempt)
    case.current_policy_state = "UNKNOWN"
    case.status = "UNKNOWN"
    case.permitted_actions = ["RECONCILE", "ESCALATE"]

    session.add(CaseEvent(
        case_id=case.id,
        source="POLICY",
        event_type="SIMULATED_NETWORK_TIMEOUT",
        description="SIMULATION: Capture response marked as lost; local attempt is UNKNOWN. No PayPal request was made.",
        is_simulated=True,
    ))
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "lose_success_response",
        "state": "UNKNOWN",
        "is_simulated": True,
    })
    return {"attempt_id": attempt.id, "status": "UNKNOWN", "is_simulated": True}


def _schedule_simulated_reconcile(case_id: str, delay: float = 3.0) -> None:
    """Resolve the demonstration attempt using simulated evidence, never a provider request."""
    async def _run():
        await asyncio.sleep(delay)
        async with AsyncSessionLocal() as bg_session:
            case = (await bg_session.execute(
                select(Case).where(Case.id == case_id)
            )).scalar_one_or_none()
            if not case:
                return

            attempts = list((await bg_session.execute(
                select(PaymentAttempt).where(
                    PaymentAttempt.order_id == case.order_id,
                    PaymentAttempt.is_simulated.is_(True),
                )
            )).scalars().all())
            unknown_attempts = [attempt for attempt in attempts if attempt.status == "UNKNOWN"]
            if not unknown_attempts:
                return

            for attempt in unknown_attempts:
                attempt.status = "COMPLETED"
            snapshot = ProviderSnapshot(
                order_status="COMPLETED",
                capture_status="COMPLETED",
                order_id=case.order_id,
                source="api",
                raw_ref="fault-lab-simulated-reconciliation",
                is_simulated=True,
                note="Simulated evidence; no PayPal transaction was created.",
            )
            decision = evaluate(snapshot=snapshot, attempts=attempts)
            old_state = case.current_policy_state
            case.current_policy_state = decision.state.value
            case.status = decision.state.value
            case.permitted_actions = decision.permitted_actions
            bg_session.add(CaseEvent(
                case_id=case.id,
                source="RECONCILER",
                event_type="SIMULATED_RECONCILIATION",
                description=f"SIMULATION: Status check resolved the demonstration attempt as {decision.state.value}. No PayPal request was made.",
                is_simulated=True,
            ))
            await bg_session.commit()
            await event_bus.broadcast(case.id, {
                "type": "reconciliation_update",
                "case_id": case.id,
                "old_state": old_state,
                "new_state": decision.state.value,
                "rule_fired": decision.rule_fired,
                "is_simulated": True,
            })

    asyncio.create_task(_run())


async def simulate_lose_success_response(case_id: str, session: AsyncSession) -> Dict[str, Any]:
    """Single fault injection: the response is lost, then local simulated evidence resolves it."""
    case = (await session.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")
    order = (await session.execute(select(Order).where(Order.id == case.order_id))).scalar_one()

    info = await _simulate_lost_response(session, case, order)
    _schedule_simulated_reconcile(case.id)
    return {
        "case_id": case.id,
        "status": "UNKNOWN",
        "is_simulated": True,
        "attempt_id": info["attempt_id"],
        "message": "Response loss simulated. A local status check will resolve it; no PayPal request was made.",
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

    event = CaseEvent(
        case_id=case.id,
        source="API",
        event_type="PAYMENT_DENIED",
        description="SIMULATION: Provider explicitly denied payment (declined instrument).",
        is_simulated=True,
    )
    session.add(event)
    decision = evaluate(
        snapshot=ProviderSnapshot(
            order_status="COMPLETED",
            capture_status="DENIED",
            order_id=case.order_id,
            source="api",
            raw_ref=req_id,
            is_simulated=True,
        ),
        attempts=[attempt],
        events=[event],
    )
    case.current_policy_state = decision.state.value
    case.status = decision.state.value
    case.permitted_actions = decision.permitted_actions
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "inject_failure",
        "state": decision.state.value,
        "permitted_actions": decision.permitted_actions,
        "requires_approval": decision.requires_approval,
        "is_simulated": True,
    })

    return {
        "case_id": case.id,
        "status": decision.state.value,
        "permitted_actions": decision.permitted_actions,
        "requires_approval": decision.requires_approval,
        "is_simulated": True,
    }


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

    event = CaseEvent(
        case_id=case.id,
        source="WEBHOOK",
        event_type="PAYMENT.CAPTURE.PENDING",
        description="SIMULATION: Payment is pending review with bank.",
        is_simulated=True,
    )
    session.add(event)
    decision = evaluate(
        snapshot=ProviderSnapshot(
            order_status="PENDING",
            capture_status="PENDING",
            order_id=case.order_id,
            source="api",
            raw_ref=req_id,
            is_simulated=True,
        ),
        attempts=[attempt],
        events=[event],
    )
    case.current_policy_state = decision.state.value
    case.status = decision.state.value
    case.permitted_actions = decision.permitted_actions
    await session.commit()

    await event_bus.broadcast(case.id, {
        "type": "lab_event",
        "action": "inject_pending",
        "state": decision.state.value,
        "is_simulated": True,
    })

    return {"case_id": case.id, "status": decision.state.value, "is_simulated": True}


async def run_demo_scenario_1_lost_success(
    order_id: Optional[str],
    case_id: str,
    session: AsyncSession
) -> Dict[str, Any]:
    """Scenario 1: simulate an unknown result and resolve it using local simulated evidence."""
    case = (await session.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise ValueError("Case not found")
    order = (await session.execute(select(Order).where(Order.id == case.order_id))).scalar_one()

    await _simulate_lost_response(session, case, order)
    _schedule_simulated_reconcile(case.id)

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
                "detail": "A local payment attempt is marked UNKNOWN. No PayPal request was made.",
                "is_simulated": True,
            },
            {
                "step": 2,
                "name": "simulated_reconciliation",
                "target_state": "COMPLETED",
                "delay_seconds": 3,
                "detail": "A simulated status check resolves the case as COMPLETED; no money moves.",
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
    """Simulate PENDING followed by a delayed completion update over SSE."""
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

    # 2. After a short delay, broadcast COMPLETED event via SSE
    async def _deliver_completed_after_5s(c_id: str):
        await asyncio.sleep(DELAYED_SCENARIO_SECONDS)
        async with AsyncSessionLocal() as bg_session:
            c_res = await bg_session.execute(select(Case).where(Case.id == c_id))
            c = c_res.scalar_one_or_none()
            if c:
                attempts = list((await bg_session.execute(
                    select(PaymentAttempt).where(
                        PaymentAttempt.order_id == c.order_id,
                        PaymentAttempt.is_simulated.is_(True),
                    )
                )).scalars().all())
                for attempt in attempts:
                    if attempt.status == "PENDING":
                        attempt.status = "COMPLETED"
                snapshot = ProviderSnapshot(
                    order_status="COMPLETED",
                    capture_status="COMPLETED",
                    order_id=c.order_id,
                    source="webhook",
                    raw_ref="fault-lab-scenario-3",
                    is_simulated=True,
                    note="Simulated delayed completion; no PayPal transaction was created.",
                )
                decision = evaluate(snapshot=snapshot, attempts=attempts)
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

                c.current_policy_state = decision.state.value
                c.status = decision.state.value
                c.permitted_actions = decision.permitted_actions

                ev = CaseEvent(
                    case_id=c.id,
                    source="WEBHOOK",
                    event_type="PAYMENT.CAPTURE.COMPLETED",
                    description=f"SIMULATION: Delayed completion delivered after {DELAYED_SCENARIO_SECONDS}s and checked by policy. No PayPal transaction was created.",
                    is_simulated=True,
                )
                bg_session.add(ev)
                await bg_session.commit()

                await event_bus.broadcast(c.id, {
                    "type": "delayed_event_delivered",
                    "event_type": "PAYMENT.CAPTURE.COMPLETED",
                    "state": decision.state.value,
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
                "delay_seconds": DELAYED_SCENARIO_SECONDS,
                "target_event": "PAYMENT.CAPTURE.COMPLETED",
                "detail": "Delivering live SSE webhook after 5s",
                "is_simulated": True,
            },
        ],
    }
