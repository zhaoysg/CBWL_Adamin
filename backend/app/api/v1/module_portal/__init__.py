from fastapi import APIRouter

from .controller import PortalRouter

portal_router = APIRouter(prefix="/portal", tags=["财不外露-会员端"])
portal_router.include_router(PortalRouter)

__all__ = ["portal_router"]
