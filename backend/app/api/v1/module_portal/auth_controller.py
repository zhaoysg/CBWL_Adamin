from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Request, Response, status
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.portal_auth import portal_auth_settings
from app.core.dependencies import db_getter, redis_getter
from app.core.exceptions import CustomException

from .auth_schema import PortalAuthSessionResponse, PortalCaptchaResponse, PortalLoginInput
from .auth_service import PortalAuthService

PortalAuthRouter = APIRouter(prefix="/auth", tags=["财不外露-H5认证"])


def _apply_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Origin, Cookie"
    response.headers["X-Content-Type-Options"] = "nosniff"


def _write_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=portal_auth_settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=None,
        httponly=True,
        secure=portal_auth_settings.REFRESH_COOKIE_SECURE,
        samesite=portal_auth_settings.REFRESH_COOKIE_SAMESITE,
        path=portal_auth_settings.REFRESH_COOKIE_PATH,
    )


def _delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=portal_auth_settings.REFRESH_COOKIE_NAME,
        path=portal_auth_settings.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=portal_auth_settings.REFRESH_COOKIE_SECURE,
        samesite=portal_auth_settings.REFRESH_COOKIE_SAMESITE,
    )


@PortalAuthRouter.get("/captcha", summary="获取 H5 登录安全验证")
async def get_portal_captcha(
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(redis_getter)],
) -> PortalCaptchaResponse:
    _apply_no_store(response)
    return await PortalAuthService.issue_captcha(request, redis)


@PortalAuthRouter.post("/login", summary="H5 用户登录")
async def portal_login(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    redis: Annotated[Redis, Depends(redis_getter)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: PortalLoginInput,
) -> PortalAuthSessionResponse:
    PortalAuthService.validate_browser_origin(request)
    _apply_no_store(response)
    session, refresh_token = await PortalAuthService.login(
        request=request,
        background_tasks=background_tasks,
        redis=redis,
        db=db,
        data=data,
    )
    _write_refresh_cookie(response, refresh_token)
    return session


@PortalAuthRouter.post("/refresh", summary="刷新 H5 用户会话")
async def portal_refresh(
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(redis_getter)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    refresh_token: Annotated[str | None, Cookie(alias=portal_auth_settings.REFRESH_COOKIE_NAME)] = None,
) -> PortalAuthSessionResponse:
    PortalAuthService.validate_browser_origin(request)
    _apply_no_store(response)
    if not refresh_token:
        raise CustomException(msg="会话已过期，请重新登录", status_code=status.HTTP_401_UNAUTHORIZED)
    session, next_refresh_token = await PortalAuthService.refresh(
        db=db,
        redis=redis,
        refresh_token=refresh_token,
    )
    _write_refresh_cookie(response, next_refresh_token)
    return session


@PortalAuthRouter.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="退出 H5 用户会话")
async def portal_logout(
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(redis_getter)],
    refresh_token: Annotated[str | None, Cookie(alias=portal_auth_settings.REFRESH_COOKIE_NAME)] = None,
) -> None:
    PortalAuthService.validate_browser_origin(request)
    _apply_no_store(response)
    try:
        if refresh_token:
            await PortalAuthService.logout(redis=redis, refresh_token=refresh_token)
    except CustomException:
        # Logout is intentionally idempotent: the browser cookie is cleared even if the server session expired.
        pass
    finally:
        _delete_refresh_cookie(response)
