from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from .enums import IdentityProvider, IdentityRealm, IdentityStatus
from .model import (
    AdminAccountModel,
    AuthIdentityModel,
    AuthSubjectModel,
    CustomerModel,
)
from .normalization import normalize_identifier
from .schema import AdminBridgeProvisionSchema, CustomerProvisionSchema


class IdentityProvisionError(ValueError):
    """Invalid provisioning request detected before persistence."""


@dataclass(frozen=True, slots=True)
class ProvisionedCustomer:
    subject: AuthSubjectModel
    identity: AuthIdentityModel
    customer: CustomerModel


@dataclass(frozen=True, slots=True)
class ProvisionedAdmin:
    subject: AuthSubjectModel
    identity: AuthIdentityModel
    admin: AdminAccountModel


class IdentityService:
    """Create identity aggregates without committing the caller's transaction.

    The request/application service owns the transaction. Database unique
    constraints are the final concurrency boundary. Callers must map an
    IntegrityError to a generic conflict without revealing account existence.
    """

    @staticmethod
    def _credential_hash(
        provider: IdentityProvider,
        credential_hash: str | None,
    ) -> str | None:
        if provider is IdentityProvider.PASSWORD:
            if not credential_hash or len(credential_hash) < 20:
                raise IdentityProvisionError("password identity requires a secure credential hash")
            return credential_hash
        if credential_hash is not None:
            raise IdentityProvisionError("non-password identity cannot store a password hash")
        return None

    @classmethod
    async def create_customer(
        cls,
        db: AsyncSession,
        data: CustomerProvisionSchema,
        *,
        credential_hash: str | None = None,
    ) -> ProvisionedCustomer:
        normalized = normalize_identifier(data.provider, data.identifier)
        stored_hash = cls._credential_hash(data.provider, credential_hash)

        subject = AuthSubjectModel(
            realm=IdentityRealm.CUSTOMER.value,
            status=IdentityStatus.ACTIVE.value,
            version_no=1,
        )
        db.add(subject)
        await db.flush()
        if subject.id is None:
            raise RuntimeError("database did not assign auth subject id")

        identity = AuthIdentityModel(
            subject_id=subject.id,
            realm=IdentityRealm.CUSTOMER.value,
            provider=data.provider.value,
            identifier_normalized=normalized,
            credential_hash=stored_hash,
            status=IdentityStatus.ACTIVE.value,
            version_no=1,
        )
        customer = CustomerModel(
            subject_id=subject.id,
            realm=IdentityRealm.CUSTOMER.value,
            customer_no=f"C{uuid4().hex[:20].upper()}",
            nickname=data.nickname,
            avatar_url=data.avatar_url,
            register_source=data.register_source.value,
            status=IdentityStatus.ACTIVE.value,
            version_no=1,
        )
        db.add_all([identity, customer])
        await db.flush()
        return ProvisionedCustomer(
            subject=subject,
            identity=identity,
            customer=customer,
        )

    @classmethod
    async def create_admin_bridge(
        cls,
        db: AsyncSession,
        data: AdminBridgeProvisionSchema,
        *,
        credential_hash: str | None = None,
    ) -> ProvisionedAdmin:
        normalized = normalize_identifier(data.provider, data.identifier)
        stored_hash = cls._credential_hash(data.provider, credential_hash)

        subject = AuthSubjectModel(
            realm=IdentityRealm.ADMIN.value,
            status=IdentityStatus.ACTIVE.value,
            version_no=1,
        )
        db.add(subject)
        await db.flush()
        if subject.id is None:
            raise RuntimeError("database did not assign auth subject id")

        identity = AuthIdentityModel(
            subject_id=subject.id,
            realm=IdentityRealm.ADMIN.value,
            provider=data.provider.value,
            identifier_normalized=normalized,
            credential_hash=stored_hash,
            status=IdentityStatus.ACTIVE.value,
            version_no=1,
        )
        admin = AdminAccountModel(
            subject_id=subject.id,
            realm=IdentityRealm.ADMIN.value,
            legacy_sys_user_id=data.legacy_sys_user_id,
            display_name=data.display_name,
            status=IdentityStatus.ACTIVE.value,
            version_no=1,
        )
        db.add_all([identity, admin])
        await db.flush()
        return ProvisionedAdmin(
            subject=subject,
            identity=identity,
            admin=admin,
        )
