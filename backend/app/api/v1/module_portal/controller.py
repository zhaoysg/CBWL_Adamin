from fastapi import APIRouter, HTTPException, status

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


@PortalRouter.get("/health", response_model=PortalHealth, summary="用户端服务健康检查")
async def portal_health() -> PortalHealth:
    return PortalHealth()


@PortalRouter.get("/home", response_model=HomeResponse, summary="获取首页聚合数据")
async def get_home() -> HomeResponse:
    return PortalService.home()


@PortalRouter.get("/academy", response_model=AcademyResponse, summary="获取投研学院聚合数据")
async def get_academy() -> AcademyResponse:
    return PortalService.academy()


@PortalRouter.get("/profile", response_model=ProfileResponse, summary="获取会员个人中心")
async def get_profile() -> ProfileResponse:
    return PortalService.profile()


@PortalRouter.get("/content/{content_id}", response_model=ContentDetailResponse, summary="获取投研内容详情")
async def get_content_detail(content_id: int) -> ContentDetailResponse:
    result = PortalService.content_detail(content_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内容不存在")
    return result


@PortalRouter.get("/course/{course_id}", response_model=CourseDetailResponse, summary="获取课程详情")
async def get_course_detail(course_id: int) -> CourseDetailResponse:
    result = PortalService.course_detail(course_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="课程不存在")
    return result


@PortalRouter.get("/member-center", response_model=MemberCenterResponse, summary="获取会员权益与套餐")
async def get_member_center() -> MemberCenterResponse:
    return PortalService.member_center()
