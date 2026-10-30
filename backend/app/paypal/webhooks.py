import json
import logging
from typing import Dict, Any

from backend.app.paypal.client import paypal_client, PayPalError, PayPalTimeout

logger = logging.getLogger(__name__)


async def verify_webhook_signature(
    headers: Dict[str, str],
    body_str: str,
    webhook_id: str,
) -> bool:
    """Verify incoming PayPal webhook signature against PayPal's verification endpoint.
    Headers are case-insensitive. Returns True ONLY if verification_status == 'SUCCESS'.
    """
    if not webhook_id:
        logger.warning("No webhook_id provided for signature verification.")
        return False

    # Normalize header keys to lowercase
    lower_headers = {k.lower(): v for k, v in headers.items()}

    transmission_id = lower_headers.get("paypal-transmission-id")
    transmission_time = lower_headers.get("paypal-transmission-time")
    cert_url = lower_headers.get("paypal-cert-url")
    auth_algo = lower_headers.get("paypal-auth-algo")
    transmission_sig = lower_headers.get("paypal-transmission-sig")

    if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]):
        logger.warning("Missing required PayPal webhook verification headers.")
        return False

    try:
        event_body = json.loads(body_str) if isinstance(body_str, str) else body_str
    except Exception as exc:
        logger.warning("Failed to parse webhook body as JSON: %s", exc)
        return False

    verify_payload = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": webhook_id,
        "webhook_event": event_body,
    }

    try:
        resp = await paypal_client.request(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            json=verify_payload,
        )
        data = resp.json()
        status = data.get("verification_status", "").upper()
        return status == "SUCCESS"
    except (PayPalError, PayPalTimeout) as exc:
        logger.warning("Webhook signature verification failed with error: %s", exc)
        return False
    except Exception as exc:
        logger.exception("Unexpected error verifying webhook signature: %s", exc)
        return False
