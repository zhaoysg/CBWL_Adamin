from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.common.enums import RET
from app.core.exceptions import CustomException

from .crud import CommerceOrderCRUD, PaymentCRUD
from .model import CommerceOrderModel, PaymentAttemptModel, PaymentEventModel
from .ownership import CommerceOwner, CommerceOwnershipValidator
from .schema import (
    CommerceOrderOutSchema,
    MembershipOrderCreateSchema,
    OrderCancelSchema,
    PaymentAttemptCreateSchema,
    PaymentAttemptOutSchema,
    PaymentEventOutSchema,
    ProviderEventRegisterSchema,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _idempotency_digest(*parts: str) -> str:
    canonical = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _public_no(prefix: str) -> str:
    return f"{prefix}{uuid4().hex.upper()}"


class CommerceOrderService:
    """Create and cancel membership orders without accepting client prices."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CommerceOrderCRUD(db)

    async def create_membership_order(
        self,
        owner: CommerceOwner,
        data: MembershipOrderCreateSchema,
        *,
        now: datetime | None = None,
    ) -> CommerceOrderOutSchema:
        current = _as_utc(now or _utc_now())
        await CommerceOwnershipValidator.validate(self.db, owner)

        idempotency_key = _idempotency_digest(
            "membership-order",
            owner.namespace,
            data.request_key,
        )
        existing = await self.crud.get_by_idempotency_key(
            idempotency_key,
            for_update=True,
        )
        if existing is not None:
            self._assert_idempotent_match(existing, owner, data)
            return self._to_schema(existing)

        plan_statement = (
            select(MemberPlanModel)
            .where(
                MemberPlanModel.id == data.plan_id,
                MemberPlanModel.status == 0,
                MemberPlanModel.is_deleted.is_(False),
            )
            .with_for_update()
        )
        plan = await self.db.scalar(plan_statement)
        if plan is None:
            raise CustomException(
                msg="会员套餐不存在或已停用",
                code=RET.NOT_FOUND.code,
                status_code=RET.NOT_FOUND.code,
            )

        amount = Decimal(plan.price).quantize(Decimal("0.01"))
        values = {
            "order_no": _public_no("CO"),
            "idempotency_key": idempotency_key,
            "legacy_user_id": owner.legacy_user_id,
            "customer_id": owner.customer_id,
            "product_type": "membership",
            "plan_id": plan.id,
            "plan_code_snapshot": plan.plan_code,
            "plan_name_snapshot": plan.plan_name,
            "plan_level_no_snapshot": plan.rank,
            "duration_days_snapshot": plan.duration_days,
            "benefits_snapshot": list(plan.benefits or []),
            "amount": amount,
            "currency": plan.currency.upper(),
            "status": "pending",
            "payment_window_seconds": data.payment_window_seconds,
            "expires_at": current + timedelta(seconds=data.payment_window_seconds),
            "paid_at": None,
            "cancelled_at": None,
            "closed_at": None,
            "refunded_at": None,
            "cancel_reason": None,
            "version_no": 1,
            "description": data.description,
        }

        try:
            async with self.db.begin_nested():
                order = CommerceOrderModel(**values)
                self.db.add(order)
                await self.db.flush()
        except IntegrityError:
            existing = await self.crud.get_by_idempotency_key(
                idempotency_key,
                for_update=True,
            )
            if existing is None:
                raise self._conflict("订单写入冲突，请使用新的请求键重试")
            self._assert_idempotent_match(existing, owner, data)
            return self._to_schema(existing)

        return self._to_schema(order)

    async def cancel(
        self,
        owner: CommerceOwner,
        order_no: str,
        data: OrderCancelSchema,
        *,
        now: datetime | None = None,
    ) -> CommerceOrderOutSchema:
        await CommerceOwnershipValidator.validate(self.db, owner)
        order = await self.crud.get_by_order_no(order_no.upper(), for_update=True)
        if order is None:
            raise CustomException(
                msg="订单不存在",
                code=RET.NOT_FOUND.code,
                status_code=RET.NOT_FOUND.code,
            )
        self.assert_owned(order, owner)
        if order.version_no != data.version_no:
            raise self._conflict("订单版本已变化，请刷新后重试")
        if order.status != "pending":
            raise self._conflict("当前订单状态不允许取消")

        current = _as_utc(now or _utc_now())
        order.status = "cancelled"
        order.cancelled_at = current
        order.cancel_reason = data.reason
        order.version_no += 1
        order.updated_time = current
        await self.db.flush()
        return self._to_schema(order)

    @classmethod
    def _assert_idempotent_match(
        cls,
        existing: CommerceOrderModel,
        owner: CommerceOwner,
        data: MembershipOrderCreateSchema,
    ) -> None:
        cls.assert_owned(existing, owner)
        mismatches: list[str] = []
        if existing.plan_id != data.plan_id:
            mismatches.append("套餐")
        if existing.payment_window_seconds != data.payment_window_seconds:
            mismatches.append("支付窗口")
        if (existing.description or None) != (data.description or None):
            mismatches.append("内部备注")
        if mismatches:
            raise cls._conflict(
                f"订单请求键已用于其他参数：{'、'.join(mismatches)}不一致"
            )

    @staticmethod
    def assert_owned(
        order: CommerceOrderModel,
        owner: CommerceOwner,
    ) -> None:
        if owner.actor_type == "legacy":
            owned = (
                order.legacy_user_id == owner.legacy_user_id
                and order.customer_id is None
            )
        else:
            owned = order.customer_id == owner.customer_id
            if (
                owned
                and order.legacy_user_id is not None
                and owner.legacy_user_id is not None
            ):
                owned = order.legacy_user_id == owner.legacy_user_id
        if not owned:
            raise CustomException(
                msg="无权访问该订单",
                code=RET.FORBIDDEN.code,
                status_code=RET.FORBIDDEN.code,
            )

    @staticmethod
    def _to_schema(order: CommerceOrderModel) -> CommerceOrderOutSchema:
        return CommerceOrderOutSchema.model_validate(order)

    @staticmethod
    def _conflict(message: str) -> CustomException:
        return CustomException(
            msg=message,
            code=RET.CONFLICT.code,
            status_code=RET.CONFLICT.code,
        )


class PaymentService:
    """Create provider attempts and deduplicate callback envelopes.

    This M4 expand service intentionally does not settle an order or grant a
    membership. Settlement/outbox processing is introduced in the next stacked
    transaction PR.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.order_crud = CommerceOrderCRUD(db)
        self.payment_crud = PaymentCRUD(db)

    async def create_attempt(
        self,
        owner: CommerceOwner,
        data: PaymentAttemptCreateSchema,
        *,
        now: datetime | None = None,
    ) -> PaymentAttemptOutSchema:
        current = _as_utc(now or _utc_now())
        await CommerceOwnershipValidator.validate(self.db, owner)

        idempotency_key = _idempotency_digest(
            "payment-attempt",
            owner.namespace,
            data.request_key,
        )
        existing = await self.payment_crud.get_attempt_by_idempotency_key(
            idempotency_key,
            for_update=True,
        )
        if existing is not None:
            self._assert_attempt_idempotent_match(existing, owner, data)
            return self._attempt_to_schema(existing)

        order = await self.order_crud.get_by_order_no(
            data.order_no,
            for_update=True,
        )
        if order is None:
            raise CustomException(
                msg="订单不存在",
                code=RET.NOT_FOUND.code,
                status_code=RET.NOT_FOUND.code,
            )
        CommerceOrderService.assert_owned(order, owner)
        if order.status != "pending":
            raise CommerceOrderService._conflict("当前订单状态不允许发起支付")
        if _as_utc(order.expires_at) <= current:
            raise CommerceOrderService._conflict("订单已超过支付有效期")

        values = {
            "payment_no": _public_no("CP"),
            "idempotency_key": idempotency_key,
            "order_id": order.id,
            "order_no": order.order_no,
            "legacy_user_id": order.legacy_user_id,
            "customer_id": order.customer_id,
            "provider": data.provider,
            "channel": data.channel,
            "provider_trade_no": None,
            "amount": order.amount,
            "currency": order.currency,
            "status": "pending",
            "initiated_at": current,
            "succeeded_at": None,
            "failed_at": None,
            "closed_at": None,
            "refunded_at": None,
            "failure_code": None,
            "failure_message": None,
            "version_no": 1,
        }

        try:
            async with self.db.begin_nested():
                attempt = PaymentAttemptModel(**values)
                self.db.add(attempt)
                await self.db.flush()
        except IntegrityError:
            existing = await self.payment_crud.get_attempt_by_idempotency_key(
                idempotency_key,
                for_update=True,
            )
            if existing is None:
                raise CommerceOrderService._conflict(
                    "支付尝试写入冲突，请使用新的请求键重试"
                )
            self._assert_attempt_idempotent_match(existing, owner, data)
            return self._attempt_to_schema(existing)

        return self._attempt_to_schema(attempt)

    async def register_provider_event(
        self,
        data: ProviderEventRegisterSchema,
        *,
        now: datetime | None = None,
    ) -> PaymentEventOutSchema:
        existing = await self.payment_crud.get_event_by_provider_id(
            provider=data.provider,
            provider_event_id=data.provider_event_id,
            for_update=True,
        )
        if existing is not None:
            self._assert_event_idempotent_match(existing, data)
            return self._event_to_schema(existing)

        payment = await self.payment_crud.get_attempt_by_payment_no(
            data.payment_no,
            for_update=True,
        )
        if payment is None:
            raise CustomException(
                msg="支付记录不存在",
                code=RET.NOT_FOUND.code,
                status_code=RET.NOT_FOUND.code,
            )
        if payment.provider != data.provider:
            raise CommerceOrderService._conflict("支付提供方与原支付尝试不一致")

        current = _as_utc(now or _utc_now())
        values = {
            "payment_id": payment.id,
            "payment_no": payment.payment_no,
            "provider": data.provider,
            "provider_event_id": data.provider_event_id,
            "event_type": data.event_type,
            "payload_digest": data.payload_digest,
            "status": "received",
            "received_at": current,
            "processed_at": None,
            "processing_code": None,
            "processing_message": None,
            "version_no": 1,
        }

        try:
            async with self.db.begin_nested():
                event = PaymentEventModel(**values)
                self.db.add(event)
                await self.db.flush()
        except IntegrityError:
            existing = await self.payment_crud.get_event_by_provider_id(
                provider=data.provider,
                provider_event_id=data.provider_event_id,
                for_update=True,
            )
            if existing is None:
                raise CommerceOrderService._conflict(
                    "支付事件写入冲突，请稍后重试"
                )
            self._assert_event_idempotent_match(existing, data)
            return self._event_to_schema(existing)

        return self._event_to_schema(event)

    @staticmethod
    def _assert_attempt_idempotent_match(
        existing: PaymentAttemptModel,
        owner: CommerceOwner,
        data: PaymentAttemptCreateSchema,
    ) -> None:
        mismatches: list[str] = []
        if existing.order_no != data.order_no:
            mismatches.append("订单")
        if existing.provider != data.provider:
            mismatches.append("支付提供方")
        if existing.channel != data.channel:
            mismatches.append("支付渠道")
        if owner.actor_type == "legacy":
            if (
                existing.legacy_user_id != owner.legacy_user_id
                or existing.customer_id is not None
            ):
                mismatches.append("交易主体")
        elif existing.customer_id != owner.customer_id:
            mismatches.append("交易主体")
        elif (
            existing.legacy_user_id is not None
            and owner.legacy_user_id is not None
            and existing.legacy_user_id != owner.legacy_user_id
        ):
            mismatches.append("旧用户映射")
        if mismatches:
            raise CommerceOrderService._conflict(
                f"支付请求键已用于其他参数：{'、'.join(mismatches)}不一致"
            )

    @staticmethod
    def _assert_event_idempotent_match(
        existing: PaymentEventModel,
        data: ProviderEventRegisterSchema,
    ) -> None:
        mismatches: list[str] = []
        if existing.payment_no != data.payment_no:
            mismatches.append("支付记录")
        if existing.event_type != data.event_type:
            mismatches.append("事件类型")
        if existing.payload_digest != data.payload_digest:
            mismatches.append("载荷摘要")
        if mismatches:
            raise CommerceOrderService._conflict(
                f"提供方事件ID已用于其他回调：{'、'.join(mismatches)}不一致"
            )

    @staticmethod
    def _attempt_to_schema(
        attempt: PaymentAttemptModel,
    ) -> PaymentAttemptOutSchema:
        return PaymentAttemptOutSchema.model_validate(attempt)

    @staticmethod
    def _event_to_schema(event: PaymentEventModel) -> PaymentEventOutSchema:
        return PaymentEventOutSchema.model_validate(event)


__all__ = ["CommerceOrderService", "PaymentService"]
