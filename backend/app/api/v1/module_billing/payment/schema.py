from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.v1.module_billing.enums import (
    BillingProvider,
    OrderStatus,
    PaymentAttemptStatus,
    PaymentEventProcessingStatus,
)

_REFERENCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"
PaymentMetadataValue = str | int | bool | None


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("支付事件时间必须包含时区")
    return value.astimezone(UTC)


class PaymentAttemptCreateSchema(BaseModel):
    provider: BillingProvider
    idempotency_key: str = Field(
        min_length=8,
        max_length=128,
        pattern=_REFERENCE_PATTERN,
        description="同一订单内支付发起幂等键",
    )

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def normalize_idempotency_key(cls, value: str) -> str:
        return value.strip()


class PaymentAttemptOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attempt_no: str
    order_id: int
    provider: BillingProvider
    idempotency_key: str
    provider_transaction_id: str | None = None
    status: PaymentAttemptStatus
    amount_minor: int
    currency: str
    provider_status: str | None = None
    payment_payload: dict[str, object] | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    expires_at: datetime | None = None
    succeeded_at: datetime | None = None
    version_no: int
    created_time: datetime
    updated_time: datetime


class ConfirmedPaymentSchema(BaseModel):
    provider: BillingProvider
    provider_event_id: str = Field(min_length=6, max_length=128, pattern=_REFERENCE_PATTERN)
    event_type: str = Field(min_length=3, max_length=64, pattern=_REFERENCE_PATTERN)
    attempt_no: str = Field(min_length=6, max_length=64, pattern=_REFERENCE_PATTERN)
    provider_transaction_id: str = Field(min_length=6, max_length=128, pattern=_REFERENCE_PATTERN)
    order_no: str = Field(min_length=6, max_length=64, pattern=_REFERENCE_PATTERN)
    amount_minor: int = Field(ge=0)
    currency: Literal["CNY"] = "CNY"
    payload_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    occurred_at: datetime | None = None
    event_metadata: dict[str, PaymentMetadataValue] | None = None

    @field_validator(
        "provider_event_id",
        "event_type",
        "attempt_no",
        "provider_transaction_id",
        "order_no",
        mode="before",
    )
    @classmethod
    def normalize_reference(cls, value: str) -> str:
        return value.strip()

    @field_validator("payload_hash", mode="before")
    @classmethod
    def normalize_payload_hash(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime | None) -> datetime | None:
        return _aware_utc(value)

    @field_validator("event_metadata")
    @classmethod
    def validate_metadata(
        cls,
        value: dict[str, PaymentMetadataValue] | None,
    ) -> dict[str, PaymentMetadataValue] | None:
        if value is None:
            return None
        if len(value) > 32:
            raise ValueError("支付事件元数据不能超过 32 项")
        for key, item in value.items():
            if not key or len(key) > 64:
                raise ValueError("支付事件元数据键长度必须为 1 到 64")
            if isinstance(item, str) and len(item) > 256:
                raise ValueError("支付事件元数据字符串不能超过 256 个字符")
        return value


class PaymentProcessingResultSchema(BaseModel):
    event_id: int
    processing_status: PaymentEventProcessingStatus
    duplicate: bool = False
    reason: str | None = None
    order_id: int | None = None
    order_no: str | None = None
    order_status: OrderStatus | None = None
    subscription_id: int | None = None
    outbox_event_id: int | None = None
