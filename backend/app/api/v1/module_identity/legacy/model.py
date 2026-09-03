from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import ModelMixin

if TYPE_CHECKING:
    from app.api.v1.module_identity.model import CustomerModel
    from app.api.v1.module_system.user.model import UserModel


_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
}


class LegacyCustomerMapModel(ModelMixin):
    """One-to-one audit bridge from a legacy ``sys_user`` to a customer actor."""

    __tablename__ = "cw_customer_legacy_map"
    __table_args__ = (
        UniqueConstraint(
            "legacy_sys_user_id",
            name="uq_cw_customer_legacy_map_legacy_user",
        ),
        UniqueConstraint(
            "customer_id",
            name="uq_cw_customer_legacy_map_customer",
        ),
        CheckConstraint(
            "credential_state IN ('migrated', 'claim_required')",
            name="ck_cw_customer_legacy_map_credential_state",
        ),
        CheckConstraint(
            "source IN ('membership', 'manual')",
            name="ck_cw_customer_legacy_map_source",
        ),
        CheckConstraint(
            "version_no >= 1",
            name="ck_cw_customer_legacy_map_version",
        ),
        Index(
            "ix_cw_customer_legacy_map_state",
            "credential_state",
            "source",
            "id",
        ),
        {"comment": "存量系统用户到H5客户的迁移映射", **_TABLE_OPTIONS},
    )

    legacy_sys_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "sys_user.id",
            name="fk_cw_customer_legacy_map_legacy_user",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
        comment="迁移前系统用户ID",
    )
    customer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "cw_customer.id",
            name="fk_cw_customer_legacy_map_customer",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
        comment="迁移后客户ID",
    )
    credential_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="凭据迁移状态",
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="映射来源",
    )
    reason_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="需认领等原因代码",
    )
    identifier_snapshot: Mapped[str] = mapped_column(
        String(191),
        nullable=False,
        comment="迁移时规范化登录标识快照",
    )
    migrated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="映射完成时间",
    )
    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="乐观锁版本",
    )

    legacy_user: Mapped[UserModel] = relationship(
        "UserModel",
        foreign_keys=[legacy_sys_user_id],
        lazy="raise",
    )
    customer: Mapped[CustomerModel] = relationship(
        "CustomerModel",
        foreign_keys=[customer_id],
        lazy="raise",
    )
