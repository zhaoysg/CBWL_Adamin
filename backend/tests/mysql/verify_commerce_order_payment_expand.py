from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, inspect, select, text

from app.api.v1.module_commerce.order_payment.model import (
    CommerceOrderModel,
    PaymentAttemptModel,
    PaymentEventModel,
)
from app.api.v1.module_commerce.order_payment.ownership import CommerceOwner
from app.api.v1.module_commerce.order_payment.schema import (
    MembershipOrderCreateSchema,
    PaymentAttemptCreateSchema,
    ProviderEventRegisterSchema,
)
from app.api.v1.module_commerce.order_payment.service import (
    CommerceOrderService,
    PaymentService,
)
from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_identity.model import AuthSubjectModel, CustomerModel
from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_system.user.model import UserModel
from app.config.setting import settings
from app.core.database import async_db_session, create_engine_and_session


async def _verify_services() -> None:
    suffix = uuid4().hex[:10]
    async with async_db_session() as db, db.begin():
        user = UserModel(
            username=f"mysql-commerce-{suffix}",
            password="not-used-by-this-verifier",
            name="MySQL交易用户",
            status=0,
            is_superuser=False,
        )
        db.add(user)
        await db.flush()

        plan = MemberPlanModel(
            plan_code=f"mysql-commerce-{suffix}",
            plan_name=f"MySQL交易套餐-{suffix}",
            rank=50,
            price="299.00",
            currency="CNY",
            duration_days=365,
            benefits=["真实MySQL会员权益"],
            status=0,
            sort_no=50,
        )
        db.add(plan)
        await db.flush()

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
                legacy_sys_user_id=user.id,
                customer_id=customer.id,
                credential_state="migrated",
                source="manual",
                reason_code=None,
                identifier_snapshot=user.username,
                migrated_at=datetime.now(UTC),
                version_no=1,
            )
        )
        await db.flush()

        owner = CommerceOwner.customer(
            customer.id,
            legacy_user_id=user.id,
            subject_id=subject.id,
        )
        order_service = CommerceOrderService(db)
        payment_service = PaymentService(db)

        order_command = MembershipOrderCreateSchema(
            plan_id=plan.id,
            request_key=f"mysql-order-{suffix}",
        )
        order = await order_service.create_membership_order(
            owner,
            order_command,
        )
        repeated_order = await order_service.create_membership_order(
            owner,
            order_command,
        )
        assert repeated_order.id == order.id
        assert order.customer_id == customer.id
        assert order.legacy_user_id == user.id
        assert str(order.amount) == "299.00"

        payment_command = PaymentAttemptCreateSchema(
            order_no=order.order_no,
            provider="wechat",
            channel="jsapi",
            request_key=f"mysql-payment-{suffix}",
        )
        payment = await payment_service.create_attempt(
            owner,
            payment_command,
        )
        repeated_payment = await payment_service.create_attempt(
            owner,
            payment_command,
        )
        assert repeated_payment.id == payment.id
        assert payment.customer_id == customer.id
        assert payment.legacy_user_id == user.id
        assert payment.order_no == order.order_no

        event_command = ProviderEventRegisterSchema(
            payment_no=payment.payment_no,
            provider="wechat",
            provider_event_id=f"mysql-event-{suffix}",
            event_type="payment_succeeded",
            payload_digest=hashlib.sha256(
                b"mysql-verifier-payload"
            ).hexdigest(),
        )
        event = await payment_service.register_provider_event(event_command)
        repeated_event = await payment_service.register_provider_event(
            event_command
        )
        assert repeated_event.id == event.id
        assert event.status == "received"

        # Expand phase must not settle money or grant membership.
        assert order.status == "pending"
        assert payment.status == "pending"

    concurrent_order_command = MembershipOrderCreateSchema(
        plan_id=plan.id,
        request_key=f"mysql-concurrent-order-{suffix}",
    )

    async def create_same_order():
        async with async_db_session() as db, db.begin():
            return await CommerceOrderService(db).create_membership_order(
                owner,
                concurrent_order_command,
            )

    concurrent_orders = await asyncio.gather(
        create_same_order(),
        create_same_order(),
    )
    assert concurrent_orders[0].id == concurrent_orders[1].id

    concurrent_payment_command = PaymentAttemptCreateSchema(
        order_no=concurrent_orders[0].order_no,
        provider="alipay",
        channel="h5",
        request_key=f"mysql-concurrent-payment-{suffix}",
    )

    async def create_same_payment():
        async with async_db_session() as db, db.begin():
            return await PaymentService(db).create_attempt(
                owner,
                concurrent_payment_command,
            )

    concurrent_payments = await asyncio.gather(
        create_same_payment(),
        create_same_payment(),
    )
    assert concurrent_payments[0].id == concurrent_payments[1].id

    concurrent_event_command = ProviderEventRegisterSchema(
        payment_no=concurrent_payments[0].payment_no,
        provider="alipay",
        provider_event_id=f"mysql-concurrent-event-{suffix}",
        event_type="payment_succeeded",
        payload_digest=hashlib.sha256(b"mysql-concurrent-payload").hexdigest(),
    )

    async def register_same_event():
        async with async_db_session() as db, db.begin():
            return await PaymentService(db).register_provider_event(
                concurrent_event_command
            )

    concurrent_events = await asyncio.gather(
        register_same_event(),
        register_same_event(),
    )
    assert concurrent_events[0].id == concurrent_events[1].id

    async with async_db_session() as db:
        order_count = await db.scalar(
            select(func.count())
            .select_from(CommerceOrderModel)
            .where(
                CommerceOrderModel.customer_id == owner.customer_id,
                CommerceOrderModel.plan_id == plan.id,
            )
        )
        payment_count = await db.scalar(
            select(func.count())
            .select_from(PaymentAttemptModel)
            .where(PaymentAttemptModel.order_id == concurrent_orders[0].id)
        )
        event_count = await db.scalar(
            select(func.count())
            .select_from(PaymentEventModel)
            .where(PaymentEventModel.payment_id == concurrent_payments[0].id)
        )
        assert order_count == 2
        assert payment_count == 1
        assert event_count == 1


