from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
import respx

from backend.app.config import settings
from backend.app.paypal.client import PayPalError
from backend.app.paypal.orders import capture_order, classify_capture_error
from backend.app.paypal.transactions import (
    MAX_RANGE, build_window, format_date, parse_response, search_transaction,
)
from backend.app.services.status_check import check_payment_status

BASE = settings.paypal_base_url
CAP = "CAP00000000000001"


def tok():
    respx.post(f"{BASE}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "T", "expires_in": 3600}))


def row(code, tid=CAP):
    return {"transaction_info": {"transaction_id": tid, "transaction_status": code,
                                 "transaction_amount": {"currency_code": "USD", "value": "25.00"}}}


def order_json(cap_status="COMPLETED"):
    return {"id": "O1", "status": "COMPLETED", "purchase_units": [{"payments": {"captures": [
        {"id": CAP, "status": cap_status, "amount": {"currency_code": "USD", "value": "25.00"}}]}}]}


# ---- Transaction Search parsing ----------------------------------------------------------

@pytest.mark.parametrize("code,expected", [("S", "COMPLETED"), ("P", "PENDING"), ("D", "DENIED"), ("V", "REVERSED")])
def test_status_codes_normalize(code, expected):
    res = parse_response({"transaction_details": [row(code)]}, CAP)
    assert res.availability == "ok" and res.normalized == expected and res.status_code == code


def test_absent_record_is_not_a_failure():
    now = datetime.now(timezone.utc)
    young = parse_response({"transaction_details": []}, CAP, anchor=now - timedelta(minutes=20), now=now)
    old = parse_response({"transaction_details": []}, CAP, anchor=now - timedelta(days=2), now=now)
    assert young.availability == "not_indexed_yet" and young.normalized == "UNKNOWN"
    assert old.availability == "not_found" and old.normalized == "UNKNOWN"
    assert not young.has_verdict and not old.has_verdict


def test_duplicate_ids_with_different_statuses_are_unknown():
    res = parse_response({"transaction_details": [row("S"), row("D")]}, CAP)
    assert res.normalized == "UNKNOWN" and res.match_count == 2


def test_window_is_capped_and_dates_are_utc_z():
    now = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    start, end = build_window(now - timedelta(days=90), now)
    assert end - start <= MAX_RANGE
    assert format_date(now) == "2026-11-01T12:00:00Z"


@pytest.mark.asyncio
@respx.mock
async def test_search_sends_required_params():
    tok()
    route = respx.get(f"{BASE}/v1/reporting/transactions").mock(
        return_value=httpx.Response(200, json={"transaction_details": [row("S")]}))
    res = await search_transaction(CAP)
    assert res.normalized == "COMPLETED"
    q = route.calls.last.request.url.params
    assert q["transaction_id"] == CAP and q["start_date"].endswith("Z") and q["end_date"].endswith("Z")


@pytest.mark.asyncio
@respx.mock
async def test_search_not_enabled_is_graceful():
    tok()
    respx.get(f"{BASE}/v1/reporting/transactions").mock(
        return_value=httpx.Response(403, json={"name": "NOT_AUTHORIZED"}))
    res = await search_transaction(CAP)
    assert res.availability == "not_enabled" and "Transaction Search" in res.note


@pytest.mark.asyncio
@respx.mock
async def test_search_timeout_is_unavailable_not_denied():
    tok()
    respx.get(f"{BASE}/v1/reporting/transactions").mock(side_effect=httpx.ReadTimeout("slow"))
    res = await search_transaction(CAP)
    assert res.availability == "unavailable" and res.normalized == "UNKNOWN"


# ---- capture error classification ---------------------------------------------------------

def err(status, issue):
    import json
    return PayPalError(status, "x", json.dumps({"details": [{"issue": issue}]}))


def test_classification():
    assert classify_capture_error(err(422, "ORDER_ALREADY_CAPTURED")) == "ALREADY_CAPTURED"
    assert classify_capture_error(err(422, "INSTRUMENT_DECLINED")) == "DECLINED"
    assert classify_capture_error(err(422, "SOMETHING_NEW")) == "UNKNOWN"       # fail closed
    assert classify_capture_error(err(500, "INSTRUMENT_DECLINED")) == "UNKNOWN"
    assert classify_capture_error(err(403, "NOT_AUTHORIZED")) == "UNKNOWN"


@pytest.mark.asyncio
@respx.mock
async def test_already_captured_is_recovered_not_denied():
    tok()
    respx.post(f"{BASE}/v2/checkout/orders/O1/capture").mock(return_value=httpx.Response(
        422, json={"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_ALREADY_CAPTURED"}]}))
    respx.get(f"{BASE}/v2/checkout/orders/O1").mock(return_value=httpx.Response(200, json=order_json()))
    snap = await capture_order("O1")
    assert snap.capture_status == "COMPLETED" and snap.capture_id == CAP
    assert "ORDER_ALREADY_CAPTURED" in snap.note


