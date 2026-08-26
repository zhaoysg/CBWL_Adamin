from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, status

from app.common.enums import EnvironmentEnum
from app.config.setting import settings

PortalDataSource = Literal["demo", "database"]


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class PortalRuntimeState:
    environment: str
    data_source: PortalDataSource
    allow_demo_in_prod: bool
    allowed: bool
    production_ready: bool
    reason: str | None = None


def get_portal_runtime_state() -> PortalRuntimeState:
    """Return the fail-closed runtime state for the M1 portal provider.

    M1 only implements the deterministic demo provider. It must never silently
    serve demo/member data when a production deployment expects database data.
    """

    raw_source = os.getenv("PORTAL_DATA_SOURCE", "demo").strip().lower()
    if raw_source not in {"demo", "database"}:
        raw_source = "demo"
        invalid_source = True
    else:
        invalid_source = False

    environment = os.getenv("ENVIRONMENT") or getattr(settings.ENVIRONMENT, "value", str(settings.ENVIRONMENT))
    environment = environment.strip().lower()
    allow_demo_in_prod = _parse_bool(os.getenv("PORTAL_ALLOW_DEMO_IN_PROD"), default=False)
    is_prod = environment == EnvironmentEnum.PROD.value

    if invalid_source:
        return PortalRuntimeState(
            environment=environment,
            data_source="demo",
            allow_demo_in_prod=allow_demo_in_prod,
            allowed=False,
            production_ready=False,
            reason="PORTAL_DATA_SOURCE 配置无效",
        )

    data_source: PortalDataSource = raw_source  # type: ignore[assignment]
    if data_source == "database":
        return PortalRuntimeState(
            environment=environment,
            data_source=data_source,
            allow_demo_in_prod=allow_demo_in_prod,
            allowed=False,
            production_ready=False,
            reason="M1 尚未提供数据库 Portal Provider",
        )

    if is_prod and not allow_demo_in_prod:
        return PortalRuntimeState(
            environment=environment,
            data_source=data_source,
            allow_demo_in_prod=allow_demo_in_prod,
            allowed=False,
            production_ready=False,
            reason="生产环境禁止启用演示数据",
        )

    return PortalRuntimeState(
        environment=environment,
        data_source=data_source,
        allow_demo_in_prod=allow_demo_in_prod,
        allowed=True,
        production_ready=False,
        reason="当前运行确定性演示数据，不能作为生产数据源",
    )


def require_portal_runtime() -> PortalRuntimeState:
    state = get_portal_runtime_state()
    if not state.allowed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=state.reason or "Portal 服务当前不可用",
            headers={"Retry-After": "60"},
        )
    return state
