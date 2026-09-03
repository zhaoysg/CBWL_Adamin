from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from app.api.v1.module_identity.enums import IdentityProvider
from app.api.v1.module_identity.model import (
    AdminAccountModel,
    AuthIdentityModel,
    AuthSubjectModel,
    CustomerModel,
)
from app.api.v1.module_identity.normalization import (
    InvalidIdentityIdentifier,
    normalize_identifier,
)
from app.api.v1.module_identity.schema import CustomerProvisionSchema
from app.api.v1.module_identity.service import IdentityProvisionError, IdentityService
from app.core.base_model import UserMixin


def _foreign_key_targets(model) -> set[str]:
    return {element.target_fullname for constraint in model.__table__.foreign_key_constraints for element in constraint.elements}


def test_identity_identifier_normalization() -> None:
    assert normalize_identifier(IdentityProvider.PASSWORD, "  Demo_User  ") == "demo_user"
    assert normalize_identifier(IdentityProvider.EMAIL_OTP, "Ａlice@Example.COM") == "alice@example.com"
    assert normalize_identifier(IdentityProvider.MOBILE_OTP, "+86 138-0013-8000") == "+8613800138000"
    assert normalize_identifier(IdentityProvider.WECHAT, " WxOpenIdAbC ") == "WxOpenIdAbC"


@pytest.mark.parametrize("value", ["", "   ", "bad\x00value", "x" * 192])
def test_invalid_identity_identifier_is_rejected(value: str) -> None:
    with pytest.raises(InvalidIdentityIdentifier):
        normalize_identifier(IdentityProvider.PASSWORD, value)


def test_mobile_identity_requires_e164() -> None:
    with pytest.raises(InvalidIdentityIdentifier, match="E.164"):
        normalize_identifier(IdentityProvider.MOBILE_OTP, "13800138000")


def test_customer_schema_rejects_blank_nickname() -> None:
    with pytest.raises(ValidationError):
        CustomerProvisionSchema(
            provider=IdentityProvider.PASSWORD,
            identifier="customer-1",
            nickname="   ",
        )


def test_customer_is_not_an_internal_user() -> None:
    assert UserMixin not in CustomerModel.__mro__
    assert "user_id" not in CustomerModel.__table__.columns
    assert "sys_user.id" not in _foreign_key_targets(CustomerModel)


def test_admin_bridge_is_the_only_identity_table_linked_to_sys_user() -> None:
    assert "sys_user.id" in _foreign_key_targets(AdminAccountModel)
    assert "sys_user.id" not in _foreign_key_targets(AuthSubjectModel)
    assert "sys_user.id" not in _foreign_key_targets(AuthIdentityModel)
    assert "sys_user.id" not in _foreign_key_targets(CustomerModel)


def test_identity_uniqueness_is_scoped_by_realm_and_provider() -> None:
    unique_columns = {tuple(column.name for column in constraint.columns) for constraint in AuthIdentityModel.__table__.constraints if isinstance(constraint, UniqueConstraint)}
    assert ("realm", "provider", "identifier_normalized") in unique_columns


def test_identity_models_match_model_mixin_columns() -> None:
    required = {
        "id",
        "uuid",
        "is_deleted",
        "created_time",
        "updated_time",
        "deleted_time",
    }
    for model in (
        AuthSubjectModel,
        AuthIdentityModel,
        AdminAccountModel,
        CustomerModel,
    ):
        assert required <= set(model.__table__.columns.keys())


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flush_count = 0
        self.commit_called = False

    def add(self, item) -> None:
        self.added.append(item)

    def add_all(self, items) -> None:
        self.added.extend(items)

    async def flush(self) -> None:
        self.flush_count += 1
        if self.flush_count == 1:
            self.added[0].id = 101

    async def commit(self) -> None:
        self.commit_called = True


@pytest.mark.asyncio
async def test_customer_provisioning_is_one_aggregate_without_commit() -> None:
    session = FakeSession()
    result = await IdentityService.create_customer(
        session,
        CustomerProvisionSchema(
            provider=IdentityProvider.PASSWORD,
            identifier="New.Customer",
            nickname=" 新客户 ",
        ),
        credential_hash="$argon2id$v=19$test-only-long-hash-value",
    )

    assert result.subject.id == 101
    assert result.customer.subject_id == 101
    assert result.identity.subject_id == 101
    assert result.identity.identifier_normalized == "new.customer"
    assert result.customer.nickname == "新客户"
    assert result.customer.customer_no.startswith("C")
    assert session.flush_count == 2
    assert session.commit_called is False


@pytest.mark.asyncio
async def test_non_password_identity_rejects_password_hash() -> None:
    with pytest.raises(IdentityProvisionError, match="cannot store"):
        await IdentityService.create_customer(
            FakeSession(),
            CustomerProvisionSchema(
                provider=IdentityProvider.WECHAT,
                identifier="openid-1",
                nickname="微信客户",
            ),
            credential_hash="$argon2id$should-not-be-here",
        )


def test_identity_migration_is_additive_reversible_and_model_aligned() -> None:
    migration = Path("app/alembic/versions/20260902_01_identity_boundary.py").read_text(encoding="utf-8")

    assert 'revision: str = "20260902_01"' in migration
    assert 'down_revision: str | None = "20260823_01"' in migration
    for table in ("auth_subject", "auth_identity", "sys_admin_account", "cw_customer"):
        assert f'op.create_table(\n        "{table}"' in migration
        assert f'op.drop_table("{table}")' in migration
    for column in (
        "uuid",
        "is_deleted",
        "created_time",
        "updated_time",
        "deleted_time",
    ):
        assert f'"{column}"' in migration

    assert 'sa.Column("created_id"' not in migration
    assert 'sa.Column("updated_id"' not in migration
    assert "ck_auth_identity_credential_shape" in migration
    assert "ck_cw_customer_register_source" in migration
    assert "alter_column" not in migration
    assert "drop_column" not in migration
    assert "cw_member_subscription" not in migration
    assert "cw_order" not in migration
