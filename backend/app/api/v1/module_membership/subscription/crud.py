from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_system.user.model import UserModel
from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema, PageResultSchema

from .model import MemberSubscriptionModel
from .schema import (
    MemberSubscriptionGrantSchema,
    MemberSubscriptionOutSchema,
    MemberSubscriptionQueryParam,
    MemberSubscriptionRevokeSchema,
)


class MemberSubscriptionCRUD(
    CRUDBase[
        MemberSubscriptionModel,
        MemberSubscriptionGrantSchema,
        MemberSubscriptionRevokeSchema,
    ]
):
    """会员订阅数据访问层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=MemberSubscriptionModel, auth=auth, db=db)

    @staticmethod
    def _detail_options():
        return (
            joinedload(MemberSubscriptionModel.user),
            joinedload(MemberSubscriptionModel.plan),
            joinedload(MemberSubscriptionModel.created_by),
            joinedload(MemberSubscriptionModel.updated_by),
        )

    async def get_detail(self, id: int, *, for_update: bool = False) -> MemberSubscriptionModel | None:
        conditions = await self._build_conditions(id=id)
        if for_update:
            lock = await self.db.execute(select(MemberSubscriptionModel.id).where(*conditions).with_for_update())
            if lock.scalar_one_or_none() is None:
                return None
        result = await self.db.execute(select(MemberSubscriptionModel).options(*self._detail_options()).where(*conditions))
        return result.scalars().first()

    async def get_by_source_ref(
        self,
        *,
        source: str,
        source_ref: str,
        for_update: bool = False,
    ) -> MemberSubscriptionModel | None:
        conditions = await self._build_conditions(source=source, source_ref=source_ref)
        if for_update:
            lock = await self.db.execute(select(MemberSubscriptionModel.id).where(*conditions).with_for_update())
            if lock.scalar_one_or_none() is None:
                return None
        result = await self.db.execute(select(MemberSubscriptionModel).options(*self._detail_options()).where(*conditions))
        return result.scalars().first()

    async def page_admin(
        self,
        *,
        page_no: int,
        page_size: int,
        search: MemberSubscriptionQueryParam,
        now: datetime,
    ) -> tuple[PageResultSchema[MemberSubscriptionOutSchema], list[MemberSubscriptionModel]]:
        conditions = await self._build_conditions()

        if search.user_id is not None:
            conditions.append(MemberSubscriptionModel.user_id == search.user_id)
        if search.plan_id is not None:
            conditions.append(MemberSubscriptionModel.plan_id == search.plan_id)
        if search.source is not None:
            conditions.append(MemberSubscriptionModel.source == search.source)
        if search.source_ref:
            conditions.append(MemberSubscriptionModel.source_ref.like(f"%{search.source_ref}%"))
        if search.status is not None:
            conditions.append(MemberSubscriptionModel.status == search.status)
        if search.starts_at:
            conditions.extend(
                [
                    MemberSubscriptionModel.starts_at >= search.starts_at[0],
                    MemberSubscriptionModel.starts_at <= search.starts_at[1],
                ]
            )
        if search.expires_at:
            conditions.extend(
                [
                    MemberSubscriptionModel.expires_at >= search.expires_at[0],
                    MemberSubscriptionModel.expires_at <= search.expires_at[1],
                ]
            )
        if search.effective_status == "revoked":
            conditions.append(MemberSubscriptionModel.status == 1)
        elif search.effective_status == "upcoming":
            conditions.extend(
                [
                    MemberSubscriptionModel.status == 0,
                    MemberSubscriptionModel.starts_at > now,
                ]
            )
        elif search.effective_status == "active":
            conditions.extend(
                [
                    MemberSubscriptionModel.status == 0,
                    MemberSubscriptionModel.starts_at <= now,
                    MemberSubscriptionModel.expires_at > now,
                ]
            )
        elif search.effective_status == "expired":
            conditions.extend(
                [
                    MemberSubscriptionModel.status == 0,
                    MemberSubscriptionModel.expires_at <= now,
                ]
            )

        if search.keyword:
            like_value = f"%{search.keyword}%"
            conditions.append(
                or_(
                    UserModel.username.like(like_value),
                    UserModel.name.like(like_value),
                    UserModel.mobile.like(like_value),
                    MemberPlanModel.plan_code.like(like_value),
                    MemberPlanModel.plan_name.like(like_value),
                    MemberSubscriptionModel.source_ref.like(like_value),
                )
            )

        base = (
            select(MemberSubscriptionModel)
            .join(UserModel, UserModel.id == MemberSubscriptionModel.user_id)
            .join(MemberPlanModel, MemberPlanModel.id == MemberSubscriptionModel.plan_id)
            .where(*conditions)
        )
        total = await self.db.scalar(
            select(func.count(MemberSubscriptionModel.id))
            .join(UserModel, UserModel.id == MemberSubscriptionModel.user_id)
            .join(MemberPlanModel, MemberPlanModel.id == MemberSubscriptionModel.plan_id)
            .where(*conditions)
        )
        result = await self.db.execute(
            base.options(*self._detail_options())
            .order_by(
                MemberSubscriptionModel.expires_at.desc(),
                MemberSubscriptionModel.id.desc(),
            )
            .offset((page_no - 1) * page_size)
            .limit(page_size)
        )
        rows = result.scalars().unique().all()
        return PageResultSchema(
            page_no=page_no,
            page_size=page_size,
            total=total or 0,
            has_next=page_no * page_size < (total or 0),
            items=[],
        ), rows
