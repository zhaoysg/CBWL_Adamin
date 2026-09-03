from __future__ import annotations

import asyncio
import json

from fakeredis.aioredis import FakeRedis
from sqlalchemy import text
from starlette.requests import Request

from app.api.v1.module_identity.legacy.migrator import (
    LegacyCustomerMigrationExecutor,
)
from app.api.v1.module_portal.customer_auth import (
    PortalCustomerAuthService,
)
from app.common.enums import RedisInitKeyConfig
from app.core.database import async_db_session
from app.core.redis_crud import RedisCURD
from app.core.security import decode_access_token
from app.utils.password_util import PwdUtil


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/portal/auth/login",
            "raw_path": b"/portal/auth/login",
            "query_string": b"",
            "headers": [(b"user-agent", b"CBWL-Mysql-CI")],
            "client": ("127.0.0.1", 12345),
            "server": ("api.example.test", 443),
        }
    )


async def _seed() -> tuple[str, str]:
    eligible_password = "Portal123!"
    claim_password = "Claim123!"
    eligible_hash = PwdUtil.hash_password(eligible_password)
    claim_hash = PwdUtil.hash_password(claim_password)
    legacy_hash = PwdUtil.hash_password("Legacy123!")

    async with async_db_session() as db, db.begin():
        await db.execute(
            text(
                "INSERT INTO sys_user "
                "(id, username, password, name, avatar, is_superuser, "
                "status, dept_id, is_deleted) VALUES "
                "(201, 'customer_dual', :eligible_hash, 'Customer Dual', "
                "NULL, 0, 0, NULL, 0), "
                "(202, 'customer_claim', :claim_hash, 'Customer Claim', "
                "NULL, 0, 0, NULL, 0), "
                "(203, 'legacy_only', :legacy_hash, 'Legacy Only', "
                "NULL, 0, 0, NULL, 0)"
            ),
            {
                "eligible_hash": eligible_hash,
                "claim_hash": claim_hash,
                "legacy_hash": legacy_hash,
            },
        )
        await db.execute(text("INSERT INTO sys_user_roles (user_id, role_id) VALUES (202, 9202)"))
        await db.execute(
            text(
                "INSERT INTO cw_member_plan "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "plan_code, plan_name, level_no, price, currency, "
                "duration_days, benefits, status, sort_no) VALUES "
                "(2201, 'plan-2201', 0, UTC_TIMESTAMP(), UTC_TIMESTAMP(), "
                "'PLAN2201', 'Plan 2201', 1, 0, 'CNY', 30, "
                "JSON_ARRAY(), 0, 0)"
            )
        )
        await db.execute(
            text(
                "INSERT INTO cw_member_subscription "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "user_id, plan_id, source, source_ref, status, starts_at, "
                "expires_at, grant_reason, version_no) VALUES "
                "(2301, 'subscription-2301', 0, UTC_TIMESTAMP(), "
                "UTC_TIMESTAMP(), 201, 2201, 'migration', 'dual-2301', 0, "
                "UTC_TIMESTAMP(), DATE_ADD(UTC_TIMESTAMP(), INTERVAL 30 DAY), "
                "'dual customer auth CI', 1), "
                "(2302, 'subscription-2302', 0, UTC_TIMESTAMP(), "
                "UTC_TIMESTAMP(), 202, 2201, 'migration', 'dual-2302', 0, "
                "UTC_TIMESTAMP(), DATE_ADD(UTC_TIMESTAMP(), INTERVAL 30 DAY), "
                "'claim customer auth CI', 1)"
            )
        )

    async with async_db_session() as db, db.begin():
        await LegacyCustomerMigrationExecutor.migrate_one(db, 201)
    async with async_db_session() as db, db.begin():
        await LegacyCustomerMigrationExecutor.migrate_one(db, 202)
    return eligible_password, claim_password


async def main() -> None:
    eligible_password, claim_password = await _seed()

    async with async_db_session() as db, db.begin():
        customer = await PortalCustomerAuthService.resolve_login(
            db,
            username="CUSTOMER_DUAL",
            password=eligible_password,
        )
        assert customer.outcome == "customer"
        assert customer.account is not None
        account = customer.account

        wrong = await PortalCustomerAuthService.resolve_login(
            db,
            username="customer_dual",
            password="Wrong123!",
        )
        assert wrong.outcome == "blocked"

        claim = await PortalCustomerAuthService.resolve_login(
            db,
            username="customer_claim",
            password=claim_password,
        )
        assert claim.outcome == "claim_required"

        legacy = await PortalCustomerAuthService.resolve_login(
            db,
            username="legacy_only",
            password="Legacy123!",
        )
        assert legacy.outcome == "legacy_fallback"

    redis = FakeRedis()
    token = await PortalCustomerAuthService.create_token(
        request=_request(),
        redis=redis,
        account=account,
    )
    payload = decode_access_token(token=token.access_token, verify_exp=True)
    raw = await RedisCURD(redis).get(f"{RedisInitKeyConfig.USER_SESSION.key}:{payload.sub}")
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    session = json.loads(raw)
    assert session["actor_type"] == "customer"
    assert session["customer_id"] == account.customer_id
    assert session["legacy_user_id"] == account.legacy_user_id
    assert "password" not in session
    assert "credential_hash" not in session

    async with async_db_session() as db:
        await PortalCustomerAuthService.validate_session(db, session)
        customer_id = await db.scalar(text("SELECT customer_id FROM cw_member_subscription WHERE id = 2301"))
        assert customer_id == account.customer_id
    await redis.aclose()
    print("portal customer dual authentication MySQL verification passed")


if __name__ == "__main__":
    asyncio.run(main())
