from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.v1.module_billing.enums import OrderStatus

_REFERENCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"


class OrderCreateSchema(BaseModel):
    plan_id: int = Field(ge=1, description="会员套餐ID")
    idempotency_key: str = Field(
        min_length=8,
        max_length=128,
        pattern=_REFERENCE_PATTERN,
        description="当前用户下单幂等键",
    )

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        return value.strip()


class OrderCloseSchema(BaseModel):
    version_no: int = Field(ge=1, description="当前订单版本号")


class OrderOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    user_id: int
    plan_id: int
    idempotency_key: str
    plan_snapshot: dict[str, Any]
    amount_minor: int
    currency: str
    status: OrderStatus
    expires_at: datetime
    paid_at: datetime | None = None
    closed_at: datetime | None = None
    paid_amount_minor: int
    refunded_amount_minor: int
    version_no: int
    created_time: datetime
    updated_time: datetime
