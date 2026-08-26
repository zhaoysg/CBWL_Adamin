from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.module_portal import portal_router
from app.api.v1.module_portal.runtime import get_portal_runtime_state
from app.api.v1.module_portal.service import PortalService


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(portal_router, prefix="/api/v1")
    return TestClient(app)


def test_home_contract() -> None:
    payload = PortalService.home()
    assert payload.brand_name == "财不外露"
    assert payload.categories[0] == "全部"
    assert len(payload.pinned) == 3
    assert len(payload.feed) >= 3
    assert any(item.access_level == "member" for item in payload.feed)
    assert any(item.access_level == "public" for item in payload.feed)
    assert payload.model_dump(mode="json")["member"]["member_no"] == "NO. 00842"

    content_ids = {item.id for item in payload.feed}
    for item in payload.pinned:
        if item.target_type == "content":
            assert item.target_id in content_ids
        else:
            assert item.target_id is None


def test_academy_contract() -> None:
    payload = PortalService.academy()
    assert len(payload.live_sessions) == 2
    assert len(payload.columns) == 2
    assert payload.course_categories[0] == "全部"
    assert all(course.lesson_count > 0 for course in payload.courses)
    assert {course.category for course in payload.courses}.issubset(set(payload.course_categories))


def test_profile_contract() -> None:
    payload = PortalService.profile()
    assert payload.stats.learning_hours == 42.5
    assert payload.recent_learning.progress == 68
    assert sum(item.unlocked for item in payload.achievements) == 3
    assert payload.member.expire_date.isoformat() == "2027-08-19"


def test_content_detail_contract() -> None:
    payload = PortalService.content_detail(1001)
    assert payload is not None
    assert payload.id == 1001
    assert payload.reading_minutes > 0
    assert len(payload.sections) >= 2
    assert PortalService.content_detail(999999) is None


def test_course_detail_contract() -> None:
    payload = PortalService.course_detail(4001)
    assert payload is not None
    assert payload.lesson_count > 0
    assert payload.category == "新手入门"
    assert sum(len(chapter.lessons) for chapter in payload.chapters) == payload.lesson_count
    assert PortalService.course_detail(999999) is None


def test_member_center_contract() -> None:
    payload = PortalService.member_center()
    assert payload.member.level_name == "星球尊享年会员"
    assert any(plan.recommended for plan in payload.plans)
    assert all(plan.price > Decimal("0") for plan in payload.plans)
    assert payload.model_dump(mode="json")["plans"][0]["price"] == "99.00"


def test_runtime_is_fail_closed_in_production(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("PORTAL_DATA_SOURCE", "demo")
    monkeypatch.delenv("PORTAL_ALLOW_DEMO_IN_PROD", raising=False)

    state = get_portal_runtime_state()
    assert state.allowed is False
    assert state.production_ready is False

    response = _client().get("/api/v1/portal/home")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "60"


def test_demo_mode_sets_no_store_headers(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("PORTAL_DATA_SOURCE", "demo")
    monkeypatch.delenv("PORTAL_ALLOW_DEMO_IN_PROD", raising=False)

    response = _client().get("/api/v1/portal/home")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store, max-age=0"
    assert response.headers["x-portal-data-source"] == "demo"


def test_route_rejects_invalid_resource_ids(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("PORTAL_DATA_SOURCE", "demo")

    client = _client()
    assert client.get("/api/v1/portal/content/0").status_code == 422
    assert client.get("/api/v1/portal/course/-1").status_code == 422


def test_health_discloses_non_production_ready_state(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("PORTAL_DATA_SOURCE", "demo")

    response = _client().get("/api/v1/portal/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["production_ready"] is False
    assert payload["data_source"] == "demo"
