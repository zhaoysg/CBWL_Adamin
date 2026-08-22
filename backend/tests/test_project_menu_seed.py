from __future__ import annotations

from fastapi.testclient import TestClient


def _flatten(nodes: list[dict]) -> list[dict]:
    result: list[dict] = []
    for node in nodes:
        result.append(node)
        result.extend(_flatten(node.get("children") or []))
    return result


def test_project_menu_seed_contains_routes_and_permissions(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = test_client.get("/system/menu/tree", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True

    menus = _flatten(payload["data"])
    route_names = {item.get("route_name") for item in menus}
    permissions = {item.get("permission") for item in menus if item.get("permission")}

    assert {
        "ContentOperations",
        "ContentArticle",
        "ContentCategory",
        "Membership",
        "MembershipPlan",
    } <= route_names

    expected_permissions = {
        "module_content:article:query",
        "module_content:article:detail",
        "module_content:article:create",
        "module_content:article:update",
        "module_content:article:publish",
        "module_content:article:offline",
        "module_content:article:archive",
        "module_content:article:delete",
        "module_content:category:query",
        "module_content:category:detail",
        "module_content:category:create",
        "module_content:category:update",
        "module_content:category:patch",
        "module_content:category:delete",
        "module_membership:plan:query",
        "module_membership:plan:detail",
        "module_membership:plan:create",
        "module_membership:plan:update",
        "module_membership:plan:patch",
        "module_membership:plan:delete",
    }
    assert expected_permissions <= permissions


def test_project_menu_seed_is_idempotent(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    first = test_client.get("/system/menu/tree", headers=auth_headers)
    second = test_client.get("/system/menu/tree", headers=auth_headers)
    assert first.status_code == 200
    assert second.status_code == 200

    first_rows = _flatten(first.json()["data"])
    second_rows = _flatten(second.json()["data"])
    first_permissions = [item.get("permission") for item in first_rows if item.get("permission")]
    second_permissions = [item.get("permission") for item in second_rows if item.get("permission")]
    assert len(first_permissions) == len(set(first_permissions))
    assert first_permissions == second_permissions
