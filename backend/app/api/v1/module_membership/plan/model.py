from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ModelMixin, UserMixin


class MemberPlanModel(ModelMixin, UserMixin):
    """会员套餐。

    ``rank`` 用于服务端权益比较，数值越大代表可访问的会员层级越高。
    数据库列使用 ``level_no``，避免和 MySQL 保留字 ``RANK`` 冲突。
    ``status``: 0 启用，1 停用。
    """

    __tablename__ = "cw_member_plan"
    __table_args__ = (
        UniqueConstraint("plan_code", name="uq_cw_member_plan_code"),
        UniqueConstraint("plan_name", name="uq_cw_member_plan_name"),
        CheckConstraint("level_no >= 1 AND level_no <= 100", name="ck_cw_member_plan_rank"),
        CheckConstraint("price >= 0", name="ck_cw_member_plan_price"),
        CheckConstraint("duration_days > 0", name="ck_cw_member_plan_duration"),
        CheckConstraint("status IN (0, 1)", name="ck_cw_member_plan_status"),
        Index("ix_cw_member_plan_enabled_sort", "status", "sort_no", "id"),
        {"comment": "财不外露会员套餐"},
    )

    plan_code: Mapped[str] = mapped_column(String(64), nullable=False, comment="套餐编码")
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="套餐名称")
    rank: Mapped[int] = mapped_column("level_no", Integer, nullable=False, default=1, comment="权益等级")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"), comment="价格")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY", comment="币种")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365, comment="有效天数")
    benefits: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, comment="权益列表")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="状态(0启用 1停用)")
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="排序")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="说明")
