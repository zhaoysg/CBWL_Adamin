from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, inspect, select, text

from app.api.v1.module_commerce.model import (
    CommerceOrderModel,
    PaymentAttemptModel,
    PaymentEventModel,
)
from app.api.v1.module_commerce.schema import (
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
from app.config.setting import settings
from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session, create_engine_and_session
from app.core.exceptions import CustomException


def _suffix() -> str:
    return uuid4().hex[:12]


async def _seed_identity_and_plan() -> tuple[PortalPrincipal, int, str]:
    suffix = _suffix()
    legacy_user_id = 1_000_000_000 + int(uuid4().hex[:7], 16)
    async with async_db_session() as db, db.begin():
        await db.execute(
            text(
                "INSERT INTO sys_user (id, is_deleted) "
                "VALUES (:id, FALSE)"
            ),
            {"id": legacy_user_id},
        )

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
            customer_no=f"MC{suffix.upper()}",
            nickname="MySQL迁移客户",
            register_source="migration",
            status="active",
            version_no=1,
        )
        db.add(customer)
        await db.flush()

        db.add(
            LegacyCustomerMapModel(
                legacy_sys_user_id=legacy_user_id,
                customer_id=customer.id,
                credential_state="migrated",
                source="manual",
                reason_code=None,
                identifier_snapshot=f"mysql-commerce-{suffix}",
                migrated_at=datetime.now(UTC),
                version_no=1,
            )
        )

        plan = MemberPlanModel(
            plan_code=f"mysql-commerce-{suffix}",
            plan_name=f"MySQL交易套餐-{suffix}",
            rank=50,
            price=Decimal("299.00"),
            currency="CNY",
            duration_days=365,
            benefits=["真实MySQL会员权益"],
            status=0,
            sort_no=50,
        )
        db.add(plan)
        await db.flush()

        customer_id = customer.id
        subject_id = subject.id
        plan_id = plan.id

    auth = AuthSchema(
        user=CoreUserSchema(
            id=legacy_user_id,
            username=f"mysql-commerce-{suffix}",
            name="MySQL交易用户",
            dept_id=None,
            is_superuser=False,
        )
    )
    principal = PortalPrincipal(
        actor_type="customer",
        auth=auth,
        legacy_user_id=legacy_user_id,
        customer_id=customer_id,
        subject_id=subject_id,
    )
    return principal, plan_id, suffix


