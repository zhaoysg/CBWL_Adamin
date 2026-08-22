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


class ContentSection(BaseModel):
    heading: str | None = None
    paragraphs: list[str]


class ContentDetailResponse(BaseModel):
    id: int
    category: str
    title: str
    summary: str
    published_at: datetime
    access_level: AccessLevel
    like_count: int
    comment_count: int
    reading_minutes: int
    author: Author
    sections: list[ContentSection]


class LessonSummary(BaseModel):
    id: int
    title: str
    duration_minutes: int
    is_preview: bool = False
    learned: bool = False


class CourseChapter(BaseModel):
    id: int
    title: str
    lessons: list[LessonSummary]


class CourseDetailResponse(BaseModel):
    id: int
    level: str
    duration_hours: float
    lesson_count: int
    title: str
    summary: str
    price_label: str
    progress: int
    student_count: int
    highlights: list[str]
    chapters: list[CourseChapter]


class MemberPlan(BaseModel):
    code: str
    name: str
    period_label: str
    price: float
    original_price: float | None = None
    benefits: list[str]
    recommended: bool = False


class MemberCenterResponse(BaseModel):
    member: MemberSummary
    current_benefits: list[str]
    plans: list[MemberPlan]


class PortalHealth(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "caibuwailu-portal"
    version: str = "0.2.0"
