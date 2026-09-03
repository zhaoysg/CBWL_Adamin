from .enums import (
    LegacyCandidateDisposition,
    LegacyCredentialState,
    LegacyMigrationSource,
)
from .migrator import (
    LegacyCustomerMigrationConflict,
    LegacyCustomerMigrationError,
    LegacyCustomerMigrationExecutor,
)
from .model import LegacyCustomerMapModel
from .plan import migration_selection_digest, select_migration_candidates
from .schema import (
    LegacyCustomerCandidateSchema,
    LegacyCustomerMigrationPlanSchema,
    LegacyCustomerMigrationResultSchema,
)
from .service import (
    LegacyCustomerMigrationPlanner,
    classify_legacy_candidate,
    is_usable_credential_hash,
    legacy_identifier_fallback,
)

__all__ = [
    "LegacyCandidateDisposition",
    "LegacyCredentialState",
    "LegacyMigrationSource",
    "LegacyCustomerMigrationConflict",
    "LegacyCustomerMigrationError",
    "LegacyCustomerMigrationExecutor",
    "LegacyCustomerMapModel",
    "LegacyCustomerCandidateSchema",
    "LegacyCustomerMigrationPlanSchema",
    "LegacyCustomerMigrationResultSchema",
    "LegacyCustomerMigrationPlanner",
    "classify_legacy_candidate",
    "is_usable_credential_hash",
    "legacy_identifier_fallback",
    "migration_selection_digest",
    "select_migration_candidates",
]