async def _verify_service_contracts(
    principal: PortalPrincipal,
    plan_id: int,
    suffix: str,
) -> None:
    async with async_db_session() as db, db.begin():
        service = CommerceService(db)
        order_payload = CommerceOrderCreateSchema(
            plan_id=plan_id,
            idempotency_key=f"mysql-order:{suffix}:primary",
        )
        order = await service.create_order(principal, order_payload)
        repeated_order = await service.create_order(principal, order_payload)
        assert repeated_order.id == order.id
        assert order.customer_id == principal.customer_id
        assert order.legacy_user_id == principal.legacy_user_id
        assert order.total_amount == Decimal("299.00")
        assert order.currency == "CNY"

        attempt_payload = PaymentAttemptCreateSchema(
            provider="wechat",
            idempotency_key=f"mysql-payment:{suffix}:primary",
        )
        attempt = await service.create_payment_attempt(
            principal,
            order.id,
            attempt_payload,
        )
        repeated_attempt = await service.create_payment_attempt(
            principal,
            order.id,
            attempt_payload,
        )
        assert repeated_attempt.id == attempt.id
        assert attempt.amount == order.total_amount
        assert attempt.currency == order.currency

        try:
            await service.create_payment_attempt(
                principal,
                order.id,
                PaymentAttemptCreateSchema(
                    provider="alipay",
                    idempotency_key=f"mysql-payment:{suffix}:second-active",
                ),
            )
        except CustomException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("a second active attempt must be rejected")

        order_row = await db.scalar(
            select(CommerceOrderModel).where(CommerceOrderModel.id == order.id)
        )
        attempt_row = await db.scalar(
            select(PaymentAttemptModel).where(PaymentAttemptModel.id == attempt.id)
        )
        assert order_row is not None
        assert attempt_row is not None
        expired_at = datetime.now(UTC) - timedelta(minutes=1)
        order_row.payment_expires_at = expired_at
        attempt_row.expires_at = expired_at
        await db.flush()

        success_payload = VerifiedPaymentEventSchema(
            provider="wechat",
            provider_event_id=f"mysql-event:{suffix}:success",
            merchant_request_no=attempt.merchant_request_no,
            provider_transaction_id=f"mysql-tx:{suffix}:success",
            event_type="payment_succeeded",
            amount=order.total_amount,
            currency=order.currency,
            signature_verified=True,
            payload_digest="a" * 64,
            occurred_at=expired_at - timedelta(seconds=1),
        )
        paid = await service.record_verified_payment_event(success_payload)
        assert paid.event.processing_status == "accepted"
        assert paid.order.status == "paid"
        assert paid.payment_attempt.status == "succeeded"

        duplicate = await service.record_verified_payment_event(success_payload)
        assert duplicate.event.id == paid.event.id
        assert duplicate.order.version_no == paid.order.version_no
        assert duplicate.payment_attempt.version_no == paid.payment_attempt.version_no

        try:
            await service.record_verified_payment_event(
                success_payload.model_copy(update={"payload_digest": "b" * 64})
            )
        except CustomException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("changed duplicate event must be rejected")

        second_order = await service.create_order(
            principal,
            CommerceOrderCreateSchema(
                plan_id=plan_id,
                idempotency_key=f"mysql-order:{suffix}:tx-conflict",
            ),
        )
        second_attempt = await service.create_payment_attempt(
            principal,
            second_order.id,
            PaymentAttemptCreateSchema(
                provider="wechat",
                idempotency_key=f"mysql-payment:{suffix}:tx-conflict",
            ),
        )
        conflict_event_id = f"mysql-event:{suffix}:tx-conflict"
        try:
            await service.record_verified_payment_event(
                VerifiedPaymentEventSchema(
                    provider="wechat",
                    provider_event_id=conflict_event_id,
                    merchant_request_no=second_attempt.merchant_request_no,
                    provider_transaction_id=paid.payment_attempt.provider_transaction_id,
                    event_type="payment_succeeded",
                    amount=second_order.total_amount,
                    currency=second_order.currency,
                    signature_verified=True,
                    payload_digest="c" * 64,
                    occurred_at=datetime.now(UTC),
                )
            )
        except CustomException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("provider transaction reuse must be rejected")

        conflict_event_count = await db.scalar(
            select(func.count())
            .select_from(PaymentEventModel)
            .where(PaymentEventModel.provider_event_id == conflict_event_id)
        )
        assert conflict_event_count == 0

        recovered = await service.record_verified_payment_event(
            VerifiedPaymentEventSchema(
                provider="wechat",
                provider_event_id=f"mysql-event:{suffix}:recovered",
                merchant_request_no=second_attempt.merchant_request_no,
                provider_transaction_id=None,
                event_type="payment_failed",
                amount=second_order.total_amount,
                currency=second_order.currency,
                signature_verified=True,
                payload_digest="d" * 64,
                occurred_at=datetime.now(UTC),
                provider_reason_code="declined",
            )
        )
        assert recovered.event.processing_status == "accepted"
        assert recovered.order.status == "pending"
        assert recovered.payment_attempt.status == "failed"

        subscriptions = await db.scalar(
            select(func.count())
            .select_from(MemberSubscriptionModel)
            .where(MemberSubscriptionModel.source_ref == order.order_no)
        )
        assert subscriptions == 0


