from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def _json_data(response):
    payload = response.json()
    assert payload["success"] is True, payload
    return payload["data"]


def _suffix() -> str:
    return uuid4().hex[:10]


def test_content_admin_requires_authentication(test_client: TestClient) -> None:
    response = test_client.get("/content/article/list", params={"page_no": 1, "page_size": 10})
    assert response.status_code == 401

    response = test_client.get("/membership/plan/list", params={"page_no": 1, "page_size": 10})
    assert response.status_code == 401


def test_membership_category_and_content_workflow(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()

    plan_response = test_client.post(
        "/membership/plan/create",
        headers=auth_headers,
        json={
            "plan_code": f"premium-{suffix}",
            "plan_name": f"尊享会员-{suffix}",
            "rank": 20,
            "price": "999.00",
            "currency": "CNY",
            "duration_days": 365,
            "benefits": ["会员专栏", "直播回看", "会员专栏"],
            "status": 0,
            "sort_no": 10,
            "description": "M2 自动化验证套餐",
        },
    )
    assert plan_response.status_code == 201, plan_response.text
    plan = _json_data(plan_response)
    assert plan["benefits"] == ["会员专栏", "直播回看"]

    root_response = test_client.post(
        "/content/category/create",
        headers=auth_headers,
        json={
            "category_code": f"research-{suffix}",
            "category_name": f"投研观点-{suffix}",
            "status": 0,
            "sort_no": 10,
        },
    )
    assert root_response.status_code == 201, root_response.text
    root = _json_data(root_response)

    child_response = test_client.post(
        "/content/category/create",
        headers=auth_headers,
        json={
            "parent_id": root["id"],
            "category_code": f"macro-{suffix}",
            "category_name": f"宏观市场-{suffix}",
            "status": 0,
            "sort_no": 20,
        },
    )
    assert child_response.status_code == 201, child_response.text
    child = _json_data(child_response)

    cycle_response = test_client.put(
        f"/content/category/update/{root['id']}",
        headers=auth_headers,
        json={
            "parent_id": child["id"],
            "category_code": root["category_code"],
            "category_name": root["category_name"],
            "icon": root["icon"],
            "status": root["status"],
            "sort_no": root["sort_no"],
            "description": root["description"],
        },
    )
    assert cycle_response.status_code == 409

    tree_response = test_client.get(
        "/content/category/tree",
        headers=auth_headers,
        params={"enabled_only": True},
    )
    assert tree_response.status_code == 200, tree_response.text
    tree = _json_data(tree_response)
    root_node = next(item for item in tree if item["id"] == root["id"])
    assert [item["id"] for item in root_node["children"]] == [child["id"]]

    invalid_entitlement = test_client.post(
        "/content/article/create",
        headers=auth_headers,
        json={
            "category_id": child["id"],
            "content_type": "macro",
            "title": "错误权益组合",
            "slug": f"invalid-entitlement-{suffix}",
            "body": "<p>正文</p>",
            "body_format": "html",
            "author_name": "测试作者",
            "access_level": "public",
            "plan_ids": [plan["id"]],
        },
    )
    assert invalid_entitlement.status_code == 422

    create_response = test_client.post(
        "/content/article/create",
        headers=auth_headers,
        json={
            "category_id": child["id"],
            "content_type": "macro",
            "title": f"全球流动性观察-{suffix}",
            "slug": f"global-liquidity-{suffix}",
            "summary": "测试投研内容工作流",
            "cover_url": "/static/upload/demo.png",
            "body": (
                '<p onclick="alert(1)">安全正文</p>'
                '<script>alert(2)</script>'
                '<a href="javascript:alert(3)">危险链接</a>'
            ),
            "body_format": "html",
            "author_name": "若琪",
            "access_level": "premium",
            "plan_ids": [plan["id"]],
            "is_pinned": True,
            "is_featured": True,
            "sort_no": 1,
            "description": "M2 自动化验证内容",
        },
    )
    assert create_response.status_code == 201, create_response.text
    content = _json_data(create_response)
    assert content["status"] == 0
    assert content["version_no"] == 1
    assert content["plan_ids"] == [plan["id"]]
    assert "<script" not in content["body"].lower()
    assert "onclick" not in content["body"].lower()
    assert "javascript:" not in content["body"].lower()

    stale_response = test_client.patch(
        f"/content/article/update/{content['id']}",
        headers=auth_headers,
        json={"version_no": 999, "title": "过期版本更新"},
    )
    assert stale_response.status_code == 409

    update_response = test_client.patch(
        f"/content/article/update/{content['id']}",
        headers=auth_headers,
        json={
            "version_no": content["version_no"],
            "title": f"全球流动性观察（修订）-{suffix}",
            "body": '<p style="color:red" onmouseover="alert(4)">修订正文</p>',
        },
    )
    assert update_response.status_code == 200, update_response.text
    content = _json_data(update_response)
    assert content["version_no"] == 2
    assert "onmouseover" not in content["body"].lower()

    publish_response = test_client.post(
        f"/content/article/publish/{content['id']}",
        headers=auth_headers,
        json={"version_no": content["version_no"]},
    )
    assert publish_response.status_code == 200, publish_response.text
    content = _json_data(publish_response)
    assert content["status"] == 1
    assert content["version_no"] == 3
    assert content["published_at"] is not None

    delete_published_response = test_client.request(
        "DELETE",
        "/content/article/delete",
        headers=auth_headers,
        json={"ids": [content["id"]]},
    )
    assert delete_published_response.status_code == 409

    offline_response = test_client.post(
        f"/content/article/offline/{content['id']}",
        headers=auth_headers,
        json={"version_no": content["version_no"]},
    )
    assert offline_response.status_code == 200, offline_response.text
    content = _json_data(offline_response)
    assert content["status"] == 2
    assert content["version_no"] == 4
    assert content["is_pinned"] is False
    assert content["is_featured"] is False

    archive_response = test_client.post(
        f"/content/article/archive/{content['id']}",
        headers=auth_headers,
        json={"version_no": content["version_no"]},
    )
    assert archive_response.status_code == 200, archive_response.text
    content = _json_data(archive_response)
    assert content["status"] == 3
    assert content["version_no"] == 5

    delete_response = test_client.request(
        "DELETE",
        "/content/article/delete",
        headers=auth_headers,
        json={"ids": [content["id"]]},
    )
    assert delete_response.status_code == 200, delete_response.text

    detail_after_delete = test_client.get(
        f"/content/article/detail/{content['id']}",
        headers=auth_headers,
    )
    assert detail_after_delete.status_code == 404

    root_only_delete = test_client.request(
        "DELETE",
        "/content/category/delete",
        headers=auth_headers,
        json=[root["id"]],
    )
    assert root_only_delete.status_code == 409

    category_delete = test_client.request(
        "DELETE",
        "/content/category/delete",
        headers=auth_headers,
        json=[root["id"], child["id"]],
    )
    assert category_delete.status_code == 200, category_delete.text

    plan_delete_blocked = test_client.request(
        "DELETE",
        "/membership/plan/delete",
        headers=auth_headers,
        json=[plan["id"]],
    )
    assert plan_delete_blocked.status_code == 409


def test_member_plan_and_content_validation_boundaries(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    suffix = _suffix()

    invalid_url = test_client.post(
        "/content/article/create",
        headers=auth_headers,
        json={
            "category_id": 1,
            "content_type": "article",
            "title": "非法URL",
            "slug": f"invalid-url-{suffix}",
            "cover_url": "javascript:alert(1)",
            "body": "<p>正文</p>",
            "body_format": "html",
            "author_name": "测试作者",
            "access_level": "public",
        },
    )
    assert invalid_url.status_code == 422

    invalid_plan_code = test_client.post(
        "/membership/plan/create",
        headers=auth_headers,
        json={
            "plan_code": "中文编码",
            "plan_name": f"非法套餐-{suffix}",
            "rank": 1,
            "price": "0",
            "currency": "CNY",
            "duration_days": 365,
            "benefits": [],
            "status": 0,
            "sort_no": 0,
        },
    )
    assert invalid_plan_code.status_code == 422
