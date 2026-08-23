from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.module_content.article.model import ContentModel, ContentPlanModel
from app.api.v1.module_membership.subscription.service import effective_subscriptions
from app.core.base_schema import AuthSchema

from .secure_schema import (
    PortalArticleResponse,
    PortalFeedItem,
    PortalFeedResponse,
    PortalMembershipItem,
    PortalMembershipResponse,
)


class SecurePortalService:
    """Database-backed member portal with fail-closed entitlement predicates."""

    @staticmethod
    async def _effective_plan_ids(db: AsyncSession, auth: AuthSchema | None) -> set[int]:
        if auth is None or auth.user.id <= 0:
            return set()
        return {row.plan_id for row in await effective_subscriptions(db, auth.user.id)}

    @staticmethod
    def _visibility_predicate(auth: AuthSchema | None, plan_ids: set[int]):
        clauses = [ContentModel.access_level == "public"]
        if auth is not None and auth.user.id > 0:
            clauses.append(ContentModel.access_level == "login")
        if plan_ids:
            clauses.append(ContentModel.access_level == "member")
            clauses.append(
                and_(
                    ContentModel.access_level == "premium",
                    exists(
                        select(ContentPlanModel.content_id).where(
                            ContentPlanModel.content_id == ContentModel.id,
                            ContentPlanModel.plan_id.in_(plan_ids),
                        )
                    ),
                )
            )
        return or_(*clauses)

    @staticmethod
    def _item(obj: ContentModel) -> PortalFeedItem:
        return PortalFeedItem(
            id=obj.id,
            category_id=obj.category_id,
            category_name=obj.category_name,
            content_type=obj.content_type,
            title=obj.title,
            slug=obj.slug,
            summary=obj.summary,
            cover_url=obj.cover_url,
            author_name=obj.author_name,
            access_level=obj.access_level,
            published_at=obj.published_at,
            is_pinned=obj.is_pinned,
            is_featured=obj.is_featured,
            like_count=obj.like_count,
            comment_count=obj.comment_count,
        )

    @classmethod
    async def feed(
        cls,
        db: AsyncSession,
        auth: AuthSchema | None,
        *,
        page_no: int,
        page_size: int,
        category_id: int | None,
        content_type: str | None,
    ) -> PortalFeedResponse:
        now = datetime.now(UTC)
        plan_ids = await cls._effective_plan_ids(db, auth)
        conditions = [
            ContentModel.is_deleted.is_(False),
            ContentModel.status == 1,
            ContentModel.published_at.is_not(None),
            ContentModel.published_at <= now,
            cls._visibility_predicate(auth, plan_ids),
        ]
        if category_id is not None:
            conditions.append(ContentModel.category_id == category_id)
        if content_type is not None:
            conditions.append(ContentModel.content_type == content_type)

        total = await db.scalar(select(func.count()).select_from(ContentModel).where(*conditions))
        result = await db.execute(
            select(ContentModel)
            .where(*conditions)
            .options(selectinload(ContentModel.category))
            .order_by(
                ContentModel.is_pinned.desc(),
                ContentModel.sort_no.desc(),
                ContentModel.published_at.desc(),
                ContentModel.id.desc(),
            )
            .offset((page_no - 1) * page_size)
            .limit(page_size)
        )
        rows = result.scalars().unique().all()
        count = int(total or 0)
        return PortalFeedResponse(
            page_no=page_no,
            page_size=page_size,
            total=count,
            has_next=page_no * page_size < count,
            items=[cls._item(row) for row in rows],
        )

    @classmethod
    async def article(
        cls,
        db: AsyncSession,
        auth: AuthSchema | None,
        content_id: int,
    ) -> PortalArticleResponse | None:
        now = datetime.now(UTC)
        plan_ids = await cls._effective_plan_ids(db, auth)
        obj = await db.scalar(
            select(ContentModel)
            .where(
                ContentModel.id == content_id,
                ContentModel.is_deleted.is_(False),
                ContentModel.status == 1,
                ContentModel.published_at.is_not(None),
                ContentModel.published_at <= now,
                cls._visibility_predicate(auth, plan_ids),
            )
            .options(selectinload(ContentModel.category))
        )
        if obj is None:
            return None
        return PortalArticleResponse(
            **cls._item(obj).model_dump(),
            body=obj.body,
            body_format=obj.body_format,
        )

    @staticmethod
    async def membership(db: AsyncSession, auth: AuthSchema) -> PortalMembershipResponse:
        rows = await effective_subscriptions(db, auth.user.id)
        items = [
            PortalMembershipItem(
                subscription_id=row.id,
                plan_id=row.plan_id,
                plan_code=row.plan.plan_code,
                plan_name=row.plan.plan_name,
                rank=row.plan.rank,
                starts_at=row.starts_at,
                expires_at=row.expires_at,
            )
            for row in rows
        ]
        return PortalMembershipResponse(
            user_id=auth.user.id,
            active=bool(items),
            highest_rank=max((item.rank for item in items), default=None),
            subscriptions=items,
        )
