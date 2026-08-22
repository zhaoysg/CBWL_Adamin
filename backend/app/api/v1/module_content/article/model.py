from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import MappedBase, ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.api.v1.module_content.category.model import ContentCategoryModel


class ContentModel(ModelMixin, UserMixin):
    """投研内容主表。

    状态：0 草稿，1 已发布，2 已下线，3 已归档。
    访问等级：public / login / member / premium。
    """

    __tablename__ = "cw_content"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_cw_content_slug"),
        CheckConstraint("status IN (0, 1, 2, 3)", name="ck_cw_content_status"),
        CheckConstraint(
            "access_level IN ('public', 'login', 'member', 'premium')",
            name="ck_cw_content_access_level",
        ),
        CheckConstraint(
            "content_type IN ('article', 'research', 'trade', 'institution', 'macro', 'notice')",
            name="ck_cw_content_type",
        ),
        CheckConstraint("body_format = 'html'", name="ck_cw_content_body_format"),
        CheckConstraint("version_no >= 1", name="ck_cw_content_version"),
        CheckConstraint("like_count >= 0", name="ck_cw_content_like_count"),
        CheckConstraint("comment_count >= 0", name="ck_cw_content_comment_count"),
        Index(
            "ix_cw_content_admin_list",
            "status",
            "category_id",
            "updated_time",
            "id",
        ),
        Index(
            "ix_cw_content_public_feed",
            "status",
            "published_at",
            "sort_no",
            "id",
        ),
        Index("ix_cw_content_category_feed", "category_id", "status", "published_at"),
        {"comment": "财不外露投研内容"},
    )

    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cw_content_category.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="内容分类ID",
    )
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="article", comment="内容类型")
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True, comment="标题")
    slug: Mapped[str] = mapped_column(String(160), nullable=False, comment="稳定访问标识")
    summary: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="摘要")
    cover_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, comment="封面地址")
    body: Mapped[str] = mapped_column(
        Text().with_variant(LONGTEXT(), "mysql"),
        nullable=False,
        comment="正文HTML",
    )
    body_format: Mapped[str] = mapped_column(String(16), nullable=False, default="html", comment="正文格式")
    author_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="展示作者")
    access_level: Mapped[str] = mapped_column(String(32), nullable=False, default="public", comment="访问等级")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="状态")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True, comment="发布时间")
    offline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="下线时间")
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否置顶")
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否推荐")
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本")
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="点赞数")
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="评论数")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="运营备注")

    category: Mapped[ContentCategoryModel] = relationship(back_populates="contents", lazy="raise")
    content_plans: Mapped[list[ContentPlanModel]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    @property
    def category_name(self) -> str:
        return self.category.category_name

    @property
    def plan_ids(self) -> list[int]:
        return sorted(item.plan_id for item in self.content_plans)


class ContentPlanModel(MappedBase):
    """premium 内容与可访问会员套餐的关联。"""

    __tablename__ = "cw_content_plan"
    __table_args__ = (
        UniqueConstraint("content_id", "plan_id", name="uq_cw_content_plan"),
        Index("ix_cw_content_plan_plan", "plan_id", "content_id"),
        {"comment": "内容可访问会员套餐"},
    )

    content_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cw_content.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cw_member_plan.id", ondelete="RESTRICT", onupdate="CASCADE"),
        primary_key=True,
    )

    content: Mapped[ContentModel] = relationship(back_populates="content_plans")
