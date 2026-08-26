"""财不外露 Portal API 契约验证。

该脚本仅依赖 Pydantic 与 Portal 模块本身，不加载 FastApiAdmin 的全局
pytest conftest、数据库、Redis 或 FastAPI 应用，因此适合作为 M1 CI 的
快速阻断检查。
"""

from __future__ import annotations

from app.api.v1.module_portal.service import PortalService


def verify_home() -> None:
    payload = PortalService.home()
    assert payload.brand_name == "财不外露"
    assert payload.categories and payload.categories[0] == "全部"
    assert len(payload.pinned) == 3
    assert len(payload.feed) >= 3
    assert any(item.access_level == "member" for item in payload.feed)
    assert any(item.access_level == "public" for item in payload.feed)
    assert payload.model_dump(mode="json")["member"]["member_no"] == "NO. 00842"


def verify_academy() -> None:
    payload = PortalService.academy()
    assert len(payload.live_sessions) >= 2
    assert len(payload.columns) >= 2
    assert payload.course_categories and payload.course_categories[0] == "全部"
    assert payload.courses
    assert all(course.lesson_count > 0 for course in payload.courses)


def verify_profile() -> None:
    payload = PortalService.profile()
    assert payload.stats.learning_hours == 42.5
    assert payload.recent_learning.progress == 68
    assert sum(item.unlocked for item in payload.achievements) == 3
    assert payload.member.expire_date.isoformat() == "2027-08-19"


def verify_details() -> None:
    content = PortalService.content_detail(1001)
    assert content is not None
    assert content.id == 1001
    assert content.reading_minutes > 0
    assert len(content.sections) >= 2
    assert PortalService.content_detail(999999) is None

    course = PortalService.course_detail(4001)
    assert course is not None
    assert course.lesson_count > 0
    assert sum(len(chapter.lessons) for chapter in course.chapters) == course.lesson_count
    assert PortalService.course_detail(999999) is None


def verify_membership() -> None:
    payload = PortalService.member_center()
    assert payload.member.level_name == "星球尊享年会员"
    assert any(plan.recommended for plan in payload.plans)
    assert all(plan.price > 0 for plan in payload.plans)


def main() -> None:
    checks = (
        ("home", verify_home),
        ("academy", verify_academy),
        ("profile", verify_profile),
        ("details", verify_details),
        ("membership", verify_membership),
    )
    for name, check in checks:
        check()
        print(f"PASS portal:{name}")
    print(f"PASS portal:all ({len(checks)} checks)")


if __name__ == "__main__":
    main()
