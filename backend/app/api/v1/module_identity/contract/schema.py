from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CustomerContractReadinessCheck(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    count: int = Field(ge=0)
    sample_ids: list[int] = Field(default_factory=list)
    message: str = Field(min_length=1, max_length=500)


class CustomerContractReadinessReport(BaseModel):
    ready: bool
    generated_at: datetime
    summary: dict[str, int]
    checks: list[CustomerContractReadinessCheck]

    @property
    def blocking_codes(self) -> list[str]:
        return [item.code for item in self.checks if item.count > 0]
