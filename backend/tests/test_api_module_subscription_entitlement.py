from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient


def _data(response):
    payload = response.json()
    assert payload["success"] is True, payload
    return payload["data"]


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_plan(test_client: TestClient, headers: dict[str, str], suffix: str, rank: int = 10):
    response = test_client.post(
        "/membership/plan/create",
        headers=headers,
        json={
            "plan_code": f"entitlement-{suffix}",
            "plan_name": f"权益套餐-{suffix}",
            "rank": rank,
            "price": "199.00",
            "currency": "CNY",
            "duration_days": 365,
            "benefits": ["投研内容"],
            "status": 0,
            "sort_no": rank,
        },
    )
    assert response.status_code == 201, response.text
    return _data(response)


def _create_category(test_client: TestClient, headers: dict[str, str], suffix: str):
    response = test_client.post(
        "/content/category/create",
        headers=headers,
        json={
            "category_code": f"entitlement-{suffix}",
            "category_name": f"权益内容-{suffix}",
            "status": 0,
            "sort_no": 1,
        },
    )
    assert response.status_code == 201, response.text
    return _data(response)


def _create_and_publish(
    test_client: TestClient,
    headers: dict[str, str],
    *,
    category_id: int,
    suffix: str,
    access_level: str,
    plan_ids: list[int] | None = None,
):
    response = test_client.post(
        "/content/article/create",
        headers=headers,
        json={
            "category_id": category_id,
            "content_type": "research",
            "title": f"{access_level}-content-{suffix}",
            "slug": f"{access_level}-content-{suffix}",
            "summary": f"{access_level} summary",
            "body": f"<p>{access_level} protected body</p>",
            "body_format": "html",
            "author_name": "M2.3",
            "access_level": access_level,
            "plan_ids": plan_ids or [],
        },
    )
    assert response.status_code == 201, response.text
    content = _data(response)
    published = test_client.post(
        f"/content/article/publish/{content['id']}",
        headers=headers,
        json={"version_no": content["version_no"]},
    )
    assert published.status_code == 200, published.text
    return _data(published)


def _titles(response) -> set[str]:
    assert response.status_code == 200, response.text
    return {item["title"] for item in response.json()["items"]}


def test_subscription_admin_requires_authentication(test_client: TestClient) -> None:
    response = test_client.get("/membership/subscription/list", params={"page_no": 1, "page_size": 10})
    assert response.status_code == 401


