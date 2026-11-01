import uuid
import json
import hashlib
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.session import get_db
from backend.app.db.models import Case, Order, CaseEvent, ActionApproval, AgentRun, PaymentAttempt, User
from backend.app.security.auth import get_current_user
from backend.app.security.permissions import require_case_access, require_order_access
from backend.app.policy.engine import evaluate
from backend.app.paypal.orders import get_order, get_capture, refund_capture
from backend.app.paypal.client import ProviderSnapshot
from backend.app.services.status_check import check_payment_status
from backend.app.services.reconciliation import reconcile_case
from backend.app.services.investigation import run_case_investigation
from backend.app.agent.prompts import wrap_untrusted_text
from backend.app.agent.investigator import stream_investigation
from backend.app.agent.schemas import AgentInvestigationResult
from backend.app.services.stream_bus import event_bus

router = APIRouter(prefix="/cases", tags=["cases"])


class CreateCaseRequest(BaseModel):
    order_id: str = Field(..., description="ID or PayPal Order ID to open a case for")


class CaseMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class ApproveActionRequest(BaseModel):
    notes: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def open_case(
    payload: CreateCaseRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Open or retrieve a dispute/investigation case for an order."""
    # Find order
    stmt = select(Order).where((Order.id == payload.order_id) | (Order.paypal_order_id == payload.order_id))
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    require_order_access(order, current_user)

    # Check if case already exists for this order
    case_stmt = select(Case).where(Case.order_id == order.id)
    case_res = await session.execute(case_stmt)
    existing_case = case_res.scalar_one_or_none()
    if existing_case:
        return {
            "id": existing_case.id,
            "order_id": order.id,
            "status": existing_case.status,
            "current_policy_state": existing_case.current_policy_state,
            "message": "Existing case retrieved",
        }

    # Fetch attempts to evaluate initial state
    att_res = await session.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
    )
    attempts = att_res.scalars().all()

    # Initial snapshot: ask PayPal. Fall back to local knowledge only if every source is unreachable.
    init_report = await check_payment_status(order, list(attempts))
    if init_report.reachable:
        init_snap = init_report.snapshot
    else:
        init_snap = ProviderSnapshot(
            order_status=order.status,
            capture_status="COMPLETED" if order.status == "COMPLETED" else "PENDING",
            order_id=order.paypal_order_id,
            source="api",
        )
    init_decision = evaluate(snapshot=init_snap, attempts=attempts, events=[])

    case = Case(
        order_id=order.id,
        buyer_id=order.user_id,
        status=init_decision.state.value,
        current_policy_state=init_decision.state.value,
        permitted_actions=init_decision.permitted_actions,
    )
    session.add(case)
    await session.flush()

    # Add initial case event
    event = CaseEvent(
        case_id=case.id,
        source="USER",
        event_type="CASE_OPENED",
        description=f"Case opened by {current_user.role} ({current_user.email})",
        is_simulated=False,
    )
    session.add(event)
    await session.commit()
    await session.refresh(case)

    return {
        "id": case.id,
        "order_id": order.id,
        "status": case.status,
        "current_policy_state": case.current_policy_state,
        "permitted_actions": case.permitted_actions,
    }


@router.get("/{case_id}")
async def get_case_detail(
    case_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Retrieve full case detail including evidence bundle, policy evaluation, and event log."""
    stmt = (
        select(Case)
        .options(
            selectinload(Case.order),
            selectinload(Case.events),
            selectinload(Case.agent_runs),
            selectinload(Case.approvals),
        )
        .where(Case.id == case_id)
    )
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    require_case_access(case, current_user)

    # Attempts
    att_res = await session.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == case.order_id)
    )
    attempts = att_res.scalars().all()

    # Authoritative live PayPal status: Orders API + Payments API + Transaction Search
    status_report = await check_payment_status(case.order, list(attempts))
    snapshot = status_report.snapshot
    if not status_report.reachable:
        snapshot = ProviderSnapshot(
            order_status=case.order.status,
            capture_status=case.current_policy_state,
            order_id=case.order.paypal_order_id,
            source="api",
            raw_ref="Snapshot unavailable during read",
        )

    # Compute current authoritative policy decision
    policy_decision = evaluate(
        snapshot=snapshot,
        attempts=attempts,
        events=case.events,
    )

    return {
        "id": case.id,
        "order_id": case.order_id,
        "buyer_id": case.buyer_id,
        "status": case.status,
        "current_policy_state": case.current_policy_state,
        "permitted_actions": case.permitted_actions,
        "evidence_bundle": {
            "snapshot": snapshot.to_dict(),
            "status_report": status_report.to_dict(),
            "attempts": [
                {
                    "id": a.id,
                    "request_id": a.request_id,
                    "status": a.status,
                    "capture_id": a.paypal_capture_id,
                    "is_simulated": a.is_simulated,
                    "created_at": a.created_at.isoformat(),
                }
                for a in attempts
            ],
            "order": {
                "id": case.order.id,
                "paypal_order_id": case.order.paypal_order_id,
                "amount": case.order.amount,
                "currency": case.order.currency,
                "status": case.order.status,
            },
        },
        "policy_decision": policy_decision.to_dict(),
        "events": [
            {
                "id": e.id,
                "source": e.source,
                "event_type": e.event_type,
                "description": e.description,
                "is_simulated": e.is_simulated,
                "created_at": e.created_at.isoformat(),
            }
            for e in case.events
        ],
        "latest_agent_run": case.agent_runs[0].summary if case.agent_runs else None,
        "approvals": [
            {
                "id": ap.id,
                "action": ap.action,
                "approved_by": ap.approved_by,
                "approved_at": ap.approved_at.isoformat(),
            }
            for ap in case.approvals
        ],
    }


