from typing import List, Any, Optional

from backend.app.agent.schemas import AgentInvestigationResult
from backend.app.paypal.client import ProviderSnapshot


def offline_investigate(
    snapshot: Optional[ProviderSnapshot] = None,
    attempts: Optional[List[Any]] = None,
    events: Optional[List[Any]] = None,
) -> AgentInvestigationResult:
    """Deterministic offline investigator mapping snapshot and events to AgentInvestigationResult."""
    cap_status = (snapshot.capture_status.upper() if snapshot and snapshot.capture_status else "UNKNOWN")

    # Check for completed capture
    if cap_status == "COMPLETED":
        return AgentInvestigationResult(
            classification="COMPLETED",
            summary="Authoritative PayPal record confirms capture completed successfully.",
            buyer_message="Your payment is confirmed. Your order is being processed.",
            seller_message="Payment settled. Safe to fulfill the order.",
            evidence_refs=["snapshot.capture_status", "snapshot.order_id"],
            unknowns=[],
            recommended_action="BLOCK_RETRY",
            requires_human_approval=True,
            confidence=1.0,
        )

    # Approved by the buyer but never captured: nothing is pending at PayPal, no money moved.
    if (snapshot and (snapshot.order_status or "").upper() == "APPROVED" and not snapshot.capture_id
            and cap_status == "PENDING"):
        return AgentInvestigationResult(
            classification="PENDING",
            summary="The buyer approved the order, but PayPal has no capture for it, so no money has moved. "
                    "The capture was never completed or was rejected (for example a declined card).",
            buyer_message="You have not been charged. Please try paying again, or use a different payment method.",
            seller_message="No payment received. Do not fulfill this order.",
            evidence_refs=["snapshot.order_status", "snapshot.capture_id"],
            unknowns=["why_the_capture_was_not_completed"],
            recommended_action="RECONCILE",
            requires_human_approval=False,
            confidence=0.9,
        )

    # Check for pending status
    if cap_status == "PENDING":
        return AgentInvestigationResult(
            classification="PENDING",
            summary="Payment attempt is pending provider settlement.",
            buyer_message="Your payment is processing. Please avoid re-submitting.",
            seller_message="Payment is pending. Await confirmation before fulfillment.",
            evidence_refs=["snapshot.capture_status"],
            unknowns=["bank_settlement_confirmation"],
            recommended_action="RECONCILE",
            requires_human_approval=False,
            confidence=0.85,
        )

    # Check for definitive failure
    if cap_status == "DENIED":
        return AgentInvestigationResult(
            classification="DEFINITIVE_FAILURE",
            summary="Payment was explicitly declined by PayPal.",
            buyer_message="Payment was not completed. You may attempt checkout again.",
            seller_message="Payment failed. Do not fulfill this order.",
            evidence_refs=["snapshot.capture_status"],
            unknowns=[],
            recommended_action="ALLOW_RETRY",
            requires_human_approval=True,
            confidence=0.95,
        )

    # Default: UNKNOWN / Network timeout
    return AgentInvestigationResult(
        classification="UNKNOWN",
        summary="Transaction status is unknown due to missing or unverified provider records. Fails closed.",
        buyer_message="We are verifying your transaction with PayPal. Please do not retry yet.",
        seller_message="Transaction state unconfirmed. Please wait for reconciliation before taking action.",
        evidence_refs=["snapshot.capture_status"],
        unknowns=["authoritative_paypal_capture_status"],
        recommended_action="RECONCILE",
        requires_human_approval=False,
        confidence=0.5,
    )
