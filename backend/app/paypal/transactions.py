"""PayPal Transaction Search API adapter (GET /v1/reporting/transactions).

Transaction Search is a *reporting* API, so it is treated as secondary evidence:

* Executed transactions can take up to ~3 hours to appear, so "not found" is NOT "failed".
* The date range is required (even when filtering by transaction_id) and capped at 31 days.
* The app needs the Transaction Search feature enabled; the permission can take up to
  9 hours to reach a fresh access token. Until then PayPal answers 403. That is reported
  as availability="not_enabled" and never breaks the main payment flow.
* A transaction ID is not guaranteed unique in the reporting system, so several rows can
  come back for one ID. If they disagree we report UNKNOWN rather than pick one.

Status codes: S = success, P = pending, D = denied, V = reversed.
"""
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.app.paypal.client import PayPalClient, PayPalError, PayPalTimeout, paypal_client
from backend.app.services.redaction import redact_dict

logger = logging.getLogger(__name__)

MAX_RANGE = timedelta(days=31)
INDEX_LAG = timedelta(hours=3)          # documented maximum delay before a transaction is listed
INDEX_LAG_MARGIN = timedelta(minutes=15)

STATUS_MAP = {
    "S": "COMPLETED",
    "P": "PENDING",
    "D": "DENIED",
    "V": "REVERSED",
}

# availability values
OK = "ok"
NOT_FOUND = "not_found"
NOT_INDEXED_YET = "not_indexed_yet"
NOT_ENABLED = "not_enabled"
UNAVAILABLE = "unavailable"


@dataclass
class TransactionSearchResult:
    availability: str = UNAVAILABLE
    transaction_id: Optional[str] = None
    status_code: Optional[str] = None       # S | P | D | V
    normalized: str = "UNKNOWN"             # COMPLETED | PENDING | DENIED | REVERSED | UNKNOWN
    amount: Optional[str] = None
    currency: Optional[str] = None
    initiated_at: Optional[str] = None
    updated_at: Optional[str] = None
    match_count: int = 0
    note: str = ""
    raw_ref: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def has_verdict(self) -> bool:
        """True only when PayPal returned a usable status for this transaction."""
        return self.availability == OK and self.normalized in ("COMPLETED", "PENDING", "DENIED", "REVERSED")


