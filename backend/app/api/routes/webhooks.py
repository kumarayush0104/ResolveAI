import json
import logging
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.db.models import WebhookEvent, Order, Case, PaymentAttempt, CaseEvent
from backend.app.paypal.webhooks import verify_webhook_signature
from backend.app.services.reconciliation import reconcile_case, reconcile_order
from backend.app.services.stream_bus import event_bus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/paypal", tags=["webhooks"])


@router.post("/webhook")
async def receive_paypal_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """Authoritative PayPal webhook receiver with cryptographic signature verification,
    idempotent deduplication, persist-before-process, and resource re-fetch.
    """
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")

    try:
        payload = json.loads(body_str)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    paypal_event_id = payload.get("id")
    event_type = payload.get("event_type")
    resource = payload.get("resource", {})
    resource_id = resource.get("id")
    resource_type = payload.get("resource_type")

    if not paypal_event_id or not event_type:
        raise HTTPException(status_code=400, detail="Missing required webhook event fields")

    # 1. Cryptographic Signature Verification
    headers_dict = dict(request.headers)
    is_verified = await verify_webhook_signature(
        headers=headers_dict,
        body_str=body_str,
        webhook_id=settings.PAYPAL_WEBHOOK_ID,
    )

    if not is_verified:
        logger.warning("Webhook signature verification failed for event %s", paypal_event_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PayPal webhook signature",
        )

    # 2. Idempotent Deduplication
    existing_stmt = select(WebhookEvent).where(WebhookEvent.paypal_event_id == paypal_event_id)
    existing_evt = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing_evt:
        # Idempotent response: no duplicate side-effect
        logger.info("Ignoring duplicate webhook event %s", paypal_event_id)
        return {"status": "duplicate_ignored", "event_id": paypal_event_id}

    # 3. Persist BEFORE processing
    webhook_record = WebhookEvent(
        paypal_event_id=paypal_event_id,
        event_type=event_type,
        resource_id=resource_id,
        resource_type=resource_type,
        raw_payload=body_str,
        verified=True,
        is_simulated=False,
        processed=False,
    )
    session.add(webhook_record)
    await session.commit()
    await session.refresh(webhook_record)

    # 4. Find the order this event is about.
    related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
    paypal_order_id = related.get("order_id")
    if not paypal_order_id and (resource_type == "checkout-order" or event_type.startswith("CHECKOUT.ORDER")):
        paypal_order_id = resource_id
    capture_id = related.get("capture_id") or (resource_id if event_type.startswith("PAYMENT.CAPTURE") else None)

    order = None
    if paypal_order_id:
        order = (await session.execute(
            select(Order).where((Order.paypal_order_id == paypal_order_id) | (Order.id == paypal_order_id))
        )).scalar_one_or_none()
    if order is None and capture_id:
        order = (await session.execute(
            select(Order).join(PaymentAttempt, PaymentAttempt.order_id == Order.id)
            .where(PaymentAttempt.paypal_capture_id == capture_id)
        )).scalars().first()

    if order is not None:
        case = (await session.execute(select(Case).where(Case.order_id == order.id))).scalar_one_or_none()

        if case:
            session.add(CaseEvent(
                case_id=case.id,
                source="WEBHOOK",
                event_type=event_type,
                description=f"Verified webhook received: {event_type} for resource {resource_id}",
                is_simulated=False,
            ))
            await session.commit()

        if event_type == "CHECKOUT.ORDER.APPROVED":
            # Approved means the buyer agreed to pay. Nothing has been captured, so no state change.
            pass
        else:
            # Never trust the payload alone: events can repeat and arrive out of order. Ask PayPal
            # (Orders API, capture, Transaction Search) and let the policy engine decide the state.
            try:
                if case:
                    await reconcile_case(case.id, session)
                else:
                    await reconcile_order(session, order)
                if case:
                    await session.refresh(case)
                    await event_bus.broadcast(case.id, {
                        "type": "webhook_event",
                        "event_type": event_type,
                        "state": case.current_policy_state,
                    })
            except Exception as exc:
                logger.error("Failed to reconcile order %s after webhook: %s", order.id, exc)

    webhook_record.processed = True
    await session.commit()

    return {"status": "processed", "event_id": paypal_event_id}
