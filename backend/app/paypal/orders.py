import json
from typing import Optional, Dict, Any

from backend.app.paypal.client import paypal_client, ProviderSnapshot, PayPalTimeout, PayPalError
from backend.app.services.redaction import redact_dict


def normalize_status(paypal_status: Optional[str]) -> str:
    """Normalize PayPal status strings to our authoritative 4-state capture model:
    COMPLETED | PENDING | DENIED | UNKNOWN
    """
    if not paypal_status:
        return "UNKNOWN"
    s = paypal_status.upper()
    if s in ("COMPLETED", "SUCCESS"):
        return "COMPLETED"
    if s in ("PENDING", "APPROVED", "CREATED", "SAVED", "ACTION_REQUIRED", "PAYER_ACTION_REQUIRED"):
        return "PENDING"
    if s in ("DECLINED", "FAILED", "DENIED", "VOIDED", "CANCELLED", "EXPIRED"):
        return "DENIED"
    if s in ("REFUNDED", "PARTIALLY_REFUNDED"):
        return "COMPLETED"
    return "UNKNOWN"


# PayPal `details[].issue` codes that mean the buyer's funding source / processor
# definitively refused this payment. Anything NOT on this list is treated as
# unresolved (fail closed) rather than as a decline.
DECLINE_ISSUES = {"INSTRUMENT_DECLINED", "TRANSACTION_REFUSED", "PAYER_CANNOT_PAY"}


def classify_capture_error(exc: PayPalError) -> str:
    """Classify a non-2xx response to POST /orders/{id}/capture.

    ALREADY_CAPTURED -> payment succeeded earlier; the response was lost. Recover via GET order.
    DECLINED         -> PayPal explicitly refused the payment (verified failure).
    UNKNOWN          -> anything else (auth problems, 5xx, validation, unfamiliar issue codes).
                        We cannot claim failure, so we fail closed.
    """
    issues = set(exc.issues)
    if exc.status_code == 422 and "ORDER_ALREADY_CAPTURED" in issues:
        return "ALREADY_CAPTURED"
    if exc.status_code in (400, 422) and issues & DECLINE_ISSUES:
        return "DECLINED"
    return "UNKNOWN"


def _first_capture(data: Dict[str, Any]) -> Dict[str, Any]:
    units = data.get("purchase_units") or []
    if not units:
        return {}
    captures = (units[0].get("payments") or {}).get("captures") or []
    return captures[0] if captures else {}


def _unit_amount(data: Dict[str, Any]) -> Dict[str, Any]:
    units = data.get("purchase_units") or []
    return (units[0].get("amount") or {}) if units else {}


def _snapshot_from_order_json(data: Dict[str, Any], order_id: Optional[str]) -> ProviderSnapshot:
    """Build a normalized snapshot from an Orders v2 order resource."""
    cap = _first_capture(data)
    order_status = data.get("status")
    raw_cap_status = cap.get("status")
    amount = cap.get("amount") or _unit_amount(data)
    refund_state = raw_cap_status.upper() if raw_cap_status and raw_cap_status.upper() in ("REFUNDED", "PARTIALLY_REFUNDED") else None
    return ProviderSnapshot(
        order_status=order_status,
        capture_status=normalize_status(raw_cap_status or order_status),
        capture_id=cap.get("id"),
        order_id=data.get("id") or order_id,
        source="api",
        raw_ref=json.dumps(redact_dict(data)),
        raw_capture_status=raw_cap_status,
        pending_reason=(cap.get("status_details") or {}).get("reason"),
        refund_state=refund_state,
        amount=amount.get("value"),
        currency=amount.get("currency_code"),
    )


