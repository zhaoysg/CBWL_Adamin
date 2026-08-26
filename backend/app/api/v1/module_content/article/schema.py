from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.base_schema import BaseQueryParam, BaseSchema, UserByQueryParam, UserBySchema
from app.core.validator import DateTimeStr

ContentType = Literal["article", "research", "trade", "institution", "macro", "notice"]
ContentAccessLevel = Literal["public", "login", "member", "premium"]
ContentBodyFormat = Literal["html"]


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_cover_url(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if "\x00" in normalized:
        raise ValueError("封面地址包含非法字符")
    if normalized.startswith("/") and not normalized.startswith("//"):
        return normalized
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("封面地址仅支持站内绝对路径或 HTTP/HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("封面地址不能包含认证信息")
    return normalized


def _normalize_plan_ids(values: list[int]) -> list[int]:
    return sorted(set(values))


class ContentCreateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category_id: int = Field(ge=1, description="内容分类ID")
    content_type: ContentType = Field(default="article", description="内容类型")
    title: str = Field(min_length=1, max_length=255, description="标题")
    slug: str = Field(
        min_length=2,
        max_length=160,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="稳定访问标识",
    )
    summary: str | None = Field(default=None, max_length=1000, description="摘要")
    cover_url: str | None = Field(default=None, max_length=1000, description="封面地址")
    body: str = Field(default="", max_length=2_000_000, description="正文HTML")
    body_format: ContentBodyFormat = Field(default="html", description="正文格式")
    author_name: str = Field(min_length=1, max_length=128, description="展示作者")
    access_level: ContentAccessLevel = Field(default="public", description="访问等级")
    plan_ids: list[int] = Field(default_factory=list, max_length=100, description="premium可访问套餐")
    is_pinned: bool = Field(default=False, description="是否置顶")
    is_featured: bool = Field(default=False, description="是否推荐")
    sort_no: int = Field(default=0, ge=-100000, le=100000, description="排序")
    description: str | None = Field(default=None, max_length=2000, description="运营备注")

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("summary", "description", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("cover_url", mode="before")
    @classmethod
    def validate_cover_url(cls, value: str | None) -> str | None:
        return _validate_cover_url(value)

    @field_validator("plan_ids")
    @classmethod
    def normalize_plan_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("会员套餐ID必须为正整数")
        return _normalize_plan_ids(value)

    @model_validator(mode="after")
    def validate_entitlement(self):
        if self.access_level == "premium" and not self.plan_ids:
            raise ValueError("premium 内容必须指定至少一个会员套餐")
        if self.access_level != "premium" and self.plan_ids:
            raise ValueError("仅 premium 内容可以指定会员套餐")
        return self


class ContentUpdateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version_no: int = Field(ge=1, description="乐观锁版本")
    category_id: int | None = Field(default=None, ge=1, description="内容分类ID")
    content_type: ContentType | None = Field(default=None, description="内容类型")
    title: str | None = Field(default=None, min_length=1, max_length=255, description="标题")
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=160,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="稳定访问标识",
    )
    summary: str | None = Field(default=None, max_length=1000, description="摘要")
    cover_url: str | None = Field(default=None, max_length=1000, description="封面地址")
    body: str | None = Field(default=None, max_length=2_000_000, description="正文HTML")
    body_format: ContentBodyFormat | None = Field(default=None, description="正文格式")
    author_name: str | None = Field(default=None, min_length=1, max_length=128, description="展示作者")
    access_level: ContentAccessLevel | None = Field(default=None, description="访问等级")
    plan_ids: list[int] | None = Field(default=None, max_length=100, description="premium可访问套餐")
    is_pinned: bool | None = Field(default=None, description="是否置顶")
    is_featured: bool | None = Field(default=None, description="是否推荐")
    sort_no: int | None = Field(default=None, ge=-100000, le=100000, description="排序")
    description: str | None = Field(default=None, max_length=2000, description="运营备注")

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None

    @field_validator("summary", "description", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("cover_url", mode="before")
    @classmethod
    def validate_cover_url(cls, value: str | None) -> str | None:
        return _validate_cover_url(value)

    @field_validator("plan_ids")
    @classmethod
    def normalize_plan_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(item <= 0 for item in value):
            raise ValueError("会员套餐ID必须为正整数")
        return _normalize_plan_ids(value)


class ContentTransitionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_no: int = Field(ge=1, description="乐观锁版本")
    published_at: datetime | None = Field(default=None, description="发布时间")

    @field_validator("published_at")
    @classmethod
    def validate_published_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("发布时间必须包含时区")
        return value


class ContentVersionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_no: int = Field(ge=1, description="乐观锁版本")


class ContentDeleteSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[int] = Field(min_length=1, max_length=100, description="内容ID列表")

    @field_validator("ids")
    @classmethod
    def normalize_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("内容ID必须为正整数")
        return sorted(set(value))


class ContentListSchema(BaseSchema, UserBySchema):
    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_name: str
    content_type: ContentType
    title: str
    slug: str
    summary: str | None
    cover_url: str | None
    author_name: str
    access_level: ContentAccessLevel
    plan_ids: list[int] = Field(default_factory=list)
    status: int
    published_at: DateTimeStr | None
    offline_at: DateTimeStr | None
    is_pinned: bool
    is_featured: bool
    sort_no: int
    version_no: int
    like_count: int
    comment_count: int
    description: str | None


class ContentDetailSchema(ContentListSchema):
    body: str
    body_format: ContentBodyFormat


class ContentQueryParam(BaseQueryParam, UserByQueryParam):
    category_id: int | None = Field(default=None, ge=1, description="内容分类", json_schema_extra={"q": "eq"})
    content_type: ContentType | None = Field(default=None, description="内容类型", json_schema_extra={"q": "eq"})
    title: str | None = Field(default=None, description="标题", json_schema_extra={"q": "like"})
    slug: str | None = Field(default=None, description="访问标识", json_schema_extra={"q": "like"})
    author_name: str | None = Field(default=None, description="作者", json_schema_extra={"q": "like"})
    access_level: ContentAccessLevel | None = Field(default=None, description="访问等级", json_schema_extra={"q": "eq"})
    status: int | None = Field(default=None, ge=0, le=3, description="状态", json_schema_extra={"q": "eq"})
    is_pinned: bool | None = Field(default=None, description="是否置顶", json_schema_extra={"q": "eq"})
    is_featured: bool | None = Field(default=None, description="是否推荐", json_schema_extra={"q": "eq"})
    published_at: list[DateTimeStr] | None = Field(default=None, description="发布时间范围")
