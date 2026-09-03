from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from app.api.v1.module_identity.contract import (
    CustomerContractReadinessService,
)
from app.core.database import async_db_session


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether customer identity and membership ownership are "
            "safe to enter the Contract migration phase."
        )
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit with status 2 when any blocking check is non-zero.",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=50,
        help="Maximum numeric IDs included per private report check (1-100).",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="Write the detailed numeric-ID report with owner-only permissions.",
    )
    return parser


def _write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                payload,
                stream,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            stream.write("\n")
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


async def _run(args: argparse.Namespace) -> int:
    if args.sample_limit <= 0 or args.sample_limit > 100:
        raise SystemExit("--sample-limit must be between 1 and 100")

    async with async_db_session() as db:
        report = await CustomerContractReadinessService.build_report(
            db,
            sample_limit=args.sample_limit,
        )

    if args.report_json is not None:
        _write_private_json(
            args.report_json,
            report.model_dump(mode="json"),
        )

    print(
        json.dumps(
            {
                "ready": report.ready,
                "blocking_codes": report.blocking_codes,
                "summary": report.summary,
                "report_json": (
                    str(args.report_json)
                    if args.report_json is not None
                    else None
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.require_ready and not report.ready:
        return 2
    return 0


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
