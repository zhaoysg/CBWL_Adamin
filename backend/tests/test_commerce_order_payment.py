from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from app.api.v1.module_commerce.model import PaymentEventModel
from app.api.v1.module_commerce.schema import (
    CommerceOrderCancelSchema,
    CommerceOrderCreateSchema,
    PaymentAttemptCreateSchema,
    VerifiedPaymentEventSchema,
)
from app.api.v1.module_commerce.service import CommerceService
from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_identity.model import AuthSubjectModel, CustomerModel
from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_membership.subscription.model import MemberSubscriptionModel
from app.api.v1.module_portal.principal import PortalPrincipal
from app.api.v1.module_system.user.model import UserModel
from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session
from app.core.exceptions import CustomException


def _suffix() -> str:
    return uuid4().hex[:12]


async def _seed_customer_and_plans(db, suffix: str):
    user = UserModel(
        username=f"commerce_{suffix}",
        password="test-only-hash",
        name=f"订单客户{suffix[:5]}",
        is_superuser=False,
        status=0,
    )
    db.add(user)
    await db.flush()

    subject = AuthSubjectModel(realm="customer", status="active", version_no=1)
    db.add(subject)
    await db.flush()

    customer = CustomerModel(
        subject_id=subject.id,
        realm="customer",
        customer_no=f"C{suffix.upper()}",
        nickname=f"客户{suffix[:5]}",
        register_source="migration",
        status="active",
        version_no=1,
    )
    db.add(customer)
    await db.flush()

    mapping = LegacyCustomerMapModel(
        legacy_sys_user_id=user.id,
        customer_id=customer.id,
        credential_state="migrated",
        source="membership",
        reason_code=None,
        identifier_snapshot=user.username,
        migrated_at=datetime.now(UTC),
        version_no=1,
    )
    first_plan = MemberPlanModel(
        plan_code=f"commerce-basic-{suffix}",
        plan_name=f"订单基础套餐-{suffix}",
        rank=10,
        price=Decimal("99.00"),
        currency="cny",
        duration_days=30,
        benefits=["会员内容"],
        status=0,
        sort_no=10,
    )
    second_plan = MemberPlanModel(
        plan_code=f"commerce-plus-{suffix}",
        plan_name=f"订单高级套餐-{suffix}",
        rank=20,
        price=Decimal("199.00"),
        currency="CNY",
        duration_days=365,
        benefits=["高级会员内容"],
        status=0,
        sort_no=20,
    )
    db.add_all([mapping, first_plan, second_plan])
    await db.flush()

    auth = AuthSchema(
        user=CoreUserSchema(
            id=user.id,
            username=user.username,
            name=user.name,
            dept_id=None,
            is_superuser=False,
        )
    )
    customer_principal = PortalPrincipal(
        actor_type="customer",
        auth=auth,
        legacy_user_id=user.id,
        customer_id=customer.id,
        subject_id=subject.id,
    )
    legacy_principal = PortalPrincipal(
        actor_type="legacy",
        auth=auth,
        legacy_user_id=user.id,
    )
    return customer_principal, legacy_principal, first_plan, second_plan


@pytest.mark.asyncio
async def test_order_amount_is_server_derived_and_creation_is_idempotent(
    test_client: TestClient,
) -> None:
    suffix = _suffix()
    async with async_db_session() as db, db.begin():
        customer, legacy, first_plan, second_plan = await _seed_customer_and_plans(db, suffix)
        service = CommerceService(db)
        key = f"order:{suffix}:0001"
        payload = CommerceOrderCreateSchema(
            plan_id=first_plan.id,
            idempotency_key=key,
        )

        first = await service.create_order(customer, payload)
        second = await service.create_order(customer, payload)
        assert second.id == first.id
        assert first.legacy_user_id == customer.legacy_user_id
        assert first.customer_id == customer.customer_id
        assert first.unit_price == Decimal("99.00")
        assert first.total_amount == Decimal("99.00")
        assert first.currency == "CNY"
        assert first.plan_code_snapshot == first_plan.plan_code
        assert first.duration_days_snapshot == 30
        assert "amount" not in CommerceOrderCreateSchema.model_fields
        assert "currency" not in CommerceOrderCreateSchema.model_fields

        with pytest.raises(CustomException) as mismatch:
            await service.create_order(
                customer,
                CommerceOrderCreateSchema(
                    plan_id=second_plan.id,
                    idempotency_key=key,
                ),
            )
        assert mismatch.value.status_code == 409

        with pytest.raises(CustomException) as stale:
            await service.cancel_order(
                customer,
                first.id,
                CommerceOrderCancelSchema(version_no=999, reason="版本过期"),
            )
        assert stale.value.status_code == 409

        cancelled = await service.cancel_order(
            customer,
            first.id,
            CommerceOrderCancelSchema(version_no=first.version_no, reason="客户主动取消"),
        )
        assert cancelled.status == "cancelled"
        assert cancelled.cancelled_at is not None
        assert cancelled.version_no == 2

        legacy_order = await service.create_order(
            legacy,
            CommerceOrderCreateSchema(
                plan_id=first_plan.id,
                idempotency_key=f"order:{suffix}:legacy",
            ),
        )
        assert legacy_order.legacy_user_id == legacy.legacy_user_id
        assert legacy_order.customer_id is None

        inconsistent_principal = PortalPrincipal(
            actor_type="customer",
            auth=customer.auth,
            legacy_user_id=customer.legacy_user_id,
            customer_id=customer.customer_id + 100000,
            subject_id=customer.subject_id,
        )
        with pytest.raises(CustomException) as inconsistent:
            await service.create_order(
                inconsistent_principal,
                CommerceOrderCreateSchema(
                    plan_id=first_plan.id,
                    idempotency_key=f"order:{suffix}:bad-map",
                ),
            )
        assert inconsistent.value.status_code == 503