def test_real_subscription_and_portal_entitlement_workflow(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    plan = _create_plan(test_client, auth_headers, suffix)
    category = _create_category(test_client, auth_headers, suffix)

    public = _create_and_publish(
        test_client,
        auth_headers,
        category_id=category["id"],
        suffix=f"public-{suffix}",
        access_level="public",
    )
    login = _create_and_publish(
        test_client,
        auth_headers,
        category_id=category["id"],
        suffix=f"login-{suffix}",
        access_level="login",
    )
    member = _create_and_publish(
        test_client,
        auth_headers,
        category_id=category["id"],
        suffix=f"member-{suffix}",
        access_level="member",
    )
    premium = _create_and_publish(
        test_client,
        auth_headers,
        category_id=category["id"],
        suffix=f"premium-{suffix}",
        access_level="premium",
        plan_ids=[plan["id"]],
    )

    anonymous = test_client.get("/portal/feed", params={"category_id": category["id"]})
    assert _titles(anonymous) == {public["title"]}

    logged_in = test_client.get(
        "/portal/feed",
        headers=auth_headers,
        params={"category_id": category["id"]},
    )
    assert _titles(logged_in) == {public["title"], login["title"]}

    unauthorized = test_client.get(f"/portal/article/{premium['id']}", headers=auth_headers)
    missing = test_client.get("/portal/article/2147483647", headers=auth_headers)
    assert unauthorized.status_code == missing.status_code == 404
    assert unauthorized.json() == missing.json()

    now = datetime.now(UTC)
    external_ref = f"manual:{suffix}:primary"
    grant_response = test_client.post(
        "/membership/subscription/grant",
        headers=auth_headers,
        json={
            "user_id": 2,
            "plan_id": plan["id"],
            "external_ref": external_ref,
            "source": "manual",
            "starts_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "description": "M2.3 entitlement test",
        },
    )
    assert grant_response.status_code == 201, grant_response.text
    subscription = _data(grant_response)
    assert subscription["effective"] is True
    assert subscription["version_no"] == 1

    retry_response = test_client.post(
        "/membership/subscription/grant",
        headers=auth_headers,
        json={
            "user_id": 2,
            "plan_id": plan["id"],
            "external_ref": external_ref,
            "source": "manual",
        },
    )
    assert retry_response.status_code == 201, retry_response.text
    assert _data(retry_response)["id"] == subscription["id"]

    entitled = test_client.get(
        "/portal/feed",
        headers=auth_headers,
        params={"category_id": category["id"]},
    )
    assert _titles(entitled) == {
        public["title"],
        login["title"],
        member["title"],
        premium["title"],
    }

    article = test_client.get(f"/portal/article/{premium['id']}", headers=auth_headers)
    assert article.status_code == 200, article.text
    assert "premium protected body" in article.json()["body"]

    membership = test_client.get("/portal/me/membership", headers=auth_headers)
    assert membership.status_code == 200, membership.text
    assert membership.json()["active"] is True
    assert membership.json()["subscriptions"][0]["subscription_id"] == subscription["id"]

    plan_delete = test_client.request(
        "DELETE",
        "/membership/plan/delete",
        headers=auth_headers,
        json=[plan["id"]],
    )
    assert plan_delete.status_code == 409

    revoke = test_client.post(
        f"/membership/subscription/revoke/{subscription['id']}",
        headers=auth_headers,
        json={"version_no": subscription["version_no"], "reason": "测试撤销"},
    )
    assert revoke.status_code == 200, revoke.text
    revoked = _data(revoke)
    assert revoked["status"] == "revoked"
    assert revoked["effective"] is False
    assert revoked["version_no"] == 2

    stale_revoke = test_client.post(
        f"/membership/subscription/revoke/{subscription['id']}",
        headers=auth_headers,
        json={"version_no": subscription["version_no"], "reason": "重复撤销"},
    )
    assert stale_revoke.status_code == 409

    after_revoke = test_client.get(
        "/portal/feed",
        headers=auth_headers,
        params={"category_id": category["id"]},
    )
    assert _titles(after_revoke) == {public["title"], login["title"]}
    assert test_client.get(f"/portal/article/{member['id']}", headers=auth_headers).status_code == 404
    assert test_client.get(f"/portal/article/{premium['id']}", headers=auth_headers).status_code == 404


def test_future_expired_and_plan_mismatch_are_not_effective(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    matching_plan = _create_plan(test_client, auth_headers, f"matching-{suffix}", rank=30)
    other_plan = _create_plan(test_client, auth_headers, f"other-{suffix}", rank=5)
    category = _create_category(test_client, auth_headers, f"boundary-{suffix}")
    premium = _create_and_publish(
        test_client,
        auth_headers,
        category_id=category["id"],
        suffix=f"boundary-{suffix}",
        access_level="premium",
        plan_ids=[matching_plan["id"]],
    )

    now = datetime.now(UTC)
    for label, plan_id, starts_at, expires_at in (
        ("expired", matching_plan["id"], now - timedelta(days=2), now - timedelta(seconds=1)),
        ("future", matching_plan["id"], now + timedelta(days=1), now + timedelta(days=2)),
        ("mismatch", other_plan["id"], now - timedelta(minutes=1), now + timedelta(days=2)),
    ):
        response = test_client.post(
            "/membership/subscription/grant",
            headers=auth_headers,
            json={
                "user_id": 2,
                "plan_id": plan_id,
                "external_ref": f"manual:{suffix}:{label}",
                "source": "manual",
                "starts_at": starts_at.isoformat(),
                "expires_at": expires_at.isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        assert _data(response)["effective"] is (label == "mismatch")

    feed = test_client.get(
        "/portal/feed",
        headers=auth_headers,
        params={"category_id": category["id"]},
    )
    assert premium["title"] not in _titles(feed)
    assert test_client.get(f"/portal/article/{premium['id']}", headers=auth_headers).status_code == 404
