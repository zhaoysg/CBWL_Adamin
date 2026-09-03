from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_base_candidates(db: AsyncSession) -> None:
    await db.execute(
        text(
            "INSERT INTO sys_user "
            "(id, username, password, name, avatar, is_superuser, "
            "status, dept_id, is_deleted) VALUES "
            "(101, 'eligible_user', "
            "'$argon2id$legacy-eligible-long-hash-value', "
            "'Eligible User', NULL, 0, 0, NULL, 0), "
            "(102, 'admin_like_user', "
            "'$argon2id$legacy-admin-long-hash-value', "
            "'Admin Like', NULL, 0, 0, NULL, 0), "
            "(103, 'conflict_user', "
            "'$argon2id$legacy-conflict-long-hash-value', "
            "'Conflict User', NULL, 0, 0, NULL, 0)"
        )
    )
    await db.execute(text("INSERT INTO sys_user_roles (user_id, role_id) VALUES (102, 9001)"))
    await db.execute(
        text(
            "INSERT INTO cw_member_plan "
            "(id, uuid, is_deleted, created_time, updated_time, "
            "plan_code, plan_name, level_no, price, currency, "
            "duration_days, benefits, status, sort_no) VALUES "
            "(201, 'plan-201', 0, UTC_TIMESTAMP(), "
            "UTC_TIMESTAMP(), 'PLAN201', 'Plan 201', 1, 0, "
            "'CNY', 30, JSON_ARRAY(), 0, 0)"
        )
    )
    await db.execute(
        text(
            "INSERT INTO cw_member_subscription "
            "(id, uuid, is_deleted, created_time, updated_time, "
            "user_id, plan_id, source, source_ref, status, "
            "starts_at, expires_at, grant_reason, version_no) "
            "VALUES "
            "(301, 'subscription-301', 0, UTC_TIMESTAMP(), "
            "UTC_TIMESTAMP(), 101, 201, 'migration', "
            "'legacy-301', 0, UTC_TIMESTAMP(), "
            "DATE_ADD(UTC_TIMESTAMP(), INTERVAL 30 DAY), "
            "'CI eligible row', 1), "
            "(302, 'subscription-302', 0, UTC_TIMESTAMP(), "
            "UTC_TIMESTAMP(), 102, 201, 'migration', "
            "'legacy-302', 0, UTC_TIMESTAMP(), "
            "DATE_ADD(UTC_TIMESTAMP(), INTERVAL 30 DAY), "
            "'CI claim row', 1), "
            "(303, 'subscription-303', 0, UTC_TIMESTAMP(), "
            "UTC_TIMESTAMP(), 103, 201, 'migration', "
            "'legacy-303', 0, UTC_TIMESTAMP(), "
            "DATE_ADD(UTC_TIMESTAMP(), INTERVAL 30 DAY), "
            "'CI conflict row', 1)"
        )
    )
    await db.execute(
        text(
            "INSERT INTO auth_subject "
            "(id, uuid, is_deleted, created_time, updated_time, "
            "realm, status, version_no) VALUES "
            "(450, 'subject-450', 0, UTC_TIMESTAMP(), "
            "UTC_TIMESTAMP(), 'customer', 'active', 1)"
        )
    )
    await db.execute(
        text(
            "INSERT INTO cw_customer "
            "(id, uuid, is_deleted, created_time, updated_time, "
            "subject_id, realm, customer_no, nickname, "
            "register_source, status, version_no) VALUES "
            "(550, 'customer-550', 0, UTC_TIMESTAMP(), "
            "UTC_TIMESTAMP(), 450, 'customer', "
            "'CCONFLICT000000550', 'Existing Conflict', "
            "'migration', 'active', 1)"
        )
    )
    await db.execute(
        text(
            "INSERT INTO auth_identity "
            "(id, uuid, is_deleted, created_time, updated_time, "
            "subject_id, realm, provider, "
            "identifier_normalized, credential_hash, status, "
            "version_no) VALUES "
            "(451, 'identity-451', 0, UTC_TIMESTAMP(), "
            "UTC_TIMESTAMP(), 450, 'customer', 'password', "
            "'conflict_user', "
            "'$argon2id$existing-customer-long-hash-value', "
            "'active', 1)"
        )
    )


async def seed_ownership_conflict(db: AsyncSession) -> None:
    await db.execute(
        text(
            "INSERT INTO sys_user "
            "(id, username, password, name, avatar, "
            "is_superuser, status, dept_id, is_deleted) VALUES "
            "(104, 'ownership_conflict', "
            "'$argon2id$ownership-conflict-long-hash-value', "
            "'Ownership Conflict', NULL, 0, 0, NULL, 0)"
        )
    )
    await db.execute(
        text(
            "INSERT INTO cw_member_subscription "
            "(id, uuid, is_deleted, created_time, updated_time, "
            "user_id, customer_id, plan_id, source, source_ref, "
            "status, starts_at, expires_at, grant_reason, "
            "version_no) VALUES "
            "(304, 'subscription-304', 0, UTC_TIMESTAMP(), "
            "UTC_TIMESTAMP(), 104, 550, 201, 'migration', "
            "'legacy-304', 0, UTC_TIMESTAMP(), "
            "DATE_ADD(UTC_TIMESTAMP(), INTERVAL 30 DAY), "
            "'CI ownership conflict', 1)"
        )
    )
