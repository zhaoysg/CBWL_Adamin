from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.api.v1.module_membership.plan.model import MemberPlanModel
    from app.api.v1.module_system.user.model import UserModel


class MemberSubscriptionModel(ModelMixin, UserMixin):
    """会员订阅实例。有效性由状态与半开时间区间共同决定。"""

    __tablename__ = "cw_member_subscription"
    __table_args__ = (
        UniqueConstraint("external_ref", name="uq_cw_member_subscription_external_ref"),
        CheckConstraint("status IN ('active', 'revoked')", name="ck_cw_member_subscription_status"),
        CheckConstraint("source IN ('manual', 'order', 'migration')", name="ck_cw_member_subscription_source"),
        CheckConstraint("expires_at > starts_at", name="ck_cw_member_subscription_period"),
        CheckConstraint("version_no >= 1", name="ck_cw_member_subscription_version"),
        Index(
            "ix_cw_member_subscription_user_effective",
            "user_id",
            "status",
            "starts_at",
            "expires_at",
            "plan_id",
        ),
        Index(
            "ix_cw_member_subscription_plan_effective",
            "plan_id",
            "status",
            "starts_at",
            "expires_at",
            "user_id",
        ),
        {"comment": "财不外露会员订阅"},
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sys_user.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="会员用户ID",
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cw_member_plan.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        comment="会员套餐ID",
    )
    external_ref: Mapped[str] = mapped_column(String(128), nullable=False, comment="幂等业务号")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", comment="来源")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", comment="状态")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="生效时间")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="失效时间")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="撤销时间")
    revoke_reason: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="撤销原因")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="运营备注")

    user: Mapped[UserModel] = relationship(foreign_keys=[user_id], lazy="raise")
    plan: Mapped[MemberPlanModel] = relationship(foreign_keys=[plan_id], lazy="raise")

    @property
    def user_name(self) -> str:
        return self.user.name or self.user.username or str(self.user_id)

    @property
    def plan_name(self) -> str:
        return self.plan.plan_name

    @property
    def plan_code(self) -> str:
        return self.plan.plan_code
