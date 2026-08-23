from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.validator import DateTimeStr

PortalContentType = Literal["article", "research", "trade", "institution", "macro", "notice"]
PortalAccessLevel = Literal["public", "login", "member", "premium"]


class PortalFeedItem(BaseModel):
    id: int
    category_id: int
    category_name: str
    content_type: PortalContentType
    title: str
    slug: str
    summary: str | None
    cover_url: str | None
    author_name: str
    access_level: PortalAccessLevel
    published_at: DateTimeStr
    is_pinned: bool
    is_featured: bool
    like_count: int
    comment_count: int


class PortalFeedResponse(BaseModel):
    page_no: int = Field(ge=1)
    page_size: int = Field(ge=1, le=50)
    total: int = Field(ge=0)
    has_next: bool
    items: list[PortalFeedItem] = Field(default_factory=list)


class PortalArticleResponse(PortalFeedItem):
    body: str
    body_format: Literal["html"]


class PortalMembershipItem(BaseModel):
    subscription_id: int
    plan_id: int
    plan_code: str
    plan_name: str
    rank: int
    starts_at: DateTimeStr
    expires_at: DateTimeStr


class PortalMembershipResponse(BaseModel):
    user_id: int
    active: bool
    highest_rank: int | None
    subscriptions: list[PortalMembershipItem] = Field(default_factory=list)
