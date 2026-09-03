from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_identity.enums import (
    CustomerRegisterSource,
    IdentityProvider,
    IdentityRealm,
    IdentityStatus,
)
from app.api.v1.module_identity.model import AuthSubjectModel, CustomerModel
from app.api.v1.module_identity.schema import CustomerProvisionSchema
from app.api.v1.module_identity.service import IdentityService

from ..normalization import InvalidIdentityIdentifier, normalize_identifier
from .enums import (
    LegacyCandidateDisposition,
    LegacyCredentialState,
    LegacyMigrationSource,
)
from .model import LegacyCustomerMapModel
from .repository import (
    LegacyCustomerMigrationConflict,
    LegacyCustomerMigrationError,
    LegacyUserSnapshot,
    assert_subscription_ownership,
    backfill_subscriptions,
    customer_identifier_exists,
    ensure_customer_exists,
    load_mapping_for_update,
    load_user_for_update,
    lock_subscriptions,
)
from .schema import LegacyCustomerMigrationResultSchema
from .service import (
    classify_legacy_candidate,
    is_usable_credential_hash,
    legacy_identifier_fallback,
)

_REASON_CODES = {
    "superuser": "superuser",
    "department_assigned": "department",
    "role_assigned": "role",
    "position_assigned": "position",
    "legacy_user_disabled": "disabled",
    "invalid_identifier": "invalid_identifier",
    "credential_reset_required": "credential_reset",
}


def _primary_reason(reasons: tuple[str, ...]) -> str | None:
    if not reasons:
        return None
    return _REASON_CODES.get(reasons[0], "manual_review")


class LegacyCustomerMigrationExecutor:
    """Migrate one legacy member inside the caller-owned transaction."""

    @classmethod
    async def migrate_one(
        cls,
        db: AsyncSession,
        legacy_sys_user_id: int,
    ) -> LegacyCustomerMigrationResultSchema:
        if legacy_sys_user_id <= 0:
            raise ValueError("legacy_sys_user_id must be positive")

        user = await load_user_for_update(db, legacy_sys_user_id)
        subscriptions = await lock_subscriptions(db, legacy_sys_user_id)
        if not subscriptions:
            raise LegacyCustomerMigrationError("legacy user has no active migration candidate subscriptions")

        existing_map = await load_mapping_for_update(
            db,
            legacy_sys_user_id,
        )
        if existing_map is not None:
            await ensure_customer_exists(db, existing_map.customer_id)
            assert_subscription_ownership(
                subscriptions,
                existing_map.customer_id,
            )
            backfilled = await backfill_subscriptions(
                db,
                legacy_sys_user_id=legacy_sys_user_id,
                customer_id=existing_map.customer_id,
            )
            return LegacyCustomerMigrationResultSchema(
                legacy_sys_user_id=legacy_sys_user_id,
                customer_id=existing_map.customer_id,
                credential_state=LegacyCredentialState(existing_map.credential_state),
                created=False,
                subscriptions_backfilled=backfilled,
                reason_code=existing_map.reason_code,
            )

        try:
            normalized_identifier = normalize_identifier(
                IdentityProvider.PASSWORD,
                user.username,
            )
            invalid_identifier = False
        except InvalidIdentityIdentifier:
            normalized_identifier = legacy_identifier_fallback(user.id)
            invalid_identifier = True

        identifier_conflict = (
            False
            if invalid_identifier
            else await customer_identifier_exists(
                db,
                normalized_identifier,
            )
        )
        disposition, reasons = classify_legacy_candidate(
            already_mapped=False,
            identifier_conflict=identifier_conflict,
            is_superuser=user.is_superuser,
            has_department=user.dept_id is not None,
            has_roles=user.has_roles,
            has_positions=user.has_positions,
            user_disabled=user.status != 0,
            invalid_identifier=invalid_identifier,
            credential_hash_usable=is_usable_credential_hash(user.password),
        )
        if disposition is LegacyCandidateDisposition.IDENTIFIER_CONFLICT:
            raise LegacyCustomerMigrationConflict("customer realm identifier already exists")

        now = datetime.now(UTC)
        if disposition is LegacyCandidateDisposition.ELIGIBLE:
            provisioned = await IdentityService.create_customer(
                db,
                CustomerProvisionSchema(
                    provider=IdentityProvider.PASSWORD,
                    identifier=user.username,
                    nickname=cls._nickname(user),
                    avatar_url=user.avatar,
                    register_source=CustomerRegisterSource.MIGRATION,
                ),
                credential_hash=user.password,
            )
            provisioned.identity.verified_at = now
            customer = provisioned.customer
            credential_state = LegacyCredentialState.MIGRATED
        else:
            customer = await cls._create_claim_required_customer(db, user)
            credential_state = LegacyCredentialState.CLAIM_REQUIRED

        if customer.id is None:
            raise RuntimeError("database did not assign customer id")
        assert_subscription_ownership(subscriptions, customer.id)

        mapping = LegacyCustomerMapModel(
            legacy_sys_user_id=user.id,
            customer_id=customer.id,
            credential_state=credential_state.value,
            source=LegacyMigrationSource.MEMBERSHIP.value,
            reason_code=_primary_reason(reasons),
            identifier_snapshot=normalized_identifier,
            migrated_at=now,
            version_no=1,
        )
        db.add(mapping)
        await db.flush()
        backfilled = await backfill_subscriptions(
            db,
            legacy_sys_user_id=user.id,
            customer_id=customer.id,
        )
        await db.flush()
        return LegacyCustomerMigrationResultSchema(
            legacy_sys_user_id=user.id,
            customer_id=customer.id,
            credential_state=credential_state,
            created=True,
            subscriptions_backfilled=backfilled,
            reason_code=mapping.reason_code,
        )

    @staticmethod
    async def _create_claim_required_customer(
        db: AsyncSession,
        user: LegacyUserSnapshot,
    ) -> CustomerModel:
        actor_status = IdentityStatus.DISABLED.value if user.status != 0 else IdentityStatus.ACTIVE.value
        subject = AuthSubjectModel(
            realm=IdentityRealm.CUSTOMER.value,
            status=actor_status,
            version_no=1,
        )
        db.add(subject)
        await db.flush()
        if subject.id is None:
            raise RuntimeError("database did not assign auth subject id")

        customer = CustomerModel(
            subject_id=subject.id,
            realm=IdentityRealm.CUSTOMER.value,
            customer_no=f"C{uuid4().hex[:20].upper()}",
            nickname=LegacyCustomerMigrationExecutor._nickname(user),
            avatar_url=user.avatar,
            register_source=CustomerRegisterSource.MIGRATION.value,
            status=actor_status,
            version_no=1,
        )
        db.add(customer)
        await db.flush()
        return customer

    @staticmethod
    def _nickname(user: LegacyUserSnapshot) -> str:
        normalized = user.name.strip()
        return normalized or f"用户{user.id}"


__all__ = [
    "LegacyCustomerMigrationConflict",
    "LegacyCustomerMigrationError",
    "LegacyCustomerMigrationExecutor",
]
