from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.v1.module_billing.enums import BillingProvider, RefundStatus, sql_enum_values
from app.core.base_model import ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.api.v1.module_billing.order.model import CommerceOrderModel
    from app.api.v1.module_billing.payment.model import PaymentAttemptModel
    from app.api.v1.module_system.user.model import UserModel


class RefundModel(ModelMixin, UserMixin):
    """会员订单退款记录。"""

    __tablename__ = "cw_refund"
    __table_args__ = (
        UniqueConstraint("refund_no", name="uq_cw_refund_refund_no"),
        UniqueConstraint("order_id", "idempotency_key", name="uq_cw_refund_order_idempotency"),
        UniqueConstraint("provider", "provider_refund_id", name="uq_cw_refund_provider_refund"),
        CheckConstraint(f"provider IN ({sql_enum_values(BillingProvider)})", name="ck_cw_refund_provider"),
        CheckConstraint(f"status IN ({sql_enum_values(RefundStatus)})", name="ck_cw_refund_status"),
        CheckConstraint("amount_minor > 0", name="ck_cw_refund_amount"),
        CheckConstraint("version_no >= 1", name="ck_cw_refund_version"),
        Index("ix_cw_refund_order_status", "order_id", "status", "created_time", "id"),
        Index("ix_cw_refund_attempt_status", "payment_attempt_id", "status", "created_time", "id"),
        Index("ix_cw_refund_provider_status", "provider", "status", "created_time", "id"),
        {"comment": "财不外露订单退款"},
    )

    refund_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="退款编号")
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cw_order.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="订单ID",
    )
    payment_attempt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cw_payment_attempt.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="原支付尝试ID",
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, comment="支付Provider")
    provider_refund_id: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="Provider退款号")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="退款幂等键")
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="退款金额")
    reason: Mapped[str] = mapped_column(String(500), nullable=False, comment="退款原因")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RefundStatus.REQUESTED.value,
        comment="退款状态",
    )
    requested_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        comment="退款申请人ID",
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="退款申请时间",
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="退款处理完成时间")
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="脱敏失败码")
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="脱敏失败说明")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本")

    order: Mapped[CommerceOrderModel] = relationship("CommerceOrderModel", foreign_keys=[order_id], lazy="raise")
    payment_attempt: Mapped[PaymentAttemptModel] = relationship(
        "PaymentAttemptModel",
        foreign_keys=[payment_attempt_id],
        lazy="raise",
    )
    requester: Mapped[UserModel | None] = relationship("UserModel", foreign_keys=[requested_by], lazy="raise")
