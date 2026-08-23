from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.dependencies import _authenticate, db_getter, redis_getter
from app.core.security import CustomOAuth2PasswordBearer

OptionalOAuth2Schema = CustomOAuth2PasswordBearer(
    token_url="system/auth/login",
    description="可选认证",
    auto_error=False,
)


async def get_optional_current_user(
    db: Annotated[AsyncSession, Depends(db_getter)],
    redis: Annotated[Redis, Depends(redis_getter)],
    token: Annotated[str | None, Depends(OptionalOAuth2Schema)],
) -> AuthSchema | None:
    if token is None:
        return None
    return await _authenticate(token, db, redis)
