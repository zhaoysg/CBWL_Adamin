from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OrderStatus = Literal["pending", "paid", "cancelled", "closed", "refunded"]
PaymentProvider = Literal["wechat", "alipay", "manual"]
PaymentChannel = Literal["h5", "jsapi", "app", "admin", "bank_transfer"]
PaymentAttemptStatus = Literal["pending", "succeeded", "failed", "closed", "refunded"]
PaymentEventType = Literal[
    "payment_succeeded",
    "payment_failed",
    "payment_closed",
    "refund_succeeded",
    "unknown",
]
PaymentEventStatus = Literal["received", "processed", "ignored", "failed"]

RequestKey = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
        description="客户端单次操作幂等键；服务端按交易主体做摘要",
    ),
]


class _CommandSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MembershipOrderCreateSchema(_CommandSchema):
    plan_id: int = Field(gt=0, description="会员套餐ID")
    request_key: RequestKey
    payment_window_seconds: int = Field(
        default=900,
        ge=60,
        le=86400,
        description="支付窗口秒数",
    )
    description: str | None = Field(default=None, max_length=500, description="内部备注")


class OrderCancelSchema(_CommandSchema):
    version_no: int = Field(ge=1, description="订单乐观锁版本")
    reason: str = Field(min_length=1, max_length=500, description="取消原因")


class PaymentAttemptCreateSchema(_CommandSchema):
    order_no: str = Field(min_length=3, max_length=40, description="订单编号")
    provider: PaymentProvider
    channel: PaymentChannel
    request_key: RequestKey

    @field_validator("order_no")
    @classmethod
    def normalize_order_no(cls, value: str) -> str:
        return value.upper()


class ProviderEventRegisterSchema(_CommandSchema):
    payment_no: str = Field(min_length=3, max_length=40, description="支付编号")
    provider: PaymentProvider
    provider_event_id: str = Field(min_length=1, max_length=191, description="提供方事件ID")
    event_type: PaymentEventType
    payload_digest: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="原始回调载荷SHA-256摘要",
    )

    @field_validator("payment_no")
    @classmethod
    def normalize_payment_no(cls, value: str) -> str:
        return value.upper()

    @field_validator("payload_digest")
    @classmethod
    def normalize_payload_digest(cls, value: str) -> str:
        return value.lower()


class CommerceOrderOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_no: str
    legacy_user_id: int | None
    customer_id: int | None
    product_type: str
    plan_id: int
    plan_code_snapshot: str
    plan_name_snapshot: str
    plan_level_no_snapshot: int
    duration_days_snapshot: int
    benefits_snapshot: list[str]
    amount: Decimal
    currency: str
    status: OrderStatus
    payment_window_seconds: int
    expires_at: datetime
    paid_at: datetime | None
    cancelled_at: datetime | None
    closed_at: datetime | None
    refunded_at: datetime | None
    cancel_reason: str | None
    version_no: int
    description: str | None
    created_time: datetime
    updated_time: datetime


class PaymentAttemptOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_no: str
    order_id: int
    order_no: str
    legacy_user_id: int | None
    customer_id: int | None
    provider: PaymentProvider
    channel: PaymentChannel
    provider_trade_no: str | None
    amount: Decimal
    currency: str
    status: PaymentAttemptStatus
    initiated_at: datetime
    succeeded_at: datetime | None
    failed_at: datetime | None
    closed_at: datetime | None
    refunded_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    version_no: int
    created_time: datetime
    updated_time: datetime


class PaymentEventOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_id: int
    payment_no: str
    provider: PaymentProvider
    provider_event_id: str
    event_type: PaymentEventType
    payload_digest: str
    status: PaymentEventStatus
    received_at: datetime
    processed_at: datetime | None
    processing_code: str | None
    processing_message: str | None
    version_no: int
    created_time: datetime
    updated_time: datetime


__all__ = [
    "CommerceOrderOutSchema",
    "MembershipOrderCreateSchema",
    "OrderCancelSchema",
    "OrderStatus",
    "PaymentAttemptCreateSchema",
    "PaymentAttemptOutSchema",
    "PaymentAttemptStatus",
    "PaymentChannel",
    "PaymentEventOutSchema",
    "PaymentEventStatus",
    "PaymentEventType",
    "PaymentProvider",
    "ProviderEventRegisterSchema",
]
