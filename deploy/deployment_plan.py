#!/usr/bin/env python3
"""Plan database refresh work for a safe, low-downtime deployment."""
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "force"}
FALSE_VALUES = {"0", "false", "no", "skip", "none"}


@dataclass(frozen=True)
class DeploymentPlan:
    rebuild_from_excel: bool
    rebuild_aggregates: bool
    new_required_migrations: tuple[str, ...]
    reason: str


def _normalize_mode(value: str, *, allow_excel_aliases: bool = False) -> str:
    normalized = value.strip().lower()
    if normalized in {"", "auto"}:
        return "auto"
    if normalized in TRUE_VALUES or (allow_excel_aliases and normalized == "excel"):
        return "force"
    if normalized in FALSE_VALUES or (allow_excel_aliases and normalized == "raw"):
        return "skip"
    raise ValueError(f"unsupported mode: {value}")


def required_migrations(database: str | Path) -> tuple[str, ...]:
    path = Path(database)
    if not path.is_file():
        return ()
    try:
        with sqlite3.connect(path) as conn:
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if not table:
                return ()
            rows = conn.execute(
                "SELECT version FROM schema_migrations "
                "WHERE requires_aggregate_rebuild = 1 ORDER BY version"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise RuntimeError(f"cannot inspect schema migrations: {type(exc).__name__}") from exc
    return tuple(str(row[0]) for row in rows)


def build_plan(
    *,
    database_existed: bool,
    excel_count: int,
    rebuild_database: str,
    rebuild_aggregates: str,
    required_before: tuple[str, ...] = (),
    required_after: tuple[str, ...] = (),
) -> DeploymentPlan:
    database_mode = _normalize_mode(rebuild_database, allow_excel_aliases=True)
    aggregate_mode = _normalize_mode(rebuild_aggregates)
    if excel_count < 0:
        raise ValueError("excel_count must be non-negative")

    rebuild_from_excel = database_mode == "force" or (
        database_mode == "auto" and not database_existed and excel_count >= 3
    )
    if rebuild_from_excel and excel_count < 3:
        raise ValueError("Excel rebuild requires at least three source files")
    if rebuild_from_excel:
        return DeploymentPlan(True, False, (), "Excel全量重建已显式启用")

    before = set(required_before)
    after = set(required_after)
    new_required = tuple(sorted(after - before))

    if not database_existed:
        return DeploymentPlan(False, False, new_required, "首次空库且无完整Excel源，跳过聚合重建")
    if aggregate_mode == "force":
        return DeploymentPlan(False, True, new_required, "REBUILD_AGGREGATES要求强制重建")
    if new_required:
        suffix = "（覆盖跳过设置）" if aggregate_mode == "skip" else ""
        return DeploymentPlan(
            False,
            True,
            new_required,
            f"检测到需要重建聚合的新迁移{suffix}",
        )
    if aggregate_mode == "skip":
        return DeploymentPlan(False, False, (), "REBUILD_AGGREGATES明确跳过且无强制迁移")
    return DeploymentPlan(False, False, (), "既有库未出现需要重建聚合的新迁移")


def _load_snapshot(path: str | Path) -> tuple[str, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError("migration snapshot must be a JSON string list")
    return tuple(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--database", required=True)

    plan = subparsers.add_parser("plan")
    plan.add_argument("--database", required=True)
    plan.add_argument("--snapshot", required=True)
    plan.add_argument("--database-existed", choices=("0", "1"), required=True)
    plan.add_argument("--excel-count", type=int, required=True)
    plan.add_argument("--rebuild-database", default="auto")
    plan.add_argument("--rebuild-aggregates", default="auto")
    plan.add_argument("--format", choices=("json", "lines"), default="json")
    args = parser.parse_args()

    if args.command == "snapshot":
        try:
            migrations = required_migrations(args.database)
        except RuntimeError as exc:
            parser.error(str(exc))
        print(json.dumps(migrations, ensure_ascii=False))
        return

    try:
        result = build_plan(
            database_existed=args.database_existed == "1",
            excel_count=args.excel_count,
            rebuild_database=args.rebuild_database,
            rebuild_aggregates=args.rebuild_aggregates,
            required_before=_load_snapshot(args.snapshot),
            required_after=required_migrations(args.database),
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.format == "lines":
        print("1" if result.rebuild_from_excel else "0")
        print("1" if result.rebuild_aggregates else "0")
        print(",".join(result.new_required_migrations) or "-")
        print(result.reason)
    else:
        print(json.dumps(asdict(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
