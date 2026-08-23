from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema
from app.core.dependencies import db_getter, get_current_user
from app.core.optional_auth import get_optional_current_user

from .secure_schema import PortalArticleResponse, PortalFeedResponse, PortalMembershipResponse
from .secure_service import SecurePortalService

SecurePortalRouter = APIRouter(tags=["财不外露-数据库会员端"])


def _secure_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Portal-Data-Source"] = "database"


@SecurePortalRouter.get("/feed", response_model=PortalFeedResponse, summary="获取按会员权益过滤的投研内容")
async def secure_feed(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema | None, Depends(get_optional_current_user)],
    page_no: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    category_id: Annotated[int | None, Query(ge=1)] = None,
    content_type: Annotated[
        Literal["article", "research", "trade", "institution", "macro", "notice"] | None,
        Query(),
    ] = None,
) -> PortalFeedResponse:
    _secure_headers(response)
    return await SecurePortalService.feed(
        db,
        auth,
        page_no=page_no,
        page_size=page_size,
        category_id=category_id,
        content_type=content_type,
    )


@SecurePortalRouter.get(
    "/article/{content_id}",
    response_model=PortalArticleResponse,
    summary="读取经过服务端权益判定的投研正文",
)
async def secure_article(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema | None, Depends(get_optional_current_user)],
    content_id: Annotated[int, Path(ge=1)],
) -> PortalArticleResponse:
    _secure_headers(response)
    result = await SecurePortalService.article(db, auth, content_id)
    if result is None:
        # Nonexistent and unauthorized resources intentionally share one response.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内容不存在")
    return result


@SecurePortalRouter.get(
    "/me/membership",
    response_model=PortalMembershipResponse,
    summary="获取当前用户有效会员权益",
)
async def secure_membership(
    response: Response,
    db: Annotated[AsyncSession, Depends(db_getter)],
    auth: Annotated[AuthSchema, Depends(get_current_user)],
) -> PortalMembershipResponse:
    _secure_headers(response)
    return await SecurePortalService.membership(db, auth)
