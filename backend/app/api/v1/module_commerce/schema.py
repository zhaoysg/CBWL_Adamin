from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OrderStatus = Literal["pending", "paid", "cancelled", "expired", "refunded"]
PaymentProvider = Literal["wechat", "alipay", "manual"]
PaymentAttemptStatus = Literal["created", "processing", "succeeded", "failed", "closed"]
PaymentEventType = Literal["payment_succeeded", "payment_failed", "payment_closed"]
PaymentProcessingStatus = Literal["accepted", "ignored", "rejected"]

_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3,8}$")


def _normalize_idempotency_key(value: str) -> str:
    normalized = value.strip()
    if not _IDEMPOTENCY_RE.fullmatch(normalized):
        raise ValueError("幂等键必须为8至128位字母、数字或 . _ : -")
    return normalized


def _normalize_currency(value: str) -> str:
    normalized = value.strip().upper()
    if not _CURRENCY_RE.fullmatch(normalized):
        raise ValueError("币种代码必须为3至8位大写字母")
    return normalized


class CommerceOrderCreateSchema(BaseModel):
    """A client intent; monetary values are deliberately absent."""

    plan_id: int = Field(..., gt=0, description="会员套餐ID")
    idempotency_key: str = Field(..., min_length=8, max_length=128, description="全局幂等键")

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        return _normalize_idempotency_key(value)


class CommerceOrderCancelSchema(BaseModel):
    version_no: int = Field(..., ge=1, description="订单乐观锁版本")
    reason: str = Field(..., min_length=2, max_length=500, description="取消原因")

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("取消原因至少2个字符")
        return normalized


class PaymentAttemptCreateSchema(BaseModel):
    provider: PaymentProvider
    idempotency_key: str = Field(..., min_length=8, max_length=128, description="订单内幂等键")

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        return _normalize_idempotency_key(value)


class VerifiedPaymentEventSchema(BaseModel):
    """Normalized callback emitted only after provider signature verification."""

    provider: PaymentProvider
    provider_event_id: str = Field(..., min_length=1, max_length=128)
    merchant_request_no: str = Field(..., min_length=1, max_length=64)
    provider_transaction_id: str | None = Field(default=None, min_length=1, max_length=128)
    event_type: PaymentEventType
    amount: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    currency: str = Field(..., min_length=3, max_length=8)
    signature_verified: Literal[True] = True
    payload_digest: str = Field(..., min_length=64, max_length=64)
    occurred_at: datetime
    provider_reason_code: str | None = Field(default=None, max_length=128)

    @field_validator("provider_event_id", "merchant_request_no")
    @classmethod
    def normalize_identifiers(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("支付事件标识不能为空")
        return normalized

    @field_validator("provider_transaction_id", "provider_reason_code")
    @classmethod
    def normalize_optional_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _normalize_currency(value)

    @field_validator("payload_digest")
    @classmethod
    def validate_payload_digest(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("payload_digest 必须是64位小写SHA-256十六进制摘要")
        return normalized

    @model_validator(mode="after")
    def validate_success_transaction(self) -> VerifiedPaymentEventSchema:
        if self.event_type == "payment_succeeded" and not self.provider_transaction_id:
            raise ValueError("支付成功事件必须包含提供方交易号")
        return self


class CommerceOrderOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    order_no: str
    legacy_user_id: int | None
    customer_id: int | None
    plan_id: int
    plan_code_snapshot: str
    plan_name_snapshot: str
    duration_days_snapshot: int
    unit_price: Decimal
    total_amount: Decimal
    currency: str
    status: OrderStatus
    idempotency_key: str
    payment_expires_at: datetime
    paid_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    version_no: int
    created_time: datetime
    updated_time: datetime


class PaymentAttemptOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    attempt_no: str
    order_id: int
    provider: PaymentProvider
    merchant_request_no: str
    provider_transaction_id: str | None
    idempotency_key: str
    amount: Decimal
    currency: str
    status: PaymentAttemptStatus
    expires_at: datetime
    succeeded_at: datetime | None
    failed_at: datetime | None
    failure_code: str | None
    version_no: int
    created_time: datetime
    updated_time: datetime


class PaymentEventOutSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: str
    order_id: int
    payment_attempt_id: int
    provider: PaymentProvider
    provider_event_id: str
    merchant_request_no: str
    provider_transaction_id: str | None
    event_type: PaymentEventType
    amount: Decimal
    currency: str
    signature_verified: bool
    payload_digest: str
    processing_status: PaymentProcessingStatus
    reason_code: str | None
    occurred_at: datetime
    processed_at: datetime
    note: str | None
    created_time: datetime
    updated_time: datetime


class PaymentEventResultSchema(BaseModel):
    event: PaymentEventOutSchema
    order: CommerceOrderOutSchema
    payment_attempt: PaymentAttemptOutSchema