async def _verify_concurrency(
    principal: PortalPrincipal,
    plan_id: int,
    suffix: str,
) -> None:
    concurrent_order_payload = CommerceOrderCreateSchema(
        plan_id=plan_id,
        idempotency_key=f"mysql-order:{suffix}:concurrent",
    )

    async def create_same_order():
        async with async_db_session() as db, db.begin():
            return await CommerceService(db).create_order(
                principal,
                concurrent_order_payload,
            )

    concurrent_orders = await asyncio.gather(
        create_same_order(),
        create_same_order(),
    )
    assert concurrent_orders[0].id == concurrent_orders[1].id

    concurrent_attempt_payload = PaymentAttemptCreateSchema(
        provider="alipay",
        idempotency_key=f"mysql-payment:{suffix}:concurrent",
    )

    async def create_same_attempt():
        async with async_db_session() as db, db.begin():
            return await CommerceService(db).create_payment_attempt(
                principal,
                concurrent_orders[0].id,
                concurrent_attempt_payload,
            )

    concurrent_attempts = await asyncio.gather(
        create_same_attempt(),
        create_same_attempt(),
    )
    assert concurrent_attempts[0].id == concurrent_attempts[1].id

    concurrent_event_payload = VerifiedPaymentEventSchema(
        provider="alipay",
        provider_event_id=f"mysql-event:{suffix}:concurrent",
        merchant_request_no=concurrent_attempts[0].merchant_request_no,
        provider_transaction_id=f"mysql-tx:{suffix}:concurrent",
        event_type="payment_succeeded",
        amount=concurrent_attempts[0].amount,
        currency=concurrent_attempts[0].currency,
        signature_verified=True,
        payload_digest="e" * 64,
        occurred_at=datetime.now(UTC),
    )

    async def record_same_event():
        async with async_db_session() as db, db.begin():
            return await CommerceService(db).record_verified_payment_event(
                concurrent_event_payload
            )

    concurrent_events = await asyncio.gather(
        record_same_event(),
        record_same_event(),
    )
    assert concurrent_events[0].event.id == concurrent_events[1].event.id
    assert concurrent_events[0].order.status == "paid"
    assert concurrent_events[1].order.status == "paid"

    competing_order_payload = CommerceOrderCreateSchema(
        plan_id=plan_id,
        idempotency_key=f"mysql-order:{suffix}:competing-attempts",
    )
    async with async_db_session() as db, db.begin():
        competing_order = await CommerceService(db).create_order(
            principal,
            competing_order_payload,
        )

    async def create_competing_attempt(index: int):
        async with async_db_session() as db, db.begin():
            return await CommerceService(db).create_payment_attempt(
                principal,
                competing_order.id,
                PaymentAttemptCreateSchema(
                    provider="wechat" if index == 0 else "alipay",
                    idempotency_key=(
                        f"mysql-payment:{suffix}:competing:{index}"
                    ),
                ),
            )

    competing_results = await asyncio.gather(
        create_competing_attempt(0),
        create_competing_attempt(1),
        return_exceptions=True,
    )
    successes = [
        result for result in competing_results if not isinstance(result, Exception)
    ]
    conflicts = [
        result
        for result in competing_results
        if isinstance(result, CustomException) and result.status_code == 409
    ]
    assert len(successes) == 1
    assert len(conflicts) == 1

    async with async_db_session() as db:
        order_count = await db.scalar(
            select(func.count())
            .select_from(CommerceOrderModel)
            .where(
                CommerceOrderModel.idempotency_key
                == concurrent_order_payload.idempotency_key
            )
        )
        attempt_count = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptModel)
            .where(PaymentAttemptModel.order_id == concurrent_orders[0].id)
        )
        event_count = await db.scalar(
            select(func.count())
            .select_from(PaymentEventModel)
            .where(
                PaymentEventModel.provider == concurrent_event_payload.provider,
                PaymentEventModel.provider_event_id
                == concurrent_event_payload.provider_event_id,
            )
        )
        competing_attempt_count = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptModel)
            .where(PaymentAttemptModel.order_id == competing_order.id)
        )
        assert order_count == 1
        assert attempt_count == 1
        assert event_count == 1
        assert competing_attempt_count == 1


