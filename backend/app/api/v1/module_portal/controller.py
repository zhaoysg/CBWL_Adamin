from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.dependencies import db_getter

from .auth_dependency import get_optional_portal_user
from .database_service import DatabasePortalService
from .runtime import PortalRuntimeState, get_portal_runtime_state, require_portal_runtime
from .schema import (
    AcademyResponse,
    ContentDetailResponse,
    CourseDetailResponse,
    HomeResponse,
    MemberCenterResponse,
    PortalHealth,
    ProfileResponse,
)
from .service import PortalService

PortalRouter = APIRouter()


def _apply_no_store_headers(response: Response, state: PortalRuntimeState) -> None:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Vary"] = "Authorization, Cookie"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Portal-Data-Source"] = state.data_source


def _prepare_response(response: Response) -> PortalRuntimeState:
    state = require_portal_runtime()
    _apply_no_store_headers(response, state)
    return state


@PortalRouter.get("/health", summary="用户端服务健康检查")
async def portal_health(response: Response) -> PortalHealth:
    state = get_portal_runtime_state()
    _apply_no_store_headers(response, state)
    return PortalHealth(
        status="ok" if state.allowed else "degraded",
        environment=state.environment,
        data_source=state.data_source,
        production_ready=state.production_ready,
        reason=state.reason,
    )


@PortalRouter.get("/home", summary="获取首页聚合数据")
async def get_home(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema | None, Depends(get_optional_portal_user)],
) -> HomeResponse:
    state = _prepare_response(response)
    if state.data_source == "demo":
        return PortalService.home()
    return await DatabasePortalService(db, auth).home()


@PortalRouter.get("/academy", summary="获取投研学院聚合数据")
async def get_academy(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema | None, Depends(get_optional_portal_user)],
) -> AcademyResponse:
    state = _prepare_response(response)
    if state.data_source == "demo":
        return PortalService.academy()
    return await DatabasePortalService(db, auth).academy()


@PortalRouter.get("/profile", summary="获取会员个人中心")
async def get_profile(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema | None, Depends(get_optional_portal_user)],
) -> ProfileResponse:
    state = _prepare_response(response)
    if state.data_source == "demo":
        return PortalService.profile()
    return await DatabasePortalService(db, auth).profile()


@PortalRouter.get("/content/{content_id}", summary="获取投研内容详情")
async def get_content_detail(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema | None, Depends(get_optional_portal_user)],
    content_id: Annotated[int, Path(gt=0, le=2_147_483_647)],
) -> ContentDetailResponse:
    state = _prepare_response(response)
    if state.data_source == "demo":
        result = PortalService.content_detail(content_id)
    else:
        result = await DatabasePortalService(db, auth).content_detail(content_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内容不存在")
    return result


@PortalRouter.get("/course/{course_id}", summary="获取课程详情")
async def get_course_detail(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema | None, Depends(get_optional_portal_user)],
    course_id: Annotated[int, Path(gt=0, le=2_147_483_647)],
) -> CourseDetailResponse:
    state = _prepare_response(response)
    if state.data_source == "demo":
        result = PortalService.course_detail(course_id)
    else:
        result = await DatabasePortalService(db, auth).course_detail(course_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="课程不存在")
    return result


@PortalRouter.get("/member-center", summary="获取会员权益与套餐")
async def get_member_center(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema | None, Depends(get_optional_portal_user)],
) -> MemberCenterResponse:
    state = _prepare_response(response)
    if state.data_source == "demo":
        return PortalService.member_center()
    return await DatabasePortalService(db, auth).member_center()
