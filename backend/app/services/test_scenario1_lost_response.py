"""Scenario 1: the buyer paid, but the success response never reached us.

Expected (project plan s13): reconcile the original capture, show completion, block a second charge.
PayPal is mocked at the HTTP layer so the real adapter, status check, reconciler and policy run.
"""
import httpx
import pytest
import respx

from backend.app.config import settings

BASE = settings.paypal_base_url
ORDER = "ORD-LOST-1"
CAP = "CAPLOST00000000001"


def order_json(status="COMPLETED", cap_status="COMPLETED", with_capture=True):
    unit = {"amount": {"currency_code": "USD", "value": "25.00"}}
    if with_capture:
        unit["payments"] = {"captures": [{
            "id": CAP, "status": cap_status, "amount": {"currency_code": "USD", "value": "25.00"},
        }]}
    return {"id": ORDER, "status": status, "purchase_units": [unit]}


def search_json(code="S"):
    return {"transaction_details": [{"transaction_info": {
        "transaction_id": CAP, "transaction_status": code,
        "transaction_amount": {"currency_code": "USD", "value": "25.00"},
    }}]}


def mock_paypal(*, capture_timeout=True, order_reachable=True, search_code="S"):
    respx.post(f"{BASE}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "T", "expires_in": 3600}))
    respx.post(f"{BASE}/v2/checkout/orders").mock(return_value=httpx.Response(201, json={
        "id": ORDER, "status": "CREATED",
        "links": [{"rel": "approve", "href": "https://sandbox.paypal.com/x"}]}))
    cap_post = respx.post(f"{BASE}/v2/checkout/orders/{ORDER}/capture")
    cap_post.mock(side_effect=httpx.ReadTimeout("lost") if capture_timeout
                  else None, return_value=None if capture_timeout else httpx.Response(201, json=order_json()))
    get_order = respx.get(f"{BASE}/v2/checkout/orders/{ORDER}")
    if order_reachable:
        get_order.mock(return_value=httpx.Response(200, json=order_json()))
    else:
        get_order.mock(side_effect=httpx.ReadTimeout("down"))
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(
        return_value=httpx.Response(200, json={"id": CAP, "status": "COMPLETED",
                                               "amount": {"currency_code": "USD", "value": "25.00"}}))
    respx.get(f"{BASE}/v1/reporting/transactions").mock(
        return_value=httpx.Response(200, json=search_json(search_code)))
    return cap_post, get_order


async def make_order(client, headers):
    r = await client.post("/api/orders", json={"amount": 25.0}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


@pytest.mark.asyncio
@respx.mock
async def test_lost_response_is_recovered_and_second_charge_blocked(async_client, auth_tokens):
    cap_post, _ = mock_paypal(capture_timeout=True)
    h = auth_tokens["buyer"]
    oid = await make_order(async_client, h)

    # The capture times out, but PayPal really completed it. We recover inline.
    r = await async_client.post(f"/api/orders/{oid}/capture", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "COMPLETED"
    assert body["recovered"] is True
    assert body["snapshot"]["capture_id"] == CAP

    # A second capture is refused and never reaches PayPal again.
    r2 = await async_client.post(f"/api/orders/{oid}/capture", headers=h)
    assert r2.status_code == 409
    assert r2.json()["detail"]["rule_id"] == "R01_COMPLETED_BLOCKS_RETRY"
    assert cap_post.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_unrecoverable_timeout_stays_unknown_never_denied_and_blocks_retry(async_client, auth_tokens):
    cap_post, _ = mock_paypal(capture_timeout=True, order_reachable=False)
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(side_effect=httpx.ReadTimeout("down"))
    h = auth_tokens["buyer"]
    oid = await make_order(async_client, h)

    r = await async_client.post(f"/api/orders/{oid}/capture", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "UNKNOWN"          # assert state_after_timeout != "DENIED"
    assert r.json()["recovered"] is False
    assert "do not pay again" in r.json()["message"].lower()

    r2 = await async_client.post(f"/api/orders/{oid}/capture", headers=h)
    assert r2.status_code == 409
    assert r2.json()["detail"]["rule_id"] == "R03_UNKNOWN_FAILS_CLOSED"
    assert cap_post.call_count == 1                  # duplicate_capture_count_for_purchase <= 1


@pytest.mark.asyncio
@respx.mock
async def test_background_style_reconcile_heals_unknown_without_a_case(async_client, auth_tokens, db_session):
    from sqlalchemy import select
    from backend.app.db.models import Order, PaymentAttempt
    from backend.app.services.reconciliation import reconcile_order

    mock_paypal(capture_timeout=True, order_reachable=False)
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(side_effect=httpx.ReadTimeout("down"))
    h = auth_tokens["buyer"]
    oid = await make_order(async_client, h)
    await async_client.post(f"/api/orders/{oid}/capture", headers=h)

    # PayPal becomes reachable again; the worker reconciles the order (no case was ever opened).
    respx.get(f"{BASE}/v2/checkout/orders/{ORDER}").mock(return_value=httpx.Response(200, json=order_json()))
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(return_value=httpx.Response(
        200, json={"id": CAP, "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "25.00"}}))

    order = (await db_session.execute(select(Order).where(Order.id == oid))).scalar_one()
    report, changed = await reconcile_order(db_session, order)
    assert changed and report.consensus == "COMPLETED"
    attempts = (await db_session.execute(select(PaymentAttempt).where(PaymentAttempt.order_id == oid))).scalars().all()
    assert [a.status for a in attempts] == ["COMPLETED"]
    assert attempts[0].paypal_capture_id == CAP
    assert order.status == "COMPLETED"


@pytest.mark.asyncio
@respx.mock
async def test_reconcile_action_does_a_real_check(async_client, auth_tokens):
    mock_paypal(capture_timeout=True, order_reachable=False)
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(side_effect=httpx.ReadTimeout("down"))
    h = auth_tokens["buyer"]
    oid = await make_order(async_client, h)
    await async_client.post(f"/api/orders/{oid}/capture", headers=h)

    case = (await async_client.post("/api/cases", json={"order_id": oid}, headers=h)).json()
    assert case["current_policy_state"] == "UNKNOWN"

    # PayPal comes back and says it completed.
    respx.get(f"{BASE}/v2/checkout/orders/{ORDER}").mock(return_value=httpx.Response(200, json=order_json()))
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(return_value=httpx.Response(
        200, json={"id": CAP, "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "25.00"}}))

    r = await async_client.post(f"/api/cases/{case['id']}/actions/RECONCILE/approve", json={}, headers=h)
    assert r.status_code == 200
    assert r.json()["state"] == "COMPLETED"
    assert r.json()["state_changed"] is True

    detail = (await async_client.get(f"/api/cases/{case['id']}", headers=h)).json()
    assert detail["current_policy_state"] == "COMPLETED"
    assert "RETRY" in [b["action"] for b in detail["policy_decision"]["blocked_actions"]]
    kinds = [s["source"] for s in detail["evidence_bundle"]["status_report"]["sources"]]
    assert {"ORDERS_API", "PAYMENTS_API", "TRANSACTION_SEARCH"} <= set(kinds)


@pytest.mark.asyncio
@respx.mock
async def test_reconcile_is_allowed_even_when_state_is_completed(async_client, auth_tokens):
    """Checking PayPal is read-only, so the button must work in every state, not only UNKNOWN."""
    mock_paypal(capture_timeout=False)
    h = auth_tokens["buyer"]
    oid = await make_order(async_client, h)
    r = await async_client.post(f"/api/orders/{oid}/capture", headers=h)
    assert r.json()["status"] == "COMPLETED"
    case = (await async_client.post("/api/cases", json={"order_id": oid}, headers=h)).json()
    assert "RECONCILE" not in case["permitted_actions"]
    r = await async_client.post(f"/api/cases/{case['id']}/actions/RECONCILE/approve", json={}, headers=h)
    assert r.status_code == 200 and r.json()["state"] == "COMPLETED" and r.json()["state_changed"] is False
