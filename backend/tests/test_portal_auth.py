from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.common.enums import EnvironmentEnum
from app.config.portal_auth import portal_auth_settings
from app.config.production_guard import UnsafeProductionConfiguration, validate_production_settings
from app.config.setting import settings


def _create_portal_user(test_client: TestClient) -> tuple[str, str]:
    suffix = uuid4().hex[:10]
    username = f"h5_{suffix}"
    password = "Portal123!"
    response = test_client.post(
        "/system/user/register",
        json={
            "username": username,
            "password": password,
            "name": f"H5用户{suffix[:6]}",
        },
    )
    assert response.status_code == 200, response.text
    return username, password


def _portal_login(test_client: TestClient, username: str, password: str):
    return test_client.post(
        "/portal/auth/login",
        json={"username": username, "password": password},
    )


def test_portal_auth_login_refresh_logout_flow(test_client: TestClient) -> None:
    username, password = _create_portal_user(test_client)
    login = _portal_login(test_client, username, password)
    assert login.status_code == 200, login.text
    login_data = login.json()
    assert login_data["user_info"]["username"] == username
    assert login_data["access_token"]
    assert "refresh_token" not in login_data

    cookie_name = portal_auth_settings.REFRESH_COOKIE_NAME
    old_refresh = test_client.cookies.get(cookie_name)
    assert old_refresh
    assert "httponly" in login.headers["set-cookie"].lower()

    first_access = login_data["access_token"]
    assert test_client.get(
        "/portal/home",
        headers={"Authorization": f"Bearer {first_access}"},
    ).status_code == 200

    refresh = test_client.post("/portal/auth/refresh")
    assert refresh.status_code == 200, refresh.text
    refresh_data = refresh.json()
    assert refresh_data["access_token"] != first_access
    assert "refresh_token" not in refresh_data
    next_refresh = test_client.cookies.get(cookie_name)
    assert next_refresh and next_refresh != old_refresh

    assert test_client.get(
        "/portal/home",
        headers={"Authorization": f"Bearer {first_access}"},
    ).status_code == 401
    assert test_client.get(
        "/portal/home",
        headers={"Authorization": f"Bearer {refresh_data['access_token']}"},
    ).status_code == 200

    test_client.cookies.set(cookie_name, old_refresh, path=portal_auth_settings.REFRESH_COOKIE_PATH)
    reused = test_client.post("/portal/auth/refresh")
    assert reused.status_code == 401

    test_client.cookies.set(cookie_name, next_refresh, path=portal_auth_settings.REFRESH_COOKIE_PATH)
    logout = test_client.post("/portal/auth/logout")
    assert logout.status_code == 204, logout.text
    assert not test_client.cookies.get(cookie_name)

    assert test_client.get(
        "/portal/home",
        headers={"Authorization": f"Bearer {refresh_data['access_token']}"},
    ).status_code == 401


def test_portal_auth_returns_generic_invalid_credentials(test_client: TestClient) -> None:
    response = _portal_login(test_client, f"missing_{uuid4().hex[:8]}", "Portal123!")
    assert response.status_code == 401
    assert response.json()["msg"] == "账号或密码错误"


def test_portal_auth_rejects_superuser_login(test_client: TestClient) -> None:
    response = _portal_login(test_client, "admin", "admin123")
    assert response.status_code == 403
    assert "管理员账号" in response.json()["msg"]
    assert not test_client.cookies.get(portal_auth_settings.REFRESH_COOKIE_NAME)


def test_portal_rejects_administration_session(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = test_client.get("/portal/home", headers=auth_headers)
    assert response.status_code == 401
    assert "客户端会话类型" in response.json()["msg"]


def test_portal_captcha_disabled_contract(test_client: TestClient) -> None:
    response = test_client.get("/portal/auth/captcha")
    assert response.status_code == 200, response.text
    assert response.json() == {"enable": False, "key": "disabled", "question": None}


def test_portal_login_rejects_legacy_h5_captcha_field(test_client: TestClient) -> None:
    response = test_client.post(
        "/portal/auth/login",
        json={
            "username": "legacy_h5_client",
            "password": "Portal123!",
            "captcha_key": "legacy-key",
            "captcha": "7",
        },
    )
    assert response.status_code == 422


def _set_safe_production_settings(monkeypatch: pytest.MonkeyPatch, *, database_type: str) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", EnvironmentEnum.PROD)
    monkeypatch.setattr(settings, "SECRET_KEY", "x" * 48)
    monkeypatch.setattr(settings, "PROD_CORS_ORIGINS", "https://admin.example.com,https://m.example.com")
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["api.example.com"])
    monkeypatch.setattr(settings, "ALLOW_CREDENTIALS", True)
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_SECONDS", 900)
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_SECONDS", 604800)
    monkeypatch.setattr(settings, "DATABASE_TYPE", database_type)
    monkeypatch.setattr(settings, "DATABASE_HOST", "mysql.internal")
    monkeypatch.setattr(settings, "DATABASE_USER", "caibuwailu")
    monkeypatch.setattr(settings, "DATABASE_PASSWORD", "test-only-password")
    monkeypatch.setattr(settings, "DATABASE_NAME", "caibuwailu")

    monkeypatch.setattr(portal_auth_settings, "ALLOWED_ORIGINS", "https://m.example.com")
    monkeypatch.setattr(portal_auth_settings, "REFRESH_COOKIE_PATH", "/api/v1/portal/auth")
    monkeypatch.setattr(portal_auth_settings, "REFRESH_COOKIE_SECURE", True)
    monkeypatch.setattr(portal_auth_settings, "RATE_LIMIT_ENABLE", True)
    monkeypatch.setattr(portal_auth_settings, "ALLOW_SUPERUSER_LOGIN", False)
    monkeypatch.setattr(portal_auth_settings, "ALLOWED_LOGIN_TYPES", "H5")


def test_production_guard_rejects_non_mysql_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_safe_production_settings(monkeypatch, database_type="sqlite")
    with pytest.raises(UnsafeProductionConfiguration, match="DATABASE_TYPE=mysql"):
        validate_production_settings()


def test_production_guard_accepts_remote_mysql_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_safe_production_settings(monkeypatch, database_type="mysql")
    validate_production_settings()
