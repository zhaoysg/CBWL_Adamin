from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path, Query, Security, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema, PageResultSchema, PaginationQueryParam
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from .schema import (
    ContentCreateSchema,
    ContentDeleteSchema,
    ContentDetailSchema,
    ContentListSchema,
    ContentQueryParam,
    ContentTransitionSchema,
    ContentUpdateSchema,
    ContentVersionSchema,
)
from .service import ContentService

ContentArticleRouter = APIRouter(
    route_class=OperationLogRoute,
    prefix="/article",
    tags=["投研内容管理"],
)


@ContentArticleRouter.get(
    "/list",
    summary="查询投研内容",
    response_model=ResponseSchema[PageResultSchema[ContentListSchema]],
)
async def list_content_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:article:query"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[ContentQueryParam, Query()],
) -> JSONResponse:
    result = await ContentService(auth, db).page(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="查询投研内容成功")


@ContentArticleRouter.get(
    "/detail/{id}",
    summary="获取投研内容详情",
    response_model=ResponseSchema[ContentDetailSchema],
)
async def detail_content_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:article:detail"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="内容ID")],
) -> JSONResponse:
    result = await ContentService(auth, db).detail(id)
    return SuccessResponse(data=result, msg="获取投研内容详情成功")


@ContentArticleRouter.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    summary="创建投研内容草稿",
    response_model=ResponseSchema[ContentDetailSchema],
)
async def create_content_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:article:create"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[ContentCreateSchema, Body(description="投研内容创建参数")],
) -> JSONResponse:
    result = await ContentService(auth, db).create(data)
    return SuccessResponse(data=result, msg="创建投研内容草稿成功")


@ContentArticleRouter.patch(
    "/update/{id}",
    summary="更新投研内容",
    response_model=ResponseSchema[ContentDetailSchema],
)
async def update_content_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:article:update"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="内容ID")],
    data: Annotated[ContentUpdateSchema, Body(description="投研内容更新参数")],
) -> JSONResponse:
    result = await ContentService(auth, db).update(id, data)
    return SuccessResponse(data=result, msg="更新投研内容成功")


@ContentArticleRouter.post(
    "/publish/{id}",
    summary="发布投研内容",
    response_model=ResponseSchema[ContentDetailSchema],
)
async def publish_content_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:article:publish"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="内容ID")],
    data: Annotated[ContentTransitionSchema, Body(description="发布参数")],
) -> JSONResponse:
    result = await ContentService(auth, db).publish(id, data)
    return SuccessResponse(data=result, msg="发布投研内容成功")


@ContentArticleRouter.post(
    "/offline/{id}",
    summary="下线投研内容",
    response_model=ResponseSchema[ContentDetailSchema],
)
async def offline_content_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:article:offline"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="内容ID")],
    data: Annotated[ContentVersionSchema, Body(description="下线参数")],
) -> JSONResponse:
    result = await ContentService(auth, db).offline(id, data)
    return SuccessResponse(data=result, msg="下线投研内容成功")


@ContentArticleRouter.post(
    "/archive/{id}",
    summary="归档投研内容",
    response_model=ResponseSchema[ContentDetailSchema],
)
async def archive_content_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:article:archive"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    id: Annotated[int, Path(ge=1, description="内容ID")],
    data: Annotated[ContentVersionSchema, Body(description="归档参数")],
) -> JSONResponse:
    result = await ContentService(auth, db).archive(id, data)
    return SuccessResponse(data=result, msg="归档投研内容成功")


@ContentArticleRouter.delete(
    "/delete",
    summary="删除投研内容",
    response_model=ResponseSchema[None],
)
async def delete_content_controller(
    auth: Annotated[AuthSchema, Security(AuthPermission(["module_content:article:delete"]))],
    db: Annotated[AsyncSession, Depends(db_getter)],
    data: Annotated[ContentDeleteSchema, Body(description="内容删除参数")],
) -> JSONResponse:
    await ContentService(auth, db).delete(data)
    return SuccessResponse(msg="删除投研内容成功")
