from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config.path_conf import ENV_DIR

PortalIdentityMode = Literal["legacy", "dual", "customer"]
PortalEntitlementMode = Literal["legacy", "dual", "customer"]


class PortalAuthSettings(BaseSettings):
    """H5 Portal authentication and entitlement migration settings."""

    model_config = SettingsConfigDict(
        env_file=ENV_DIR / f".env.{os.getenv('ENVIRONMENT')}",
        env_file_encoding="utf-8",
        env_prefix="PORTAL_",
        extra="ignore",
        case_sensitive=True,
    )

    ALLOWED_ORIGINS: str = ""
    ALLOWED_LOGIN_TYPES: str = "H5,移动端"
    ALLOW_SUPERUSER_LOGIN: bool = False
    IDENTITY_MODE: PortalIdentityMode = "legacy"
    ENTITLEMENT_MODE: PortalEntitlementMode = "legacy"

    REFRESH_COOKIE_NAME: str = "cbwl_portal_refresh"
    REFRESH_COOKIE_PATH: str = "/"
    REFRESH_COOKIE_SECURE: bool = False
    REFRESH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    RATE_LIMIT_ENABLE: bool = False
    CAPTCHA_ISSUE_LIMIT: int = Field(default=20, ge=1, le=1000)
    CAPTCHA_ISSUE_WINDOW_SECONDS: int = Field(default=60, ge=10, le=3600)
    LOGIN_ATTEMPT_LIMIT: int = Field(default=5, ge=1, le=100)
    LOGIN_ATTEMPT_WINDOW_SECONDS: int = Field(default=300, ge=30, le=86400)
    CAPTCHA_TTL_SECONDS: int = Field(default=120, ge=30, le=600)

    @field_validator("ALLOWED_ORIGINS")
    @classmethod
    def validate_allowed_origins(cls, value: str) -> str:
        for raw in value.split(","):
            origin = raw.strip()
            if not origin:
                continue
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Portal Origin 无效: {origin}")
            if (
                parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    f"Portal Origin 只能包含协议、主机和端口: {origin}"
                )
        return value

    @field_validator("REFRESH_COOKIE_NAME")
    @classmethod
    def validate_cookie_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(
            char in normalized for char in " ;,=\t\r\n"
        ):
            raise ValueError("Portal Refresh Cookie 名称无效")
        return normalized

    @field_validator("REFRESH_COOKIE_PATH")
    @classmethod
    def validate_cookie_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.startswith("/") or any(
            char in normalized for char in ";\r\n"
        ):
            raise ValueError("Portal Refresh Cookie Path 无效")
        return normalized

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        return tuple(
            _canonical_origin(item)
            for item in self.ALLOWED_ORIGINS.split(",")
            if item.strip()
        )

    @property
    def allowed_login_types(self) -> frozenset[str]:
        return frozenset(
            item.strip()
            for item in self.ALLOWED_LOGIN_TYPES.split(",")
            if item.strip()
        )


def _canonical_origin(raw: str) -> str:
    parsed = urlsplit(raw.strip())
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("Origin 缺少主机名")
    port = parsed.port
    default_port = (parsed.scheme == "https" and port == 443) or (
        parsed.scheme == "http" and port == 80
    )
    port_suffix = "" if port is None or default_port else f":{port}"
    return f"{parsed.scheme.lower()}://{host}{port_suffix}"


@lru_cache(maxsize=1)
def get_portal_auth_settings() -> PortalAuthSettings:
    return PortalAuthSettings()


portal_auth_settings = get_portal_auth_settings()

__all__ = [
    "PortalAuthSettings",
    "PortalEntitlementMode",
    "PortalIdentityMode",
    "_canonical_origin",
    "portal_auth_settings",
]