@router.post("/{case_id}/investigate")
async def trigger_investigation(
    case_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Trigger AI investigation with SSE streaming tool-call loop and policy guardrails."""
    stmt = (
        select(Case)
        .options(
            selectinload(Case.order),
            selectinload(Case.events),
            selectinload(Case.approvals),
        )
        .where(Case.id == case_id)
    )
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    require_case_access(case, current_user)

    order = case.order
    att_res = await session.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
    )
    attempts = list(att_res.scalars().all())

    # Extract user messages
    messages = [
        e.description for e in case.events if e.source == "USER" and e.event_type == "CASE_MESSAGE"
    ]

    # Authoritative live PayPal status (all sources). Unreachable -> UNKNOWN, never a failure.
    status_report = await check_payment_status(order, attempts)
    snapshot = status_report.snapshot

    async def generate_sse():
        final_result_data = None
        async for event in stream_investigation(
            order_id=order.paypal_order_id,
            case_id=case.id,
            snapshot=snapshot,
            attempts=attempts,
            events=case.events,
            messages=messages,
            session=session,
            status_report=status_report.to_dict(),
        ):
            if event.get("type") == "final":
                final_result_data = event.get("result")
            yield f"data: {json.dumps(event)}\n\n"

        # On completion, persist AgentRun and update case status via policy engine
        if final_result_data:
            try:
                result_obj = AgentInvestigationResult(**final_result_data)
                ai_proposal = {
                    "recommended_action": result_obj.recommended_action,
                    "classification": result_obj.classification,
                }
                policy_decision = evaluate(
                    snapshot=snapshot,
                    attempts=attempts,
                    events=case.events,
                    ai_proposal=ai_proposal,
                )
                ai_overridden = any(
                    b.get("rule_id") == "R08_AI_IS_ADVISORY" for b in policy_decision.blocked_actions
                )
                hash_input = f"{order.id}:{snapshot.capture_status if snapshot else 'UNKNOWN'}:{len(case.events)}"
                input_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

                agent_run = AgentRun(
                    case_id=case.id,
                    input_hash=input_hash,
                    classification=result_obj.classification,
                    summary=result_obj.summary,
                    buyer_message=result_obj.buyer_message,
                    seller_message=result_obj.seller_message,
                    evidence_refs=result_obj.evidence_refs,
                    unknowns=result_obj.unknowns,
                    recommended_action=result_obj.recommended_action,
                    confidence=result_obj.confidence,
                    raw_output=result_obj.model_dump_json(),
                    ai_overridden=ai_overridden,
                )
                session.add(agent_run)

                case_ev = CaseEvent(
                    case_id=case.id,
                    source="AI",
                    event_type="AI_INVESTIGATION_COMPLETED",
                    description=f"Investigation completed. Recommended: {result_obj.recommended_action}. AI overridden: {ai_overridden}",
                    is_simulated=getattr(snapshot, "is_simulated", False),
                )
                session.add(case_ev)

                case.current_policy_state = policy_decision.state.value
                case.permitted_actions = policy_decision.permitted_actions
                case.status = policy_decision.state.value

                await session.commit()

                await event_bus.broadcast(case.id, {
                    "type": "investigation_completed",
                    "case_id": case.id,
                    "state": case.current_policy_state,
                    "permitted_actions": case.permitted_actions,
                    "ai_overridden": ai_overridden,
                    "summary": agent_run.summary,
                })
            except Exception as e:
                # Log error and continue
                pass

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{case_id}/messages")
async def add_case_message(
    case_id: str,
    payload: CaseMessageRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Add a message from buyer or seller to the case.
    Wrapped in `<untrusted_user_text>` tags to prevent prompt injection.
    """
    stmt = select(Case).where(Case.id == case_id)
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    require_case_access(case, current_user)

    safe_text = wrap_untrusted_text(payload.message)
    event = CaseEvent(
        case_id=case.id,
        source="USER",
        event_type="CASE_MESSAGE",
        description=f"[{current_user.role.upper()}]: {safe_text}",
        is_simulated=False,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    await event_bus.broadcast(case.id, {
        "type": "new_message",
        "case_id": case.id,
        "sender": current_user.role,
        "message": safe_text,
    })

    return {
        "event_id": event.id,
        "case_id": case.id,
        "message": safe_text,
        "created_at": event.created_at.isoformat(),
    }


@router.post("/{case_id}/actions/{action}/approve")
async def approve_case_action(
    case_id: str,
    action: str,
    payload: ApproveActionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Approve a permitted policy action (e.g. REFUND or ALLOW_RETRY)."""
    stmt = select(Case).options(selectinload(Case.order)).where(Case.id == case_id)
    result = await session.execute(stmt)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    require_case_access(case, current_user)

    action_upper = action.upper()
    # RECONCILE only reads PayPal, so it is allowed in every state. Everything else is policy-gated.
    if action_upper != "RECONCILE" and action_upper not in case.permitted_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action '{action_upper}' is not currently permitted by policy engine. Permitted: {case.permitted_actions}",
        )

    # Record action approval
    approval = ActionApproval(
        case_id=case.id,
        action=action_upper,
        approved_by=current_user.id,
        evidence_snapshot={"state": case.current_policy_state, "notes": payload.notes},
    )
    session.add(approval)

    # Perform action side-effects
    if action_upper == "RECONCILE":
        # "Check PayPal again": run a real multi-source check and let the policy engine re-decide.
        session.add(approval)
        await session.flush()
        out = await reconcile_case(case.id, session, record_evidence=True)
        await session.refresh(case)
        await event_bus.broadcast(case.id, {
            "type": "action_approved",
            "action": action_upper,
            "case_id": case.id,
            "state": case.current_policy_state,
        })
        return {
            "case_id": case.id,
            "action": action_upper,
            "state": case.current_policy_state,
            "permitted_actions": case.permitted_actions,
            "state_changed": out["state_changed"] if out else False,
            "report": out["report"] if out else None,
        }

    if action_upper == "REFUND":
        # Find capture ID
        att_res = await session.execute(
            select(PaymentAttempt).where(PaymentAttempt.order_id == case.order_id)
        )
        attempts = att_res.scalars().all()
        capture_id = next((a.paypal_capture_id for a in attempts if a.paypal_capture_id), None)
        if not capture_id:
            raise HTTPException(status_code=400, detail="Cannot refund: No valid capture ID found.")

        # Execute refund on PayPal
        req_id = f"ref-{uuid.uuid4().hex[:12]}"
        try:
            refund_res = await refund_capture(
                capture_id=capture_id,
                amount=case.order.amount,
                currency=case.order.currency,
                request_id=req_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"PayPal refund call failed: {exc}")

        # Update case state to REFUND_PENDING (R09: refund requested != completed)
        case.current_policy_state = "REFUND_PENDING"
        case.status = "REFUND_PENDING"
        case.permitted_actions = ["RECONCILE"]

        event = CaseEvent(
            case_id=case.id,
            source="POLICY",
            event_type="REFUND_REQUESTED",
            description=f"Refund of {case.order.amount} {case.order.currency} submitted to PayPal. Status: REFUND_PENDING.",
        )
        session.add(event)

    elif action_upper == "ALLOW_RETRY":
        case.current_policy_state = "RETRY_ALLOWED"
        case.status = "RETRY_ALLOWED"
        case.permitted_actions = ["RETRY"]

        event = CaseEvent(
            case_id=case.id,
            source="POLICY",
            event_type="RETRY_APPROVED",
            description="User/merchant approved a fresh payment retry.",
        )
        session.add(event)

    await session.commit()
    await session.refresh(case)

    await event_bus.broadcast(case.id, {
        "type": "action_approved",
        "action": action_upper,
        "case_id": case.id,
        "state": case.current_policy_state,
    })

    return {
        "case_id": case.id,
        "action": action_upper,
        "state": case.current_policy_state,
        "permitted_actions": case.permitted_actions,
    }
