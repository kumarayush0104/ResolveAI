"""Regression: a capture PayPal rejects (e.g. card needs action) must not dead-lock the order.

Before the fix the failed capture left the attempt UNKNOWN, the next status check read the
order's APPROVED as "pending at PayPal", and every retry was blocked with R02 forever.
"""
import httpx
import pytest
import respx
from sqlalchemy import select

from backend.app.config import settings
from backend.app.db.models import PaymentAttempt

BASE = settings.paypal_base_url
OID = "ORD-RETRY-1"


@pytest.mark.asyncio
@respx.mock
async def test_rejected_capture_is_retryable_and_explains_why(async_client, auth_tokens, db_session):
    respx.post(f"{BASE}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "T", "expires_in": 3600}))
    respx.post(f"{BASE}/v2/checkout/orders").mock(
        return_value=httpx.Response(201, json={"id": OID, "status": "CREATED", "links": []}))
    respx.get(f"{BASE}/v2/checkout/orders/{OID}").mock(
        return_value=httpx.Response(200, json={"id": OID, "status": "APPROVED", "purchase_units": []}))
    cap = respx.post(f"{BASE}/v2/checkout/orders/{OID}/capture")
    cap.side_effect = [
        httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY",
                                  "details": [{"issue": "PAYER_ACTION_REQUIRED"}]}),
        httpx.Response(201, json={"id": OID, "status": "COMPLETED", "purchase_units": [
            {"payments": {"captures": [{"id": "CAP-1", "status": "COMPLETED",
                                         "amount": {"value": "45.00", "currency_code": "USD"}}]}}]}),
    ]

    created = (await async_client.post("/api/orders", json={"amount": 45.0}, headers=auth_tokens["buyer"])).json()
    oid = created["id"]

    first = await async_client.post(f"/api/orders/{oid}/capture", headers=auth_tokens["buyer"])
    assert first.status_code == 200
    assert first.json()["status"] == "UNKNOWN"
    assert "PAYER_ACTION_REQUIRED" in first.json()["message"]

    # Make the failed attempt look old enough to not be an in-flight request.
    from datetime import datetime, timedelta, timezone
    att = (await db_session.execute(select(PaymentAttempt))).scalars().all()
    for a in att:
        a.updated_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    second = await async_client.post(f"/api/orders/{oid}/capture", headers=auth_tokens["buyer"])
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "COMPLETED"
