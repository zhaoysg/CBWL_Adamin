from enum import StrEnum


class LegacyCredentialState(StrEnum):
    MIGRATED = "migrated"
    CLAIM_REQUIRED = "claim_required"


class LegacyMigrationSource(StrEnum):
    MEMBERSHIP = "membership"
    MANUAL = "manual"


class LegacyCandidateDisposition(StrEnum):
    ELIGIBLE = "eligible"
    CLAIM_REQUIRED = "claim_required"
    ALREADY_MAPPED = "already_mapped"
    IDENTIFIER_CONFLICT = "identifier_conflict"
