"""add isolated admin and customer identity boundary

Revision ID: 20260902_01
Revises: 20260823_01
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_01"
down_revision: str | None = "20260823_01"
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


def _create_model_indexes(table_name: str) -> None:
    op.create_index(
        f"ix_{table_name}_is_deleted",
        table_name,
        ["is_deleted"],
        unique=False,
    )
    op.create_index(
        f"ix_{table_name}_created_time",
        table_name,
        ["created_time"],
        unique=False,
    )


def _drop_model_indexes(table_name: str) -> None:
    op.drop_index(f"ix_{table_name}_created_time", table_name=table_name)
    op.drop_index(f"ix_{table_name}_is_deleted", table_name=table_name)


def upgrade() -> None:
    op.create_table(
        "auth_subject",
        *_model_columns(),
        sa.Column("realm", sa.String(length=32), nullable=False, comment="安全域"),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="active",
            nullable=False,
            comment="主体状态",
        ),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="乐观锁版本",
        ),
        sa.CheckConstraint(
            "realm IN ('admin', 'customer')",
            name="ck_auth_subject_realm",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_auth_subject_status",
        ),
        sa.CheckConstraint("version_no >= 1", name="ck_auth_subject_version"),
        sa.UniqueConstraint("id", "realm", name="uq_auth_subject_id_realm"),
        comment="认证主体",
        **_MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_auth_subject_realm_status",
        "auth_subject",
        ["realm", "status", "id"],
        unique=False,
    )
    _create_model_indexes("auth_subject")

    op.create_table(
        "auth_identity",
        *_model_columns(),
        sa.Column("subject_id", sa.Integer(), nullable=False, comment="认证主体ID"),
        sa.Column("realm", sa.String(length=32), nullable=False, comment="安全域"),
        sa.Column(
            "provider",
            sa.String(length=32),
            nullable=False,
            comment="认证提供方",
        ),
        sa.Column(
            "identifier_normalized",
            sa.String(length=191),
            nullable=False,
            comment="规范化登录标识",
        ),
        sa.Column(
            "credential_hash",
            sa.String(length=255),
            nullable=True,
            comment="密码凭据哈希，仅password使用",
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.CheckConstraint(
            "realm IN ('admin', 'customer')",
            name="ck_auth_identity_realm",
        ),
        sa.CheckConstraint(
            "provider IN "
            "('password', 'mobile_otp', 'email_otp', 'wechat', 'external')",
            name="ck_auth_identity_provider",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_auth_identity_status",
        ),
        sa.CheckConstraint(
            "(provider = 'password' AND credential_hash IS NOT NULL) OR "
            "(provider <> 'password' AND credential_hash IS NULL)",
            name="ck_auth_identity_credential_shape",
        ),
        sa.CheckConstraint("version_no >= 1", name="ck_auth_identity_version"),
        sa.ForeignKeyConstraint(
            ["subject_id", "realm"],
            ["auth_subject.id", "auth_subject.realm"],
            name="fk_auth_identity_subject_realm",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint(
            "realm",
            "provider",
            "identifier_normalized",
            name="uq_auth_identity_realm_provider_identifier",
        ),
        comment="认证凭据与外部身份",
        **_MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_auth_identity_subject",
        "auth_identity",
        ["subject_id", "realm", "status", "id"],
        unique=False,
    )
    _create_model_indexes("auth_identity")

    op.create_table(
        "sys_admin_account",
        *_model_columns(),
        sa.Column("subject_id", sa.Integer(), nullable=False, comment="认证主体ID"),
        sa.Column(
            "realm",
            sa.String(length=32),
            server_default="admin",
            nullable=False,
            comment="固定为admin",
        ),
        sa.Column(
            "legacy_sys_user_id",
            sa.Integer(),
            nullable=False,
            comment="现有后台RBAC用户ID",
        ),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.CheckConstraint("realm = 'admin'", name="ck_sys_admin_account_realm"),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_sys_admin_account_status",
        ),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_sys_admin_account_version",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id", "realm"],
            ["auth_subject.id", "auth_subject.realm"],
            name="fk_sys_admin_account_subject_realm",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_sys_user_id"],
            ["sys_user.id"],
            name="fk_sys_admin_account_legacy_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("subject_id", name="uq_sys_admin_account_subject"),
        sa.UniqueConstraint(
            "legacy_sys_user_id",
            name="uq_sys_admin_account_legacy_user",
        ),
        comment="内部管理员业务主体",
        **_MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_sys_admin_account_status",
        "sys_admin_account",
        ["status", "id"],
        unique=False,
    )
    _create_model_indexes("sys_admin_account")

    op.create_table(
        "cw_customer",
        *_model_columns(),
        sa.Column("subject_id", sa.Integer(), nullable=False, comment="认证主体ID"),
        sa.Column(
            "realm",
            sa.String(length=32),
            server_default="customer",
            nullable=False,
            comment="固定为customer",
        ),
        sa.Column(
            "customer_no",
            sa.String(length=32),
            nullable=False,
            comment="不可变客户编号",
        ),
        sa.Column("nickname", sa.String(length=128), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column(
            "register_source",
            sa.String(length=32),
            server_default="h5",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.CheckConstraint("realm = 'customer'", name="ck_cw_customer_realm"),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_cw_customer_status",
        ),
        sa.CheckConstraint(
            "register_source IN ('h5', 'admin_import', 'migration', 'promotion')",
            name="ck_cw_customer_register_source",
        ),
        sa.CheckConstraint("version_no >= 1", name="ck_cw_customer_version"),
        sa.ForeignKeyConstraint(
            ["subject_id", "realm"],
            ["auth_subject.id", "auth_subject.realm"],
            name="fk_cw_customer_subject_realm",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("subject_id", name="uq_cw_customer_subject"),
        sa.UniqueConstraint("customer_no", name="uq_cw_customer_no"),
        comment="H5外部客户",
        **_MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_cw_customer_status_created",
        "cw_customer",
        ["status", "created_time", "id"],
        unique=False,
    )
    _create_model_indexes("cw_customer")


def downgrade() -> None:
    _drop_model_indexes("cw_customer")
    op.drop_index("ix_cw_customer_status_created", table_name="cw_customer")
    op.drop_table("cw_customer")

    _drop_model_indexes("sys_admin_account")
    op.drop_index("ix_sys_admin_account_status", table_name="sys_admin_account")
    op.drop_table("sys_admin_account")

    _drop_model_indexes("auth_identity")
    op.drop_index("ix_auth_identity_subject", table_name="auth_identity")
    op.drop_table("auth_identity")

    _drop_model_indexes("auth_subject")
    op.drop_index("ix_auth_subject_realm_status", table_name="auth_subject")
    op.drop_table("auth_subject")
