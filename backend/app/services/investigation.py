import hashlib
import json
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Case, Order, PaymentAttempt, CaseEvent, AgentRun
from backend.app.paypal.orders import get_order, get_capture
from backend.app.paypal.client import ProviderSnapshot
from backend.app.policy.engine import evaluate
from backend.app.agent.investigator import run_investigation
from backend.app.services.stream_bus import event_bus
from backend.app.services.status_check import check_payment_status


async def run_case_investigation(
    case: Case,
    session: AsyncSession,
) -> Dict[str, Any]:
    """Run full investigation workflow on a case:
    1. Fetch authoritative PayPal snapshot
    2. Run AI investigator (with offline fallback)
    3. Authoritative policy verification (policy always wins)
    4. Persist AgentRun and CaseEvent
    5. Broadcast updates via SSE
    """
    # 1. Fetch related data
    await session.refresh(case, ["order", "events", "approvals"])
    order = case.order

    attempts_res = await session.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
    )
    attempts = list(attempts_res.scalars().all())

    # Get authoritative status from PayPal (Orders API + Payments API + Transaction Search)
    status_report = await check_payment_status(order, attempts)
    snapshot = status_report.snapshot

    # 2. Run AI Investigator
    investigation_result = await run_investigation(
        snapshot=snapshot,
        attempts=attempts,
        events=case.events,
        status_report=status_report.to_dict(),
    )

    ai_proposal = {
        "recommended_action": investigation_result.recommended_action,
        "classification": investigation_result.classification,
    }

    # 3. Policy Gate Evaluation (Rule R08: AI is advisory, policy engine is authoritative)
    policy_decision = evaluate(
        snapshot=snapshot,
        attempts=attempts,
        events=case.events,
        ai_proposal=ai_proposal,
    )

    # Check if policy overrode AI proposal
    ai_overridden = any(
        b.get("rule_id") == "R08_AI_IS_ADVISORY" for b in policy_decision.blocked_actions
    )

    # Calculate input hash for reproducibility
    hash_input = f"{order.id}:{snapshot.capture_status}:{len(case.events)}"
    input_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    # 4. Record AgentRun
    agent_run = AgentRun(
        case_id=case.id,
        input_hash=input_hash,
        classification=investigation_result.classification,
        summary=investigation_result.summary,
        buyer_message=investigation_result.buyer_message,
        seller_message=investigation_result.seller_message,
        evidence_refs=investigation_result.evidence_refs,
        unknowns=investigation_result.unknowns,
        recommended_action=investigation_result.recommended_action,
        confidence=investigation_result.confidence,
        raw_output=investigation_result.model_dump_json(),
        ai_overridden=ai_overridden,
    )
    session.add(agent_run)

    # Record case event
    event = CaseEvent(
        case_id=case.id,
        source="AI",
        event_type="AI_INVESTIGATION_COMPLETED",
        description=f"Investigation completed. Recommended: {investigation_result.recommended_action}. AI overridden: {ai_overridden}",
        is_simulated=getattr(snapshot, "is_simulated", False),
    )
    session.add(event)

    # Update case state and permitted actions
    case.current_policy_state = policy_decision.state.value
    case.permitted_actions = policy_decision.permitted_actions
    case.status = policy_decision.state.value

    await session.commit()
    await session.refresh(case)

    # 5. Broadcast to SSE subscribers
    await event_bus.broadcast(case.id, {
        "type": "investigation_completed",
        "case_id": case.id,
        "state": case.current_policy_state,
        "permitted_actions": case.permitted_actions,
        "ai_overridden": ai_overridden,
        "summary": agent_run.summary,
    })

    return {
        "case_id": case.id,
        "investigation": investigation_result.model_dump(),
        "policy_decision": policy_decision.to_dict(),
        "ai_overridden": ai_overridden,
    }
