"""create 财不外露 orders, payments, refunds and outbox

Revision ID: 20260827_01
Revises: 20260823_01
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_01"
down_revision: str | None = "20260823_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _model_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(length=64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_time", sa.DateTime(timezone=True), nullable=True),
    ]


def _user_audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_id", sa.Integer(), nullable=True),
        sa.Column("updated_id", sa.Integer(), nullable=True),
        sa.Column("deleted_id", sa.Integer(), nullable=True),
    ]


def _user_audit_constraints() -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(["created_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["updated_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["deleted_id"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
    ]


def upgrade() -> None:
    op.create_table(
        "cw_order",
        *_model_columns(),
        *_user_audit_columns(),
        sa.Column("order_no", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("plan_snapshot", sa.JSON(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_amount_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("refunded_amount_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("version_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_user_audit_constraints(),
        sa.ForeignKeyConstraint(["user_id"], ["sys_user.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["cw_member_plan.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("order_no", name="uq_cw_order_order_no"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_cw_order_user_idempotency"),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'closed', 'refunding', 'partially_refunded', 'refunded', 'failed')",
            name="ck_cw_order_status",
        ),
        sa.CheckConstraint(
            "amount_minor >= 0 AND paid_amount_minor >= 0 AND paid_amount_minor <= amount_minor "
            "AND refunded_amount_minor >= 0 AND refunded_amount_minor <= paid_amount_minor",
            name="ck_cw_order_amounts",
        ),
        sa.CheckConstraint("version_no >= 1", name="ck_cw_order_version"),
        comment="财不外露会员订单",
    )
    op.create_index("ix_cw_order_user_status_created", "cw_order", ["user_id", "status", "created_time", "id"])
    op.create_index("ix_cw_order_status_expiry", "cw_order", ["status", "expires_at", "id"])
    op.create_index("ix_cw_order_plan_created", "cw_order", ["plan_id", "created_time", "id"])
    op.create_index("ix_cw_order_is_deleted", "cw_order", ["is_deleted"])
    op.create_index("ix_cw_order_created_time", "cw_order", ["created_time"])
    op.create_index("ix_cw_order_created_id", "cw_order", ["created_id"])
    op.create_index("ix_cw_order_updated_id", "cw_order", ["updated_id"])
    op.create_index("ix_cw_order_deleted_id", "cw_order", ["deleted_id"])

    op.create_table(
        "cw_payment_attempt",
        *_model_columns(),
        *_user_audit_columns(),
        sa.Column("attempt_no", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("provider_transaction_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'created'"), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("provider_status", sa.String(length=64), nullable=True),
        sa.Column("payment_payload", sa.JSON(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_user_audit_constraints(),
        sa.ForeignKeyConstraint(["order_id"], ["cw_order.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("attempt_no", name="uq_cw_payment_attempt_attempt_no"),
        sa.UniqueConstraint("order_id", "idempotency_key", name="uq_cw_payment_attempt_order_idempotency"),
        sa.UniqueConstraint("provider", "provider_transaction_id", name="uq_cw_payment_attempt_provider_txn"),
        sa.CheckConstraint("provider IN ('sandbox', 'manual')", name="ck_cw_payment_attempt_provider"),
        sa.CheckConstraint(
            "status IN ('created', 'pending', 'succeeded', 'failed', 'expired', 'cancelled')",
            name="ck_cw_payment_attempt_status",
        ),
        sa.CheckConstraint("amount_minor >= 0", name="ck_cw_payment_attempt_amount"),
        sa.CheckConstraint("version_no >= 1", name="ck_cw_payment_attempt_version"),
        comment="财不外露支付尝试",
    )
    op.create_index(
        "ix_cw_payment_attempt_order_status",
        "cw_payment_attempt",
        ["order_id", "status", "created_time", "id"],
    )
    op.create_index(
        "ix_cw_payment_attempt_provider_status",
        "cw_payment_attempt",
        ["provider", "status", "created_time", "id"],
    )
    op.create_index("ix_cw_payment_attempt_is_deleted", "cw_payment_attempt", ["is_deleted"])
    op.create_index("ix_cw_payment_attempt_created_time", "cw_payment_attempt", ["created_time"])
    op.create_index("ix_cw_payment_attempt_created_id", "cw_payment_attempt", ["created_id"])
    op.create_index("ix_cw_payment_attempt_updated_id", "cw_payment_attempt", ["updated_id"])
    op.create_index("ix_cw_payment_attempt_deleted_id", "cw_payment_attempt", ["deleted_id"])

    op.create_table(
        "cw_payment_event",
        *_model_columns(),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("provider_transaction_id", sa.String(length=128), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("order_no", sa.String(length=64), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("signature_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processing_status", sa.String(length=32), server_default=sa.text("'received'"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["cw_order.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_cw_payment_event_provider_event"),
        sa.CheckConstraint("provider IN ('sandbox', 'manual')", name="ck_cw_payment_event_provider"),
        sa.CheckConstraint(
            "processing_status IN ('received', 'processed', 'ignored', 'rejected', 'failed')",
            name="ck_cw_payment_event_processing_status",
        ),
        comment="财不外露支付事件",
    )
    op.create_index(
        "ix_cw_payment_event_order_received",
        "cw_payment_event",
        ["order_id", "received_at", "id"],
    )
    op.create_index("ix_cw_payment_event_order_no", "cw_payment_event", ["order_no", "received_at", "id"])
    op.create_index(
        "ix_cw_payment_event_provider_txn",
        "cw_payment_event",
        ["provider", "provider_transaction_id", "received_at", "id"],
    )
    op.create_index(
        "ix_cw_payment_event_processing",
        "cw_payment_event",
        ["processing_status", "received_at", "id"],
    )
    op.create_index("ix_cw_payment_event_is_deleted", "cw_payment_event", ["is_deleted"])
    op.create_index("ix_cw_payment_event_created_time", "cw_payment_event", ["created_time"])

    op.create_table(
        "cw_refund",
        *_model_columns(),
        *_user_audit_columns(),
        sa.Column("refund_no", sa.String(length=64), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("payment_attempt_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_refund_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'requested'"), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("version_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_user_audit_constraints(),
        sa.ForeignKeyConstraint(["order_id"], ["cw_order.id"], ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"],
            ["cw_payment_attempt.id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["sys_user.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("refund_no", name="uq_cw_refund_refund_no"),
        sa.UniqueConstraint("order_id", "idempotency_key", name="uq_cw_refund_order_idempotency"),
        sa.UniqueConstraint("provider", "provider_refund_id", name="uq_cw_refund_provider_refund"),
        sa.CheckConstraint("provider IN ('sandbox', 'manual')", name="ck_cw_refund_provider"),
        sa.CheckConstraint(
            "status IN ('requested', 'processing', 'succeeded', 'failed', 'cancelled')",
            name="ck_cw_refund_status",
        ),
        sa.CheckConstraint("amount_minor > 0", name="ck_cw_refund_amount"),
        sa.CheckConstraint("version_no >= 1", name="ck_cw_refund_version"),
        comment="财不外露订单退款",
    )
    op.create_index("ix_cw_refund_order_status", "cw_refund", ["order_id", "status", "created_time", "id"])
    op.create_index(
        "ix_cw_refund_attempt_status",
        "cw_refund",
        ["payment_attempt_id", "status", "created_time", "id"],
    )
    op.create_index("ix_cw_refund_provider_status", "cw_refund", ["provider", "status", "created_time", "id"])
    op.create_index("ix_cw_refund_is_deleted", "cw_refund", ["is_deleted"])
    op.create_index("ix_cw_refund_created_time", "cw_refund", ["created_time"])
    op.create_index("ix_cw_refund_created_id", "cw_refund", ["created_id"])
    op.create_index("ix_cw_refund_updated_id", "cw_refund", ["updated_id"])
    op.create_index("ix_cw_refund_deleted_id", "cw_refund", ["deleted_id"])

    op.create_table(
        "cw_outbox_event",
        *_model_columns(),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("deduplication_key", sa.String(length=128), nullable=True),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("version_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.UniqueConstraint("uuid"),
        sa.UniqueConstraint("event_id", name="uq_cw_outbox_event_event_id"),
        sa.UniqueConstraint("deduplication_key", name="uq_cw_outbox_event_deduplication"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'published', 'failed')",
            name="ck_cw_outbox_event_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_cw_outbox_event_attempts"),
        sa.CheckConstraint("version_no >= 1", name="ck_cw_outbox_event_version"),
        comment="财不外露事务发件箱",
    )
    op.create_index(
        "ix_cw_outbox_event_delivery",
        "cw_outbox_event",
        ["status", "available_at", "created_time", "id"],
    )
    op.create_index(
        "ix_cw_outbox_event_aggregate",
        "cw_outbox_event",
        ["aggregate_type", "aggregate_id", "created_time", "id"],
    )
    op.create_index("ix_cw_outbox_event_is_deleted", "cw_outbox_event", ["is_deleted"])
    op.create_index("ix_cw_outbox_event_created_time", "cw_outbox_event", ["created_time"])


def downgrade() -> None:
    op.drop_table("cw_outbox_event")
    op.drop_table("cw_refund")
    op.drop_table("cw_payment_event")
    op.drop_table("cw_payment_attempt")
    op.drop_table("cw_order")
