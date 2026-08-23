from fastapi import APIRouter

from app.api.v1.module_membership.plan.controller import MemberPlanRouter
from app.api.v1.module_membership.subscription.controller import MemberSubscriptionRouter

membership_router = APIRouter(prefix="/membership")
membership_router.include_router(MemberPlanRouter)
membership_router.include_router(MemberSubscriptionRouter)

__all__ = ["membership_router"]
