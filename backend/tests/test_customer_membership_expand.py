from pathlib import Path

import pytest
from sqlalchemy import UniqueConstraint

from app.api.v1.module_identity.legacy.enums import LegacyCandidateDisposition
from app.api.v1.module_identity.legacy.model import LegacyCustomerMapModel
from app.api.v1.module_identity.legacy.service import classify_legacy_candidate
from app.api.v1.module_membership.subscription.model import MemberSubscriptionModel


def _foreign_key_targets(model) -> set[str]:
    return {element.target_fullname for constraint in model.__table__.foreign_key_constraints for element in constraint.elements}


def test_membership_expand_keeps_legacy_owner_and_adds_nullable_customer() -> None:
    columns = MemberSubscriptionModel.__table__.columns
    assert "user_id" in columns
    assert "customer_id" in columns
    assert columns["user_id"].nullable is False
    assert columns["customer_id"].nullable is True
    assert "sys_user.id" in _foreign_key_targets(MemberSubscriptionModel)
    assert "cw_customer.id" in _foreign_key_targets(MemberSubscriptionModel)


def test_customer_membership_window_index_is_declared() -> None:
    index_columns = {index.name: tuple(column.name for column in index.columns) for index in MemberSubscriptionModel.__table__.indexes}
    assert index_columns["ix_cw_member_subscription_customer_window"] == (
        "customer_id",
        "status",
        "starts_at",
        "expires_at",
        "id",
    )


def test_legacy_map_is_one_to_one_and_contains_no_credentials() -> None:
    unique_columns = {tuple(column.name for column in constraint.columns) for constraint in LegacyCustomerMapModel.__table__.constraints if isinstance(constraint, UniqueConstraint)}
    assert ("legacy_sys_user_id",) in unique_columns
    assert ("customer_id",) in unique_columns
    assert "credential_hash" not in LegacyCustomerMapModel.__table__.columns
    assert "password" not in LegacyCustomerMapModel.__table__.columns
    assert _foreign_key_targets(LegacyCustomerMapModel) == {
        "sys_user.id",
        "cw_customer.id",
    }


@pytest.mark.parametrize(
    ("kwargs", "expected", "expected_reasons"),
    [
        (
            {},
            LegacyCandidateDisposition.ELIGIBLE,
            (),
        ),
        (
            {"already_mapped": True},
            LegacyCandidateDisposition.ALREADY_MAPPED,
            (),
        ),
        (
            {"identifier_conflict": True},
            LegacyCandidateDisposition.IDENTIFIER_CONFLICT,
            ("customer_identifier_conflict",),
        ),
        (
            {"is_superuser": True, "has_roles": True},
            LegacyCandidateDisposition.CLAIM_REQUIRED,
            ("superuser", "role_assigned"),
        ),
        (
            {"user_disabled": True, "invalid_identifier": True},
            LegacyCandidateDisposition.CLAIM_REQUIRED,
            ("legacy_user_disabled", "invalid_identifier"),
        ),
    ],
)
def test_legacy_candidate_classification_is_safe_by_default(
    kwargs: dict[str, bool],
    expected: LegacyCandidateDisposition,
    expected_reasons: tuple[str, ...],
) -> None:
    defaults = {
        "already_mapped": False,
        "identifier_conflict": False,
        "is_superuser": False,
        "has_department": False,
        "has_roles": False,
        "has_positions": False,
        "user_disabled": False,
        "invalid_identifier": False,
    }
    disposition, reasons = classify_legacy_candidate(**(defaults | kwargs))
    assert disposition == expected
    assert reasons == expected_reasons


def test_expand_migration_is_additive_reversible_and_data_neutral() -> None:
    migration = Path("app/alembic/versions/20260903_01_customer_membership_expand.py").read_text(encoding="utf-8")

    assert 'revision: str = "20260903_01"' in migration
    assert 'down_revision: str | None = "20260902_01"' in migration
    assert '"cw_customer_legacy_map"' in migration
    assert 'op.add_column(\n        "cw_member_subscription"' in migration
    assert '"customer_id"' in migration
    assert 'op.drop_column("cw_member_subscription", "customer_id")' in migration
    assert 'op.drop_table("cw_customer_legacy_map")' in migration

    upgrade_body, downgrade_body = migration.split(
        "\ndef downgrade() -> None:",
        maxsplit=1,
    )
    assert 'drop_column("cw_member_subscription", "user_id")' not in upgrade_body
    assert 'alter_column("cw_member_subscription", "user_id"' not in upgrade_body
    assert "UPDATE CW_MEMBER_SUBSCRIPTION" not in migration.upper()
    assert "INSERT INTO CW_CUSTOMER" not in migration.upper()

    drop_fk = downgrade_body.index("fk_cw_member_subscription_customer")
    drop_index = downgrade_body.index("ix_cw_member_subscription_customer_window")
    drop_column = downgrade_body.index('drop_column("cw_member_subscription", "customer_id")')
    assert drop_fk < drop_index < drop_column
