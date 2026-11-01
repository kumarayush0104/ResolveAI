"""Webhooks drive state through the policy engine, and lab scenario 1 recovers a REAL capture."""
import httpx
import pytest
import respx
from sqlalchemy import select

from backend.app.config import settings
from backend.app.db.models import Case, Order, PaymentAttempt, CaseEvent
from backend.app.services.lab import _simulate_lost_response
from backend.app.services.reconciliation import reconcile_case

BASE = settings.paypal_base_url
CAP = "CAPWH000000000001"
HDRS = {
    "paypal-transmission-id": "t1", "paypal-transmission-time": "2026-11-01T12:00:00Z",
    "paypal-cert-url": "https://api.sandbox.paypal.com/cert", "paypal-auth-algo": "SHA256withRSA",
    "paypal-transmission-sig": "sig",
}


def order_json(status="COMPLETED", with_capture=True):
    unit = {"amount": {"currency_code": "USD", "value": "25.00"}}
    if with_capture:
        unit["payments"] = {"captures": [{"id": CAP, "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "25.00"}}]}
    return {"id": "OWH1", "status": status, "purchase_units": [unit]}


def mock_base(order_body):
    respx.post(f"{BASE}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "T", "expires_in": 3600}))
    respx.post(f"{BASE}/v2/checkout/orders").mock(return_value=httpx.Response(201, json={"id": "OWH1", "status": "CREATED", "links": []}))
    respx.get(f"{BASE}/v2/checkout/orders/OWH1").mock(return_value=httpx.Response(200, json=order_body))
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(return_value=httpx.Response(
        200, json={"id": CAP, "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "25.00"}}))
    respx.get(f"{BASE}/v1/reporting/transactions").mock(return_value=httpx.Response(200, json={
        "transaction_details": [{"transaction_info": {"transaction_id": CAP, "transaction_status": "S"}}]}))
    respx.post(f"{BASE}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "SUCCESS"}))


@pytest.mark.asyncio
@respx.mock
async def test_capture_webhook_updates_case_via_policy_engine(async_client, auth_tokens):
    mock_base(order_json(status="APPROVED", with_capture=False))
    h = auth_tokens["buyer"]
    oid = (await async_client.post("/api/orders", json={"amount": 25.0}, headers=h)).json()["id"]
    case = (await async_client.post("/api/cases", json={"order_id": oid}, headers=h)).json()

    # PayPal now has the capture; the webhook arrives.
    respx.get(f"{BASE}/v2/checkout/orders/OWH1").mock(return_value=httpx.Response(200, json=order_json()))
    payload = {"id": "WH-1", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource_type": "capture",
               "resource": {"id": CAP, "supplementary_data": {"related_ids": {"order_id": "OWH1"}}}}
    r = await async_client.post("/api/paypal/webhook", json=payload, headers=HDRS)
    assert r.status_code == 200 and r.json()["status"] == "processed"

    detail = (await async_client.get(f"/api/cases/{case['id']}", headers=h)).json()
    assert detail["current_policy_state"] == "COMPLETED"
    assert detail["permitted_actions"] == ["REFUND", "VIEW_DETAILS"]          # computed by policy, not copied
    assert any(e["event_type"] == "PAYMENT.CAPTURE.COMPLETED" for e in detail["events"])


@pytest.mark.asyncio
@respx.mock
async def test_order_approved_webhook_does_not_change_state(async_client, auth_tokens):
    mock_base(order_json(status="APPROVED", with_capture=False))
    h = auth_tokens["buyer"]
    oid = (await async_client.post("/api/orders", json={"amount": 25.0}, headers=h)).json()["id"]
    case = (await async_client.post("/api/cases", json={"order_id": oid}, headers=h)).json()
    before = case["current_policy_state"]
    payload = {"id": "WH-2", "event_type": "CHECKOUT.ORDER.APPROVED", "resource_type": "checkout-order",
               "resource": {"id": "OWH1"}}
    assert (await async_client.post("/api/paypal/webhook", json=payload, headers=HDRS)).status_code == 200
    detail = (await async_client.get(f"/api/cases/{case['id']}", headers=h)).json()
    assert detail["current_policy_state"] == before          # approved is not paid


@pytest.mark.asyncio
@respx.mock
async def test_lab_scenario1_recovers_the_real_capture_id(async_client, auth_tokens, db_session):
    mock_base(order_json())                                   # PayPal really has the completed capture
    h = auth_tokens["buyer"]
    oid = (await async_client.post("/api/orders", json={"amount": 25.0}, headers=h)).json()["id"]
    case_id = (await async_client.post("/api/cases", json={"order_id": oid}, headers=h)).json()["id"]

    case = (await db_session.execute(select(Case).where(Case.id == case_id))).scalar_one()
    order = (await db_session.execute(select(Order).where(Order.id == oid))).scalar_one()

    info = await _simulate_lost_response(db_session, case, order)
    assert info["paypal_before"] == "COMPLETED"
    assert case.current_policy_state == "UNKNOWN" and order.status == "CREATED"
    attempts = (await db_session.execute(select(PaymentAttempt).where(PaymentAttempt.order_id == oid))).scalars().all()
    assert all(a.paypal_capture_id is None for a in attempts)   # local knowledge truly wiped

    out = await reconcile_case(case_id, db_session, record_evidence=True)
    assert out["current_state"] == "COMPLETED"
    attempts = (await db_session.execute(select(PaymentAttempt).where(PaymentAttempt.order_id == oid))).scalars().all()
    assert [a.paypal_capture_id for a in attempts] == [CAP]      # the REAL id, never "sim-cap-..."
    events = (await db_session.execute(select(CaseEvent).where(CaseEvent.case_id == case_id))).scalars().all()
    assert not any("sim-cap" in e.description for e in events)


@pytest.mark.asyncio
@respx.mock
async def test_lab_scenario1_stays_unknown_if_paypal_has_nothing(async_client, auth_tokens, db_session):
    """If the order was never captured, the reconciler must NOT invent a completion."""
    mock_base(order_json(status="CREATED", with_capture=False))
    h = auth_tokens["buyer"]
    oid = (await async_client.post("/api/orders", json={"amount": 25.0}, headers=h)).json()["id"]
    case_id = (await async_client.post("/api/cases", json={"order_id": oid}, headers=h)).json()["id"]
    case = (await db_session.execute(select(Case).where(Case.id == case_id))).scalar_one()
    order = (await db_session.execute(select(Order).where(Order.id == oid))).scalar_one()

    await _simulate_lost_response(db_session, case, order)
    out = await reconcile_case(case_id, db_session, record_evidence=True)
    assert out["current_state"] != "COMPLETED"
    assert "RETRY" in [b["action"] for b in out["decision"]["blocked_actions"]]
