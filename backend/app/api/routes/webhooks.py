import json
import logging
from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db.session import get_db
from backend.app.db.models import WebhookEvent, Order, Case, PaymentAttempt, CaseEvent
from backend.app.paypal.webhooks import verify_webhook_signature
from backend.app.paypal.orders import get_order, get_capture
from backend.app.policy.engine import evaluate
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

    # 4. Authoritative Re-fetch: Re-GET the resource directly from PayPal
    # This prevents trusting stale out-of-order payloads
    order_id = None
    if resource_type == "capture" or "CAPTURE" in event_type:
        # Related order ID might be in supplementary_data or links
        order_id = (
            resource.get("supplementary_data", {})
            .get("related_ids", {})
            .get("order_id")
        )
    elif resource_type == "checkout-order" or "ORDER" in event_type:
        order_id = resource_id

    # If we can match to an order, re-fetch and update case
    if order_id:
        ord_stmt = select(Order).where((Order.paypal_order_id == order_id) | (Order.id == order_id))
        order = (await session.execute(ord_stmt)).scalar_one_or_none()

        if order:
            try:
                snap = await get_order(order.paypal_order_id)
                if snap.capture_status == "COMPLETED":
                    order.status = "COMPLETED"
                elif snap.capture_status == "DENIED":
                    order.status = "DENIED"

                # Update case if one exists
                case_stmt = select(Case).where(Case.order_id == order.id)
                case = (await session.execute(case_stmt)).scalar_one_or_none()
                if case:
                    ev = CaseEvent(
                        case_id=case.id,
                        source="WEBHOOK",
                        event_type=event_type,
                        description=f"Verified webhook received: {event_type} for resource {resource_id}",
                        is_simulated=False,
                    )
                    session.add(ev)

                    # Update case status
                    case.status = snap.capture_status
                    case.current_policy_state = snap.capture_status
                    await event_bus.broadcast(case.id, {
                        "type": "webhook_event",
                        "event_type": event_type,
                        "state": case.current_policy_state,
                    })
            except Exception as exc:
                logger.error("Failed to re-fetch resource for order %s: %s", order_id, exc)

    webhook_record.processed = True
    await session.commit()

    return {"status": "processed", "event_id": paypal_event_id}
