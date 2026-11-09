import uuid
import json
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.db.models import Order, OrderLineItem, PaymentAttempt, Product, User, Case, CaseEvent
from backend.app.security.auth import get_current_user
from backend.app.security.permissions import require_order_access
from backend.app.paypal.orders import create_order, capture_order, get_order
from backend.app.paypal.client import ProviderSnapshot
from backend.app.policy.rules import (
    R01_COMPLETED_BLOCKS_RETRY,
    R02_PENDING_BLOCKS_RETRY,
    R03_UNKNOWN_FAILS_CLOSED,
    R07_ONE_ACTIVE_ATTEMPT,
)
from backend.app.services.reconciliation import reconcile_order, reconcile_case
from backend.app.services.status_check import check_payment_status

router = APIRouter(prefix="/orders", tags=["orders"])


class CreateOrderItem(BaseModel):
    product_id: str
    quantity: int = Field(..., ge=1, le=99)


class CreateOrderRequest(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0.0, description="Legacy purchase amount")
    currency: str = Field(default="USD", max_length=3)
    request_id: Optional[str] = None
    items: List[CreateOrderItem] = Field(default_factory=list)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_new_order(
    payload: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    paypal_request_id: Optional[str] = Header(None, alias="PayPal-Request-Id"),
):
    """Create a PayPal order using the current catalog prices and persist its item snapshot."""
    req_id = payload.request_id or paypal_request_id or str(uuid.uuid4())
    order_items = []
    if payload.items:
        if payload.currency.upper() != "USD":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Catalog items are priced in USD")
        product_ids = {item.product_id for item in payload.items}
        products = (await session.execute(
            select(Product).where(Product.id.in_(product_ids), Product.active.is_(True))
        )).scalars().all()
        by_id = {product.id: product for product in products}
        if len(by_id) != len(product_ids):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "One or more cart items are unavailable")
        subtotal = Decimal("0.00")
        for item in payload.items:
            product = by_id[item.product_id]
            price = Decimal(str(product.price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal += price * item.quantity
            order_items.append((product, item.quantity, price))
        amount = float(subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    elif payload.amount is not None:
        amount = payload.amount
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide cart items or an amount")

    try:
        paypal_res = await create_order(
            amount=amount,
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
        amount=amount,
        currency=payload.currency,
        status="CREATED",
        paypal_approval_url=paypal_res.get("approval_url"),
    )
    session.add(order)
    await session.flush()
    if order_items:
        session.add_all([
            OrderLineItem(
                order_id=order.id,
                product_id=product.id,
                name=product.name,
                quantity=quantity,
                unit_price=float(price),
            )
            for product, quantity, price in order_items
        ])
    await session.commit()
    await session.refresh(order)

    return {
        "id": order.id,
        "order_id": order.paypal_order_id,
        "paypal_order_id": order.paypal_order_id,
        "amount": order.amount,
        "currency": order.currency,
        "items": [
            {"product_id": product.id, "name": product.name, "quantity": quantity, "unit_price": float(price)}
            for product, quantity, price in order_items
        ],
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


async def _get_order_or_404(session: AsyncSession, order_id: str, user: User) -> Order:
    stmt = select(Order).where((Order.id == order_id) | (Order.paypal_order_id == order_id))
    order = (await session.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    require_order_access(order, user)
    return order


async def _record_block(session: AsyncSession, order: Order, rule_id: str, message: str) -> None:
    """Put a blocked duplicate on the case timeline (if there is a case) so the metric is real."""
    case = (await session.execute(select(Case).where(Case.order_id == order.id))).scalar_one_or_none()
    if case:
        session.add(CaseEvent(
            case_id=case.id,
            source="POLICY",
            event_type="DUPLICATE_CAPTURE_BLOCKED",
            description=f"{rule_id}: {message}",
        ))
        await session.commit()


@router.get("/{order_id}/status")
async def get_payment_status(
    order_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Read-only. Ask PayPal three ways (Orders API, Payments API capture, Transaction Search)
    and report whether they agree. Changes nothing in our database."""
    order = await _get_order_or_404(session, order_id, current_user)
    attempts = list((await session.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
    )).scalars().all())
    report = await check_payment_status(order, attempts)
    return {"order_id": order.id, "local_status": order.status, "report": report.to_dict()}


@router.post("/{order_id}/reconcile")
async def reconcile_order_status(
    order_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Check PayPal and apply the verified result to the order, its attempts and its case."""
    order = await _get_order_or_404(session, order_id, current_user)
    case = (await session.execute(select(Case).where(Case.order_id == order.id))).scalar_one_or_none()
    if case:
        out = await reconcile_case(case.id, session, record_evidence=True)
        await session.refresh(order)
        return {"order_id": order.id, "local_status": order.status, "case_id": case.id,
                "state": out["current_state"], "report": out["report"]}
    report, changed = await reconcile_order(session, order)
    return {"order_id": order.id, "local_status": order.status, "changed": changed, "report": report.to_dict()}


@router.post("/{order_id}/capture")
async def capture_order_payment(
    order_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    paypal_request_id: Optional[str] = Header(None, alias="PayPal-Request-Id"),
):
    """Capture endpoint enforcing idempotency, the single-active-attempt rule, and
    "reconcile before you retry".

    Lost-response safety: if an earlier attempt has no confirmed outcome (timeout, UNKNOWN, PENDING)
    we first ask PayPal what really happened. If the money already moved we report that and refuse a
    second capture. If we still cannot tell, we refuse too (fail closed).
    """
    order = await _get_order_or_404(session, order_id, current_user)

    # 1. R01: already completed locally
    if order.status == "COMPLETED":
        await _record_block(session, order, R01_COMPLETED_BLOCKS_RETRY, "Payment already completed.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"rule_id": R01_COMPLETED_BLOCKS_RETRY,
                    "message": "Payment is already completed. Duplicate capture blocked."},
        )

    # 2. An earlier attempt with no confirmed outcome must be reconciled before anything new is sent.
    prior = (await session.execute(
        select(PaymentAttempt).where(
            PaymentAttempt.order_id == order.id,
            PaymentAttempt.status.in_(["PENDING", "UNKNOWN", "CREATED"]),
        )
    )).scalars().all()
    if prior:
        report, _ = await reconcile_order(session, order)
        verdict = report.snapshot.capture_status
        if verdict == "COMPLETED":
            await _record_block(session, order, R01_COMPLETED_BLOCKS_RETRY,
                                "A previous attempt actually succeeded (response was lost). Second charge blocked.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"rule_id": R01_COMPLETED_BLOCKS_RETRY,
                        "message": "Your earlier payment actually went through. Duplicate capture blocked.",
                        "recovered": True,
                        "capture_id": report.snapshot.capture_id},
            )
        if verdict != "DENIED":
            rule = R02_PENDING_BLOCKS_RETRY if verdict == "PENDING" else R03_UNKNOWN_FAILS_CLOSED
            msg = ("The earlier payment is still pending at PayPal. Retry blocked."
                   if verdict == "PENDING"
                   else "We can't confirm what happened to the earlier attempt yet. Retry blocked to avoid a double charge.")
            await _record_block(session, order, rule, msg)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"rule_id": rule, "message": msg, "status": verdict},
            )
        # DENIED: PayPal verified the earlier attempt failed, so a new attempt is allowed below.

    # 3. Persist the attempt BEFORE calling PayPal. The unique index backs this up under a race.
    req_id = paypal_request_id or f"cap-{uuid.uuid4().hex}"
    attempt = PaymentAttempt(order_id=order.id, request_id=req_id, status="PENDING")
    session.add(attempt)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"rule_id": R07_ONE_ACTIVE_ATTEMPT,
                    "message": "Another payment attempt is currently active. Duplicate capture blocked."},
        )
    await session.refresh(attempt)

    # 4. Call PayPal. A timeout comes back as UNKNOWN, never as a failure.
    snapshot = await capture_order(order.paypal_order_id, request_id=req_id)

    attempt.status = snapshot.capture_status
    attempt.paypal_capture_id = snapshot.capture_id
    attempt.paypal_response_raw = snapshot.raw_ref
    attempt.is_simulated = snapshot.is_simulated
    if snapshot.capture_status == "COMPLETED":
        order.status = "COMPLETED"
    elif snapshot.capture_status == "DENIED":
        order.status = "DENIED"
    await session.commit()

    # 5. Lost response? Ask PayPal what happened right now instead of leaving the buyer guessing.
    recovered = False
    if snapshot.capture_status == "UNKNOWN":
        report, _ = await reconcile_order(session, order)
        if report.snapshot.capture_status == "COMPLETED":
            recovered = True
            snapshot = report.snapshot
        await session.refresh(attempt)

    await session.refresh(attempt)
    message = None
    if recovered:
        message = "The response was lost, but PayPal confirms the payment completed. You will not be charged again."
    elif attempt.status == "UNKNOWN":
        message = "We could not confirm the result yet. Do not pay again. We are checking with PayPal."

    return {
        "order_id": order.id,
        "paypal_order_id": order.paypal_order_id,
        "attempt_id": attempt.id,
        "snapshot": snapshot.to_dict(),
        "status": attempt.status,
        "recovered": recovered,
        "message": message,
    }
