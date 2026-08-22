from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema


class ContentCategoryBaseSchema(BaseModel):
    parent_id: int | None = Field(default=None, ge=1, description="父分类ID")
    category_code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$", description="分类编码")
    category_name: str = Field(min_length=1, max_length=128, description="分类名称")
    icon: str | None = Field(default=None, max_length=255, description="图标")
    status: int = Field(default=0, ge=0, le=1, description="状态(0启用 1停用)")
    sort_no: int = Field(default=0, ge=-100000, le=100000, description="排序")
    description: str | None = Field(default=None, max_length=1000, description="说明")

    @field_validator("category_code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("category_name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class ContentCategoryCreateSchema(ContentCategoryBaseSchema):
    """创建内容分类。"""


class ContentCategoryUpdateSchema(ContentCategoryBaseSchema):
    """完整更新内容分类。"""


class ContentCategoryOutSchema(ContentCategoryBaseSchema, BaseSchema, UserBySchema):
    model_config = ConfigDict(from_attributes=True)


class ContentCategoryTreeSchema(BaseModel):
    id: int
    parent_id: int | None
    category_code: str
    category_name: str
    icon: str | None
    status: int
    sort_no: int
    children: list[ContentCategoryTreeSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ContentCategoryOptionSchema(BaseModel):
    id: int
    parent_id: int | None
    category_code: str
    category_name: str
    status: int

    model_config = ConfigDict(from_attributes=True)


class ContentCategoryQueryParam(BaseQueryParam, UserByQueryParam):
    parent_id: int | None = Field(default=None, ge=1, description="父分类ID", json_schema_extra={"q": "eq"})
    category_code: str | None = Field(default=None, description="分类编码", json_schema_extra={"q": "like"})
    category_name: str | None = Field(default=None, description="分类名称", json_schema_extra={"q": "like"})
    status: int | None = Field(default=None, ge=0, le=1, description="状态", json_schema_extra={"q": "eq"})
