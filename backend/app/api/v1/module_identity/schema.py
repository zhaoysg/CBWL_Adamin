from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from .enums import CustomerRegisterSource, IdentityProvider
from .normalization import normalize_identifier


class CustomerProvisionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: IdentityProvider
    identifier: str = Field(min_length=1, max_length=191)
    nickname: str = Field(min_length=1, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=500)
    register_source: CustomerRegisterSource = CustomerRegisterSource.H5

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str, info: ValidationInfo) -> str:
        provider = info.data.get("provider")
        if provider is not None:
            normalize_identifier(provider, value)
        return value

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("nickname cannot be blank")
        return normalized


class AdminBridgeProvisionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legacy_sys_user_id: int = Field(gt=0)
    provider: IdentityProvider = IdentityProvider.PASSWORD
    identifier: str = Field(min_length=1, max_length=191)
    display_name: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str, info: ValidationInfo) -> str:
        provider = info.data.get("provider")
        if provider is not None:
            normalize_identifier(provider, value)
        return value

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name cannot be blank")
        return normalized


class IdentityProvisionResult(BaseModel):
    subject_id: int
    actor_id: int
    realm: str
    provider: str
    identifier_normalized: str
