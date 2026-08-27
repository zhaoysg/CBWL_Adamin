from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.api.v1.module_billing.enums import OutboxEventStatus, sql_enum_values
from app.core.base_model import ModelMixin


class OutboxEventModel(ModelMixin):
    """与业务事务一同写入、提交后异步投递的发件箱事件。"""

    __tablename__ = "cw_outbox_event"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_cw_outbox_event_event_id"),
        UniqueConstraint("deduplication_key", name="uq_cw_outbox_event_deduplication"),
        CheckConstraint(f"status IN ({sql_enum_values(OutboxEventStatus)})", name="ck_cw_outbox_event_status"),
        CheckConstraint("attempts >= 0", name="ck_cw_outbox_event_attempts"),
        CheckConstraint("version_no >= 1", name="ck_cw_outbox_event_version"),
        Index("ix_cw_outbox_event_delivery", "status", "available_at", "created_time", "id"),
        Index("ix_cw_outbox_event_aggregate", "aggregate_type", "aggregate_id", "created_time", "id"),
        {"comment": "财不外露事务发件箱"},
    )

    event_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="事件ID")
    deduplication_key: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="事件去重键")
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="聚合类型")
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False, comment="聚合标识")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="领域事件类型")
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, comment="非敏感事件载荷")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OutboxEventStatus.PENDING.value,
        comment="投递状态",
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="最早可投递时间",
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="投递完成时间")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="投递尝试次数")
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="脱敏的最后错误")
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本")
