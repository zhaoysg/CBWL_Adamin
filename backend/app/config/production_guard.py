from __future__ import annotations

from app.common.enums import EnvironmentEnum
from app.config.setting import settings


class UnsafeProductionConfiguration(RuntimeError):
    """Raised when production starts with development or upstream example settings."""


def validate_production_settings() -> None:
    """Fail closed before connecting to the database or Redis in production."""

    if settings.ENVIRONMENT != EnvironmentEnum.PROD:
        return

    errors: list[str] = []
    if len(settings.SECRET_KEY) < 32 or "dev-secret" in settings.SECRET_KEY:
        errors.append("SECRET_KEY 必须是至少 32 位的独立随机值")
    if not settings.PROD_CORS_ORIGINS.strip():
        errors.append("必须配置 PROD_CORS_ORIGINS")
    if not settings.ALLOWED_HOSTS or any(host == "*" for host in settings.ALLOWED_HOSTS):
        errors.append("ALLOWED_HOSTS 必须使用明确域名，禁止通配符 *")
    if any("fastapiadmin.com" in host for host in settings.ALLOWED_HOSTS):
        errors.append("ALLOWED_HOSTS 仍包含上游 FastApiAdmin 示例域名")

    if errors:
        raise UnsafeProductionConfiguration("；".join(errors))
