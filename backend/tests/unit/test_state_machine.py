import pytest
from backend.app.policy.engine import evaluate
from backend.app.policy.states import PaymentState
from backend.app.paypal.client import ProviderSnapshot


def test_state_after_timeout_is_never_denied():
    """State machine core invariant: timeout must transition to UNKNOWN, never DENIED."""
    timeout_snapshot = ProviderSnapshot(
        order_status="UNKNOWN",
        capture_status="UNKNOWN",
        raw_ref="Simulated timeout exception",
    )
    decision = evaluate(snapshot=timeout_snapshot, attempts=[{"status": "UNKNOWN"}])
    assert decision.state != PaymentState.DENIED
    assert decision.state == PaymentState.UNKNOWN


def test_retry_allowed_is_false_on_pending_and_unknown():
    """State machine core invariant: retry_allowed is False if original_state in {'PENDING', 'UNKNOWN'}."""
    for st in ["PENDING", "UNKNOWN"]:
        snap = ProviderSnapshot(capture_status=st)
        decision = evaluate(snapshot=snap, attempts=[{"status": st}])
        assert "RETRY" not in decision.permitted_actions
        assert "ALLOW_RETRY" not in decision.permitted_actions


def test_full_successful_lifecycle():
    """Test standard progression: CREATED -> PENDING -> COMPLETED -> REFUND_PENDING -> REFUNDED."""
    # 1. CREATED
    dec_created = evaluate(snapshot=None, attempts=[])
    assert dec_created.state == PaymentState.CREATED
    assert "CAPTURE" in dec_created.permitted_actions

    # 2. PENDING
    snap_pending = ProviderSnapshot(capture_status="PENDING")
    dec_pending = evaluate(snapshot=snap_pending, attempts=[{"status": "PENDING"}])
    assert dec_pending.state == PaymentState.PENDING

    # 3. COMPLETED
    snap_completed = ProviderSnapshot(capture_status="COMPLETED")
    dec_completed = evaluate(snapshot=snap_completed, attempts=[{"status": "COMPLETED"}])
    assert dec_completed.state == PaymentState.COMPLETED
    assert "REFUND" in dec_completed.permitted_actions

    # 4. REFUND_PENDING
    dec_ref_pending = evaluate(snapshot=snap_completed, attempts=[], events=[{"event_type": "REFUND_REQUESTED"}])
    assert dec_ref_pending.state == PaymentState.REFUND_PENDING

    # 5. REFUNDED
    dec_refunded = evaluate(snapshot=snap_completed, attempts=[], events=[{"event_type": "REFUND_COMPLETED"}])
    assert dec_refunded.state == PaymentState.REFUNDED
