from __future__ import annotations

import hashlib
import json
from collections.abc import Collection

from .enums import LegacyCandidateDisposition
from .schema import (
    LegacyCustomerCandidateSchema,
    LegacyCustomerMigrationPlanSchema,
)


def select_migration_candidates(
    plan: LegacyCustomerMigrationPlanSchema,
    *,
    include_claim_required: bool,
    legacy_user_ids: Collection[int] | None = None,
    limit: int | None = None,
) -> list[LegacyCustomerCandidateSchema]:
    allowed = {
        LegacyCandidateDisposition.ELIGIBLE,
        LegacyCandidateDisposition.ALREADY_MAPPED,
    }
    if include_claim_required:
        allowed.add(LegacyCandidateDisposition.CLAIM_REQUIRED)

    selected_ids = set(legacy_user_ids or ())
    candidates = [
        candidate
        for candidate in sorted(
            plan.candidates,
            key=lambda item: item.legacy_sys_user_id,
        )
        if candidate.disposition in allowed and (not selected_ids or candidate.legacy_sys_user_id in selected_ids)
    ]
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        candidates = candidates[:limit]
    return candidates


def migration_selection_digest(
    candidates: Collection[LegacyCustomerCandidateSchema],
) -> str:
    payload = [
        candidate.model_dump(mode="json")
        for candidate in sorted(
            candidates,
            key=lambda item: item.legacy_sys_user_id,
        )
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
