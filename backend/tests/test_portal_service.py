from app.api.v1.module_portal.service import PortalService


def test_home_contract() -> None:
    payload = PortalService.home()
    assert payload.brand_name == "财不外露"
    assert payload.categories[0] == "全部"
    assert len(payload.pinned) == 3
    assert len(payload.feed) >= 3
    assert any(item.access_level == "member" for item in payload.feed)
    assert any(item.access_level == "public" for item in payload.feed)
    assert payload.model_dump(mode="json")["member"]["member_no"] == "NO. 00842"


def test_academy_contract() -> None:
    payload = PortalService.academy()
    assert len(payload.live_sessions) == 2
    assert len(payload.columns) == 2
    assert payload.course_categories[0] == "全部"
    assert all(course.lesson_count > 0 for course in payload.courses)


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
    assert sum(len(chapter.lessons) for chapter in payload.chapters) == payload.lesson_count
    assert PortalService.course_detail(999999) is None


def test_member_center_contract() -> None:
    payload = PortalService.member_center()
    assert payload.member.level_name == "星球尊享年会员"
    assert any(plan.recommended for plan in payload.plans)
    assert all(plan.price > 0 for plan in payload.plans)
