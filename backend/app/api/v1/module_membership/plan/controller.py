from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, BatchSetAvailable, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    MemberPlanCreateSchema,
    MemberPlanOptionSchema,
    MemberPlanOutSchema,
    MemberPlanQueryParam,
    MemberPlanUpdateSchema,
)
from .service import MemberPlanService

MemberPlanRouter = APIRouter(route_class=OperationLogRoute, prefix="/plan", tags=["会员套餐"])


@MemberPlanRouter.get(
    "/list",
    summary="查询会员套餐",
    response_model=ResponseSchema[PageResultSchema[MemberPlanOutSchema]],
)
async def list_member_plan_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:plan:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[MemberPlanQueryParam, Query()],
) -> JSONResponse:
    result = await MemberPlanService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询会员套餐成功")


@MemberPlanRouter.get(
    "/options",
    summary="获取启用会员套餐选项",
    response_model=ResponseSchema[list[MemberPlanOptionSchema]],
)
async def list_member_plan_options_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:plan:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result = await MemberPlanService(auth, db).options()
    return SuccessResponse(data=result, msg="获取会员套餐选项成功")


@MemberPlanRouter.get(
    "/detail/{id}",
    summary="获取会员套餐详情",
    response_model=ResponseSchema[MemberPlanOutSchema],
)
async def detail_member_plan_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:plan:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="套餐ID")],
) -> JSONResponse:
    result = await MemberPlanService(auth, db).detail(id)
    return SuccessResponse(data=result, msg="获取会员套餐详情成功")


@MemberPlanRouter.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    summary="创建会员套餐",
    response_model=ResponseSchema[MemberPlanOutSchema],
)
async def create_member_plan_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:plan:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[MemberPlanCreateSchema, Body(description="会员套餐创建参数")],
) -> JSONResponse:
    result = await MemberPlanService(auth, db).create(data)
    return SuccessResponse(
        data=result,
        msg="创建会员套餐成功",
        status_code=status.HTTP_201_CREATED,
    )


@MemberPlanRouter.put(
    "/update/{id}",
    summary="更新会员套餐",
    response_model=ResponseSchema[MemberPlanOutSchema],
)
async def update_member_plan_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:plan:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="套餐ID")],
    data: Annotated[MemberPlanUpdateSchema, Body(description="会员套餐更新参数")],
) -> JSONResponse:
    result = await MemberPlanService(auth, db).update(id, data)
    return SuccessResponse(data=result, msg="更新会员套餐成功")


@MemberPlanRouter.delete(
    "/delete",
    summary="删除会员套餐",
    response_model=ResponseSchema[None],
)
async def delete_member_plan_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:plan:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    ids: Annotated[list[int], Body(min_length=1, description="套餐ID列表")],
) -> JSONResponse:
    await MemberPlanService(auth, db).delete(ids)
    return SuccessResponse(msg="删除会员套餐成功")


@MemberPlanRouter.patch(
    "/status/batch",
    summary="批量修改会员套餐状态",
    response_model=ResponseSchema[None],
)
async def batch_member_plan_status_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_membership:plan:patch"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BatchSetAvailable, Body(description="状态设置")],
) -> JSONResponse:
    await MemberPlanService(auth, db).set_available(data)
    return SuccessResponse(msg="批量修改会员套餐状态成功")