async def create_order(
    amount: float,
    currency: str = "USD",
    return_url: str = "http://localhost:8000/api/orders/return",
    cancel_url: str = "http://localhost:8000/api/orders/cancel",
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a PayPal order with intent=CAPTURE and idempotency key."""
    body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {
                    "currency_code": currency,
                    "value": f"{amount:.2f}",
                },
                "description": "ResolveAI purchase",
            }
        ],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "user_action": "PAY_NOW",
        },
    }

    headers = {}
    if request_id:
        headers["PayPal-Request-Id"] = request_id

    resp = await paypal_client.request("POST", "/v2/checkout/orders", json=body, headers=headers)
    data = resp.json()

    order_id = data.get("id")
    approval_url = None
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            approval_url = link.get("href")
            break

    return {
        "order_id": order_id,
        "approval_url": approval_url,
        "raw_response": redact_dict(data),
    }


async def capture_order(
    order_id: str,
    request_id: Optional[str] = None,
) -> ProviderSnapshot:
    """Capture payment for an approved order.
    CRITICAL: If a timeout occurs, return a snapshot with capture_status=UNKNOWN.
    Never return DENIED on timeout.
    """
    headers = {}
    if request_id:
        headers["PayPal-Request-Id"] = request_id

    try:
        resp = await paypal_client.request(
            "POST",
            f"/v2/checkout/orders/{order_id}/capture",
            json={},
            headers=headers,
        )
        data = resp.json()
    except PayPalTimeout:
        # TIMEOUT SAFETY: Never map to failure/DENIED
        return ProviderSnapshot(
            order_status="UNKNOWN",
            capture_status="UNKNOWN",
            capture_id=None,
            order_id=order_id,
            source="api",
            raw_ref="Request timed out. Authoritative reconciliation required.",
        )
    except PayPalError as exc:
        kind = classify_capture_error(exc)
        raw_err = json.dumps(redact_dict({"error": exc.message, "status_code": exc.status_code, "issues": exc.issues}))

        if kind == "ALREADY_CAPTURED":
            # The first capture succeeded and its response was lost. This is NOT a failure:
            # read the order to get the real capture record (PayPal's documented resolution).
            try:
                recovered = await get_order(order_id)
            except (PayPalError, PayPalTimeout):
                return ProviderSnapshot(
                    order_status="UNKNOWN",
                    capture_status="UNKNOWN",
                    order_id=order_id,
                    source="api",
                    raw_ref=raw_err,
                    note="ORDER_ALREADY_CAPTURED returned, but the order could not be re-read yet.",
                )
            recovered.note = "ORDER_ALREADY_CAPTURED: recovered the original capture via GET order."
            return recovered

        if kind == "DECLINED":
            return ProviderSnapshot(
                order_status="DENIED",
                capture_status="DENIED",
                capture_id=None,
                order_id=order_id,
                source="api",
                raw_ref=raw_err,
                raw_capture_status="DECLINED",
                note="PayPal explicitly declined the payment.",
            )

        return ProviderSnapshot(
            order_status="UNKNOWN",
            capture_status="UNKNOWN",
            capture_id=None,
            order_id=order_id,
            source="api",
            raw_ref=raw_err,
            note="Unrecognised PayPal error; outcome not established, failing closed.",
        )

    return _snapshot_from_order_json(data, order_id)


async def get_order(order_id: str) -> ProviderSnapshot:
    """GET /v2/checkout/orders/{id}: order status plus purchase_units[0].payments.captures[0]."""
    resp = await paypal_client.request("GET", f"/v2/checkout/orders/{order_id}")
    return _snapshot_from_order_json(resp.json(), order_id)


async def get_capture(capture_id: str) -> ProviderSnapshot:
    """GET /v2/payments/captures/{id}: the capture resource itself (most specific status)."""
    resp = await paypal_client.request("GET", f"/v2/payments/captures/{capture_id}")
    data = resp.json()
    cap_status = data.get("status")
    norm_status = normalize_status(cap_status)
    amount = data.get("amount") or {}
    refund_state = cap_status.upper() if cap_status and cap_status.upper() in ("REFUNDED", "PARTIALLY_REFUNDED") else None
    return ProviderSnapshot(
        order_status="COMPLETED" if norm_status == "COMPLETED" else cap_status,
        capture_status=norm_status,
        capture_id=capture_id,
        order_id=None,
        source="api",
        raw_ref=json.dumps(redact_dict(data)),
        raw_capture_status=cap_status,
        pending_reason=(data.get("status_details") or {}).get("reason"),
        refund_state=refund_state,
        amount=amount.get("value"),
        currency=amount.get("currency_code"),
    )


async def refund_capture(
    capture_id: str,
    amount: Optional[float] = None,
    currency: Optional[str] = "USD",
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a refund against a completed capture."""
    body = {}
    if amount is not None:
        body["amount"] = {
            "value": f"{amount:.2f}",
            "currency_code": currency or "USD",
        }

    headers = {}
    if request_id:
        headers["PayPal-Request-Id"] = request_id

    resp = await paypal_client.request(
        "POST",
        f"/v2/payments/captures/{capture_id}/refund",
        json=body if body else None,
        headers=headers,
    )
    data = resp.json()
    return redact_dict(data)
