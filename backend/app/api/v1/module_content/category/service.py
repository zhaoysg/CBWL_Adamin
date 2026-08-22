from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import RET
from app.core.base_schema import AuthSchema, BatchSetAvailable, PageResultSchema
from app.core.exceptions import CustomException
from app.utils.common_util import search_to_dict

from .crud import ContentCategoryCRUD
from .model import ContentCategoryModel
from .schema import (
    ContentCategoryCreateSchema,
    ContentCategoryOptionSchema,
    ContentCategoryOutSchema,
    ContentCategoryQueryParam,
    ContentCategoryTreeSchema,
    ContentCategoryUpdateSchema,
)


class ContentCategoryService:
    """内容分类领域服务。"""

    MAX_TREE_DEPTH = 64

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        self.auth = auth
        self.db = db
        self.crud = ContentCategoryCRUD(auth, db)

    async def detail(self, id: int) -> ContentCategoryOutSchema:
        obj = await self.crud.get_or_404(id=id, msg="内容分类不存在")
        return ContentCategoryOutSchema.model_validate(obj)

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: ContentCategoryQueryParam | None,
        order_by: list[dict[str, str]] | None,
    ) -> PageResultSchema[ContentCategoryOutSchema]:
        return await self.crud.page(
            offset=(page_no - 1) * page_size,
            limit=page_size,
            order_by=order_by or [{"sort_no": "asc"}, {"id": "asc"}],
            search=search_to_dict(search),
            out_schema=ContentCategoryOutSchema,
        )

    async def tree(self, enabled_only: bool = False) -> list[ContentCategoryTreeSchema]:
        search = {"status": ("eq", 0)} if enabled_only else None
        objs = await self.crud.get_list(
            search=search,
            order_by=[{"sort_no": "asc"}, {"id": "asc"}],
        )
        nodes: dict[int, dict] = {
            obj.id: {
                "id": obj.id,
                "parent_id": obj.parent_id,
                "category_code": obj.category_code,
                "category_name": obj.category_name,
                "icon": obj.icon,
                "status": obj.status,
                "sort_no": obj.sort_no,
                "children": [],
            }
            for obj in objs
        }
        roots: list[dict] = []
        for obj in objs:
            node = nodes[obj.id]
            if obj.parent_id is not None and obj.parent_id in nodes:
                nodes[obj.parent_id]["children"].append(node)
            else:
                roots.append(node)
        return [ContentCategoryTreeSchema.model_validate(node) for node in roots]

    async def options(self) -> list[ContentCategoryOptionSchema]:
        objs = await self.crud.get_list(
            search={"status": ("eq", 0)},
            order_by=[{"sort_no": "asc"}, {"id": "asc"}],
        )
        return [ContentCategoryOptionSchema.model_validate(obj) for obj in objs]

    async def create(self, data: ContentCategoryCreateSchema) -> ContentCategoryOutSchema:
        await self._assert_parent(data.parent_id)
        await self._assert_unique(data.category_code, data.category_name, data.parent_id)
        obj = await self.crud.create(data=data)
        return await self.detail(obj.id)

    async def update(self, id: int, data: ContentCategoryUpdateSchema) -> ContentCategoryOutSchema:
        await self.crud.get_or_404(id=id, msg="内容分类不存在")
        await self._assert_parent(data.parent_id, category_id=id)
        await self._assert_unique(data.category_code, data.category_name, data.parent_id, exclude_id=id)
        await self.crud.update(id=id, data=data)
        return await self.detail(id)

    async def delete(self, ids: list[int]) -> None:
        unique_ids = sorted(set(ids))
        if not unique_ids:
            raise CustomException(msg="请选择需要删除的内容分类", status_code=RET.BAD_REQUEST.code)

        existing_count = await self.db.scalar(
            select(func.count()).select_from(ContentCategoryModel).where(
                ContentCategoryModel.id.in_(unique_ids),
                ContentCategoryModel.is_deleted.is_(False),
            )
        )
        if existing_count != len(unique_ids):
            raise CustomException(msg="部分内容分类不存在", status_code=RET.NOT_FOUND.code)

        external_child_count = await self.db.scalar(
            select(func.count()).select_from(ContentCategoryModel).where(
                ContentCategoryModel.parent_id.in_(unique_ids),
                ContentCategoryModel.id.not_in(unique_ids),
                ContentCategoryModel.is_deleted.is_(False),
            )
        )
        if external_child_count:
            raise CustomException(
                msg="分类仍包含未选择的子分类，不能删除",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )

        from app.api.v1.module_content.article.model import ContentModel

        content_count = await self.db.scalar(
            select(func.count()).select_from(ContentModel).where(
                ContentModel.category_id.in_(unique_ids),
                ContentModel.is_deleted.is_(False),
            )
        )
        if content_count:
            raise CustomException(
                msg="分类下仍有内容，不能删除",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        await self.crud.delete(ids=unique_ids)

    async def set_available(self, data: BatchSetAvailable) -> None:
        unique_ids = sorted(set(data.ids))
        if not unique_ids:
            raise CustomException(msg="请选择需要修改状态的内容分类", status_code=RET.BAD_REQUEST.code)

        objs = await self.crud.get_list(search={"id": ("in", unique_ids)})
        if len(objs) != len(unique_ids):
            raise CustomException(msg="部分内容分类不存在", status_code=RET.NOT_FOUND.code)

        if data.status == 0:
            parent_ids = {obj.parent_id for obj in objs if obj.parent_id is not None and obj.parent_id not in unique_ids}
            if parent_ids:
                disabled_parent_count = await self.db.scalar(
                    select(func.count()).select_from(ContentCategoryModel).where(
                        ContentCategoryModel.id.in_(parent_ids),
                        or_(ContentCategoryModel.status != 0, ContentCategoryModel.is_deleted.is_(True)),
                    )
                )
                if disabled_parent_count:
                    raise CustomException(
                        msg="存在停用的父分类，不能启用子分类",
                        code=RET.CONFLICT.code,
                        status_code=RET.CONFLICT.code,
                    )
        await self.crud.set(ids=unique_ids, status=data.status)

    async def _assert_parent(self, parent_id: int | None, category_id: int | None = None) -> None:
        if parent_id is None:
            return
        if category_id is not None and parent_id == category_id:
            raise CustomException(msg="父分类不能选择自身", status_code=RET.BAD_REQUEST.code)

        current = await self.crud.get(id=parent_id)
        if current is None:
            raise CustomException(msg="父分类不存在", status_code=RET.NOT_FOUND.code)

        visited: set[int] = set()
        depth = 0
        while current is not None:
            if current.id in visited:
                raise CustomException(msg="分类层级数据存在循环，请先修复数据", status_code=RET.CONFLICT.code)
            visited.add(current.id)
            if category_id is not None and current.id == category_id:
                raise CustomException(msg="不能将分类移动到其子分类下", status_code=RET.CONFLICT.code)
            if current.parent_id is None:
                break
            depth += 1
            if depth > self.MAX_TREE_DEPTH:
                raise CustomException(msg="分类层级超过系统限制", status_code=RET.CONFLICT.code)
            current = await self.crud.get(id=current.parent_id)

    async def _assert_unique(
        self,
        category_code: str,
        category_name: str,
        parent_id: int | None,
        exclude_id: int | None = None,
    ) -> None:
        conditions = [
            ContentCategoryModel.is_deleted.is_(False),
            or_(
                ContentCategoryModel.category_code == category_code,
                and_(
                    ContentCategoryModel.category_name == category_name,
                    ContentCategoryModel.parent_id.is_(None)
                    if parent_id is None
                    else ContentCategoryModel.parent_id == parent_id,
                ),
            ),
        ]
        if exclude_id is not None:
            conditions.append(ContentCategoryModel.id != exclude_id)
        obj = await self.db.scalar(select(ContentCategoryModel).where(*conditions).limit(1))
        if obj is None:
            return
        if obj.category_code == category_code:
            raise CustomException(
                msg="分类编码已存在",
                code=RET.CONFLICT.code,
                status_code=RET.CONFLICT.code,
            )
        raise CustomException(
            msg="同级分类名称已存在",
            code=RET.CONFLICT.code,
            status_code=RET.CONFLICT.code,
        )
