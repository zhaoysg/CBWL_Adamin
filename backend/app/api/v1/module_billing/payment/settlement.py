from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_billing.enums import (
    OrderStatus,
    OutboxEventStatus,
    PaymentAttemptStatus,
    PaymentEventProcessingStatus,
)
from app.api.v1.module_billing.order.model import CommerceOrderModel
from app.api.v1.module_billing.outbox.model import OutboxEventModel
from app.api.v1.module_membership.entitlement import as_utc, utc_now
from app.api.v1.module_membership.subscription.model import MemberSubscriptionModel
from app.common.enums import RET
from app.core.exceptions import CustomException

from .model import PaymentAttemptModel, PaymentEventModel
from .schema import ConfirmedPaymentSchema, PaymentProcessingResultSchema


class PaymentSettlementService:
    """Apply a provider-verified success fact in one database transaction."""

    SUBSCRIPTION_SOURCE = "payment"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def process_confirmed_success(
        self,
        data: ConfirmedPaymentSchema,
    ) -> PaymentProcessingResultSchema:
        event, duplicate = await self._create_or_get_event(data)
        if duplicate:
            return await self._result_for_existing(event, duplicate=True)

        order = await self.db.scalar(
            select(CommerceOrderModel)
            .where(
                CommerceOrderModel.order_no == data.order_no,
                CommerceOrderModel.is_deleted.is_(False),
            )
            .with_for_update()
        )
        if order is None:
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason="order_not_found",
            )

        event.order_id = order.id
        if order.status == OrderStatus.PAID.value:
            owner = await self._transaction_owner(data)
            if owner is not None and owner.order_id == order.id and order.amount_minor == data.amount_minor and order.currency == data.currency:
                return await self._finish_event(
                    event,
                    status=PaymentEventProcessingStatus.IGNORED,
                    reason="duplicate_payment_fact",
                    order=order,
                )
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason="order_already_paid_by_other_transaction",
                order=order,
            )

        if order.status != OrderStatus.PENDING.value:
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason=f"order_status_{order.status}",
                order=order,
            )
        if as_utc(order.expires_at) <= utc_now():
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason="order_expired",
                order=order,
            )
        if order.amount_minor != data.amount_minor or order.currency != data.currency:
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason="amount_or_currency_mismatch",
                order=order,
            )

        attempt = await self.db.scalar(
            select(PaymentAttemptModel)
            .where(
                PaymentAttemptModel.attempt_no == data.attempt_no,
                PaymentAttemptModel.order_id == order.id,
                PaymentAttemptModel.provider == data.provider.value,
                PaymentAttemptModel.is_deleted.is_(False),
            )
            .with_for_update()
        )
        if attempt is None:
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason="payment_attempt_not_found",
                order=order,
            )
        if attempt.status not in {
            PaymentAttemptStatus.CREATED.value,
            PaymentAttemptStatus.PENDING.value,
        }:
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason=f"payment_attempt_status_{attempt.status}",
                order=order,
            )

        transaction_owner = await self._transaction_owner(data)
        if transaction_owner is not None and transaction_owner.id != attempt.id:
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason="provider_transaction_bound_to_other_attempt",
                order=order,
            )

        now = data.occurred_at or utc_now()
        try:
            async with self.db.begin_nested():
                attempt.provider_transaction_id = data.provider_transaction_id
                attempt.status = PaymentAttemptStatus.SUCCEEDED.value
                attempt.provider_status = "succeeded"
                attempt.succeeded_at = now
                attempt.version_no += 1
                attempt.updated_time = utc_now()
                await self.db.flush()
        except IntegrityError:
            return await self._finish_event(
                event,
                status=PaymentEventProcessingStatus.REJECTED,
                reason="provider_transaction_conflict",
                order=order,
            )

        order.status = OrderStatus.PAID.value
        order.paid_at = now
        order.paid_amount_minor = data.amount_minor
        order.version_no += 1
        order.updated_time = utc_now()

        subscription = await self._grant_subscription(order, data)
        outbox = await self._create_outbox(order, subscription)

        event.processing_status = PaymentEventProcessingStatus.PROCESSED.value
        event.processing_error = None
        event.processed_at = utc_now()
        await self.db.flush()
        return PaymentProcessingResultSchema(
            event_id=event.id,
            processing_status=PaymentEventProcessingStatus.PROCESSED,
            order_id=order.id,
            order_no=order.order_no,
            order_status=OrderStatus.PAID,
            subscription_id=subscription.id,
            outbox_event_id=outbox.id,
        )

    async def _create_or_get_event(
        self,
        data: ConfirmedPaymentSchema,
    ) -> tuple[PaymentEventModel, bool]:
        existing = await self.db.scalar(
            select(PaymentEventModel)
            .where(
                PaymentEventModel.provider == data.provider.value,
                PaymentEventModel.provider_event_id == data.provider_event_id,
            )
            .with_for_update()
        )
        if existing is not None:
            self._assert_same_event(existing, data)
            return existing, True

        values = {
            "provider": data.provider.value,
            "provider_event_id": data.provider_event_id,
            "event_type": data.event_type,
            "provider_transaction_id": data.provider_transaction_id,
            "order_id": None,
            "order_no": data.order_no,
            "amount_minor": data.amount_minor,
            "currency": data.currency,
            "payload_hash": data.payload_hash,
            "signature_verified": True,
            "event_metadata": data.event_metadata,
            "received_at": utc_now(),
            "processing_status": PaymentEventProcessingStatus.RECEIVED.value,
            "processed_at": None,
            "processing_error": None,
        }
        try:
            async with self.db.begin_nested():
                event = PaymentEventModel(**values)
                self.db.add(event)
                await self.db.flush()
        except IntegrityError:
            existing = await self.db.scalar(
                select(PaymentEventModel)
                .where(
                    PaymentEventModel.provider == data.provider.value,
                    PaymentEventModel.provider_event_id == data.provider_event_id,
                )
                .with_for_update()
            )
            if existing is None:
                raise self._conflict("支付事件写入冲突，请稍后重试")
            self._assert_same_event(existing, data)
            return existing, True
        return event, False

    async def _transaction_owner(
        self,
        data: ConfirmedPaymentSchema,
    ) -> PaymentAttemptModel | None:
        return await self.db.scalar(
            select(PaymentAttemptModel)
            .where(
                PaymentAttemptModel.provider == data.provider.value,
                PaymentAttemptModel.provider_transaction_id == data.provider_transaction_id,
                PaymentAttemptModel.is_deleted.is_(False),
            )
            .with_for_update()
        )

    async def _grant_subscription(
        self,
        order: CommerceOrderModel,
        data: ConfirmedPaymentSchema,
    ) -> MemberSubscriptionModel:
        existing = await self.db.scalar(
            select(MemberSubscriptionModel)
            .where(
                MemberSubscriptionModel.source == self.SUBSCRIPTION_SOURCE,
                MemberSubscriptionModel.source_ref == order.order_no,
                MemberSubscriptionModel.is_deleted.is_(False),
            )
            .with_for_update()
        )
        if existing is not None:
            self._assert_subscription_matches(existing, order)
            return existing

        duration_days = order.plan_snapshot.get("duration_days")
        if not isinstance(duration_days, int) or duration_days <= 0:
            raise self._conflict("订单套餐快照缺少有效的会员时长")

        starts_at = data.occurred_at or utc_now()
        values = {
            "user_id": order.user_id,
            "plan_id": order.plan_id,
            "source": self.SUBSCRIPTION_SOURCE,
            "source_ref": order.order_no,
            "status": 0,
            "starts_at": starts_at,
            "expires_at": starts_at + timedelta(days=duration_days),
            "revoked_at": None,
            "grant_reason": f"订单 {order.order_no} 支付成功自动发放",
            "revoke_reason": None,
            "version_no": 1,
            "description": f"provider={data.provider.value}; transaction={data.provider_transaction_id}",
        }
        try:
            async with self.db.begin_nested():
                subscription = MemberSubscriptionModel(**values)
                self.db.add(subscription)
                await self.db.flush()
        except IntegrityError:
            existing = await self.db.scalar(
                select(MemberSubscriptionModel)
                .where(
                    MemberSubscriptionModel.source == self.SUBSCRIPTION_SOURCE,
                    MemberSubscriptionModel.source_ref == order.order_no,
                    MemberSubscriptionModel.is_deleted.is_(False),
                )
                .with_for_update()
            )
            if existing is None:
                raise self._conflict("会员订阅写入冲突，请稍后重试")
            self._assert_subscription_matches(existing, order)
            return existing
        return subscription

    async def _create_outbox(
        self,
        order: CommerceOrderModel,
        subscription: MemberSubscriptionModel,
    ) -> OutboxEventModel:
        deduplication_key = f"billing.order.paid:{order.order_no}"
        existing = await self.db.scalar(select(OutboxEventModel).where(OutboxEventModel.deduplication_key == deduplication_key).with_for_update())
        if existing is not None:
            return existing

        values = {
            "event_id": self._new_reference("OB"),
            "deduplication_key": deduplication_key,
            "aggregate_type": "order",
            "aggregate_id": order.order_no,
            "event_type": "billing.order.paid",
            "payload": {
                "order_no": order.order_no,
                "user_id": order.user_id,
                "plan_id": order.plan_id,
                "subscription_id": subscription.id,
                "amount_minor": order.amount_minor,
                "currency": order.currency,
            },
            "status": OutboxEventStatus.PENDING.value,
            "available_at": utc_now(),
            "published_at": None,
            "attempts": 0,
            "last_error": None,
            "version_no": 1,
        }
        try:
            async with self.db.begin_nested():
                outbox = OutboxEventModel(**values)
                self.db.add(outbox)
                await self.db.flush()
        except IntegrityError:
            existing = await self.db.scalar(select(OutboxEventModel).where(OutboxEventModel.deduplication_key == deduplication_key).with_for_update())
            if existing is None:
                raise self._conflict("事务发件箱写入冲突，请稍后重试")
            return existing
        return outbox

    async def _finish_event(
        self,
        event: PaymentEventModel,
        *,
        status: PaymentEventProcessingStatus,
        reason: str,
        order: CommerceOrderModel | None = None,
    ) -> PaymentProcessingResultSchema:
        event.processing_status = status.value
        event.processing_error = reason
        event.processed_at = utc_now()
        await self.db.flush()
        return PaymentProcessingResultSchema(
            event_id=event.id,
            processing_status=status,
            reason=reason,
            order_id=order.id if order is not None else None,
            order_no=order.order_no if order is not None else event.order_no,
            order_status=OrderStatus(order.status) if order is not None else None,
        )

    async def _result_for_existing(
        self,
        event: PaymentEventModel,
        *,
        duplicate: bool,
    ) -> PaymentProcessingResultSchema:
        order = None
        subscription = None
        outbox = None
        if event.order_id is not None:
            order = await self.db.get(CommerceOrderModel, event.order_id)
        if event.order_no:
            subscription = await self.db.scalar(
                select(MemberSubscriptionModel).where(
                    MemberSubscriptionModel.source == self.SUBSCRIPTION_SOURCE,
                    MemberSubscriptionModel.source_ref == event.order_no,
                    MemberSubscriptionModel.is_deleted.is_(False),
                )
            )
            outbox = await self.db.scalar(select(OutboxEventModel).where(OutboxEventModel.deduplication_key == f"billing.order.paid:{event.order_no}"))
        return PaymentProcessingResultSchema(
            event_id=event.id,
            processing_status=PaymentEventProcessingStatus(event.processing_status),
            duplicate=duplicate,
            reason=event.processing_error,
            order_id=order.id if order is not None else event.order_id,
            order_no=order.order_no if order is not None else event.order_no,
            order_status=OrderStatus(order.status) if order is not None else None,
            subscription_id=subscription.id if subscription is not None else None,
            outbox_event_id=outbox.id if outbox is not None else None,
        )

    @staticmethod
    def _assert_same_event(
        existing: PaymentEventModel,
        data: ConfirmedPaymentSchema,
    ) -> None:
        if (
            existing.event_type != data.event_type
            or existing.provider_transaction_id != data.provider_transaction_id
            or existing.order_no != data.order_no
            or existing.amount_minor != data.amount_minor
            or existing.currency != data.currency
            or existing.payload_hash != data.payload_hash
        ):
            raise PaymentSettlementService._conflict("Provider 事件ID已用于其他支付事实")

    @staticmethod
    def _assert_subscription_matches(
        existing: MemberSubscriptionModel,
        order: CommerceOrderModel,
    ) -> None:
        if existing.user_id != order.user_id or existing.plan_id != order.plan_id:
            raise PaymentSettlementService._conflict("订单号已关联到其他会员订阅")

    @staticmethod
    def _new_reference(prefix: str) -> str:
        return f"{prefix}{utc_now():%Y%m%d%H%M%S}{uuid4().hex[:12].upper()}"

    @staticmethod
    def _conflict(message: str) -> CustomException:
        return CustomException(
            msg=message,
            code=RET.CONFLICT.code,
            status_code=RET.CONFLICT.code,
        )
