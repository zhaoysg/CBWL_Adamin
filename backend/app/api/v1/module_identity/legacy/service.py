from __future__ import annotations

from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.module_identity.enums import IdentityProvider, IdentityRealm
from app.api.v1.module_identity.model import AuthIdentityModel
from app.api.v1.module_membership.subscription.model import MemberSubscriptionModel
from app.api.v1.module_system.user.model import UserModel

from ..normalization import InvalidIdentityIdentifier, normalize_identifier
from .enums import LegacyCandidateDisposition
from .model import LegacyCustomerMapModel
from .schema import LegacyCustomerCandidateSchema, LegacyCustomerMigrationPlanSchema


def classify_legacy_candidate(
    *,
    already_mapped: bool,
    identifier_conflict: bool,
    is_superuser: bool,
    has_department: bool,
    has_roles: bool,
    has_positions: bool,
    user_disabled: bool,
    invalid_identifier: bool,
) -> tuple[LegacyCandidateDisposition, tuple[str, ...]]:
    """Classify without mutating data; safe defaults require account claim."""

    if already_mapped:
        return LegacyCandidateDisposition.ALREADY_MAPPED, ()
    if identifier_conflict:
        return LegacyCandidateDisposition.IDENTIFIER_CONFLICT, (
            "customer_identifier_conflict",
        )

    reasons: list[str] = []
    if is_superuser:
        reasons.append("superuser")
    if has_department:
        reasons.append("department_assigned")
    if has_roles:
        reasons.append("role_assigned")
    if has_positions:
        reasons.append("position_assigned")
    if user_disabled:
        reasons.append("legacy_user_disabled")
    if invalid_identifier:
        reasons.append("invalid_identifier")

    if reasons:
        return LegacyCandidateDisposition.CLAIM_REQUIRED, tuple(reasons)
    return LegacyCandidateDisposition.ELIGIBLE, ()


class LegacyCustomerMigrationPlanner:
    """Read-only planner for the expand/migrate/contract customer transition."""

    @classmethod
    async def plan_membership_candidates(
        cls,
        db: AsyncSession,
    ) -> LegacyCustomerMigrationPlanSchema:
        result = await db.execute(
            select(
                UserModel,
                func.count(MemberSubscriptionModel.id).label("subscription_count"),
            )
            .join(
                MemberSubscriptionModel,
                MemberSubscriptionModel.user_id == UserModel.id,
            )
            .options(
                selectinload(UserModel.roles),
                selectinload(UserModel.positions),
            )
            .where(
                UserModel.is_deleted.is_(False),
                MemberSubscriptionModel.is_deleted.is_(False),
            )
            .group_by(UserModel.id)
            .order_by(UserModel.id)
        )
        rows = result.all()
        if not rows:
            return LegacyCustomerMigrationPlanSchema(
                total=0,
                eligible=0,
                claim_required=0,
                already_mapped=0,
                identifier_conflict=0,
                candidates=[],
            )

        legacy_user_ids = [user.id for user, _ in rows]
        mapped_ids = set(
            (
                await db.scalars(
                    select(LegacyCustomerMapModel.legacy_sys_user_id).where(
                        LegacyCustomerMapModel.legacy_sys_user_id.in_(
                            legacy_user_ids
                        ),
                        LegacyCustomerMapModel.is_deleted.is_(False),
                    )
                )
            ).all()
        )

        normalized_by_user: dict[int, str] = {}
        invalid_identifier_ids: set[int] = set()
        for user, _ in rows:
            try:
                normalized_by_user[user.id] = normalize_identifier(
                    IdentityProvider.PASSWORD,
                    user.username,
                )
            except InvalidIdentityIdentifier:
                normalized_by_user[user.id] = user.username.strip().casefold()
                invalid_identifier_ids.add(user.id)

        normalized_identifiers = set(normalized_by_user.values())
        conflicting_identifiers = set(
            (
                await db.scalars(
                    select(AuthIdentityModel.identifier_normalized).where(
                        AuthIdentityModel.realm == IdentityRealm.CUSTOMER,
                        AuthIdentityModel.provider == IdentityProvider.PASSWORD,
                        AuthIdentityModel.identifier_normalized.in_(
                            normalized_identifiers
                        ),
                        AuthIdentityModel.is_deleted.is_(False),
                    )
                )
            ).all()
        )

        candidates: list[LegacyCustomerCandidateSchema] = []
        counts: Counter[LegacyCandidateDisposition] = Counter()
        for user, subscription_count in rows:
            normalized = normalized_by_user[user.id]
            disposition, reasons = classify_legacy_candidate(
                already_mapped=user.id in mapped_ids,
                identifier_conflict=normalized in conflicting_identifiers,
                is_superuser=bool(user.is_superuser),
                has_department=user.dept_id is not None,
                has_roles=bool(user.roles),
                has_positions=bool(user.positions),
                user_disabled=user.status != 0,
                invalid_identifier=user.id in invalid_identifier_ids,
            )
            counts[disposition] += 1
            candidates.append(
                LegacyCustomerCandidateSchema(
                    legacy_sys_user_id=user.id,
                    username=user.username,
                    normalized_identifier=normalized,
                    subscription_count=int(subscription_count),
                    disposition=disposition,
                    reasons=list(reasons),
                )
            )

        return LegacyCustomerMigrationPlanSchema(
            total=len(candidates),
            eligible=counts[LegacyCandidateDisposition.ELIGIBLE],
            claim_required=counts[LegacyCandidateDisposition.CLAIM_REQUIRED],
            already_mapped=counts[LegacyCandidateDisposition.ALREADY_MAPPED],
            identifier_conflict=counts[
                LegacyCandidateDisposition.IDENTIFIER_CONFLICT
            ],
            candidates=candidates,
        )
