from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.api.v1.module_content.article.model import ContentModel


class ContentCategoryModel(ModelMixin, UserMixin):
    """投研内容分类。"""

    __tablename__ = "cw_content_category"
    __table_args__ = (
        UniqueConstraint("category_code", name="uq_cw_content_category_code"),
        CheckConstraint("status IN (0, 1)", name="ck_cw_content_category_status"),
        Index("ix_cw_content_category_parent_sort", "parent_id", "status", "sort_no", "id"),
        {"comment": "财不外露内容分类"},
    )

    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("cw_content_category.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
        index=True,
        comment="父分类ID",
    )
    category_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="分类编码")
    category_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True, comment="分类名称")
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="图标")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="状态(0启用 1停用)")
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="说明")

    parent: Mapped["ContentCategoryModel | None"] = relationship(
        remote_side="ContentCategoryModel.id",
        back_populates="children",
        foreign_keys=[parent_id],
        uselist=False,
    )
    children: Mapped[list["ContentCategoryModel"]] = relationship(
        back_populates="parent",
        foreign_keys="ContentCategoryModel.parent_id",
        order_by="ContentCategoryModel.sort_no, ContentCategoryModel.id",
    )
    contents: Mapped[list["ContentModel"]] = relationship(back_populates="category")
