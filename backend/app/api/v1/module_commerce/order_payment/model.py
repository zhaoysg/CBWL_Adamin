from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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
    """Membership order with reversible legacy/customer ownership."""

    __tablename__ = "cw_commerce_order"
    __table_args__ = (
        UniqueConstraint("order_no", name="uq_cw_commerce_order_no"),
        UniqueConstraint("idempotency_key", name="uq_cw_commerce_order_idempotency"),
        UniqueConstraint("id", "order_no", name="uq_cw_commerce_order_id_no"),
        CheckConstraint(
            "legacy_user_id IS NOT NULL OR customer_id IS NOT NULL",
            name="ck_cw_commerce_order_owner_present",
        ),
        CheckConstraint(
            "product_type = 'membership'",
            name="ck_cw_commerce_order_product_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled', 'closed', 'refunded')",
            name="ck_cw_commerce_order_status",
        ),
        CheckConstraint(
            "(status <> 'paid' OR paid_at IS NOT NULL) "
            "AND (status <> 'cancelled' OR cancelled_at IS NOT NULL) "
            "AND (status <> 'closed' OR closed_at IS NOT NULL) "
            "AND (status <> 'refunded' OR refunded_at IS NOT NULL)",
            name="ck_cw_commerce_order_state_shape",
        ),
        CheckConstraint(
            "expires_at > created_time",
            name="ck_cw_commerce_order_expiry",
        ),
        CheckConstraint(
            "length(idempotency_key) = 64",
            name="ck_cw_commerce_order_idempotency_length",
        ),
        CheckConstraint("amount >= 0", name="ck_cw_commerce_order_amount"),
        CheckConstraint(
            "payment_window_seconds >= 60 AND payment_window_seconds <= 86400",
            name="ck_cw_commerce_order_payment_window",
        ),
        CheckConstraint(
            "plan_level_no_snapshot >= 1 AND plan_level_no_snapshot <= 100",
            name="ck_cw_commerce_order_plan_level",
        ),
        CheckConstraint(
            "duration_days_snapshot > 0",
            name="ck_cw_commerce_order_duration",
        ),
        CheckConstraint("version_no >= 1", name="ck_cw_commerce_order_version"),
        Index(
            "ix_cw_commerce_order_customer_status_created",
            "customer_id",
            "status",
            "created_time",
            "id",
        ),
        Index(
            "ix_cw_commerce_order_legacy_status_created",
            "legacy_user_id",
            "status",
            "created_time",
            "id",
        ),
        Index(
            "ix_cw_commerce_order_status_expiry",
            "status",
            "expires_at",
            "id",
        ),
        Index(
            "ix_cw_commerce_order_plan_status",
            "plan_id",
            "status",
            "id",
        ),
        {"comment": "财不外露会员订单", **_TABLE_OPTIONS},
    )

    order_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="不可变订单编号",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="服务端计算的订单幂等摘要",
    )
    legacy_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "sys_user.id",
            name="fk_cw_commerce_order_legacy_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
        comment="迁移期原系统用户ID",
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "cw_customer.id",
            name="fk_cw_commerce_order_customer",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
        comment="H5客户ID",
    )
    product_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="membership",
        comment="商品类型",
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "cw_member_plan.id",
            name="fk_cw_commerce_order_plan",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
        comment="会员套餐ID",
    )
    plan_code_snapshot: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="下单时套餐编码",
    )
    plan_name_snapshot: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="下单时套餐名称",
    )
    plan_level_no_snapshot: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="下单时权益等级",
    )
    duration_days_snapshot: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="下单时有效天数",
    )
    benefits_snapshot: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="下单时权益快照",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="应付金额",
    )
    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="币种",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="订单状态",
    )
    payment_window_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=900,
        comment="支付窗口秒数",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="支付截止时间",
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="支付完成时间",
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="取消时间",
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="关闭时间",
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="退款完成时间",
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
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="内部备注",
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


