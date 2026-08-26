from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_membership.entitlement import as_utc, utc_now
from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.api.v1.module_system.user.model import UserModel
from app.common.enums import RET
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException

from .crud import MemberSubscriptionCRUD
from .model import MemberSubscriptionModel
from .schema import (
    MemberSubscriptionGrantSchema,
    MemberSubscriptionOutSchema,
    MemberSubscriptionQueryParam,
    MemberSubscriptionRevokeSchema,
    MemberSubscriptionUserOptionSchema,
    SubscriptionEffectiveStatus,
)


class MemberSubscriptionService:
    """会员订阅领域服务。"""

    SOURCE_MANUAL = "manual"

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = MemberSubscriptionCRUD(auth, db)

    async def detail(self, id: int) -> MemberSubscriptionOutSchema:
        obj = await self.crud.get_detail(id)
        if obj is None:
            raise CustomException(msg="会员订阅不存在", status_code=RET.NOT_FOUND.code)
        return self._to_schema(obj, utc_now())

    async def page(
        self,
        *,
        page_no: int,
        page_size: int,
        search: MemberSubscriptionQueryParam,
    ) -> PageResultSchema[MemberSubscriptionOutSchema]:
        current = utc_now()
        page, rows = await self.crud.page_admin(
            page_no=page_no,
            page_size=page_size,
            search=search,
            now=current,
        )
        page.items = [self._to_schema(item, current) for item in rows]
        return page

    async def user_options(
        self,
        *,
        keyword: str | None,
        limit: int,
    ) -> list[MemberSubscriptionUserOptionSchema]:
        conditions = [
            UserModel.status == 0,
            UserModel.is_deleted.is_(False),
        ]
        if keyword:
            like_value = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    UserModel.username.like(like_value),
                    UserModel.name.like(like_value),
                    UserModel.mobile.like(like_value),
                )
            )
        result = await self.db.execute(select(UserModel).where(*conditions).order_by(UserModel.id.asc()).limit(limit))
        return [MemberSubscriptionUserOptionSchema.model_validate(item) for item in result.scalars().all()]

    async def grant_manual(self, data: MemberSubscriptionGrantSchema) -> MemberSubscriptionOutSchema:
        existing = await self.crud.get_by_source_ref(
            source=self.SOURCE_MANUAL,
            source_ref=data.source_ref,
            for_update=True,
        )
        if existing is not None:
            self._assert_idempotent_match(existing, data)
            return self._to_schema(existing, utc_now())

        user = await self.db.scalar(
            select(UserModel).where(
                UserModel.id == data.user_id,
                UserModel.status == 0,
                UserModel.is_deleted.is_(False),
            )
        )
        if user is None:
            raise CustomException(msg="用户不存在或已停用", status_code=RET.NOT_FOUND.code)

        plan = await self.db.scalar(
            select(MemberPlanModel).where(
                MemberPlanModel.id == data.plan_id,
                MemberPlanModel.status == 0,
                MemberPlanModel.is_deleted.is_(False),
            )
        )
        if plan is None:
            raise CustomException(msg="会员套餐不存在或已停用", status_code=RET.NOT_FOUND.code)

        starts_at = as_utc(data.starts_at or utc_now())
        expires_at = as_utc(data.expires_at or (starts_at + timedelta(days=plan.duration_days)))
        if expires_at <= starts_at:
            raise CustomException(msg="到期时间必须晚于生效时间", status_code=RET.BAD_REQUEST.code)

        values = {
            "user_id": data.user_id,
            "plan_id": data.plan_id,
            "source": self.SOURCE_MANUAL,
            "source_ref": data.source_ref,
            "status": 0,
            "starts_at": starts_at,
            "expires_at": expires_at,
            "revoked_at": None,
            "grant_reason": data.grant_reason,
            "revoke_reason": None,
            "version_no": 1,
            "description": data.description,
        }
        actor_id = self.auth.user.id
        if actor_id:
            values["created_id"] = actor_id
            values["updated_id"] = actor_id

        try:
            async with self.db.begin_nested():
                obj = MemberSubscriptionModel(**values)
                self.db.add(obj)
                await self.db.flush()
                subscription_id = obj.id
        except IntegrityError:
            # 两个请求可能同时通过首次查询；唯一约束负责仲裁，失败方在
            # savepoint 回滚后读取胜出的记录，并只在请求完全一致时复用。
            existing = await self.crud.get_by_source_ref(
                source=self.SOURCE_MANUAL,
                source_ref=data.source_ref,
                for_update=True,
            )
            if existing is None:
                raise CustomException(
                    msg="会员授权写入冲突，请稍后重试",
                    code=RET.CONFLICT.code,
                    status_code=RET.CONFLICT.code,
                )
            self._assert_idempotent_match(existing, data)
            return self._to_schema(existing, utc_now())

        return await self.detail(subscription_id)

    async def revoke(
        self,
        id: int,
        data: MemberSubscriptionRevokeSchema,
    ) -> MemberSubscriptionOutSchema:
        obj = await self.crud.get_detail(id, for_update=True)
        if obj is None:
            raise CustomException(msg="会员订阅不存在", status_code=RET.NOT_FOUND.code)
        if obj.version_no != data.version_no:
            raise self._conflict("订阅版本已变化，请刷新后重试")
        if obj.status == 1:
            raise self._conflict("会员订阅已经撤销")

        obj.status = 1
        obj.revoked_at = utc_now()
        obj.revoke_reason = data.reason
        obj.version_no += 1
        obj.updated_time = utc_now()
        if self.auth.user.id:
            obj.updated_id = self.auth.user.id
        await self.db.flush()
        return await self.detail(id)

    @staticmethod
    def _assert_idempotent_match(
        existing: MemberSubscriptionModel,
        data: MemberSubscriptionGrantSchema,
    ) -> None:
        mismatches: list[str] = []
        if existing.user_id != data.user_id:
            mismatches.append("用户")
        if existing.plan_id != data.plan_id:
            mismatches.append("套餐")
        if data.starts_at is not None and as_utc(existing.starts_at) != as_utc(data.starts_at):
            mismatches.append("生效时间")
        if data.expires_at is not None and as_utc(existing.expires_at) != as_utc(data.expires_at):
            mismatches.append("到期时间")
        if existing.grant_reason != data.grant_reason:
            mismatches.append("授权原因")
        if (existing.description or None) != (data.description or None):
            mismatches.append("内部备注")
        if mismatches:
            raise MemberSubscriptionService._conflict(f"幂等键已用于其他授权参数：{'、'.join(mismatches)}不一致")

    @staticmethod
    def effective_status(
        obj: MemberSubscriptionModel,
        now: datetime,
    ) -> SubscriptionEffectiveStatus:
        if obj.status == 1:
            return "revoked"
        starts_at = as_utc(obj.starts_at)
        expires_at = as_utc(obj.expires_at)
        if starts_at > now:
            return "upcoming"
        if expires_at <= now:
            return "expired"
        return "active"

    @classmethod
    def _to_schema(
        cls,
        obj: MemberSubscriptionModel,
        now: datetime,
    ) -> MemberSubscriptionOutSchema:
        return MemberSubscriptionOutSchema(
            id=obj.id,
            uuid=obj.uuid,
            is_deleted=obj.is_deleted,
            created_time=obj.created_time,
            updated_time=obj.updated_time,
            deleted_time=obj.deleted_time,
            created_id=obj.created_id,
            created_by=obj.created_by,
            updated_id=obj.updated_id,
            updated_by=obj.updated_by,
            deleted_id=obj.deleted_id,
            deleted_by=None,
            user_id=obj.user_id,
            username=obj.user.username,
            user_name=obj.user.name or obj.user.username,
            mobile=obj.user.mobile,
            plan_id=obj.plan_id,
            plan_code=obj.plan.plan_code,
            plan_name=obj.plan.plan_name,
            rank=obj.plan.rank,
            source=obj.source,
            source_ref=obj.source_ref,
            status=obj.status,
            effective_status=cls.effective_status(obj, now),
            starts_at=obj.starts_at,
            expires_at=obj.expires_at,
            revoked_at=obj.revoked_at,
            grant_reason=obj.grant_reason,
            revoke_reason=obj.revoke_reason,
            version_no=obj.version_no,
            description=obj.description,
        )

    @staticmethod
    def _conflict(message: str) -> CustomException:
        return CustomException(
            msg=message,
            code=RET.CONFLICT.code,
            status_code=RET.CONFLICT.code,
        )
