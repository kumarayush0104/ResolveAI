"""Multi-source payment status check.

Asks PayPal the same question three ways and reports whether the answers agree:

1. Orders API v2       GET /v2/checkout/orders/{id}        (order + embedded capture)
2. Payments API v2     GET /v2/payments/captures/{id}      (the capture itself)
3. Transaction Search  GET /v1/reporting/transactions      (reporting, lags up to ~3h)

Verified webhook events are listed for context but never decide the status on their own:
they are delivered at-least-once and out of order, so a webhook only triggers a fresh check.

The verdict handed to the policy engine is a ProviderSnapshot. If the sources disagree in a way
we cannot explain, the snapshot is UNKNOWN (fail closed) and flagged as a conflict.
"""
import asyncio
import logging
from dataclasses import dataclass, field, asdict, replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.paypal.client import ProviderSnapshot, PayPalError, PayPalTimeout
from backend.app.paypal.orders import get_order, get_capture
from backend.app.paypal.transactions import (
    TransactionSearchResult,
    search_transaction,
    OK as SEARCH_OK,
)

logger = logging.getLogger(__name__)

ORDERS_API = "ORDERS_API"
PAYMENTS_API = "PAYMENTS_API"
TRANSACTION_SEARCH = "TRANSACTION_SEARCH"
WEBHOOKS = "WEBHOOKS"

_WEBHOOK_STATUS = {
    "PAYMENT.CAPTURE.COMPLETED": "COMPLETED",
    "PAYMENT.CAPTURE.PENDING": "PENDING",
    "PAYMENT.CAPTURE.DENIED": "DENIED",
    "PAYMENT.CAPTURE.DECLINED": "DENIED",
    "PAYMENT.CAPTURE.REFUNDED": "COMPLETED",
    "PAYMENT.CAPTURE.REVERSED": "REVERSED",
}


@dataclass
class SourceResult:
    source: str
    ok: bool                       # did PayPal answer with usable data?
    normalized: str = "UNKNOWN"    # COMPLETED | PENDING | DENIED | REVERSED | UNKNOWN
    raw_status: Optional[str] = None
    detail: str = ""
    resource_id: Optional[str] = None
    availability: str = "ok"
    authoritative: bool = True     # webhooks are context only
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StatusReport:
    order_id: str
    capture_id: Optional[str]
    consensus: str                         # COMPLETED | PENDING | DENIED | UNKNOWN | CONFLICT
    sources: List[SourceResult]
    conflicts: List[str]
    notes: List[str]
    snapshot: ProviderSnapshot             # what the policy engine evaluates
    reachable: bool                        # at least one authoritative source answered
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "capture_id": self.capture_id,
            "consensus": self.consensus,
            "agrees": self.consensus not in ("CONFLICT",) and not self.conflicts,
            "sources": [s.to_dict() for s in self.sources],
            "conflicts": self.conflicts,
            "notes": self.notes,
            "snapshot": self.snapshot.to_dict(),
            "reachable": self.reachable,
            "checked_at": self.checked_at,
        }

    def summary_line(self) -> str:
        parts = []
        for s in self.sources:
            if not s.authoritative:
                continue
            label = {ORDERS_API: "Orders API", PAYMENTS_API: "Payments API", TRANSACTION_SEARCH: "Transaction Search"}.get(s.source, s.source)
            if s.ok:
                parts.append(f"{label}={s.raw_status or s.normalized}")
            else:
                parts.append(f"{label}=unavailable")
        verdict = self.consensus if self.consensus != "CONFLICT" else "CONFLICT (failed closed)"
        return f"Checked PayPal: {', '.join(parts) or 'no source reachable'} -> {verdict}"


def _src_from_snapshot(source: str, snap: ProviderSnapshot, resource_id: Optional[str]) -> SourceResult:
    return SourceResult(
        source=source,
        ok=True,
        normalized=snap.capture_status,
        raw_status=snap.raw_capture_status or snap.order_status,
        detail=snap.pending_reason and f"Pending reason: {snap.pending_reason}" or "",
        resource_id=resource_id,
    )


