from fastapi import APIRouter

from app.api.v1.module_content.article.controller import ContentArticleRouter
from app.api.v1.module_content.category.controller import ContentCategoryRouter

content_router = APIRouter(prefix="/content")
content_router.include_router(ContentCategoryRouter)
content_router.include_router(ContentArticleRouter)

__all__ = ["content_router"]
