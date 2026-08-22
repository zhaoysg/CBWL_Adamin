from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema, PageResultSchema

from .model import ContentModel, ContentPlanModel
from .schema import ContentCreateSchema, ContentListSchema, ContentUpdateSchema


class ContentCRUD(CRUDBase[ContentModel, ContentCreateSchema, ContentUpdateSchema]):
    """投研内容数据访问层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=ContentModel, auth=auth, db=db)

    async def get_detail(self, id: int, *, for_update: bool = False) -> ContentModel | None:
        conditions = await self._build_conditions(id=id)
        sql = select(ContentModel).where(*conditions)
        for option in self._loader_options(["category", "content_plans"]):
            sql = sql.options(option)
        if for_update:
            sql = sql.with_for_update()
        result = await self.db.execute(sql)
        return result.scalars().first()

    async def page_admin(
        self,
        *,
        page_no: int,
        page_size: int,
        search: dict[str, Any] | None,
        order_by: list[dict[str, str]],
    ) -> PageResultSchema[ContentListSchema]:
        return await self.page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=order_by,
            search=search,
            out_schema=ContentListSchema,
            preload=["category", "content_plans"],
        )

    async def replace_plan_ids(self, content_id: int, plan_ids: list[int]) -> None:
        await self.db.execute(delete(ContentPlanModel).where(ContentPlanModel.content_id == content_id))
        if plan_ids:
            self.db.add_all(
                ContentPlanModel(content_id=content_id, plan_id=plan_id)
                for plan_id in sorted(set(plan_ids))
            )
        await self.db.flush()

    async def update_with_version(
        self,
        *,
        content_id: int,
        expected_version: int,
        values: dict[str, Any],
    ) -> bool:
        payload = dict(values)
        payload.pop("version_no", None)
        payload["version_no"] = ContentModel.version_no + 1
        payload["updated_time"] = datetime.now(UTC)
        if self.auth.user.id:
            payload["updated_id"] = self.auth.user.id

        result = await self.db.execute(
            update(ContentModel)
            .where(
                ContentModel.id == content_id,
                ContentModel.version_no == expected_version,
                ContentModel.is_deleted.is_(False),
            )
            .values(**payload)
        )
        await self.db.flush()
        return bool(getattr(result, "rowcount", 0) == 1)
