from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema


class MemberPlanBaseSchema(BaseModel):
    plan_code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$", description="套餐编码")
    plan_name: str = Field(min_length=1, max_length=128, description="套餐名称")
    rank: int = Field(default=1, ge=1, le=100, description="权益等级")
    price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2, description="价格")
    currency: Literal["CNY"] = Field(default="CNY", description="币种")
    duration_days: int = Field(default=365, ge=1, le=3650, description="有效天数")
    benefits: list[str] = Field(default_factory=list, max_length=50, description="权益列表")
    status: int = Field(default=0, ge=0, le=1, description="状态(0启用 1停用)")
    sort_no: int = Field(default=0, ge=-100000, le=100000, description="排序")
    description: str | None = Field(default=None, max_length=1000, description="说明")

    @field_validator("plan_code", mode="before")
    @classmethod
    def normalize_plan_code(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("plan_name", mode="before")
    @classmethod
    def normalize_plan_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("benefits")
    @classmethod
    def normalize_benefits(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            normalized = item.strip()
            if not normalized:
                raise ValueError("会员权益不能包含空值")
            if len(normalized) > 128:
                raise ValueError("单项会员权益不能超过 128 个字符")
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result


class MemberPlanCreateSchema(MemberPlanBaseSchema):
    """创建会员套餐。"""


class MemberPlanUpdateSchema(MemberPlanBaseSchema):
    """完整更新会员套餐。"""


class MemberPlanOutSchema(MemberPlanBaseSchema, BaseSchema, UserBySchema):
    model_config = ConfigDict(from_attributes=True)


class MemberPlanOptionSchema(BaseModel):
    id: int
    plan_code: str
    plan_name: str
    rank: int

    model_config = ConfigDict(from_attributes=True)


class MemberPlanQueryParam(BaseQueryParam, UserByQueryParam):
    plan_code: str | None = Field(default=None, description="套餐编码", json_schema_extra={"q": "like"})
    plan_name: str | None = Field(default=None, description="套餐名称", json_schema_extra={"q": "like"})
    rank: int | None = Field(default=None, ge=1, le=100, description="权益等级", json_schema_extra={"q": "eq"})
    status: int | None = Field(default=None, ge=0, le=1, description="状态", json_schema_extra={"q": "eq"})
