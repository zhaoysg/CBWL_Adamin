from __future__ import annotations

from fastapi.testclient import TestClient

PROJECT_PERMISSION_PREFIXES = ("module_content:", "module_membership:")


def _flatten(nodes: list[dict], parent_route_name: str | None = None) -> list[dict]:
    result: list[dict] = []
    for node in nodes:
        row = dict(node)
        row["_parent_route_name"] = parent_route_name
        result.append(row)
        result.extend(
            _flatten(
                node.get("children") or [],
                node.get("route_name") or parent_route_name,
            )
        )
    return result


def _project_rows(rows: list[dict]) -> list[dict]:
    route_names = {
        "ContentOperations",
        "ContentArticle",
        "ContentCategory",
        "Membership",
        "MembershipPlan",
    }
    return [
        row
        for row in rows
        if row.get("route_name") in route_names
        or str(row.get("permission") or "").startswith(PROJECT_PERMISSION_PREFIXES)
    ]


def _project_signature(rows: list[dict]) -> list[tuple]:
    return sorted(
        (
            row.get("type"),
            row.get("route_name"),
            row.get("permission"),
            row.get("_parent_route_name"),
        )
        for row in _project_rows(rows)
    )


def test_project_menu_seed_contains_routes_and_permissions(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = test_client.get("/system/menu/tree", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True

    menus = _flatten(payload["data"])
    by_route_name = {
        item.get("route_name"): item for item in menus if item.get("route_name")
    }
    permissions = {item.get("permission") for item in menus if item.get("permission")}

    assert {
        "ContentOperations",
        "ContentArticle",
        "ContentCategory",
        "Membership",
        "MembershipPlan",
    } <= by_route_name.keys()

    assert by_route_name["ContentArticle"]["type"] == 2
    assert by_route_name["ContentArticle"]["_parent_route_name"] == "ContentOperations"
    assert by_route_name["ContentCategory"]["type"] == 2
    assert by_route_name["ContentCategory"]["_parent_route_name"] == "ContentOperations"
    assert by_route_name["MembershipPlan"]["type"] == 2
    assert by_route_name["MembershipPlan"]["_parent_route_name"] == "Membership"

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

    project_buttons = [
        item
        for item in menus
        if item.get("type") == 3
        and str(item.get("permission") or "").startswith(PROJECT_PERMISSION_PREFIXES)
    ]
    button_permissions = [item["permission"] for item in project_buttons]
    assert len(button_permissions) == len(set(button_permissions))


def test_project_menu_tree_is_stable_across_repeated_reads(
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    first = test_client.get("/system/menu/tree", headers=auth_headers)
    second = test_client.get("/system/menu/tree", headers=auth_headers)
    assert first.status_code == 200
    assert second.status_code == 200

    first_rows = _flatten(first.json()["data"])
    second_rows = _flatten(second.json()["data"])
    assert _project_signature(first_rows) == _project_signature(second_rows)
