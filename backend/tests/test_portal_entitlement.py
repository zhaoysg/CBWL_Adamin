from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient


def _data(response):
    payload = response.json()
    assert payload["success"] is True, payload
    return payload["data"]


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_portal_user(test_client: TestClient, suffix: str) -> tuple[int, dict[str, str]]:
    username = f"portal_{suffix}"[:32]
    password = "Portal123!"
    register = test_client.post(
        "/system/user/register",
        json={
            "username": username,
            "password": password,
            "name": f"权益用户{suffix[:6]}",
        },
    )
    assert register.status_code == 200, register.text
    user_id = int(_data(register)["id"])

    login = test_client.post(
        "/system/auth/login",
        data={
            "username": username,
            "password": password,
            "captcha_key": "",
            "captcha": "",
            "login_type": "移动端",
        },
    )
    assert login.status_code == 200, login.text
    token = _data(login)["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _create_plan(test_client: TestClient, headers: dict[str, str], suffix: str, rank: int) -> dict:
    response = test_client.post(
        "/membership/plan/create",
        headers=headers,
        json={
            "plan_code": f"portal-{rank}-{suffix}",
            "plan_name": f"Portal套餐-{rank}-{suffix}",
            "rank": rank,
            "price": "199.00",
            "currency": "CNY",
            "duration_days": 30,
            "benefits": [f"等级{rank}内容"],
            "status": 0,
            "sort_no": rank,
        },
    )
    assert response.status_code == 201, response.text
    return _data(response)


def _create_category(test_client: TestClient, headers: dict[str, str], suffix: str) -> dict:
    response = test_client.post(
        "/content/category/create",
        headers=headers,
        json={
            "category_code": f"portal-{suffix}",
            "category_name": f"Portal分类-{suffix}",
            "status": 0,
            "sort_no": 1,
        },
    )
    assert response.status_code == 201, response.text
    return _data(response)


def _create_published_content(
    test_client: TestClient,
    headers: dict[str, str],
    *,
    category_id: int,
    suffix: str,
    access_level: str,
    plan_ids: list[int] | None = None,
) -> dict:
    create = test_client.post(
        "/content/article/create",
        headers=headers,
        json={
            "category_id": category_id,
            "content_type": "research",
            "title": f"{access_level}-内容-{suffix}",
            "slug": f"{access_level}-{suffix}",
            "summary": f"{access_level} 权限自动化验证",
            "body": f"<h2>{access_level}</h2><p>数据库真实正文</p>",
            "body_format": "html",
            "author_name": "测试研究员",
            "access_level": access_level,
            "plan_ids": plan_ids or [],
            "is_pinned": access_level == "public",
            "sort_no": 1,
        },
    )
    assert create.status_code == 201, create.text
    content = _data(create)
    publish = test_client.post(
        f"/content/article/publish/{content['id']}",
        headers=headers,
        json={"version_no": content["version_no"]},
    )
    assert publish.status_code == 200, publish.text
    return _data(publish)


def test_database_portal_rejects_invalid_credentials(test_client: TestClient) -> None:
    previous_source = os.environ.get("PORTAL_DATA_SOURCE")
    os.environ["PORTAL_DATA_SOURCE"] = "database"
    try:
        invalid_bearer = test_client.get(
            "/portal/home",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert invalid_bearer.status_code == 401

        invalid_scheme = test_client.get(
            "/portal/home",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert invalid_scheme.status_code == 401
    finally:
        if previous_source is None:
            os.environ.pop("PORTAL_DATA_SOURCE", None)
        else:
            os.environ["PORTAL_DATA_SOURCE"] = previous_source


def test_database_portal_entitlement_matrix(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    previous_source = os.environ.get("PORTAL_DATA_SOURCE")
    os.environ["PORTAL_DATA_SOURCE"] = "database"
    try:
        suffix = _suffix()
        user_id, member_headers = _create_portal_user(test_client, suffix)
        basic_plan = _create_plan(test_client, auth_headers, suffix, 10)
        premium_plan = _create_plan(test_client, auth_headers, f"premium-{suffix}", 20)
        category = _create_category(test_client, auth_headers, suffix)

        public_content = _create_published_content(
            test_client,
            auth_headers,
            category_id=category["id"],
            suffix=f"public-{suffix}",
            access_level="public",
        )
        login_content = _create_published_content(
            test_client,
            auth_headers,
            category_id=category["id"],
            suffix=f"login-{suffix}",
            access_level="login",
        )
        member_content = _create_published_content(
            test_client,
            auth_headers,
            category_id=category["id"],
            suffix=f"member-{suffix}",
            access_level="member",
        )
        premium_content = _create_published_content(
            test_client,
            auth_headers,
            category_id=category["id"],
            suffix=f"premium-content-{suffix}",
            access_level="premium",
            plan_ids=[premium_plan["id"]],
        )

        health = test_client.get("/portal/health")
        assert health.status_code == 200, health.text
        assert health.json()["production_ready"] is True
        assert health.json()["data_source"] == "database"

        anonymous_home = test_client.get("/portal/home")
        assert anonymous_home.status_code == 200, anonymous_home.text
        home_data = anonymous_home.json()
        assert home_data["member"] is None
        by_id = {item["id"]: item for item in home_data["feed"]}
        assert by_id[public_content["id"]]["can_access"] is True
        assert by_id[login_content["id"]]["lock_reason"] == "login_required"
        assert by_id[member_content["id"]]["lock_reason"] == "login_required"
        assert by_id[premium_content["id"]]["lock_reason"] == "login_required"

        assert test_client.get(f"/portal/content/{public_content['id']}").status_code == 200
        assert test_client.get(f"/portal/content/{login_content['id']}").status_code == 401
        assert test_client.get(f"/portal/content/{member_content['id']}").status_code == 401

        logged_in_home = test_client.get("/portal/home", headers=member_headers)
        assert logged_in_home.status_code == 200, logged_in_home.text
        logged_by_id = {item["id"]: item for item in logged_in_home.json()["feed"]}
        assert logged_by_id[login_content["id"]]["can_access"] is True
        assert logged_by_id[member_content["id"]]["lock_reason"] == "membership_required"
        assert logged_by_id[premium_content["id"]]["lock_reason"] == "plan_required"
        assert test_client.get(f"/portal/content/{login_content['id']}", headers=member_headers).status_code == 200
        assert test_client.get(f"/portal/content/{member_content['id']}", headers=member_headers).status_code == 403

        basic_grant = test_client.post(
            "/membership/subscription/grant/manual",
            headers=auth_headers,
            json={
                "user_id": user_id,
                "plan_id": basic_plan["id"],
                "source_ref": f"portal-basic-{suffix}",
                "grant_reason": "Portal 基础会员权限测试",
            },
        )
        assert basic_grant.status_code == 201, basic_grant.text
        basic_subscription = _data(basic_grant)

        member_after_grant = test_client.get(
            f"/portal/content/{member_content['id']}",
            headers=member_headers,
        )
        assert member_after_grant.status_code == 200, member_after_grant.text
        assert "数据库真实正文" in member_after_grant.json()["body_html"]
        assert (
            test_client.get(
                f"/portal/content/{premium_content['id']}",
                headers=member_headers,
            ).status_code
            == 403
        )

        premium_grant = test_client.post(
            "/membership/subscription/grant/manual",
            headers=auth_headers,
            json={
                "user_id": user_id,
                "plan_id": premium_plan["id"],
                "source_ref": f"portal-premium-{suffix}",
                "grant_reason": "Portal 指定套餐权限测试",
            },
        )
        assert premium_grant.status_code == 201, premium_grant.text
        premium_subscription = _data(premium_grant)

        premium_detail = test_client.get(
            f"/portal/content/{premium_content['id']}",
            headers=member_headers,
        )
        assert premium_detail.status_code == 200, premium_detail.text

        profile = test_client.get("/portal/profile", headers=member_headers)
        assert profile.status_code == 200, profile.text
        profile_data = profile.json()
        assert profile_data["member"]["is_member"] is True
        assert premium_plan["plan_code"] in profile_data["member"]["active_plan_codes"]
        assert profile_data["recent_learning"] is None

        member_center = test_client.get("/portal/member-center", headers=member_headers)
        assert member_center.status_code == 200, member_center.text
        plan_ids = {item["id"] for item in member_center.json()["plans"]}
        assert {basic_plan["id"], premium_plan["id"]} <= plan_ids

        revoke_premium = test_client.post(
            f"/membership/subscription/revoke/{premium_subscription['id']}",
            headers=auth_headers,
            json={"version_no": premium_subscription["version_no"], "reason": "撤销高级权益"},
        )
        assert revoke_premium.status_code == 200, revoke_premium.text
        assert (
            test_client.get(
                f"/portal/content/{premium_content['id']}",
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            test_client.get(
                f"/portal/content/{member_content['id']}",
                headers=member_headers,
            ).status_code
            == 200
        )

        revoke_basic = test_client.post(
            f"/membership/subscription/revoke/{basic_subscription['id']}",
            headers=auth_headers,
            json={"version_no": basic_subscription["version_no"], "reason": "撤销基础权益"},
        )
        assert revoke_basic.status_code == 200, revoke_basic.text
        assert (
            test_client.get(
                f"/portal/content/{member_content['id']}",
                headers=member_headers,
            ).status_code
            == 403
        )
    finally:
        if previous_source is None:
            os.environ.pop("PORTAL_DATA_SOURCE", None)
        else:
            os.environ["PORTAL_DATA_SOURCE"] = previous_source


def test_future_and_expired_subscriptions_do_not_unlock_member_content(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    previous_source = os.environ.get("PORTAL_DATA_SOURCE")
    os.environ["PORTAL_DATA_SOURCE"] = "database"
    try:
        suffix = _suffix()
        user_id, member_headers = _create_portal_user(test_client, suffix)
        plan = _create_plan(test_client, auth_headers, suffix, 30)
        category = _create_category(test_client, auth_headers, suffix)
        member_content = _create_published_content(
            test_client,
            auth_headers,
            category_id=category["id"],
            suffix=f"time-{suffix}",
            access_level="member",
        )
        now = datetime.now(UTC)

        for label, starts_at, expires_at in (
            ("future", now + timedelta(days=1), now + timedelta(days=2)),
            ("expired", now - timedelta(days=2), now - timedelta(days=1)),
        ):
            response = test_client.post(
                "/membership/subscription/grant/manual",
                headers=auth_headers,
                json={
                    "user_id": user_id,
                    "plan_id": plan["id"],
                    "source_ref": f"{label}-{suffix}",
                    "starts_at": starts_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "grant_reason": f"{label} 时间边界测试",
                },
            )
            assert response.status_code == 201, response.text

        detail = test_client.get(
            f"/portal/content/{member_content['id']}",
            headers=member_headers,
        )
        assert detail.status_code == 403
    finally:
        if previous_source is None:
            os.environ.pop("PORTAL_DATA_SOURCE", None)
        else:
            os.environ["PORTAL_DATA_SOURCE"] = previous_source
