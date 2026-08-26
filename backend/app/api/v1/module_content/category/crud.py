from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import ContentCategoryModel
from .schema import ContentCategoryCreateSchema, ContentCategoryUpdateSchema


class ContentCategoryCRUD(CRUDBase[ContentCategoryModel, ContentCategoryCreateSchema, ContentCategoryUpdateSchema]):
    """内容分类数据访问层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=ContentCategoryModel, auth=auth, db=db)
