from fastapi import APIRouter

from app.api.v1.module_membership.plan.controller import MemberPlanRouter

membership_router = APIRouter(prefix="/membership")
membership_router.include_router(MemberPlanRouter)

__all__ = ["membership_router"]
