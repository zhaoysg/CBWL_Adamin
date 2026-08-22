from fastapi import APIRouter

from .schema import AcademyResponse, HomeResponse, PortalHealth, ProfileResponse
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
