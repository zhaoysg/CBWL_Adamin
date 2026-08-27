from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_billing.enums import OrderStatus
from app.api.v1.module_billing.money import decimal_to_minor
from app.api.v1.module_membership.entitlement import utc_now
from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_system.user.model import UserModel
from app.common.enums import RET
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException

from .model import CommerceOrderModel
from .schema import OrderCloseSchema, OrderCreateSchema, OrderOutSchema


class OrderService:
    """Current-user order creation and pending-order state transitions."""

    ORDER_TTL = timedelta(minutes=30)

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    async def create(self, data: OrderCreateSchema) -> OrderOutSchema:
        user_id = self._current_user_id()
        existing = await self._get_by_idempotency(
            user_id=user_id,
            idempotency_key=data.idempotency_key,
            for_update=True,
        )
        if existing is not None:
            if existing.plan_id != data.plan_id:
                raise self._conflict("下单幂等键已用于其他会员套餐")
            return self._to_schema(existing)

        user = await self.db.scalar(
            select(UserModel).where(
                UserModel.id == user_id,
                UserModel.status == 0,
                UserModel.is_deleted.is_(False),
            )
        )
        if user is None:
            raise CustomException(msg="用户不存在或已停用", status_code=RET.NOT_FOUND.code)

        plan = await self.db.scalar(
            select(MemberPlanModel).where(
                MemberPlanModel.id == data.plan_id,
                MemberPlanModel.status == 0,
                MemberPlanModel.is_deleted.is_(False),
            )
        )
        if plan is None:
            raise CustomException(msg="会员套餐不存在或已停用", status_code=RET.NOT_FOUND.code)

        try:
            amount_minor = decimal_to_minor(plan.price, plan.currency)
        except ValueError as exc:
            raise CustomException(
                msg=str(exc),
                code=RET.BAD_REQUEST.code,
                status_code=RET.BAD_REQUEST.code,
            ) from exc

        now = utc_now()
        values = {
            "order_no": self._new_reference("CW"),
            "user_id": user_id,
            "plan_id": plan.id,
            "idempotency_key": data.idempotency_key,
            "plan_snapshot": {
                "plan_id": plan.id,
                "plan_code": plan.plan_code,
                "plan_name": plan.plan_name,
                "rank": plan.rank,
                "duration_days": plan.duration_days,
                "benefits": list(plan.benefits or []),
                "amount_minor": amount_minor,
                "currency": plan.currency,
            },
            "amount_minor": amount_minor,
            "currency": plan.currency,
            "status": OrderStatus.PENDING.value,
            "expires_at": now + self.ORDER_TTL,
            "paid_at": None,
            "closed_at": None,
            "paid_amount_minor": 0,
            "refunded_amount_minor": 0,
            "version_no": 1,
            "created_id": user_id,
            "updated_id": user_id,
        }

        try:
            async with self.db.begin_nested():
                order = CommerceOrderModel(**values)
                self.db.add(order)
                await self.db.flush()
        except IntegrityError:
            existing = await self._get_by_idempotency(
                user_id=user_id,
                idempotency_key=data.idempotency_key,
                for_update=True,
            )
            if existing is None:
                raise self._conflict("订单创建冲突，请稍后重试")
            if existing.plan_id != data.plan_id:
                raise self._conflict("下单幂等键已用于其他会员套餐")
            return self._to_schema(existing)

        return self._to_schema(order)

    async def close(self, order_no: str, data: OrderCloseSchema) -> OrderOutSchema:
        order = await self.get_owned_for_update(order_no)
        if order.status == OrderStatus.CLOSED.value:
            return self._to_schema(order)
        if order.version_no != data.version_no:
            raise self._conflict("订单版本已变化，请刷新后重试")
        if order.status != OrderStatus.PENDING.value:
            raise self._conflict("只有待支付订单可以关闭")

        now = utc_now()
        order.status = OrderStatus.CLOSED.value
        order.closed_at = now
        order.version_no += 1
        order.updated_time = now
        order.updated_id = self._current_user_id()
        await self.db.flush()
        return self._to_schema(order)

    async def get_owned_for_update(self, order_no: str) -> CommerceOrderModel:
        user_id = self._current_user_id()
        result = await self.db.execute(
            select(CommerceOrderModel)
            .where(
                CommerceOrderModel.order_no == order_no,
                CommerceOrderModel.user_id == user_id,
                CommerceOrderModel.is_deleted.is_(False),
            )
            .with_for_update()
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise CustomException(msg="订单不存在", status_code=RET.NOT_FOUND.code)
        return order

    async def _get_by_idempotency(
        self,
        *,
        user_id: int,
        idempotency_key: str,
        for_update: bool,
    ) -> CommerceOrderModel | None:
        statement = select(CommerceOrderModel).where(
            CommerceOrderModel.user_id == user_id,
            CommerceOrderModel.idempotency_key == idempotency_key,
            CommerceOrderModel.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)

    def _current_user_id(self) -> int:
        user_id = int(self.auth.user.id or 0)
        if user_id <= 0:
            raise CustomException(
                msg="认证已失效",
                code=RET.UNAUTHORIZED.code,
                status_code=RET.UNAUTHORIZED.code,
            )
        return user_id

    @staticmethod
    def _new_reference(prefix: str) -> str:
        return f"{prefix}{utc_now():%Y%m%d%H%M%S}{uuid4().hex[:12].upper()}"

    @staticmethod
    def _to_schema(order: CommerceOrderModel) -> OrderOutSchema:
        return OrderOutSchema.model_validate(order)

    @staticmethod
    def _conflict(message: str) -> CustomException:
        return CustomException(
            msg=message,
            code=RET.CONFLICT.code,
            status_code=RET.CONFLICT.code,
        )
