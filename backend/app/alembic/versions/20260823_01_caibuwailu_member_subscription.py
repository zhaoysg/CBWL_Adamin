"""create 财不外露 member subscriptions

Revision ID: 20260823_01
Revises: 20260822_01
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_01"
down_revision: str | None = "20260822_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cw_member_subscription",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_id", sa.Integer(), nullable=True),
        sa.Column("updated_id", sa.Integer(), nullable=True),
        sa.Column("deleted_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=False),
        sa.Column("status", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grant_reason", sa.String(length=500), nullable=False),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True),
        sa.Column("version_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "source IN ('manual', 'payment', 'migration', 'promotion')",
            name="ck_cw_member_subscription_source",
        ),
        sa.CheckConstraint("status IN (0, 1)", name="ck_cw_member_subscription_status"),
        sa.CheckConstraint("expires_at > starts_at", name="ck_cw_member_subscription_window"),
        sa.CheckConstraint("version_no >= 1", name="ck_cw_member_subscription_version"),
        sa.ForeignKeyConstraint(
            ["created_id"],
            ["sys_user.id"],
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_id"],
            ["sys_user.id"],
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_id"],
            ["sys_user.id"],
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["sys_user.id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["cw_member_plan.id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint(
            "source",
            "source_ref",
            name="uq_cw_member_subscription_source_ref",
        ),
        comment="财不外露用户会员订阅",
    )
    op.create_index(
        "ix_cw_member_subscription_user_window",
        "cw_member_subscription",
        ["user_id", "status", "starts_at", "expires_at", "id"],
    )
    op.create_index(
        "ix_cw_member_subscription_plan_window",
        "cw_member_subscription",
        ["plan_id", "status", "expires_at", "id"],
    )
    op.create_index(
        "ix_cw_member_subscription_expiry",
        "cw_member_subscription",
        ["status", "expires_at", "id"],
    )
    op.create_index("ix_cw_member_subscription_is_deleted", "cw_member_subscription", ["is_deleted"])
    op.create_index("ix_cw_member_subscription_created_time", "cw_member_subscription", ["created_time"])
    op.create_index("ix_cw_member_subscription_created_id", "cw_member_subscription", ["created_id"])
    op.create_index("ix_cw_member_subscription_updated_id", "cw_member_subscription", ["updated_id"])
    op.create_index("ix_cw_member_subscription_deleted_id", "cw_member_subscription", ["deleted_id"])


def downgrade() -> None:
    op.drop_table("cw_member_subscription")
