import httpx
import pytest
import respx

from backend.app.config import settings

BASE = settings.paypal_base_url
CAP = "CAPENDPT0000000001"


def mock_all():
    respx.post(f"{BASE}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "T", "expires_in": 3600}))
    respx.post(f"{BASE}/v2/checkout/orders").mock(return_value=httpx.Response(201, json={"id": "OE1", "status": "CREATED", "links": []}))
    respx.get(f"{BASE}/v2/checkout/orders/OE1").mock(return_value=httpx.Response(200, json={
        "id": "OE1", "status": "COMPLETED", "purchase_units": [{"payments": {"captures": [
            {"id": CAP, "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "9.00"}}]}}]}))
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(return_value=httpx.Response(
        200, json={"id": CAP, "status": "COMPLETED", "amount": {"currency_code": "USD", "value": "9.00"}}))
    respx.get(f"{BASE}/v1/reporting/transactions").mock(return_value=httpx.Response(200, json={
        "transaction_details": [{"transaction_info": {"transaction_id": CAP, "transaction_status": "S"}}]}))


@pytest.mark.asyncio
@respx.mock
async def test_status_endpoint_reports_each_source_read_only(async_client, auth_tokens):
    mock_all()
    h = auth_tokens["buyer"]
    oid = (await async_client.post("/api/orders", json={"amount": 9.0}, headers=h)).json()["id"]

    r = await async_client.get(f"/api/orders/{oid}/status", headers=h)
    assert r.status_code == 200
    rep = r.json()["report"]
    assert rep["consensus"] == "COMPLETED" and rep["agrees"] is True
    assert {s["source"] for s in rep["sources"]} == {"ORDERS_API", "PAYMENTS_API", "TRANSACTION_SEARCH"}
    assert r.json()["local_status"] == "CREATED"          # GET never mutates local state

    # POST reconcile applies it.
    r2 = await async_client.post(f"/api/orders/{oid}/reconcile", headers=h)
    assert r2.status_code == 200 and r2.json()["local_status"] == "COMPLETED"


@pytest.mark.asyncio
@respx.mock
async def test_buyer_cannot_check_someone_elses_order(async_client, auth_tokens):
    mock_all()
    oid = (await async_client.post("/api/orders", json={"amount": 9.0}, headers=auth_tokens["admin"])).json()["id"]
    r = await async_client.get(f"/api/orders/{oid}/status", headers=auth_tokens["buyer"])
    assert r.status_code == 403


@pytest.mark.asyncio
@respx.mock
async def test_transaction_lookup_is_merchant_only(async_client, auth_tokens):
    mock_all()
    assert (await async_client.get(f"/api/paypal/transactions/{CAP}", headers=auth_tokens["buyer"])).status_code == 403
    r = await async_client.get(f"/api/paypal/transactions/{CAP}", headers=auth_tokens["admin"])
    assert r.status_code == 200 and r.json()["normalized"] == "COMPLETED" and r.json()["status_code"] == "S"