@pytest.mark.asyncio
async def test_payment_event_is_deduplicated_and_updates_order_atomically(
    test_client: TestClient,
) -> None:
    suffix = _suffix()
    async with async_db_session() as db, db.begin():
        customer, _, plan, _ = await _seed_customer_and_plans(db, suffix)
        service = CommerceService(db)
        order = await service.create_order(
            customer,
            CommerceOrderCreateSchema(
                plan_id=plan.id,
                idempotency_key=f"order:{suffix}:payment",
            ),
        )
        attempt = await service.create_payment_attempt(
            customer,
            order.id,
            PaymentAttemptCreateSchema(
                provider="wechat",
                idempotency_key=f"payment:{suffix}:0001",
            ),
        )
        repeated_attempt = await service.create_payment_attempt(
            customer,
            order.id,
            PaymentAttemptCreateSchema(
                provider="wechat",
                idempotency_key=f"payment:{suffix}:0001",
            ),
        )
        assert repeated_attempt.id == attempt.id
        assert attempt.amount == order.total_amount
        assert attempt.currency == order.currency

        # SQLite is test-only in this project. Its standard function set does not
        # include CHAR_LENGTH, while MySQL 8.4 enforces the named digest check in
        # the dedicated integration job. Keep service behavior covered here.
        await db.execute(text("PRAGMA ignore_check_constraints = ON"))

        bad_amount = await service.record_verified_payment_event(
            VerifiedPaymentEventSchema(
                provider="wechat",
                provider_event_id=f"event-bad-{suffix}",
                merchant_request_no=attempt.merchant_request_no,
                provider_transaction_id=f"wx-bad-{suffix}",
                event_type="payment_succeeded",
                amount=Decimal("1.00"),
                currency="CNY",
                signature_verified=True,
                payload_digest="1" * 64,
                occurred_at=datetime.now(UTC),
            )
        )
        assert bad_amount.event.processing_status == "rejected"
        assert bad_amount.event.reason_code == "amount_mismatch"
        assert bad_amount.order.status == "pending"
        assert bad_amount.payment_attempt.status == "created"

        success_payload = VerifiedPaymentEventSchema(
            provider="wechat",
            provider_event_id=f"event-success-{suffix}",
            merchant_request_no=attempt.merchant_request_no,
            provider_transaction_id=f"wx-success-{suffix}",
            event_type="payment_succeeded",
            amount=order.total_amount,
            currency=order.currency,
            signature_verified=True,
            payload_digest="a" * 64,
            occurred_at=datetime.now(UTC),
        )
        paid = await service.record_verified_payment_event(success_payload)
        assert paid.event.processing_status == "accepted"
        assert paid.event.reason_code is None
        assert paid.order.status == "paid"
        assert paid.order.paid_at is not None
        assert paid.order.version_no == 2
        assert paid.payment_attempt.status == "succeeded"
        assert paid.payment_attempt.provider_transaction_id == f"wx-success-{suffix}"
        assert paid.payment_attempt.version_no == 2

        duplicate = await service.record_verified_payment_event(success_payload)
        assert duplicate.event.id == paid.event.id
        assert duplicate.order.version_no == paid.order.version_no
        assert duplicate.payment_attempt.version_no == paid.payment_attempt.version_no

        with pytest.raises(CustomException) as changed_payload:
            await service.record_verified_payment_event(
                success_payload.model_copy(update={"payload_digest": "b" * 64})
            )
        assert changed_payload.value.status_code == 409

        late_failure = await service.record_verified_payment_event(
            VerifiedPaymentEventSchema(
                provider="wechat",
                provider_event_id=f"event-late-failure-{suffix}",
                merchant_request_no=attempt.merchant_request_no,
                provider_transaction_id=None,
                event_type="payment_failed",
                amount=order.total_amount,
                currency=order.currency,
                signature_verified=True,
                payload_digest="c" * 64,
                occurred_at=datetime.now(UTC),
                provider_reason_code="provider_timeout",
            )
        )
        assert late_failure.event.processing_status == "ignored"
        assert late_failure.event.reason_code == "already_succeeded"
        assert late_failure.order.status == "paid"
        assert late_failure.payment_attempt.status == "succeeded"

        with pytest.raises(CustomException) as cancel_paid:
            await service.cancel_order(
                customer,
                order.id,
                CommerceOrderCancelSchema(
                    version_no=paid.order.version_no,
                    reason="支付后错误取消",
                ),
            )
        assert cancel_paid.value.status_code == 409

        subscriptions = await db.scalar(
            select(func.count())
            .select_from(MemberSubscriptionModel)
            .where(MemberSubscriptionModel.source_ref == order.order_no)
        )
        assert subscriptions == 0

        event_columns = set(PaymentEventModel.__table__.columns.keys())
        assert "payload_digest" in event_columns
        assert not {
            "raw_payload",
            "raw_body",
            "signature",
            "authorization",
            "token",
            "cookie",
        }.intersection(event_columns)
