from __future__ import annotations

from collections import Counter

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_identity.enums import IdentityProvider, IdentityRealm
from app.api.v1.module_identity.model import AuthIdentityModel
from app.api.v1.module_membership.subscription.model import MemberSubscriptionModel
from app.api.v1.module_system.user.model import (
    UserModel,
    UserPositionsModel,
    UserRolesModel,
)

from ..normalization import InvalidIdentityIdentifier, normalize_identifier
from .enums import LegacyCandidateDisposition
from .model import LegacyCustomerMapModel
from .schema import LegacyCustomerCandidateSchema, LegacyCustomerMigrationPlanSchema


def legacy_identifier_fallback(legacy_sys_user_id: int) -> str:
    return f"legacy-sys-user:{legacy_sys_user_id}"


def is_usable_credential_hash(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip()
    return len(normalized) >= 20 and normalized not in {"!", "*"}


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
    credential_hash_usable: bool = True,
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
    if not credential_hash_usable:
        reasons.append("credential_reset_required")

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
        subscription_counts = (
            select(
                MemberSubscriptionModel.user_id.label("legacy_sys_user_id"),
                func.count(MemberSubscriptionModel.id).label(
                    "subscription_count"
                ),
            )
            .where(MemberSubscriptionModel.is_deleted.is_(False))
            .group_by(MemberSubscriptionModel.user_id)
            .subquery()
        )
        has_roles = exists(
            select(UserRolesModel.user_id).where(
                UserRolesModel.user_id == UserModel.id
            )
        )
        has_positions = exists(
            select(UserPositionsModel.user_id).where(
                UserPositionsModel.user_id == UserModel.id
            )
        )
        result = await db.execute(
            select(
                UserModel.id.label("legacy_sys_user_id"),
                UserModel.username,
                UserModel.password,
                UserModel.is_superuser,
                UserModel.dept_id,
                UserModel.status,
                subscription_counts.c.subscription_count,
                has_roles.label("has_roles"),
                has_positions.label("has_positions"),
            )
            .join(
                subscription_counts,
                subscription_counts.c.legacy_sys_user_id == UserModel.id,
            )
            .where(UserModel.is_deleted.is_(False))
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

        legacy_user_ids = [row.legacy_sys_user_id for row in rows]
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
        valid_normalized_identifiers: set[str] = set()
        for row in rows:
            try:
                normalized = normalize_identifier(
                    IdentityProvider.PASSWORD,
                    row.username,
                )
                valid_normalized_identifiers.add(normalized)
            except InvalidIdentityIdentifier:
                normalized = legacy_identifier_fallback(
                    row.legacy_sys_user_id
                )
                invalid_identifier_ids.add(row.legacy_sys_user_id)
            normalized_by_user[row.legacy_sys_user_id] = normalized

        conflicting_identifiers: set[str] = set()
        if valid_normalized_identifiers:
            conflicting_identifiers = set(
                (
                    await db.scalars(
                        select(
                            AuthIdentityModel.identifier_normalized
                        ).where(
                            AuthIdentityModel.realm
                            == IdentityRealm.CUSTOMER,
                            AuthIdentityModel.provider
                            == IdentityProvider.PASSWORD,
                            AuthIdentityModel.identifier_normalized.in_(
                                valid_normalized_identifiers
                            ),
                            AuthIdentityModel.is_deleted.is_(False),
                        )
                    )
                ).all()
            )

        candidates: list[LegacyCustomerCandidateSchema] = []
        counts: Counter[LegacyCandidateDisposition] = Counter()
        for row in rows:
            normalized = normalized_by_user[row.legacy_sys_user_id]
            disposition, reasons = classify_legacy_candidate(
                already_mapped=row.legacy_sys_user_id in mapped_ids,
                identifier_conflict=(
                    normalized in conflicting_identifiers
                ),
                is_superuser=bool(row.is_superuser),
                has_department=row.dept_id is not None,
                has_roles=bool(row.has_roles),
                has_positions=bool(row.has_positions),
                user_disabled=row.status != 0,
                invalid_identifier=(
                    row.legacy_sys_user_id in invalid_identifier_ids
                ),
                credential_hash_usable=is_usable_credential_hash(
                    row.password
                ),
            )
            counts[disposition] += 1
            candidates.append(
                LegacyCustomerCandidateSchema(
                    legacy_sys_user_id=row.legacy_sys_user_id,
                    username=row.username,
                    normalized_identifier=normalized,
                    subscription_count=int(row.subscription_count),
                    disposition=disposition,
                    reasons=list(reasons),
                )
            )

        return LegacyCustomerMigrationPlanSchema(
            total=len(candidates),
            eligible=counts[LegacyCandidateDisposition.ELIGIBLE],
            claim_required=counts[
                LegacyCandidateDisposition.CLAIM_REQUIRED
            ],
            already_mapped=counts[
                LegacyCandidateDisposition.ALREADY_MAPPED
            ],
            identifier_conflict=counts[
                LegacyCandidateDisposition.IDENTIFIER_CONFLICT
            ],
            candidates=candidates,
        )