def _verify_schema() -> None:
    engine, _ = create_engine_and_session(settings.DB_URI)
    inspector = inspect(engine)
    expected_tables = {"cw_order", "cw_payment_attempt", "cw_payment_event"}
    assert expected_tables <= set(inspector.get_table_names())

    order_columns = {item["name"] for item in inspector.get_columns("cw_order")}
    attempt_columns = {
        item["name"] for item in inspector.get_columns("cw_payment_attempt")
    }
    event_columns = {
        item["name"] for item in inspector.get_columns("cw_payment_event")
    }
    assert {
        "legacy_user_id",
        "customer_id",
        "unit_price",
        "total_amount",
        "payment_expires_at",
        "idempotency_key",
    } <= order_columns
    assert {
        "attempt_no",
        "merchant_request_no",
        "provider_transaction_id",
        "idempotency_key",
    } <= attempt_columns
    assert {
        "payment_attempt_id",
        "signature_verified",
        "payload_digest",
        "processing_status",
        "occurred_at",
    } <= event_columns
    assert not {
        "raw_payload",
        "raw_body",
        "signature",
        "authorization",
        "token",
        "cookie",
    }.intersection(event_columns)

    order_indexes = {item["name"] for item in inspector.get_indexes("cw_order")}
    attempt_indexes = {
        item["name"] for item in inspector.get_indexes("cw_payment_attempt")
    }
    assert "ix_cw_order_customer_status_created" in order_indexes
    assert "ix_cw_order_status_expiry" in order_indexes
    assert "ix_cw_payment_attempt_order_status" in attempt_indexes

    order_checks = {
        item["name"] for item in inspector.get_check_constraints("cw_order")
    }
    attempt_checks = {
        item["name"]
        for item in inspector.get_check_constraints("cw_payment_attempt")
    }
    event_checks = {
        item["name"] for item in inspector.get_check_constraints("cw_payment_event")
    }
    assert "ck_cw_order_owner" in order_checks
    assert "ck_cw_order_paid_shape" in order_checks
    assert "ck_cw_payment_attempt_succeeded_shape" in attempt_checks
    assert "ck_cw_payment_attempt_failed_shape" in attempt_checks
    assert "ck_cw_payment_event_digest" in event_checks
    assert "ck_cw_payment_event_signature_verified" in event_checks

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT TABLE_NAME, TABLE_COLLATION "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME IN ("
                "'cw_order', 'cw_payment_attempt', 'cw_payment_event'"
                ")"
            )
        ).all()
        referential_actions = connection.execute(
            text(
                "SELECT CONSTRAINT_NAME, UPDATE_RULE, DELETE_RULE "
                "FROM information_schema.REFERENTIAL_CONSTRAINTS "
                "WHERE CONSTRAINT_SCHEMA = DATABASE() "
                "AND TABLE_NAME IN ("
                "'cw_order', 'cw_payment_attempt', 'cw_payment_event'"
                ")"
            )
        ).all()
    collations = dict(rows)
    assert set(collations) == expected_tables
    assert set(collations.values()) == {"utf8mb4_bin"}
    assert referential_actions
    assert all(
        update_rule in {"NO ACTION", "RESTRICT"}
        for _, update_rule, _ in referential_actions
    )
    assert all(
        delete_rule in {"NO ACTION", "RESTRICT"}
        for _, _, delete_rule in referential_actions
    )

    engine.dispose()


async def _main() -> None:
    principal, plan_id, suffix = await _seed_identity_and_plan()
    await _verify_service_contracts(principal, plan_id, suffix)
    await _verify_concurrency(principal, plan_id, suffix)


def main() -> None:
    _verify_schema()
    asyncio.run(_main())


if __name__ == "__main__":
    main()
