"""add auditable money fields to payment events

Revision ID: 20260827_02
Revises: 20260827_01
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_02"
down_revision: str | None = "20260827_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("cw_payment_event") as batch_op:
        batch_op.add_column(sa.Column("amount_minor", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("currency", sa.String(length=8), nullable=True))
        batch_op.create_check_constraint(
            "ck_cw_payment_event_amount",
            "amount_minor IS NULL OR amount_minor >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("cw_payment_event") as batch_op:
        batch_op.drop_constraint("ck_cw_payment_event_amount", type_="check")
        batch_op.drop_column("currency")
        batch_op.drop_column("amount_minor")