@pytest.mark.asyncio
@respx.mock
async def test_real_decline_is_denied_and_odd_422_is_unknown():
    tok()
    route = respx.post(f"{BASE}/v2/checkout/orders/O1/capture")
    route.mock(return_value=httpx.Response(422, json={"details": [{"issue": "INSTRUMENT_DECLINED"}]}))
    assert (await capture_order("O1")).capture_status == "DENIED"
    route.mock(return_value=httpx.Response(422, json={"details": [{"issue": "ORDER_NOT_APPROVED"}]}))
    assert (await capture_order("O1")).capture_status == "UNKNOWN"


# ---- consensus across sources ---------------------------------------------------------------

def fake_order():
    return SimpleNamespace(paypal_order_id="O1", created_at=datetime.now(timezone.utc) - timedelta(days=1))


def mock_sources(order_cap="COMPLETED", search_code="S", search_status=200):
    tok()
    respx.get(f"{BASE}/v2/checkout/orders/O1").mock(return_value=httpx.Response(200, json=order_json(order_cap)))
    respx.get(f"{BASE}/v2/payments/captures/{CAP}").mock(return_value=httpx.Response(
        200, json={"id": CAP, "status": order_cap, "amount": {"currency_code": "USD", "value": "25.00"}}))
    respx.get(f"{BASE}/v1/reporting/transactions").mock(return_value=httpx.Response(
        search_status, json={"transaction_details": [row(search_code)]} if search_status == 200 else {}))


@pytest.mark.asyncio
@respx.mock
async def test_all_sources_agree():
    mock_sources()
    rep = await check_payment_status(fake_order(), [])
    assert rep.consensus == "COMPLETED" and not rep.conflicts and rep.snapshot.capture_status == "COMPLETED"
    assert len([s for s in rep.sources if s.ok]) == 3


@pytest.mark.asyncio
@respx.mock
async def test_denied_in_search_vs_completed_in_api_fails_closed():
    mock_sources(search_code="D")
    rep = await check_payment_status(fake_order(), [])
    assert rep.consensus == "CONFLICT"
    assert rep.snapshot.capture_status == "UNKNOWN" and rep.snapshot.conflict is True


@pytest.mark.asyncio
@respx.mock
async def test_reversal_without_refund_is_a_conflict():
    mock_sources(search_code="V")
    rep = await check_payment_status(fake_order(), [])
    assert rep.consensus == "CONFLICT" and rep.snapshot.capture_status == "UNKNOWN"


@pytest.mark.asyncio
@respx.mock
async def test_lagging_pending_in_search_is_not_a_conflict():
    mock_sources(search_code="P")
    rep = await check_payment_status(fake_order(), [])
    assert rep.consensus == "COMPLETED" and not rep.conflicts
    assert any("lag" in n for n in rep.notes)


@pytest.mark.asyncio
@respx.mock
async def test_search_not_enabled_does_not_block_a_clear_api_answer():
    mock_sources(search_status=403)
    rep = await check_payment_status(fake_order(), [])
    assert rep.consensus == "COMPLETED" and rep.reachable


@pytest.mark.asyncio
@respx.mock
async def test_everything_unreachable_is_unknown_not_denied():
    tok()
    respx.get(f"{BASE}/v2/checkout/orders/O1").mock(side_effect=httpx.ReadTimeout("x"))
    rep = await check_payment_status(fake_order(), [])
    assert rep.consensus == "UNKNOWN" and rep.snapshot.capture_status == "UNKNOWN" and not rep.reachable


@pytest.mark.asyncio
@respx.mock
async def test_simulated_capture_ids_are_never_sent_to_paypal():
    tok()
    order_route = respx.get(f"{BASE}/v2/checkout/orders/O1").mock(
        return_value=httpx.Response(200, json={"id": "O1", "status": "APPROVED", "purchase_units": []}))
    fake_attempt = SimpleNamespace(paypal_capture_id="sim-cap-123", is_simulated=True)
    rep = await check_payment_status(fake_order(), [fake_attempt])
    assert rep.capture_id is None and order_route.called
