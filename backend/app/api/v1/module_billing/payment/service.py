from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_billing.enums import OrderStatus, PaymentAttemptStatus
from app.api.v1.module_billing.order.service import OrderService
from app.api.v1.module_membership.entitlement import as_utc, utc_now
from app.common.enums import RET
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException

from .model import PaymentAttemptModel
from .schema import PaymentAttemptCreateSchema, PaymentAttemptOutSchema


class PaymentAttemptService:
    """Create current-user payment attempts from immutable order money."""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.order_service = OrderService(auth, db)

    async def create(
        self,
        order_no: str,
        data: PaymentAttemptCreateSchema,
    ) -> PaymentAttemptOutSchema:
        order = await self.order_service.get_owned_for_update(order_no)
        if order.status != OrderStatus.PENDING.value:
            raise self._conflict("只有待支付订单可以创建支付尝试")
        if as_utc(order.expires_at) <= utc_now():
            raise self._conflict("订单已超过支付有效期")

        existing = await self.db.scalar(
            select(PaymentAttemptModel)
            .where(
                PaymentAttemptModel.order_id == order.id,
                PaymentAttemptModel.idempotency_key == data.idempotency_key,
                PaymentAttemptModel.is_deleted.is_(False),
            )
            .with_for_update()
        )
        if existing is not None:
            if existing.provider != data.provider.value:
                raise self._conflict("支付幂等键已用于其他支付 Provider")
            return PaymentAttemptOutSchema.model_validate(existing)

        user_id = int(self.auth.user.id or 0)
        values = {
            "attempt_no": self._new_reference("PA"),
            "order_id": order.id,
            "provider": data.provider.value,
            "idempotency_key": data.idempotency_key,
            "provider_transaction_id": None,
            "status": PaymentAttemptStatus.CREATED.value,
            "amount_minor": order.amount_minor,
            "currency": order.currency,
            "provider_status": None,
            "payment_payload": None,
            "failure_code": None,
            "failure_message": None,
            "expires_at": order.expires_at,
            "succeeded_at": None,
            "version_no": 1,
            "created_id": user_id,
            "updated_id": user_id,
        }

        try:
            async with self.db.begin_nested():
                attempt = PaymentAttemptModel(**values)
                self.db.add(attempt)
                await self.db.flush()
        except IntegrityError:
            existing = await self.db.scalar(
                select(PaymentAttemptModel)
                .where(
                    PaymentAttemptModel.order_id == order.id,
                    PaymentAttemptModel.idempotency_key == data.idempotency_key,
                    PaymentAttemptModel.is_deleted.is_(False),
                )
                .with_for_update()
            )
            if existing is None:
                raise self._conflict("支付尝试创建冲突，请稍后重试")
            if existing.provider != data.provider.value:
                raise self._conflict("支付幂等键已用于其他支付 Provider")
            return PaymentAttemptOutSchema.model_validate(existing)

        return PaymentAttemptOutSchema.model_validate(attempt)

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
