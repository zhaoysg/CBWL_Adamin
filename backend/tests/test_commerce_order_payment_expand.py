from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.api.v1.module_commerce.order_payment.model import (
    CommerceOrderModel,
    PaymentAttemptModel,
    PaymentEventModel,
)
from app.api.v1.module_commerce.order_payment.ownership import CommerceOwner
from app.api.v1.module_commerce.order_payment.schema import (
    MembershipOrderCreateSchema,
    OrderCancelSchema,
    PaymentAttemptCreateSchema,
    ProviderEventRegisterSchema,
)
from app.api.v1.module_commerce.order_payment.service import (
    CommerceOrderService,
    PaymentService,
)
from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_identity.model import AuthSubjectModel, CustomerModel
from app.core.database import async_db_session
from app.core.exceptions import CustomException


def _data(response):
    payload = response.json()
    assert payload["success"] is True, payload
    return payload["data"]


def _suffix() -> str:
    return uuid4().hex[:10]


def test_command_schemas_reject_client_amount_and_raw_callback_payload() -> None:
    with pytest.raises(ValidationError):
        MembershipOrderCreateSchema.model_validate(
            {
                "plan_id": 1,
                "request_key": "client-price",
                "amount": "0.01",
            }
        )

    with pytest.raises(ValidationError):
        ProviderEventRegisterSchema.model_validate(
            {
                "payment_no": "CPTEST",
                "provider": "wechat",
                "provider_event_id": "evt-test",
                "event_type": "payment_succeeded",
                "payload_digest": "a" * 64,
                "raw_payload": {"transaction_id": "must-not-be-persisted"},
            }
        )


def _create_user(test_client: TestClient, suffix: str) -> int:
    response = test_client.post(
        "/system/user/register",
        json={
            "username": f"commerce_{suffix}"[:32],
            "password": "Commerce123!",
            "name": f"交易用户{suffix[:6]}",
        },
    )
    assert response.status_code == 200, response.text
    return int(_data(response)["id"])


def _create_plan(
    test_client: TestClient,
    auth_headers: dict[str, str],
    *,
    suffix: str,
    price: str = "199.00",
    rank: int = 20,
) -> dict:
    response = test_client.post(
        "/membership/plan/create",
        headers=auth_headers,
        json={
            "plan_code": f"commerce-{rank}-{suffix}",
            "plan_name": f"交易套餐-{rank}-{suffix}",
            "rank": rank,
            "price": price,
            "currency": "CNY",
            "duration_days": 365,
            "benefits": ["会员内容", "年度复盘"],
            "status": 0,
            "sort_no": rank,
        },
    )
    assert response.status_code == 201, response.text
    return _data(response)


async def _create_customer_only_owner(db, *, suffix: str) -> CommerceOwner:
    subject = AuthSubjectModel(
        realm="customer",
        status="active",
        version_no=1,
    )
    db.add(subject)
    await db.flush()

    customer = CustomerModel(
        subject_id=subject.id,
        realm="customer",
        customer_no=f"CN{suffix.upper().zfill(12)}"[:32],
        nickname=f"纯客户{suffix[:6]}",
        register_source="h5",
        status="active",
        version_no=1,
    )
    db.add(customer)
    await db.flush()
    return CommerceOwner.customer(customer.id, subject_id=subject.id)


async def _create_customer_owner(
    db,
    *,
    legacy_user_id: int,
    suffix: str,
) -> CommerceOwner:
    subject = AuthSubjectModel(
        realm="customer",
        status="active",
        version_no=1,
    )
    db.add(subject)
    await db.flush()

    customer = CustomerModel(
        subject_id=subject.id,
        realm="customer",
        customer_no=f"CC{suffix.upper().zfill(12)}"[:32],
        nickname=f"客户{suffix[:6]}",
        register_source="migration",
        status="active",
        version_no=1,
    )
    db.add(customer)
    await db.flush()

    mapping = LegacyCustomerMapModel(
        legacy_sys_user_id=legacy_user_id,
        customer_id=customer.id,
        credential_state="migrated",
        source="manual",
        reason_code=None,
        identifier_snapshot=f"commerce_{suffix}",
        migrated_at=datetime.now(UTC),
        version_no=1,
    )
    db.add(mapping)
    await db.flush()

    return CommerceOwner.customer(
        customer.id,
        legacy_user_id=legacy_user_id,
        subject_id=subject.id,
    )


