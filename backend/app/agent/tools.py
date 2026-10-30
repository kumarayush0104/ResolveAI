"""Read-only tool declarations and executors for AI Investigator."""
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.paypal.orders import get_order, get_capture
from backend.app.db.models import WebhookEvent, PaymentAttempt, CaseEvent
from backend.app.services.redaction import redact_dict


async def tool_get_order(order_id: str) -> Dict[str, Any]:
    """Fetch authoritative order details from PayPal."""
    snap = await get_order(order_id)
    return snap.to_dict()


async def tool_get_capture(capture_id: str) -> Dict[str, Any]:
    """Fetch authoritative capture details from PayPal."""
    snap = await get_capture(capture_id)
    return snap.to_dict()


async def tool_list_webhook_events(order_id: str, session: AsyncSession) -> List[Dict[str, Any]]:
    """List verified webhook events associated with this order."""
    result = await session.execute(
        select(WebhookEvent).where(WebhookEvent.resource_id == order_id)
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "paypal_event_id": e.paypal_event_id,
            "event_type": e.event_type,
            "verified": e.verified,
            "is_simulated": e.is_simulated,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


async def tool_get_payment_attempts(order_id: str, session: AsyncSession) -> List[Dict[str, Any]]:
    """Get recorded payment attempts for the order."""
    result = await session.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == order_id)
    )
    attempts = result.scalars().all()
    return [
        {
            "id": a.id,
            "request_id": a.request_id,
            "status": a.status,
            "paypal_capture_id": a.paypal_capture_id,
            "is_simulated": a.is_simulated,
            "created_at": a.created_at.isoformat(),
        }
        for a in attempts
    ]


async def tool_get_case_messages(case_id: str, session: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve message events associated with this case."""
    result = await session.execute(
        select(CaseEvent).where(
            CaseEvent.case_id == case_id,
            CaseEvent.source == "USER",
        )
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "source": e.source,
            "event_type": e.event_type,
            "description": redact_dict(e.description),
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
