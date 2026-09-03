from pathlib import Path

import pytest

from app.api.v1.module_identity.contract.schema import (
    CustomerContractReadinessCheck,
    CustomerContractReadinessReport,
)
from app.api.v1.module_identity.contract.service import (
    CustomerContractReadinessService,
)


def test_readiness_report_exposes_only_blocking_codes() -> None:
    report = CustomerContractReadinessReport(
        ready=False,
        generated_at="2026-09-03T00:00:00Z",
        summary={"subscriptions": 2},
        checks=[
            CustomerContractReadinessCheck(
                code="ok-check",
                count=0,
                sample_ids=[],
                message="ok",
            ),
            CustomerContractReadinessCheck(
                code="blocking-check",
                count=2,
                sample_ids=[10, 20],
                message="blocked",
            ),
        ],
    )
    assert report.blocking_codes == ["blocking-check"]


@pytest.mark.asyncio
async def test_readiness_service_rejects_unbounded_samples() -> None:
    with pytest.raises(ValueError, match="between 1 and 100"):
        await CustomerContractReadinessService.build_report(
            None,  # type: ignore[arg-type]
            sample_limit=0,
        )
    with pytest.raises(ValueError, match="between 1 and 100"):
        await CustomerContractReadinessService.build_report(
            None,  # type: ignore[arg-type]
            sample_limit=101,
        )


def test_readiness_command_is_read_only_and_fail_closed() -> None:
    command = Path("app/scripts/check_customer_contract_readiness.py").read_text(encoding="utf-8")
    service = Path("app/api/v1/module_identity/contract/service.py").read_text(encoding="utf-8")

    assert '"--require-ready"' in command
    assert '"--report-json"' in command
    assert "O_NOFOLLOW" in command
    assert "return 2" in command
    assert ".commit(" not in command
    assert ".rollback(" not in command
    assert ".commit(" not in service
    assert ".rollback(" not in service
    assert "update(" not in service
    assert "delete(" not in service
