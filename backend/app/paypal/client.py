import time
import httpx
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

from backend.app.config import settings


class PayPalTimeout(Exception):
    """Raised when a PayPal API call times out.
    NEVER map this to payment failure or DENIED state.
    """
    def __init__(self, message: str = "PayPal API request timed out"):
        super().__init__(message)


class PayPalError(Exception):
    """Raised when PayPal returns an error response."""
    def __init__(self, status_code: int, message: str, details: Any = None):
        super().__init__(f"PayPal error {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.details = details


@dataclass
class ProviderSnapshot:
    """Normalized snapshot of payment and order state from PayPal."""
    order_status: Optional[str] = None
    capture_status: str = "UNKNOWN"  # COMPLETED | PENDING | DENIED | UNKNOWN
    capture_id: Optional[str] = None
    order_id: Optional[str] = None
    observed_at: str = ""
    source: str = "api"  # api | webhook
    raw_ref: str = ""
    is_simulated: bool = False

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PayPalClient:
    """Authoritative asynchronous client for PayPal REST APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.base_url = base_url or settings.paypal_base_url
        self.client_id = client_id or settings.PAYPAL_CLIENT_ID
        self.client_secret = client_secret or settings.PAYPAL_CLIENT_SECRET
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def get_token(self, force_refresh: bool = False) -> str:
        """Fetch or return cached OAuth2 bearer token.
        Refreshes 60 seconds before expiry.
        """
        now = time.time()
        if not force_refresh and self._cached_token and now < (self._token_expires_at - 60):
            return self._cached_token

        url = f"{self.base_url}/v1/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en_US",
        }
        data = {"grant_type": "client_credentials"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    auth=(self.client_id, self.client_secret),
                    headers=headers,
                    data=data,
                )
        except httpx.TimeoutException as exc:
            raise PayPalTimeout("OAuth2 token request timed out") from exc
        except httpx.RequestError as exc:
            raise PayPalError(500, f"Network error during OAuth token request: {exc}") from exc

        if resp.status_code != 200:
            raise PayPalError(resp.status_code, f"Failed to acquire OAuth2 token: {resp.text}")

        token_data = resp.json()
        self._cached_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 32400)
        self._token_expires_at = now + expires_in
        return self._cached_token

    async def request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> httpx.Response:
        """Execute authenticated PayPal API request with timeout safety and error normalization."""
        token = await self.get_token()
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        full_url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method=method,
                    url=full_url,
                    json=json,
                    headers=req_headers,
                )
        except httpx.TimeoutException as exc:
            # CRITICAL RULE: Timeouts NEVER map to DENIED/failure
            raise PayPalTimeout(f"PayPal request timed out: {method} {path}") from exc
        except httpx.RequestError as exc:
            raise PayPalError(500, f"PayPal connection error: {exc}") from exc

        if resp.status_code >= 400:
            raise PayPalError(
                status_code=resp.status_code,
                message=f"PayPal API error: {resp.text}",
                details=resp.text,
            )

        return resp


paypal_client = PayPalClient()
