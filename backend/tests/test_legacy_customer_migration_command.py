from pathlib import Path

import pytest

from app.api.v1.module_identity.legacy.enums import (
    LegacyCandidateDisposition,
)
from app.api.v1.module_identity.legacy.plan import (
    migration_selection_digest,
    select_migration_candidates,
)
from app.api.v1.module_identity.legacy.schema import (
    LegacyCustomerCandidateSchema,
    LegacyCustomerMigrationPlanSchema,
)
from app.api.v1.module_identity.legacy.service import (
    classify_legacy_candidate,
    is_usable_credential_hash,
    legacy_identifier_fallback,
)


def _candidate(
    legacy_user_id: int,
    disposition: LegacyCandidateDisposition,
    *,
    reasons: list[str] | None = None,
) -> LegacyCustomerCandidateSchema:
    return LegacyCustomerCandidateSchema(
        legacy_sys_user_id=legacy_user_id,
        username=f"legacy_{legacy_user_id}",
        normalized_identifier=f"legacy_{legacy_user_id}",
        subscription_count=1,
        disposition=disposition,
        reasons=reasons or [],
    )


def _plan() -> LegacyCustomerMigrationPlanSchema:
    candidates = [
        _candidate(4, LegacyCandidateDisposition.IDENTIFIER_CONFLICT),
        _candidate(2, LegacyCandidateDisposition.CLAIM_REQUIRED),
        _candidate(3, LegacyCandidateDisposition.ALREADY_MAPPED),
        _candidate(1, LegacyCandidateDisposition.ELIGIBLE),
    ]
    return LegacyCustomerMigrationPlanSchema(
        total=4,
        eligible=1,
        claim_required=1,
        already_mapped=1,
        identifier_conflict=1,
        candidates=candidates,
    )


def test_default_selection_excludes_claim_and_conflict() -> None:
    selected = select_migration_candidates(
        _plan(),
        include_claim_required=False,
    )
    assert [item.legacy_sys_user_id for item in selected] == [1, 3]


def test_explicit_claim_selection_still_excludes_identifier_conflict() -> None:
    selected = select_migration_candidates(
        _plan(),
        include_claim_required=True,
    )
    assert [item.legacy_sys_user_id for item in selected] == [1, 2, 3]


def test_selection_filter_and_limit_are_deterministic() -> None:
    selected = select_migration_candidates(
        _plan(),
        include_claim_required=True,
        legacy_user_ids={2, 3, 4},
        limit=1,
    )
    assert [item.legacy_sys_user_id for item in selected] == [2]

    with pytest.raises(ValueError, match="limit must be positive"):
        select_migration_candidates(
            _plan(),
            include_claim_required=True,
            limit=0,
        )


def test_plan_digest_is_order_independent_but_content_sensitive() -> None:
    first = _candidate(1, LegacyCandidateDisposition.ELIGIBLE)
    second = _candidate(2, LegacyCandidateDisposition.CLAIM_REQUIRED)
    digest = migration_selection_digest([second, first])
    assert digest == migration_selection_digest([first, second])

    changed = second.model_copy(update={"reasons": ["credential_reset_required"]})
    assert digest != migration_selection_digest([first, changed])


def test_credential_hash_requires_a_real_legacy_hash_shape() -> None:
    assert is_usable_credential_hash(None) is False
    assert is_usable_credential_hash("") is False
    assert is_usable_credential_hash("!") is False
    assert is_usable_credential_hash("short") is False
    assert is_usable_credential_hash("$argon2id$legacy-long-hash-value") is True


def test_missing_credential_hash_requires_claim() -> None:
    disposition, reasons = classify_legacy_candidate(
        already_mapped=False,
        identifier_conflict=False,
        is_superuser=False,
        has_department=False,
        has_roles=False,
        has_positions=False,
        user_disabled=False,
        invalid_identifier=False,
        credential_hash_usable=False,
    )
    assert disposition is LegacyCandidateDisposition.CLAIM_REQUIRED
    assert reasons == ("credential_reset_required",)


def test_invalid_identifier_fallback_contains_no_legacy_identifier() -> None:
    assert legacy_identifier_fallback(42) == "legacy-sys-user:42"


def test_migration_executor_keeps_transaction_ownership_with_caller() -> None:
    migrator = Path("app/api/v1/module_identity/legacy/migrator.py").read_text(encoding="utf-8")
    repository = Path("app/api/v1/module_identity/legacy/repository.py").read_text(encoding="utf-8")

    assert ".commit(" not in migrator
    assert ".rollback(" not in migrator
    assert ".commit(" not in repository
    assert ".rollback(" not in repository
    assert repository.count(".with_for_update()") >= 6


def test_command_is_dry_run_by_default_and_guards_apply() -> None:
    command = Path("app/scripts/migrate_legacy_customers.py").read_text(encoding="utf-8")

    assert '"--apply"' in command
    assert '"--plan-digest"' in command
    assert '"--report-json"' in command
    assert "secrets.compare_digest" in command
    assert "O_NOFOLLOW" in command
    assert "async with db.begin()" in command
    assert "no migration candidates were selected" in command
