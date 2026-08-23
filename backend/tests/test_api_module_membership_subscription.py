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


def _current_user_id(test_client: TestClient, auth_headers: dict[str, str]) -> int:
    response = test_client.get(
        "/system/user/current/info",
        headers=auth_headers,
        params={"check_data_scope": False},
    )
    assert response.status_code == 200, response.text
    return int(_data(response)["id"])


def _create_plan(
    test_client: TestClient,
    auth_headers: dict[str, str],
    *,
    suffix: str,
    rank: int = 10,
) -> dict:
    response = test_client.post(
        "/membership/plan/create",
        headers=auth_headers,
        json={
            "plan_code": f"subscription-{rank}-{suffix}",
            "plan_name": f"订阅套餐-{rank}-{suffix}",
            "rank": rank,
            "price": "99.00",
            "currency": "CNY",
            "duration_days": 30,
            "benefits": ["投研内容"],
            "status": 0,
            "sort_no": rank,
        },
    )
    assert response.status_code == 201, response.text
    return _data(response)


def test_subscription_admin_endpoints_require_authentication(test_client: TestClient) -> None:
    response = test_client.get(
        "/membership/subscription/list",
        params={"page_no": 1, "page_size": 10},
    )
    assert response.status_code == 401

    response = test_client.post(
        "/membership/subscription/grant/manual",
        json={
            "user_id": 1,
            "plan_id": 1,
            "source_ref": "manual-unauthorized",
            "grant_reason": "未授权测试",
        },
    )
    assert response.status_code == 401


def test_manual_subscription_is_idempotent_and_revocable(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    user_id = _current_user_id(test_client, auth_headers)
    plan = _create_plan(test_client, auth_headers, suffix=suffix)
    starts_at = datetime.now(UTC) - timedelta(minutes=5)
    expires_at = starts_at + timedelta(days=15)
    payload = {
        "user_id": user_id,
        "plan_id": plan["id"],
        "source_ref": f"manual-{suffix}",
        "starts_at": starts_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "grant_reason": "客服补偿授权",
        "description": "自动化测试",
    }

    first = test_client.post(
        "/membership/subscription/grant/manual",
        headers=auth_headers,
        json=payload,
    )
    assert first.status_code == 201, first.text
    subscription = _data(first)
    assert subscription["effective_status"] == "active"
    assert subscription["source"] == "manual"
    assert subscription["version_no"] == 1

    second = test_client.post(
        "/membership/subscription/grant/manual",
        headers=auth_headers,
        json=payload,
    )
    assert second.status_code == 201, second.text
    assert _data(second)["id"] == subscription["id"]

    other_plan = _create_plan(test_client, auth_headers, suffix=f"other-{suffix}", rank=20)
    mismatch = test_client.post(
        "/membership/subscription/grant/manual",
        headers=auth_headers,
        json={**payload, "plan_id": other_plan["id"]},
    )
    assert mismatch.status_code == 409

    reason_mismatch = test_client.post(
        "/membership/subscription/grant/manual",
        headers=auth_headers,
        json={**payload, "grant_reason": "另一次不同的人工授权"},
    )
    assert reason_mismatch.status_code == 409

    description_mismatch = test_client.post(
        "/membership/subscription/grant/manual",
        headers=auth_headers,
        json={**payload, "description": "不同内部备注"},
    )
    assert description_mismatch.status_code == 409

    detail = test_client.get(
        f"/membership/subscription/detail/{subscription['id']}",
        headers=auth_headers,
    )
    assert detail.status_code == 200, detail.text
    assert _data(detail)["username"]

    page = test_client.get(
        "/membership/subscription/list",
        headers=auth_headers,
        params={
            "page_no": 1,
            "page_size": 10,
            "keyword": payload["source_ref"],
            "effective_status": "active",
        },
    )
    assert page.status_code == 200, page.text
    page_data = _data(page)
    assert page_data["total"] == 1
    assert page_data["items"][0]["id"] == subscription["id"]

    stale_revoke = test_client.post(
        f"/membership/subscription/revoke/{subscription['id']}",
        headers=auth_headers,
        json={"version_no": 999, "reason": "过期版本"},
    )
    assert stale_revoke.status_code == 409

    revoked = test_client.post(
        f"/membership/subscription/revoke/{subscription['id']}",
        headers=auth_headers,
        json={"version_no": subscription["version_no"], "reason": "客服撤销"},
    )
    assert revoked.status_code == 200, revoked.text
    revoked_data = _data(revoked)
    assert revoked_data["status"] == 1
    assert revoked_data["effective_status"] == "revoked"
    assert revoked_data["version_no"] == 2

    repeat_revoke = test_client.post(
        f"/membership/subscription/revoke/{subscription['id']}",
        headers=auth_headers,
        json={"version_no": revoked_data["version_no"], "reason": "重复撤销"},
    )
    assert repeat_revoke.status_code == 409

    delete_plan = test_client.request(
        "DELETE",
        "/membership/plan/delete",
        headers=auth_headers,
        json=[plan["id"]],
    )
    assert delete_plan.status_code == 409


def test_subscription_time_boundaries(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()
    user_id = _current_user_id(test_client, auth_headers)
    plan = _create_plan(test_client, auth_headers, suffix=suffix)
    now = datetime.now(UTC)

    upcoming = test_client.post(
        "/membership/subscription/grant/manual",
        headers=auth_headers,
        json={
            "user_id": user_id,
            "plan_id": plan["id"],
            "source_ref": f"upcoming-{suffix}",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "expires_at": (now + timedelta(days=2)).isoformat(),
            "grant_reason": "未来生效",
        },
    )
    assert upcoming.status_code == 201, upcoming.text
    assert _data(upcoming)["effective_status"] == "upcoming"

    expired = test_client.post(
        "/membership/subscription/grant/manual",
        headers=auth_headers,
        json={
            "user_id": user_id,
            "plan_id": plan["id"],
            "source_ref": f"expired-{suffix}",
            "starts_at": (now - timedelta(days=2)).isoformat(),
            "expires_at": (now - timedelta(days=1)).isoformat(),
            "grant_reason": "历史迁移",
        },
    )
    assert expired.status_code == 201, expired.text
    assert _data(expired)["effective_status"] == "expired"

    invalid_window = test_client.post(
        "/membership/subscription/grant/manual",
        headers=auth_headers,
        json={
            "user_id": user_id,
            "plan_id": plan["id"],
            "source_ref": f"invalid-{suffix}",
            "starts_at": now.isoformat(),
            "expires_at": (now - timedelta(seconds=1)).isoformat(),
            "grant_reason": "非法时间窗口",
        },
    )
    assert invalid_window.status_code == 422
