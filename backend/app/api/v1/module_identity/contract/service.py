from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_identity.enums import (
    IdentityProvider,
    IdentityRealm,
    IdentityStatus,
)
from app.api.v1.module_identity.legacy.enums import LegacyCredentialState
from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_identity.model import (
    AuthIdentityModel,
    AuthSubjectModel,
    CustomerModel,
)
from app.api.v1.module_membership.subscription.model import (
    MemberSubscriptionModel,
)
from app.api.v1.module_system.user.model import UserModel

from .schema import (
    CustomerContractReadinessCheck,
    CustomerContractReadinessReport,
)


async def _count_query(db: AsyncSession, query) -> int:
    return int(await db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0)


async def _sample_query(
    db: AsyncSession,
    query,
    *,
    limit: int,
) -> list[int]:
    return [int(value) for value in (await db.scalars(query.limit(limit))).all()]


async def _check(
    db: AsyncSession,
    *,
    code: str,
    query,
    message: str,
    sample_limit: int,
) -> CustomerContractReadinessCheck:
    return CustomerContractReadinessCheck(
        code=code,
        count=await _count_query(db, query),
        sample_ids=await _sample_query(db, query, limit=sample_limit),
        message=message,
    )


class CustomerContractReadinessService:
    """Read-only precondition checks before removing legacy ownership."""

    @classmethod
    async def build_report(
        cls,
        db: AsyncSession,
        *,
        sample_limit: int = 50,
    ) -> CustomerContractReadinessReport:
        if sample_limit <= 0 or sample_limit > 100:
            raise ValueError("sample_limit must be between 1 and 100")

        subscriptions = select(MemberSubscriptionModel.id).where(MemberSubscriptionModel.is_deleted.is_(False))
        mapped_subscriptions = subscriptions.where(MemberSubscriptionModel.customer_id.is_not(None))
        active_maps = select(LegacyCustomerMapModel.id).where(LegacyCustomerMapModel.is_deleted.is_(False))

        summary = {
            "subscriptions": await _count_query(db, subscriptions),
            "mapped_subscriptions": await _count_query(
                db,
                mapped_subscriptions,
            ),
            "active_maps": await _count_query(db, active_maps),
            "migrated_maps": await _count_query(
                db,
                active_maps.where(LegacyCustomerMapModel.credential_state == LegacyCredentialState.MIGRATED),
            ),
            "claim_required_maps": await _count_query(
                db,
                active_maps.where(LegacyCustomerMapModel.credential_state == LegacyCredentialState.CLAIM_REQUIRED),
            ),
        }

        exact_map_join = and_(
            LegacyCustomerMapModel.legacy_sys_user_id == MemberSubscriptionModel.user_id,
            LegacyCustomerMapModel.customer_id == MemberSubscriptionModel.customer_id,
            LegacyCustomerMapModel.is_deleted.is_(False),
        )
        legacy_map_join = and_(
            LegacyCustomerMapModel.legacy_sys_user_id == MemberSubscriptionModel.user_id,
            LegacyCustomerMapModel.is_deleted.is_(False),
        )
        active_password_count = (
            select(func.count(AuthIdentityModel.id))
            .where(
                AuthIdentityModel.subject_id == CustomerModel.subject_id,
                AuthIdentityModel.realm == IdentityRealm.CUSTOMER,
                AuthIdentityModel.provider == IdentityProvider.PASSWORD,
                AuthIdentityModel.status == IdentityStatus.ACTIVE,
                AuthIdentityModel.is_deleted.is_(False),
            )
            .correlate(CustomerModel)
            .scalar_subquery()
        )

        checks: Sequence[CustomerContractReadinessCheck] = [
            await _check(
                db,
                code="subscription_customer_missing",
                query=select(MemberSubscriptionModel.id)
                .where(
                    MemberSubscriptionModel.is_deleted.is_(False),
                    MemberSubscriptionModel.customer_id.is_(None),
                )
                .order_by(MemberSubscriptionModel.id),
                message="仍有会员订阅未回填 customer_id",
                sample_limit=sample_limit,
            ),
            await _check(
                db,
                code="subscription_mapping_missing",
                query=select(MemberSubscriptionModel.id)
                .outerjoin(LegacyCustomerMapModel, exact_map_join)
                .where(
                    MemberSubscriptionModel.is_deleted.is_(False),
                    MemberSubscriptionModel.customer_id.is_not(None),
                    LegacyCustomerMapModel.id.is_(None),
                )
                .order_by(MemberSubscriptionModel.id),
                message="会员订阅没有匹配的一对一迁移映射",
                sample_limit=sample_limit,
            ),
            await _check(
                db,
                code="subscription_customer_mismatch",
                query=select(MemberSubscriptionModel.id)
                .join(LegacyCustomerMapModel, legacy_map_join)
                .where(
                    MemberSubscriptionModel.is_deleted.is_(False),
                    MemberSubscriptionModel.customer_id.is_not(None),
                    MemberSubscriptionModel.customer_id != LegacyCustomerMapModel.customer_id,
                )
                .order_by(MemberSubscriptionModel.id),
                message="会员订阅 customer_id 与迁移映射不一致",
                sample_limit=sample_limit,
            ),
            await _check(
                db,
                code="mapping_customer_invalid",
                query=select(LegacyCustomerMapModel.id)
                .outerjoin(
                    CustomerModel,
                    CustomerModel.id == LegacyCustomerMapModel.customer_id,
                )
                .where(
                    LegacyCustomerMapModel.is_deleted.is_(False),
                    or_(
                        CustomerModel.id.is_(None),
                        CustomerModel.is_deleted.is_(True),
                        CustomerModel.status != IdentityStatus.ACTIVE,
                        CustomerModel.realm != IdentityRealm.CUSTOMER,
                    ),
                )
                .order_by(LegacyCustomerMapModel.id),
                message="迁移映射指向缺失、停用或非 customer realm 的客户",
                sample_limit=sample_limit,
            ),
            await _check(
                db,
                code="mapping_legacy_user_invalid",
                query=select(LegacyCustomerMapModel.id)
                .outerjoin(
                    UserModel,
                    UserModel.id == LegacyCustomerMapModel.legacy_sys_user_id,
                )
                .where(
                    LegacyCustomerMapModel.is_deleted.is_(False),
                    or_(
                        UserModel.id.is_(None),
                        UserModel.is_deleted.is_(True),
                    ),
                )
                .order_by(LegacyCustomerMapModel.id),
                message="迁移映射缺少过渡期旧用户回滚主体",
                sample_limit=sample_limit,
            ),
            await _check(
                db,
                code="claim_required_remaining",
                query=select(LegacyCustomerMapModel.id)
                .where(
                    LegacyCustomerMapModel.is_deleted.is_(False),
                    LegacyCustomerMapModel.credential_state == LegacyCredentialState.CLAIM_REQUIRED,
                )
                .order_by(LegacyCustomerMapModel.id),
                message="仍有客户需要完成身份认领或密码重置",
                sample_limit=sample_limit,
            ),
            await _check(
                db,
                code="migrated_password_identity_invalid",
                query=select(LegacyCustomerMapModel.id)
                .join(
                    CustomerModel,
                    CustomerModel.id == LegacyCustomerMapModel.customer_id,
                )
                .where(
                    LegacyCustomerMapModel.is_deleted.is_(False),
                    LegacyCustomerMapModel.credential_state == LegacyCredentialState.MIGRATED,
                    active_password_count != 1,
                )
                .order_by(LegacyCustomerMapModel.id),
                message="已迁移客户没有且仅有一个有效密码身份",
                sample_limit=sample_limit,
            ),
            await _check(
                db,
                code="customer_subject_invalid",
                query=select(CustomerModel.id)
                .outerjoin(
                    AuthSubjectModel,
                    and_(
                        AuthSubjectModel.id == CustomerModel.subject_id,
                        AuthSubjectModel.realm == CustomerModel.realm,
                    ),
                )
                .join(
                    LegacyCustomerMapModel,
                    and_(
                        LegacyCustomerMapModel.customer_id == CustomerModel.id,
                        LegacyCustomerMapModel.is_deleted.is_(False),
                    ),
                )
                .where(
                    CustomerModel.is_deleted.is_(False),
                    or_(
                        AuthSubjectModel.id.is_(None),
                        AuthSubjectModel.is_deleted.is_(True),
                        AuthSubjectModel.status != IdentityStatus.ACTIVE,
                        AuthSubjectModel.realm != IdentityRealm.CUSTOMER,
                    ),
                )
                .order_by(CustomerModel.id),
                message="迁移客户的认证主体缺失、停用或 realm 不一致",
                sample_limit=sample_limit,
            ),
        ]

        return CustomerContractReadinessReport(
            ready=all(item.count == 0 for item in checks),
            generated_at=datetime.now(UTC),
            summary=summary,
            checks=list(checks),
        )
