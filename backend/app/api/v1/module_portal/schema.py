from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AccessLevel = Literal["public", "login", "member", "premium"]
PinnedTargetType = Literal["content", "academy", "member"]


class PortalModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Author(PortalModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=128)
    avatar_text: str = Field(default="研", min_length=1, max_length=4)


class PinnedItem(PortalModel):
    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    subtitle: str = Field(min_length=1, max_length=500)
    icon: str = Field(min_length=1, max_length=64)
    accent: str = Field(default="blue", min_length=1, max_length=32)
    target_type: PinnedTargetType
    target_id: int | None = Field(default=None, gt=0)


class CommentPreview(PortalModel):
    author: str = Field(min_length=1, max_length=128)
    avatar_text: str = Field(min_length=1, max_length=4)
    content: str = Field(min_length=1, max_length=500)


class FeedItem(PortalModel):
    id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=128)
    content_type: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=1000)
    published_at: datetime
    access_level: AccessLevel = "public"
    like_count: int = Field(default=0, ge=0)
    comment_count: int = Field(default=0, ge=0)
    author: Author
    liked_by_names: list[str] = Field(default_factory=list, max_length=20)
    comments: list[CommentPreview] = Field(default_factory=list, max_length=10)


class MemberSummary(PortalModel):
    id: int = Field(gt=0)
    nickname: str = Field(min_length=1, max_length=128)
    level_name: str = Field(min_length=1, max_length=128)
    expire_date: date
    member_no: str = Field(min_length=1, max_length=64)
    joined_days: int = Field(ge=0)
    slogan: str = Field(min_length=1, max_length=500)


class HomeResponse(PortalModel):
    brand_name: str = Field(min_length=1, max_length=64)
    brand_slogan: str = Field(min_length=1, max_length=255)
    joined_count: int = Field(ge=0)
    member: MemberSummary
    pinned: list[PinnedItem] = Field(max_length=20)
    categories: list[str] = Field(min_length=1, max_length=30)
    feed: list[FeedItem] = Field(max_length=100)


class LiveSession(PortalModel):
    id: int = Field(gt=0)
    schedule_text: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    subtitle: str = Field(min_length=1, max_length=500)
    access_label: str = Field(min_length=1, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=20)
    reservation_count: int = Field(ge=0)


class ColumnCard(PortalModel):
    id: int = Field(gt=0)
    status: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=1000)
    article_count: int = Field(ge=0)
    access_label: str = Field(min_length=1, max_length=64)
    accent: str = Field(default="cyan", min_length=1, max_length=32)


class CourseCard(PortalModel):
    id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=64)
    level: str = Field(min_length=1, max_length=64)
    duration_hours: float = Field(gt=0, le=10000)
    lesson_count: int = Field(gt=0, le=10000)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    price_label: str = Field(min_length=1, max_length=64)
    badge: str | None = Field(default=None, max_length=64)
    progress: int = Field(default=0, ge=0, le=100)


class AcademyResponse(PortalModel):
    live_sessions: list[LiveSession] = Field(max_length=50)
    columns: list[ColumnCard] = Field(max_length=100)
    course_categories: list[str] = Field(min_length=1, max_length=50)
    courses: list[CourseCard] = Field(max_length=200)


class LearningStats(PortalModel):
    learning_courses: int = Field(ge=0)
    reading_columns: int = Field(ge=0)
    replay_count: int = Field(ge=0)
    learning_hours: float = Field(ge=0, le=1_000_000)


class RecentLearning(PortalModel):
    course_id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    lesson_title: str = Field(min_length=1, max_length=255)
    learned_lessons: int = Field(ge=0)
    total_lessons: int = Field(gt=0)
    progress: int = Field(ge=0, le=100)
    last_studied_at: datetime


class Achievement(PortalModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=128)
    icon: str = Field(min_length=1, max_length=64)
    unlocked: bool


class AssetEntry(PortalModel):
    title: str = Field(min_length=1, max_length=255)
    meta: str = Field(min_length=1, max_length=128)
    badge: str | None = Field(default=None, max_length=64)
    icon: str = Field(min_length=1, max_length=64)


class ProfileResponse(PortalModel):
    member: MemberSummary
    benefits: list[str] = Field(max_length=50)
    stats: LearningStats
    recent_learning: RecentLearning
    achievements: list[Achievement] = Field(max_length=100)
    assets: list[AssetEntry] = Field(max_length=100)


class ContentSection(PortalModel):
    heading: str | None = Field(default=None, max_length=255)
    paragraphs: list[str] = Field(min_length=1, max_length=50)


class ContentDetailResponse(PortalModel):
    id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=1000)
    published_at: datetime
    access_level: AccessLevel
    like_count: int = Field(ge=0)
    comment_count: int = Field(ge=0)
    reading_minutes: int = Field(gt=0, le=1440)
    author: Author
    sections: list[ContentSection] = Field(min_length=1, max_length=100)


class LessonSummary(PortalModel):
    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    duration_minutes: int = Field(ge=0, le=1440)
    is_preview: bool = False
    learned: bool = False


class CourseChapter(PortalModel):
    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    lessons: list[LessonSummary] = Field(min_length=1, max_length=500)


class CourseDetailResponse(PortalModel):
    id: int = Field(gt=0)
    category: str = Field(min_length=1, max_length=64)
    level: str = Field(min_length=1, max_length=64)
    duration_hours: float = Field(gt=0, le=10000)
    lesson_count: int = Field(gt=0, le=10000)
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=1000)
    price_label: str = Field(min_length=1, max_length=64)
    progress: int = Field(ge=0, le=100)
    student_count: int = Field(ge=0)
    highlights: list[str] = Field(max_length=50)
    chapters: list[CourseChapter] = Field(min_length=1, max_length=100)


class MemberPlan(PortalModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=128)
    period_label: str = Field(min_length=1, max_length=128)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    original_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    benefits: list[str] = Field(min_length=1, max_length=50)
    recommended: bool = False


class MemberCenterResponse(PortalModel):
    member: MemberSummary
    current_benefits: list[str] = Field(max_length=50)
    plans: list[MemberPlan] = Field(min_length=1, max_length=50)


class PortalHealth(PortalModel):
    status: Literal["ok", "degraded"]
    service: str = "caibuwailu-portal"
    version: str = "0.2.1"
    environment: str
    data_source: Literal["demo", "database"]
    production_ready: bool
    reason: str | None = None
