from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_crud import CRUDBase
from app.core.base_schema import AuthSchema

from .model import MemberPlanModel
from .schema import MemberPlanCreateSchema, MemberPlanUpdateSchema


class MemberPlanCRUD(CRUDBase[MemberPlanModel, MemberPlanCreateSchema, MemberPlanUpdateSchema]):
    """会员套餐数据访问层。"""

    def __init__(self, auth: AuthSchema, db: AsyncSession) -> None:
        super().__init__(model=MemberPlanModel, auth=auth, db=db)
