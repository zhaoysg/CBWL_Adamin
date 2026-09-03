"""create reversible customer order and payment facts

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
        "cw_order",
        *_model_columns(),
        sa.Column("order_no", sa.String(length=40), nullable=False),
        sa.Column("legacy_user_id", sa.Integer(), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("plan_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(length=128), nullable=False),
        sa.Column("duration_days_snapshot", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payment_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "legacy_user_id IS NOT NULL OR customer_id IS NOT NULL",
            name="ck_cw_order_owner",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled', 'expired', 'refunded')",
            name="ck_cw_order_status",
        ),
        sa.CheckConstraint("unit_price >= 0", name="ck_cw_order_unit_price"),
        sa.CheckConstraint("total_amount >= 0", name="ck_cw_order_total_amount"),
        sa.CheckConstraint(
            "duration_days_snapshot > 0",
            name="ck_cw_order_duration",
        ),
        sa.CheckConstraint("version_no >= 1", name="ck_cw_order_version"),
        sa.CheckConstraint(
            "status NOT IN ('paid', 'refunded') OR paid_at IS NOT NULL",
            name="ck_cw_order_paid_shape",
        ),
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancelled_at IS NOT NULL",
            name="ck_cw_order_cancelled_shape",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_user_id"],
            ["sys_user.id"],
            name="fk_cw_order_legacy_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["cw_customer.id"],
            name="fk_cw_order_customer",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["cw_member_plan.id"],
            name="fk_cw_order_plan",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("order_no", name="uq_cw_order_no"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_cw_order_idempotency_key",
        ),
        comment="财不外露客户订单",
        **_MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_cw_order_legacy_status_created",
        "cw_order",
        ["legacy_user_id", "status", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_order_customer_status_created",
        "cw_order",
        ["customer_id", "status", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_order_status_expiry",
        "cw_order",
        ["status", "payment_expires_at", "id"],
        unique=False,
    )
    op.create_index("ix_cw_order_is_deleted", "cw_order", ["is_deleted"], unique=False)
    op.create_index("ix_cw_order_created_time", "cw_order", ["created_time"], unique=False)

    op.create_table(
        "cw_payment_attempt",
        *_model_columns(),
        sa.Column("attempt_no", sa.String(length=40), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("merchant_request_no", sa.String(length=64), nullable=False),
        sa.Column("provider_transaction_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'created'"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column(
            "version_no",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('wechat', 'alipay', 'manual')",
            name="ck_cw_payment_attempt_provider",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'processing', 'succeeded', 'failed', 'closed')",
            name="ck_cw_payment_attempt_status",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_cw_payment_attempt_amount"),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_cw_payment_attempt_version",
        ),
        sa.CheckConstraint(
            "status <> 'succeeded' OR succeeded_at IS NOT NULL",
            name="ck_cw_payment_attempt_succeeded_shape",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["cw_order.id"],
            name="fk_cw_payment_attempt_order",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint("attempt_no", name="uq_cw_payment_attempt_no"),
        sa.UniqueConstraint(
            "order_id",
            "idempotency_key",
            name="uq_cw_payment_attempt_order_idempotency",
        ),
        sa.UniqueConstraint(
            "provider",
            "merchant_request_no",
            name="uq_cw_payment_attempt_provider_request",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_cw_payment_attempt_provider_transaction",
        ),
        comment="财不外露订单支付尝试",
        **_MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_cw_payment_attempt_order_status",
        "cw_payment_attempt",
        ["order_id", "status", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_attempt_provider_status_created",
        "cw_payment_attempt",
        ["provider", "status", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_attempt_is_deleted",
        "cw_payment_attempt",
        ["is_deleted"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_attempt_created_time",
        "cw_payment_attempt",
        ["created_time"],
        unique=False,
    )

    op.create_table(
        "cw_payment_event",
        *_model_columns(),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("payment_attempt_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=128), nullable=False),
        sa.Column("merchant_request_no", sa.String(length=64), nullable=False),
        sa.Column("provider_transaction_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "provider IN ('wechat', 'alipay', 'manual')",
            name="ck_cw_payment_event_provider",
        ),
        sa.CheckConstraint(
            "event_type IN ('payment_succeeded', 'payment_failed', 'payment_closed')",
            name="ck_cw_payment_event_type",
        ),
        sa.CheckConstraint(
            "processing_status IN ('accepted', 'ignored', 'rejected')",
            name="ck_cw_payment_event_processing_status",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_cw_payment_event_amount"),
        sa.CheckConstraint(
            "CHAR_LENGTH(payload_digest) = 64",
            name="ck_cw_payment_event_digest",
        ),
        sa.CheckConstraint(
            "signature_verified = TRUE",
            name="ck_cw_payment_event_signature_verified",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["cw_order.id"],
            name="fk_cw_payment_event_order",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"],
            ["cw_payment_attempt.id"],
            name="fk_cw_payment_event_attempt",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_cw_payment_event_provider_event",
        ),
        comment="财不外露规范化支付事件",
        **_MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_cw_payment_event_order_received",
        "cw_payment_event",
        ["order_id", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_event_attempt_received",
        "cw_payment_event",
        ["payment_attempt_id", "created_time", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_event_processing",
        "cw_payment_event",
        ["processing_status", "processed_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_event_is_deleted",
        "cw_payment_event",
        ["is_deleted"],
        unique=False,
    )
    op.create_index(
        "ix_cw_payment_event_created_time",
        "cw_payment_event",
        ["created_time"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("cw_payment_event")
    op.drop_table("cw_payment_attempt")
    op.drop_table("cw_order")
