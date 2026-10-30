import pytest
import respx
import httpx
from backend.app.config import settings
from backend.app.paypal.client import PayPalClient, PayPalTimeout, PayPalError, ProviderSnapshot
from backend.app.paypal.orders import create_order, capture_order, get_order, normalize_status
from backend.app.services.redaction import redact_dict


@pytest.mark.asyncio
@respx.mock
async def test_oauth2_token_caching():
    """Test OAuth2 token acquisition and reuse before expiry."""
    client = PayPalClient(base_url="https://api-m.sandbox.paypal.com", client_id="cid", client_secret="csec")

    token_route = respx.post("https://api-m.sandbox.paypal.com/v1/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "ACCESS_TOKEN_123", "token_type": "Bearer", "expires_in": 3600},
        )
    )

    t1 = await client.get_token()
    assert t1 == "ACCESS_TOKEN_123"
    assert token_route.call_count == 1

    # Second call should use cache
    t2 = await client.get_token()
    assert t2 == "ACCESS_TOKEN_123"
    assert token_route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_timeout_raises_paypal_timeout_never_denied():
    """CRITICAL RULE: Timeout must raise PayPalTimeout and NEVER return DENIED."""
    client = PayPalClient(base_url="https://api-m.sandbox.paypal.com")
    client._cached_token = "VALID_TOKEN"
    client._token_expires_at = 9999999999.0

    respx.get("https://api-m.sandbox.paypal.com/v2/checkout/orders/ORD-TIMEOUT").mock(
        side_effect=httpx.TimeoutException("Connection timed out")
    )

    with pytest.raises(PayPalTimeout) as exc_info:
        await client.request("GET", "/v2/checkout/orders/ORD-TIMEOUT")

    assert "timed out" in str(exc_info.value).lower()


@pytest.mark.asyncio
@respx.mock
async def test_capture_order_timeout_sets_unknown():
    """When capture times out, capture_status MUST be UNKNOWN, never DENIED."""
    respx.post(f"{settings.paypal_base_url}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
    )
    respx.post(f"{settings.paypal_base_url}/v2/checkout/orders/ORD-TIMEOUT-TEST/capture").mock(
        side_effect=httpx.TimeoutException("Gateway timeout")
    )

    snap = await capture_order("ORD-TIMEOUT-TEST")
    assert snap.capture_status == "UNKNOWN"
    assert snap.order_status == "UNKNOWN"
    assert snap.capture_id is None
    assert "reconciliation required" in snap.raw_ref.lower()


@pytest.mark.asyncio
@respx.mock
async def test_order_creation_and_normalization():
    """Test order creation normalizing approval links."""
    respx.post(f"{settings.paypal_base_url}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
    )
    respx.post(f"{settings.paypal_base_url}/v2/checkout/orders").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "ORD-REAL-123",
                "status": "CREATED",
                "links": [
                    {"rel": "self", "href": "https://api-m.sandbox.paypal.com/v2/checkout/orders/ORD-REAL-123"},
                    {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORD-REAL-123"},
                ],
            },
        )
    )

    res = await create_order(amount=99.99, currency="USD")
    assert res["order_id"] == "ORD-REAL-123"
    assert "https://www.sandbox.paypal.com/checkoutnow" in res["approval_url"]


def test_redaction_removes_pii():
    """Sensitive fields must be masked before DB storage or logging."""
    raw = {
        "client_secret": "SUPER_SECRET_123",
        "payer": {
            "email_address": "buyer@example.com",
            "name": {"given_name": "John", "surname": "Doe"},
        },
    }
    redacted = redact_dict(raw)
    assert redacted["client_secret"] == "[REDACTED_SECRET]"
    assert redacted["payer"]["email_address"] == "[REDACTED_EMAIL]"
    assert redacted["payer"]["name"]["given_name"] == "[REDACTED_NAME]"
