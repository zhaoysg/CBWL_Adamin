"""create reversible commerce order and payment ownership

Revision ID: 20260903_02
Revises: 20260903_01
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_02"
down_revision: str | None = "20260903_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_bin",
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


def _base_indexes(table_name: str) -> None:
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


def upgrade() -> None:
    op.create_table(
        "cw_commerce_order",
        *_model_columns(),
        sa.Column("order_no", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("legacy_user_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column(
            "product_type",
            sa.String(length=32),
            server_default=sa.text("'membership'"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("plan_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("plan_level_no_snapshot", sa.Integer(), nullable=False),
        sa.Column("duration_days_snapshot", sa.Integer(), nullable=False),
        sa.Column("benefits_snapshot", sa.JSON(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "payment_window_seconds",
            sa.Integer(),
            server_default=sa.text("900"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "legacy_user_id IS NOT NULL OR customer_id IS NOT NULL",
            name="ck_cw_commerce_order_owner_present",
        ),
        sa.CheckConstraint(
            "product_type = 'membership'",
            name="ck_cw_commerce_order_product_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled', 'closed', 'refunded')",
            name="ck_cw_commerce_order_status",
        ),
        sa.CheckConstraint(
            "(status <> 'paid' OR paid_at IS NOT NULL) "
            "AND (status <> 'cancelled' OR cancelled_at IS NOT NULL) "
            "AND (status <> 'closed' OR closed_at IS NOT NULL) "
            "AND (status <> 'refunded' OR refunded_at IS NOT NULL)",
            name="ck_cw_commerce_order_state_shape",
        ),
        sa.CheckConstraint(
            "expires_at > created_time",
            name="ck_cw_commerce_order_expiry",
        ),
        sa.CheckConstraint(
            "length(idempotency_key) = 64",
            name="ck_cw_commerce_order_idempotency_length",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_cw_commerce_order_amount"),
        sa.CheckConstraint(
            "payment_window_seconds >= 60 AND payment_window_seconds <= 86400",
            name="ck_cw_commerce_order_payment_window",
        ),
        sa.CheckConstraint(
            "plan_level_no_snapshot >= 1 AND plan_level_no_snapshot <= 100",
            name="ck_cw_commerce_order_plan_level",
        ),
        sa.CheckConstraint(
            "duration_days_snapshot > 0",
            name="ck_cw_commerce_order_duration",
        ),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_cw_commerce_order_version",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_user_id"],
            ["sys_user.id"],
            name="fk_cw_commerce_order_legacy_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["cw_customer.id"],
            name="fk_cw_commerce_order_customer",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["cw_member_plan.id"],
            name="fk_cw_commerce_order_plan",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("order_no", name="uq_cw_commerce_order_no"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_cw_commerce_order_idempotency",
        ),
        sa.UniqueConstraint(
            "id",
            "order_no",
            name="uq_cw_commerce_order_id_no",
        ),
        comment="财不外露会员订单",
        **_MYSQL_OPTIONS,
    )
    _base_indexes("cw_commerce_order")
    op.create_index(
        "ix_cw_commerce_order_customer_status_created",
        "cw_commerce_order",
        ["customer_id", "status", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_commerce_order_legacy_status_created",
        "cw_commerce_order",
        ["legacy_user_id", "status", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_commerce_order_status_expiry",
        "cw_commerce_order",
        ["status", "expires_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_commerce_order_plan_status",
        "cw_commerce_order",
        ["plan_id", "status", "id"],
        unique=False,
    )

    op.create_table(
        "cw_payment_attempt",
        *_model_columns(),
        sa.Column("payment_no", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("order_no", sa.String(length=40), nullable=False),
        sa.Column("legacy_user_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("provider_trade_no", sa.String(length=128), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=255), nullable=True),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "legacy_user_id IS NOT NULL OR customer_id IS NOT NULL",
            name="ck_cw_payment_attempt_owner_present",
        ),
        sa.CheckConstraint(
            "provider IN ('wechat', 'alipay', 'manual')",
            name="ck_cw_payment_attempt_provider",
        ),
        sa.CheckConstraint(
            "channel IN ('h5', 'jsapi', 'app', 'admin', 'bank_transfer')",
            name="ck_cw_payment_attempt_channel",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'closed', 'refunded')",
            name="ck_cw_payment_attempt_status",
        ),
        sa.CheckConstraint(
            "(status <> 'succeeded' OR succeeded_at IS NOT NULL) "
            "AND (status <> 'failed' OR failed_at IS NOT NULL) "
            "AND (status <> 'closed' OR closed_at IS NOT NULL) "
            "AND (status <> 'refunded' OR refunded_at IS NOT NULL)",
            name="ck_cw_payment_attempt_state_shape",
        ),
        sa.CheckConstraint(
            "length(idempotency_key) = 64",
            name="ck_cw_payment_attempt_idempotency_length",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_cw_payment_attempt_amount"),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_cw_payment_attempt_version",
        ),
        sa.ForeignKeyConstraint(
            ["order_id", "order_no"],
            ["cw_commerce_order.id", "cw_commerce_order.order_no"],
            name="fk_cw_payment_attempt_order_identity",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_user_id"],
            ["sys_user.id"],
            name="fk_cw_payment_attempt_legacy_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["cw_customer.id"],
            name="fk_cw_payment_attempt_customer",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("payment_no", name="uq_cw_payment_attempt_no"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_cw_payment_attempt_idempotency",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_trade_no",
            name="uq_cw_payment_attempt_provider_trade",
        ),
        sa.UniqueConstraint(
            "id",
            "payment_no",
            name="uq_cw_payment_attempt_id_no",
        ),
        comment="财不外露支付尝试",
        **_MYSQL_OPTIONS,
    )
    _base_indexes("cw_payment_attempt")
    op.create_index(
        "ix_cw_payment_attempt_order_status",
        "cw_payment_attempt",
        ["order_id", "status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_attempt_customer_status_created",
        "cw_payment_attempt",
        ["customer_id", "status", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_attempt_legacy_status_created",
        "cw_payment_attempt",
        ["legacy_user_id", "status", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_attempt_provider_status_created",
        "cw_payment_attempt",
        ["provider", "status", "created_time", "id"],
        unique=False,
    )

    op.create_table(
        "cw_payment_event",
        *_model_columns(),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("payment_no", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=191), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'received'"),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_code", sa.String(length=64), nullable=True),
        sa.Column("processing_message", sa.String(length=255), nullable=True),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('wechat', 'alipay', 'manual')",
            name="ck_cw_payment_event_provider",
        ),
        sa.CheckConstraint(
            "event_type IN ('payment_succeeded', 'payment_failed', 'payment_closed', 'refund_succeeded', 'unknown')",
            name="ck_cw_payment_event_type",
        ),
        sa.CheckConstraint(
            "status IN ('received', 'processed', 'ignored', 'failed')",
            name="ck_cw_payment_event_status",
        ),
        sa.CheckConstraint(
            "(status = 'received' AND processed_at IS NULL) "
            "OR (status <> 'received' AND processed_at IS NOT NULL)",
            name="ck_cw_payment_event_state_shape",
        ),
        sa.CheckConstraint(
            "length(payload_digest) = 64",
            name="ck_cw_payment_event_digest_length",
        ),
        sa.CheckConstraint(
            "provider_event_id <> ''",
            name="ck_cw_payment_event_provider_event_id",
        ),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_cw_payment_event_version",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id", "payment_no"],
            ["cw_payment_attempt.id", "cw_payment_attempt.payment_no"],
            name="fk_cw_payment_event_payment_identity",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_cw_payment_event_provider_event",
        ),
        comment="支付提供方事件去重信封",
        **_MYSQL_OPTIONS,
    )
    _base_indexes("cw_payment_event")
    op.create_index(
        "ix_cw_payment_event_payment_status",
        "cw_payment_event",
        ["payment_id", "status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_event_provider_received",
        "cw_payment_event",
        ["provider", "received_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("cw_payment_event")
    op.drop_table("cw_payment_attempt")
    op.drop_table("cw_commerce_order")
