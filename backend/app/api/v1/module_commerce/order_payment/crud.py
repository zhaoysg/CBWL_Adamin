from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .model import CommerceOrderModel, PaymentAttemptModel, PaymentEventModel


def _lock(statement: Select, *, for_update: bool) -> Select:
    return statement.with_for_update() if for_update else statement


class CommerceOrderCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
        *,
        for_update: bool = False,
    ) -> CommerceOrderModel | None:
        statement = select(CommerceOrderModel).where(
            CommerceOrderModel.idempotency_key == idempotency_key,
            CommerceOrderModel.is_deleted.is_(False),
        )
        return await self.db.scalar(_lock(statement, for_update=for_update))

    async def get_by_order_no(
        self,
        order_no: str,
        *,
        for_update: bool = False,
    ) -> CommerceOrderModel | None:
        statement = select(CommerceOrderModel).where(
            CommerceOrderModel.order_no == order_no,
            CommerceOrderModel.is_deleted.is_(False),
        )
        return await self.db.scalar(_lock(statement, for_update=for_update))


class PaymentCRUD:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_attempt_by_idempotency_key(
        self,
        idempotency_key: str,
        *,
        for_update: bool = False,
    ) -> PaymentAttemptModel | None:
        statement = select(PaymentAttemptModel).where(
            PaymentAttemptModel.idempotency_key == idempotency_key,
            PaymentAttemptModel.is_deleted.is_(False),
        )
        return await self.db.scalar(_lock(statement, for_update=for_update))

    async def get_attempt_by_payment_no(
        self,
        payment_no: str,
        *,
        for_update: bool = False,
    ) -> PaymentAttemptModel | None:
        statement = select(PaymentAttemptModel).where(
            PaymentAttemptModel.payment_no == payment_no,
            PaymentAttemptModel.is_deleted.is_(False),
        )
        return await self.db.scalar(_lock(statement, for_update=for_update))

    async def get_event_by_provider_id(
        self,
        *,
        provider: str,
        provider_event_id: str,
        for_update: bool = False,
    ) -> PaymentEventModel | None:
        statement = select(PaymentEventModel).where(
            PaymentEventModel.provider == provider,
            PaymentEventModel.provider_event_id == provider_event_id,
            PaymentEventModel.is_deleted.is_(False),
        )
        return await self.db.scalar(_lock(statement, for_update=for_update))


__all__ = ["CommerceOrderCRUD", "PaymentCRUD"]
