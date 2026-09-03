from pydantic import BaseModel, Field

from .enums import LegacyCandidateDisposition


class LegacyCustomerCandidateSchema(BaseModel):
    legacy_sys_user_id: int = Field(gt=0)
    username: str = Field(min_length=1, max_length=64)
    normalized_identifier: str = Field(min_length=1, max_length=191)
    subscription_count: int = Field(ge=1)
    disposition: LegacyCandidateDisposition
    reasons: list[str] = Field(default_factory=list)


class LegacyCustomerMigrationPlanSchema(BaseModel):
    total: int = Field(ge=0)
    eligible: int = Field(ge=0)
    claim_required: int = Field(ge=0)
    already_mapped: int = Field(ge=0)
    identifier_conflict: int = Field(ge=0)
    candidates: list[LegacyCustomerCandidateSchema] = Field(default_factory=list)
