from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_membership.entitlement import as_utc, utc_now
from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_portal.principal import PortalPrincipal
from app.common.enums import RET
from app.core.exceptions import CustomException

from .model import CommerceOrderModel, PaymentAttemptModel, PaymentEventModel
from .repository import CommerceRepository
from .schema import (
    CommerceOrderCancelSchema,
    CommerceOrderCreateSchema,
    CommerceOrderOutSchema,
    PaymentAttemptCreateSchema,
    PaymentAttemptOutSchema,
    PaymentEventOutSchema,
    PaymentEventResultSchema,
    VerifiedPaymentEventSchema,
)

_CENT = Decimal("0.01")


class CommerceService:
    """Order and normalized payment transitions inside a caller-owned transaction.

    The service never commits or rolls back the outer transaction. Unique keys
    arbitrate concurrent idempotent requests through savepoints; all aggregate
    state changes are flushed atomically with the normalized payment event.
    """

    PAYMENT_WINDOW = timedelta(minutes=15)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = CommerceRepository(db)

    async def create_order(
        self,
        principal: PortalPrincipal,
        data: CommerceOrderCreateSchema,
    ) -> CommerceOrderOutSchema:
        legacy_user_id, customer_id = await self._resolve_owner(principal)
        existing = await self.repository.get_order_by_idempotency_key(
            data.idempotency_key,
            for_update=True,
        )
        if existing is not None:
            self._assert_order_idempotent_match(
                existing,
                legacy_user_id=legacy_user_id,
                customer_id=customer_id,
                plan_id=data.plan_id,
            )
            return self._order_schema(existing)

        plan = await self.db.scalar(
            select(MemberPlanModel).where(
                MemberPlanModel.id == data.plan_id,
                MemberPlanModel.status == 0,
                MemberPlanModel.is_deleted.is_(False),
            )
        )
        if plan is None:
            raise CustomException(
                msg="会员套餐不存在或已停用",
                code=RET.NOT_FOUND.code,
                status_code=RET.NOT_FOUND.code,
            )

        price = self._money(plan.price)
        currency = self._currency(plan.currency)
        now = utc_now()
        values = {
            "order_no": self._new_number("O"),
            "legacy_user_id": legacy_user_id,
            "customer_id": customer_id,
            "plan_id": plan.id,
            "plan_code_snapshot": plan.plan_code,
            "plan_name_snapshot": plan.plan_name,
            "duration_days_snapshot": plan.duration_days,
            "unit_price": price,
            "total_amount": price,
            "currency": currency,
            "status": "pending",
            "idempotency_key": data.idempotency_key,
            "payment_expires_at": now + self.PAYMENT_WINDOW,
            "paid_at": None,
            "cancelled_at": None,
            "cancel_reason": None,
            "version_no": 1,
        }

        try:
            async with self.db.begin_nested():
                order = CommerceOrderModel(**values)
                self.db.add(order)
                await self.db.flush()
        except IntegrityError as exc:
            existing = await self.repository.get_order_by_idempotency_key(
                data.idempotency_key,
                for_update=True,
            )
            if existing is None:
                raise self._conflict("订单写入冲突，请重新发起下单") from exc
            self._assert_order_idempotent_match(
                existing,
                legacy_user_id=legacy_user_id,
                customer_id=customer_id,
                plan_id=data.plan_id,
            )
            return self._order_schema(existing)

        return self._order_schema(order)

    async def cancel_order(
        self,
        principal: PortalPrincipal,
        order_id: int,
        data: CommerceOrderCancelSchema,
    ) -> CommerceOrderOutSchema:
        order = await self.repository.get_order(order_id, for_update=True)
        if order is None:
            raise self._not_found()
        self._assert_owner(order, principal)
        if order.version_no != data.version_no:
            raise self._conflict("订单版本已变化，请刷新后重试")
        if order.status != "pending":
            raise self._conflict("当前订单状态不允许取消")

        now = utc_now()
        order.status = "cancelled"
        order.cancelled_at = now
        order.cancel_reason = data.reason
        order.version_no += 1
        order.updated_time = now
        await self.db.flush()
        return self._order_schema(order)

    async def create_payment_attempt(
        self,
        principal: PortalPrincipal,
        order_id: int,
        data: PaymentAttemptCreateSchema,
    ) -> PaymentAttemptOutSchema:
        order = await self.repository.get_order(order_id, for_update=True)
        if order is None:
            raise self._not_found()
        self._assert_owner(order, principal)

        existing = await self.repository.get_payment_attempt_by_idempotency_key(
            order_id=order.id,
            idempotency_key=data.idempotency_key,
            for_update=True,
        )
        if existing is not None:
            if existing.provider != data.provider:
                raise self._conflict("支付幂等键已用于其他支付提供方")
            return self._attempt_schema(existing)

        now = utc_now()
        if order.status != "pending":
            raise self._conflict("当前订单状态不可发起支付")
        if as_utc(order.payment_expires_at) <= now:
            raise self._conflict("订单支付时间已结束")

        attempt_no = self._new_number("P")
        values = {
            "attempt_no": attempt_no,
            "order_id": order.id,
            "provider": data.provider,
            "merchant_request_no": attempt_no,
            "provider_transaction_id": None,
            "idempotency_key": data.idempotency_key,
            "amount": self._money(order.total_amount),
            "currency": self._currency(order.currency),
            "status": "created",
            "expires_at": order.payment_expires_at,
            "succeeded_at": None,
            "failed_at": None,
            "failure_code": None,
            "version_no": 1,
        }

        try:
            async with self.db.begin_nested():
                attempt = PaymentAttemptModel(**values)
                self.db.add(attempt)
                await self.db.flush()
        except IntegrityError as exc:
            existing = await self.repository.get_payment_attempt_by_idempotency_key(
                order_id=order.id,
                idempotency_key=data.idempotency_key,
                for_update=True,
            )
            if existing is None:
                raise self._conflict("支付尝试写入冲突，请重新发起支付") from exc
            if existing.provider != data.provider:
                raise self._conflict("支付幂等键已用于其他支付提供方")
            return self._attempt_schema(existing)

        return self._attempt_schema(attempt)

    async def record_verified_payment_event(
        self,
        data: VerifiedPaymentEventSchema,
    ) -> PaymentEventResultSchema:
        """Apply a verified provider event without storing the raw callback body."""

        existing = await self.repository.get_payment_event(
            provider=data.provider,
            provider_event_id=data.provider_event_id,
            for_update=True,
        )
        if existing is not None:
            self._assert_event_idempotent_match(existing, data)
            return await self._event_result(existing)

        attempt = await self.repository.get_payment_attempt_by_merchant_request(
            provider=data.provider,
            merchant_request_no=data.merchant_request_no,
            for_update=True,
        )
        if attempt is None:
            raise CustomException(
                msg="支付尝试不存在",
                code=RET.NOT_FOUND.code,
                status_code=RET.NOT_FOUND.code,
            )
        order = await self.repository.get_order(attempt.order_id, for_update=True)
        if order is None:
            raise RuntimeError("payment attempt references a missing order")

        processing_status, reason_code = self._decide_event(
            order=order,
            attempt=attempt,
            data=data,
        )
        now = utc_now()
        event = PaymentEventModel(
            order_id=order.id,
            payment_attempt_id=attempt.id,
            provider=data.provider,
            provider_event_id=data.provider_event_id,
            merchant_request_no=data.merchant_request_no,
            provider_transaction_id=data.provider_transaction_id,
            event_type=data.event_type,
            amount=self._money(data.amount),
            currency=self._currency(data.currency),
            signature_verified=True,
            payload_digest=data.payload_digest,
            processing_status=processing_status,
            reason_code=reason_code,
            occurred_at=as_utc(data.occurred_at),
            processed_at=now,
            note=None,
        )

        try:
            async with self.db.begin_nested():
                self.db.add(event)
                await self.db.flush()
        except IntegrityError as exc:
            existing = await self.repository.get_payment_event(
                provider=data.provider,
                provider_event_id=data.provider_event_id,
                for_update=True,
            )
            if existing is None:
                raise self._conflict("支付事件写入冲突，请稍后重试") from exc
            self._assert_event_idempotent_match(existing, data)
            return await self._event_result(existing)

        if processing_status == "accepted":
            self._apply_accepted_event(
                order=order,
                attempt=attempt,
                data=data,
                now=now,
            )
            await self.db.flush()

        return PaymentEventResultSchema(
            event=self._event_schema(event),
            order=self._order_schema(order),
            payment_attempt=self._attempt_schema(attempt),
        )

    async def _resolve_owner(
        self,
        principal: PortalPrincipal,
    ) -> tuple[int | None, int | None]:
        if not principal.is_authenticated:
            raise CustomException(
                msg="请登录后下单",
                code=RET.UNAUTHORIZED.code,
                status_code=RET.UNAUTHORIZED.code,
            )
        if principal.actor_type == "legacy":
            return principal.legacy_user_id, None

        if principal.actor_type != "customer" or principal.customer_id is None:
            raise CustomException(
                msg="客户身份无效",
                code=RET.UNAUTHORIZED.code,
                status_code=RET.UNAUTHORIZED.code,
            )
        mapping = await self.db.scalar(
            select(LegacyCustomerMapModel).where(
                LegacyCustomerMapModel.legacy_sys_user_id == principal.legacy_user_id,
                LegacyCustomerMapModel.customer_id == principal.customer_id,
                LegacyCustomerMapModel.credential_state == "migrated",
                LegacyCustomerMapModel.is_deleted.is_(False),
            )
        )
        if mapping is None:
            raise CustomException(
                msg="客户归属数据尚未完成一致性迁移",
                code=RET.SERVICE_UNAVAILABLE.code,
                status_code=RET.SERVICE_UNAVAILABLE.code,
            )
        return principal.legacy_user_id, principal.customer_id

    @staticmethod
    def _assert_owner(
        order: CommerceOrderModel,
        principal: PortalPrincipal,
    ) -> None:
        if not principal.is_authenticated:
            raise CommerceService._not_found()
        if principal.actor_type == "customer":
            if order.customer_id != principal.customer_id:
                raise CommerceService._not_found()
            if order.legacy_user_id is not None and order.legacy_user_id != principal.legacy_user_id:
                raise CustomException(
                    msg="订单客户归属数据不一致",
                    code=RET.SERVICE_UNAVAILABLE.code,
                    status_code=RET.SERVICE_UNAVAILABLE.code,
                )
            return
        if principal.actor_type == "legacy" and order.legacy_user_id == principal.legacy_user_id:
            if order.customer_id is not None:
                raise CustomException(
                    msg="订单已归属客户身份，请使用客户会话访问",
                    code=RET.UNAUTHORIZED.code,
                    status_code=RET.UNAUTHORIZED.code,
                )
            return
        raise CommerceService._not_found()

    @staticmethod
    def _assert_order_idempotent_match(
        existing: CommerceOrderModel,
        *,
        legacy_user_id: int | None,
        customer_id: int | None,
        plan_id: int,
    ) -> None:
        if (
            existing.legacy_user_id != legacy_user_id
            or existing.customer_id != customer_id
            or existing.plan_id != plan_id
        ):
            raise CommerceService._conflict("订单幂等键已用于其他下单参数")

    @classmethod
    def _decide_event(
        cls,
        *,
        order: CommerceOrderModel,
        attempt: PaymentAttemptModel,
        data: VerifiedPaymentEventSchema,
    ) -> tuple[str, str | None]:
        if cls._money(attempt.amount) != cls._money(data.amount):
            return "rejected", "amount_mismatch"
        if cls._currency(attempt.currency) != cls._currency(data.currency):
            return "rejected", "currency_mismatch"

        now = utc_now()
        if data.event_type == "payment_succeeded":
            if order.status == "paid":
                same_transaction = (
                    attempt.status == "succeeded"
                    and attempt.provider_transaction_id == data.provider_transaction_id
                )
                return (
                    ("ignored", "already_paid")
                    if same_transaction
                    else ("rejected", "order_already_paid")
                )
            if order.status != "pending":
                return "rejected", "order_not_payable"
            if as_utc(order.payment_expires_at) <= now:
                return "rejected", "order_expired"
            if attempt.status not in {"created", "processing"}:
                return "rejected", "attempt_not_payable"
            return "accepted", None

        if attempt.status == "succeeded" or order.status == "paid":
            return "ignored", "already_succeeded"
        if attempt.status in {"failed", "closed"}:
            return "ignored", f"already_{attempt.status}"
        if order.status != "pending":
            return "rejected", "order_not_payable"
        return "accepted", data.provider_reason_code or (
            "provider_failed" if data.event_type == "payment_failed" else "provider_closed"
        )

    @staticmethod
    def _apply_accepted_event(
        *,
        order: CommerceOrderModel,
        attempt: PaymentAttemptModel,
        data: VerifiedPaymentEventSchema,
        now,
    ) -> None:
        if data.event_type == "payment_succeeded":
            attempt.status = "succeeded"
            attempt.provider_transaction_id = data.provider_transaction_id
            attempt.succeeded_at = now
            attempt.failed_at = None
            attempt.failure_code = None
            attempt.version_no += 1
            attempt.updated_time = now

            order.status = "paid"
            order.paid_at = now
            order.version_no += 1
            order.updated_time = now
            return

        attempt.status = "failed" if data.event_type == "payment_failed" else "closed"
        attempt.failed_at = now
        attempt.failure_code = data.provider_reason_code or (
            "provider_failed" if data.event_type == "payment_failed" else "provider_closed"
        )
        attempt.version_no += 1
        attempt.updated_time = now

    @staticmethod
    def _assert_event_idempotent_match(
        existing: PaymentEventModel,
        data: VerifiedPaymentEventSchema,
    ) -> None:
        if (
            existing.merchant_request_no != data.merchant_request_no
            or existing.event_type != data.event_type
            or CommerceService._money(existing.amount) != CommerceService._money(data.amount)
            or CommerceService._currency(existing.currency) != CommerceService._currency(data.currency)
            or existing.provider_transaction_id != data.provider_transaction_id
            or existing.payload_digest != data.payload_digest
        ):
            raise CommerceService._conflict("支付事件幂等键已用于其他回调内容")

    async def _event_result(
        self,
        event: PaymentEventModel,
    ) -> PaymentEventResultSchema:
        order = await self.repository.get_order(event.order_id)
        attempt = await self.repository.get_payment_attempt(event.payment_attempt_id)
        if order is None or attempt is None:
            raise RuntimeError("payment event references a missing aggregate")
        return PaymentEventResultSchema(
            event=self._event_schema(event),
            order=self._order_schema(order),
            payment_attempt=self._attempt_schema(attempt),
        )

    @staticmethod
    def _new_number(prefix: str) -> str:
        return f"{prefix}{uuid4().hex.upper()}"

    @staticmethod
    def _money(value) -> Decimal:
        return Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP)

    @staticmethod
    def _currency(value: str) -> str:
        normalized = value.strip().upper()
        if not normalized or len(normalized) > 8:
            raise CustomException(
                msg="套餐币种配置无效",
                code=RET.BAD_REQUEST.code,
                status_code=RET.BAD_REQUEST.code,
            )
        return normalized

    @staticmethod
    def _order_schema(order: CommerceOrderModel) -> CommerceOrderOutSchema:
        return CommerceOrderOutSchema.model_validate(order)

    @staticmethod
    def _attempt_schema(attempt: PaymentAttemptModel) -> PaymentAttemptOutSchema:
        return PaymentAttemptOutSchema.model_validate(attempt)

    @staticmethod
    def _event_schema(event: PaymentEventModel) -> PaymentEventOutSchema:
        return PaymentEventOutSchema.model_validate(event)

    @staticmethod
    def _not_found() -> CustomException:
        return CustomException(
            msg="订单不存在",
            code=RET.NOT_FOUND.code,
            status_code=RET.NOT_FOUND.code,
        )

    @staticmethod
    def _conflict(message: str) -> CustomException:
        return CustomException(
            msg=message,
            code=RET.CONFLICT.code,
            status_code=RET.CONFLICT.code,
        )
