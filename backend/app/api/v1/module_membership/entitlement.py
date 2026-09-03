from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from .subscription.model import MemberSubscriptionModel

EntitlementFailure = Literal[
    "login_required",
    "membership_required",
    "plan_required",
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class EntitlementContext:
    user_id: int | None
    active_plan_ids: frozenset[int]
    subscriptions: tuple[MemberSubscriptionModel, ...]
    customer_id: int | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None or self.customer_id is not None

    @property
    def is_member(self) -> bool:
        return bool(self.active_plan_ids)


@dataclass(frozen=True, slots=True)
class EntitlementDecision:
    can_access: bool
    failure: EntitlementFailure | None = None


async def load_entitlement_context(
    db: AsyncSession,
    user_id: int | None,
    *,
    now: datetime | None = None,
) -> EntitlementContext:
    if user_id is None:
        return EntitlementContext(
            user_id=None,
            active_plan_ids=frozenset(),
            subscriptions=(),
        )

    current = as_utc(now or utc_now())
    result = await db.execute(
        select(MemberSubscriptionModel)
        .options(joinedload(MemberSubscriptionModel.plan))
        .where(
            MemberSubscriptionModel.user_id == user_id,
            MemberSubscriptionModel.status == 0,
            MemberSubscriptionModel.starts_at <= current,
            MemberSubscriptionModel.expires_at > current,
            MemberSubscriptionModel.is_deleted.is_(False),
        )
        .order_by(
            MemberSubscriptionModel.expires_at.desc(),
            MemberSubscriptionModel.id.desc(),
        )
    )
    subscriptions = tuple(result.scalars().unique().all())
    return EntitlementContext(
        user_id=user_id,
        active_plan_ids=frozenset(item.plan_id for item in subscriptions),
        subscriptions=subscriptions,
    )


def evaluate_content_access(
    *,
    access_level: str,
    required_plan_ids: set[int] | frozenset[int],
    context: EntitlementContext,
) -> EntitlementDecision:
    if access_level == "public":
        return EntitlementDecision(can_access=True)
    if not context.is_authenticated:
        return EntitlementDecision(
            can_access=False,
            failure="login_required",
        )
    if access_level == "login":
        return EntitlementDecision(can_access=True)
    if access_level == "member":
        if context.is_member:
            return EntitlementDecision(can_access=True)
        return EntitlementDecision(
            can_access=False,
            failure="membership_required",
        )
    if access_level == "premium":
        if context.active_plan_ids.intersection(required_plan_ids):
            return EntitlementDecision(can_access=True)
        return EntitlementDecision(
            can_access=False,
            failure="plan_required",
        )
    return EntitlementDecision(can_access=False, failure="plan_required")


async def count_active_members(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    current = as_utc(now or utc_now())
    value = await db.scalar(
        select(func.count(func.distinct(MemberSubscriptionModel.user_id))).where(
            MemberSubscriptionModel.status == 0,
            MemberSubscriptionModel.starts_at <= current,
            MemberSubscriptionModel.expires_at > current,
            MemberSubscriptionModel.is_deleted.is_(False),
        )
    )
    return int(value or 0)
