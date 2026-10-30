import json
import pytest
import respx
import httpx
from backend.app.config import settings


@pytest.mark.asyncio
@respx.mock
async def test_webhook_signature_failure_returns_400(async_client):
    """Unverified webhook signature must be rejected with 400."""
    respx.post(f"{settings.paypal_base_url}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
    )
    # Verification returns FAILURE
    respx.post(f"{settings.paypal_base_url}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "FAILURE"})
    )

    headers = {
        "paypal-transmission-id": "trans-1",
        "paypal-transmission-time": "2026-10-30T12:00:00Z",
        "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "fake_sig",
    }
    payload = {
        "id": "WH-EVT-FAIL",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"id": "CAP-123"},
    }

    resp = await async_client.post("/api/paypal/webhook", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "Invalid PayPal webhook signature" in resp.json()["detail"]


@pytest.mark.asyncio
@respx.mock
async def test_webhook_deduplication(async_client):
    """Posting the same webhook event ID twice must succeed idempotently without side-effects."""
    respx.post(f"{settings.paypal_base_url}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
    )
    respx.post(f"{settings.paypal_base_url}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "SUCCESS"})
    )
    respx.get(f"{settings.paypal_base_url}/v2/checkout/orders/ORD-WH-TEST").mock(
        return_value=httpx.Response(200, json={"id": "ORD-WH-TEST", "status": "COMPLETED"})
    )

    headers = {
        "paypal-transmission-id": "trans-1",
        "paypal-transmission-time": "2026-10-30T12:00:00Z",
        "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "fake_sig",
    }
    payload = {
        "id": "WH-EVT-DUP-1",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"id": "ORD-WH-TEST"},
        "resource_type": "checkout-order",
    }

    # First delivery
    resp1 = await async_client.post("/api/paypal/webhook", json=payload, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processed"

    # Second delivery with identical event id
    resp2 = await async_client.post("/api/paypal/webhook", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "duplicate_ignored"
