import uuid
import json
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.db.models import Order, PaymentAttempt, User
from backend.app.security.auth import get_current_user
from backend.app.security.permissions import require_order_access
from backend.app.paypal.orders import create_order, capture_order, get_order
from backend.app.paypal.client import ProviderSnapshot
from backend.app.policy.rules import R01_COMPLETED_BLOCKS_RETRY, R07_ONE_ACTIVE_ATTEMPT

router = APIRouter(prefix="/orders", tags=["orders"])


class CreateOrderRequest(BaseModel):
    amount: float = Field(..., gt=0.0, description="Purchase amount")
    currency: str = Field(default="USD", max_length=3)
    request_id: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_new_order(
    payload: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    paypal_request_id: Optional[str] = Header(None, alias="PayPal-Request-Id"),
):
    """Create a new PayPal order, persist to database, and return approval URL."""
    req_id = payload.request_id or paypal_request_id or str(uuid.uuid4())

    try:
        paypal_res = await create_order(
            amount=payload.amount,
            currency=payload.currency,
            request_id=req_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to initiate order with PayPal: {exc}",
        )

    order = Order(
        paypal_order_id=paypal_res["order_id"],
        user_id=current_user.id,
        amount=payload.amount,
        currency=payload.currency,
        status="CREATED",
        paypal_approval_url=paypal_res.get("approval_url"),
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    return {
        "id": order.id,
        "order_id": order.paypal_order_id,
        "paypal_order_id": order.paypal_order_id,
        "amount": order.amount,
        "currency": order.currency,
        "status": order.status,
        "approval_url": order.paypal_approval_url,
    }


@router.get("/{order_id}")
async def get_order_by_id(
    order_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Fetch order details and authoritative normalized PayPal snapshot."""
    # Lookup by internal UUID or PayPal Order ID
    stmt = select(Order).where((Order.id == order_id) | (Order.paypal_order_id == order_id))
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    require_order_access(order, current_user)

    # Fetch live snapshot from PayPal
    try:
        snapshot = await get_order(order.paypal_order_id)
    except Exception:
        snapshot = ProviderSnapshot(
            order_status=order.status,
            capture_status="UNKNOWN",
            order_id=order.paypal_order_id,
            source="api",
            raw_ref="PayPal order fetch unreachable",
        )

    # Fetch attempts
    att_stmt = select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
    att_res = await session.execute(att_stmt)
    attempts = att_res.scalars().all()

    return {
        "id": order.id,
        "paypal_order_id": order.paypal_order_id,
        "amount": order.amount,
        "currency": order.currency,
        "status": order.status,
        "approval_url": order.paypal_approval_url,
        "snapshot": snapshot.to_dict(),
        "attempts": [
            {
                "id": a.id,
                "request_id": a.request_id,
                "status": a.status,
                "capture_id": a.paypal_capture_id,
                "is_simulated": a.is_simulated,
            }
            for a in attempts
        ],
    }


@router.post("/{order_id}/capture")
async def capture_order_payment(
    order_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    paypal_request_id: Optional[str] = Header(None, alias="PayPal-Request-Id"),
):
    """Authoritative capture endpoint enforcing idempotency and the single-active-attempt rule."""
    stmt = select(Order).where((Order.id == order_id) | (Order.paypal_order_id == order_id))
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    require_order_access(order, current_user)

    # 1. R01: If already completed, block retry
    if order.status == "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "rule_id": R01_COMPLETED_BLOCKS_RETRY,
                "message": "Payment is already completed. Duplicate capture blocked.",
            },
        )

    # 2. Check for active attempts (R07_ONE_ACTIVE_ATTEMPT)
    att_stmt = select(PaymentAttempt).where(
        PaymentAttempt.order_id == order.id,
        PaymentAttempt.status.notin_(["COMPLETED", "DENIED", "UNKNOWN"]),
    )
    active_attempts = (await session.execute(att_stmt)).scalars().all()
    if active_attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "rule_id": R07_ONE_ACTIVE_ATTEMPT,
                "message": "Another payment attempt is currently active. Duplicate capture blocked.",
            },
        )

    # 3. Create active attempt record
    req_id = paypal_request_id or f"cap-{uuid.uuid4().hex}"
    attempt = PaymentAttempt(
        order_id=order.id,
        request_id=req_id,
        status="PENDING",
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)

    # 4. Call PayPal capture
    snapshot = await capture_order(order.paypal_order_id, request_id=req_id)

    # 5. Update attempt status
    attempt.status = snapshot.capture_status
    attempt.paypal_capture_id = snapshot.capture_id
    attempt.paypal_response_raw = snapshot.raw_ref
    attempt.is_simulated = snapshot.is_simulated

    if snapshot.capture_status == "COMPLETED":
        order.status = "COMPLETED"
    elif snapshot.capture_status == "DENIED":
        order.status = "DENIED"

    await session.commit()
    await session.refresh(attempt)

    return {
        "order_id": order.id,
        "paypal_order_id": order.paypal_order_id,
        "attempt_id": attempt.id,
        "snapshot": snapshot.to_dict(),
        "status": attempt.status,
    }
