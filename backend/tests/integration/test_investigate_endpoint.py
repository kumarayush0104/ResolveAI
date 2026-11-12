"""Regression: POST /cases/{id}/investigate must stream a final result (it used to stream nothing)."""
import json
import httpx
import pytest
import respx

from backend.app.config import settings

BASE = settings.paypal_base_url
OID = "ORD-INV-1"


@pytest.mark.asyncio
@respx.mock
async def test_investigate_streams_final_result(async_client, auth_tokens):
    respx.post(f"{BASE}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "T", "expires_in": 3600}))
    respx.post(f"{BASE}/v2/checkout/orders").mock(
        return_value=httpx.Response(201, json={"id": OID, "status": "CREATED", "links": []}))
    respx.get(f"{BASE}/v2/checkout/orders/{OID}").mock(
        return_value=httpx.Response(200, json={"id": OID, "status": "APPROVED", "purchase_units": []}))
    h = auth_tokens["buyer"]
    order = (await async_client.post("/api/orders", json={"amount": 25.0}, headers=h)).json()
    case = await async_client.post("/api/cases", json={"order_id": order["id"]}, headers=h)
    assert case.status_code in (200, 201), case.text
    cid = case.json()["id"]

    resp = await async_client.post(f"/api/cases/{cid}/investigate", headers=h)
    assert resp.status_code == 200
    events = [json.loads(l[6:]) for l in resp.text.splitlines() if l.startswith("data: ")]
    finals = [e for e in events if e["type"] == "final"]
    assert finals, resp.text
    assert "no money has moved" in finals[0]["result"]["summary"]
