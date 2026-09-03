from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PortalAuthModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PortalCaptchaResponse(PortalAuthModel):
    enable: bool
    key: str = Field(min_length=1, max_length=128)
    question: str | None = Field(default=None, max_length=64)


class PortalLoginInput(PortalAuthModel):
    username: str = Field(min_length=2, max_length=191)
    password: str = Field(min_length=6, max_length=128)
    captcha_key: str | None = Field(default=None, min_length=1, max_length=128)
    captcha_answer: str | None = Field(default=None, min_length=1, max_length=8)

    @field_validator("captcha_answer")
    @classmethod
    def validate_captcha_answer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isdecimal():
            raise ValueError("验证码答案只能包含数字")
        return value


class PortalAuthUser(PortalAuthModel):
    id: int = Field(gt=0, description="H5 当前公开主体ID")
    username: str = Field(min_length=1, max_length=191)
    name: str | None = Field(default=None, max_length=128)
    avatar: str | None = Field(default=None, max_length=1000)
    identity_source: Literal["legacy", "customer"] = "legacy"
    customer_id: int | None = Field(default=None, gt=0)
    subject_id: int | None = Field(default=None, gt=0)
    legacy_user_id: int | None = Field(default=None, gt=0)


class PortalAuthSessionResponse(PortalAuthModel):
    access_token: str = Field(min_length=1)
    token_type: str = Field(default="Bearer", min_length=1, max_length=32)
    expires_in: int = Field(gt=0)
    user_info: PortalAuthUser
