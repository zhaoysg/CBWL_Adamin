from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1.module_identity.enums import (
    CustomerRegisterSource,
    IdentityProvider,
    IdentityRealm,
    IdentityStatus,
)
from app.api.v1.module_identity.legacy.enums import (
    LegacyCredentialState,
    LegacyMigrationSource,
)
from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_identity.model import AuthSubjectModel, CustomerModel
from app.api.v1.module_identity.schema import CustomerProvisionSchema
from app.api.v1.module_identity.service import IdentityService
from app.api.v1.module_system.user.model import UserModel
from app.config.portal_auth import portal_auth_settings
from app.core.database import async_db_session


@pytest.fixture(autouse=True)
def clear_shared_cookie_jar(test_client: TestClient):
    test_client.cookies.clear()
    yield
    test_client.cookies.clear()


def _create_legacy_portal_user(
    test_client: TestClient,
) -> tuple[str, str]:
    suffix = uuid4().hex[:10]
    username = f"dual_{suffix}"
    password = "Portal123!"
    response = test_client.post(
        "/system/user/register",
        json={
            "username": username,
            "password": password,
            "name": f"双读用户{suffix[:6]}",
        },
    )
    assert response.status_code == 200, response.text
    return username, password


async def _legacy_user(username: str) -> UserModel:
    async with async_db_session() as db:
        user = await db.scalar(select(UserModel).where(UserModel.username == username))
        assert user is not None
        return user


async def _map_migrated_customer(username: str) -> tuple[int, int, int]:
    async with async_db_session() as db, db.begin():
        user = await db.scalar(select(UserModel).where(UserModel.username == username))
        assert user is not None
        provisioned = await IdentityService.create_customer(
            db,
            CustomerProvisionSchema(
                provider=IdentityProvider.PASSWORD,
                identifier=user.username,
                nickname=user.name,
                avatar_url=user.avatar,
                register_source=CustomerRegisterSource.MIGRATION,
            ),
            credential_hash=user.password,
        )
        provisioned.identity.verified_at = datetime.now(UTC)
        mapping = LegacyCustomerMapModel(
            legacy_sys_user_id=user.id,
            customer_id=provisioned.customer.id,
            credential_state=LegacyCredentialState.MIGRATED.value,
            source=LegacyMigrationSource.MEMBERSHIP.value,
            identifier_snapshot=user.username.casefold(),
            migrated_at=datetime.now(UTC),
            version_no=1,
        )
        db.add(mapping)
        await db.flush()
        return (
            provisioned.customer.id,
            provisioned.subject.id,
            user.id,
        )


async def _map_claim_required_customer(username: str) -> tuple[int, int]:
    async with async_db_session() as db, db.begin():
        user = await db.scalar(select(UserModel).where(UserModel.username == username))
        assert user is not None
        subject = AuthSubjectModel(
            realm=IdentityRealm.CUSTOMER.value,
            status=IdentityStatus.ACTIVE.value,
            version_no=1,
        )
        db.add(subject)
        await db.flush()
        customer = CustomerModel(
            subject_id=subject.id,
            realm=IdentityRealm.CUSTOMER.value,
            customer_no=f"C{uuid4().hex[:20].upper()}",
            nickname=user.name,
            avatar_url=user.avatar,
            register_source=CustomerRegisterSource.MIGRATION.value,
            status=IdentityStatus.ACTIVE.value,
            version_no=1,
        )
        db.add(customer)
        await db.flush()
        db.add(
            LegacyCustomerMapModel(
                legacy_sys_user_id=user.id,
                customer_id=customer.id,
                credential_state=(LegacyCredentialState.CLAIM_REQUIRED.value),
                source=LegacyMigrationSource.MEMBERSHIP.value,
                reason_code="role",
                identifier_snapshot=user.username.casefold(),
                migrated_at=datetime.now(UTC),
                version_no=1,
            )
        )
        await db.flush()
        return customer.id, user.id


async def _disable_customer(customer_id: int) -> None:
    async with async_db_session() as db, db.begin():
        customer = await db.get(CustomerModel, customer_id)
        assert customer is not None
        customer.status = IdentityStatus.DISABLED.value


