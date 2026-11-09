import httpx
import pytest
import respx

from backend.app.config import settings
from backend.app.db.models import Case, Order, PaymentAttempt


@pytest.mark.asyncio
@respx.mock
async def test_seller_catalog_price_sets_server_order_total(async_client, auth_tokens):
    respx.post(f"{settings.paypal_base_url}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "TEST_TOKEN", "expires_in": 3600})
    )
    paypal_order = respx.post(f"{settings.paypal_base_url}/v2/checkout/orders").mock(
        return_value=httpx.Response(201, json={
            "id": "ORD-CATALOG-1",
            "status": "CREATED",
            "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORD-CATALOG-1"}],
        })
    )

    created = await async_client.post(
        "/api/catalog/items",
        json={"name": "Custom item", "description": "Seller-priced item", "price": 7.25},
        headers=auth_tokens["seller"],
    )
    assert created.status_code == 201
    product = created.json()

    buyer_list = await async_client.get("/api/catalog/items", headers=auth_tokens["buyer"])
    assert buyer_list.status_code == 200
    assert buyer_list.json()[0]["id"] == product["id"]

    order = await async_client.post(
        "/api/orders",
        json={"items": [{"product_id": product["id"], "quantity": 3, "unit_price": 0.01}]},
        headers=auth_tokens["buyer"],
    )
    assert order.status_code == 201
    assert order.json()["amount"] == 21.75
    assert paypal_order.calls.last.request.content
    assert "21.75" in paypal_order.calls.last.request.content.decode()


@pytest.mark.asyncio
async def test_buyers_cannot_manage_catalog(async_client, auth_tokens):
    response = await async_client.post(
        "/api/catalog/items",
        json={"name": "Not allowed", "description": "", "price": 2.00},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@respx.mock
async def test_buyer_refund_requires_seller_approval(async_client, auth_tokens, db_session):
    order = Order(
        paypal_order_id="ORD-REFUND-1",
        user_id="11111111-1111-4111-8111-111111111111",
        amount=25.0,
        currency="USD",
        status="COMPLETED",
    )
    db_session.add(order)
    await db_session.flush()
    attempt = PaymentAttempt(order_id=order.id, request_id="refund-test-attempt", status="COMPLETED",
                             paypal_capture_id="CAP-REFUND-1")
    case = Case(
        order_id=order.id,
        buyer_id=order.user_id,
        status="COMPLETED",
        current_policy_state="COMPLETED",
        permitted_actions=["REFUND", "VIEW_DETAILS"],
    )
    db_session.add_all([attempt, case])
    await db_session.commit()
    await db_session.refresh(case)

    request = await async_client.post(
        f"/api/cases/{case.id}/actions/REFUND/approve",
        json={},
        headers=auth_tokens["buyer"],
    )
    assert request.status_code == 200
    assert request.json()["state"] == "REFUND_PENDING"

    paypal_refund = respx.post(
        f"{settings.paypal_base_url}/v2/payments/captures/CAP-REFUND-1/refund"
    ).mock(return_value=httpx.Response(201, json={"id": "REFUND-1", "status": "PENDING"}))
    respx.post(f"{settings.paypal_base_url}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "TEST_TOKEN", "expires_in": 3600})
    )
    approval = await async_client.post(
        f"/api/cases/{case.id}/actions/REFUND/approve",
        json={},
        headers=auth_tokens["seller"],
    )
    assert approval.status_code == 200
    assert approval.json()["state"] == "REFUND_PENDING"
    assert len(paypal_refund.calls) == 1


@pytest.mark.asyncio
async def test_seller_can_decline_requested_refund(async_client, auth_tokens, db_session):
    order = Order(
        paypal_order_id="ORD-REFUND-2",
        user_id="11111111-1111-4111-8111-111111111111",
        amount=25.0,
        currency="USD",
        status="COMPLETED",
    )
    db_session.add(order)
    await db_session.flush()
    case = Case(
        order_id=order.id,
        buyer_id=order.user_id,
        status="REFUND_PENDING",
        current_policy_state="REFUND_PENDING",
        permitted_actions=["RECONCILE"],
    )
    db_session.add(case)
    await db_session.flush()
    from backend.app.db.models import CaseEvent
    db_session.add(CaseEvent(
        case_id=case.id,
        source="USER",
        event_type="REFUND_REQUESTED",
        description="Waiting for seller",
    ))
    await db_session.commit()

    response = await async_client.post(
        f"/api/cases/{case.id}/actions/DENY_REFUND/approve",
        json={"notes": "Item already delivered"},
        headers=auth_tokens["seller"],
    )
    assert response.status_code == 200
    assert response.json()["state"] == "COMPLETED"
