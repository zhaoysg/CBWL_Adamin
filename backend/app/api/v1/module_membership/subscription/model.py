from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import ModelMixin, UserMixin

if TYPE_CHECKING:
    from app.api.v1.module_identity.model import CustomerModel
    from app.api.v1.module_membership.plan.model import MemberPlanModel
    from app.api.v1.module_system.user.model import UserModel


class MemberSubscriptionModel(ModelMixin, UserMixin):
    """用户会员订阅。

    ``status``: 0 生效中（是否过期由时间窗口实时计算），1 已撤销。
    ``source``: manual / payment / migration / promotion。
    ``source_ref`` 是来源侧幂等键，同一来源内全局唯一。

    M2 expand 阶段同时保留 ``user_id`` 与可空 ``customer_id``。只有在迁移
    报告确认全部记录可映射后，后续 contract 迁移才会移除旧字段。
    """

    __tablename__ = "cw_member_subscription"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_ref",
            name="uq_cw_member_subscription_source_ref",
        ),
        CheckConstraint(
            "source IN ('manual', 'payment', 'migration', 'promotion')",
            name="ck_cw_member_subscription_source",
        ),
        CheckConstraint(
            "status IN (0, 1)",
            name="ck_cw_member_subscription_status",
        ),
        CheckConstraint(
            "expires_at > starts_at",
            name="ck_cw_member_subscription_window",
        ),
        CheckConstraint(
            "version_no >= 1",
            name="ck_cw_member_subscription_version",
        ),
        Index(
            "ix_cw_member_subscription_user_window",
            "user_id",
            "status",
            "starts_at",
            "expires_at",
            "id",
        ),
        Index(
            "ix_cw_member_subscription_customer_window",
            "customer_id",
            "status",
            "starts_at",
            "expires_at",
            "id",
        ),
        Index(
            "ix_cw_member_subscription_plan_window",
            "plan_id",
            "status",
            "expires_at",
            "id",
        ),
        Index(
            "ix_cw_member_subscription_expiry",
            "status",
            "expires_at",
            "id",
        ),
        {"comment": "财不外露用户会员订阅"},
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "sys_user.id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
        comment="迁移期原系统用户ID",
    )
    customer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "cw_customer.id",
            name="fk_cw_member_subscription_customer",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=True,
        comment="H5客户ID；M2 expand阶段允许为空",
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "cw_member_plan.id",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
        comment="会员套餐ID",
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="订阅来源",
    )
    source_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="来源幂等键",
    )
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="状态(0生效 1撤销)",
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="生效时间",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="到期时间(排他)",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="撤销时间",
    )
    grant_reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="授权原因",
    )
    revoke_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="撤销原因",
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

    user: Mapped[UserModel] = relationship(
        "UserModel",
        foreign_keys=[user_id],
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