def _login(
    test_client: TestClient,
    username: str,
    password: str,
):
    return test_client.post(
        "/portal/auth/login",
        json={"username": username, "password": password},
    )


@pytest.mark.asyncio
async def test_dual_mode_prefers_migrated_customer_identity(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    username, password = _create_legacy_portal_user(test_client)
    customer_id, subject_id, legacy_user_id = await _map_migrated_customer(username)
    monkeypatch.setattr(portal_auth_settings, "IDENTITY_MODE", "dual")

    login = _login(test_client, username, password)
    assert login.status_code == 200, login.text
    user = login.json()["user_info"]
    assert user == {
        "id": customer_id,
        "username": username,
        "name": user["name"],
        "avatar": None,
        "identity_source": "customer",
        "customer_id": customer_id,
        "subject_id": subject_id,
        "legacy_user_id": legacy_user_id,
    }

    access_token = login.json()["access_token"]
    assert (
        test_client.get(
            "/portal/home",
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code
        == 200
    )
    admin_response = test_client.get(
        "/system/user/current/info",
        params={"check_data_scope": "false"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert admin_response.status_code == 401

    refresh = test_client.post("/portal/auth/refresh")
    assert refresh.status_code == 200, refresh.text
    refreshed_user = refresh.json()["user_info"]
    assert refreshed_user["identity_source"] == "customer"
    assert refreshed_user["customer_id"] == customer_id
    assert refreshed_user["legacy_user_id"] == legacy_user_id


@pytest.mark.asyncio
async def test_dual_mode_falls_back_only_for_unmapped_legacy_user(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    username, password = _create_legacy_portal_user(test_client)
    legacy = await _legacy_user(username)
    monkeypatch.setattr(portal_auth_settings, "IDENTITY_MODE", "dual")

    login = _login(test_client, username, password)
    assert login.status_code == 200, login.text
    user = login.json()["user_info"]
    assert user["identity_source"] == "legacy"
    assert user["customer_id"] is None
    assert user["legacy_user_id"] == legacy.id


@pytest.mark.asyncio
async def test_claim_required_mapping_cannot_bypass_with_legacy_password(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    username, password = _create_legacy_portal_user(test_client)
    await _map_claim_required_customer(username)
    monkeypatch.setattr(portal_auth_settings, "IDENTITY_MODE", "dual")

    response = _login(test_client, username, password)
    assert response.status_code == 409
    assert "身份认领" in response.json()["msg"]
    assert not test_client.cookies.get(portal_auth_settings.REFRESH_COOKIE_NAME)

    wrong = _login(test_client, username, "Wrong123!")
    assert wrong.status_code == 401
    assert wrong.json()["msg"] == "账号或密码错误"


@pytest.mark.asyncio
async def test_customer_mode_rejects_unmapped_legacy_login(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    username, password = _create_legacy_portal_user(test_client)
    monkeypatch.setattr(portal_auth_settings, "IDENTITY_MODE", "customer")

    response = _login(test_client, username, password)
    assert response.status_code == 401
    assert response.json()["msg"] == "账号或密码错误"


@pytest.mark.asyncio
async def test_disabled_customer_invalidates_access_and_refresh(
    test_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    username, password = _create_legacy_portal_user(test_client)
    customer_id, _, _ = await _map_migrated_customer(username)
    monkeypatch.setattr(portal_auth_settings, "IDENTITY_MODE", "dual")

    login = _login(test_client, username, password)
    assert login.status_code == 200, login.text
    access_token = login.json()["access_token"]
    await _disable_customer(customer_id)

    access = test_client.get(
        "/portal/home",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert access.status_code == 401
    assert "客户会话已失效" in access.json()["msg"]

    refresh = test_client.post("/portal/auth/refresh")
    assert refresh.status_code == 401
    assert "客户会话已失效" in refresh.json()["msg"]

    logout = test_client.post("/portal/auth/logout")
    assert logout.status_code == 204
