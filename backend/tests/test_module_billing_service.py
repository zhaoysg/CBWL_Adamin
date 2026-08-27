from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.module_billing.enums import (
    BillingProvider,
    OrderStatus,
    OutboxEventStatus,
    PaymentAttemptStatus,
    PaymentEventProcessingStatus,
)
from app.api.v1.module_billing.order.model import CommerceOrderModel
from app.api.v1.module_billing.order.schema import OrderCloseSchema, OrderCreateSchema
from app.api.v1.module_billing.order.service import OrderService
from app.api.v1.module_billing.outbox.model import OutboxEventModel
from app.api.v1.module_billing.payment.model import PaymentAttemptModel, PaymentEventModel
from app.api.v1.module_billing.payment.schema import (
    ConfirmedPaymentSchema,
    PaymentAttemptCreateSchema,
)
from app.api.v1.module_billing.payment.service import PaymentAttemptService
from app.api.v1.module_billing.payment.settlement import PaymentSettlementService
from app.api.v1.module_membership.entitlement import utc_now
from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_membership.subscription.model import MemberSubscriptionModel
from app.api.v1.module_system.user.model import UserModel
from app.core.base_model import MappedBase
from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.exceptions import CustomException
from app.utils.import_util import ImportUtil


@pytest_asyncio.fixture
async def billing_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    ImportUtil.find_models.cache_clear()
    ImportUtil.find_models(MappedBase)
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(MappedBase.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_users_and_plans(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[AuthSchema, int, int, int, int]:
    async with factory() as db, db.begin():
        user = UserModel(
            username="billing-user",
            password="not-used",
            name="Billing User",
            status=0,
        )
        other_user = UserModel(
            username="billing-other",
            password="not-used",
            name="Billing Other",
            status=0,
        )
        plan = MemberPlanModel(
            plan_code="billing-basic",
            plan_name="Billing Basic",
            rank=10,
            price=Decimal("199.00"),
            currency="CNY",
            duration_days=30,
            benefits=["会员投研"],
            status=0,
            sort_no=10,
        )
        other_plan = MemberPlanModel(
            plan_code="billing-premium",
            plan_name="Billing Premium",
            rank=20,
            price=Decimal("399.00"),
            currency="CNY",
            duration_days=90,
            benefits=["高级投研"],
            status=0,
            sort_no=20,
        )
        db.add_all([user, other_user, plan, other_plan])
        await db.flush()

        auth = AuthSchema(
            user=CoreUserSchema(
                id=user.id,
                username=user.username,
                name=user.name,
                is_superuser=False,
            )
        )
        return auth, user.id, other_user.id, plan.id, other_plan.id


def _confirmed_payment(
    *,
    order_no: str,
    attempt_no: str,
    event_id: str,
    transaction_id: str,
    amount_minor: int = 19900,
    payload_hash: str = "a" * 64,
) -> ConfirmedPaymentSchema:
    return ConfirmedPaymentSchema(
        provider=BillingProvider.SANDBOX,
        provider_event_id=event_id,
        event_type="payment.succeeded",
        attempt_no=attempt_no,
        provider_transaction_id=transaction_id,
        order_no=order_no,
        amount_minor=amount_minor,
        currency="CNY",
        payload_hash=payload_hash,
        occurred_at=utc_now(),
        event_metadata={"scenario": "automated-test"},
    )


@pytest.mark.asyncio
async def test_order_creation_uses_server_snapshot_and_user_idempotency(
    billing_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    auth, _, _, plan_id, other_plan_id = await _seed_users_and_plans(billing_session_factory)

    async with billing_session_factory() as db, db.begin():
        service = OrderService(auth, db)
        order = await service.create(
            OrderCreateSchema(
                plan_id=plan_id,
                idempotency_key="order-idem-0001",
            )
        )
        assert order.amount_minor == 19900
        assert order.currency == "CNY"
        assert order.plan_snapshot["duration_days"] == 30
        assert order.plan_snapshot["amount_minor"] == 19900
        assert order.status == OrderStatus.PENDING

        plan = await db.get(MemberPlanModel, plan_id)
        assert plan is not None
        plan.price = Decimal("999.00")
        await db.flush()

        retry = await service.create(
            OrderCreateSchema(
                plan_id=plan_id,
                idempotency_key="order-idem-0001",
            )
        )
        assert retry.id == order.id
        assert retry.amount_minor == 19900

        with pytest.raises(CustomException, match="幂等键"):
            await service.create(
                OrderCreateSchema(
                    plan_id=other_plan_id,
                    idempotency_key="order-idem-0001",
                )
            )

        with pytest.raises(CustomException, match="版本"):
            await service.close(
                order.order_no,
                OrderCloseSchema(version_no=999),
            )

        closed = await service.close(
            order.order_no,
            OrderCloseSchema(version_no=order.version_no),
        )
        assert closed.status == OrderStatus.CLOSED
        assert closed.version_no == 2

        repeated_close = await service.close(
            order.order_no,
            OrderCloseSchema(version_no=order.version_no),
        )
        assert repeated_close.status == OrderStatus.CLOSED


@pytest.mark.asyncio
async def test_payment_success_grants_one_subscription_and_one_outbox_event(
    billing_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    auth, _, _, plan_id, _ = await _seed_users_and_plans(billing_session_factory)

    async with billing_session_factory() as db, db.begin():
        order = await OrderService(auth, db).create(
            OrderCreateSchema(
                plan_id=plan_id,
                idempotency_key="order-idem-0002",
            )
        )
        attempt_service = PaymentAttemptService(auth, db)
        attempt = await attempt_service.create(
            order.order_no,
            PaymentAttemptCreateSchema(
                provider=BillingProvider.SANDBOX,
                idempotency_key="attempt-idem-0002",
            ),
        )
        retry = await attempt_service.create(
            order.order_no,
            PaymentAttemptCreateSchema(
                provider=BillingProvider.SANDBOX,
                idempotency_key="attempt-idem-0002",
            ),
        )
        assert retry.id == attempt.id
        with pytest.raises(CustomException, match="Provider"):
            await attempt_service.create(
                order.order_no,
                PaymentAttemptCreateSchema(
                    provider=BillingProvider.MANUAL,
                    idempotency_key="attempt-idem-0002",
                ),
            )

    confirmed = _confirmed_payment(
        order_no=order.order_no,
        attempt_no=attempt.attempt_no,
        event_id="event-success-0002",
        transaction_id="transaction-0002",
    )
    async with billing_session_factory() as db, db.begin():
        result = await PaymentSettlementService(db).process_confirmed_success(confirmed)
        assert result.processing_status == PaymentEventProcessingStatus.PROCESSED
        assert result.order_status == OrderStatus.PAID
        assert result.subscription_id is not None
        assert result.outbox_event_id is not None

    async with billing_session_factory() as db, db.begin():
        duplicate = await PaymentSettlementService(db).process_confirmed_success(confirmed)
        assert duplicate.duplicate is True
        assert duplicate.processing_status == PaymentEventProcessingStatus.PROCESSED
        assert duplicate.subscription_id == result.subscription_id

        ignored = await PaymentSettlementService(db).process_confirmed_success(
            _confirmed_payment(
                order_no=order.order_no,
                attempt_no=attempt.attempt_no,
                event_id="event-success-0002-retry",
                transaction_id="transaction-0002",
                payload_hash="b" * 64,
            )
        )
        assert ignored.processing_status == PaymentEventProcessingStatus.IGNORED
        assert ignored.reason == "duplicate_payment_fact"

    async with billing_session_factory() as db:
        persisted_order = await db.get(CommerceOrderModel, order.id)
        persisted_attempt = await db.get(PaymentAttemptModel, attempt.id)
        assert persisted_order is not None
        assert persisted_attempt is not None
        assert persisted_order.status == OrderStatus.PAID.value
        assert persisted_order.paid_amount_minor == 19900
        assert persisted_attempt.status == PaymentAttemptStatus.SUCCEEDED.value
        assert persisted_attempt.provider_transaction_id == "transaction-0002"

        subscription_count = await db.scalar(
            select(func.count())
            .select_from(MemberSubscriptionModel)
            .where(
                MemberSubscriptionModel.source == "payment",
                MemberSubscriptionModel.source_ref == order.order_no,
            )
        )
        outbox_count = await db.scalar(select(func.count()).select_from(OutboxEventModel).where(OutboxEventModel.deduplication_key == f"billing.order.paid:{order.order_no}"))
        event_count = await db.scalar(select(func.count()).select_from(PaymentEventModel).where(PaymentEventModel.order_no == order.order_no))
        assert subscription_count == 1
        assert outbox_count == 1
        assert event_count == 2

        outbox = await db.scalar(select(OutboxEventModel).where(OutboxEventModel.deduplication_key == f"billing.order.paid:{order.order_no}"))
        assert outbox is not None
        assert outbox.status == OutboxEventStatus.PENDING.value
        assert outbox.payload["subscription_id"] == result.subscription_id


@pytest.mark.asyncio
async def test_rejected_payment_facts_are_audited_without_granting_entitlement(
    billing_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    auth, _, _, plan_id, _ = await _seed_users_and_plans(billing_session_factory)

    async with billing_session_factory() as db, db.begin():
        order = await OrderService(auth, db).create(
            OrderCreateSchema(
                plan_id=plan_id,
                idempotency_key="order-idem-0003",
            )
        )
        attempt = await PaymentAttemptService(auth, db).create(
            order.order_no,
            PaymentAttemptCreateSchema(
                provider=BillingProvider.SANDBOX,
                idempotency_key="attempt-idem-0003",
            ),
        )

    async with billing_session_factory() as db, db.begin():
        mismatch = await PaymentSettlementService(db).process_confirmed_success(
            _confirmed_payment(
                order_no=order.order_no,
                attempt_no=attempt.attempt_no,
                event_id="event-mismatch-0003",
                transaction_id="transaction-0003",
                amount_minor=19899,
            )
        )
        assert mismatch.processing_status == PaymentEventProcessingStatus.REJECTED
        assert mismatch.reason == "amount_or_currency_mismatch"

    async with billing_session_factory() as db, db.begin():
        service = OrderService(auth, db)
        current_order = await service.get_owned_for_update(order.order_no)
        closed = await service.close(
            order.order_no,
            OrderCloseSchema(version_no=current_order.version_no),
        )
        assert closed.status == OrderStatus.CLOSED

    async with billing_session_factory() as db, db.begin():
        late = await PaymentSettlementService(db).process_confirmed_success(
            _confirmed_payment(
                order_no=order.order_no,
                attempt_no=attempt.attempt_no,
                event_id="event-late-0003",
                transaction_id="transaction-late-0003",
                payload_hash="c" * 64,
            )
        )
        assert late.processing_status == PaymentEventProcessingStatus.REJECTED
        assert late.reason == "order_status_closed"

    async with billing_session_factory() as db:
        subscription_count = await db.scalar(select(func.count()).select_from(MemberSubscriptionModel).where(MemberSubscriptionModel.source_ref == order.order_no))
        rejected_count = await db.scalar(
            select(func.count())
            .select_from(PaymentEventModel)
            .where(
                PaymentEventModel.order_no == order.order_no,
                PaymentEventModel.processing_status == PaymentEventProcessingStatus.REJECTED.value,
            )
        )
        persisted_order = await db.get(CommerceOrderModel, order.id)
        assert subscription_count == 0
        assert rejected_count == 2
        assert persisted_order is not None
        assert persisted_order.status == OrderStatus.CLOSED.value


@pytest.mark.asyncio
async def test_subscription_conflict_rolls_back_payment_order_and_event_changes(
    billing_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    auth, _, other_user_id, plan_id, _ = await _seed_users_and_plans(billing_session_factory)

    async with billing_session_factory() as db, db.begin():
        order = await OrderService(auth, db).create(
            OrderCreateSchema(
                plan_id=plan_id,
                idempotency_key="order-idem-0004",
            )
        )
        attempt = await PaymentAttemptService(auth, db).create(
            order.order_no,
            PaymentAttemptCreateSchema(
                provider=BillingProvider.SANDBOX,
                idempotency_key="attempt-idem-0004",
            ),
        )

    async with billing_session_factory() as db, db.begin():
        starts_at = utc_now()
        db.add(
            MemberSubscriptionModel(
                user_id=other_user_id,
                plan_id=plan_id,
                source="payment",
                source_ref=order.order_no,
                status=0,
                starts_at=starts_at,
                expires_at=starts_at + timedelta(days=30),
                revoked_at=None,
                grant_reason="冲突夹具",
                revoke_reason=None,
                version_no=1,
                description=None,
            )
        )

    with pytest.raises(CustomException, match="其他会员订阅"):
        async with billing_session_factory() as db, db.begin():
            await PaymentSettlementService(db).process_confirmed_success(
                _confirmed_payment(
                    order_no=order.order_no,
                    attempt_no=attempt.attempt_no,
                    event_id="event-rollback-0004",
                    transaction_id="transaction-0004",
                    payload_hash="d" * 64,
                )
            )

    async with billing_session_factory() as db:
        persisted_order = await db.get(CommerceOrderModel, order.id)
        persisted_attempt = await db.get(PaymentAttemptModel, attempt.id)
        event_count = await db.scalar(select(func.count()).select_from(PaymentEventModel).where(PaymentEventModel.provider_event_id == "event-rollback-0004"))
        outbox_count = await db.scalar(select(func.count()).select_from(OutboxEventModel).where(OutboxEventModel.deduplication_key == f"billing.order.paid:{order.order_no}"))
        assert persisted_order is not None
        assert persisted_attempt is not None
        assert persisted_order.status == OrderStatus.PENDING.value
        assert persisted_order.paid_amount_minor == 0
        assert persisted_attempt.status == PaymentAttemptStatus.CREATED.value
        assert persisted_attempt.provider_transaction_id is None
        assert event_count == 0
        assert outbox_count == 0
