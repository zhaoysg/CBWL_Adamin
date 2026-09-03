from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from fastapi import BackgroundTasks, Request, status
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_system.auth.service import LoginService
from app.common.enums import RET, EnvironmentEnum, RedisInitKeyConfig
from app.config.portal_auth import _canonical_origin, portal_auth_settings
from app.config.setting import settings
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.core.redis_crud import RedisCURD
from app.core.security import CustomOAuth2PasswordRequestForm, decode_access_token
from app.utils.ip_local_util import get_client_ip

from .auth_schema import (
    PortalAuthSessionResponse,
    PortalAuthUser,
    PortalCaptchaResponse,
    PortalLoginInput,
)
from .customer_auth import PortalCustomerAuthService

_CAPTCHA_PREFIX = "portal_auth:captcha"
_RATE_LIMIT_PREFIX = "portal_auth:rate"
_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


class PortalAuthService:
    """Browser-facing authentication boundary for the independent H5 client."""

    @classmethod
    async def issue_captcha(
        cls,
        request: Request,
        redis: Redis,
    ) -> PortalCaptchaResponse:
        await cls._enforce_rate_limit(
            redis=redis,
            bucket="captcha",
            identity=get_client_ip(request) or "unknown",
            limit=portal_auth_settings.CAPTCHA_ISSUE_LIMIT,
            window_seconds=(
                portal_auth_settings.CAPTCHA_ISSUE_WINDOW_SECONDS
            ),
        )
        if not settings.CAPTCHA_ENABLE:
            return PortalCaptchaResponse(
                enable=False,
                key="disabled",
                question=None,
            )

        left = secrets.randbelow(9) + 1
        right = secrets.randbelow(9) + 1
        if secrets.randbelow(2) == 0:
            question = f"{left} + {right} = ?"
            answer = str(left + right)
        else:
            high, low = max(left, right), min(left, right)
            question = f"{high} - {low} = ?"
            answer = str(high - low)

        key = secrets.token_urlsafe(24)
        digest = cls._captcha_digest(key, answer)
        if not await RedisCURD(redis).set(
            key=f"{_CAPTCHA_PREFIX}:{key}",
            value=digest,
            expire=portal_auth_settings.CAPTCHA_TTL_SECONDS,
        ):
            raise CustomException(
                msg="安全验证服务暂不可用",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return PortalCaptchaResponse(
            enable=True,
            key=key,
            question=question,
        )

    @classmethod
    async def login(
        cls,
        *,
        request: Request,
        background_tasks: BackgroundTasks,
        redis: Redis,
        db: AsyncSession,
        data: PortalLoginInput,
    ) -> tuple[PortalAuthSessionResponse, str]:
        identity = (
            f"{get_client_ip(request) or 'unknown'}:"
            f"{data.username.casefold()}"
        )
        await cls._enforce_rate_limit(
            redis=redis,
            bucket="login",
            identity=identity,
            limit=portal_auth_settings.LOGIN_ATTEMPT_LIMIT,
            window_seconds=(
                portal_auth_settings.LOGIN_ATTEMPT_WINDOW_SECONDS
            ),
        )
        await cls._consume_captcha(
            redis=redis,
            key=data.captcha_key,
            answer=data.captcha_answer,
        )

        if portal_auth_settings.IDENTITY_MODE != "legacy":
            resolution = await PortalCustomerAuthService.resolve_login(
                db,
                username=data.username,
                password=data.password,
            )
            if resolution.outcome == "customer":
                if resolution.account is None:
                    raise RuntimeError(
                        "customer login resolved without an account"
                    )
                token = await PortalCustomerAuthService.create_token(
                    request=request,
                    redis=redis,
                    account=resolution.account,
                )
                return (
                    PortalAuthSessionResponse(
                        access_token=token.access_token,
                        token_type=token.token_type,
                        expires_in=token.expires_in,
                        user_info=PortalAuthUser(
                            id=resolution.account.customer_id,
                            username=resolution.account.username,
                            name=resolution.account.name,
                            avatar=resolution.account.avatar,
                            identity_source="customer",
                            customer_id=resolution.account.customer_id,
                            subject_id=resolution.account.subject_id,
                            legacy_user_id=(
                                resolution.account.legacy_user_id
                            ),
                        ),
                    ),
                    token.refresh_token,
                )
            if resolution.outcome == "claim_required":
                raise CustomException(
                    msg="该账号需要完成 H5 身份认领或重置密码",
                    code=status.HTTP_409_CONFLICT,
                    status_code=status.HTTP_409_CONFLICT,
                )
            if (
                resolution.outcome == "blocked"
                or portal_auth_settings.IDENTITY_MODE == "customer"
            ):
                cls._raise_invalid_credentials()

        return await cls._legacy_login(
            request=request,
            background_tasks=background_tasks,
            redis=redis,
            db=db,
            data=data,
        )

    @classmethod
    async def _legacy_login(
        cls,
        *,
        request: Request,
        background_tasks: BackgroundTasks,
        redis: Redis,
        db: AsyncSession,
        data: PortalLoginInput,
    ) -> tuple[PortalAuthSessionResponse, str]:
        login_form = CustomOAuth2PasswordRequestForm(
            grant_type="password",
            scope="",
            client_id=None,
            client_secret=None,
            username=data.username,
            password=data.password,
            captcha_key=data.captcha_key or "",
            captcha="",
            login_type="H5",
        )
        try:
            result = await LoginService.authenticate_user(
                request=request,
                background_tasks=background_tasks,
                redis=redis,
                login_form=login_form,
                db=db,
            )
        except CustomException as exc:
            if exc.msg in {"用户不存在", "账号或密码错误"}:
                cls._raise_invalid_credentials(exc)
            raise

        if (
            bool(result.user_info.get("is_superuser"))
            and not portal_auth_settings.ALLOW_SUPERUSER_LOGIN
        ):
            await LoginService.logout(
                redis=redis,
                token=result.refresh_token,
            )
            logger.warning(
                "拒绝超级管理员账号登录 H5: username={}",
                data.username,
            )
            raise CustomException(
                msg="管理员账号不能用于 H5 登录",
                code=RET.FORBIDDEN.code,
                status_code=status.HTTP_403_FORBIDDEN,
            )

        legacy_user_id = int(result.user_info.get("id") or 0)
        user = PortalAuthUser.model_validate(
            {
                "id": legacy_user_id,
                "username": result.user_info.get("username"),
                "name": result.user_info.get("name"),
                "avatar": result.user_info.get("avatar"),
                "identity_source": "legacy",
                "legacy_user_id": legacy_user_id,
            }
        )
        return (
            PortalAuthSessionResponse(
                access_token=result.access_token,
                token_type=result.token_type,
                expires_in=result.expires_in,
                user_info=user,
            ),
            result.refresh_token,
        )

    @classmethod
    async def refresh(
        cls,
        *,
        db: AsyncSession,
        redis: Redis,
        refresh_token: str,
    ) -> tuple[PortalAuthSessionResponse, str]:
        session = await cls._assert_current_refresh_token(
            redis,
            refresh_token,
        )
        if cls._session_actor(session) == "customer":
            await PortalCustomerAuthService.validate_session(db, session)

        result = await LoginService.refresh_token(
            db=db,
            redis=redis,
            refresh_token=refresh_token,
        )
        user = await cls._user_from_access_token(
            redis,
            result.access_token,
        )
        return (
            PortalAuthSessionResponse(
                access_token=result.access_token,
                token_type=result.token_type,
                expires_in=result.expires_in,
                user_info=user,
            ),
            result.refresh_token,
        )

    @classmethod
    async def logout(cls, *, redis: Redis, refresh_token: str) -> None:
        await cls._assert_current_refresh_token(redis, refresh_token)
        await LoginService.logout(redis=redis, token=refresh_token)

    @staticmethod
    def validate_browser_origin(request: Request) -> None:
        if settings.ENVIRONMENT != EnvironmentEnum.PROD:
            return
        raw_origin = request.headers.get("origin", "").strip()
        if not raw_origin:
            raise CustomException(
                msg="缺少请求来源",
                code=RET.FORBIDDEN.code,
                status_code=status.HTTP_403_FORBIDDEN,
            )
        try:
            origin = _canonical_origin(raw_origin)
        except (TypeError, ValueError) as exc:
            raise CustomException(
                msg="请求来源无效",
                code=RET.FORBIDDEN.code,
                status_code=status.HTTP_403_FORBIDDEN,
            ) from exc
        if origin not in portal_auth_settings.allowed_origins:
            raise CustomException(
                msg="请求来源未授权",
                code=RET.FORBIDDEN.code,
                status_code=status.HTTP_403_FORBIDDEN,
            )

    @classmethod
    async def _consume_captcha(
        cls,
        *,
        redis: Redis,
        key: str | None,
        answer: str | None,
    ) -> None:
        if not settings.CAPTCHA_ENABLE:
            return
        if not key or not answer:
            raise CustomException(
                msg="请完成安全验证",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"{_CAPTCHA_PREFIX}:{key}"
        redis_crud = RedisCURD(redis)
        expected = await redis_crud.get(cache_key)
        await redis_crud.delete(cache_key)
        if isinstance(expected, bytes):
            expected = expected.decode("utf-8")
        actual = cls._captcha_digest(key, answer)
        if not isinstance(expected, str) or not hmac.compare_digest(
            expected,
            actual,
        ):
            raise CustomException(
                msg="安全验证错误或已过期",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        legacy_key = f"{RedisInitKeyConfig.CAPTCHA_CODES.key}:{key}"
        if not await redis_crud.set(
            legacy_key,
            "verified",
            expire=settings.CAPTCHA_EXPIRE_SECONDS,
        ):
            raise CustomException(
                msg="安全验证服务暂不可用",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    @staticmethod
    def _captcha_digest(key: str, answer: str) -> str:
        return hmac.new(
            settings.SECRET_KEY.encode(),
            f"{key}:{answer}".encode(),
            hashlib.sha256,
        ).hexdigest()

    @classmethod
    async def _assert_current_refresh_token(
        cls,
        redis: Redis,
        token: str,
    ) -> dict[str, Any]:
        payload = decode_access_token(token=token, verify_exp=True)
        if not payload.is_refresh:
            raise CustomException(
                msg="非法刷新凭证",
                code=RET.INVALID_CREDENTIALS.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        redis_crud = RedisCURD(redis)
        current = await redis_crud.get(
            f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{payload.sub}"
        )
        if isinstance(current, bytes):
            current = current.decode("utf-8")
        if not isinstance(current, str) or not hmac.compare_digest(
            current,
            token,
        ):
            raise CustomException(
                msg="刷新凭证已失效",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        session = await cls._session(redis_crud, payload.sub)
        cls._assert_portal_session(session)
        return session

    @classmethod
    async def _user_from_access_token(
        cls,
        redis: Redis,
        token: str,
    ) -> PortalAuthUser:
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
        session = await cls._session(redis_crud, payload.sub)
        cls._assert_portal_session(session)
        if cls._session_actor(session) == "customer":
            return PortalCustomerAuthService.user_from_session(session)
        legacy_user_id = int(session.get("user_id") or 0)
        return PortalAuthUser(
            id=legacy_user_id,
            username=str(session.get("user_name") or ""),
            name=session.get("name"),
            avatar=session.get("avatar"),
            identity_source="legacy",
            legacy_user_id=legacy_user_id,
        )

    @staticmethod
    async def _session(
        redis_crud: RedisCURD,
        session_id: str,
    ) -> dict[str, Any]:
        raw = await redis_crud.get(
            f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}"
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
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CustomException(
                msg="会话已失效",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc
        if not isinstance(data, dict):
            raise CustomException(
                msg="会话已失效",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return data

    @classmethod
    def _assert_portal_session(cls, session: dict[str, Any]) -> None:
        if (
            str(session.get("login_type") or "")
            not in portal_auth_settings.allowed_login_types
        ):
            raise CustomException(
                msg="客户端会话类型不匹配",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        actor = cls._session_actor(session)
        mode = portal_auth_settings.IDENTITY_MODE
        if (mode == "legacy" and actor != "legacy") or (
            mode == "customer" and actor != "customer"
        ):
            raise CustomException(
                msg="客户身份模式不匹配",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

    @staticmethod
    def _session_actor(session: dict[str, Any]) -> str:
        actor = str(session.get("actor_type") or "legacy")
        if actor not in {"legacy", "customer"}:
            raise CustomException(
                msg="客户会话类型无效",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return actor

    @staticmethod
    def _raise_invalid_credentials(
        exc: Exception | None = None,
    ) -> None:
        error = CustomException(
            msg="账号或密码错误",
            code=RET.UNAUTHORIZED.code,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        if exc is None:
            raise error
        raise error from exc

    @staticmethod
    async def _enforce_rate_limit(
        *,
        redis: Redis,
        bucket: str,
        identity: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        if not portal_auth_settings.RATE_LIMIT_ENABLE:
            return
        digest = hashlib.sha256(
            identity.encode(),
            usedforsecurity=False,
        ).hexdigest()
        key = f"{_RATE_LIMIT_PREFIX}:{bucket}:{digest}"
        try:
            current = int(
                await redis.eval(
                    _RATE_LIMIT_SCRIPT,
                    1,
                    key,
                    window_seconds,
                )
            )
        except Exception as exc:
            logger.exception(
                "Portal 登录限流服务异常: bucket={}",
                bucket,
            )
            raise CustomException(
                msg="登录保护服务暂不可用",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc
        if current > limit:
            raise CustomException(
                msg="请求过于频繁，请稍后再试",
                code=status.HTTP_429_TOO_MANY_REQUESTS,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )
