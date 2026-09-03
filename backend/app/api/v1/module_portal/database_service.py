from __future__ import annotations

import html
import math
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api.v1.module_content.article.model import ContentModel
from app.api.v1.module_identity.model import CustomerModel
from app.api.v1.module_membership.entitlement import (
    EntitlementContext,
    EntitlementDecision,
    EntitlementFailure,
    as_utc,
    count_active_members,
    evaluate_content_access,
    utc_now,
)
from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_system.user.model import UserModel
from app.common.enums import RET
from app.core.exceptions import CustomException

from .entitlement import load_portal_entitlement_context
from .principal import PortalPrincipal
from .schema import (
    AcademyResponse,
    Author,
    ContentDetailResponse,
    CourseDetailResponse,
    FeedItem,
    HomeResponse,
    LearningStats,
    MemberCenterResponse,
    MemberPlan,
    MemberSummary,
    PinnedItem,
    ProfileResponse,
    UnlockAction,
)

_TAG_RE = re.compile(r"<[^>]+>")


class DatabasePortalService:
    """面向 H5 的真实数据库 Portal Provider。"""

    def __init__(
        self,
        db: AsyncSession,
        principal: PortalPrincipal,
        *,
        now: datetime | None = None,
    ) -> None:
        self.db = db
        self.principal = principal
        self.auth = principal.auth
        self.now = as_utc(now or utc_now())
        self._context: EntitlementContext | None = None
        self._user: UserModel | None = None
        self._customer: CustomerModel | None = None

    @property
    def user_id(self) -> int | None:
        return self.principal.legacy_user_id

    @property
    def customer_id(self) -> int | None:
        return self.principal.customer_id

    async def home(self) -> HomeResponse:
        context = await self._entitlement_context()
        member = await self._member_summary(context)
        contents = await self._published_contents(limit=100)
        feed = [self._feed_item(item, context) for item in contents]
        pinned = [
            self._pinned_item(item)
            for item in contents
            if item.is_pinned
        ][:20]
        categories = list(
            dict.fromkeys(item.category for item in feed)
        )[:30]

        return HomeResponse(
            brand_name="财不外露",
            brand_slogan="理性研究，长期主义",
            joined_count=await count_active_members(self.db, now=self.now),
            member=member,
            pinned=pinned,
            categories=categories,
            feed=feed,
        )

    async def academy(self) -> AcademyResponse:
        return AcademyResponse(
            live_sessions=[],
            columns=[],
            course_categories=[],
            courses=[],
        )

    async def profile(self) -> ProfileResponse:
        context = await self._require_authenticated_context()
        member = await self._member_summary(context)
        if member is None:
            raise CustomException(
                msg="用户不存在",
                status_code=RET.NOT_FOUND.code,
            )

        return ProfileResponse(
            member=member,
            benefits=self._active_benefits(context),
            stats=LearningStats(
                learning_courses=0,
                reading_columns=0,
                replay_count=0,
                learning_hours=0,
            ),
            recent_learning=None,
            achievements=[],
            assets=[],
        )

    async def content_detail(
        self,
        content_id: int,
    ) -> ContentDetailResponse | None:
        """Backward-compatible strict detail endpoint."""

        content = await self._published_content(content_id)
        if content is None:
            return None
        decision = await self._content_decision(content)
        self._raise_content_denied(decision)
        return self._content_response(content, decision)

    async def content_preview(
        self,
        content_id: int,
    ) -> ContentDetailResponse | None:
        """Return public metadata and the body only when authorized."""

        content = await self._published_content(content_id)
        if content is None:
            return None
        decision = await self._content_decision(content)
        return self._content_response(content, decision)

    async def course_detail(
        self,
        course_id: int,
    ) -> CourseDetailResponse | None:
        return None

    async def member_center(self) -> MemberCenterResponse:
        context = await self._entitlement_context()
        member = await self._member_summary(context)
        result = await self.db.execute(
            select(MemberPlanModel)
            .where(
                MemberPlanModel.status == 0,
                MemberPlanModel.is_deleted.is_(False),
            )
            .order_by(
                MemberPlanModel.sort_no.asc(),
                MemberPlanModel.rank.asc(),
                MemberPlanModel.id.asc(),
            )
        )
        plans = result.scalars().all()
        highest_rank = max(
            (item.rank for item in plans),
            default=None,
        )
        return MemberCenterResponse(
            member=member,
            current_benefits=self._active_benefits(context),
            plans=[
                MemberPlan(
                    id=item.id,
                    code=item.plan_code,
                    name=item.plan_name,
                    rank=item.rank,
                    duration_days=item.duration_days,
                    period_label=self._period_label(item.duration_days),
                    price=item.price,
                    original_price=None,
                    benefits=list(item.benefits or []),
                    recommended=(
                        highest_rank is not None
                        and item.rank == highest_rank
                    ),
                )
                for item in plans
            ],
        )

    async def _published_contents(
        self,
        *,
        limit: int,
    ) -> list[ContentModel]:
        result = await self.db.execute(
            select(ContentModel)
            .options(
                joinedload(ContentModel.category),
                selectinload(ContentModel.content_plans),
            )
            .where(
                ContentModel.status == 1,
                ContentModel.published_at.is_not(None),
                ContentModel.published_at <= self.now,
                ContentModel.is_deleted.is_(False),
            )
            .order_by(
                ContentModel.is_pinned.desc(),
                ContentModel.sort_no.asc(),
                ContentModel.published_at.desc(),
                ContentModel.id.desc(),
            )
            .limit(limit)
        )
        return list(result.scalars().unique().all())

    async def _published_content(
        self,
        content_id: int,
    ) -> ContentModel | None:
        result = await self.db.execute(
            select(ContentModel)
            .options(
                joinedload(ContentModel.category),
                selectinload(ContentModel.content_plans),
            )
            .where(
                ContentModel.id == content_id,
                ContentModel.status == 1,
                ContentModel.published_at.is_not(None),
                ContentModel.published_at <= self.now,
                ContentModel.is_deleted.is_(False),
            )
        )
        return result.scalars().unique().first()

    async def _content_decision(
        self,
        content: ContentModel,
    ) -> EntitlementDecision:
        context = await self._entitlement_context()
        return evaluate_content_access(
            access_level=content.access_level,
            required_plan_ids=set(content.plan_ids),
            context=context,
        )

    def _content_response(
        self,
        content: ContentModel,
        decision: EntitlementDecision,
    ) -> ContentDetailResponse:
        unlock_action, unlock_message = self._content_unlock_prompt(
            decision.failure
        )
        reading_source = (
            content.body
            if decision.can_access
            else content.summary or ""
        )
        body_text = html.unescape(
            _TAG_RE.sub(" ", reading_source)
        )
        reading_minutes = max(
            1,
            min(1440, math.ceil(len(body_text.strip()) / 400)),
        )
        return ContentDetailResponse(
            id=content.id,
            category=content.category.category_name,
            title=content.title,
            summary=content.summary or "",
            cover_url=content.cover_url,
            published_at=content.published_at or content.updated_time,
            access_level=content.access_level,
            can_access=decision.can_access,
            lock_reason=decision.failure,
            unlock_action=unlock_action,
            unlock_message=unlock_message,
            like_count=content.like_count,
            comment_count=content.comment_count,
            reading_minutes=reading_minutes,
            author=self._author(content),
            body_html=content.body if decision.can_access else None,
            sections=[],
        )

    @staticmethod
    def _raise_content_denied(
        decision: EntitlementDecision,
    ) -> None:
        if decision.can_access:
            return
        if decision.failure == "login_required":
            raise CustomException(
                msg="请登录后查看该内容",
                code=RET.UNAUTHORIZED.code,
                status_code=RET.UNAUTHORIZED.code,
            )
        if decision.failure == "membership_required":
            raise CustomException(
                msg="该内容仅限有效会员查看",
                code=RET.FORBIDDEN.code,
                status_code=RET.FORBIDDEN.code,
            )
        raise CustomException(
            msg="当前会员套餐不包含该内容",
            code=RET.FORBIDDEN.code,
            status_code=RET.FORBIDDEN.code,
        )

    async def _entitlement_context(self) -> EntitlementContext:
        if self._context is None:
            self._context = await load_portal_entitlement_context(
                self.db,
                self.principal,
                now=self.now,
            )
        return self._context

    async def _require_authenticated_context(
        self,
    ) -> EntitlementContext:
        if not self.principal.is_authenticated:
            raise CustomException(
                msg="请登录后访问个人中心",
                code=RET.UNAUTHORIZED.code,
                status_code=RET.UNAUTHORIZED.code,
            )
        return await self._entitlement_context()

    async def _load_user(self) -> UserModel | None:
        if self.user_id is None:
            return None
        if self._user is None:
            self._user = await self.db.scalar(
                select(UserModel).where(
                    UserModel.id == self.user_id,
                    UserModel.status == 0,
                    UserModel.is_deleted.is_(False),
                )
            )
        return self._user

    async def _load_customer(self) -> CustomerModel | None:
        if self.customer_id is None:
            return None
        if self._customer is None:
            self._customer = await self.db.scalar(
                select(CustomerModel).where(
                    CustomerModel.id == self.customer_id,
                    CustomerModel.status == "active",
                    CustomerModel.is_deleted.is_(False),
                )
            )
        return self._customer

    async def _member_summary(
        self,
        context: EntitlementContext,
    ) -> MemberSummary | None:
        ranked = sorted(
            context.subscriptions,
            key=lambda item: (
                item.plan.rank,
                as_utc(item.expires_at),
                item.id,
            ),
            reverse=True,
        )
        best = ranked[0] if ranked else None
        latest_expiry = max(
            (as_utc(item.expires_at) for item in ranked),
            default=None,
        )

        if self.principal.actor_type == "customer":
            customer = await self._load_customer()
            if customer is None:
                return None
            created_at = as_utc(customer.created_time)
            member_id = customer.id
            nickname = customer.nickname
            member_no = customer.customer_no
        else:
            user = await self._load_user()
            if user is None:
                return None
            created_at = as_utc(user.created_time)
            member_id = user.id
            nickname = user.name or user.username
            member_no = f"CW{user.id:08d}"

        joined_days = max(
            (self.now.date() - created_at.date()).days,
            0,
        )
        return MemberSummary(
            id=member_id,
            nickname=nickname,
            level_name=(
                best.plan.plan_name if best else "注册用户"
            ),
            expire_date=(
                latest_expiry.date() if latest_expiry else None
            ),
            member_no=member_no,
            joined_days=joined_days,
            slogan="独立思考，持续学习，控制风险",
            is_member=bool(ranked),
            active_plan_codes=sorted(
                {item.plan.plan_code for item in ranked}
            ),
        )

    def _active_benefits(
        self,
        context: EntitlementContext,
    ) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        subscriptions = sorted(
            context.subscriptions,
            key=lambda item: (item.plan.rank, item.id),
            reverse=True,
        )
        for subscription in subscriptions:
            for benefit in subscription.plan.benefits or []:
                if benefit not in seen:
                    seen.add(benefit)
                    result.append(benefit)
        return result[:50]

    def _feed_item(
        self,
        content: ContentModel,
        context: EntitlementContext,
    ) -> FeedItem:
        decision = evaluate_content_access(
            access_level=content.access_level,
            required_plan_ids=set(content.plan_ids),
            context=context,
        )
        return FeedItem(
            id=content.id,
            category=content.category.category_name,
            content_type=content.content_type,
            title=content.title,
            summary=content.summary or "",
            cover_url=content.cover_url,
            published_at=content.published_at or content.updated_time,
            access_level=content.access_level,
            can_access=decision.can_access,
            lock_reason=decision.failure,
            like_count=content.like_count,
            comment_count=content.comment_count,
            author=self._author(content),
            liked_by_names=[],
            comments=[],
        )

    @staticmethod
    def _content_unlock_prompt(
        failure: EntitlementFailure | None,
    ) -> tuple[UnlockAction | None, str | None]:
        if failure == "login_required":
            return "login", "登录后可查看完整正文"
        if failure == "membership_required":
            return "member", "开通有效会员后可查看完整正文"
        if failure == "plan_required":
            return "upgrade", "升级到适用会员套餐后可查看完整正文"
        return None, None

    @staticmethod
    def _author(content: ContentModel) -> Author:
        name = content.author_name.strip() or "投研团队"
        return Author(
            id=content.created_id or content.id,
            name=name,
            title="投研主理人",
            avatar_text=name[:1],
        )

    @staticmethod
    def _pinned_item(content: ContentModel) -> PinnedItem:
        icon_map = {
            "research": "report",
            "trade": "trend",
            "institution": "building",
            "macro": "globe",
            "notice": "bell",
        }
        return PinnedItem(
            id=content.id,
            title=content.title,
            subtitle=content.summary or "查看最新投研内容",
            icon=icon_map.get(content.content_type, "document"),
            accent="blue",
            target_type="content",
            target_id=content.id,
        )

    @staticmethod
    def _period_label(duration_days: int) -> str:
        if duration_days % 365 == 0:
            years = duration_days // 365
            return f"{years}年"
        if duration_days % 30 == 0:
            months = duration_days // 30
            return f"{months}个月"
        return f"{duration_days}天"