def _verify_schema() -> None:
    engine, _ = create_engine_and_session(settings.DB_URI)
    inspector = inspect(engine)
    expected_tables = {
        "cw_commerce_order",
        "cw_payment_attempt",
        "cw_payment_event",
    }
    assert expected_tables <= set(inspector.get_table_names())

    order_columns = {item["name"] for item in inspector.get_columns("cw_commerce_order")}
    payment_columns = {item["name"] for item in inspector.get_columns("cw_payment_attempt")}
    assert {"legacy_user_id", "customer_id", "idempotency_key"} <= order_columns
    assert {"legacy_user_id", "customer_id", "idempotency_key"} <= payment_columns

    order_indexes = {
        item["name"] for item in inspector.get_indexes("cw_commerce_order")
    }
    payment_indexes = {
        item["name"] for item in inspector.get_indexes("cw_payment_attempt")
    }
    assert "ix_cw_commerce_order_customer_status_created" in order_indexes
    assert "ix_cw_payment_attempt_customer_status_created" in payment_indexes

    order_checks = {
        item["name"] for item in inspector.get_check_constraints("cw_commerce_order")
    }
    payment_checks = {
        item["name"] for item in inspector.get_check_constraints("cw_payment_attempt")
    }
    event_checks = {
        item["name"] for item in inspector.get_check_constraints("cw_payment_event")
    }
    assert "ck_cw_commerce_order_owner_present" in order_checks
    assert "ck_cw_commerce_order_state_shape" in order_checks
    assert "ck_cw_payment_attempt_owner_present" in payment_checks
    assert "ck_cw_payment_attempt_state_shape" in payment_checks
    assert "ck_cw_payment_event_state_shape" in event_checks
    assert "ck_cw_payment_event_digest_length" in event_checks

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT TABLE_NAME, TABLE_COLLATION "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() "
                "AND TABLE_NAME IN ("
                "'cw_commerce_order', 'cw_payment_attempt', 'cw_payment_event'"
                ")"
            )
        ).all()
    collations = {name: collation for name, collation in rows}
    assert set(collations) == expected_tables
    assert set(collations.values()) == {"utf8mb4_bin"}

    engine.dispose()


def main() -> None:
    _verify_schema()
    asyncio.run(_verify_services())


if __name__ == "__main__":
    main()