@pytest.mark.asyncio
async def test_legacy_and_customer_only_order_ownership_shapes(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    legacy_user_id = _create_user(test_client, f"legacy-{suffix}")
    plan = _create_plan(test_client, auth_headers, suffix=f"shape-{suffix}")

    async with async_db_session() as db, db.begin():
        service = CommerceOrderService(db)
        legacy_order = await service.create_membership_order(
            CommerceOwner.legacy(legacy_user_id),
            MembershipOrderCreateSchema(
                plan_id=plan["id"],
                request_key=f"legacy-shape-{suffix}",
            ),
        )
        customer_owner = await _create_customer_only_owner(db, suffix=suffix)
        customer_order = await service.create_membership_order(
            customer_owner,
            MembershipOrderCreateSchema(
                plan_id=plan["id"],
                request_key=f"customer-shape-{suffix}",
            ),
        )

        assert legacy_order.legacy_user_id == legacy_user_id
        assert legacy_order.customer_id is None
        assert customer_order.legacy_user_id is None
        assert customer_order.customer_id == customer_owner.customer_id


@pytest.mark.asyncio
async def test_membership_order_uses_server_plan_snapshot_and_idempotency(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    user_id = _create_user(test_client, suffix)
    plan = _create_plan(test_client, auth_headers, suffix=suffix)
    other_plan = _create_plan(
        test_client,
        auth_headers,
        suffix=f"other-{suffix}",
        price="399.00",
        rank=30,
    )

    async with async_db_session() as db, db.begin():
        owner = await _create_customer_owner(
            db,
            legacy_user_id=user_id,
            suffix=suffix,
        )
        service = CommerceOrderService(db)
        command = MembershipOrderCreateSchema(
            plan_id=plan["id"],
            request_key=f"order-{suffix}",
            payment_window_seconds=900,
            description="H5年度会员下单",
        )

        first = await service.create_membership_order(owner, command)
        second = await service.create_membership_order(owner, command)

        assert second.id == first.id
        assert first.order_no.startswith("CO")
        assert first.legacy_user_id == user_id
        assert first.customer_id == owner.customer_id
        assert first.plan_code_snapshot == plan["plan_code"]
        assert first.plan_name_snapshot == plan["plan_name"]
        assert first.plan_level_no_snapshot == plan["rank"]
        assert first.duration_days_snapshot == plan["duration_days"]
        assert first.benefits_snapshot == plan["benefits"]
        assert str(first.amount) == "199.00"
        assert first.currency == "CNY"
        assert first.status == "pending"
        assert first.version_no == 1

        count = await db.scalar(
            select(func.count())
            .select_from(CommerceOrderModel)
            .where(CommerceOrderModel.customer_id == owner.customer_id)
        )
        assert count == 1

        with pytest.raises(CustomException) as conflict:
            await service.create_membership_order(
                owner,
                command.model_copy(update={"plan_id": other_plan["id"]}),
            )
        assert conflict.value.status_code == 409


@pytest.mark.asyncio
async def test_customer_mapping_mismatch_fails_closed_without_order(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    mapped_user_id = _create_user(test_client, suffix)
    wrong_user_id = _create_user(test_client, f"wrong-{suffix}")
    plan = _create_plan(test_client, auth_headers, suffix=suffix)

    async with async_db_session() as db, db.begin():
        owner = await _create_customer_owner(
            db,
            legacy_user_id=mapped_user_id,
            suffix=suffix,
        )
        mismatched = CommerceOwner.customer(
            owner.customer_id,
            legacy_user_id=wrong_user_id,
            subject_id=owner.subject_id,
        )

        with pytest.raises(CustomException) as unavailable:
            await CommerceOrderService(db).create_membership_order(
                mismatched,
                MembershipOrderCreateSchema(
                    plan_id=plan["id"],
                    request_key=f"mismatch-{suffix}",
                ),
            )
        assert unavailable.value.status_code == 503
        count = await db.scalar(
            select(func.count())
            .select_from(CommerceOrderModel)
            .where(CommerceOrderModel.customer_id == owner.customer_id)
        )
        assert count == 0


@pytest.mark.asyncio
async def test_order_creation_rolls_back_with_caller_transaction(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    user_id = _create_user(test_client, f"rollback-{suffix}")
    plan = _create_plan(test_client, auth_headers, suffix=f"rollback-{suffix}")

    async with async_db_session() as db, db.begin():
        owner = await _create_customer_owner(
            db,
            legacy_user_id=user_id,
            suffix=f"rollback-{suffix}",
        )

    with pytest.raises(RuntimeError, match="force outer rollback"):
        async with async_db_session() as db, db.begin():
            await CommerceOrderService(db).create_membership_order(
                owner,
                MembershipOrderCreateSchema(
                    plan_id=plan["id"],
                    request_key=f"rollback-order-{suffix}",
                ),
            )
            raise RuntimeError("force outer rollback")

    async with async_db_session() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(CommerceOrderModel)
            .where(CommerceOrderModel.customer_id == owner.customer_id)
        )
        assert count == 0


@pytest.mark.asyncio
async def test_payment_attempt_copies_order_ownership_and_is_idempotent(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    user_id = _create_user(test_client, suffix)
    plan = _create_plan(test_client, auth_headers, suffix=suffix)

    async with async_db_session() as db, db.begin():
        owner = await _create_customer_owner(
            db,
            legacy_user_id=user_id,
            suffix=suffix,
        )
        order = await CommerceOrderService(db).create_membership_order(
            owner,
            MembershipOrderCreateSchema(
                plan_id=plan["id"],
                request_key=f"payment-order-{suffix}",
            ),
        )
        service = PaymentService(db)
        command = PaymentAttemptCreateSchema(
            order_no=order.order_no,
            provider="wechat",
            channel="jsapi",
            request_key=f"payment-{suffix}",
        )

        first = await service.create_attempt(owner, command)
        second = await service.create_attempt(owner, command)

        assert second.id == first.id
        assert first.payment_no.startswith("CP")
        assert first.order_id == order.id
        assert first.order_no == order.order_no
        assert first.legacy_user_id == order.legacy_user_id
        assert first.customer_id == order.customer_id
        assert first.amount == order.amount
        assert first.currency == order.currency
        assert first.status == "pending"

        count = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptModel)
            .where(PaymentAttemptModel.order_id == order.id)
        )
        assert count == 1

        with pytest.raises(CustomException) as conflict:
            await service.create_attempt(
                owner,
                command.model_copy(update={"provider": "alipay"}),
            )
        assert conflict.value.status_code == 409


@pytest.mark.asyncio
async def test_cancelled_and_expired_orders_cannot_start_payment(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    user_id = _create_user(test_client, suffix)
    plan = _create_plan(test_client, auth_headers, suffix=suffix)
    current = datetime.now(UTC)

    async with async_db_session() as db, db.begin():
        owner = await _create_customer_owner(
            db,
            legacy_user_id=user_id,
            suffix=suffix,
        )
        order_service = CommerceOrderService(db)
        payment_service = PaymentService(db)

        cancelled = await order_service.create_membership_order(
            owner,
            MembershipOrderCreateSchema(
                plan_id=plan["id"],
                request_key=f"cancel-{suffix}",
            ),
            now=current,
        )
        with pytest.raises(CustomException) as stale:
            await order_service.cancel(
                owner,
                cancelled.order_no,
                OrderCancelSchema(version_no=99, reason="过期版本"),
            )
        assert stale.value.status_code == 409

        cancelled = await order_service.cancel(
            owner,
            cancelled.order_no,
            OrderCancelSchema(
                version_no=cancelled.version_no,
                reason="客户主动取消",
            ),
        )
        assert cancelled.status == "cancelled"
        assert cancelled.version_no == 2

        with pytest.raises(CustomException) as cancelled_error:
            await payment_service.create_attempt(
                owner,
                PaymentAttemptCreateSchema(
                    order_no=cancelled.order_no,
                    provider="wechat",
                    channel="jsapi",
                    request_key=f"cancelled-payment-{suffix}",
                ),
            )
        assert cancelled_error.value.status_code == 409

        expiring = await order_service.create_membership_order(
            owner,
            MembershipOrderCreateSchema(
                plan_id=plan["id"],
                request_key=f"expired-{suffix}",
                payment_window_seconds=60,
            ),
            now=current,
        )
        with pytest.raises(CustomException) as expired_error:
            await payment_service.create_attempt(
                owner,
                PaymentAttemptCreateSchema(
                    order_no=expiring.order_no,
                    provider="wechat",
                    channel="jsapi",
                    request_key=f"expired-payment-{suffix}",
                ),
                now=current + timedelta(seconds=60),
            )
        assert expired_error.value.status_code == 409


@pytest.mark.asyncio
async def test_provider_event_deduplicates_digest_without_settling_order(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    user_id = _create_user(test_client, suffix)
    plan = _create_plan(test_client, auth_headers, suffix=suffix)

    async with async_db_session() as db, db.begin():
        owner = await _create_customer_owner(
            db,
            legacy_user_id=user_id,
            suffix=suffix,
        )
        order = await CommerceOrderService(db).create_membership_order(
            owner,
            MembershipOrderCreateSchema(
                plan_id=plan["id"],
                request_key=f"event-order-{suffix}",
            ),
        )
        payment_service = PaymentService(db)
        attempt = await payment_service.create_attempt(
            owner,
            PaymentAttemptCreateSchema(
                order_no=order.order_no,
                provider="wechat",
                channel="jsapi",
                request_key=f"event-payment-{suffix}",
            ),
        )
        digest = hashlib.sha256(b"safe-test-payload").hexdigest()
        command = ProviderEventRegisterSchema(
            payment_no=attempt.payment_no,
            provider="wechat",
            provider_event_id=f"evt-{suffix}",
            event_type="payment_succeeded",
            payload_digest=digest,
        )

        first = await payment_service.register_provider_event(command)
        second = await payment_service.register_provider_event(command)

        assert second.id == first.id
        assert first.status == "received"
        assert first.payload_digest == digest
        event_count = await db.scalar(
            select(func.count())
            .select_from(PaymentEventModel)
            .where(PaymentEventModel.payment_id == attempt.id)
        )
        assert event_count == 1

        with pytest.raises(CustomException) as mismatch:
            await payment_service.register_provider_event(
                command.model_copy(
                    update={
                        "payload_digest": hashlib.sha256(
                            b"different-payload"
                        ).hexdigest()
                    }
                )
            )
        assert mismatch.value.status_code == 409

        stored_order = await db.scalar(
            select(CommerceOrderModel).where(
                CommerceOrderModel.id == order.id
            )
        )
        stored_attempt = await db.scalar(
            select(PaymentAttemptModel).where(
                PaymentAttemptModel.id == attempt.id
            )
        )
        assert stored_order is not None
        assert stored_attempt is not None
        assert stored_order.status == "pending"
        assert stored_attempt.status == "pending"
