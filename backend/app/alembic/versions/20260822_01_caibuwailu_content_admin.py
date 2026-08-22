"""create 财不外露 membership and content administration tables

Revision ID: 20260822_01
Revises:
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "20260822_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_id", sa.Integer(), nullable=True),
        sa.Column("updated_id", sa.Integer(), nullable=True),
        sa.Column("deleted_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["updated_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["deleted_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.UniqueConstraint("uuid"),
    ]


def upgrade() -> None:
    op.create_table(
        "cw_member_plan",
        *_audit_columns(),
        sa.Column("plan_code", sa.String(length=64), nullable=False),
        sa.Column("plan_name", sa.String(length=128), nullable=False),
        sa.Column("level_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default=sa.text("'CNY'"), nullable=False),
        sa.Column("duration_days", sa.Integer(), server_default=sa.text("365"), nullable=False),
        sa.Column("benefits", sa.JSON(), nullable=False),
        sa.Column("status", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sort_no", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("level_no >= 1 AND level_no <= 100", name="ck_cw_member_plan_rank"),
        sa.CheckConstraint("price >= 0", name="ck_cw_member_plan_price"),
        sa.CheckConstraint("duration_days > 0", name="ck_cw_member_plan_duration"),
        sa.CheckConstraint("status IN (0, 1)", name="ck_cw_member_plan_status"),
        sa.UniqueConstraint("plan_code", name="uq_cw_member_plan_code"),
        sa.UniqueConstraint("plan_name", name="uq_cw_member_plan_name"),
        comment="财不外露会员套餐",
    )
    op.create_index("ix_cw_member_plan_enabled_sort", "cw_member_plan", ["status", "sort_no", "id"])
    op.create_index("ix_cw_member_plan_is_deleted", "cw_member_plan", ["is_deleted"])
    op.create_index("ix_cw_member_plan_created_time", "cw_member_plan", ["created_time"])
    op.create_index("ix_cw_member_plan_created_id", "cw_member_plan", ["created_id"])
    op.create_index("ix_cw_member_plan_updated_id", "cw_member_plan", ["updated_id"])
    op.create_index("ix_cw_member_plan_deleted_id", "cw_member_plan", ["deleted_id"])

    op.create_table(
        "cw_content_category",
        *_audit_columns(),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("category_code", sa.String(length=64), nullable=False),
        sa.Column("category_name", sa.String(length=128), nullable=False),
        sa.Column("icon", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sort_no", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN (0, 1)", name="ck_cw_content_category_status"),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["cw_content_category.id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("category_code", name="uq_cw_content_category_code"),
        comment="财不外露内容分类",
    )
    op.create_index(
        "ix_cw_content_category_parent_sort",
        "cw_content_category",
        ["parent_id", "status", "sort_no", "id"],
    )
    op.create_index("ix_cw_content_category_name", "cw_content_category", ["category_name"])
    op.create_index("ix_cw_content_category_is_deleted", "cw_content_category", ["is_deleted"])
    op.create_index("ix_cw_content_category_created_time", "cw_content_category", ["created_time"])
    op.create_index("ix_cw_content_category_created_id", "cw_content_category", ["created_id"])
    op.create_index("ix_cw_content_category_updated_id", "cw_content_category", ["updated_id"])
    op.create_index("ix_cw_content_category_deleted_id", "cw_content_category", ["deleted_id"])

    body_type = sa.Text().with_variant(mysql.LONGTEXT(), "mysql")
    op.create_table(
        "cw_content",
        *_audit_columns(),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=32), server_default=sa.text("'article'"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=True),
        sa.Column("cover_url", sa.String(length=1000), nullable=True),
        sa.Column("body", body_type, nullable=False),
        sa.Column("body_format", sa.String(length=16), server_default=sa.text("'html'"), nullable=False),
        sa.Column("author_name", sa.String(length=128), nullable=False),
        sa.Column("access_level", sa.String(length=32), server_default=sa.text("'public'"), nullable=False),
        sa.Column("status", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_featured", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sort_no", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("like_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("comment_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN (0, 1, 2, 3)", name="ck_cw_content_status"),
        sa.CheckConstraint(
            "access_level IN ('public', 'login', 'member', 'premium')",
            name="ck_cw_content_access_level",
        ),
        sa.CheckConstraint(
            "content_type IN ('article', 'research', 'trade', 'institution', 'macro', 'notice')",
            name="ck_cw_content_type",
        ),
        sa.CheckConstraint("body_format = 'html'", name="ck_cw_content_body_format"),
        sa.CheckConstraint("version_no >= 1", name="ck_cw_content_version"),
        sa.CheckConstraint("like_count >= 0", name="ck_cw_content_like_count"),
        sa.CheckConstraint("comment_count >= 0", name="ck_cw_content_comment_count"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["cw_content_category.id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("slug", name="uq_cw_content_slug"),
        comment="财不外露投研内容",
    )
    op.create_index(
        "ix_cw_content_admin_list",
        "cw_content",
        ["status", "category_id", "updated_time", "id"],
    )
    op.create_index(
        "ix_cw_content_public_feed",
        "cw_content",
        ["status", "published_at", "sort_no", "id"],
    )
    op.create_index(
        "ix_cw_content_category_feed",
        "cw_content",
        ["category_id", "status", "published_at"],
    )
    op.create_index("ix_cw_content_title", "cw_content", ["title"])
    op.create_index("ix_cw_content_published_at", "cw_content", ["published_at"])
    op.create_index("ix_cw_content_is_deleted", "cw_content", ["is_deleted"])
    op.create_index("ix_cw_content_created_time", "cw_content", ["created_time"])
    op.create_index("ix_cw_content_created_id", "cw_content", ["created_id"])
    op.create_index("ix_cw_content_updated_id", "cw_content", ["updated_id"])
    op.create_index("ix_cw_content_deleted_id", "cw_content", ["deleted_id"])

    op.create_table(
        "cw_content_plan",
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["cw_content.id"],
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["cw_member_plan.id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("content_id", "plan_id"),
        sa.UniqueConstraint("content_id", "plan_id", name="uq_cw_content_plan"),
        comment="内容可访问会员套餐",
    )
    op.create_index("ix_cw_content_plan_plan", "cw_content_plan", ["plan_id", "content_id"])


def downgrade() -> None:
    op.drop_index("ix_cw_content_plan_plan", table_name="cw_content_plan")
    op.drop_table("cw_content_plan")

    op.drop_index("ix_cw_content_deleted_id", table_name="cw_content")
    op.drop_index("ix_cw_content_updated_id", table_name="cw_content")
    op.drop_index("ix_cw_content_created_id", table_name="cw_content")
    op.drop_index("ix_cw_content_created_time", table_name="cw_content")
    op.drop_index("ix_cw_content_is_deleted", table_name="cw_content")
    op.drop_index("ix_cw_content_published_at", table_name="cw_content")
    op.drop_index("ix_cw_content_title", table_name="cw_content")
    op.drop_index("ix_cw_content_category_feed", table_name="cw_content")
    op.drop_index("ix_cw_content_public_feed", table_name="cw_content")
    op.drop_index("ix_cw_content_admin_list", table_name="cw_content")
    op.drop_table("cw_content")

    op.drop_index("ix_cw_content_category_deleted_id", table_name="cw_content_category")
    op.drop_index("ix_cw_content_category_updated_id", table_name="cw_content_category")
    op.drop_index("ix_cw_content_category_created_id", table_name="cw_content_category")
    op.drop_index("ix_cw_content_category_created_time", table_name="cw_content_category")
    op.drop_index("ix_cw_content_category_is_deleted", table_name="cw_content_category")
    op.drop_index("ix_cw_content_category_name", table_name="cw_content_category")
    op.drop_index("ix_cw_content_category_parent_sort", table_name="cw_content_category")
    op.drop_table("cw_content_category")

    op.drop_index("ix_cw_member_plan_deleted_id", table_name="cw_member_plan")
    op.drop_index("ix_cw_member_plan_updated_id", table_name="cw_member_plan")
    op.drop_index("ix_cw_member_plan_created_id", table_name="cw_member_plan")
    op.drop_index("ix_cw_member_plan_created_time", table_name="cw_member_plan")
    op.drop_index("ix_cw_member_plan_is_deleted", table_name="cw_member_plan")
    op.drop_index("ix_cw_member_plan_enabled_sort", table_name="cw_member_plan")
    op.drop_table("cw_member_plan")
