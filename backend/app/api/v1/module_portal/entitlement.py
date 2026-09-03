from __future__ import annotations

from datetime import datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.v1.module_membership.entitlement import (
    EntitlementContext,
    as_utc,
    load_entitlement_context,
    utc_now,
)
from app.api.v1.module_membership.subscription.model import (
    MemberSubscriptionModel,
)
from app.common.enums import RET
from app.config.portal_auth import portal_auth_settings
from app.core.exceptions import CustomException
from app.core.logger import logger

from .principal import PortalPrincipal


def _subscription_ids(
    context: EntitlementContext,
) -> tuple[int, ...]:
    return tuple(sorted(item.id for item in context.subscriptions))


async def _load_customer_entitlement_context(
    db: AsyncSession,
    *,
    legacy_user_id: int | None,
    customer_id: int,
    now: datetime,
) -> EntitlementContext:
    result = await db.execute(
        select(MemberSubscriptionModel)
        .options(joinedload(MemberSubscriptionModel.plan))
        .where(
            MemberSubscriptionModel.customer_id == customer_id,
            MemberSubscriptionModel.status == 0,
            MemberSubscriptionModel.starts_at <= now,
            MemberSubscriptionModel.expires_at > now,
            MemberSubscriptionModel.is_deleted.is_(False),
        )
        .order_by(
            MemberSubscriptionModel.expires_at.desc(),
            MemberSubscriptionModel.id.desc(),
        )
    )
    subscriptions = tuple(result.scalars().unique().all())
    return EntitlementContext(
        user_id=legacy_user_id,
        customer_id=customer_id,
        active_plan_ids=frozenset(item.plan_id for item in subscriptions),
        subscriptions=subscriptions,
    )


def _raise_consistency_error(
    *,
    principal: PortalPrincipal,
    legacy_ids: tuple[int, ...],
    customer_ids: tuple[int, ...],
) -> None:
    logger.error(
        "Portal 会员权益双读不一致: legacy_user_id={} customer_id={} legacy_subscription_ids={} customer_subscription_ids={}",
        principal.legacy_user_id,
        principal.customer_id,
        legacy_ids,
        customer_ids,
    )
    raise CustomException(
        msg="会员权益数据同步中，请稍后重试",
        code=RET.SERVICE_UNAVAILABLE.code,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


async def load_portal_entitlement_context(
    db: AsyncSession,
    principal: PortalPrincipal,
    *,
    now: datetime | None = None,
) -> EntitlementContext:
    """Load entitlement according to the independently staged read mode.

    ``dual`` performs two real queries for a migrated customer and requires the
    same active subscription IDs. A mismatch fails closed so an incomplete
    backfill cannot accidentally grant or revoke protected content access.
    """

    if not principal.is_authenticated:
        return EntitlementContext(
            user_id=None,
            customer_id=None,
            active_plan_ids=frozenset(),
            subscriptions=(),
        )

    current = as_utc(now or utc_now())
    mode = portal_auth_settings.ENTITLEMENT_MODE
    legacy_context = await load_entitlement_context(
        db,
        principal.legacy_user_id,
        now=current,
    )
    if mode == "legacy":
        return legacy_context

    if principal.customer_id is None:
        if mode == "dual":
            return legacy_context
        raise CustomException(
            msg="客户会员身份尚未完成迁移",
            code=RET.SERVICE_UNAVAILABLE.code,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    customer_context = await _load_customer_entitlement_context(
        db,
        legacy_user_id=principal.legacy_user_id,
        customer_id=principal.customer_id,
        now=current,
    )
    if mode == "customer":
        return customer_context

    legacy_ids = _subscription_ids(legacy_context)
    customer_ids = _subscription_ids(customer_context)
    if legacy_ids != customer_ids:
        _raise_consistency_error(
            principal=principal,
            legacy_ids=legacy_ids,
            customer_ids=customer_ids,
        )
    return customer_context


__all__ = ["load_portal_entitlement_context"]
