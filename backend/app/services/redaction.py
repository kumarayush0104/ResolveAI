import re
import json
from typing import Any, Dict, Union

# Common PII regex patterns
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def redact_text(text: str) -> str:
    """Mask emails and IPs in plain text strings."""
    if not isinstance(text, str):
        return text
    text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    text = IPV4_PATTERN.sub("[REDACTED_IP]", text)
    return text


def redact_dict(data: Union[Dict[str, Any], list, str, Any]) -> Any:
    """Recursively redact sensitive keys and values from dictionaries and lists."""
    if isinstance(data, dict):
        redacted = {}
        for key, val in data.items():
            k_lower = key.lower()
            if any(secret_term in k_lower for secret_term in ["client_secret", "secret", "password", "token", "auth"]):
                redacted[key] = "[REDACTED_SECRET]"
            elif any(pii_term in k_lower for pii_term in ["email", "payer_email", "email_address"]):
                redacted[key] = "[REDACTED_EMAIL]"
            elif any(name_term in k_lower for name_term in ["given_name", "surname", "full_name"]):
                redacted[key] = "[REDACTED_NAME]"
            else:
                redacted[key] = redact_dict(val)
        return redacted
    elif isinstance(data, list):
        return [redact_dict(item) for item in data]
    elif isinstance(data, str):
        return redact_text(data)
    else:
        return data


def redact_json_string(raw: str) -> str:
    """Parse JSON, redact sensitive fields, and serialize back to string."""
    try:
        obj = json.loads(raw)
        redacted = redact_dict(obj)
        return json.dumps(redacted)
    except Exception:
        return redact_text(raw)
