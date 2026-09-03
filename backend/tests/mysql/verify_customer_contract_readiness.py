from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.api.v1.module_identity.contract import (
    CustomerContractReadinessService,
)
from app.core.database import async_db_session


async def _report():
    async with async_db_session() as db:
        return await CustomerContractReadinessService.build_report(db)


def _counts(report) -> dict[str, int]:
    return {item.code: item.count for item in report.checks}


async def _execute(statement: str) -> None:
    async with async_db_session() as db, db.begin():
        await db.execute(text(statement))


async def _seed() -> None:
    async with async_db_session() as db, db.begin():
        await db.execute(text("INSERT INTO sys_user (id, is_deleted) VALUES (101, 0)"))
        await db.execute(
            text(
                "INSERT INTO cw_member_plan "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "plan_code, plan_name, level_no, price, currency, "
                "duration_days, benefits, status, sort_no) VALUES "
                "(201, 'plan-201', 0, UTC_TIMESTAMP(), UTC_TIMESTAMP(), "
                "'plan-201', 'Plan 201', 1, 0, 'CNY', 30, "
                "JSON_ARRAY(), 0, 0)"
            )
        )
        await db.execute(
            text(
                "INSERT INTO auth_subject "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "realm, status, version_no) VALUES "
                "(401, 'subject-401', 0, UTC_TIMESTAMP(), "
                "UTC_TIMESTAMP(), 'customer', 'active', 1)"
            )
        )
        await db.execute(
            text(
                "INSERT INTO cw_customer "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "subject_id, realm, customer_no, nickname, "
                "register_source, status, version_no) VALUES "
                "(501, 'customer-501', 0, UTC_TIMESTAMP(), "
                "UTC_TIMESTAMP(), 401, 'customer', "
                "'CREADY0000000501', 'Ready Customer', "
                "'migration', 'active', 1)"
            )
        )
        await db.execute(
            text(
                "INSERT INTO auth_identity "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "subject_id, realm, provider, identifier_normalized, "
                "credential_hash, status, version_no) VALUES "
                "(402, 'identity-402', 0, UTC_TIMESTAMP(), "
                "UTC_TIMESTAMP(), 401, 'customer', 'password', "
                "'ready_user', '$argon2id$ready-long-hash-value', "
                "'active', 1)"
            )
        )
        await db.execute(
            text(
                "INSERT INTO cw_customer_legacy_map "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "legacy_sys_user_id, customer_id, credential_state, "
                "source, identifier_snapshot, migrated_at, version_no) "
                "VALUES (601, 'map-601', 0, UTC_TIMESTAMP(), "
                "UTC_TIMESTAMP(), 101, 501, 'migrated', 'membership', "
                "'ready_user', UTC_TIMESTAMP(), 1)"
            )
        )
        await db.execute(
            text(
                "INSERT INTO cw_member_subscription "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "user_id, customer_id, plan_id, source, source_ref, "
                "status, starts_at, expires_at, grant_reason, "
                "version_no) VALUES "
                "(301, 'subscription-301', 0, UTC_TIMESTAMP(), "
                "UTC_TIMESTAMP(), 101, 501, 201, 'migration', "
                "'ready-301', 0, UTC_TIMESTAMP(), "
                "DATE_ADD(UTC_TIMESTAMP(), INTERVAL 30 DAY), "
                "'contract readiness CI', 1)"
            )
        )


async def main() -> None:
    await _seed()

    ready = await _report()
    assert ready.ready is True
    assert ready.blocking_codes == []
    assert ready.summary == {
        "subscriptions": 1,
        "mapped_subscriptions": 1,
        "active_maps": 1,
        "migrated_maps": 1,
        "claim_required_maps": 0,
    }

    await _execute(
        "UPDATE cw_member_subscription SET customer_id = NULL WHERE id = 301"
    )
    missing = await _report()
    assert missing.ready is False
    assert _counts(missing)["subscription_customer_missing"] == 1

    await _execute(
        "UPDATE cw_member_subscription SET customer_id = 501 WHERE id = 301"
    )
    await _execute(
        "UPDATE cw_customer_legacy_map "
        "SET credential_state = 'claim_required' WHERE id = 601"
    )
    claim = await _report()
    assert claim.ready is False
    assert _counts(claim)["claim_required_remaining"] == 1

    await _execute(
        "UPDATE cw_customer_legacy_map "
        "SET credential_state = 'migrated' WHERE id = 601"
    )
    await _execute("UPDATE auth_identity SET is_deleted = 1 WHERE id = 402")
    missing_identity = await _report()
    assert missing_identity.ready is False
    assert (
        _counts(missing_identity)["migrated_password_identity_invalid"] == 1
    )

    await _execute("UPDATE auth_identity SET is_deleted = 0 WHERE id = 402")
    await _execute("UPDATE cw_customer SET status = 'disabled' WHERE id = 501")
    disabled = await _report()
    assert disabled.ready is False
    assert _counts(disabled)["mapping_customer_invalid"] == 1

    await _execute("UPDATE cw_customer SET status = 'active' WHERE id = 501")
    final = await _report()
    assert final.ready is True
    print("customer contract readiness MySQL verification passed")


if __name__ == "__main__":
    asyncio.run(main())
