from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_identity.model import AuthSubjectModel, CustomerModel
from app.api.v1.module_system.user.model import UserModel
from app.common.enums import RET
from app.core.exceptions import CustomException

CommerceActorType = Literal["legacy", "customer"]


@dataclass(frozen=True, slots=True)
class CommerceOwner:
    """Server-derived business owner for an order or payment attempt.

    During the migration window a customer actor may carry both IDs. After the
    final contract migration, customer-only ownership remains valid.
    """

    actor_type: CommerceActorType
    legacy_user_id: int | None = None
    customer_id: int | None = None
    subject_id: int | None = None

    def __post_init__(self) -> None:
        if self.actor_type == "legacy":
            if self.legacy_user_id is None or self.legacy_user_id <= 0:
                raise ValueError("legacy owner requires a positive legacy_user_id")
            if self.customer_id is not None or self.subject_id is not None:
                raise ValueError("legacy owner cannot contain customer identity data")
            return

        if self.customer_id is None or self.customer_id <= 0:
            raise ValueError("customer owner requires a positive customer_id")
        if self.legacy_user_id is not None and self.legacy_user_id <= 0:
            raise ValueError("legacy_user_id must be positive when supplied")
        if self.subject_id is not None and self.subject_id <= 0:
            raise ValueError("subject_id must be positive when supplied")

    @classmethod
    def legacy(cls, legacy_user_id: int) -> CommerceOwner:
        return cls(actor_type="legacy", legacy_user_id=legacy_user_id)

    @classmethod
    def customer(
        cls,
        customer_id: int,
        *,
        legacy_user_id: int | None = None,
        subject_id: int | None = None,
    ) -> CommerceOwner:
        return cls(
            actor_type="customer",
            legacy_user_id=legacy_user_id,
            customer_id=customer_id,
            subject_id=subject_id,
        )

    @property
    def namespace(self) -> str:
        if self.actor_type == "customer":
            return f"customer:{self.customer_id}"
        return f"legacy:{self.legacy_user_id}"


class CommerceOwnershipValidator:
    """Validate ownership against active identity records inside the transaction."""

    @classmethod
    async def validate(
        cls,
        db: AsyncSession,
        owner: CommerceOwner,
        *,
        for_update: bool = True,
    ) -> None:
        if owner.legacy_user_id is not None:
            user_stmt = select(UserModel.id).where(
                UserModel.id == owner.legacy_user_id,
                UserModel.status == 0,
                UserModel.is_deleted.is_(False),
            )
            if for_update:
                user_stmt = user_stmt.with_for_update()
            if await db.scalar(user_stmt) is None:
                raise cls._forbidden("交易主体不可用")

        if owner.actor_type == "legacy":
            return

        customer_stmt = (
            select(CustomerModel, AuthSubjectModel)
            .join(
                AuthSubjectModel,
                and_(
                    AuthSubjectModel.id == CustomerModel.subject_id,
                    AuthSubjectModel.realm == CustomerModel.realm,
                ),
            )
            .where(
                CustomerModel.id == owner.customer_id,
                CustomerModel.realm == "customer",
                CustomerModel.status == "active",
                CustomerModel.is_deleted.is_(False),
                AuthSubjectModel.realm == "customer",
                AuthSubjectModel.status == "active",
                AuthSubjectModel.is_deleted.is_(False),
            )
        )
        if for_update:
            customer_stmt = customer_stmt.with_for_update()
        row = (await db.execute(customer_stmt)).first()
        if row is None:
            raise cls._forbidden("客户交易主体不可用")

        customer, subject = row
        if owner.subject_id is not None and subject.id != owner.subject_id:
            raise cls._unavailable("客户认证主体不一致，暂不能创建交易")
        if customer.subject_id != subject.id:
            raise cls._unavailable("客户认证关系不一致，暂不能创建交易")

        if owner.legacy_user_id is None:
            return

        mapping_stmt = select(LegacyCustomerMapModel.id).where(
            LegacyCustomerMapModel.legacy_sys_user_id == owner.legacy_user_id,
            LegacyCustomerMapModel.customer_id == owner.customer_id,
            LegacyCustomerMapModel.credential_state == "migrated",
            LegacyCustomerMapModel.is_deleted.is_(False),
        )
        if for_update:
            mapping_stmt = mapping_stmt.with_for_update()
        if await db.scalar(mapping_stmt) is None:
            raise cls._unavailable("客户与旧用户映射不一致，暂不能创建交易")

    @staticmethod
    def _forbidden(message: str) -> CustomException:
        return CustomException(
            msg=message,
            code=RET.FORBIDDEN.code,
            status_code=RET.FORBIDDEN.code,
        )

    @staticmethod
    def _unavailable(message: str) -> CustomException:
        return CustomException(
            msg=message,
            code=RET.SERVICE_UNAVAILABLE.code,
            status_code=RET.SERVICE_UNAVAILABLE.code,
        )


__all__ = ["CommerceActorType", "CommerceOwner", "CommerceOwnershipValidator"]
