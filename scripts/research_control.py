#!/usr/bin/env python3
"""Deterministic SQLite research campaign control plane."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_guard import PathGuardError, check_paths, validate_campaign_paths


DB_SCHEMA_VERSION = 1
EXPERIMENT_STATES = (
    "queued",
    "claimed",
    "preparing",
    "running",
    "validating",
    "recorded",
    "accepted",
    "rejected",
    "escalated",
    "failed",
)
CAMPAIGN_STATES = (
    "draft",
    "active",
    "pausing",
    "paused",
    "completed",
    "stopped",
    "failed",
    "escalated",
)
EXPERIMENT_TRANSITIONS = {
    "queued": {"claimed"},
    "claimed": {"preparing", "queued", "escalated", "failed"},
    "preparing": {"running", "failed", "escalated"},
    "running": {"validating", "failed", "escalated"},
    "validating": {"recorded", "failed", "escalated"},
    "recorded": {"accepted", "rejected", "escalated"},
    "failed": {"queued"},
    "accepted": set(),
    "rejected": set(),
    "escalated": set(),
}
CAMPAIGN_TRANSITIONS = {
    "draft": {"active", "stopped"},
    "active": {"pausing", "completed", "stopped", "failed", "escalated"},
    "pausing": {"paused", "stopped", "failed", "escalated"},
    "paused": {"active", "stopped"},
    "completed": set(),
    "stopped": set(),
    "failed": set(),
    "escalated": set(),
}
FAILURE_TAXONOMY = {
    "infra_transient": {
        "consumes_attempt": True,
        "retryable": True,
        "counts_consecutive_candidate_failure": False,
    },
    "infra_permanent": {
        "consumes_attempt": True,
        "retryable": False,
        "counts_consecutive_candidate_failure": False,
    },
    "implementation_error": {
        "consumes_attempt": True,
        "retryable": False,
        "counts_consecutive_candidate_failure": False,
    },
    "validation_error": {
        "consumes_attempt": True,
        "retryable": False,
        "counts_consecutive_candidate_failure": False,
    },
    "backtest_error": {
        "consumes_attempt": True,
        "retryable": False,
        "counts_consecutive_candidate_failure": False,
    },
    "output_parse_error": {
        "consumes_attempt": True,
        "retryable": False,
        "counts_consecutive_candidate_failure": False,
    },
    "candidate_rejected": {
        "consumes_attempt": True,
        "retryable": False,
        "counts_consecutive_candidate_failure": True,
    },
    "guard_violation": {
        "consumes_attempt": True,
        "retryable": False,
        "counts_consecutive_candidate_failure": False,
    },
    "budget_stop": {
        "consumes_attempt": False,
        "retryable": False,
        "counts_consecutive_candidate_failure": False,
    },
    "operator_stop": {
        "consumes_attempt": False,
        "retryable": False,
        "counts_consecutive_candidate_failure": False,
    },
}
FAILURE_ALIASES = {
    "lease_expired": "infra_transient",
    "transient": "infra_transient",
    "timeout": "infra_transient",
    "non_retryable": "implementation_error",
    "runtime_python_missing": "infra_permanent",
    "freqtrade_module_missing": "infra_permanent",
    "freqtrade_version_mismatch": "infra_permanent",
    "dataset_missing": "infra_permanent",
    "dataset_manifest_missing": "infra_permanent",
    "dataset_hash_mismatch": "infra_permanent",
    "environment_not_ready": "infra_permanent",
}
TERMINAL_EXPERIMENT_STATES = {"accepted", "rejected", "escalated", "failed"}
DB_RELATIVE_PATH = Path("research") / "registry" / "research.db"
AUDIT_JSONL = Path("research") / "registry" / "audit_events.jsonl"


class CampaignError(RuntimeError):
    pass


class SimulatedCrash(RuntimeError):
    pass


def normalize_failure_type(failure_type: str | None) -> str | None:
    if failure_type is None:
        return None
    return FAILURE_ALIASES.get(failure_type, failure_type)


def failure_policy(failure_type: str | None) -> dict:
    normalized = normalize_failure_type(failure_type)
    if normalized not in FAILURE_TAXONOMY:
        return FAILURE_TAXONOMY["implementation_error"]
    return FAILURE_TAXONOMY[normalized]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value in ("null", "None", "~"):
        return None
    if (value.startswith("[") and value.endswith("]")) or (value.startswith("{") and value.endswith("}")):
        return json.loads(value)
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def load_simple_yaml(path: str | Path) -> dict:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for lineno, raw_line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw_line.split(" #", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if ":" not in line:
            raise ValueError(f"{path}:{lineno}: unsupported YAML line")
        key, value = line.strip().split(":", 1)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"{path}:{lineno}: invalid indentation")
        parent = stack[-1][1]
        if value.strip() == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(value)
    return root


def load_campaign(path: str | Path) -> dict:
    path = Path(path)
    text = path.read_text(encoding="utf-8").lstrip()
    if text.startswith("{"):
        config = json.loads(text)
    else:
        try:
            import yaml  # type: ignore

            config = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        except Exception:
            config = load_simple_yaml(path)
    if not isinstance(config, dict):
        raise ValueError("campaign config must be a mapping")
    validate_campaign_config(config)
    return config


def validate_campaign_config(config: dict) -> None:
    required = [
        "campaign_id",
        "mode",
        "scope",
        "budget",
        "autonomy",
        "stop_conditions",
        "escalation_conditions",
    ]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"campaign config missing keys: {', '.join(missing)}")
    if config["mode"] not in {"dry_run", "fixed_backtest", "sealed_offline_backtest", "candidate_identity_equivalence", "single_variable_semantic_mutation", "research_data_plane", "bounded_autonomous_search"}:
        raise ValueError("campaign mode must be dry_run, fixed_backtest, sealed_offline_backtest, candidate_identity_equivalence, single_variable_semantic_mutation, research_data_plane, or bounded_autonomous_search")
    validate_campaign_paths(config)
    budget = config.get("budget") or {}
    for key in (
        "max_experiments",
        "max_total_attempts",
        "max_consecutive_failures",
        "max_retries_per_experiment",
        "max_wall_clock_minutes",
    ):
        if int(budget.get(key, -1)) < 0:
            raise ValueError(f"budget.{key} must be a non-negative integer")
    autonomy = config.get("autonomy") or {}
    fixed = {
        "automatically_claim_next": True,
        "automatically_generate_hypotheses": False,
        "automatically_promote_champion": False,
        "access_sealed_holdout": False,
    }
    for key, expected in fixed.items():
        if autonomy.get(key) is not expected:
            raise ValueError(f"autonomy.{key} must be {expected!r} in dry-run control-plane phase")


def default_db_path(repo_root: str | Path) -> Path:
    return Path(repo_root) / DB_RELATIVE_PATH


class ResearchStore:
    def __init__(self, repo_root: str | Path, db_path: str | Path | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.db_path = Path(db_path) if db_path else default_db_path(self.repo_root)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.executescript(
            """
            BEGIN;
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY,
              applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS campaigns (
              campaign_id TEXT PRIMARY KEY,
              config_path TEXT NOT NULL,
              mode TEXT NOT NULL,
              status TEXT NOT NULL,
              config_json TEXT NOT NULL,
              owner TEXT,
              started_at TEXT,
              completed_at TEXT,
              updated_at TEXT NOT NULL,
              consecutive_failures INTEGER NOT NULL DEFAULT 0,
              last_stop_reason TEXT,
              last_escalation_reason TEXT,
              completion_quality TEXT,
              remaining_experiments INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS hypotheses (
              hypothesis_id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id TEXT NOT NULL,
              fingerprint TEXT NOT NULL,
              title TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id),
              UNIQUE(campaign_id, fingerprint)
            );
            CREATE TABLE IF NOT EXISTS experiments (
              experiment_id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id TEXT NOT NULL,
              hypothesis_id INTEGER NOT NULL,
              fingerprint TEXT NOT NULL,
              status TEXT NOT NULL,
              priority INTEGER NOT NULL DEFAULT 100,
              retry_count INTEGER NOT NULL DEFAULT 0,
              max_retries INTEGER NOT NULL DEFAULT 0,
              failure_type TEXT,
              result TEXT,
              lease_owner TEXT,
              lease_expires_at TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id),
              FOREIGN KEY(hypothesis_id) REFERENCES hypotheses(hypothesis_id),
              UNIQUE(campaign_id, fingerprint)
            );
            CREATE TABLE IF NOT EXISTS experiment_attempts (
              attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
              experiment_id INTEGER NOT NULL,
              campaign_id TEXT NOT NULL,
              owner TEXT NOT NULL,
              attempt_no INTEGER NOT NULL,
              status TEXT NOT NULL,
              failure_type TEXT,
              started_at TEXT NOT NULL,
              completed_at TEXT,
              simulated_action TEXT,
              charged INTEGER NOT NULL DEFAULT 0,
              artifact_path TEXT,
              FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id),
              FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id),
              UNIQUE(experiment_id, attempt_no)
            );
            CREATE TABLE IF NOT EXISTS budget_events (
              budget_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id TEXT NOT NULL,
              experiment_id INTEGER,
              attempt_id INTEGER,
              event_type TEXT NOT NULL,
              amount INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              details_json TEXT NOT NULL DEFAULT '{}',
              idempotency_key TEXT NOT NULL UNIQUE,
              FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
              artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id TEXT NOT NULL,
              experiment_id INTEGER NOT NULL,
              attempt_id INTEGER,
              artifact_type TEXT NOT NULL,
              path TEXT NOT NULL,
              created_at TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id),
              FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id)
            );
            CREATE TABLE IF NOT EXISTS locks (
              lock_name TEXT PRIMARY KEY,
              owner TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
              audit_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
              campaign_id TEXT,
              experiment_id INTEGER,
              event_type TEXT NOT NULL,
              severity TEXT NOT NULL,
              message TEXT NOT NULL,
              created_at TEXT NOT NULL,
              details_json TEXT NOT NULL DEFAULT '{}'
            );
            INSERT OR IGNORE INTO schema_migrations(version, applied_at)
              VALUES (1, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
            COMMIT;
            """
        )
        self._ensure_column("campaigns", "completion_quality", "TEXT")
        self._ensure_column("campaigns", "remaining_experiments", "INTEGER NOT NULL DEFAULT 0")

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def begin(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        self.conn.execute("COMMIT")

    def rollback(self) -> None:
        self.conn.execute("ROLLBACK")

    def audit(
        self,
        event_type: str,
        message: str,
        campaign_id: str | None = None,
        experiment_id: int | None = None,
        severity: str = "info",
        details: dict | None = None,
    ) -> None:
        created_at = utc_now()
        payload = json.dumps(details or {}, sort_keys=True)
        self.conn.execute(
            """
            INSERT INTO audit_events(campaign_id, experiment_id, event_type, severity, message, created_at, details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (campaign_id, experiment_id, event_type, severity, message, created_at, payload),
        )
        audit_path = self.repo_root / AUDIT_JSONL
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "campaign_id": campaign_id,
                        "experiment_id": experiment_id,
                        "event_type": event_type,
                        "severity": severity,
                        "message": message,
                        "created_at": created_at,
                        "details": details or {},
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    def upsert_campaign(self, config: dict, config_path: str | Path, owner: str | None = None) -> None:
        now = utc_now()
        campaign_id = config["campaign_id"]
        config_json = json.dumps(config, sort_keys=True)
        existing = self.conn.execute(
            "SELECT status FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
        if existing:
            self.conn.execute(
                """
                UPDATE campaigns
                SET config_path = ?, mode = ?, config_json = ?, owner = COALESCE(owner, ?), updated_at = ?
                WHERE campaign_id = ?
                """,
                (str(config_path), config["mode"], config_json, owner, now, campaign_id),
            )
            return
        self.conn.execute(
            """
            INSERT INTO campaigns(campaign_id, config_path, mode, status, config_json, owner, started_at, updated_at)
            VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            (campaign_id, str(config_path), config["mode"], config_json, owner, now, now),
        )
        self.transition_campaign(campaign_id, "active", reason="campaign initialized")

    def campaign(self, campaign_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)).fetchone()
        if not row:
            raise CampaignError(f"campaign not found: {campaign_id}")
        return row

    def transition_campaign(
        self,
        campaign_id: str,
        new_status: str,
        reason: str,
        completion_quality: str | None = None,
        remaining_experiments: int | None = None,
    ) -> None:
        row = self.campaign(campaign_id)
        old_status = row["status"]
        if new_status not in CAMPAIGN_TRANSITIONS.get(old_status, set()):
            self.audit(
                "illegal_campaign_transition",
                f"illegal campaign transition {old_status}->{new_status}",
                campaign_id=campaign_id,
                severity="error",
                details={"from": old_status, "to": new_status, "reason": reason},
            )
            raise CampaignError(f"illegal campaign transition {old_status}->{new_status}")
        now = utc_now()
        completed_at = now if new_status in {"completed", "stopped", "failed", "escalated"} else row["completed_at"]
        self.conn.execute(
            """
            UPDATE campaigns
            SET status = ?, completed_at = ?, updated_at = ?, last_stop_reason = ?,
                completion_quality = COALESCE(?, completion_quality),
                remaining_experiments = COALESCE(?, remaining_experiments)
            WHERE campaign_id = ?
            """,
            (new_status, completed_at, now, reason, completion_quality, remaining_experiments, campaign_id),
        )
        self.audit(
            "campaign_transition",
            f"campaign {old_status}->{new_status}: {reason}",
            campaign_id=campaign_id,
            details={"from": old_status, "to": new_status},
        )

    def transition_experiment(self, experiment_id: int, new_status: str, reason: str) -> None:
        row = self.conn.execute("SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)).fetchone()
        if not row:
            raise CampaignError(f"experiment not found: {experiment_id}")
        old_status = row["status"]
        if new_status not in EXPERIMENT_TRANSITIONS.get(old_status, set()):
            self.audit(
                "illegal_experiment_transition",
                f"illegal experiment transition {old_status}->{new_status}",
                campaign_id=row["campaign_id"],
                experiment_id=experiment_id,
                severity="error",
                details={"from": old_status, "to": new_status, "reason": reason},
            )
            raise CampaignError(f"illegal experiment transition {old_status}->{new_status}")
        self.conn.execute(
            "UPDATE experiments SET status = ?, updated_at = ? WHERE experiment_id = ?",
            (new_status, utc_now(), experiment_id),
        )
        self.audit(
            "experiment_transition",
            f"experiment {old_status}->{new_status}: {reason}",
            campaign_id=row["campaign_id"],
            experiment_id=experiment_id,
            details={"from": old_status, "to": new_status},
        )

    def add_hypothesis(self, campaign_id: str, fingerprint: str, title: str, payload: dict, priority: int = 100) -> int | None:
        now = utc_now()
        try:
            cur = self.conn.execute(
                """
                INSERT INTO hypotheses(campaign_id, fingerprint, title, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (campaign_id, fingerprint, title, json.dumps(payload, sort_keys=True), now),
            )
        except sqlite3.IntegrityError:
            self.audit(
                "duplicate_hypothesis_rejected",
                f"duplicate hypothesis rejected: {fingerprint}",
                campaign_id=campaign_id,
                severity="warning",
                details={"fingerprint": fingerprint},
            )
            return None
        hypothesis_id = int(cur.lastrowid)
        budget = json.loads(self.campaign(campaign_id)["config_json"]).get("budget") or {}
        max_retries = int(payload.get("max_retries", budget.get("max_retries_per_experiment", 0)))
        self.conn.execute(
            """
            INSERT INTO experiments(campaign_id, hypothesis_id, fingerprint, status, priority, max_retries, created_at, updated_at)
            VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
            """,
            (campaign_id, hypothesis_id, fingerprint, priority, max_retries, now, now),
        )
        self.audit(
            "hypothesis_queued",
            f"queued hypothesis {fingerprint}",
            campaign_id=campaign_id,
            details={"hypothesis_id": hypothesis_id, "priority": priority},
        )
        return hypothesis_id

    def reclaim_expired_leases(self, campaign_id: str) -> int:
        now = utc_now()
        rows = self.conn.execute(
            """
            SELECT experiment_id, lease_owner, lease_expires_at
            FROM experiments
            WHERE campaign_id = ?
              AND status IN ('claimed', 'preparing', 'running', 'validating')
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= ?
            """,
            (campaign_id, now),
        ).fetchall()
        for row in rows:
            attempt = self.conn.execute(
                """
                SELECT attempt_id FROM experiment_attempts
                WHERE experiment_id = ? AND completed_at IS NULL
                ORDER BY attempt_id DESC
                LIMIT 1
                """,
                (row["experiment_id"],),
            ).fetchone()
            if attempt:
                self.complete_attempt(
                    int(attempt["attempt_id"]),
                    "failed",
                    "lease_expired_before_runner_completion",
                    failure_type="lease_expired",
                )
            self.transition_experiment(row["experiment_id"], "failed", "expired lease reclaimed")
            if self.can_retry_experiment(row["experiment_id"], "lease_expired"):
                self.transition_experiment(row["experiment_id"], "queued", "retry after expired lease")
                self.conn.execute(
                    """
                    UPDATE experiments
                    SET lease_owner = NULL, lease_expires_at = NULL, failure_type = 'lease_expired',
                        retry_count = retry_count + 1, updated_at = ?
                    WHERE experiment_id = ?
                    """,
                    (utc_now(), row["experiment_id"]),
                )
            self.audit(
                "lease_reclaimed",
                "expired lease reclaimed",
                campaign_id=campaign_id,
                experiment_id=row["experiment_id"],
                severity="warning",
                details={"lease_owner": row["lease_owner"], "lease_expires_at": row["lease_expires_at"]},
            )
        return len(rows)

    def claim_next(self, campaign_id: str, owner: str, lease_seconds: int) -> sqlite3.Row | None:
        self.reclaim_expired_leases(campaign_id)
        row = self.conn.execute(
            """
            SELECT * FROM experiments
            WHERE campaign_id = ? AND status = 'queued'
            ORDER BY priority ASC, experiment_id ASC
            LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()
        if not row:
            return None
        experiment_id = int(row["experiment_id"])
        self.transition_experiment(experiment_id, "claimed", f"claimed by {owner}")
        lease_expires = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).replace(microsecond=0).isoformat()
        self.conn.execute(
            """
            UPDATE experiments
            SET lease_owner = ?, lease_expires_at = ?, updated_at = ?
            WHERE experiment_id = ?
            """,
            (owner, lease_expires, utc_now(), experiment_id),
        )
        attempt_no = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM experiment_attempts WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()[0]
        ) + 1
        cur = self.conn.execute(
            """
            INSERT INTO experiment_attempts(experiment_id, campaign_id, owner, attempt_no, status, started_at, charged)
            VALUES (?, ?, ?, ?, 'claimed', ?, 1)
            """,
            (experiment_id, campaign_id, owner, attempt_no, utc_now()),
        )
        attempt_id = int(cur.lastrowid)
        self.conn.execute(
            """
            INSERT OR IGNORE INTO budget_events(campaign_id, experiment_id, attempt_id, event_type, amount, created_at, details_json, idempotency_key)
            VALUES (?, ?, ?, 'attempt_started', 1, ?, '{}', ?)
            """,
            (campaign_id, experiment_id, attempt_id, utc_now(), f"attempt:{attempt_id}:started"),
        )
        self.audit(
            "experiment_claimed",
            f"experiment {experiment_id} claimed by {owner}",
            campaign_id=campaign_id,
            experiment_id=experiment_id,
            details={"attempt_id": attempt_id, "lease_expires_at": lease_expires},
        )
        return self.conn.execute(
            """
            SELECT e.*, a.attempt_id, a.attempt_no, h.payload_json
            FROM experiments e
            JOIN experiment_attempts a ON a.experiment_id = e.experiment_id
            JOIN hypotheses h ON h.hypothesis_id = e.hypothesis_id
            WHERE e.experiment_id = ? AND a.attempt_id = ?
            """,
            (experiment_id, attempt_id),
        ).fetchone()

    def complete_attempt(
        self,
        attempt_id: int,
        status: str,
        simulated_action: str,
        failure_type: str | None = None,
        artifact_path: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE experiment_attempts
            SET status = ?, failure_type = ?, completed_at = ?, simulated_action = ?, artifact_path = ?
            WHERE attempt_id = ?
            """,
            (status, failure_type, utc_now(), simulated_action, artifact_path, attempt_id),
        )

    def can_retry_experiment(self, experiment_id: int, failure_type: str | None) -> bool:
        row = self.conn.execute(
            "SELECT retry_count, max_retries FROM experiments WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
        if not row:
            return False
        policy = failure_policy(failure_type)
        return (
            policy["retryable"]
            and int(row["retry_count"]) < int(row["max_retries"])
        )

    def record_failure(self, campaign_id: str, experiment_id: int, attempt_id: int, failure_type: str) -> None:
        normalized = normalize_failure_type(failure_type) or "implementation_error"
        self.transition_experiment(experiment_id, "failed", f"experiment failure: {normalized}")
        self.conn.execute(
            "UPDATE experiments SET failure_type = ?, lease_owner = NULL, lease_expires_at = NULL WHERE experiment_id = ?",
            (normalized, experiment_id),
        )
        self.complete_attempt(attempt_id, "failed", f"experiment_{normalized}", failure_type=normalized)
        if self.can_retry_experiment(experiment_id, normalized):
            self.transition_experiment(experiment_id, "queued", f"retry allowed for {normalized}")
            self.conn.execute(
                "UPDATE experiments SET retry_count = retry_count + 1, updated_at = ? WHERE experiment_id = ?",
                (utc_now(), experiment_id),
            )
        elif failure_policy(normalized)["counts_consecutive_candidate_failure"]:
            self.conn.execute(
                """
                UPDATE campaigns
                SET consecutive_failures = consecutive_failures + 1, updated_at = ?
                WHERE campaign_id = ?
                """,
                (utc_now(), campaign_id),
            )

    def reset_consecutive_failures(self, campaign_id: str) -> None:
        self.conn.execute(
            "UPDATE campaigns SET consecutive_failures = 0, updated_at = ? WHERE campaign_id = ?",
            (utc_now(), campaign_id),
        )

    def budget_summary(self, campaign_id: str) -> dict:
        row = self.campaign(campaign_id)
        attempts = int(
            self.conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM budget_events WHERE campaign_id = ? AND event_type = 'attempt_started'",
                (campaign_id,),
            ).fetchone()[0]
        )
        completed = int(
            self.conn.execute(
                """
                SELECT COUNT(*) FROM experiments
                WHERE campaign_id = ? AND status IN ('accepted', 'rejected', 'failed')
                """,
                (campaign_id,),
            ).fetchone()[0]
        )
        queued = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE campaign_id = ? AND status = 'queued'",
                (campaign_id,),
            ).fetchone()[0]
        )
        active_leases = self.conn.execute(
            """
            SELECT experiment_id, lease_owner, lease_expires_at
            FROM experiments
            WHERE campaign_id = ? AND lease_owner IS NOT NULL
            ORDER BY lease_expires_at
            """,
            (campaign_id,),
        ).fetchall()
        return {
            "campaign_status": row["status"],
            "attempts": attempts,
            "completed_experiments": completed,
            "queued_experiments": queued,
            "consecutive_failures": int(row["consecutive_failures"]),
            "active_leases": [dict(item) for item in active_leases],
            "last_stop_reason": row["last_stop_reason"],
            "last_escalation_reason": row["last_escalation_reason"],
            "completion_quality": row["completion_quality"],
            "remaining_experiments": int(row["remaining_experiments"]),
        }

    def should_stop_for_budget(self, campaign_id: str, config: dict) -> str | None:
        budget = config.get("budget") or {}
        summary = self.budget_summary(campaign_id)
        if summary["completed_experiments"] >= int(budget["max_experiments"]):
            return "max_experiments reached"
        if summary["attempts"] >= int(budget["max_total_attempts"]):
            return "max_total_attempts reached"
        if summary["consecutive_failures"] >= int(budget["max_consecutive_failures"]):
            return "max_consecutive_failures reached"
        started_at = parse_time(self.campaign(campaign_id)["started_at"])
        if started_at:
            elapsed = datetime.now(timezone.utc) - started_at
            if elapsed.total_seconds() >= int(budget["max_wall_clock_minutes"]) * 60:
                return "max_wall_clock_minutes reached"
        return None

    def campaign_stop_target(self, campaign_id: str, reason: str) -> tuple[str, str]:
        queued = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE campaign_id = ? AND status = 'queued'",
                (campaign_id,),
            ).fetchone()[0]
        )
        if reason == "queue empty and auto generation disabled":
            return "completed", "complete"
        if reason == "max_experiments reached" and queued == 0:
            return "completed", "complete"
        if reason.startswith("max_") or reason in {"operator_stop"}:
            return "stopped", "partial" if queued else "complete"
        return "stopped", "partial" if queued else "complete"

    def stop_campaign(self, campaign_id: str, reason: str) -> None:
        queued = int(
            self.conn.execute(
                "SELECT COUNT(*) FROM experiments WHERE campaign_id = ? AND status = 'queued'",
                (campaign_id,),
            ).fetchone()[0]
        )
        status, quality = self.campaign_stop_target(campaign_id, reason)
        self.transition_campaign(
            campaign_id,
            status,
            reason,
            completion_quality=quality,
            remaining_experiments=queued,
        )

    def status_report(self, campaign_id: str) -> dict:
        campaign = dict(self.campaign(campaign_id))
        counts = {
            row["status"]: int(row["count"])
            for row in self.conn.execute(
                "SELECT status, COUNT(*) AS count FROM experiments WHERE campaign_id = ? GROUP BY status",
                (campaign_id,),
            ).fetchall()
        }
        retries = int(
            self.conn.execute(
                "SELECT COALESCE(SUM(retry_count), 0) FROM experiments WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()[0]
        )
        next_row = self.conn.execute(
            """
            SELECT experiment_id, fingerprint, priority FROM experiments
            WHERE campaign_id = ? AND status = 'queued'
            ORDER BY priority ASC, experiment_id ASC
            LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()
        report = {
            "campaign": campaign,
            "counts": counts,
            "retries": retries,
            "budget": self.budget_summary(campaign_id),
            "next_experiment": dict(next_row) if next_row else None,
        }
        return report

    def final_report_markdown(self, campaign_id: str) -> str:
        report = self.status_report(campaign_id)
        counts = report["counts"]
        lines = [
            f"# Research Campaign Report: {campaign_id}",
            "",
            "## Summary",
            "",
            f"- status: `{report['campaign']['status']}`",
            f"- attempts: `{report['budget']['attempts']}`",
            f"- completed experiments: `{report['budget']['completed_experiments']}`",
            f"- queued experiments: `{report['budget']['queued_experiments']}`",
            f"- consecutive failures: `{report['budget']['consecutive_failures']}`",
            f"- last stop reason: `{report['campaign']['last_stop_reason']}`",
            f"- failure context: `{self.failure_context(report['campaign']['last_stop_reason'])}`",
            "",
            "## Experiment Counts",
            "",
        ]
        for state in EXPERIMENT_STATES:
            if state in counts:
                lines.append(f"- {state}: `{counts[state]}`")
        lines.extend(["", "## Notes", "", "This report is generated by the Research Campaign control plane."])
        out = self.repo_root / "research" / "reports" / f"{campaign_id}_final_report.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(out.relative_to(self.repo_root).as_posix())

    @staticmethod
    def failure_context(reason: str | None) -> str:
        text = reason or ""
        environment_markers = [
            "environment preflight failed",
            "runtime_python_missing",
            "freqtrade_module_missing",
            "freqtrade_version_mismatch",
            "dataset_missing",
            "dataset_manifest_missing",
            "dataset_hash_mismatch",
            "environment_not_ready",
        ]
        if any(marker in text for marker in environment_markers):
            return "environment"
        if "candidate_rejected" in text:
            return "candidate"
        if "guard" in text:
            return "guard"
        return "control-plane"


def execute_dry_run(store: ResearchStore, config: dict, claimed: sqlite3.Row) -> str:
    experiment_id = int(claimed["experiment_id"])
    attempt_id = int(claimed["attempt_id"])
    campaign_id = claimed["campaign_id"]
    payload = json.loads(claimed["payload_json"])
    attempt_no = int(claimed["attempt_no"])
    outcomes = payload.get("outcome_sequence") or [payload.get("simulated_outcome", "success")]
    outcome = outcomes[min(attempt_no - 1, len(outcomes) - 1)]
    guard_paths = payload.get("guard_paths") or [payload.get("artifact_path", "research/artifacts/dry_run.txt")]

    try:
        checked_paths = check_paths(store.repo_root, config, guard_paths)
    except PathGuardError as exc:
        store.transition_experiment(experiment_id, "escalated", f"path guard violation: {exc.reason}")
        store.conn.execute(
            """
            UPDATE experiments
            SET failure_type = 'guard_violation', lease_owner = NULL, lease_expires_at = NULL,
                updated_at = ?
            WHERE experiment_id = ?
            """,
            (utc_now(), experiment_id),
        )
        store.complete_attempt(attempt_id, "escalated", "dry_run_guard_violation", failure_type="guard_violation")
        store.conn.execute(
            """
            UPDATE campaigns
            SET status = 'escalated', completed_at = ?, updated_at = ?,
                last_stop_reason = 'guard violation', last_escalation_reason = ?
            WHERE campaign_id = ?
            """,
            (utc_now(), utc_now(), str(exc), campaign_id),
        )
        store.audit(
            "path_guard_violation",
            str(exc),
            campaign_id=campaign_id,
            experiment_id=experiment_id,
            severity="critical",
            details={"path": exc.path, "reason": exc.reason},
        )
        return "escalated"

    store.transition_experiment(experiment_id, "preparing", "dry-run prepare")
    store.transition_experiment(experiment_id, "running", "dry-run runner")
    if outcome in {"retryable_failure", "timeout", "permanent_failure"}:
        failure_type = {
            "retryable_failure": "transient",
            "timeout": "timeout",
            "permanent_failure": "candidate_rejected",
        }[outcome]
        store.record_failure(campaign_id, experiment_id, attempt_id, failure_type)
        return "failed"

    store.transition_experiment(experiment_id, "validating", "dry-run validate")
    store.transition_experiment(experiment_id, "recorded", "dry-run record")
    artifact_path = checked_paths[0]
    store.conn.execute(
        """
        INSERT INTO artifacts(campaign_id, experiment_id, attempt_id, artifact_type, path, created_at, metadata_json)
        VALUES (?, ?, ?, 'dry_run_report', ?, ?, ?)
        """,
        (
            campaign_id,
            experiment_id,
            attempt_id,
            artifact_path,
            utc_now(),
            json.dumps({"outcome": outcome, "attempt_no": attempt_no}, sort_keys=True),
        ),
    )
    final_state = "accepted" if outcome == "success" else "rejected"
    store.transition_experiment(experiment_id, final_state, f"dry-run {final_state}")
    store.conn.execute(
        """
        UPDATE experiments
        SET result = ?, lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
        WHERE experiment_id = ?
        """,
        (outcome, utc_now(), experiment_id),
    )
    store.complete_attempt(attempt_id, final_state, f"dry_run_{outcome}", artifact_path=artifact_path)
    store.reset_consecutive_failures(campaign_id)
    return final_state


def execute_fixed_backtest(store: ResearchStore, config: dict, claimed: sqlite3.Row) -> str:
    from run_experiment import run_fixed_backtest

    experiment_id = int(claimed["experiment_id"])
    attempt_id = int(claimed["attempt_id"])
    campaign_id = claimed["campaign_id"]
    payload = json.loads(claimed["payload_json"])

    try:
        store.transition_experiment(experiment_id, "preparing", "fixed-backtest prepare")
        result = run_fixed_backtest(store.repo_root, config, experiment_id, payload)
        store.transition_experiment(experiment_id, "running", "fixed-backtest executed")
        if result["status"] == "escalated":
            store.transition_experiment(experiment_id, "escalated", result["failure_type"])
            store.conn.execute(
                """
                UPDATE experiments
                SET failure_type = ?, lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
                WHERE experiment_id = ?
                """,
                (result["failure_type"], utc_now(), experiment_id),
            )
            store.complete_attempt(attempt_id, "escalated", "fixed_backtest_guard_violation", failure_type=result["failure_type"], artifact_path=result.get("report_path"))
            store.conn.execute(
                """
                UPDATE campaigns
                SET status = 'escalated', completed_at = ?, updated_at = ?,
                    last_stop_reason = 'guard violation', last_escalation_reason = ?,
                    completion_quality = 'partial'
                WHERE campaign_id = ?
                """,
                (utc_now(), utc_now(), result.get("message", "guard violation"), campaign_id),
            )
            return "escalated"

        if result["status"] == "failed":
            store.record_failure(campaign_id, experiment_id, attempt_id, result["failure_type"])
            if not failure_policy(result.get("failure_type")).get("retryable"):
                reason_code = result.get("reason_code") or result.get("failure_type")
                queued = int(
                    store.conn.execute(
                        "SELECT COUNT(*) FROM experiments WHERE campaign_id = ? AND status = 'queued'",
                        (campaign_id,),
                    ).fetchone()[0]
                )
                store.transition_campaign(
                    campaign_id,
                    "failed",
                    f"fixed backtest failed: {reason_code}",
                    completion_quality="partial",
                    remaining_experiments=queued,
                )
            return "failed"

        store.transition_experiment(experiment_id, "validating", "fixed-backtest validate")
        store.transition_experiment(experiment_id, "recorded", "fixed-backtest record")
        final_state = "accepted" if result["status"] == "accepted" else "rejected"
        if final_state == "rejected":
            store.transition_experiment(experiment_id, final_state, "fixed-backtest acceptance gate rejected")
            store.conn.execute(
                "UPDATE campaigns SET consecutive_failures = consecutive_failures + 1, updated_at = ? WHERE campaign_id = ?",
                (utc_now(), campaign_id),
            )
        else:
            store.transition_experiment(experiment_id, final_state, "fixed-backtest accepted")
            store.reset_consecutive_failures(campaign_id)
        store.conn.execute(
            """
            UPDATE experiments
            SET result = ?, failure_type = ?, lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
            WHERE experiment_id = ?
            """,
            (result["status"], result.get("failure_type"), utc_now(), experiment_id),
        )
        report_path = result.get("report_path")
        if report_path:
            store.conn.execute(
                """
                INSERT INTO artifacts(campaign_id, experiment_id, attempt_id, artifact_type, path, created_at, metadata_json)
                VALUES (?, ?, ?, 'runner_report', ?, ?, ?)
                """,
                (
                    campaign_id,
                    experiment_id,
                    attempt_id,
                    report_path,
                    utc_now(),
                    json.dumps({"runner_type": "fixed_backtest", "status": result["status"]}, sort_keys=True),
                ),
            )
        store.complete_attempt(attempt_id, final_state, f"fixed_backtest_{result['status']}", failure_type=result.get("failure_type"), artifact_path=report_path)
        return final_state
    except PathGuardError as exc:
        store.transition_experiment(experiment_id, "escalated", f"path guard violation: {exc.reason}")
        store.complete_attempt(attempt_id, "escalated", "fixed_backtest_guard_violation", failure_type="guard_violation")
        store.conn.execute(
            """
            UPDATE campaigns
            SET status = 'escalated', completed_at = ?, updated_at = ?,
                last_stop_reason = 'guard violation', last_escalation_reason = ?,
                completion_quality = 'partial'
            WHERE campaign_id = ?
            """,
            (utc_now(), utc_now(), str(exc), campaign_id),
        )
        return "escalated"


def execute_sealed_offline_backtest(store: ResearchStore, config: dict, claimed: sqlite3.Row) -> str:
    from run_offline_backtest import run_offline_backtest

    experiment_id = int(claimed["experiment_id"])
    attempt_id = int(claimed["attempt_id"])
    campaign_id = claimed["campaign_id"]
    payload = json.loads(claimed["payload_json"])
    snapshot = payload.get("exchange_snapshot") or (config.get("sealed_offline_backtest") or {}).get("exchange_snapshot")
    execution_run_id = payload.get("execution_run_id") or f"ATTEMPT-{attempt_id}"
    try:
        store.transition_experiment(experiment_id, "preparing", "sealed-offline prepare")
        result = run_offline_backtest(store.repo_root, config, experiment_id, execution_run_id, snapshot)
        store.transition_experiment(experiment_id, "running", "sealed-offline executed")
        if result["status"] == "failed":
            store.record_failure(campaign_id, experiment_id, attempt_id, result.get("failure_type"))
            if not failure_policy(result.get("failure_type")).get("retryable"):
                queued = int(
                    store.conn.execute(
                        "SELECT COUNT(*) FROM experiments WHERE campaign_id = ? AND status = 'queued'",
                        (campaign_id,),
                    ).fetchone()[0]
                )
                store.transition_campaign(
                    campaign_id,
                    "failed",
                    f"sealed offline backtest failed: {result.get('reason_code') or result.get('failure_type')}",
                    completion_quality="partial",
                    remaining_experiments=queued,
                )
            return "failed"
        store.transition_experiment(experiment_id, "validating", "sealed-offline validate")
        store.transition_experiment(experiment_id, "recorded", "sealed-offline record")
        final_state = "accepted" if result["status"] == "accepted" else "rejected"
        store.transition_experiment(experiment_id, final_state, f"sealed-offline {final_state}")
        if final_state == "accepted":
            store.reset_consecutive_failures(campaign_id)
        store.conn.execute(
            """
            UPDATE experiments
            SET result = ?, failure_type = ?, lease_owner = NULL, lease_expires_at = NULL, updated_at = ?
            WHERE experiment_id = ?
            """,
            (result["status"], result.get("failure_type"), utc_now(), experiment_id),
        )
        report_path = result.get("report_path")
        if report_path:
            store.conn.execute(
                """
                INSERT INTO artifacts(campaign_id, experiment_id, attempt_id, artifact_type, path, created_at, metadata_json)
                VALUES (?, ?, ?, 'runner_report', ?, ?, ?)
                """,
                (
                    campaign_id,
                    experiment_id,
                    attempt_id,
                    report_path,
                    utc_now(),
                    json.dumps({"runner_type": "sealed_offline_backtest", "status": result["status"]}, sort_keys=True),
                ),
            )
        store.complete_attempt(attempt_id, final_state, f"sealed_offline_{result['status']}", failure_type=result.get("failure_type"), artifact_path=report_path)
        return final_state
    except PathGuardError as exc:
        store.transition_experiment(experiment_id, "escalated", f"path guard violation: {exc.reason}")
        store.complete_attempt(attempt_id, "escalated", "sealed_offline_guard_violation", failure_type="guard_violation")
        store.conn.execute(
            """
            UPDATE campaigns
            SET status = 'escalated', completed_at = ?, updated_at = ?,
                last_stop_reason = 'guard violation', last_escalation_reason = ?,
                completion_quality = 'partial'
            WHERE campaign_id = ?
            """,
            (utc_now(), utc_now(), str(exc), campaign_id),
        )
        return "escalated"


def run_orchestrator(
    repo_root: str | Path,
    campaign_path: str | Path,
    owner: str,
    max_steps: int | None = None,
    resume: bool = False,
    simulate_crash_after: int | None = None,
) -> dict:
    config = load_campaign(campaign_path)
    campaign_id = config["campaign_id"]
    lease_seconds = int((config.get("autonomy") or {}).get("lease_seconds", 60))
    store = ResearchStore(repo_root)
    store.init_schema()
    steps = 0
    try:
        store.begin()
        store.upsert_campaign(config, campaign_path, owner=owner)
        store.commit()
        while True:
            store.begin()
            campaign = store.campaign(campaign_id)
            if campaign["status"] != "active":
                store.commit()
                break
            store.reclaim_expired_leases(campaign_id)
            stop_reason = store.should_stop_for_budget(campaign_id, config)
            if stop_reason:
                store.stop_campaign(campaign_id, stop_reason)
                store.final_report_markdown(campaign_id)
                store.commit()
                break
            campaign_runner_type = config.get("runner_type") or config.get("mode", "dry_run")
            if campaign_runner_type == "fixed_backtest" and not ((config.get("fixed_backtest") or {}).get("fake_freqtrade_script")):
                from research_environment_doctor import run_environment_doctor

                preflight = run_environment_doctor(store.repo_root, config, runtime_path=config.get("runtime_config"))
                if not preflight["ok"]:
                    queued = int(
                        store.conn.execute(
                            "SELECT COUNT(*) FROM experiments WHERE campaign_id = ? AND status = 'queued'",
                            (campaign_id,),
                        ).fetchone()[0]
                    )
                    reason_codes = sorted({issue["reason_code"] for issue in preflight["issues"]})
                    store.transition_campaign(
                        campaign_id,
                        "failed",
                        f"environment preflight failed: {', '.join(reason_codes)}",
                        completion_quality="partial",
                        remaining_experiments=queued,
                    )
                    store.audit(
                        "environment_preflight_failed",
                        "fixed backtest environment is not ready",
                        campaign_id=campaign_id,
                        severity="error",
                        details=preflight,
                    )
                    store.final_report_markdown(campaign_id)
                    store.commit()
                    break
            claimed = store.claim_next(campaign_id, owner, lease_seconds)
            if not claimed:
                if store.budget_summary(campaign_id)["active_leases"]:
                    store.commit()
                    break
                if not (config.get("autonomy") or {}).get("automatically_generate_hypotheses", False):
                    store.stop_campaign(campaign_id, "queue empty and auto generation disabled")
                    store.final_report_markdown(campaign_id)
                store.commit()
                break
            steps += 1
            if simulate_crash_after is not None and steps == simulate_crash_after:
                store.audit(
                    "simulated_crash",
                    f"simulated crash after claim {steps}",
                    campaign_id=campaign_id,
                    experiment_id=int(claimed["experiment_id"]),
                    severity="warning",
                    details={"owner": owner},
                )
                store.commit()
                raise SimulatedCrash(f"simulated crash after {steps} claim(s)")
            payload = json.loads(claimed["payload_json"])
            runner_type = payload.get("runner_type") or config.get("runner_type") or config.get("mode", "dry_run")
            if runner_type == "dry_run":
                execute_dry_run(store, config, claimed)
            elif runner_type == "fixed_backtest":
                execute_fixed_backtest(store, config, claimed)
            elif runner_type == "sealed_offline_backtest":
                execute_sealed_offline_backtest(store, config, claimed)
            else:
                store.record_failure(campaign_id, int(claimed["experiment_id"]), int(claimed["attempt_id"]), "implementation_error")
            if store.campaign(campaign_id)["status"] in {"escalated", "failed"}:
                store.final_report_markdown(campaign_id)
                store.commit()
                break
            stop_reason = store.should_stop_for_budget(campaign_id, config)
            if stop_reason and store.campaign(campaign_id)["status"] == "active":
                store.stop_campaign(campaign_id, stop_reason)
                store.final_report_markdown(campaign_id)
            store.commit()
            if max_steps is not None and steps >= max_steps:
                break
            if not (config.get("autonomy") or {}).get("automatically_claim_next", False):
                break
        report = store.status_report(campaign_id)
        return report
    except Exception:
        try:
            store.rollback()
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        store.close()


def seed_demo_campaign(repo_root: str | Path, campaign_path: str | Path, reset: bool = False) -> dict:
    config = load_campaign(campaign_path)
    campaign_id = config["campaign_id"]
    store = ResearchStore(repo_root)
    store.init_schema()
    if reset and store.db_path.exists():
        store.close()
        store.db_path.unlink()
        audit_path = Path(repo_root) / AUDIT_JSONL
        if audit_path.exists():
            audit_path.unlink()
        store = ResearchStore(repo_root)
        store.init_schema()
    happy_inputs = [
        ("demo-success-001", "First success", {"simulated_outcome": "success", "artifact_path": "research/artifacts/demo-success-001.txt"}, 1),
        ("demo-success-002", "Second success", {"simulated_outcome": "success", "artifact_path": "research/artifacts/demo-success-002.txt"}, 2),
        ("demo-success-003", "Third success", {"simulated_outcome": "success", "artifact_path": "research/artifacts/demo-success-003.txt"}, 3),
        ("demo-success-004", "Crash recovery target", {"simulated_outcome": "success", "artifact_path": "research/artifacts/demo-success-004.txt"}, 4),
        ("demo-retry-005", "Retry then success", {"outcome_sequence": ["retryable_failure", "success"], "artifact_path": "research/artifacts/demo-retry-005.txt"}, 5),
        ("demo-success-006", "Sixth success", {"simulated_outcome": "success", "artifact_path": "research/artifacts/demo-success-006.txt"}, 6),
        ("demo-timeout-007", "Timeout then success", {"outcome_sequence": ["timeout", "success"], "artifact_path": "research/artifacts/demo-timeout-007.txt"}, 7),
        ("demo-permanent-008", "Permanent failure", {"simulated_outcome": "permanent_failure", "artifact_path": "research/artifacts/demo-permanent-008.txt"}, 8),
        ("demo-success-008", "Eighth success", {"simulated_outcome": "success", "artifact_path": "research/artifacts/demo-success-008.txt"}, 8),
        ("demo-success-009", "Ninth success", {"simulated_outcome": "success", "artifact_path": "research/artifacts/demo-success-009.txt"}, 9),
        ("demo-success-001", "Duplicate fingerprint", {"simulated_outcome": "success", "artifact_path": "research/artifacts/duplicate.txt"}, 11),
    ]
    guard_inputs = [
        ("demo-guard-ok-001", "Guard setup success", {"simulated_outcome": "success", "artifact_path": "research/artifacts/demo-guard-ok-001.txt"}, 1),
        ("demo-guard-002", "Guard violation", {"simulated_outcome": "success", "guard_paths": ["scripts/start_bot.sh"]}, 2),
        ("demo-guard-002", "Duplicate guard fingerprint", {"simulated_outcome": "success", "artifact_path": "research/artifacts/duplicate.txt"}, 3),
    ]
    fixed_backtest_inputs = [
        ("fixed-backtest-001", "Single fixed backtest", {"runner_type": "fixed_backtest"}, 1),
    ]
    sealed_offline_inputs = [
        ("sealed-offline-backtest-001", "Single sealed offline backtest", {"runner_type": "sealed_offline_backtest", "execution_run_id": "ORCH-ATTEMPT"}, 1),
    ]
    runner_type = config.get("runner_type") or config.get("mode")
    if "guard" in campaign_id:
        inputs = guard_inputs
    elif "sealed-offline" in campaign_id or runner_type == "sealed_offline_backtest":
        inputs = sealed_offline_inputs
    elif "fixed-backtest" in campaign_id:
        inputs = fixed_backtest_inputs
    else:
        inputs = happy_inputs
    try:
        store.begin()
        store.upsert_campaign(config, campaign_path, owner="seed")
        inserted = 0
        duplicates = 0
        for fingerprint, title, payload, priority in inputs:
            result = store.add_hypothesis(campaign_id, fingerprint, title, payload, priority)
            if result is None:
                duplicates += 1
            else:
                inserted += 1
        store.commit()
        return {"campaign_id": campaign_id, "inserted": inserted, "duplicates_rejected": duplicates}
    except Exception:
        store.rollback()
        raise
    finally:
        store.close()


def cli_orchestrator(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the dry-run research campaign orchestrator.")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--owner", default=f"owner-{os.getpid()}")
    parser.add_argument("--simulate-crash-after", type=int)
    args = parser.parse_args(argv)
    report = run_orchestrator(
        Path.cwd(),
        args.campaign,
        owner=args.owner,
        max_steps=args.max_steps,
        resume=args.resume,
        simulate_crash_after=args.simulate_crash_after,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0


def cli_status(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show research campaign status.")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    config = load_campaign(args.campaign)
    store = ResearchStore(Path.cwd())
    store.init_schema()
    report = store.status_report(config["campaign_id"])
    store.close()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return 0
    print(f"Campaign: {config['campaign_id']}")
    print(f"Status: {report['campaign']['status']}")
    print(f"Counts: {report['counts']}")
    print(f"Retries: {report['retries']}")
    print(f"Attempts used: {report['budget']['attempts']}")
    print(f"Consecutive failures: {report['budget']['consecutive_failures']}")
    print(f"Active leases: {report['budget']['active_leases']}")
    print(f"Last stop reason: {report['budget']['last_stop_reason']}")
    print(f"Last escalation reason: {report['budget']['last_escalation_reason']}")
    print(f"Next experiment: {report['next_experiment']}")
    return 0


def cli_seed(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the demo dry-run research campaign.")
    parser.add_argument("--campaign", default="research/campaigns/active/demo-control-plane.yaml")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)
    result = seed_demo_campaign(Path.cwd(), args.campaign, reset=args.reset)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
