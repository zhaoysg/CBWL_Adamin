from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.v1.module_billing.enums import (
    BillingProvider,
    PaymentAttemptStatus,
    PaymentEventProcessingStatus,
    sql_enum_values,
)
from app.core.base_model import ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.api.v1.module_billing.order.model import CommerceOrderModel


class PaymentAttemptModel(ModelMixin, UserMixin):
    """一次面向支付 Provider 的支付发起记录。"""

    __tablename__ = "cw_payment_attempt"
    __table_args__ = (
        UniqueConstraint("attempt_no", name="uq_cw_payment_attempt_attempt_no"),
        UniqueConstraint("order_id", "idempotency_key", name="uq_cw_payment_attempt_order_idempotency"),
        UniqueConstraint("provider", "provider_transaction_id", name="uq_cw_payment_attempt_provider_txn"),
        CheckConstraint(f"provider IN ({sql_enum_values(BillingProvider)})", name="ck_cw_payment_attempt_provider"),
        CheckConstraint(f"status IN ({sql_enum_values(PaymentAttemptStatus)})", name="ck_cw_payment_attempt_status"),
        CheckConstraint("amount_minor >= 0", name="ck_cw_payment_attempt_amount"),
        CheckConstraint("version_no >= 1", name="ck_cw_payment_attempt_version"),
        Index("ix_cw_payment_attempt_order_status", "order_id", "status", "created_time", "id"),
        Index("ix_cw_payment_attempt_provider_status", "provider", "status", "created_time", "id"),
        {"comment": "财不外露支付尝试"},
    )

    attempt_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="支付尝试编号")
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cw_order.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="订单ID",
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, comment="支付Provider")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="支付发起幂等键")
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Provider交易号")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PaymentAttemptStatus.CREATED.value,
        comment="支付尝试状态",
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="请求支付金额")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, comment="币种")
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Provider公开状态")
    payment_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True, comment="可公开支付发起数据")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="脱敏失败码")
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="脱敏失败说明")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="支付尝试到期时间")
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="支付成功时间")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本")

    order: Mapped[CommerceOrderModel] = relationship("CommerceOrderModel", foreign_keys=[order_id], lazy="raise")


class PaymentEventModel(ModelMixin):
    """回调或主动查询产生的不可变支付事件证据。"""

    __tablename__ = "cw_payment_event"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_cw_payment_event_provider_event"),
        CheckConstraint(f"provider IN ({sql_enum_values(BillingProvider)})", name="ck_cw_payment_event_provider"),
        CheckConstraint(
            f"processing_status IN ({sql_enum_values(PaymentEventProcessingStatus)})",
            name="ck_cw_payment_event_processing_status",
        ),
        CheckConstraint("amount_minor IS NULL OR amount_minor >= 0", name="ck_cw_payment_event_amount"),
        Index("ix_cw_payment_event_order_received", "order_id", "received_at", "id"),
        Index("ix_cw_payment_event_order_no", "order_no", "received_at", "id"),
        Index("ix_cw_payment_event_provider_txn", "provider", "provider_transaction_id", "received_at", "id"),
        Index("ix_cw_payment_event_processing", "processing_status", "received_at", "id"),
        {"comment": "财不外露支付事件"},
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False, comment="支付Provider")
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="Provider事件ID")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="Provider事件类型")
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Provider交易号")
    order_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("cw_order.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="已关联订单ID",
    )
    order_no: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="事件携带订单号")
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="事件声明金额")
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True, comment="事件声明币种")
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="原始报文SHA-256")
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="签名是否验证通过")
    event_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True, comment="经筛选的非敏感事件元数据")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="事件接收时间",
    )
    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PaymentEventProcessingStatus.RECEIVED.value,
        comment="处理状态",
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="处理完成时间")
    processing_error: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="脱敏处理错误")

    order: Mapped[CommerceOrderModel | None] = relationship("CommerceOrderModel", foreign_keys=[order_id], lazy="raise")
