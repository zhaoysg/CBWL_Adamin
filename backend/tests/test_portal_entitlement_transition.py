from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.module_membership.entitlement import EntitlementContext
from app.api.v1.module_portal import entitlement as portal_entitlement
from app.api.v1.module_portal.principal import PortalPrincipal
from app.config.portal_auth import portal_auth_settings
from app.core.base_schema import AuthSchema, CoreUserSchema
from app.core.exceptions import CustomException


def _auth(user_id: int = 11) -> AuthSchema:
    return AuthSchema(
        user=CoreUserSchema(
            id=user_id,
            username=f"legacy_{user_id}",
            name=f"Legacy {user_id}",
            is_superuser=False,
        ),
        permissions=[],
        menu_ids=[],
    )


def _principal(
    *,
    actor_type: str = "customer",
    legacy_user_id: int = 11,
    customer_id: int = 21,
) -> PortalPrincipal:
    if actor_type == "legacy":
        return PortalPrincipal(
            actor_type="legacy",
            auth=_auth(legacy_user_id),
            legacy_user_id=legacy_user_id,
        )
    return PortalPrincipal(
        actor_type="customer",
        auth=_auth(legacy_user_id),
        legacy_user_id=legacy_user_id,
        customer_id=customer_id,
        subject_id=31,
    )


def _context(
    *subscription_ids: int,
    user_id: int | None = 11,
    customer_id: int | None = None,
) -> EntitlementContext:
    subscriptions = tuple(SimpleNamespace(id=item, plan_id=item + 100) for item in subscription_ids)
    return EntitlementContext(
        user_id=user_id,
        customer_id=customer_id,
        active_plan_ids=frozenset(item.plan_id for item in subscriptions),
        subscriptions=subscriptions,
    )


def test_portal_principal_rejects_ambiguous_identity_data() -> None:
    with pytest.raises(ValueError, match="anonymous"):
        PortalPrincipal(
            actor_type="anonymous",
            auth=_auth(),
        )
    with pytest.raises(ValueError, match="must match"):
        PortalPrincipal(
            actor_type="legacy",
            auth=_auth(10),
            legacy_user_id=11,
        )
    with pytest.raises(ValueError, match="customer and subject"):
        PortalPrincipal(
            actor_type="customer",
            auth=_auth(11),
            legacy_user_id=11,
        )


def test_customer_only_entitlement_context_is_authenticated() -> None:
    context = EntitlementContext(
        user_id=None,
        customer_id=21,
        active_plan_ids=frozenset(),
        subscriptions=(),
    )
    assert context.is_authenticated is True


@pytest.mark.asyncio
async def test_anonymous_entitlement_does_not_query_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_loader = AsyncMock()
    customer_loader = AsyncMock()
    monkeypatch.setattr(
        portal_entitlement,
        "load_entitlement_context",
        legacy_loader,
    )
    monkeypatch.setattr(
        portal_entitlement,
        "_load_customer_entitlement_context",
        customer_loader,
    )

    context = await portal_entitlement.load_portal_entitlement_context(
        AsyncMock(),
        PortalPrincipal.anonymous(),
    )
    assert context.is_authenticated is False
    legacy_loader.assert_not_awaited()
    customer_loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_mode_uses_only_legacy_subscription_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _context(1, 2)
    legacy_loader = AsyncMock(return_value=legacy)
    customer_loader = AsyncMock()
    monkeypatch.setattr(portal_auth_settings, "ENTITLEMENT_MODE", "legacy")
    monkeypatch.setattr(
        portal_entitlement,
        "load_entitlement_context",
        legacy_loader,
    )
    monkeypatch.setattr(
        portal_entitlement,
        "_load_customer_entitlement_context",
        customer_loader,
    )

    result = await portal_entitlement.load_portal_entitlement_context(
        AsyncMock(),
        _principal(),
    )
    assert result is legacy
    legacy_loader.assert_awaited_once()
    customer_loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_dual_mode_requires_identical_active_subscription_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal()
    legacy = _context(2, 1)
    customer = _context(1, 2, customer_id=principal.customer_id)
    monkeypatch.setattr(portal_auth_settings, "ENTITLEMENT_MODE", "dual")
    monkeypatch.setattr(
        portal_entitlement,
        "load_entitlement_context",
        AsyncMock(return_value=legacy),
    )
    monkeypatch.setattr(
        portal_entitlement,
        "_load_customer_entitlement_context",
        AsyncMock(return_value=customer),
    )

    result = await portal_entitlement.load_portal_entitlement_context(
        AsyncMock(),
        principal,
    )
    assert result is customer


@pytest.mark.asyncio
async def test_dual_mode_fails_closed_on_subscription_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = _principal()
    monkeypatch.setattr(portal_auth_settings, "ENTITLEMENT_MODE", "dual")
    monkeypatch.setattr(
        portal_entitlement,
        "load_entitlement_context",
        AsyncMock(return_value=_context(1, 2)),
    )
    monkeypatch.setattr(
        portal_entitlement,
        "_load_customer_entitlement_context",
        AsyncMock(
            return_value=_context(
                1,
                customer_id=principal.customer_id,
            )
        ),
    )

    with pytest.raises(CustomException) as error:
        await portal_entitlement.load_portal_entitlement_context(
            AsyncMock(),
            principal,
        )
    assert error.value.status_code == 503
    assert "同步中" in error.value.msg


@pytest.mark.asyncio
async def test_dual_mode_keeps_unmapped_legacy_user_on_legacy_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _context(1)
    customer_loader = AsyncMock()
    monkeypatch.setattr(portal_auth_settings, "ENTITLEMENT_MODE", "dual")
    monkeypatch.setattr(
        portal_entitlement,
        "load_entitlement_context",
        AsyncMock(return_value=legacy),
    )
    monkeypatch.setattr(
        portal_entitlement,
        "_load_customer_entitlement_context",
        customer_loader,
    )

    result = await portal_entitlement.load_portal_entitlement_context(
        AsyncMock(),
        _principal(actor_type="legacy"),
    )
    assert result is legacy
    customer_loader.assert_not_awaited()


@pytest.mark.asyncio
async def test_customer_mode_rejects_legacy_only_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        portal_auth_settings,
        "ENTITLEMENT_MODE",
        "customer",
    )
    monkeypatch.setattr(
        portal_entitlement,
        "load_entitlement_context",
        AsyncMock(return_value=_context()),
    )

    with pytest.raises(CustomException) as error:
        await portal_entitlement.load_portal_entitlement_context(
            AsyncMock(),
            _principal(actor_type="legacy"),
        )
    assert error.value.status_code == 503
    assert "尚未完成迁移" in error.value.msg
