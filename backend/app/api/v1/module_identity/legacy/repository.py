from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_identity.enums import (
    IdentityProvider,
    IdentityRealm,
)
from app.api.v1.module_identity.model import (
    AuthIdentityModel,
    CustomerModel,
)
from app.api.v1.module_membership.subscription.model import (
    MemberSubscriptionModel,
)
from app.api.v1.module_system.user.model import (
    UserModel,
    UserPositionsModel,
    UserRolesModel,
)

from .model import LegacyCustomerMapModel


class LegacyCustomerMigrationError(RuntimeError):
    """Base error for an isolated legacy customer migration."""


class LegacyCustomerMigrationConflict(LegacyCustomerMigrationError):
    """Migration cannot continue without a human decision."""


@dataclass(frozen=True, slots=True)
class LegacyUserSnapshot:
    id: int
    username: str
    password: str
    name: str
    avatar: str | None
    is_superuser: bool
    status: int
    dept_id: int | None
    has_roles: bool
    has_positions: bool


async def load_user_for_update(
    db: AsyncSession,
    legacy_sys_user_id: int,
) -> LegacyUserSnapshot:
    row = (
        await db.execute(
            select(
                UserModel.id,
                UserModel.username,
                UserModel.password,
                UserModel.name,
                UserModel.avatar,
                UserModel.is_superuser,
                UserModel.status,
                UserModel.dept_id,
            )
            .where(
                UserModel.id == legacy_sys_user_id,
                UserModel.is_deleted.is_(False),
            )
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise LegacyCustomerMigrationError("legacy user does not exist or is deleted")

    role_ids = (await db.scalars(select(UserRolesModel.role_id).where(UserRolesModel.user_id == legacy_sys_user_id).with_for_update())).all()
    position_ids = (await db.scalars(select(UserPositionsModel.position_id).where(UserPositionsModel.user_id == legacy_sys_user_id).with_for_update())).all()
    return LegacyUserSnapshot(
        id=row.id,
        username=row.username,
        password=row.password,
        name=row.name,
        avatar=row.avatar,
        is_superuser=bool(row.is_superuser),
        status=row.status,
        dept_id=row.dept_id,
        has_roles=bool(role_ids),
        has_positions=bool(position_ids),
    )


async def lock_subscriptions(
    db: AsyncSession,
    legacy_sys_user_id: int,
) -> list[tuple[int, int | None]]:
    rows = (
        await db.execute(
            select(
                MemberSubscriptionModel.id,
                MemberSubscriptionModel.customer_id,
            )
            .where(
                MemberSubscriptionModel.user_id == legacy_sys_user_id,
                MemberSubscriptionModel.is_deleted.is_(False),
            )
            .order_by(MemberSubscriptionModel.id)
            .with_for_update()
        )
    ).all()
    return [(row.id, row.customer_id) for row in rows]


async def load_mapping_for_update(
    db: AsyncSession,
    legacy_sys_user_id: int,
) -> LegacyCustomerMapModel | None:
    return await db.scalar(
        select(LegacyCustomerMapModel)
        .where(
            LegacyCustomerMapModel.legacy_sys_user_id == legacy_sys_user_id,
            LegacyCustomerMapModel.is_deleted.is_(False),
        )
        .with_for_update()
    )


async def customer_identifier_exists(
    db: AsyncSession,
    normalized_identifier: str,
) -> bool:
    identity_id = await db.scalar(
        select(AuthIdentityModel.id)
        .where(
            AuthIdentityModel.realm == IdentityRealm.CUSTOMER,
            AuthIdentityModel.provider == IdentityProvider.PASSWORD,
            AuthIdentityModel.identifier_normalized == normalized_identifier,
            AuthIdentityModel.is_deleted.is_(False),
        )
        .with_for_update()
    )
    return identity_id is not None


async def ensure_customer_exists(
    db: AsyncSession,
    customer_id: int,
) -> None:
    existing = await db.scalar(
        select(CustomerModel.id)
        .where(
            CustomerModel.id == customer_id,
            CustomerModel.is_deleted.is_(False),
        )
        .with_for_update()
    )
    if existing is None:
        raise LegacyCustomerMigrationConflict("legacy map references a missing or deleted customer")


def assert_subscription_ownership(
    subscriptions: list[tuple[int, int | None]],
    customer_id: int,
) -> None:
    if any(existing_customer_id is not None and existing_customer_id != customer_id for _, existing_customer_id in subscriptions):
        raise LegacyCustomerMigrationConflict("legacy subscriptions already reference another customer")


async def backfill_subscriptions(
    db: AsyncSession,
    *,
    legacy_sys_user_id: int,
    customer_id: int,
) -> int:
    result = await db.execute(
        update(MemberSubscriptionModel)
        .where(
            MemberSubscriptionModel.user_id == legacy_sys_user_id,
            MemberSubscriptionModel.customer_id.is_(None),
            MemberSubscriptionModel.is_deleted.is_(False),
        )
        .values(customer_id=customer_id)
    )
    return int(result.rowcount or 0)
