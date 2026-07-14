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
        CREATE TABLE IF NOT EXISTS research_discovery_runs (
          run_id TEXT PRIMARY KEY,
          trigger_fingerprint TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL,
          state_fingerprint TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_discovery_ideas (
          idea_key TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          idea_id TEXT NOT NULL,
          idea_version INTEGER NOT NULL,
          semantic_fingerprint TEXT NOT NULL UNIQUE,
          strategy_family TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_discovery_critiques (
          critique_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          idea_key TEXT NOT NULL,
          verdict TEXT NOT NULL,
          critic_fingerprint TEXT NOT NULL UNIQUE,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_discovery_shortlists (
          run_id TEXT PRIMARY KEY,
          shortlist_fingerprint TEXT NOT NULL UNIQUE,
          recommendation TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_discovery_approvals (
          approval_fingerprint TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          decision TEXT NOT NULL,
          selected_idea_id TEXT,
          payload_json TEXT NOT NULL,
          decided_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_discovery_handoffs (
          handoff_fingerprint TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          idea_id TEXT NOT NULL,
          status TEXT NOT NULL,
          director_result_code TEXT,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS research_discovery_events (
          event_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          reason_code TEXT,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT OR IGNORE INTO director_schema_migrations(version, applied_at) VALUES (?, ?)",
        (DIRECTOR_SCHEMA_VERSION, utc_now()),
    )


def open_director_registry(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    ensure_director_schema(connection)
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
    connection.row_factory = sqlite3.Row
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "research_discovery_runs" not in tables:
        connection.close()
        return {"available": True, "completed_runs": 0, "director_rejections": 0, "recent_ideas": []}
    completed = connection.execute("SELECT COUNT(*) FROM research_discovery_runs WHERE status IN ('completed', 'no_research_recommended')").fetchone()[0]
    rejected = connection.execute("SELECT COUNT(*) FROM research_discovery_handoffs WHERE status='director_rejected'").fetchone()[0]
    ideas = [dict(row) for row in connection.execute("SELECT idea_id, idea_version, strategy_family, status, semantic_fingerprint FROM research_discovery_ideas ORDER BY created_at DESC, idea_key LIMIT 20")]
    connection.close()
    return {"available": True, "completed_runs": completed, "director_rejections": rejected, "recent_ideas": ideas}


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
