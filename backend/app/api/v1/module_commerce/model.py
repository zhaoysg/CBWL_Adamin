from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import ModelMixin

if TYPE_CHECKING:
    from app.api.v1.module_identity.model import CustomerModel
    from app.api.v1.module_membership.plan.model import MemberPlanModel
    from app.api.v1.module_system.user.model import UserModel

_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_bin",
}


class CommerceOrderModel(ModelMixin):
    """Immutable commercial snapshot plus reversible customer ownership."""

    __tablename__ = "cw_order"
    __table_args__ = (
        UniqueConstraint("order_no", name="uq_cw_order_no"),
        UniqueConstraint("idempotency_key", name="uq_cw_order_idempotency_key"),
        CheckConstraint(
            "legacy_user_id IS NOT NULL OR customer_id IS NOT NULL",
            name="ck_cw_order_owner",
        ),
        CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled', 'expired', 'refunded')",
            name="ck_cw_order_status",
        ),
        CheckConstraint("unit_price >= 0", name="ck_cw_order_unit_price"),
        CheckConstraint("total_amount >= 0", name="ck_cw_order_total_amount"),
        CheckConstraint(
            "duration_days_snapshot > 0",
            name="ck_cw_order_duration",
        ),
        CheckConstraint("version_no >= 1", name="ck_cw_order_version"),
        CheckConstraint(
            "status NOT IN ('paid', 'refunded') OR paid_at IS NOT NULL",
            name="ck_cw_order_paid_shape",
        ),
        CheckConstraint(
            "status <> 'cancelled' OR cancelled_at IS NOT NULL",
            name="ck_cw_order_cancelled_shape",
        ),
        Index(
            "ix_cw_order_legacy_status_created",
            "legacy_user_id",
            "status",
            "created_time",
            "id",
        ),
        Index(
            "ix_cw_order_customer_status_created",
            "customer_id",
            "status",
            "created_time",
            "id",
        ),
        Index(
            "ix_cw_order_status_expiry",
            "status",
            "payment_expires_at",
            "id",
        ),
        {"comment": "财不外露客户订单", **_TABLE_OPTIONS},
    )

    order_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="服务端生成的不可变订单号",
    )
    legacy_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "sys_user.id",
            name="fk_cw_order_legacy_user",
        ),
        nullable=True,
        comment="迁移期原系统用户ID",
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "cw_customer.id",
            name="fk_cw_order_customer",
        ),
        nullable=True,
        comment="H5客户ID",
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "cw_member_plan.id",
            name="fk_cw_order_plan",
        ),
        nullable=False,
        comment="下单时会员套餐ID",
    )
    plan_code_snapshot: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="下单时套餐编码快照",
    )
    plan_name_snapshot: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="下单时套餐名称快照",
    )
    duration_days_snapshot: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="下单时套餐有效天数快照",
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="服务端套餐单价快照",
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="订单应付金额",
    )
    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="ISO风格大写币种代码",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="订单状态",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="客户端一次下单意图的全局幂等键",
    )
    payment_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="支付截止时间",
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="支付成功时间",
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="取消时间",
    )
    cancel_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="取消原因",
    )
    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="乐观锁版本",
    )

    legacy_user: Mapped[UserModel | None] = relationship(
        "UserModel",
        foreign_keys=[legacy_user_id],
        lazy="raise",
    )
    customer: Mapped[CustomerModel | None] = relationship(
        "CustomerModel",
        foreign_keys=[customer_id],
        lazy="raise",
    )
    plan: Mapped[MemberPlanModel] = relationship(
        "MemberPlanModel",
        foreign_keys=[plan_id],
        lazy="raise",
    )
    payment_attempts: Mapped[list[PaymentAttemptModel]] = relationship(
        "PaymentAttemptModel",
        back_populates="order",
        lazy="raise",
    )
    payment_events: Mapped[list[PaymentEventModel]] = relationship(
        "PaymentEventModel",
        back_populates="order",
        lazy="raise",
    )


