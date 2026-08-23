from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

from app.core.base_schema import AuthSchema

from .subscription.model import MemberSubscriptionModel
from .subscription.service import effective_subscriptions

AccessLevel = Literal["public", "login", "member", "premium"]


@dataclass(frozen=True, slots=True)
class EntitlementDecision:
    allowed: bool
    reason: str
    subscription_id: int | None = None
    plan_id: int | None = None


async def evaluate_entitlement(
    *,
    db,
    auth: AuthSchema | None,
    access_level: AccessLevel,
    allowed_plan_ids: Collection[int] = (),
) -> EntitlementDecision:
    """Evaluate access server-side. Administrator status never bypasses membership."""

    if access_level == "public":
        return EntitlementDecision(True, "public")
    if auth is None or auth.user.id <= 0:
        return EntitlementDecision(False, "authentication_required")
    if access_level == "login":
        return EntitlementDecision(True, "authenticated")

    rows: list[MemberSubscriptionModel] = await effective_subscriptions(db, auth.user.id)
    if not rows:
        return EntitlementDecision(False, "active_membership_required")

    if access_level == "member":
        row = rows[0]
        return EntitlementDecision(True, "active_membership", row.id, row.plan_id)

    allowed = set(allowed_plan_ids)
    for row in rows:
        if row.plan_id in allowed:
            return EntitlementDecision(True, "matching_plan", row.id, row.plan_id)
    return EntitlementDecision(False, "matching_plan_required")
