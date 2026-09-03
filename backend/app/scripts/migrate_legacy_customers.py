from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.api.v1.module_identity.legacy.migrator import (
    LegacyCustomerMigrationConflict,
    LegacyCustomerMigrationError,
    LegacyCustomerMigrationExecutor,
)
from app.api.v1.module_identity.legacy.plan import (
    migration_selection_digest,
    select_migration_candidates,
)
from app.api.v1.module_identity.legacy.service import (
    LegacyCustomerMigrationPlanner,
)
from app.core.database import async_db_session


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply the legacy sys_user to cw_customer membership "
            "migration. The default mode is read-only."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply selected migrations. Without this flag no data is changed.",
    )
    parser.add_argument(
        "--plan-digest",
        help=(
            "Required with --apply. Must match the digest printed by a "
            "fresh dry run using the same selection flags."
        ),
    )
    parser.add_argument(
        "--include-claim-required",
        action="store_true",
        help=(
            "Also create customer ownership records for candidates that "
            "must claim new credentials. No password identity is copied."
        ),
    )
    parser.add_argument(
        "--legacy-user-id",
        type=int,
        action="append",
        dest="legacy_user_ids",
        help="Limit the operation to one legacy user ID. Repeatable.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many selected users, ordered by legacy ID.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help=(
            "Write a private JSON audit report. Required for --apply; "
            "created with owner-only permissions."
        ),
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


async def _build_selection(args: argparse.Namespace):
    async with async_db_session() as db:
        plan = await LegacyCustomerMigrationPlanner.plan_membership_candidates(
            db
        )
    candidates = select_migration_candidates(
        plan,
        include_claim_required=args.include_claim_required,
        legacy_user_ids=args.legacy_user_ids,
        limit=args.limit,
    )
    digest = migration_selection_digest(candidates)
    return plan, candidates, digest


async def _apply(args: argparse.Namespace) -> int:
    plan, candidates, digest = await _build_selection(args)
    if not args.plan_digest:
        raise SystemExit("--plan-digest is required with --apply")
    if args.report_json is None:
        raise SystemExit("--report-json is required with --apply")
    if not candidates:
        raise SystemExit("no migration candidates were selected")
    if not secrets.compare_digest(args.plan_digest, digest):
        raise SystemExit(
            "migration plan changed; run a new dry run and use its digest"
        )

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            async with async_db_session() as db:
                async with db.begin():
                    result = (
                        await LegacyCustomerMigrationExecutor.migrate_one(
                            db,
                            candidate.legacy_sys_user_id,
                        )
                    )
            results.append(result.model_dump(mode="json"))
        except (
            IntegrityError,
            LegacyCustomerMigrationConflict,
            LegacyCustomerMigrationError,
        ) as exc:
            failures.append(
                {
                    "legacy_sys_user_id": candidate.legacy_sys_user_id,
                    "error_type": type(exc).__name__,
                }
            )

    report = {
        "mode": "apply",
        "plan_digest": digest,
        "selection": {
            "selected": len(candidates),
            "include_claim_required": args.include_claim_required,
            "legacy_user_ids": sorted(args.legacy_user_ids or []),
            "limit": args.limit,
        },
        "plan_counts": {
            "total": plan.total,
            "eligible": plan.eligible,
            "claim_required": plan.claim_required,
            "already_mapped": plan.already_mapped,
            "identifier_conflict": plan.identifier_conflict,
        },
        "results": results,
        "failures": failures,
    }
    _write_private_json(args.report_json, report)
    print(
        json.dumps(
            {
                "mode": "apply",
                "plan_digest": digest,
                "selected": len(candidates),
                "succeeded": len(results),
                "failed": len(failures),
                "report_json": str(args.report_json),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 1 if failures else 0


async def _dry_run(args: argparse.Namespace) -> int:
    plan, candidates, digest = await _build_selection(args)
    report = {
        "mode": "dry-run",
        "plan_digest": digest,
        "selection": {
            "selected": len(candidates),
            "include_claim_required": args.include_claim_required,
            "legacy_user_ids": sorted(args.legacy_user_ids or []),
            "limit": args.limit,
        },
        "plan": plan.model_dump(mode="json"),
    }
    if args.report_json is not None:
        _write_private_json(args.report_json, report)

    print(
        json.dumps(
            {
                "mode": "dry-run",
                "plan_digest": digest,
                "selected": len(candidates),
                "eligible": plan.eligible,
                "claim_required": plan.claim_required,
                "already_mapped": plan.already_mapped,
                "identifier_conflict": plan.identifier_conflict,
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
    return 0


async def _run(args: argparse.Namespace) -> int:
    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be positive")
    if args.legacy_user_ids and any(
        user_id <= 0 for user_id in args.legacy_user_ids
    ):
        raise SystemExit("--legacy-user-id must be positive")
    if not args.apply and args.plan_digest:
        raise SystemExit("--plan-digest is only valid with --apply")
    return await (_apply(args) if args.apply else _dry_run(args))


def main() -> int:
    args = _parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
