from __future__ import annotations

import hmac
import json
from typing import Annotated, Any

from fastapi import Depends, status
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import RET, RedisInitKeyConfig
from app.config.portal_auth import portal_auth_settings
from app.core.base_schema import AuthSchema
from app.core.dependencies import _authenticate, db_getter, redis_getter
from app.core.exceptions import CustomException
from app.core.redis_crud import RedisCURD
from app.core.security import OptionalOAuth2Schema, decode_access_token

from .customer_auth import PortalCustomerAuthService


async def get_optional_portal_user(
    db: Annotated[AsyncSession, Depends(db_getter)],
    redis: Annotated[Redis, Depends(redis_getter)],
    token: Annotated[str | None, Depends(OptionalOAuth2Schema)],
) -> AuthSchema | None:
    if not token:
        return None
    session = await _validate_portal_access_token(
        redis=redis,
        token=token,
    )
    if _session_actor(session) == "customer":
        await PortalCustomerAuthService.validate_session(db, session)
    return await _authenticate(
        token,
        db,
        redis,
        allow_portal_session=True,
    )


async def get_current_portal_user(
    auth: Annotated[AuthSchema | None, Depends(get_optional_portal_user)],
) -> AuthSchema:
    if auth is None:
        raise CustomException(
            msg="请登录后继续",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return auth


async def _validate_portal_access_token(
    *,
    redis: Redis,
    token: str,
) -> dict[str, Any]:
    payload = decode_access_token(token=token, verify_exp=True)
    if payload.is_refresh:
        raise CustomException(
            msg="非法访问凭证",
            code=RET.INVALID_CREDENTIALS.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    redis_crud = RedisCURD(redis)
    current = await redis_crud.get(
        f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{payload.sub}"
    )
    if isinstance(current, bytes):
        current = current.decode("utf-8")
    if not isinstance(current, str) or not hmac.compare_digest(
        current,
        token,
    ):
        raise CustomException(
            msg="访问凭证已失效",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    raw = await redis_crud.get(
        f"{RedisInitKeyConfig.USER_SESSION.key}:{payload.sub}"
    )
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        raise CustomException(
            msg="会话已失效",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        session = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CustomException(
            msg="会话已失效",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        ) from exc
    if not isinstance(session, dict):
        raise CustomException(
            msg="会话已失效",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    if (
        str(session.get("login_type") or "")
        not in portal_auth_settings.allowed_login_types
    ):
        raise CustomException(
            msg="客户端会话类型不匹配",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    actor = _session_actor(session)
    mode = portal_auth_settings.IDENTITY_MODE
    if (mode == "legacy" and actor != "legacy") or (
        mode == "customer" and actor != "customer"
    ):
        raise CustomException(
            msg="客户身份模式不匹配",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return session


def _session_actor(session: dict[str, Any]) -> str:
    actor = str(session.get("actor_type") or "legacy")
    if actor not in {"legacy", "customer"}:
        raise CustomException(
            msg="客户会话类型无效",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return actor


__all__ = ["get_current_portal_user", "get_optional_portal_user"]
