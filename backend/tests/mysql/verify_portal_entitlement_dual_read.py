from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.api.v1.module_portal.database_service import DatabasePortalService
from app.api.v1.module_portal.entitlement import (
    load_portal_entitlement_context,
)
from app.api.v1.module_portal.principal import PortalPrincipal
from app.config.portal_auth import portal_auth_settings
from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.database import async_db_session
from app.core.exceptions import CustomException


def _customer_principal() -> PortalPrincipal:
    return PortalPrincipal(
        actor_type="customer",
        auth=AuthSchema(
            user=CoreUserSchema(
                id=101,
                username="legacy_101",
                name="Legacy 101",
                is_superuser=False,
            ),
            permissions=[],
            menu_ids=[],
        ),
        legacy_user_id=101,
        customer_id=501,
        subject_id=401,
    )


def _legacy_principal() -> PortalPrincipal:
    return PortalPrincipal(
        actor_type="legacy",
        auth=AuthSchema(
            user=CoreUserSchema(
                id=101,
                username="legacy_101",
                name="Legacy 101",
                is_superuser=False,
            ),
            permissions=[],
            menu_ids=[],
        ),
        legacy_user_id=101,
    )


async def _seed() -> None:
    async with async_db_session() as db, db.begin():
        await db.execute(text("INSERT INTO sys_user (id) VALUES (101)"))
        await db.execute(
            text(
                "INSERT INTO cw_member_plan "
                "(id, uuid, is_deleted, created_time, updated_time, "
                "plan_code, plan_name, level_no, price, currency, "
                "duration_days, benefits, status, sort_no) VALUES "
                "(201, 'plan-201', 0, UTC_TIMESTAMP(), UTC_TIMESTAMP(), "
                "'plan-201', 'Plan 201', 1, 0, 'CNY', 30, "
                "JSON_ARRAY('完整内容'), 0, 0)"
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
                "'CLEGACY000000101', 'Customer 501', "
                "'migration', 'active', 1)"
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
                "'legacy_101', UTC_TIMESTAMP(), 1)"
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
                "'entitlement-301', 0, UTC_TIMESTAMP(), "
                "DATE_ADD(UTC_TIMESTAMP(), INTERVAL 30 DAY), "
                "'dual read CI', 1)"
            )
        )


async def _load(principal: PortalPrincipal):
    async with async_db_session() as db:
        return await load_portal_entitlement_context(db, principal)


async def main() -> None:
    await _seed()
    customer = _customer_principal()

    portal_auth_settings.ENTITLEMENT_MODE = "legacy"
    legacy_context = await _load(customer)
    assert [item.id for item in legacy_context.subscriptions] == [301]
    assert legacy_context.customer_id is None

    portal_auth_settings.ENTITLEMENT_MODE = "dual"
    dual_context = await _load(customer)
    assert [item.id for item in dual_context.subscriptions] == [301]
    assert dual_context.customer_id == 501

    async with async_db_session() as db:
        member_center = await DatabasePortalService(
            db,
            customer,
        ).member_center()
        assert member_center.member is not None
        assert member_center.member.id == 501
        assert member_center.member.member_no == "CLEGACY000000101"
        assert member_center.member.nickname == "Customer 501"
        assert member_center.member.is_member is True

    async with async_db_session() as db, db.begin():
        await db.execute(text("UPDATE cw_member_subscription SET customer_id = NULL WHERE id = 301"))
    try:
        await _load(customer)
    except CustomException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("dual-read mismatch did not fail closed")

    async with async_db_session() as db, db.begin():
        await db.execute(text("UPDATE cw_member_subscription SET customer_id = 501 WHERE id = 301"))
    portal_auth_settings.ENTITLEMENT_MODE = "customer"
    customer_context = await _load(customer)
    assert [item.id for item in customer_context.subscriptions] == [301]
    assert customer_context.customer_id == 501

    try:
        await _load(_legacy_principal())
    except CustomException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("customer-only entitlement mode accepted legacy principal")

    print("portal entitlement dual-read MySQL verification passed")


if __name__ == "__main__":
    asyncio.run(main())
