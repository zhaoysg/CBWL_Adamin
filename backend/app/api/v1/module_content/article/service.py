from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_content.category.model import ContentCategoryModel
from app.api.v1.module_membership.plan.model import MemberPlanModel
from app.common.enums import RET
from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict
from app.utils.xss_util import sanitize_html

from .crud import ContentCRUD
from .model import ContentModel
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


class ContentService:
    """投研内容工作流服务。

    所有状态变更都使用 ``version_no`` 乐观锁。Controller 不直接修改 ORM，
    以保证正文清理、会员套餐校验和状态机不能被绕过。
    """

    _ORDER_FIELDS = {
        "id",
        "title",
        "status",
        "is_pinned",
        "is_featured",
        "sort_no",
        "published_at",
        "created_time",
        "updated_time",
    }

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = ContentCRUD(auth, db)

    async def detail(self, id: int) -> ContentDetailSchema:
        obj = await self.crud.get_detail(id)
        if obj is None:
            raise CustomException(msg="投研内容不存在", status_code=RET.NOT_FOUND.code)
        return ContentDetailSchema.model_validate(obj)

    async def page(
        self,
        *,
        page_no: int,
        page_size: int,
        search: ContentQueryParam | None,
        order_by: list[dict[str, str]] | None,
    ) -> PageResultSchema[ContentListSchema]:
        return await self.crud.page_admin(
            page_no=page_no,
            page_size=page_size,
            search=search_to_dict(search),
            order_by=self._normalize_order(order_by),
        )

    async def create(self, data: ContentCreateSchema) -> ContentDetailSchema:
        await self._assert_category(data.category_id, require_enabled=True)
        await self._assert_slug_unique(data.slug)
        await self._assert_entitlement(data.access_level, data.plan_ids)

        payload = data.model_dump(exclude={"plan_ids"})
        payload["body"] = self._sanitize_body(data.body)
        payload.update(
            status=0,
            published_at=None,
            offline_at=None,
            version_no=1,
            like_count=0,
            comment_count=0,
        )
        obj = await self.crud.create(payload)
        await self.crud.replace_plan_ids(obj.id, data.plan_ids)
        return await self.detail(obj.id)

    async def update(self, id: int, data: ContentUpdateSchema) -> ContentDetailSchema:
        current = await self._get_locked(id, data.version_no)
        if current.status == 3:
            raise self._conflict("已归档内容不可直接编辑，请先复制为新草稿")

        patch = data.model_dump(exclude_unset=True, exclude={"version_no"})
        plan_ids_provided = "plan_ids" in patch
        requested_plan_ids = patch.pop("plan_ids", None)
        if not patch and not plan_ids_provided:
            raise CustomException(msg="未提供任何可更新字段", status_code=RET.BAD_REQUEST.code)

        final_category_id = patch.get("category_id", current.category_id)
        await self._assert_category(
            final_category_id,
            require_enabled=current.status == 1,
        )

        final_slug = patch.get("slug", current.slug)
        await self._assert_slug_unique(final_slug, exclude_id=id)

        if "body" in patch:
            patch["body"] = self._sanitize_body(patch["body"] or "")

        final_access_level = patch.get("access_level", current.access_level)
        if plan_ids_provided:
            final_plan_ids = requested_plan_ids or []
        elif final_access_level == "premium":
            final_plan_ids = current.plan_ids
        else:
            final_plan_ids = []
        await self._assert_entitlement(final_access_level, final_plan_ids)

        updated = await self.crud.update_with_version(
            content_id=id,
            expected_version=data.version_no,
            values=patch,
        )
        if not updated:
            raise self._conflict("内容已被其他运营人员修改，请刷新后重试")
        if final_plan_ids != current.plan_ids:
            await self.crud.replace_plan_ids(id, final_plan_ids)
        return await self.detail(id)

    async def publish(self, id: int, data: ContentTransitionSchema) -> ContentDetailSchema:
        current = await self._get_locked(id, data.version_no)
        if current.status not in {0, 2}:
            raise self._conflict("仅草稿或已下线内容可以发布")
        if not current.body.strip():
            raise CustomException(msg="正文为空，不能发布", status_code=RET.BAD_REQUEST.code)
        await self._assert_category(current.category_id, require_enabled=True)
        await self._assert_entitlement(current.access_level, current.plan_ids)

        published_at = data.published_at or datetime.now(UTC)
        await self._transition(
            current,
            data.version_no,
            status=1,
            published_at=published_at,
            offline_at=None,
        )
        return await self.detail(id)

    async def offline(self, id: int, data: ContentVersionSchema) -> ContentDetailSchema:
        current = await self._get_locked(id, data.version_no)
        if current.status != 1:
            raise self._conflict("仅已发布内容可以下线")
        await self._transition(
            current,
            data.version_no,
            status=2,
            offline_at=datetime.now(UTC),
            is_pinned=False,
            is_featured=False,
        )
        return await self.detail(id)

    async def archive(self, id: int, data: ContentVersionSchema) -> ContentDetailSchema:
        current = await self._get_locked(id, data.version_no)
        if current.status not in {0, 2}:
            raise self._conflict("仅草稿或已下线内容可以归档")
        await self._transition(
            current,
            data.version_no,
            status=3,
            is_pinned=False,
            is_featured=False,
        )
        return await self.detail(id)

    async def delete(self, data: ContentDeleteSchema) -> None:
        locked: list[ContentModel] = []
        for content_id in data.ids:
            obj = await self.crud.get_detail(content_id, for_update=True)
            if obj is None:
                raise CustomException(msg="部分投研内容不存在", status_code=RET.NOT_FOUND.code)
            locked.append(obj)

        invalid = [obj.title for obj in locked if obj.status not in {0, 3}]
        if invalid:
            raise self._conflict("仅草稿或已归档内容可以删除")
        await self.crud.delete(data.ids)

    async def _get_locked(self, id: int, expected_version: int) -> ContentModel:
        obj = await self.crud.get_detail(id, for_update=True)
        if obj is None:
            raise CustomException(msg="投研内容不存在", status_code=RET.NOT_FOUND.code)
        if obj.version_no != expected_version:
            raise self._conflict("内容版本已变化，请刷新后重试")
        return obj

    async def _transition(
        self,
        current: ContentModel,
        expected_version: int,
        **values: Any,
    ) -> None:
        updated = await self.crud.update_with_version(
            content_id=current.id,
            expected_version=expected_version,
            values=values,
        )
        if not updated:
            raise self._conflict("内容状态已被其他操作修改，请刷新后重试")

    async def _assert_category(self, category_id: int, *, require_enabled: bool) -> None:
        conditions = [
            ContentCategoryModel.id == category_id,
            ContentCategoryModel.is_deleted.is_(False),
        ]
        if require_enabled:
            conditions.append(ContentCategoryModel.status == 0)
        category = await self.db.scalar(select(ContentCategoryModel).where(*conditions).limit(1))
        if category is None:
            message = "内容分类不存在或已停用" if require_enabled else "内容分类不存在"
            raise CustomException(msg=message, status_code=RET.NOT_FOUND.code)

    async def _assert_slug_unique(self, slug: str, exclude_id: int | None = None) -> None:
        conditions = [ContentModel.slug == slug]
        if exclude_id is not None:
            conditions.append(ContentModel.id != exclude_id)
        existing = await self.db.scalar(select(ContentModel.id).where(*conditions).limit(1))
        if existing is not None:
            raise self._conflict("内容访问标识已存在；已删除内容也会保留该标识")

    async def _assert_entitlement(self, access_level: str, plan_ids: list[int]) -> None:
        if access_level != "premium":
            if plan_ids:
                raise CustomException(
                    msg="仅 premium 内容可以指定会员套餐",
                    status_code=RET.BAD_REQUEST.code,
                )
            return
        if not plan_ids:
            raise CustomException(
                msg="premium 内容必须指定至少一个启用的会员套餐",
                status_code=RET.BAD_REQUEST.code,
            )
        count = await self.db.scalar(
            select(func.count())
            .select_from(MemberPlanModel)
            .where(
                MemberPlanModel.id.in_(plan_ids),
                MemberPlanModel.status == 0,
                MemberPlanModel.is_deleted.is_(False),
            )
        )
        if count != len(set(plan_ids)):
            raise CustomException(
                msg="会员套餐不存在或已停用",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )

    @classmethod
    def _normalize_order(cls, order_by: list[dict[str, str]] | None) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in order_by or []:
            for field, direction in item.items():
                if field in cls._ORDER_FIELDS:
                    normalized.append({field: "desc" if direction.lower() == "desc" else "asc"})
        return normalized or [
            {"is_pinned": "desc"},
            {"sort_no": "asc"},
            {"updated_time": "desc"},
            {"id": "desc"},
        ]

    @staticmethod
    def _sanitize_body(body: str) -> str:
        return sanitize_html(body.replace("\x00", ""))

    @staticmethod
    def _conflict(message: str) -> CustomException:
        return CustomException(
            msg=message,
            code=RET.CONFLICT.code,
            status_code=RET.CONFLICT.code,
        )
