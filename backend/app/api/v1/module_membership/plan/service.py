from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import RET
from app.core.base_schema import AuthSchema, BatchSetAvailable, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict

from .crud import MemberPlanCRUD
from .model import MemberPlanModel
from .schema import (
    MemberPlanCreateSchema,
    MemberPlanOptionSchema,
    MemberPlanOutSchema,
    MemberPlanQueryParam,
    MemberPlanUpdateSchema,
)


class MemberPlanService:
    """会员套餐领域服务。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = MemberPlanCRUD(auth, db)

    async def detail(self, id: int) -> MemberPlanOutSchema:
        obj = await self.crud.get_or_404(id=id, msg="会员套餐不存在")
        return MemberPlanOutSchema.model_validate(obj)

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: MemberPlanQueryParam | None,
        order_by: list[dict[str, str]] | None,
    ) -> PageResultSchema[MemberPlanOutSchema]:
        return await self.crud.page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=order_by or [{"sort_no": "asc"}, {"id": "asc"}],
            search=search_to_dict(search),
            out_schema=MemberPlanOutSchema,
        )

    async def options(self) -> list[MemberPlanOptionSchema]:
        objs = await self.crud.get_list(
            search={"status": ("eq", 0)},
            order_by=[{"sort_no": "asc"}, {"rank": "asc"}, {"id": "asc"}],
        )
        return [MemberPlanOptionSchema.model_validate(obj) for obj in objs]

    async def create(self, data: MemberPlanCreateSchema) -> MemberPlanOutSchema:
        if await self.crud.exists(plan_code=data.plan_code):
            raise CustomException(
                msg="套餐编码已存在",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        if await self.crud.exists(plan_name=data.plan_name):
            raise CustomException(
                msg="套餐名称已存在",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        obj = await self.crud.create(data=data)
        return await self.detail(obj.id)

    async def update(self, id: int, data: MemberPlanUpdateSchema) -> MemberPlanOutSchema:
        await self.crud.get_or_404(id=id, msg="会员套餐不存在")
        same_code = await self.crud.get(plan_code=data.plan_code)
        if same_code and same_code.id != id:
            raise CustomException(
                msg="套餐编码已存在",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        same_name = await self.crud.get(plan_name=data.plan_name)
        if same_name and same_name.id != id:
            raise CustomException(
                msg="套餐名称已存在",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        await self.crud.update(id=id, data=data)
        return await self.detail(id)

    async def delete(self, ids: list[int]) -> None:
        unique_ids = sorted(set(ids))
        if not unique_ids:
            raise CustomException(msg="请选择需要删除的会员套餐", status_code=RET.BAD_REQUEST.code)

        objs = await self.crud.get_list(search={"id": ("in", unique_ids)})
        if len(objs) != len(unique_ids):
            raise CustomException(msg="部分会员套餐不存在", status_code=RET.NOT_FOUND.code)

        # 延迟导入，避免会员、内容和订阅模型在模块初始化阶段形成循环依赖。
        from app.api.v1.module_content.article.model import ContentPlanModel
        from app.api.v1.module_membership.subscription.model import MemberSubscriptionModel

        association_count = await self.db.scalar(
            select(func.count())
            .select_from(ContentPlanModel)
            .where(ContentPlanModel.plan_id.in_(unique_ids))
        )
        subscription_count = await self.db.scalar(
            select(func.count())
            .select_from(MemberSubscriptionModel)
            .where(
                MemberSubscriptionModel.plan_id.in_(unique_ids),
                MemberSubscriptionModel.is_deleted.is_(False),
            )
        )
        if association_count or subscription_count:
            raise CustomException(
                msg="套餐仍被内容权限或会员订阅引用，请停用而不是删除",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        await self.crud.delete(ids=unique_ids)

    async def set_available(self, data: BatchSetAvailable) -> None:
        unique_ids = sorted(set(data.ids))
        if not unique_ids:
            raise CustomException(msg="请选择需要修改状态的会员套餐", status_code=RET.BAD_REQUEST.code)
        count = await self.db.scalar(
            select(func.count())
            .select_from(MemberPlanModel)
            .where(
                MemberPlanModel.id.in_(unique_ids),
                MemberPlanModel.is_deleted.is_(False),
            )
        )
        if count != len(unique_ids):
            raise CustomException(msg="部分会员套餐不存在", status_code=RET.NOT_FOUND.code)

        if data.status == 1:
            from app.api.v1.module_content.article.model import ContentModel, ContentPlanModel
            from app.api.v1.module_membership.subscription.model import MemberSubscriptionModel

            published_reference_count = await self.db.scalar(
                select(func.count())
                .select_from(ContentPlanModel)
                .join(ContentModel, ContentModel.id == ContentPlanModel.content_id)
                .where(
                    ContentPlanModel.plan_id.in_(unique_ids),
                    ContentModel.status == 1,
                    ContentModel.is_deleted.is_(False),
                )
            )
            active_subscription_count = await self.db.scalar(
                select(func.count())
                .select_from(MemberSubscriptionModel)
                .where(
                    MemberSubscriptionModel.plan_id.in_(unique_ids),
                    MemberSubscriptionModel.status == "active",
                    MemberSubscriptionModel.is_deleted.is_(False),
                )
            )
            if published_reference_count or active_subscription_count:
                raise CustomException(
                    msg="套餐仍被已发布内容或有效订阅使用，请先完成业务迁移",
                    code=RET.CONFLICT.code,
                    status_code=RET.CONFLICT.code,
                )
        await self.crud.set(ids=unique_ids, status=data.status)
