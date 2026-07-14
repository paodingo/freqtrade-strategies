#!/usr/bin/env python3
"""Shared deterministic helpers for the Stage 4A Research Director control plane."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_control import load_simple_yaml


DIRECTOR_SCHEMA_VERSION = 5

DISCOVERY_TABLE_CONTRACTS: dict[str, dict[str, Any]] = {
    "research_discovery_runs": {
        "columns": (
            ("run_id", "TEXT", 0, None, 1),
            ("trigger_fingerprint", "TEXT", 1, None, 0),
            ("status", "TEXT", 1, None, 0),
            ("state_fingerprint", "TEXT", 1, None, 0),
            ("payload_json", "TEXT", 1, None, 0),
            ("created_at", "TEXT", 1, None, 0),
        ),
        "unique": frozenset({("run_id",), ("trigger_fingerprint",)}),
    },
    "research_discovery_ideas": {
        "columns": (
            ("idea_key", "TEXT", 0, None, 1),
            ("run_id", "TEXT", 1, None, 0),
            ("idea_id", "TEXT", 1, None, 0),
            ("idea_version", "INTEGER", 1, None, 0),
            ("semantic_fingerprint", "TEXT", 1, None, 0),
            ("strategy_family", "TEXT", 1, None, 0),
            ("status", "TEXT", 1, None, 0),
            ("payload_json", "TEXT", 1, None, 0),
            ("created_at", "TEXT", 1, None, 0),
        ),
        "unique": frozenset({("idea_key",), ("semantic_fingerprint",)}),
    },
    "research_discovery_critiques": {
        "columns": (
            ("critique_id", "TEXT", 0, None, 1),
            ("run_id", "TEXT", 1, None, 0),
            ("idea_key", "TEXT", 1, None, 0),
            ("verdict", "TEXT", 1, None, 0),
            ("critic_fingerprint", "TEXT", 1, None, 0),
            ("payload_json", "TEXT", 1, None, 0),
            ("created_at", "TEXT", 1, None, 0),
        ),
        "unique": frozenset({("critique_id",), ("critic_fingerprint",)}),
    },
    "research_discovery_shortlists": {
        "columns": (
            ("run_id", "TEXT", 0, None, 1),
            ("shortlist_fingerprint", "TEXT", 1, None, 0),
            ("recommendation", "TEXT", 1, None, 0),
            ("payload_json", "TEXT", 1, None, 0),
            ("created_at", "TEXT", 1, None, 0),
        ),
        "unique": frozenset({("run_id",), ("shortlist_fingerprint",)}),
    },
    "research_discovery_approvals": {
        "columns": (
            ("approval_fingerprint", "TEXT", 0, None, 1),
            ("run_id", "TEXT", 1, None, 0),
            ("decision", "TEXT", 1, None, 0),
            ("selected_idea_id", "TEXT", 0, None, 0),
            ("payload_json", "TEXT", 1, None, 0),
            ("decided_at", "TEXT", 1, None, 0),
        ),
        "unique": frozenset({("approval_fingerprint",)}),
    },
    "research_discovery_handoffs": {
        "columns": (
            ("handoff_fingerprint", "TEXT", 0, None, 1),
            ("run_id", "TEXT", 1, None, 0),
            ("idea_id", "TEXT", 1, None, 0),
            ("status", "TEXT", 1, None, 0),
            ("director_result_code", "TEXT", 0, None, 0),
            ("payload_json", "TEXT", 1, None, 0),
            ("created_at", "TEXT", 1, None, 0),
        ),
        "unique": frozenset({("handoff_fingerprint",)}),
    },
    "research_discovery_events": {
        "columns": (
            ("event_id", "TEXT", 0, None, 1),
            ("run_id", "TEXT", 1, None, 0),
            ("event_type", "TEXT", 1, None, 0),
            ("reason_code", "TEXT", 0, None, 0),
            ("payload_json", "TEXT", 1, None, 0),
            ("created_at", "TEXT", 1, None, 0),
        ),
        "unique": frozenset({("event_id",)}),
    },
}


class DirectorSchemaMismatchError(RuntimeError):
    def __init__(self, table: str, category: str, expected: Any, actual: Any):
        self.table = table
        self.category = category
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"research discovery schema mismatch: table={table} category={category} "
            f"expected={expected!r} actual={actual!r}"
        )


def discovery_table_ddl(table: str, contract: dict[str, Any]) -> str:
    unique_columns = contract["unique"]
    definitions: list[str] = []
    for name, declared_type, not_null, default, primary_key in contract["columns"]:
        parts = [name, declared_type]
        if not_null:
            parts.append("NOT NULL")
        if default is not None:
            parts.append(f"DEFAULT {default}")
        if primary_key:
            parts.append("PRIMARY KEY")
        elif (name,) in unique_columns:
            parts.append("UNIQUE")
        definitions.append(" ".join(parts))
    definitions.extend(
        f"UNIQUE ({', '.join(columns)})"
        for columns in sorted(unique_columns)
        if len(columns) > 1
    )
    body = ",\n          ".join(definitions)
    return f"CREATE TABLE IF NOT EXISTS {table} (\n          {body}\n        )"


def validate_discovery_table_shape(
    connection: sqlite3.Connection,
    table: str,
    contract: dict[str, Any],
) -> None:
    actual_columns = tuple(
        (row[1], (row[2] or "").upper(), row[3], row[4], row[5])
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    )
    expected_columns = contract["columns"]
    column_checks = (
        ("column_names", 0),
        ("declared_type", 1),
        ("not_null", 2),
        ("default", 3),
        ("primary_key", 4),
    )
    for category, position in column_checks:
        expected = tuple(column[position] for column in expected_columns)
        actual = tuple(column[position] for column in actual_columns)
        if actual != expected:
            raise DirectorSchemaMismatchError(table, category, expected, actual)

    actual_unique = {
        tuple(
            row[2]
            for row in connection.execute(f'PRAGMA index_info("{index[1]}")')
        )
        for index in connection.execute(f'PRAGMA index_list("{table}")')
        if index[2] == 1 and index[4] == 0
    }
    expected_unique = set(contract["unique"])
    if actual_unique != expected_unique:
        raise DirectorSchemaMismatchError(
            table,
            "unique_constraints",
            tuple(sorted(expected_unique)),
            tuple(sorted(actual_unique)),
        )


def worktree_preflight(repo: str | Path, expected_branch: str, expected_head: str) -> dict[str, Any]:
    """Return a fail-closed, machine-readable clean-worktree gate result."""
    repo = Path(repo).resolve()

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=repo, text=True, encoding="utf-8"
        ).strip()

    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    staged = [line for line in git("diff", "--cached", "--name-only").splitlines() if line]
    unstaged = [line for line in git("diff", "--name-only").splitlines() if line]
    untracked = [line for line in git("ls-files", "--others", "--exclude-standard").splitlines() if line]
    checks = {
        "branch_matches": branch == expected_branch,
        "head_matches": head == expected_head,
        "staged_changes_zero": not staged,
        "unstaged_tracked_changes_zero": not unstaged,
        "unignored_untracked_files_zero": not untracked,
    }
    return {
        "repo": repo.as_posix(),
        "branch": branch,
        "head": head,
        "expected_branch": expected_branch,
        "expected_head": expected_head,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "checks": checks,
        "passed": all(checks.values()),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def load_document(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig").lstrip()
    if text.startswith("{"):
        payload = json.loads(text)
    else:
        payload = load_simple_yaml(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping")
    return payload


def write_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def yaml_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def dump_yaml(payload: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(dump_yaml(value, indent + 2))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        else:
            lines.append(f"{prefix}{key}: {yaml_scalar(value)}")
    return "\n".join(lines)


def write_yaml(path: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(payload) + "\n", encoding="utf-8")


def normalized_question(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def proposal_fingerprint(proposal: dict[str, Any]) -> str:
    identity = {
        "research_question": normalized_question(str(proposal.get("research_question", ""))),
        "referenced_variables": sorted(proposal.get("referenced_variables") or []),
        "referenced_mechanisms": sorted(proposal.get("referenced_mechanisms") or []),
        "market_scope": proposal.get("market_scope") or {},
        "data_scope": proposal.get("data_scope") or {},
        "proposed_method": proposal.get("proposed_method") or {},
    }
    return fingerprint(identity)


def ensure_director_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS director_schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_state_snapshots (
          snapshot_id TEXT PRIMARY KEY,
          fingerprint TEXT NOT NULL,
          git_head TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS director_runs (
          run_id TEXT PRIMARY KEY,
          state_fingerprint TEXT NOT NULL,
          objective TEXT,
          risk_tolerance TEXT NOT NULL,
          budget_json TEXT NOT NULL,
          recommendation TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS director_proposals (
          proposal_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          semantic_fingerprint TEXT NOT NULL UNIQUE,
          risk_class TEXT NOT NULL,
          information_gain REAL NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS director_rejections (
          rejection_id INTEGER PRIMARY KEY AUTOINCREMENT,
          run_id TEXT NOT NULL,
          proposal_key TEXT NOT NULL,
          reason_code TEXT NOT NULL,
          details_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS approval_routes (
          route_id TEXT PRIMARY KEY,
          proposal_id TEXT NOT NULL,
          decision TEXT NOT NULL,
          rules_json TEXT NOT NULL,
          approval_granted INTEGER NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS compiled_campaigns (
          compilation_id TEXT PRIMARY KEY,
          proposal_id TEXT NOT NULL,
          campaign_id TEXT NOT NULL,
          campaign_fingerprint TEXT NOT NULL UNIQUE,
          compile_mode TEXT NOT NULL,
          execution_authorized INTEGER NOT NULL,
          referenced_hashes_json TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS constitution_approvals (
          constitution_id TEXT NOT NULL,
          approved_version INTEGER NOT NULL,
          constitution_sha256 TEXT NOT NULL UNIQUE,
          approver_type TEXT NOT NULL,
          approved_at TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          PRIMARY KEY (constitution_id, approved_version)
        );
        CREATE TABLE IF NOT EXISTS proposal_selection_events (
          proposal_id TEXT PRIMARY KEY,
          proposal_fingerprint TEXT NOT NULL,
          approval_status TEXT NOT NULL,
          approver_type TEXT NOT NULL,
          approved_at TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS campaign_execution_authorizations (
          authorization_id TEXT PRIMARY KEY,
          campaign_id TEXT NOT NULL,
          approved_compiled_fingerprint TEXT NOT NULL,
          proposal_id TEXT NOT NULL,
          execution_authorized INTEGER NOT NULL,
          payload_json TEXT NOT NULL,
          authorized_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stage4b1_campaign_runs (
          run_id TEXT PRIMARY KEY,
          campaign_id TEXT NOT NULL,
          status TEXT NOT NULL,
          result_code TEXT NOT NULL,
          campaign_executed INTEGER NOT NULL,
          dataset_created INTEGER NOT NULL,
          validation_accesses INTEGER NOT NULL,
          holdout_accesses INTEGER NOT NULL,
          payload_json TEXT NOT NULL,
          completed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stage4b1_readiness_assets (
          asset_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          artifact_type TEXT NOT NULL,
          path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_campaign_runs (
          run_id TEXT PRIMARY KEY,
          campaign_id TEXT NOT NULL,
          proposal_id TEXT NOT NULL,
          status TEXT NOT NULL,
          result_code TEXT NOT NULL,
          campaign_executed INTEGER NOT NULL,
          candidate_created INTEGER NOT NULL,
          strategy_modified INTEGER NOT NULL,
          validation_accesses INTEGER NOT NULL,
          holdout_accesses INTEGER NOT NULL,
          payload_json TEXT NOT NULL,
          completed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_campaign_assets (
          asset_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          artifact_type TEXT NOT NULL,
          path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stage4c1_portfolios (
          portfolio_id TEXT PRIMARY KEY,
          approval_status TEXT NOT NULL,
          max_campaigns INTEGER NOT NULL,
          executed_campaigns INTEGER NOT NULL,
          stop_reason TEXT,
          payload_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stage4c1_portfolio_cycles (
          cycle_id TEXT PRIMARY KEY,
          portfolio_id TEXT NOT NULL,
          cycle_number INTEGER NOT NULL,
          proposal_id TEXT NOT NULL,
          campaign_id TEXT NOT NULL,
          campaign_fingerprint TEXT NOT NULL,
          status TEXT NOT NULL,
          result_code TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          completed_at TEXT NOT NULL
        );
        """
    )
    try:
        connection.execute("BEGIN")
        for table, contract in DISCOVERY_TABLE_CONTRACTS.items():
            connection.execute(discovery_table_ddl(table, contract))
        for table, contract in DISCOVERY_TABLE_CONTRACTS.items():
            validate_discovery_table_shape(connection, table, contract)
        connection.execute(
            "INSERT OR IGNORE INTO director_schema_migrations(version, applied_at) VALUES (?, ?)",
            (DIRECTOR_SCHEMA_VERSION, utc_now()),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def open_director_registry(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        ensure_director_schema(connection)
    except Exception:
        connection.close()
        raise
    return connection


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def registry_summary(path: str | Path | None) -> dict[str, Any]:
    if not path or not Path(path).exists():
        return {"available": False, "integrity": "unavailable", "tables": {}, "evidence": []}
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    counts = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in tables
        if not table.startswith("sqlite_")
    }
    campaigns: list[dict[str, Any]] = []
    if "campaigns" in tables:
        campaigns.extend(dict(row) for row in connection.execute(
            "SELECT campaign_id, mode, status, completion_quality, remaining_experiments, last_stop_reason FROM campaigns ORDER BY campaign_id"
        ))
    for table in ("stage3d1_campaigns", "stage3d2b_campaigns"):
        if table in tables:
            campaigns.extend(dict(row) for row in connection.execute(
                f"SELECT campaign_id, status, final_report_path FROM {table} ORDER BY campaign_id"
            ))
    closures: list[dict[str, Any]] = []
    if "stage3d4b_branch_closure_events" in tables:
        closures.extend(dict(row) for row in connection.execute(
            "SELECT closure_id, research_status, mechanism_decision, engineering_validity, code_change_status, closure_artifact FROM stage3d4b_branch_closure_events"
        ))
    temporal: list[dict[str, Any]] = []
    if "stage3e1_temporal_conclusions" in tables:
        temporal.extend(dict(row) for row in connection.execute(
            "SELECT campaign_id, classification, recommendation, comparison_sha256 FROM stage3e1_temporal_conclusions"
        ))
    invalidations: list[dict[str, Any]] = []
    if "stage3d3b_invalidation_events" in tables:
        invalidations.extend(dict(row) for row in connection.execute(
            "SELECT event_id, original_campaign_id, affected_ids_json, created_at FROM stage3d3b_invalidation_events"
        ))
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    return {
        "available": True,
        "integrity": integrity,
        "tables": counts,
        "campaigns": campaigns,
        "closures": closures,
        "temporal_conclusions": temporal,
        "invalidations": invalidations,
        "evidence": ["Research Registry read-only SQLite queries", "PRAGMA integrity_check"],
    }


def discovery_registry_summary(path: str | Path | None) -> dict[str, Any]:
    if not path or not Path(path).is_file():
        return {"available": False, "completed_runs": 0, "director_rejections": 0, "recent_ideas": []}
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.row_factory = sqlite3.Row
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "research_discovery_runs" not in tables:
            return {"available": True, "completed_runs": 0, "director_rejections": 0, "recent_ideas": []}

        def payload_object(raw: object, table: str) -> dict[str, Any]:
            try:
                payload = json.loads(raw) if isinstance(raw, str) else None
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid {table} payload_json") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"invalid {table} payload_json")
            return payload

        connection.execute(
            "SELECT status FROM research_discovery_runs LIMIT 1"
        ).fetchone()
        rejected = connection.execute("SELECT COUNT(*) FROM research_discovery_handoffs WHERE status='director_rejected'").fetchone()[0]
        duplicate_completed = connection.execute(
            "SELECT run_id FROM research_discovery_events "
            "WHERE event_type='completed' GROUP BY run_id "
            "HAVING COUNT(*) != 1 LIMIT 1"
        ).fetchone()
        if duplicate_completed is not None:
            raise ValueError(
                f"duplicate completed event: {duplicate_completed['run_id']}"
            )
        invalid_completed = connection.execute(
            "SELECT event_id FROM research_discovery_events "
            "WHERE event_type='completed' AND json_valid(payload_json)=0 LIMIT 1"
        ).fetchone()
        if invalid_completed is not None:
            raise ValueError("invalid research_discovery_events payload_json")
        orphan_completed = connection.execute(
            "SELECT events.run_id FROM research_discovery_events AS events "
            "LEFT JOIN research_discovery_runs AS runs ON runs.run_id=events.run_id "
            "WHERE events.event_type='completed' AND runs.run_id IS NULL LIMIT 1"
        ).fetchone()
        if orphan_completed is not None:
            raise ValueError("invalid completed event binding")
        completed = connection.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT run_id FROM research_discovery_runs "
            "WHERE status IN ('completed', 'no_research_recommended') "
            "UNION "
            "SELECT events.run_id FROM research_discovery_events AS events "
            "INNER JOIN research_discovery_runs AS runs ON runs.run_id=events.run_id "
            "WHERE events.event_type='completed'"
            ") AS completed_runs"
        ).fetchone()[0]
        idea_rows = connection.execute(
            "SELECT idea_key, run_id, idea_id, idea_version, strategy_family, "
            "semantic_fingerprint, payload_json FROM research_discovery_ideas "
            "ORDER BY created_at DESC, idea_key LIMIT 20"
        ).fetchall()
        if not idea_rows:
            return {
                "available": True,
                "completed_runs": completed,
                "director_rejections": rejected,
                "recent_ideas": [],
            }

        run_ids = sorted({str(row["run_id"]) for row in idea_rows})
        idea_keys = sorted({str(row["idea_key"]) for row in idea_rows})
        ideas_by_key = {str(row["idea_key"]): row for row in idea_rows}
        for row in idea_rows:
            payload_object(row["payload_json"], "research_discovery_ideas")
        run_marks = ",".join("?" for _ in run_ids)
        idea_marks = ",".join("?" for _ in idea_keys)

        latest_critiques: dict[str, sqlite3.Row] = {}
        for row in connection.execute(
            "SELECT critique_id, run_id, idea_key, verdict, critic_fingerprint, "
            "payload_json, created_at "
            "FROM research_discovery_critiques "
            f"WHERE run_id IN ({run_marks}) AND idea_key IN ({idea_marks}) "
            "ORDER BY created_at, critique_id",
            (*run_ids, *idea_keys),
        ):
            payload = payload_object(row["payload_json"], "research_discovery_critiques")
            idea = ideas_by_key.get(str(row["idea_key"]))
            if (
                idea is None
                or row["run_id"] != idea["run_id"]
                or payload.get("verdict") != row["verdict"]
                or payload.get("idea_semantic_fingerprint")
                != idea["semantic_fingerprint"]
            ):
                raise ValueError("invalid research_discovery_critiques payload binding")
            latest_critiques[str(row["idea_key"])] = row

        ranked_by_run: dict[
            str, set[tuple[str, str, str, int | None, str | None]]
        ] = {}
        shortlist_fingerprints: dict[str, str] = {}
        shortlist_rows = connection.execute(
            "SELECT run_id, shortlist_fingerprint, payload_json "
            "FROM research_discovery_shortlists "
            f"WHERE run_id IN ({run_marks})",
            run_ids,
        ).fetchall()
        for row in shortlist_rows:
            payload = payload_object(row["payload_json"], "research_discovery_shortlists")
            if payload.get("shortlist_fingerprint") != row["shortlist_fingerprint"]:
                raise ValueError("invalid research_discovery_shortlists payload binding")
            ranked = payload.get("ranked_ideas")
            if not isinstance(ranked, list):
                raise ValueError("invalid research_discovery_shortlists ranked_ideas")
            ranked_bindings: set[tuple[str, str, str, int | None, str | None]] = set()
            for item in ranked:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("idea_id"), str)
                    or not isinstance(item.get("idea_fingerprint"), str)
                    or not isinstance(item.get("critique_fingerprint"), str)
                ):
                    raise ValueError("invalid research_discovery_shortlists ranked_ideas")
                item_version = item.get("idea_version")
                item_ref = item.get("idea_ref")
                if (
                    item_version is not None
                    and (type(item_version) is not int or item_version < 1)
                ) or (item_ref is not None and not isinstance(item_ref, str)):
                    raise ValueError("invalid research_discovery_shortlists ranked_ideas")
                ranked_bindings.add(
                    (
                        item["idea_id"],
                        item["idea_fingerprint"],
                        item["critique_fingerprint"],
                        item_version,
                        item_ref,
                    )
                )
            shortlist_run_id = str(row["run_id"])
            ranked_by_run[shortlist_run_id] = ranked_bindings
            shortlist_fingerprints[shortlist_run_id] = str(
                row["shortlist_fingerprint"]
            )

        approvals_by_run: dict[str, tuple[sqlite3.Row, dict[str, Any]]] = {}
        for row in connection.execute(
            "SELECT approval_fingerprint, run_id, decision, selected_idea_id, "
            "payload_json, decided_at "
            "FROM research_discovery_approvals "
            f"WHERE run_id IN ({run_marks}) ORDER BY decided_at",
            run_ids,
        ):
            payload = payload_object(row["payload_json"], "research_discovery_approvals")
            if (
                payload.get("decision", row["decision"]) != row["decision"]
                or payload.get("selected_idea_id", row["selected_idea_id"])
                != row["selected_idea_id"]
                or payload.get("approval_fingerprint")
                != row["approval_fingerprint"]
                or str(row["run_id"]) in approvals_by_run
            ):
                raise ValueError("invalid research_discovery_approvals payload binding")
            approvals_by_run[str(row["run_id"])] = (row, payload)

        handoffs_by_run: dict[str, tuple[sqlite3.Row, dict[str, Any]]] = {}
        for row in connection.execute(
            "SELECT handoff_fingerprint, run_id, idea_id, status, "
            "director_result_code, payload_json, created_at "
            "FROM research_discovery_handoffs "
            f"WHERE run_id IN ({run_marks}) ORDER BY created_at",
            run_ids,
        ):
            payload = payload_object(row["payload_json"], "research_discovery_handoffs")
            run_id = str(row["run_id"])
            idea_ref = payload.get("idea_ref")
            if (
                run_id in handoffs_by_run
                or payload.get("discovery_run_id") != run_id
                or payload.get("handoff_fingerprint")
                != row["handoff_fingerprint"]
                or not isinstance(idea_ref, str)
                or Path(idea_ref).stem.rsplit("-v", 1)[0] != row["idea_id"]
                or not isinstance(payload.get("idea_fingerprint"), str)
            ):
                raise ValueError("invalid research_discovery_handoffs run binding")
            handoffs_by_run[run_id] = (row, payload)

        ideas: list[dict[str, Any]] = []
        for row in idea_rows:
            run_id = str(row["run_id"])
            idea_id = str(row["idea_id"])
            status = "discovered"
            critique = latest_critiques.get(str(row["idea_key"]))
            if critique is not None:
                status = (
                    "critic_rejected"
                    if critique["verdict"] == "reject"
                    else "criticized"
                )
            critique_fingerprint = (
                str(critique["critic_fingerprint"]) if critique is not None else ""
            )
            expected_idea_ref = (
                f"research/discovery/runs/{run_id}/ideas/"
                f"{idea_id}-v{row['idea_version']}.json"
            )
            ranked = any(
                ranked_id == idea_id
                and ranked_fingerprint == row["semantic_fingerprint"]
                and ranked_critique == critique_fingerprint
                and (ranked_version is None or ranked_version == row["idea_version"])
                and (ranked_ref is None or ranked_ref == expected_idea_ref)
                for (
                    ranked_id,
                    ranked_fingerprint,
                    ranked_critique,
                    ranked_version,
                    ranked_ref,
                ) in ranked_by_run.get(run_id, set())
            )
            approval_binding = approvals_by_run.get(run_id)
            approval_chain_valid = False
            if ranked:
                status = "shortlisted"
                if approval_binding is not None:
                    approval, approval_payload = approval_binding
                    approval_chain_valid = (
                        approval_payload.get("shortlist_fingerprint")
                        == shortlist_fingerprints.get(run_id)
                    )
                    if (
                        approval_chain_valid
                        and approval["decision"] in {"rejected", "deferred"}
                        and approval["selected_idea_id"] is None
                        and approval_payload.get("selected_idea_fingerprint") is None
                        and approval_payload.get("selected_critique_fingerprint") is None
                    ):
                        status = str(approval["decision"])
                    elif (
                        approval_chain_valid
                        and
                        approval["decision"] == "approved_for_director_handoff"
                        and approval["selected_idea_id"] == idea_id
                        and approval_payload.get("selected_idea_fingerprint")
                        == row["semantic_fingerprint"]
                        and approval_payload.get("selected_critique_fingerprint")
                        == critique_fingerprint
                    ):
                        status = "human_approved"
            handoff_binding = handoffs_by_run.get(run_id)
            if handoff_binding is not None:
                handoff, handoff_payload = handoff_binding
            else:
                handoff, handoff_payload = None, None
            if (
                handoff is not None
                and handoff_payload is not None
                and status == "human_approved"
                and approval_chain_valid
                and approval_binding is not None
                and handoff["idea_id"] == idea_id
                and handoff_payload.get("idea_ref") == expected_idea_ref
                and handoff_payload.get("idea_fingerprint")
                == row["semantic_fingerprint"]
                and handoff_payload.get("critique_fingerprint")
                == critique_fingerprint
                and handoff_payload.get("approval_fingerprint")
                == approval_binding[0]["approval_fingerprint"]
                and handoff_payload.get("shortlist_fingerprint")
                == shortlist_fingerprints.get(run_id)
            ):
                status = {
                    "handed_to_director": "handed_to_director",
                    "director_proposed": "converted",
                    "director_rejected": "director_rejected",
                }.get(str(handoff["status"]), status)
            ideas.append(
                {
                    "idea_id": row["idea_id"],
                    "idea_version": row["idea_version"],
                    "strategy_family": row["strategy_family"],
                    "status": status,
                    "semantic_fingerprint": row["semantic_fingerprint"],
                }
            )
        return {"available": True, "completed_runs": completed, "director_rejections": rejected, "recent_ideas": ideas}
    finally:
        connection.close()


def director_registry_export(path: str | Path) -> dict[str, Any]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    result: dict[str, Any] = {}
    for table in (
        "research_state_snapshots", "director_runs", "director_proposals",
        "director_rejections", "approval_routes", "compiled_campaigns",
        "research_discovery_runs", "research_discovery_ideas",
        "research_discovery_critiques", "research_discovery_shortlists",
        "research_discovery_approvals", "research_discovery_handoffs",
        "research_discovery_events",
    ):
        if table_exists(connection, table):
            result[table] = [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
    connection.close()
    return result
