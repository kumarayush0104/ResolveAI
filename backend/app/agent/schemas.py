from typing import List, Optional
from pydantic import BaseModel, Field


class AgentInvestigationResult(BaseModel):
    """Authoritative structured output contract from the AI Investigator."""
    classification: str = Field(
        ...,
        description="PENDING | COMPLETED | DEFINITIVE_FAILURE | UNKNOWN | CONFLICT"
    )
    summary: str = Field(
        ...,
        description="Plain-language explanation grounded in evidence"
    )
    buyer_message: str = Field(
        ...,
        description="Short, reassuring, accurate message for the buyer"
    )
    seller_message: str = Field(
        ...,
        description="Short fulfillment guidance for the seller"
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="References to exact fields in the evidence bundle"
    )
    unknowns: List[str] = Field(
        default_factory=list,
        description="List of unresolved or unverified ambiguities"
    )
    recommended_action: str = Field(
        ...,
        description="RECONCILE | BLOCK_RETRY | ALLOW_RETRY | ESCALATE"
    )
    requires_human_approval: bool = Field(
        default=True,
        description="Whether this action requires human confirmation"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )


class CaseMessageCreate(BaseModel):
    message: str = Field(..., max_length=1000)


class ActionApproveRequest(BaseModel):
    notes: Optional[str] = None
