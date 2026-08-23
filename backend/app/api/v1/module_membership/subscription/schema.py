from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.base_schema import BaseSchema, UserBySchema
from app.core.validator import DateTimeStr

SubscriptionStatus = Literal["active", "revoked"]
SubscriptionSource = Literal["manual", "order", "migration"]


def _require_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("时间必须包含时区")
    return value.astimezone(UTC) if value is not None else None


class MemberSubscriptionGrantSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: int = Field(ge=1, description="用户ID")
    plan_id: int = Field(ge=1, description="套餐ID")
    external_ref: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    source: SubscriptionSource = Field(default="manual")
    starts_at: datetime | None = Field(default=None)
    expires_at: datetime | None = Field(default=None)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("starts_at", "expires_at")
    @classmethod
    def validate_aware_time(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_period(self):
        if self.starts_at is not None and self.expires_at is not None and self.expires_at <= self.starts_at:
            raise ValueError("失效时间必须晚于生效时间")
        return self


class MemberSubscriptionRevokeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version_no: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=500)


class MemberSubscriptionOutSchema(BaseSchema, UserBySchema):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_name: str
    plan_id: int
    plan_name: str
    plan_code: str
    external_ref: str
    source: SubscriptionSource
    status: SubscriptionStatus
    starts_at: DateTimeStr
    expires_at: DateTimeStr
    revoked_at: DateTimeStr | None
    revoke_reason: str | None
    version_no: int
    description: str | None
    effective: bool = False


class MemberSubscriptionQueryParam(BaseModel):
    user_id: int | None = Field(default=None, ge=1)
    plan_id: int | None = Field(default=None, ge=1)
    external_ref: str | None = Field(default=None, max_length=128)
    source: SubscriptionSource | None = None
    status: SubscriptionStatus | None = None
    effective_only: bool = False
