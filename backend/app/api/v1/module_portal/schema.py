from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

AccessLevel = Literal["public", "login", "member", "premium"]


class Author(BaseModel):
    id: int
    name: str
    title: str
    avatar_text: str = "研"


class PinnedItem(BaseModel):
    id: int
    title: str
    subtitle: str
    icon: str
    accent: str = "blue"


class CommentPreview(BaseModel):
    author: str
    avatar_text: str
    content: str


class FeedItem(BaseModel):
    id: int
    category: str
    content_type: str
    title: str
    summary: str
    published_at: datetime
    access_level: AccessLevel = "public"
    like_count: int = 0
    comment_count: int = 0
    author: Author
    liked_by_names: list[str] = Field(default_factory=list)
    comments: list[CommentPreview] = Field(default_factory=list)


class MemberSummary(BaseModel):
    id: int
    nickname: str
    level_name: str
    expire_date: date
    member_no: str
    joined_days: int
    slogan: str


class HomeResponse(BaseModel):
    brand_name: str
    brand_slogan: str
    joined_count: int
    member: MemberSummary
    pinned: list[PinnedItem]
    categories: list[str]
    feed: list[FeedItem]


class LiveSession(BaseModel):
    id: int
    schedule_text: str
    title: str
    subtitle: str
    access_label: str
    tags: list[str]
    reservation_count: int


class ColumnCard(BaseModel):
    id: int
    status: str
    title: str
    summary: str
    article_count: int
    access_label: str
    accent: str = "cyan"


class CourseCard(BaseModel):
    id: int
    level: str
    duration_hours: float
    lesson_count: int
    title: str
    summary: str
    tags: list[str]
    price_label: str
    badge: str | None = None
    progress: int = 0


class AcademyResponse(BaseModel):
    live_sessions: list[LiveSession]
    columns: list[ColumnCard]
    course_categories: list[str]
    courses: list[CourseCard]


class LearningStats(BaseModel):
    learning_courses: int
    reading_columns: int
    replay_count: int
    learning_hours: float


class RecentLearning(BaseModel):
    course_id: int
    category: str
    title: str
    lesson_title: str
    learned_lessons: int
    total_lessons: int
    progress: int
    last_studied_at: datetime


class Achievement(BaseModel):
    code: str
    name: str
    icon: str
    unlocked: bool


class AssetEntry(BaseModel):
    title: str
    meta: str
    badge: str | None = None
    icon: str


class ProfileResponse(BaseModel):
    member: MemberSummary
    benefits: list[str]
    stats: LearningStats
    recent_learning: RecentLearning
    achievements: list[Achievement]
    assets: list[AssetEntry]


class PortalHealth(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "caibuwailu-portal"
    version: str = "0.1.0"
