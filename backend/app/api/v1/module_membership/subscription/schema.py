from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema
from app.core.validator import DateTimeStr

SubscriptionSource = Literal["manual", "payment", "migration", "promotion"]
SubscriptionEffectiveStatus = Literal["upcoming", "active", "expired", "revoked"]


def ensure_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("订阅时间必须包含时区，例如 2026-08-23T12:00:00+08:00")
    return value.astimezone(UTC)


class MemberSubscriptionGrantSchema(BaseModel):
    user_id: int = Field(ge=1, description="用户ID")
    plan_id: int = Field(ge=1, description="会员套餐ID")
    source_ref: str = Field(
        min_length=6,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
        description="人工授权幂等键",
    )
    starts_at: datetime | None = Field(default=None, description="生效时间；留空表示立即生效")
    expires_at: datetime | None = Field(default=None, description="到期时间；留空按套餐有效天数计算")
    grant_reason: str = Field(min_length=2, max_length=500, description="授权原因")
    description: str | None = Field(default=None, max_length=2000, description="内部备注")

    @field_validator("source_ref", mode="before")
    @classmethod
    def normalize_source_ref(cls, value: str) -> str:
        return value.strip()

    @field_validator("grant_reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("starts_at", "expires_at")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def validate_window(self):
        if self.starts_at is not None and self.expires_at is not None and self.expires_at <= self.starts_at:
            raise ValueError("到期时间必须晚于生效时间")
        return self


class MemberSubscriptionRevokeSchema(BaseModel):
    version_no: int = Field(ge=1, description="当前版本号")
    reason: str = Field(min_length=2, max_length=500, description="撤销原因")

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return value.strip()


class MemberSubscriptionUserOptionSchema(BaseModel):
    id: int
    username: str
    name: str
    mobile: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MemberSubscriptionOutSchema(BaseSchema, UserBySchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    user_name: str
    mobile: str | None = None
    plan_id: int
    plan_code: str
    plan_name: str
    rank: int
    source: SubscriptionSource
    source_ref: str
    status: int
    effective_status: SubscriptionEffectiveStatus
    starts_at: DateTimeStr
    expires_at: DateTimeStr
    revoked_at: DateTimeStr | None = None
    grant_reason: str
    revoke_reason: str | None = None
    version_no: int
    description: str | None = None


class MemberSubscriptionQueryParam(BaseQueryParam, UserByQueryParam):
    keyword: str | None = Field(default=None, max_length=128, description="用户、套餐或来源单号关键字")
    user_id: int | None = Field(default=None, ge=1, description="用户ID")
    plan_id: int | None = Field(default=None, ge=1, description="套餐ID")
    source: SubscriptionSource | None = Field(default=None, description="订阅来源")
    source_ref: str | None = Field(default=None, max_length=128, description="来源幂等键")
    status: int | None = Field(default=None, ge=0, le=1, description="持久化状态")
    effective_status: SubscriptionEffectiveStatus | None = Field(default=None, description="实时有效状态")
    starts_at: list[datetime] | None = Field(default=None, min_length=2, max_length=2, description="生效时间范围")
    expires_at: list[datetime] | None = Field(default=None, min_length=2, max_length=2, description="到期时间范围")

    @field_validator("keyword", "source_ref", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("starts_at", "expires_at")
    @classmethod
    def normalize_ranges(cls, value: list[datetime] | None) -> list[datetime] | None:
        if value is None:
            return None
        normalized = [ensure_aware_utc(item) for item in value]
        if normalized[1] <= normalized[0]:
            raise ValueError("时间范围结束值必须晚于开始值")
        return [item for item in normalized if item is not None]