def _src_failed(source: str, exc: BaseException, resource_id: Optional[str]) -> SourceResult:
    if isinstance(exc, PayPalTimeout):
        detail = "Timed out. Outcome not established."
    elif isinstance(exc, PayPalError):
        detail = f"PayPal returned HTTP {exc.status_code}."
    else:
        detail = "Lookup failed."
    return SourceResult(source=source, ok=False, normalized="UNKNOWN", detail=detail, resource_id=resource_id, availability="unavailable")


def _src_from_search(res: TransactionSearchResult) -> SourceResult:
    return SourceResult(
        source=TRANSACTION_SEARCH,
        ok=res.has_verdict,
        normalized=res.normalized if res.has_verdict else "UNKNOWN",
        raw_status=res.status_code,
        detail=res.note,
        resource_id=res.transaction_id,
        availability=res.availability,
    )


def _webhook_source(events: List[Any]) -> Optional[SourceResult]:
    relevant = [e for e in events if getattr(e, "event_type", "") in _WEBHOOK_STATUS and getattr(e, "verified", False)]
    if not relevant:
        return None
    latest = max(relevant, key=lambda e: getattr(e, "created_at", datetime.min.replace(tzinfo=timezone.utc)))
    return SourceResult(
        source=WEBHOOKS,
        ok=True,
        normalized=_WEBHOOK_STATUS[latest.event_type],
        raw_status=latest.event_type,
        detail=f"{len(relevant)} verified event(s). Context only: a webhook triggers a fresh check, it does not decide status.",
        resource_id=getattr(latest, "resource_id", None),
        authoritative=False,
    )


def _decide(primary: Optional[SourceResult], primary_snap: Optional[ProviderSnapshot],
            order_src: Optional[SourceResult], search: Optional[SourceResult]) -> tuple:
    """Return (consensus, conflicts, notes, verdict_source). verdict_source in {'primary','search',None}."""
    conflicts: List[str] = []
    notes: List[str] = []

    # Orders API vs Payments API: the capture resource is more specific, but they must not contradict.
    if order_src and order_src.ok and primary is not order_src and primary and primary.ok:
        if order_src.normalized != primary.normalized:
            conflicts.append(
                f"Orders API says {order_src.raw_status or order_src.normalized} but the capture says "
                f"{primary.raw_status or primary.normalized}."
            )

    search_ok = bool(search and search.ok)
    primary_ok = bool(primary and primary.ok)

    if not primary_ok and not search_ok:
        return "UNKNOWN", conflicts, notes, None

    if not primary_ok and search_ok:
        if search.normalized == "REVERSED":
            conflicts.append("Transaction Search reports the transaction was reversed, but the Orders/Payments API could not confirm.")
            return "CONFLICT", conflicts, notes, None
        notes.append("Orders/Payments API unreachable; status taken from Transaction Search.")
        return search.normalized, conflicts, notes, "search"

    if primary_ok and not search_ok:
        if search and search.availability != SEARCH_OK:
            notes.append(f"Transaction Search: {search.detail}" if search.detail else "Transaction Search had no answer.")
        return ("CONFLICT" if conflicts else primary.normalized), conflicts, notes, "primary"

    # Both answered.
    p, s = primary.normalized, search.normalized
    refunded = bool(primary_snap and primary_snap.refund_state)
    if p == s:
        pass
    elif p in ("COMPLETED", "DENIED") and s == "PENDING":
        notes.append("Transaction Search still shows Pending. Reporting data can lag, so the live API result is used.")
    elif s == "REVERSED" and p == "COMPLETED" and refunded:
        pass  # reversal corroborates the refund the API already reports
    else:
        conflicts.append(
            f"Transaction Search says {search.raw_status or s} but the Orders/Payments API says "
            f"{primary.raw_status or p}."
        )
    return ("CONFLICT" if conflicts else p), conflicts, notes, "primary"


