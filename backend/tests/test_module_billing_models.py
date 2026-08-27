from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import JSON, BigInteger, CheckConstraint, UniqueConstraint

from app.api.v1.module_billing.enums import (
    BillingProvider,
    OrderStatus,
    OutboxEventStatus,
    PaymentAttemptStatus,
    PaymentEventProcessingStatus,
    RefundStatus,
)
from app.api.v1.module_billing.money import decimal_to_minor
from app.api.v1.module_billing.order.model import CommerceOrderModel
from app.api.v1.module_billing.outbox.model import OutboxEventModel
from app.api.v1.module_billing.payment.model import PaymentAttemptModel, PaymentEventModel
from app.api.v1.module_billing.refund.model import RefundModel
from app.core.base_model import MappedBase
from app.utils.import_util import ImportUtil

_REQUIRED_TABLES = {
    "cw_order",
    "cw_payment_attempt",
    "cw_payment_event",
    "cw_refund",
    "cw_outbox_event",
}


def _constraint_names(model: type[MappedBase], constraint_type: type) -> set[str]:
    return {constraint.name for constraint in model.__table__.constraints if isinstance(constraint, constraint_type) and constraint.name is not None}


def _index_names(model: type[MappedBase]) -> set[str]:
    return {index.name for index in model.__table__.indexes if index.name is not None}


def test_billing_enum_contract_is_explicit_and_stable() -> None:
    assert {item.value for item in OrderStatus} == {
        "pending",
        "paid",
        "closed",
        "refunding",
        "partially_refunded",
        "refunded",
        "failed",
    }
    assert {item.value for item in BillingProvider} == {"sandbox", "manual"}
    assert {item.value for item in PaymentAttemptStatus} == {
        "created",
        "pending",
        "succeeded",
        "failed",
        "expired",
        "cancelled",
    }
    assert {item.value for item in PaymentEventProcessingStatus} == {
        "received",
        "processed",
        "ignored",
        "rejected",
        "failed",
    }
    assert {item.value for item in RefundStatus} == {
        "requested",
        "processing",
        "succeeded",
        "failed",
        "cancelled",
    }
    assert {item.value for item in OutboxEventStatus} == {
        "pending",
        "processing",
        "published",
        "failed",
    }


def test_decimal_to_minor_is_exact_and_fail_closed() -> None:
    assert decimal_to_minor(Decimal("199.00"), "CNY") == 19900
    assert decimal_to_minor(Decimal("0.01"), "cny") == 1
    assert decimal_to_minor(Decimal("0"), "CNY") == 0

    with pytest.raises(ValueError, match="最多支持"):
        decimal_to_minor(Decimal("1.001"), "CNY")
    with pytest.raises(ValueError, match="不支持的币种"):
        decimal_to_minor(Decimal("1.00"), "USD")
    with pytest.raises(ValueError, match="不能为负数"):
        decimal_to_minor(Decimal("-0.01"), "CNY")


def test_billing_models_are_discoverable_by_alembic() -> None:
    ImportUtil.find_models.cache_clear()
    discovered = {model.__tablename__ for model in ImportUtil.find_models(MappedBase)}
    assert _REQUIRED_TABLES <= discovered


def test_order_model_enforces_integer_money_and_idempotency() -> None:
    table = CommerceOrderModel.__table__
    assert isinstance(table.c.amount_minor.type, BigInteger)
    assert isinstance(table.c.paid_amount_minor.type, BigInteger)
    assert isinstance(table.c.refunded_amount_minor.type, BigInteger)
    assert isinstance(table.c.plan_snapshot.type, JSON)
    assert table.c.amount_minor.nullable is False
    assert table.c.currency.nullable is False
    assert table.c.idempotency_key.nullable is False
    assert table.c.status.default.arg == OrderStatus.PENDING.value

    assert {
        "uq_cw_order_order_no",
        "uq_cw_order_user_idempotency",
    } <= _constraint_names(CommerceOrderModel, UniqueConstraint)
    assert {
        "ck_cw_order_status",
        "ck_cw_order_amounts",
        "ck_cw_order_version",
    } <= _constraint_names(CommerceOrderModel, CheckConstraint)
    assert {
        "ix_cw_order_user_status_created",
        "ix_cw_order_status_expiry",
        "ix_cw_order_plan_created",
    } <= _index_names(CommerceOrderModel)


def test_payment_models_keep_provider_evidence_without_raw_secrets() -> None:
    attempt_table = PaymentAttemptModel.__table__
    event_table = PaymentEventModel.__table__

    assert isinstance(attempt_table.c.amount_minor.type, BigInteger)
    assert attempt_table.c.status.default.arg == PaymentAttemptStatus.CREATED.value
    assert {
        "uq_cw_payment_attempt_attempt_no",
        "uq_cw_payment_attempt_order_idempotency",
        "uq_cw_payment_attempt_provider_txn",
    } <= _constraint_names(PaymentAttemptModel, UniqueConstraint)

    event_columns = set(event_table.c.keys())
    assert {"raw_body", "raw_payload", "request_body", "request_headers"}.isdisjoint(event_columns)
    assert {
        "provider",
        "provider_event_id",
        "amount_minor",
        "currency",
        "payload_hash",
        "signature_verified",
        "processing_status",
    } <= event_columns
    assert isinstance(event_table.c.amount_minor.type, BigInteger)
    assert event_table.c.currency.nullable is True
    assert event_table.c.processing_status.default.arg == PaymentEventProcessingStatus.RECEIVED.value
    assert "uq_cw_payment_event_provider_event" in _constraint_names(PaymentEventModel, UniqueConstraint)
    assert "ck_cw_payment_event_amount" in _constraint_names(PaymentEventModel, CheckConstraint)


def test_refund_and_outbox_models_have_deduplication_guards() -> None:
    assert isinstance(RefundModel.__table__.c.amount_minor.type, BigInteger)
    assert RefundModel.__table__.c.status.default.arg == RefundStatus.REQUESTED.value
    assert {
        "uq_cw_refund_refund_no",
        "uq_cw_refund_order_idempotency",
        "uq_cw_refund_provider_refund",
    } <= _constraint_names(RefundModel, UniqueConstraint)

    assert isinstance(OutboxEventModel.__table__.c.payload.type, JSON)
    assert OutboxEventModel.__table__.c.status.default.arg == OutboxEventStatus.PENDING.value
    assert {
        "uq_cw_outbox_event_event_id",
        "uq_cw_outbox_event_deduplication",
    } <= _constraint_names(OutboxEventModel, UniqueConstraint)
    assert "ix_cw_outbox_event_delivery" in _index_names(OutboxEventModel)


def test_m2_4_migration_chain_is_explicit() -> None:
    versions = Path(__file__).parents[1] / "app/alembic/versions"
    base_migration = (versions / "20260827_01_caibuwailu_order_payment.py").read_text(encoding="utf-8")
    event_money_migration = (versions / "20260827_02_caibuwailu_payment_event_amount.py").read_text(encoding="utf-8")

    assert 'revision: str = "20260827_01"' in base_migration
    assert 'down_revision: str | None = "20260823_01"' in base_migration
    for table_name in _REQUIRED_TABLES:
        assert f'"{table_name}"' in base_migration

    assert 'revision: str = "20260827_02"' in event_money_migration
    assert 'down_revision: str | None = "20260827_01"' in event_money_migration
    assert '"amount_minor"' in event_money_migration
    assert '"currency"' in event_money_migration
