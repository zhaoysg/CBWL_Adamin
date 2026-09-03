from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .model import CommerceOrderModel, PaymentAttemptModel, PaymentEventModel


class CommerceRepository:
    """Parameterized data access for the commerce aggregate."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_order(
        self,
        order_id: int,
        *,
        for_update: bool = False,
    ) -> CommerceOrderModel | None:
        statement = select(CommerceOrderModel).where(
            CommerceOrderModel.id == order_id,
            CommerceOrderModel.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)

    async def get_order_by_idempotency_key(
        self,
        idempotency_key: str,
        *,
        for_update: bool = False,
    ) -> CommerceOrderModel | None:
        statement = select(CommerceOrderModel).where(
            CommerceOrderModel.idempotency_key == idempotency_key,
            CommerceOrderModel.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)

    async def get_payment_attempt(
        self,
        attempt_id: int,
        *,
        for_update: bool = False,
    ) -> PaymentAttemptModel | None:
        statement = select(PaymentAttemptModel).where(
            PaymentAttemptModel.id == attempt_id,
            PaymentAttemptModel.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)

    async def get_payment_attempt_by_idempotency_key(
        self,
        *,
        order_id: int,
        idempotency_key: str,
        for_update: bool = False,
    ) -> PaymentAttemptModel | None:
        statement = select(PaymentAttemptModel).where(
            PaymentAttemptModel.order_id == order_id,
            PaymentAttemptModel.idempotency_key == idempotency_key,
            PaymentAttemptModel.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)

    async def get_payment_attempt_by_merchant_request(
        self,
        *,
        provider: str,
        merchant_request_no: str,
        for_update: bool = False,
    ) -> PaymentAttemptModel | None:
        statement = select(PaymentAttemptModel).where(
            PaymentAttemptModel.provider == provider,
            PaymentAttemptModel.merchant_request_no == merchant_request_no,
            PaymentAttemptModel.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)

    async def get_payment_event(
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
        if for_update:
            statement = statement.with_for_update()
        return await self.db.scalar(statement)
