from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import ua_parser
from fastapi import Request, status
from redis.asyncio.client import Redis
from sqlalchemy import and_, select
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
from app.api.v1.module_system.user.model import UserModel
from app.common.enums import RET, RedisInitKeyConfig
from app.config.setting import settings
from app.core.base_schema import JWTOutSchema, JWTPayloadSchema
from app.core.exceptions import CustomException
from app.core.redis_crud import RedisCURD
from app.core.security import create_access_token
from app.utils.ip_local_util import get_client_ip
from app.utils.password_util import PwdUtil

from .auth_schema import PortalAuthUser

CustomerLoginOutcome = Literal[
    "customer",
    "legacy_fallback",
    "claim_required",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class PortalCustomerAccount:
    identity_id: int
    subject_id: int
    customer_id: int
    legacy_user_id: int
    username: str
    name: str
    avatar: str | None


@dataclass(frozen=True, slots=True)
class CustomerLoginResolution:
    outcome: CustomerLoginOutcome
    account: PortalCustomerAccount | None = None


class PortalCustomerAuthService:
    """Customer-realm authentication used during the dual-read migration."""

    @classmethod
    async def resolve_login(
        cls,
        db: AsyncSession,
        *,
        username: str,
        password: str,
    ) -> CustomerLoginResolution:
        normalized = username.strip().casefold()
        customer_row = (
            await db.execute(
                select(
                    AuthIdentityModel,
                    AuthSubjectModel,
                    CustomerModel,
                    LegacyCustomerMapModel,
                    UserModel,
                )
                .join(
                    AuthSubjectModel,
                    and_(
                        AuthSubjectModel.id == AuthIdentityModel.subject_id,
                        AuthSubjectModel.realm == AuthIdentityModel.realm,
                    ),
                )
                .join(
                    CustomerModel,
                    and_(
                        CustomerModel.subject_id == AuthSubjectModel.id,
                        CustomerModel.realm == AuthSubjectModel.realm,
                    ),
                )
                .outerjoin(
                    LegacyCustomerMapModel,
                    and_(
                        LegacyCustomerMapModel.customer_id == CustomerModel.id,
                        LegacyCustomerMapModel.is_deleted.is_(False),
                    ),
                )
                .outerjoin(
                    UserModel,
                    and_(
                        UserModel.id == LegacyCustomerMapModel.legacy_sys_user_id,
                        UserModel.is_deleted.is_(False),
                    ),
                )
                .where(
                    AuthIdentityModel.realm == IdentityRealm.CUSTOMER,
                    AuthIdentityModel.provider == IdentityProvider.PASSWORD,
                    AuthIdentityModel.identifier_normalized == normalized,
                )
            )
        ).first()
        if customer_row is not None:
            identity, subject, customer, mapping, legacy_user = customer_row
            active = (
                not identity.is_deleted
                and identity.status == IdentityStatus.ACTIVE
                and not subject.is_deleted
                and subject.status == IdentityStatus.ACTIVE
                and not customer.is_deleted
                and customer.status == IdentityStatus.ACTIVE
                and mapping is not None
                and mapping.credential_state == LegacyCredentialState.MIGRATED
                and legacy_user is not None
                and legacy_user.status == 0
                and not legacy_user.is_superuser
            )
            if not active or not identity.credential_hash:
                return CustomerLoginResolution(outcome="blocked")
            if not PwdUtil.verify_password(
                plain_password=password,
                password_hash=identity.credential_hash,
            ):
                return CustomerLoginResolution(outcome="blocked")

            identity.last_login_at = datetime.now(UTC)
            return CustomerLoginResolution(
                outcome="customer",
                account=PortalCustomerAccount(
                    identity_id=identity.id,
                    subject_id=subject.id,
                    customer_id=customer.id,
                    legacy_user_id=legacy_user.id,
                    username=identity.identifier_normalized,
                    name=customer.nickname,
                    avatar=customer.avatar_url,
                ),
            )

        legacy_row = (
            await db.execute(
                select(UserModel, LegacyCustomerMapModel)
                .join(
                    LegacyCustomerMapModel,
                    and_(
                        LegacyCustomerMapModel.legacy_sys_user_id == UserModel.id,
                        LegacyCustomerMapModel.is_deleted.is_(False),
                    ),
                )
                .where(
                    UserModel.username == username,
                    UserModel.is_deleted.is_(False),
                )
            )
        ).first()
        if legacy_row is None:
            return CustomerLoginResolution(outcome="legacy_fallback")

        legacy_user, mapping = legacy_row
        if not PwdUtil.verify_password(
            plain_password=password,
            password_hash=legacy_user.password,
        ):
            return CustomerLoginResolution(outcome="blocked")
        if mapping.credential_state == LegacyCredentialState.CLAIM_REQUIRED:
            return CustomerLoginResolution(outcome="claim_required")
        return CustomerLoginResolution(outcome="blocked")

    @classmethod
    async def create_token(
        cls,
        *,
        request: Request,
        redis: Redis,
        account: PortalCustomerAccount,
    ) -> JWTOutSchema:
        session_id = str(uuid.uuid4())
        access_expires = timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_SECONDS)
        refresh_expires = timedelta(seconds=settings.REFRESH_TOKEN_EXPIRE_SECONDS)
        now = datetime.now(UTC)
        ua_result = ua_parser.parse(request.headers.get("user-agent") or "")
        session = {
            "session_id": session_id,
            "actor_type": "customer",
            "identity_source": "customer",
            "identity_id": account.identity_id,
            "subject_id": account.subject_id,
            "customer_id": account.customer_id,
            "legacy_user_id": account.legacy_user_id,
            "user_id": account.legacy_user_id,
            "is_superuser": False,
            "user_status": 0,
            "name": account.name,
            "user_name": account.username,
            "dept_id": None,
            "mobile": None,
            "email": None,
            "gender": None,
            "avatar": account.avatar,
            "permissions": [],
            "menu_ids": [],
            "ipaddr": get_client_ip(request),
            "login_location": None,
            "os": (ua_result.os.family if ua_result.os else "Unknown"),
            "browser": (ua_result.user_agent.family if ua_result.user_agent else "Unknown"),
            "login_time": now.isoformat(),
            "login_type": "H5",
        }
        redis_crud = RedisCURD(redis)
        await redis_crud.set(
            key=f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}",
            value=json.dumps(session, ensure_ascii=False),
            expire=int(refresh_expires.total_seconds()),
        )

        access_token = create_access_token(
            payload=JWTPayloadSchema(
                sub=session_id,
                is_refresh=False,
                exp=now + access_expires,
            )
        )
        refresh_token = create_access_token(
            payload=JWTPayloadSchema(
                sub=session_id,
                is_refresh=True,
                exp=now + refresh_expires,
            )
        )
        await redis_crud.set(
            key=f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}",
            value=access_token,
            expire=int(access_expires.total_seconds()),
        )
        await redis_crud.set(
            key=f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{session_id}",
            value=refresh_token,
            expire=int(refresh_expires.total_seconds()),
        )
        return JWTOutSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=settings.TOKEN_TYPE,
            expires_in=int(access_expires.total_seconds()),
        )

    @staticmethod
    async def validate_session(
        db: AsyncSession,
        session: dict[str, Any],
    ) -> None:
        try:
            identity_id = int(session["identity_id"])
            subject_id = int(session["subject_id"])
            customer_id = int(session["customer_id"])
            legacy_user_id = int(session["legacy_user_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CustomException(
                msg="客户会话已失效",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc
        if int(session.get("user_id") or 0) != legacy_user_id:
            raise CustomException(
                msg="客户会话已失效",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        valid = await db.scalar(
            select(CustomerModel.id)
            .join(
                AuthSubjectModel,
                and_(
                    AuthSubjectModel.id == CustomerModel.subject_id,
                    AuthSubjectModel.realm == CustomerModel.realm,
                ),
            )
            .join(
                AuthIdentityModel,
                and_(
                    AuthIdentityModel.id == identity_id,
                    AuthIdentityModel.subject_id == AuthSubjectModel.id,
                    AuthIdentityModel.realm == AuthSubjectModel.realm,
                ),
            )
            .join(
                LegacyCustomerMapModel,
                and_(
                    LegacyCustomerMapModel.customer_id == CustomerModel.id,
                    LegacyCustomerMapModel.legacy_sys_user_id == legacy_user_id,
                    LegacyCustomerMapModel.is_deleted.is_(False),
                ),
            )
            .join(
                UserModel,
                and_(
                    UserModel.id == legacy_user_id,
                    UserModel.is_deleted.is_(False),
                ),
            )
            .where(
                CustomerModel.id == customer_id,
                CustomerModel.subject_id == subject_id,
                CustomerModel.realm == IdentityRealm.CUSTOMER,
                CustomerModel.status == IdentityStatus.ACTIVE,
                CustomerModel.is_deleted.is_(False),
                AuthSubjectModel.status == IdentityStatus.ACTIVE,
                AuthSubjectModel.is_deleted.is_(False),
                AuthIdentityModel.provider == IdentityProvider.PASSWORD,
                AuthIdentityModel.status == IdentityStatus.ACTIVE,
                AuthIdentityModel.is_deleted.is_(False),
                LegacyCustomerMapModel.credential_state == LegacyCredentialState.MIGRATED,
                UserModel.status == 0,
                UserModel.is_superuser.is_(False),
            )
        )
        if valid is None:
            raise CustomException(
                msg="客户会话已失效",
                code=RET.UNAUTHORIZED.code,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

    @staticmethod
    def user_from_session(session: dict[str, Any]) -> PortalAuthUser:
        return PortalAuthUser(
            id=int(session.get("customer_id") or 0),
            username=str(session.get("user_name") or ""),
            name=session.get("name"),
            avatar=session.get("avatar"),
            identity_source="customer",
            customer_id=int(session.get("customer_id") or 0),
            subject_id=int(session.get("subject_id") or 0),
            legacy_user_id=int(session.get("legacy_user_id") or 0),
        )
