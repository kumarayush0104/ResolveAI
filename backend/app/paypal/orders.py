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
        # Non-2xx response from PayPal
        raw_err = redact_dict({"error": exc.message, "status_code": exc.status_code})
        return ProviderSnapshot(
            order_status="DENIED" if exc.status_code in (400, 422) else "UNKNOWN",
            capture_status="DENIED" if exc.status_code in (400, 422) else "UNKNOWN",
            capture_id=None,
            order_id=order_id,
            source="api",
            raw_ref=json.dumps(raw_err),
        )

    redacted_data = redact_dict(data)
    raw_json = json.dumps(redacted_data)

    order_status = data.get("status")
    capture_id = None
    capture_status_str = None

    # Extract capture details from purchase_units if present
    purchase_units = data.get("purchase_units", [])
    if purchase_units:
        payments = purchase_units[0].get("payments", {})
        captures = payments.get("captures", [])
        if captures:
            first_capture = captures[0]
            capture_id = first_capture.get("id")
            capture_status_str = first_capture.get("status")

    norm_status = normalize_status(capture_status_str or order_status)

    return ProviderSnapshot(
        order_status=order_status,
        capture_status=norm_status,
        capture_id=capture_id,
        order_id=order_id,
        source="api",
        raw_ref=raw_json,
    )


async def get_order(order_id: str) -> ProviderSnapshot:
    """Fetch order details from PayPal and normalize to ProviderSnapshot."""
    resp = await paypal_client.request("GET", f"/v2/checkout/orders/{order_id}")
    data = resp.json()
    redacted_data = redact_dict(data)
    raw_json = json.dumps(redacted_data)

    order_status = data.get("status")
    capture_id = None
    capture_status_str = None

    purchase_units = data.get("purchase_units", [])
    if purchase_units:
        payments = purchase_units[0].get("payments", {})
        captures = payments.get("captures", [])
        if captures:
            first_capture = captures[0]
            capture_id = first_capture.get("id")
            capture_status_str = first_capture.get("status")

    norm_status = normalize_status(capture_status_str or order_status)

    return ProviderSnapshot(
        order_status=order_status,
        capture_status=norm_status,
        capture_id=capture_id,
        order_id=order_id,
        source="api",
        raw_ref=raw_json,
    )


async def get_capture(capture_id: str) -> ProviderSnapshot:
    """Fetch capture details from PayPal payments API and normalize to ProviderSnapshot."""
    resp = await paypal_client.request("GET", f"/v2/payments/captures/{capture_id}")
    data = resp.json()
    redacted_data = redact_dict(data)
    raw_json = json.dumps(redacted_data)

    cap_status = data.get("status")
    norm_status = normalize_status(cap_status)

    return ProviderSnapshot(
        order_status="COMPLETED" if norm_status == "COMPLETED" else cap_status,
        capture_status=norm_status,
        capture_id=capture_id,
        order_id=None,
        source="api",
        raw_ref=raw_json,
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
