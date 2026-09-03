from __future__ import annotations

import asyncio

from sqlalchemy import func, select, text

from app.api.v1.module_identity.legacy.enums import (
    LegacyCandidateDisposition,
    LegacyCredentialState,
)
from app.api.v1.module_identity.legacy.migrator import (
    LegacyCustomerMigrationConflict,
    LegacyCustomerMigrationExecutor,
)
from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_identity.legacy.plan import (
    migration_selection_digest,
    select_migration_candidates,
)
from app.api.v1.module_identity.legacy.service import (
    LegacyCustomerMigrationPlanner,
)
from app.api.v1.module_identity.model import (
    AuthIdentityModel,
    AuthSubjectModel,
    CustomerModel,
)
from app.api.v1.module_membership.subscription.model import (
    MemberSubscriptionModel,
)
from app.core.database import async_db_session
from tests.mysql.legacy_customer_migration_fixture import (
    seed_base_candidates,
    seed_ownership_conflict,
)


async def migrate(legacy_user_id: int):
    async with async_db_session() as db:
        async with db.begin():
            return await LegacyCustomerMigrationExecutor.migrate_one(
                db,
                legacy_user_id,
            )


async def verify_plan() -> None:
    async with async_db_session() as db:
        plan = await LegacyCustomerMigrationPlanner.plan_membership_candidates(db)
    assert plan.total == 3
    assert plan.eligible == 1
    assert plan.claim_required == 1
    assert plan.identifier_conflict == 1
    assert plan.already_mapped == 0

    dispositions = {item.legacy_sys_user_id: item.disposition for item in plan.candidates}
    assert dispositions == {
        101: LegacyCandidateDisposition.ELIGIBLE,
        102: LegacyCandidateDisposition.CLAIM_REQUIRED,
        103: LegacyCandidateDisposition.IDENTIFIER_CONFLICT,
    }
    default_selection = select_migration_candidates(
        plan,
        include_claim_required=False,
    )
    assert [item.legacy_sys_user_id for item in default_selection] == [101]
    full_selection = select_migration_candidates(
        plan,
        include_claim_required=True,
    )
    assert [item.legacy_sys_user_id for item in full_selection] == [101, 102]
    assert migration_selection_digest(full_selection) == (migration_selection_digest(list(reversed(full_selection))))


async def verify_migrations() -> None:
    eligible = await migrate(101)
    claim = await migrate(102)
    assert eligible.credential_state is LegacyCredentialState.MIGRATED
    assert eligible.created is True
    assert eligible.subscriptions_backfilled == 1
    assert claim.credential_state is LegacyCredentialState.CLAIM_REQUIRED
    assert claim.created is True
    assert claim.subscriptions_backfilled == 1
    assert claim.reason_code == "role"

    try:
        await migrate(103)
    except LegacyCustomerMigrationConflict:
        pass
    else:
        raise AssertionError("identifier conflict was not rejected")

    async with async_db_session() as db:
        maps = (await db.scalars(select(LegacyCustomerMapModel).order_by(LegacyCustomerMapModel.legacy_sys_user_id))).all()
        assert [item.legacy_sys_user_id for item in maps] == [101, 102]
        assert [item.credential_state for item in maps] == [
            LegacyCredentialState.MIGRATED.value,
            LegacyCredentialState.CLAIM_REQUIRED.value,
        ]

        eligible_identity = await db.scalar(select(AuthIdentityModel).where(AuthIdentityModel.identifier_normalized == "eligible_user"))
        assert eligible_identity is not None
        assert eligible_identity.credential_hash == ("$argon2id$legacy-eligible-long-hash-value")
        assert eligible_identity.verified_at is not None

        claim_customer = await db.get(CustomerModel, maps[1].customer_id)
        assert claim_customer is not None
        claim_identity_count = await db.scalar(select(func.count(AuthIdentityModel.id)).where(AuthIdentityModel.subject_id == claim_customer.subject_id))
        assert claim_identity_count == 0

        rows = (
            await db.execute(
                select(
                    MemberSubscriptionModel.id,
                    MemberSubscriptionModel.customer_id,
                ).order_by(MemberSubscriptionModel.id)
            )
        ).all()
        assert rows[0].customer_id == eligible.customer_id
        assert rows[1].customer_id == claim.customer_id
        assert rows[2].customer_id is None


async def verify_idempotent_repair() -> None:
    async with async_db_session() as db:
        async with db.begin():
            await db.execute(text("UPDATE cw_member_subscription SET customer_id = NULL WHERE id = 301"))

    repaired = await migrate(101)
    assert repaired.created is False
    assert repaired.subscriptions_backfilled == 1

    rerun = await migrate(101)
    assert rerun.created is False
    assert rerun.customer_id == repaired.customer_id
    assert rerun.subscriptions_backfilled == 0

    async with async_db_session() as db:
        map_count = await db.scalar(select(func.count(LegacyCustomerMapModel.id)).where(LegacyCustomerMapModel.legacy_sys_user_id == 101))
        identity_count = await db.scalar(select(func.count(AuthIdentityModel.id)).where(AuthIdentityModel.identifier_normalized == "eligible_user"))
        assert map_count == 1
        assert identity_count == 1


async def verify_conflict_rollback() -> None:
    async with async_db_session() as db:
        async with db.begin():
            await seed_ownership_conflict(db)

    async with async_db_session() as db:
        before = (
            await db.scalar(select(func.count(AuthSubjectModel.id))),
            await db.scalar(select(func.count(CustomerModel.id))),
            await db.scalar(select(func.count(LegacyCustomerMapModel.id))),
        )

    try:
        await migrate(104)
    except LegacyCustomerMigrationConflict:
        pass
    else:
        raise AssertionError("conflicting subscription owner was not rejected")

    async with async_db_session() as db:
        after = (
            await db.scalar(select(func.count(AuthSubjectModel.id))),
            await db.scalar(select(func.count(CustomerModel.id))),
            await db.scalar(select(func.count(LegacyCustomerMapModel.id))),
        )
        assert after == before
        assert await db.scalar(select(MemberSubscriptionModel.customer_id).where(MemberSubscriptionModel.id == 304)) == 550
        assert await db.scalar(select(func.count(LegacyCustomerMapModel.id)).where(LegacyCustomerMapModel.legacy_sys_user_id == 104)) == 0


async def main() -> None:
    async with async_db_session() as db:
        async with db.begin():
            await seed_base_candidates(db)
    await verify_plan()
    await verify_migrations()
    await verify_idempotent_repair()
    await verify_conflict_rollback()
    print("legacy customer migration MySQL verification passed")


if __name__ == "__main__":
    asyncio.run(main())