async def check_payment_status(order: Any, attempts: List[Any], webhook_events: Optional[List[Any]] = None) -> StatusReport:
    """Query every source and decide. Never raises for PayPal/network trouble."""
    webhook_events = webhook_events or []
    paypal_order_id: str = order.paypal_order_id

    # Capture IDs on simulated attempts are fake: never send them to PayPal.
    known_capture_id = next(
        (a.paypal_capture_id for a in attempts if a.paypal_capture_id and not getattr(a, "is_simulated", False)),
        None,
    )

    order_snap: Optional[ProviderSnapshot] = None
    order_src: SourceResult
    try:
        order_snap = await get_order(paypal_order_id)
        order_src = _src_from_snapshot(ORDERS_API, order_snap, paypal_order_id)
    except (PayPalError, PayPalTimeout, Exception) as exc:  # noqa: BLE001 - lookups must never raise
        order_src = _src_failed(ORDERS_API, exc, paypal_order_id)

    capture_id = known_capture_id or (order_snap.capture_id if order_snap else None)

    cap_snap: Optional[ProviderSnapshot] = None
    cap_src: Optional[SourceResult] = None
    search_src: Optional[SourceResult] = None

    if capture_id:
        cap_res, search_res = await asyncio.gather(
            get_capture(capture_id),
            search_transaction(capture_id, anchor=getattr(order, "created_at", None)),
            return_exceptions=True,
        )
        if isinstance(cap_res, BaseException):
            cap_src = _src_failed(PAYMENTS_API, cap_res, capture_id)
        else:
            cap_snap = cap_res
            cap_src = _src_from_snapshot(PAYMENTS_API, cap_snap, capture_id)
        if isinstance(search_res, BaseException):
            search_src = _src_failed(TRANSACTION_SEARCH, search_res, capture_id)
        else:
            search_src = _src_from_search(search_res)

    # The capture resource is the most specific evidence; fall back to the order.
    if cap_src and cap_src.ok:
        primary, primary_snap = cap_src, cap_snap
    elif order_src.ok:
        primary, primary_snap = order_src, order_snap
    else:
        primary, primary_snap = None, None

    consensus, conflicts, notes, verdict_from = _decide(primary, primary_snap, order_src, search_src)

    sources: List[SourceResult] = [order_src]
    if cap_src:
        sources.append(cap_src)
    if search_src:
        sources.append(search_src)
    wh = _webhook_source(webhook_events)
    if wh:
        sources.append(wh)

    reachable = any(s.ok and s.authoritative for s in sources)

    # Build the snapshot the policy engine will judge.
    if consensus == "CONFLICT":
        base = primary_snap or order_snap
        snapshot = ProviderSnapshot(
            order_status=base.order_status if base else None,
            capture_status="UNKNOWN",
            capture_id=capture_id,
            order_id=paypal_order_id,
            source="api",
            raw_ref=(base.raw_ref if base else ""),
            raw_capture_status=base.raw_capture_status if base else None,
            conflict=True,
            note="Sources disagree: " + " ".join(conflicts),
        )
    elif verdict_from == "primary" and primary_snap is not None:
        snapshot = replace(primary_snap, order_id=paypal_order_id)
        if capture_id and not snapshot.capture_id:
            snapshot.capture_id = capture_id
        if order_snap and not snapshot.order_status:
            snapshot.order_status = order_snap.order_status
        if notes:
            snapshot.note = " ".join(notes)
    elif verdict_from == "search":
        snapshot = ProviderSnapshot(
            order_status=order_snap.order_status if order_snap else None,
            capture_status=consensus,
            capture_id=capture_id,
            order_id=paypal_order_id,
            source="api",
            raw_ref=search_src.detail if search_src else "",
            raw_capture_status=search_src.raw_status if search_src else None,
            note=" ".join(notes),
        )
    else:
        snapshot = ProviderSnapshot(
            order_status="UNKNOWN",
            capture_status="UNKNOWN",
            capture_id=capture_id,
            order_id=paypal_order_id,
            source="api",
            raw_ref="No PayPal source could be reached. Reconciliation will retry.",
            note="No source reachable.",
        )

    return StatusReport(
        order_id=paypal_order_id,
        capture_id=capture_id,
        consensus=consensus,
        sources=sources,
        conflicts=conflicts,
        notes=notes,
        snapshot=snapshot,
        reachable=reachable,
    )
