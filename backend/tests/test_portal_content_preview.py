from __future__ import annotations

import os
from uuid import uuid4

from fastapi.testclient import TestClient


def _data(response):
    payload = response.json()
    assert payload["success"] is True, payload
    return payload["data"]


def _create_login_content(test_client: TestClient, auth_headers: dict[str, str]) -> dict:
    suffix = uuid4().hex[:10]
    category_response = test_client.post(
        "/content/category/create",
        headers=auth_headers,
        json={
            "category_code": f"preview-{suffix}",
            "category_name": f"预览分类-{suffix}",
            "status": 0,
            "sort_no": 1,
        },
    )
    assert category_response.status_code == 201, category_response.text
    category = _data(category_response)

    create_response = test_client.post(
        "/content/article/create",
        headers=auth_headers,
        json={
            "category_id": category["id"],
            "content_type": "research",
            "title": f"登录预览内容-{suffix}",
            "slug": f"login-preview-{suffix}",
            "summary": "这是允许游客看到的公开摘要",
            "body": "<h2>受保护正文</h2><p>该文本不得出现在游客响应中</p>",
            "body_format": "html",
            "author_name": "预览测试员",
            "access_level": "login",
            "plan_ids": [],
            "is_pinned": False,
            "sort_no": 1,
        },
    )
    assert create_response.status_code == 201, create_response.text
    content = _data(create_response)

    publish_response = test_client.post(
        f"/content/article/publish/{content['id']}",
        headers=auth_headers,
        json={"version_no": content["version_no"]},
    )
    assert publish_response.status_code == 200, publish_response.text
    return _data(publish_response)


def _create_mobile_user(test_client: TestClient) -> dict[str, str]:
    suffix = uuid4().hex[:10]
    username = f"preview_{suffix}"[:32]
    password = "Portal123!"
    register = test_client.post(
        "/system/user/register",
        json={"username": username, "password": password, "name": f"预览用户{suffix[:6]}"},
    )
    assert register.status_code == 200, register.text

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
    return {"Authorization": f"Bearer {_data(login)['access_token']}"}


def test_h5_content_preview_never_exposes_locked_body(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    previous_source = os.environ.get("PORTAL_DATA_SOURCE")
    os.environ["PORTAL_DATA_SOURCE"] = "database"
    try:
        content = _create_login_content(test_client, auth_headers)

        strict = test_client.get(f"/portal/content/{content['id']}")
        assert strict.status_code == 401

        preview = test_client.get(f"/portal/content/{content['id']}/preview")
        assert preview.status_code == 200, preview.text
        payload = preview.json()
        assert payload["title"] == content["title"]
        assert payload["summary"] == "这是允许游客看到的公开摘要"
        assert payload["can_access"] is False
        assert payload["lock_reason"] == "login_required"
        assert payload["unlock_action"] == "login"
        assert payload["unlock_message"]
        assert payload["body_html"] is None
        assert payload["sections"] == []
        assert "受保护正文" not in preview.text
        assert "该文本不得出现在游客响应中" not in preview.text

        mobile_headers = _create_mobile_user(test_client)
        unlocked = test_client.get(
            f"/portal/content/{content['id']}/preview",
            headers=mobile_headers,
        )
        assert unlocked.status_code == 200, unlocked.text
        unlocked_payload = unlocked.json()
        assert unlocked_payload["can_access"] is True
        assert unlocked_payload["lock_reason"] is None
        assert unlocked_payload["unlock_action"] is None
        assert "受保护正文" in unlocked_payload["body_html"]

        assert test_client.get("/portal/profile").status_code == 401
    finally:
        if previous_source is None:
            os.environ.pop("PORTAL_DATA_SOURCE", None)
        else:
            os.environ["PORTAL_DATA_SOURCE"] = previous_source
