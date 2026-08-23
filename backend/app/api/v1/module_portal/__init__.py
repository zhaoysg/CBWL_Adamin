from fastapi import APIRouter

from .controller import PortalRouter
from .secure_controller import SecurePortalRouter

portal_router = APIRouter(prefix="/portal", tags=["财不外露-会员端"])
portal_router.include_router(PortalRouter)
portal_router.include_router(SecurePortalRouter)

__all__ = ["portal_router"]
