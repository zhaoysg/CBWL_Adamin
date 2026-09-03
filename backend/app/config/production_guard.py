from __future__ import annotations

from urllib.parse import urlsplit

from app.common.enums import EnvironmentEnum
from app.config.portal_auth import portal_auth_settings
from app.config.setting import settings


class UnsafeProductionConfiguration(RuntimeError):
    """Raised when production starts with development or unsafe settings."""


def validate_production_settings() -> None:
    """Fail closed before connecting to MySQL or Redis in production."""

    if settings.ENVIRONMENT != EnvironmentEnum.PROD:
        return

    errors: list[str] = []
    if len(settings.SECRET_KEY) < 32 or "dev-secret" in settings.SECRET_KEY:
        errors.append("SECRET_KEY 必须是至少 32 位的独立随机值")
    if not settings.PROD_CORS_ORIGINS.strip():
        errors.append("必须配置 PROD_CORS_ORIGINS")
    if not settings.ALLOWED_HOSTS or any(
        host == "*" for host in settings.ALLOWED_HOSTS
    ):
        errors.append("ALLOWED_HOSTS 必须使用明确域名，禁止通配符 *")
    if any(
        "fastapiadmin.com" in host for host in settings.ALLOWED_HOSTS
    ):
        errors.append("ALLOWED_HOSTS 仍包含上游 FastApiAdmin 示例域名")

    if settings.DATABASE_TYPE != "mysql":
        errors.append(
            "生产运行只允许 DATABASE_TYPE=mysql；SQLite 仅限自动化测试"
        )
    if settings.DATABASE_HOST.strip().lower() in {
        "",
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        errors.append(
            "生产 MySQL 必须使用明确的远程或容器服务主机，禁止本机地址"
        )
    if not settings.DATABASE_USER.strip():
        errors.append("生产 MySQL 必须配置 DATABASE_USER")
    if not settings.DATABASE_PASSWORD:
        errors.append("生产 MySQL 必须配置 DATABASE_PASSWORD")
    if not settings.DATABASE_NAME.strip():
        errors.append("生产 MySQL 必须配置 DATABASE_NAME")

    if (
        settings.ACCESS_TOKEN_EXPIRE_SECONDS <= 0
        or settings.ACCESS_TOKEN_EXPIRE_SECONDS > 30 * 60
    ):
        errors.append("生产 Access Token 有效期必须在 1 至 1800 秒之间")
    if (
        settings.REFRESH_TOKEN_EXPIRE_SECONDS
        <= settings.ACCESS_TOKEN_EXPIRE_SECONDS
    ):
        errors.append("Refresh Token 有效期必须长于 Access Token")
    if settings.REFRESH_TOKEN_EXPIRE_SECONDS > 30 * 24 * 60 * 60:
        errors.append("Refresh Token 有效期不得超过 30 天")

    global_origins = {
        _canonical_origin(origin) for origin in settings.ALLOW_ORIGINS
    }
    portal_origins = set(portal_auth_settings.allowed_origins)
    if not portal_origins:
        errors.append("必须配置 PORTAL_ALLOWED_ORIGINS")
    if any(
        urlsplit(origin).scheme != "https"
        for origin in portal_origins
    ):
        errors.append("PORTAL_ALLOWED_ORIGINS 生产环境只允许 HTTPS Origin")
    if not portal_origins.issubset(global_origins):
        errors.append(
            "PORTAL_ALLOWED_ORIGINS 必须包含在 PROD_CORS_ORIGINS 中"
        )
    if not settings.ALLOW_CREDENTIALS:
        errors.append("Portal Refresh Cookie 需要 ALLOW_CREDENTIALS=True")
    if not portal_auth_settings.REFRESH_COOKIE_SECURE:
        errors.append("生产 Portal Refresh Cookie 必须启用 Secure")

    expected_cookie_path = (
        f"{settings.ROOT_PATH.rstrip('/')}/portal/auth"
        or "/portal/auth"
    )
    if portal_auth_settings.REFRESH_COOKIE_PATH != expected_cookie_path:
        errors.append(
            f"生产 Portal Refresh Cookie Path 必须为 {expected_cookie_path}"
        )
    if not portal_auth_settings.RATE_LIMIT_ENABLE:
        errors.append("生产 Portal 登录与验证码必须启用 Redis 限流")
    if portal_auth_settings.ALLOW_SUPERUSER_LOGIN:
        errors.append("生产 H5 禁止超级管理员账号登录")
    if "H5" not in portal_auth_settings.allowed_login_types:
        errors.append("PORTAL_ALLOWED_LOGIN_TYPES 必须包含 H5")

    identity_mode = portal_auth_settings.IDENTITY_MODE
    entitlement_mode = portal_auth_settings.ENTITLEMENT_MODE
    if identity_mode == "legacy" and entitlement_mode == "customer":
        errors.append(
            "PORTAL_ENTITLEMENT_MODE=customer 不能与 legacy 身份模式组合"
        )
    if identity_mode == "customer" and entitlement_mode != "customer":
        errors.append(
            "PORTAL_IDENTITY_MODE=customer 时权益读取也必须使用 customer"
        )

    if errors:
        raise UnsafeProductionConfiguration("；".join(errors))


def _canonical_origin(raw: str) -> str:
    parsed = urlsplit(raw.strip())
    host = (parsed.hostname or "").lower()
    if not host:
        return raw.strip().rstrip("/").lower()
    port = parsed.port
    default_port = (parsed.scheme == "https" and port == 443) or (
        parsed.scheme == "http" and port == 80
    )
    port_suffix = "" if port is None or default_port else f":{port}"
    return f"{parsed.scheme.lower()}://{host}{port_suffix}"
