from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from backend.app.policy.states import PaymentState


# Rule IDs as specified in Section 6.3 of in-depth.md
R01_COMPLETED_BLOCKS_RETRY = "R01_COMPLETED_BLOCKS_RETRY"
R02_PENDING_BLOCKS_RETRY = "R02_PENDING_BLOCKS_RETRY"
R03_UNKNOWN_FAILS_CLOSED = "R03_UNKNOWN_FAILS_CLOSED"
R04_DENIED_ALLOWS_RETRY = "R04_DENIED_ALLOWS_RETRY"
R05_REFUND_ONLY_COMPLETED = "R05_REFUND_ONLY_COMPLETED"
R06_VOID_ONLY_UNCAPTURED_AUTH = "R06_VOID_ONLY_UNCAPTURED_AUTH"
R07_ONE_ACTIVE_ATTEMPT = "R07_ONE_ACTIVE_ATTEMPT"
R08_AI_IS_ADVISORY = "R08_AI_IS_ADVISORY"
R09_REFUND_REQUESTED_NE_COMPLETED = "R09_REFUND_REQUESTED_NE_COMPLETED"


@dataclass
class PolicyDecision:
    """Deterministic result of the policy engine evaluation."""
    state: PaymentState
    permitted_actions: List[str]
    blocked_actions: List[Dict[str, Any]]  # {action, rule_id, reason, evidence_refs}
    requires_approval: bool
    rule_fired: str  # primary rule ID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value if isinstance(self.state, PaymentState) else str(self.state),
            "permitted_actions": self.permitted_actions,
            "blocked_actions": self.blocked_actions,
            "requires_approval": self.requires_approval,
            "rule_fired": self.rule_fired,
        }
