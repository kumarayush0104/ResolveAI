import os
import pytest
import respx
import httpx
from backend.app.config import settings

creds_available = bool(
    os.environ.get("PAYPAL_CLIENT_ID")
    and os.environ.get("PAYPAL_CLIENT_SECRET")
    and "mock" not in os.environ.get("PAYPAL_CLIENT_ID", "")
)


@pytest.mark.asyncio
@respx.mock
async def test_orders_crud_mocked(async_client, auth_tokens):
    """Test full order lifecycle via API with respx mocking."""
    # Mock token
    respx.post(f"{settings.paypal_base_url}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "TEST_TOKEN", "expires_in": 3600})
    )

    # Mock order create
    respx.post(f"{settings.paypal_base_url}/v2/checkout/orders").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "ORD-MOCK-999",
                "status": "CREATED",
                "links": [
                    {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORD-MOCK-999"}
                ],
            },
        )
    )

    # 1. Create order
    create_resp = await async_client.post(
        "/api/orders",
        json={"amount": 45.0, "currency": "USD"},
        headers=auth_tokens["buyer"],
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["order_id"] == "ORD-MOCK-999"
    assert "https://www.sandbox.paypal.com/checkoutnow" in created_data["approval_url"]
    order_uuid = created_data["id"]

    # Mock order get
    respx.get(f"{settings.paypal_base_url}/v2/checkout/orders/ORD-MOCK-999").mock(
        return_value=httpx.Response(
            200,
            json={"id": "ORD-MOCK-999", "status": "APPROVED", "purchase_units": []},
        )
    )

    # 2. Get order
    get_resp = await async_client.get(
        f"/api/orders/{order_uuid}",
        headers=auth_tokens["buyer"],
    )
    assert get_resp.status_code == 200
    got_data = get_resp.json()
    assert got_data["snapshot"]["order_status"] == "APPROVED"

    # Mock capture
    respx.post(f"{settings.paypal_base_url}/v2/checkout/orders/ORD-MOCK-999/capture").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "ORD-MOCK-999",
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [{"id": "CAP-MOCK-888", "status": "COMPLETED"}]
                        }
                    }
                ],
            },
        )
    )

    # 3. Capture order
    cap_resp = await async_client.post(
        f"/api/orders/{order_uuid}/capture",
        headers=auth_tokens["buyer"],
    )
    assert cap_resp.status_code == 200
    cap_data = cap_resp.json()
    assert cap_data["status"] == "COMPLETED"
    assert cap_data["snapshot"]["capture_id"] == "CAP-MOCK-888"

    # 4. Duplicate capture attempt must return 409 Conflict (R01_COMPLETED_BLOCKS_RETRY)
    dup_resp = await async_client.post(
        f"/api/orders/{order_uuid}/capture",
        headers=auth_tokens["buyer"],
    )
    assert dup_resp.status_code == 409
    assert "R01_COMPLETED_BLOCKS_RETRY" in str(dup_resp.json())


@pytest.mark.skipif(not creds_available, reason="Live PayPal sandbox credentials not provided")
@pytest.mark.asyncio
async def test_live_sandbox_order_creation(async_client, auth_tokens):
    """Optional live test against real PayPal sandbox if live credentials exist."""
    resp = await async_client.post(
        "/api/orders",
        json={"amount": 10.0, "currency": "USD"},
        headers=auth_tokens["buyer"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["order_id"].startswith("8") or len(data["order_id"]) > 5
    assert "paypal.com" in data["approval_url"]
