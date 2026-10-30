import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
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
from backend.app.services.investigation import run_case_investigation
from backend.app.agent.prompts import wrap_untrusted_text
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

    # Initial snapshot
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

    # Authoritative live PayPal snapshot
    try:
        capture_id = next((a.paypal_capture_id for a in attempts if a.paypal_capture_id), None)
        if capture_id:
            snapshot = await get_capture(capture_id)
        else:
            snapshot = await get_order(case.order.paypal_order_id)
    except Exception:
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
    """Trigger AI investigation with policy guardrails."""
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

    result_data = await run_case_investigation(case, session)
    return result_data


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
    if action_upper not in case.permitted_actions:
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