class PaymentAttemptModel(ModelMixin):
    """One provider payment attempt for an immutable order snapshot."""

    __tablename__ = "cw_payment_attempt"
    __table_args__ = (
        ForeignKeyConstraint(
            ["order_id", "order_no"],
            ["cw_commerce_order.id", "cw_commerce_order.order_no"],
            name="fk_cw_payment_attempt_order_identity",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        UniqueConstraint("payment_no", name="uq_cw_payment_attempt_no"),
        UniqueConstraint(
            "idempotency_key",
            name="uq_cw_payment_attempt_idempotency",
        ),
        UniqueConstraint(
            "provider",
            "provider_trade_no",
            name="uq_cw_payment_attempt_provider_trade",
        ),
        UniqueConstraint("id", "payment_no", name="uq_cw_payment_attempt_id_no"),
        CheckConstraint(
            "legacy_user_id IS NOT NULL OR customer_id IS NOT NULL",
            name="ck_cw_payment_attempt_owner_present",
        ),
        CheckConstraint(
            "provider IN ('wechat', 'alipay', 'manual')",
            name="ck_cw_payment_attempt_provider",
        ),
        CheckConstraint(
            "channel IN ('h5', 'jsapi', 'app', 'admin', 'bank_transfer')",
            name="ck_cw_payment_attempt_channel",
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'closed', 'refunded')",
            name="ck_cw_payment_attempt_status",
        ),
        CheckConstraint(
            "(status <> 'succeeded' OR succeeded_at IS NOT NULL) "
            "AND (status <> 'failed' OR failed_at IS NOT NULL) "
            "AND (status <> 'closed' OR closed_at IS NOT NULL) "
            "AND (status <> 'refunded' OR refunded_at IS NOT NULL)",
            name="ck_cw_payment_attempt_state_shape",
        ),
        CheckConstraint(
            "length(idempotency_key) = 64",
            name="ck_cw_payment_attempt_idempotency_length",
        ),
        CheckConstraint("amount >= 0", name="ck_cw_payment_attempt_amount"),
        CheckConstraint("version_no >= 1", name="ck_cw_payment_attempt_version"),
        Index(
            "ix_cw_payment_attempt_order_status",
            "order_id",
            "status",
            "id",
        ),
        Index(
            "ix_cw_payment_attempt_customer_status_created",
            "customer_id",
            "status",
            "created_time",
            "id",
        ),
        Index(
            "ix_cw_payment_attempt_legacy_status_created",
            "legacy_user_id",
            "status",
            "created_time",
            "id",
        ),
        Index(
            "ix_cw_payment_attempt_provider_status_created",
            "provider",
            "status",
            "created_time",
            "id",
        ),
        {"comment": "财不外露支付尝试", **_TABLE_OPTIONS},
    )

    payment_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="不可变支付编号",
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="服务端计算的支付幂等摘要",
    )
    order_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="订单ID",
    )
    order_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="订单编号快照",
    )
    legacy_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "sys_user.id",
            name="fk_cw_payment_attempt_legacy_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
        comment="迁移期原系统用户ID",
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "cw_customer.id",
            name="fk_cw_payment_attempt_customer",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
        comment="H5客户ID",
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="支付提供方",
    )
    channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="支付渠道",
    )
    provider_trade_no: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="支付提供方交易号",
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="支付金额快照",
    )
    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="币种快照",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="支付状态",
    )
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="支付发起时间",
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="支付成功时间",
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="支付失败时间",
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="支付关闭时间",
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="退款完成时间",
    )
    failure_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="安全失败代码",
    )
    failure_message: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="安全失败说明",
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
        foreign_keys=[order_id, order_no],
        lazy="raise",
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
    events: Mapped[list[PaymentEventModel]] = relationship(
        "PaymentEventModel",
        back_populates="payment",
        lazy="raise",
    )


class PaymentEventModel(ModelMixin):
    """Idempotent provider callback envelope without raw payload storage."""

    __tablename__ = "cw_payment_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_id", "payment_no"],
            ["cw_payment_attempt.id", "cw_payment_attempt.payment_no"],
            name="fk_cw_payment_event_payment_identity",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
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
            "event_type IN ('payment_succeeded', 'payment_failed', 'payment_closed', 'refund_succeeded', 'unknown')",
            name="ck_cw_payment_event_type",
        ),
        CheckConstraint(
            "status IN ('received', 'processed', 'ignored', 'failed')",
            name="ck_cw_payment_event_status",
        ),
        CheckConstraint(
            "(status = 'received' AND processed_at IS NULL) "
            "OR (status <> 'received' AND processed_at IS NOT NULL)",
            name="ck_cw_payment_event_state_shape",
        ),
        CheckConstraint(
            "length(payload_digest) = 64",
            name="ck_cw_payment_event_digest_length",
        ),
        CheckConstraint(
            "provider_event_id <> ''",
            name="ck_cw_payment_event_provider_event_id",
        ),
        CheckConstraint("version_no >= 1", name="ck_cw_payment_event_version"),
        Index(
            "ix_cw_payment_event_payment_status",
            "payment_id",
            "status",
            "id",
        ),
        Index(
            "ix_cw_payment_event_provider_received",
            "provider",
            "received_at",
            "id",
        ),
        {"comment": "支付提供方事件去重信封", **_TABLE_OPTIONS},
    )

    payment_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="支付尝试ID",
    )
    payment_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        comment="支付编号快照",
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="支付提供方",
    )
    provider_event_id: Mapped[str] = mapped_column(
        String(191),
        nullable=False,
        comment="提供方事件幂等键",
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="规范化事件类型",
    )
    payload_digest: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="原始回调载荷SHA-256摘要",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="received",
        comment="事件处理状态",
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="接收时间",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="处理完成时间",
    )
    processing_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="安全处理代码",
    )
    processing_message: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="安全处理说明",
    )
    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="乐观锁版本",
    )

    payment: Mapped[PaymentAttemptModel] = relationship(
        "PaymentAttemptModel",
        back_populates="events",
        foreign_keys=[payment_id, payment_no],
        lazy="raise",
    )
