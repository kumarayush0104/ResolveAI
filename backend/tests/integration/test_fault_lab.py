import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.db.models import Case, CaseEvent, Order, PaymentAttempt, User, WebhookEvent
from backend.app.services import lab as lab_service
from backend.app.services import reconciliation
from backend.app.api.routes import lab as lab_routes


async def create_case(session):
    buyer = (await session.execute(select(User).where(User.role == "buyer"))).scalar_one()
    order = Order(
        paypal_order_id=f"LAB-{uuid.uuid4().hex}",
        user_id=buyer.id,
        amount=12.50,
        currency="USD",
        status="CREATED",
    )
    session.add(order)
    await session.flush()
    case = Case(
        order_id=order.id,
        buyer_id=buyer.id,
        status="CREATED",
        current_policy_state="CREATED",
        permitted_actions=["CAPTURE"],
    )
    session.add(case)
    await session.commit()
    return order, case


def make_session_factory(session):
    return async_sessionmaker(
        bind=session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.mark.asyncio
async def test_fault_lab_requires_authentication(async_client, db_session):
    _, case = await create_case(db_session)

    response = await async_client.post(
        "/api/lab/inject-pending",
        json={"case_id": case.id},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_lost_response_is_local_and_simulated_reconciliation_completes(
    async_client, auth_tokens, db_session, monkeypatch
):
    order, case = await create_case(db_session)
    monkeypatch.setattr(lab_service, "AsyncSessionLocal", make_session_factory(db_session))
    monkeypatch.setattr(lab_service, "_schedule_simulated_reconcile", lambda case_id: None)

    response = await async_client.post(
        "/api/lab/lose-success-response",
        json={"case_id": case.id, "order_id": order.id},
        headers=auth_tokens["buyer"],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "UNKNOWN"
    assert response.json()["is_simulated"] is True
    attempt = (await db_session.execute(
        select(PaymentAttempt).where(PaymentAttempt.order_id == order.id)
    )).scalar_one()
    assert attempt.status == "UNKNOWN" and attempt.is_simulated
    assert order.status == "CREATED"

    monkeypatch.setattr(reconciliation, "AsyncSessionLocal", make_session_factory(db_session))

    async def fail_if_reconciled(*args, **kwargs):
        raise AssertionError("The background reconciler must not query simulated cases")

    monkeypatch.setattr(reconciliation, "reconcile_case", fail_if_reconciled)
    await reconciliation.run_reconciliation_cycle()

    lab_service._schedule_simulated_reconcile(case.id, delay=0)
    await asyncio.sleep(0.05)
    await db_session.refresh(case)
    await db_session.refresh(attempt)
    assert case.current_policy_state == "COMPLETED"
    assert attempt.status == "COMPLETED"
    assert attempt.paypal_capture_id is None
    detail = await async_client.get(f"/api/cases/{case.id}", headers=auth_tokens["buyer"])
    assert detail.status_code == 200
    assert detail.json()["evidence_bundle"]["status_report"]["is_simulated"] is True
    assert detail.json()["policy_decision"]["state"] == "COMPLETED"
    approval = await async_client.post(
        f"/api/cases/{case.id}/actions/REFUND/approve",
        json={},
        headers=auth_tokens["buyer"],
    )
    assert approval.status_code == 409


@pytest.mark.asyncio
async def test_single_fault_injections_apply_their_expected_behavior(async_client, auth_tokens, db_session):
    _, case = await create_case(db_session)
    response = await async_client.post(
        "/api/lab/inject-failure",
        json={"case_id": case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert response.json()["status"] == "DENIED"
    assert response.json()["permitted_actions"] == ["ALLOW_RETRY"]
    assert response.json()["requires_approval"] is True

    pending_case = (await create_case(db_session))[1]
    response = await async_client.post(
        "/api/lab/inject-pending",
        json={"case_id": pending_case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"
    assert response.json()["is_simulated"] is True

    duplicate_case = (await create_case(db_session))[1]
    response = await async_client.post(
        "/api/lab/duplicate-webhook",
        json={"case_id": duplicate_case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert response.json()["second_delivery"] == "duplicate_ignored"
    assert response.json()["duplicate_blocked"] is True
    assert response.json()["side_effect_count"] == 1
    assert len((await db_session.execute(
        select(CaseEvent).where(CaseEvent.case_id == duplicate_case.id)
    )).scalars().all()) == 1
    await db_session.refresh(duplicate_case)
    assert duplicate_case.current_policy_state == "COMPLETED"

    out_of_order_case = (await create_case(db_session))[1]
    response = await async_client.post(
        "/api/lab/out-of-order",
        json={"case_id": out_of_order_case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert response.json()["current_state"] == "COMPLETED"
    assert response.json()["regressed"] is False
    assert response.json()["events_processed"] == 2

    retry_order, retry_case = await create_case(db_session)
    response = await async_client.post(
        "/api/lab/concurrent-retry",
        json={"case_id": retry_case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert response.json()["attempt_1"] == "created"
    assert response.json()["attempt_2"] == "blocked_409"
    assert response.json()["rule_fired"] == "R07_ONE_ACTIVE_ATTEMPT"
    active = (await db_session.execute(
        select(PaymentAttempt).where(
            PaymentAttempt.order_id == retry_order.id,
            PaymentAttempt.status == "PENDING",
        )
    )).scalars().all()
    assert len(active) == 1

    injection_case = (await create_case(db_session))[1]
    response = await async_client.post(
        "/api/lab/prompt-injection",
        json={"case_id": injection_case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert response.json()["status"] == "blocked_by_policy"
    assert response.json()["rule_fired"] == "R08_AI_IS_ADVISORY"


@pytest.mark.asyncio
async def test_delayed_event_starts_pending_then_delivers_completion(
    async_client, auth_tokens, db_session, monkeypatch
):
    _, case = await create_case(db_session)
    monkeypatch.setattr(lab_routes, "AsyncSessionLocal", make_session_factory(db_session))

    response = await async_client.post(
        "/api/lab/delayed-event",
        json={"case_id": case.id, "delay_seconds": 1},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert response.json()["current_state"] == "PENDING"
    await asyncio.sleep(1.1)
    await db_session.refresh(case)
    assert case.current_policy_state == "COMPLETED"


@pytest.mark.asyncio
async def test_all_end_to_end_scenarios_are_simulated(async_client, auth_tokens, db_session, monkeypatch):
    monkeypatch.setattr(lab_service, "_schedule_simulated_reconcile", lambda case_id: None)

    _, first_case = await create_case(db_session)
    response = await async_client.post(
        "/api/lab/run-scenario-1",
        json={"case_id": first_case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert all(step["is_simulated"] for step in response.json()["steps"])
    assert "No PayPal request was made" in response.json()["steps"][0]["detail"]

    _, second_case = await create_case(db_session)
    response = await async_client.post(
        "/api/lab/run-scenario-2",
        json={"case_id": second_case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    assert response.json()["steps"][2]["rule_fired"] == "R04_DENIED_ALLOWS_RETRY"

    monkeypatch.setattr(lab_service, "AsyncSessionLocal", make_session_factory(db_session))
    monkeypatch.setattr(lab_service, "DELAYED_SCENARIO_SECONDS", 0.01)
    _, third_case = await create_case(db_session)
    response = await async_client.post(
        "/api/lab/run-scenario-3",
        json={"case_id": third_case.id},
        headers=auth_tokens["buyer"],
    )
    assert response.status_code == 200
    await asyncio.sleep(0.05)
    await db_session.refresh(third_case)
    assert third_case.current_policy_state == "COMPLETED"


@pytest.mark.asyncio
async def test_simulate_webhook_is_marked_and_updates_case_through_policy(async_client, auth_tokens, db_session):
    _, case = await create_case(db_session)

    response = await async_client.post(
        "/api/lab/simulate-webhook",
        json={"case_id": case.id, "event_type": "PAYMENT.CAPTURE.COMPLETED"},
        headers=auth_tokens["buyer"],
    )

    assert response.status_code == 200
    webhook = (await db_session.execute(
        select(WebhookEvent).where(WebhookEvent.paypal_event_id == response.json()["event_id"])
    )).scalar_one()
    assert webhook.is_simulated and webhook.processed
    await db_session.refresh(case)
    assert case.current_policy_state == "COMPLETED"
