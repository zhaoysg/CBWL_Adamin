from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, BatchSetAvailable, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    ContentCategoryCreateSchema,
    ContentCategoryOptionSchema,
    ContentCategoryOutSchema,
    ContentCategoryQueryParam,
    ContentCategoryTreeSchema,
    ContentCategoryUpdateSchema,
)
from .service import ContentCategoryService

ContentCategoryRouter = APIRouter(
    route_class=OperationLogRoute,
    prefix="/category",
    tags=["投研内容分类"],
)


@ContentCategoryRouter.get(
    "/list",
    summary="查询内容分类",
    response_model=ResponseSchema[PageResultSchema[ContentCategoryOutSchema]],
)
async def list_content_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:category:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[ContentCategoryQueryParam, Query()],
) -> JSONResponse:
    result = await ContentCategoryService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询内容分类成功")


@ContentCategoryRouter.get(
    "/tree",
    summary="获取内容分类树",
    response_model=ResponseSchema[list[ContentCategoryTreeSchema]],
)
async def tree_content_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:category:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    enabled_only: Annotated[bool, Query(description="仅返回启用分类")] = False,
) -> JSONResponse:
    result = await ContentCategoryService(auth, db).tree(enabled_only=enabled_only)
    return SuccessResponse(data=result, msg="获取内容分类树成功")


@ContentCategoryRouter.get(
    "/options",
    summary="获取启用内容分类选项",
    response_model=ResponseSchema[list[ContentCategoryOptionSchema]],
)
async def options_content_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:category:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    result = await ContentCategoryService(auth, db).options()
    return SuccessResponse(data=result, msg="获取内容分类选项成功")


@ContentCategoryRouter.get(
    "/detail/{id}",
    summary="获取内容分类详情",
    response_model=ResponseSchema[ContentCategoryOutSchema],
)
async def detail_content_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:category:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="分类ID")],
) -> JSONResponse:
    result = await ContentCategoryService(auth, db).detail(id)
    return SuccessResponse(data=result, msg="获取内容分类详情成功")


@ContentCategoryRouter.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    summary="创建内容分类",
    response_model=ResponseSchema[ContentCategoryOutSchema],
)
async def create_content_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:category:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[ContentCategoryCreateSchema, Body(description="内容分类创建参数")],
) -> JSONResponse:
    result = await ContentCategoryService(auth, db).create(data)
    return SuccessResponse(
        data=result,
        msg="创建内容分类成功",
        status_code=status.HTTP_201_CREATED,
    )


@ContentCategoryRouter.put(
    "/update/{id}",
    summary="更新内容分类",
    response_model=ResponseSchema[ContentCategoryOutSchema],
)
async def update_content_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:category:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="分类ID")],
    data: Annotated[ContentCategoryUpdateSchema, Body(description="内容分类更新参数")],
) -> JSONResponse:
    result = await ContentCategoryService(auth, db).update(id, data)
    return SuccessResponse(data=result, msg="更新内容分类成功")


@ContentCategoryRouter.delete(
    "/delete",
    summary="删除内容分类",
    response_model=ResponseSchema[None],
)
async def delete_content_category_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:category:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    ids: Annotated[list[int], Body(min_length=1, description="分类ID列表")],
) -> JSONResponse:
    await ContentCategoryService(auth, db).delete(ids)
    return SuccessResponse(msg="删除内容分类成功")


@ContentCategoryRouter.patch(
    "/status/batch",
    summary="批量修改内容分类状态",
    response_model=ResponseSchema[None],
)
async def batch_content_category_status_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:category:patch"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[BatchSetAvailable, Body(description="状态设置")],
) -> JSONResponse:
    await ContentCategoryService(auth, db).set_available(data)
    return SuccessResponse(msg="批量修改内容分类状态成功")
