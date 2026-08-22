from fastapi import APIRouter, HTTPException, Path, Response, status

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
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Portal-Data-Source"] = state.data_source


def _prepare_response(response: Response) -> PortalRuntimeState:
    state = require_portal_runtime()
    _apply_no_store_headers(response, state)
    return state


@PortalRouter.get("/health", response_model=PortalHealth, summary="用户端服务健康检查")
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


@PortalRouter.get("/home", response_model=HomeResponse, summary="获取首页聚合数据")
async def get_home(response: Response) -> HomeResponse:
    _prepare_response(response)
    return PortalService.home()


@PortalRouter.get("/academy", response_model=AcademyResponse, summary="获取投研学院聚合数据")
async def get_academy(response: Response) -> AcademyResponse:
    _prepare_response(response)
    return PortalService.academy()


@PortalRouter.get("/profile", response_model=ProfileResponse, summary="获取会员个人中心")
async def get_profile(response: Response) -> ProfileResponse:
    _prepare_response(response)
    return PortalService.profile()


@PortalRouter.get("/content/{content_id}", response_model=ContentDetailResponse, summary="获取投研内容详情")
async def get_content_detail(
    response: Response,
    content_id: int = Path(gt=0, le=2_147_483_647),
) -> ContentDetailResponse:
    _prepare_response(response)
    result = PortalService.content_detail(content_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内容不存在")
    return result


@PortalRouter.get("/course/{course_id}", response_model=CourseDetailResponse, summary="获取课程详情")
async def get_course_detail(
    response: Response,
    course_id: int = Path(gt=0, le=2_147_483_647),
) -> CourseDetailResponse:
    _prepare_response(response)
    result = PortalService.course_detail(course_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="课程不存在")
    return result


@PortalRouter.get("/member-center", response_model=MemberCenterResponse, summary="获取会员权益与套餐")
async def get_member_center(response: Response) -> MemberCenterResponse:
    _prepare_response(response)
    return PortalService.member_center()