class PaymentAttemptModel(ModelMixin):
    """One server-created attempt to pay a fixed order amount."""

    __tablename__ = "cw_payment_attempt"
    __table_args__ = (
        UniqueConstraint("attempt_no", name="uq_cw_payment_attempt_no"),
        UniqueConstraint(
            "order_id",
            "idempotency_key",
            name="uq_cw_payment_attempt_order_idempotency",
        ),
        UniqueConstraint(
            "provider",
            "merchant_request_no",
            name="uq_cw_payment_attempt_provider_request",
        ),
        UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_cw_payment_attempt_provider_transaction",
        ),
        CheckConstraint(
            "provider IN ('wechat', 'alipay', 'manual')",
            name="ck_cw_payment_attempt_provider",
        ),
        CheckConstraint(
            "status IN ('created', 'processing', 'succeeded', 'failed', 'closed')",
            name="ck_cw_payment_attempt_status",
        ),
        CheckConstraint("amount >= 0", name="ck_cw_payment_attempt_amount"),
        CheckConstraint("version_no >= 1", name="ck_cw_payment_attempt_version"),
        CheckConstraint(
            "status <> 'succeeded' OR succeeded_at IS NOT NULL",
            name="ck_cw_payment_attempt_succeeded_shape",
        ),
        CheckConstraint(
            "status NOT IN ('failed', 'closed') OR failed_at IS NOT NULL",
            name="ck_cw_payment_attempt_failed_shape",
        ),
        Index(
            "ix_cw_payment_attempt_order_status",
            "order_id",
            "status",
            "id",
        ),
        Index(
            "ix_cw_payment_attempt_provider_status_created",
            "provider",
            "status",
            "created_time",
            "id",
        ),
        {"comment": "财不外露订单支付尝试", **_TABLE_OPTIONS},
    )

    attempt_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="服务端支付尝试编号",
    )
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "cw_order.id",
            name="fk_cw_payment_attempt_order",
        ),
        nullable=False,
        comment="订单ID",
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="支付提供方",
    )
    merchant_request_no: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="提交给支付提供方的商户请求号",
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="支付提供方交易号",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="同一订单内创建支付尝试的幂等键",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="支付金额快照",
    )
    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="支付币种快照",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="created",
        comment="支付尝试状态",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="支付尝试截止时间",
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="支付成功时间",
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="失败或关闭时间",
    )
    failure_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="规范化失败代码，不保存原始敏感报文",
    )
    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="乐观锁版本",
    )

    order: Mapped[CommerceOrderModel] = relationship(
        "CommerceOrderModel",
        back_populates="payment_attempts",
        lazy="raise",
    )
    events: Mapped[list[PaymentEventModel]] = relationship(
        "PaymentEventModel",
        back_populates="payment_attempt",
        lazy="raise",
    )


class PaymentEventModel(ModelMixin):
    """Deduplicated, verified and normalized payment callback fact."""

    __tablename__ = "cw_payment_event"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_cw_payment_event_provider_event",
        ),
        CheckConstraint(
            "provider IN ('wechat', 'alipay', 'manual')",
            name="ck_cw_payment_event_provider",
        ),
        CheckConstraint(
            "event_type IN ('payment_succeeded', 'payment_failed', 'payment_closed')",
            name="ck_cw_payment_event_type",
        ),
        CheckConstraint(
            "processing_status IN ('accepted', 'ignored', 'rejected')",
            name="ck_cw_payment_event_processing_status",
        ),
        CheckConstraint("amount >= 0", name="ck_cw_payment_event_amount"),
        CheckConstraint(
            "LENGTH(payload_digest) = 64",
            name="ck_cw_payment_event_digest",
        ),
        CheckConstraint(
            "signature_verified = TRUE",
            name="ck_cw_payment_event_signature_verified",
        ),
        Index(
            "ix_cw_payment_event_order_received",
            "order_id",
            "created_time",
            "id",
        ),
        Index(
            "ix_cw_payment_event_attempt_received",
            "payment_attempt_id",
            "created_time",
            "id",
        ),
        Index(
            "ix_cw_payment_event_processing",
            "processing_status",
            "processed_at",
            "id",
        ),
        {"comment": "财不外露规范化支付事件", **_TABLE_OPTIONS},
    )

    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "cw_order.id",
            name="fk_cw_payment_event_order",
        ),
        nullable=False,
        comment="订单ID",
    )
    payment_attempt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "cw_payment_attempt.id",
            name="fk_cw_payment_event_attempt",
        ),
        nullable=False,
        comment="支付尝试ID",
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="支付提供方",
    )
    provider_event_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="支付提供方事件幂等键",
    )
    merchant_request_no: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="商户请求号",
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="支付提供方交易号",
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="规范化事件类型",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="回调金额",
    )
    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="回调币种",
    )
    signature_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="上游适配器已验证签名",
    )
    payload_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="规范化前原始载荷的SHA-256摘要",
    )
    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="处理结果",
    )
    reason_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="安全、稳定的处理原因代码",
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True).with_variant(
            mysql.DATETIME(fsp=6),
            "mysql",
        ),
        nullable=False,
        comment="支付提供方事件发生时间",
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="本系统处理时间",
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="不含原始报文的内部说明",
    )

    order: Mapped[CommerceOrderModel] = relationship(
        "CommerceOrderModel",
        back_populates="payment_events",
        lazy="raise",
    )
    payment_attempt: Mapped[PaymentAttemptModel] = relationship(
        "PaymentAttemptModel",
        back_populates="events",
        lazy="raise",
    )
