from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    MemberSubscriptionGrantSchema,
    MemberSubscriptionOutSchema,
    MemberSubscriptionQueryParam,
    MemberSubscriptionRevokeSchema,
)
from .service import MemberSubscriptionService

MemberSubscriptionRouter = APIRouter(
    route_class=OperationLogRoute,
    prefix="/subscription",
    tags=["会员订阅"],
)


@MemberSubscriptionRouter.get(
    "/list",
    response_model=ResponseSchema[PageResultSchema[MemberSubscriptionOutSchema]],
    summary="查询会员订阅",
)
async def list_subscription_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:subscription:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[MemberSubscriptionQueryParam, Query()],
) -> JSONResponse:
    result = await MemberSubscriptionService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
    )
    return SuccessResponse(data=result, msg="查询会员订阅成功")


@MemberSubscriptionRouter.get(
    "/detail/{id}",
    response_model=ResponseSchema[MemberSubscriptionOutSchema],
    summary="获取会员订阅详情",
)
async def detail_subscription_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:subscription:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1)],
) -> JSONResponse:
    result = await MemberSubscriptionService(auth, db).detail(id)
    return SuccessResponse(data=result, msg="获取会员订阅详情成功")


@MemberSubscriptionRouter.post(
    "/grant",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseSchema[MemberSubscriptionOutSchema],
    summary="人工发放会员订阅",
)
async def grant_subscription_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:subscription:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[MemberSubscriptionGrantSchema, Body()],
) -> JSONResponse:
    result = await MemberSubscriptionService(auth, db).grant(data)
    return SuccessResponse(data=result, msg="发放会员订阅成功", status_code=status.HTTP_201_CREATED)


@MemberSubscriptionRouter.post(
    "/revoke/{id}",
    response_model=ResponseSchema[MemberSubscriptionOutSchema],
    summary="撤销会员订阅",
)
async def revoke_subscription_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:subscription:revoke"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1)],
    data: Annotated[MemberSubscriptionRevokeSchema, Body()],
) -> JSONResponse:
    result = await MemberSubscriptionService(auth, db).revoke(id, data)
    return SuccessResponse(data=result, msg="撤销会员订阅成功")
