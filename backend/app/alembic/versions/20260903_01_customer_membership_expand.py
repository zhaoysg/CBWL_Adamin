"""expand customer mapping and membership ownership

Revision ID: 20260903_01
Revises: 20260902_01
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_01"
down_revision: str | None = "20260902_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
}


def _model_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "created_time",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_time",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_time", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid"),
    ]


def upgrade() -> None:
    op.create_table(
        "cw_customer_legacy_map",
        *_model_columns(),
        sa.Column(
            "legacy_sys_user_id",
            sa.Integer(),
            nullable=False,
            comment="迁移前系统用户ID",
        ),
        sa.Column(
            "customer_id",
            sa.Integer(),
            nullable=False,
            comment="迁移后客户ID",
        ),
        sa.Column(
            "credential_state",
            sa.String(length=32),
            nullable=False,
            comment="凭据迁移状态",
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            comment="映射来源",
        ),
        sa.Column(
            "reason_code",
            sa.String(length=64),
            nullable=True,
            comment="需认领等原因代码",
        ),
        sa.Column(
            "identifier_snapshot",
            sa.String(length=191),
            nullable=False,
            comment="迁移时规范化登录标识快照",
        ),
        sa.Column(
            "migrated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="映射完成时间",
        ),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="乐观锁版本",
        ),
        sa.CheckConstraint(
            "credential_state IN ('migrated', 'claim_required')",
            name="ck_cw_customer_legacy_map_credential_state",
        ),
        sa.CheckConstraint(
            "source IN ('membership', 'manual')",
            name="ck_cw_customer_legacy_map_source",
        ),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_cw_customer_legacy_map_version",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_sys_user_id"],
            ["sys_user.id"],
            name="fk_cw_customer_legacy_map_legacy_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["cw_customer.id"],
            name="fk_cw_customer_legacy_map_customer",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint(
            "legacy_sys_user_id",
            name="uq_cw_customer_legacy_map_legacy_user",
        ),
        sa.UniqueConstraint(
            "customer_id",
            name="uq_cw_customer_legacy_map_customer",
        ),
        comment="存量系统用户到H5客户的迁移映射",
        **_MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_cw_customer_legacy_map_state",
        "cw_customer_legacy_map",
        ["credential_state", "source", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_customer_legacy_map_is_deleted",
        "cw_customer_legacy_map",
        ["is_deleted"],
        unique=False,
    )
    op.create_index(
        "ix_cw_customer_legacy_map_created_time",
        "cw_customer_legacy_map",
        ["created_time"],
        unique=False,
    )

    op.add_column(
        "cw_member_subscription",
        sa.Column(
            "customer_id",
            sa.Integer(),
            nullable=True,
            comment="H5客户ID；M2 expand阶段允许为空",
        ),
    )
    op.create_index(
        "ix_cw_member_subscription_customer_window",
        "cw_member_subscription",
        ["customer_id", "status", "starts_at", "expires_at", "id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_cw_member_subscription_customer",
        "cw_member_subscription",
        "cw_customer",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
        onupdate="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cw_member_subscription_customer",
        "cw_member_subscription",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_cw_member_subscription_customer_window",
        table_name="cw_member_subscription",
    )
    op.drop_column("cw_member_subscription", "customer_id")
    op.drop_table("cw_customer_legacy_map")
