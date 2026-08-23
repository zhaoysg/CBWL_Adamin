from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_system.user.model import UserModel
from app.common.enums import RET
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException

from .model import MemberSubscriptionModel
from .schema import (
    MemberSubscriptionGrantSchema,
    MemberSubscriptionOutSchema,
    MemberSubscriptionQueryParam,
    MemberSubscriptionRevokeSchema,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class MemberSubscriptionService:
    """订阅管理领域服务。所有有效期判断采用 [starts_at, expires_at) 半开区间。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db

    @staticmethod
    def _loader_options():
        return (
            selectinload(MemberSubscriptionModel.user),
            selectinload(MemberSubscriptionModel.plan),
        )

    @staticmethod
    def _is_effective(obj: MemberSubscriptionModel, now: datetime) -> bool:
        return (
            obj.status == "active"
            and obj.revoked_at is None
            and _utc(obj.starts_at) <= now < _utc(obj.expires_at)
            and obj.plan.status == 0
            and not obj.plan.is_deleted
        )

    def _serialize(self, obj: MemberSubscriptionModel, now: datetime | None = None) -> MemberSubscriptionOutSchema:
        check_time = now or datetime.now(UTC)
        schema = MemberSubscriptionOutSchema.model_validate(obj)
        return schema.model_copy(update={"effective": self._is_effective(obj, check_time)})

    async def _get(self, subscription_id: int, *, for_update: bool = False) -> MemberSubscriptionModel | None:
        if for_update:
            locked = await self.db.scalar(
                select(MemberSubscriptionModel.id)
                .where(
                    MemberSubscriptionModel.id == subscription_id,
                    MemberSubscriptionModel.is_deleted.is_(False),
                )
                .with_for_update()
            )
            if locked is None:
                return None
        stmt = (
            select(MemberSubscriptionModel)
            .where(
                MemberSubscriptionModel.id == subscription_id,
                MemberSubscriptionModel.is_deleted.is_(False),
            )
            .options(*self._loader_options())
        )
        return await self.db.scalar(stmt)

    async def detail(self, subscription_id: int) -> MemberSubscriptionOutSchema:
        obj = await self._get(subscription_id)
        if obj is None:
            raise CustomException(msg="会员订阅不存在", status_code=RET.NOT_FOUND.code)
        return self._serialize(obj)

    async def page(
        self,
        *,
        page_no: int,
        page_size: int,
        search: MemberSubscriptionQueryParam,
    ) -> PageResultSchema[MemberSubscriptionOutSchema]:
        now = datetime.now(UTC)
        conditions = [MemberSubscriptionModel.is_deleted.is_(False)]
        if search.user_id is not None:
            conditions.append(MemberSubscriptionModel.user_id == search.user_id)
        if search.plan_id is not None:
            conditions.append(MemberSubscriptionModel.plan_id == search.plan_id)
        if search.external_ref:
            conditions.append(MemberSubscriptionModel.external_ref.like(f"%{search.external_ref.strip()}%"))
        if search.source is not None:
            conditions.append(MemberSubscriptionModel.source == search.source)
        if search.status is not None:
            conditions.append(MemberSubscriptionModel.status == search.status)
        if search.effective_only:
            conditions.extend(
                [
                    MemberSubscriptionModel.status == "active",
                    MemberSubscriptionModel.revoked_at.is_(None),
                    MemberSubscriptionModel.starts_at <= now,
                    MemberSubscriptionModel.expires_at > now,
                    MemberPlanModel.status == 0,
                    MemberPlanModel.is_deleted.is_(False),
                ]
            )

        base = select(MemberSubscriptionModel).join(
            MemberPlanModel,
            MemberPlanModel.id == MemberSubscriptionModel.plan_id,
        )
        total = await self.db.scalar(
            select(func.count())
            .select_from(MemberSubscriptionModel)
            .join(MemberPlanModel, MemberPlanModel.id == MemberSubscriptionModel.plan_id)
            .where(*conditions)
        )
        result = await self.db.execute(
            base.where(*conditions)
            .options(*self._loader_options())
            .order_by(MemberSubscriptionModel.created_time.desc(), MemberSubscriptionModel.id.desc())
            .offset((page_no - 1) * page_size)
            .limit(page_size)
        )
        rows = result.scalars().unique().all()
        count = int(total or 0)
        return PageResultSchema[MemberSubscriptionOutSchema](
            page_no=page_no,
            page_size=page_size,
            total=count,
            has_next=page_no * page_size < count,
            items=[self._serialize(row, now) for row in rows],
        )

    async def grant(self, data: MemberSubscriptionGrantSchema) -> MemberSubscriptionOutSchema:
        now = datetime.now(UTC)

        # Lock the user row: concurrent grants for the same user are serialized on MySQL/PostgreSQL.
        user = await self.db.scalar(
            select(UserModel)
            .where(
                UserModel.id == data.user_id,
                UserModel.is_deleted.is_(False),
                UserModel.status == 0,
            )
            .with_for_update()
        )
        if user is None:
            raise CustomException(msg="用户不存在或已停用", status_code=RET.NOT_FOUND.code)

        plan = await self.db.scalar(
            select(MemberPlanModel).where(
                MemberPlanModel.id == data.plan_id,
                MemberPlanModel.is_deleted.is_(False),
                MemberPlanModel.status == 0,
            )
        )
        if plan is None:
            raise CustomException(msg="会员套餐不存在或已停用", status_code=RET.NOT_FOUND.code)

        existing = await self.db.scalar(
            select(MemberSubscriptionModel)
            .where(
                MemberSubscriptionModel.external_ref == data.external_ref,
                MemberSubscriptionModel.is_deleted.is_(False),
            )
            .options(*self._loader_options())
        )
        if existing is not None:
            if existing.user_id == data.user_id and existing.plan_id == data.plan_id and existing.source == data.source:
                return self._serialize(existing, now)
            raise CustomException(
                msg="幂等业务号已被其他订阅使用",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )

        starts_at = data.starts_at.astimezone(UTC) if data.starts_at else now
        expires_at = (
            data.expires_at.astimezone(UTC)
            if data.expires_at
            else starts_at + timedelta(days=plan.duration_days)
        )
        if expires_at <= starts_at:
            raise CustomException(msg="失效时间必须晚于生效时间", status_code=RET.BAD_REQUEST.code)

        overlap = await self.db.scalar(
            select(MemberSubscriptionModel.id).where(
                MemberSubscriptionModel.user_id == data.user_id,
                MemberSubscriptionModel.plan_id == data.plan_id,
                MemberSubscriptionModel.status == "active",
                MemberSubscriptionModel.is_deleted.is_(False),
                MemberSubscriptionModel.starts_at < expires_at,
                MemberSubscriptionModel.expires_at > starts_at,
            )
        )
        if overlap is not None:
            raise CustomException(
                msg="该用户在所选时间段已存在同套餐订阅",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )

        obj = MemberSubscriptionModel(
            user_id=data.user_id,
            plan_id=data.plan_id,
            external_ref=data.external_ref,
            source=data.source,
            status="active",
            starts_at=starts_at,
            expires_at=expires_at,
            version_no=1,
            description=data.description,
            created_id=self.auth.user.id or None,
            updated_id=self.auth.user.id or None,
        )
        try:
            async with self.db.begin_nested():
                self.db.add(obj)
                await self.db.flush()
        except IntegrityError:
            duplicate = await self.db.scalar(
                select(MemberSubscriptionModel)
                .where(
                    MemberSubscriptionModel.external_ref == data.external_ref,
                    MemberSubscriptionModel.is_deleted.is_(False),
                )
                .options(*self._loader_options())
            )
            if duplicate is not None and duplicate.user_id == data.user_id and duplicate.plan_id == data.plan_id:
                return self._serialize(duplicate, now)
            raise CustomException(
                msg="会员订阅写入冲突，请使用新的幂等业务号重试",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        return await self.detail(obj.id)

    async def revoke(
        self,
        subscription_id: int,
        data: MemberSubscriptionRevokeSchema,
    ) -> MemberSubscriptionOutSchema:
        obj = await self._get(subscription_id, for_update=True)
        if obj is None:
            raise CustomException(msg="会员订阅不存在", status_code=RET.NOT_FOUND.code)
        if obj.version_no != data.version_no:
            raise CustomException(
                msg="会员订阅已发生变化，请刷新后重试",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        if obj.status == "revoked":
            raise CustomException(
                msg="会员订阅已撤销",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )

        obj.status = "revoked"
        obj.revoked_at = datetime.now(UTC)
        obj.revoke_reason = data.reason
        obj.version_no += 1
        obj.updated_id = self.auth.user.id or None
        await self.db.flush()
        return await self.detail(subscription_id)


async def effective_subscriptions(
    db: AsyncSession,
    user_id: int,
    *,
    now: datetime | None = None,
) -> list[MemberSubscriptionModel]:
    """Load currently effective subscriptions; expired, future and revoked rows are excluded."""

    check_time = now or datetime.now(UTC)
    result = await db.execute(
        select(MemberSubscriptionModel)
        .join(MemberPlanModel, MemberPlanModel.id == MemberSubscriptionModel.plan_id)
        .where(
            MemberSubscriptionModel.user_id == user_id,
            MemberSubscriptionModel.status == "active",
            MemberSubscriptionModel.revoked_at.is_(None),
            MemberSubscriptionModel.is_deleted.is_(False),
            MemberSubscriptionModel.starts_at <= check_time,
            MemberSubscriptionModel.expires_at > check_time,
            MemberPlanModel.status == 0,
            MemberPlanModel.is_deleted.is_(False),
        )
        .options(*MemberSubscriptionService._loader_options())
        .order_by(MemberPlanModel.rank.desc(), MemberSubscriptionModel.expires_at.desc())
    )
    return list(result.scalars().unique().all())