def format_date(dt: datetime) -> str:
    """PayPal wants an RFC 3339 timestamp with seconds. We always send UTC with a trailing Z."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_window(anchor: Optional[datetime], now: Optional[datetime] = None) -> tuple:
    """Return (start, end) no wider than 31 days.

    With an anchor (e.g. when the order was created) the window starts a day before it.
    Without one we look back over the most recent 30 days.
    """
    now = now or datetime.now(timezone.utc)
    if anchor is None:
        start = now - timedelta(days=30)
    else:
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        start = anchor - timedelta(days=1)
    end = min(now, start + MAX_RANGE - timedelta(seconds=1))
    if end <= start:
        end = start + timedelta(hours=1)
    return start, end


def _info_to_row(info: Dict[str, Any]) -> Dict[str, Any]:
    amt = info.get("transaction_amount") or {}
    return {
        "transaction_id": info.get("transaction_id"),
        "status_code": (info.get("transaction_status") or "").upper() or None,
        "amount": amt.get("value"),
        "currency": amt.get("currency_code"),
        "initiated_at": info.get("transaction_initiation_date"),
        "updated_at": info.get("transaction_updated_date"),
    }


def parse_response(
    body: Dict[str, Any],
    transaction_id: str,
    anchor: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> TransactionSearchResult:
    """Turn a Transaction Search response body into a normalized result."""
    now = now or datetime.now(timezone.utc)
    raw_ref = json.dumps(redact_dict({"transaction_details": [
        {"transaction_info": d.get("transaction_info", {})} for d in body.get("transaction_details", [])
    ]}))

    rows: List[Dict[str, Any]] = [
        _info_to_row(d.get("transaction_info") or {})
        for d in body.get("transaction_details", [])
    ]
    rows = [r for r in rows if r["transaction_id"] == transaction_id]

    if not rows:
        # Absence proves nothing. Within the reporting delay it is expected.
        young = anchor is not None and (now - (anchor if anchor.tzinfo else anchor.replace(tzinfo=timezone.utc))) < (INDEX_LAG + INDEX_LAG_MARGIN)
        if young:
            return TransactionSearchResult(
                availability=NOT_INDEXED_YET,
                transaction_id=transaction_id,
                note="Not listed yet. Transaction Search can lag by up to 3 hours. This is not a failure.",
                raw_ref=raw_ref,
            )
        return TransactionSearchResult(
            availability=NOT_FOUND,
            transaction_id=transaction_id,
            note="No record in this date window. It may be outside the window or not indexed yet.",
            raw_ref=raw_ref,
        )

    codes = {r["status_code"] for r in rows}
    first = rows[0]
    if len(codes) > 1:
        return TransactionSearchResult(
            availability=OK,
            transaction_id=transaction_id,
            normalized="UNKNOWN",
            match_count=len(rows),
            note=f"{len(rows)} records share this ID with different statuses ({', '.join(sorted(c or '?' for c in codes))}).",
            raw_ref=raw_ref,
        )

    code = first["status_code"]
    normalized = STATUS_MAP.get(code or "", "UNKNOWN")
    return TransactionSearchResult(
        availability=OK,
        transaction_id=transaction_id,
        status_code=code,
        normalized=normalized,
        amount=first["amount"],
        currency=first["currency"],
        initiated_at=first["initiated_at"],
        updated_at=first["updated_at"],
        match_count=len(rows),
        note="" if normalized != "UNKNOWN" else f"Unrecognised transaction_status '{code}'.",
        raw_ref=raw_ref,
    )


async def search_transaction(
    transaction_id: str,
    *,
    anchor: Optional[datetime] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    client: Optional[PayPalClient] = None,
) -> TransactionSearchResult:
    """Look up one transaction by its PayPal transaction ID (a capture ID is one).

    Never raises for PayPal/network problems: those become an availability value so callers
    can treat the lookup as optional evidence.
    """
    client = client or paypal_client
    now = datetime.now(timezone.utc)
    if start is None or end is None:
        start, end = build_window(anchor, now)
    if end - start > MAX_RANGE:
        end = start + MAX_RANGE - timedelta(seconds=1)

    params = {
        "transaction_id": transaction_id,
        "start_date": format_date(start),
        "end_date": format_date(end),
        "fields": "transaction_info",
        "page_size": 100,
        "page": 1,
    }

    try:
        resp = await client.request("GET", "/v1/reporting/transactions", params=params)
        body = resp.json()
    except PayPalTimeout:
        return TransactionSearchResult(
            availability=UNAVAILABLE,
            transaction_id=transaction_id,
            note="Transaction Search timed out. Outcome not established.",
        )
    except PayPalError as exc:
        if exc.status_code in (401, 403):
            return TransactionSearchResult(
                availability=NOT_ENABLED,
                transaction_id=transaction_id,
                note=(
                    "Transaction Search is not enabled for this app. In the developer dashboard open your app, "
                    "turn on Features > Transaction Search, then wait for a fresh access token "
                    "(it can take up to 9 hours)."
                ),
            )
        logger.warning("Transaction Search error %s: %s", exc.status_code, exc.message)
        return TransactionSearchResult(
            availability=UNAVAILABLE,
            transaction_id=transaction_id,
            note=f"Transaction Search returned HTTP {exc.status_code}.",
        )
    except ValueError:
        return TransactionSearchResult(
            availability=UNAVAILABLE,
            transaction_id=transaction_id,
            note="Transaction Search returned an unreadable response.",
        )

    return parse_response(body, transaction_id, anchor=anchor, now=now)
