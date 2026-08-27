from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.v1.module_billing.enums import OrderStatus, sql_enum_values
from app.core.base_model import ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.api.v1.module_membership.plan.model import MemberPlanModel
    from app.api.v1.module_system.user.model import UserModel


class CommerceOrderModel(ModelMixin, UserMixin):
    """会员套餐订单聚合根，金额统一使用最小货币单位。"""

    __tablename__ = "cw_order"
    __table_args__ = (
        UniqueConstraint("order_no", name="uq_cw_order_order_no"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_cw_order_user_idempotency"),
        CheckConstraint(f"status IN ({sql_enum_values(OrderStatus)})", name="ck_cw_order_status"),
        CheckConstraint(
            "amount_minor >= 0 AND paid_amount_minor >= 0 AND paid_amount_minor <= amount_minor "
            "AND refunded_amount_minor >= 0 AND refunded_amount_minor <= paid_amount_minor",
            name="ck_cw_order_amounts",
        ),
        CheckConstraint("version_no >= 1", name="ck_cw_order_version"),
        Index("ix_cw_order_user_status_created", "user_id", "status", "created_time", "id"),
        Index("ix_cw_order_status_expiry", "status", "expires_at", "id"),
        Index("ix_cw_order_plan_created", "plan_id", "created_time", "id"),
        {"comment": "财不外露会员订单"},
    )

    order_no: Mapped[str] = mapped_column(String(64), nullable=False, comment="服务端订单号")
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="下单用户ID",
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cw_member_plan.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="会员套餐ID",
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, comment="用户下单幂等键")
    plan_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, comment="下单时套餐快照")
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="应付金额(最小货币单位)")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, comment="币种")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OrderStatus.PENDING.value,
        comment="订单状态",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="待支付订单到期时间")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="支付完成时间")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="订单关闭时间")
    paid_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="已支付金额")
    refunded_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="累计退款金额")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="内部备注")

    user: Mapped[UserModel] = relationship("UserModel", foreign_keys=[user_id], lazy="raise")
    plan: Mapped[MemberPlanModel] = relationship("MemberPlanModel", foreign_keys=[plan_id], lazy="raise")
