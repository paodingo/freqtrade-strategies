#!/usr/bin/env python3
"""Run Stage 3B.1 identity-equivalence candidate lifecycle."""

from __future__ import annotations

import argparse
import json
import os
import py_compile
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from create_candidate_strategy import (
    BASE_STRATEGY_PATH,
    BASE_STRATEGY_SHA256,
    EXPECTED_BASELINE_TRADE_HASH,
    CandidateError,
    candidate_class_name,
    candidate_root,
    create_candidate_strategy,
    validate_candidate_source,
)
from research_control import load_campaign, load_simple_yaml, utc_now
from run_experiment import artifact_hashes, dump_json, find_result_json, repo_rel, sha256_file
from run_offline_backtest import run_offline_backtest
from run_stage3a5_acceptance import CORE_COMPARE_KEYS, compare_summaries, metric_summary, write_normalized_trades
from validate_strategy_market_contract import validate_contract


FINAL_STATES = {
    "identity_verified",
    "identity_mismatch",
    "creation_failed",
    "validation_failed",
    "execution_failed",
    "escalated",
}
STATE_FLOW = (
    "queued",
    "claimed",
    "candidate_created",
    "static_validated",
    "executed",
    "compared",
    "recorded",
    "identity_verified",
)


class Stage3B1Error(RuntimeError):
    def __init__(self, status: str, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.status = status
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


def clean_network_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    return env


def init_registry(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stage3b1_candidate_lifecycle (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          campaign_id TEXT NOT NULL,
          hypothesis_id TEXT NOT NULL,
          experiment_id TEXT NOT NULL,
          candidate_id TEXT NOT NULL,
          candidate_class TEXT NOT NULL,
          candidate_path TEXT NOT NULL,
          base_strategy_hash TEXT NOT NULL,
          candidate_strategy_hash TEXT,
          creation_status TEXT NOT NULL,
          static_validation_status TEXT,
          execution_status TEXT,
          equivalence_verdict TEXT,
          baseline_trade_hash TEXT,
          candidate_trade_hash TEXT,
          result_artifact_path TEXT,
          failure_class TEXT,
          failure_reason TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(campaign_id, experiment_id)
        );
        CREATE TABLE IF NOT EXISTS stage3b1_candidate_state_events (
          event_id INTEGER PRIMARY KEY AUTOINCREMENT,
          campaign_id TEXT NOT NULL,
          experiment_id TEXT NOT NULL,
          state TEXT NOT NULL,
          created_at TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '{}'
        );
        """
    )


def record_state(conn: sqlite3.Connection, campaign_id: str, experiment_id: str, state: str, details: dict | None = None) -> None:
    conn.execute(
        """
        INSERT INTO stage3b1_candidate_state_events(campaign_id, experiment_id, state, created_at, details_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (campaign_id, experiment_id, state, utc_now(), json.dumps(details or {}, sort_keys=True)),
    )


def upsert_lifecycle(
    conn: sqlite3.Connection,
    campaign_id: str,
    experiment_id: str,
    candidate_class: str,
    candidate_path: str,
    base_hash: str,
    **fields: Any,
) -> None:
    now = utc_now()
    payload = {
        "hypothesis_id": fields.pop("hypothesis_id", "stage3b1-identity-equivalence"),
        "candidate_id": fields.pop("candidate_id", f"{campaign_id}:{experiment_id}:{candidate_class}"),
        "candidate_strategy_hash": fields.pop("candidate_strategy_hash", None),
        "creation_status": fields.pop("creation_status", "pending"),
        "static_validation_status": fields.pop("static_validation_status", None),
        "execution_status": fields.pop("execution_status", None),
        "equivalence_verdict": fields.pop("equivalence_verdict", None),
        "baseline_trade_hash": fields.pop("baseline_trade_hash", None),
        "candidate_trade_hash": fields.pop("candidate_trade_hash", None),
        "result_artifact_path": fields.pop("result_artifact_path", None),
        "failure_class": fields.pop("failure_class", None),
        "failure_reason": fields.pop("failure_reason", None),
    }
    conn.execute(
        """
        INSERT INTO stage3b1_candidate_lifecycle(
          campaign_id, hypothesis_id, experiment_id, candidate_id, candidate_class,
          candidate_path, base_strategy_hash, candidate_strategy_hash, creation_status,
          static_validation_status, execution_status, equivalence_verdict,
          baseline_trade_hash, candidate_trade_hash, result_artifact_path,
          failure_class, failure_reason, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(campaign_id, experiment_id) DO UPDATE SET
          candidate_strategy_hash = excluded.candidate_strategy_hash,
          creation_status = excluded.creation_status,
          static_validation_status = excluded.static_validation_status,
          execution_status = excluded.execution_status,
          equivalence_verdict = excluded.equivalence_verdict,
          baseline_trade_hash = excluded.baseline_trade_hash,
          candidate_trade_hash = excluded.candidate_trade_hash,
          result_artifact_path = excluded.result_artifact_path,
          failure_class = excluded.failure_class,
          failure_reason = excluded.failure_reason,
          updated_at = excluded.updated_at
        """,
        (
            campaign_id,
            payload["hypothesis_id"],
            experiment_id,
            payload["candidate_id"],
            candidate_class,
            candidate_path,
            base_hash,
            payload["candidate_strategy_hash"],
            payload["creation_status"],
            payload["static_validation_status"],
            payload["execution_status"],
            payload["equivalence_verdict"],
            payload["baseline_trade_hash"],
            payload["candidate_trade_hash"],
            payload["result_artifact_path"],
            payload["failure_class"],
            payload["failure_reason"],
            now,
            now,
        ),
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_base_strategy(repo_root: Path, checkpoint: str) -> dict[str, str]:
    actual = sha256_file(repo_root / BASE_STRATEGY_PATH).upper()
    result = {"checkpoint": checkpoint, "path": BASE_STRATEGY_PATH.as_posix(), "sha256": actual}
    if actual != BASE_STRATEGY_SHA256:
        raise Stage3B1Error("escalated", "validation_error", "base_strategy_integrity_violation", f"base strategy hash changed at {checkpoint}: {actual}")
    return result


def verify_artifact_hashes(run_dir: Path) -> dict[str, Any]:
    record_path = run_dir / "artifact-hashes.json"
    if not record_path.exists():
        raise Stage3B1Error("validation_failed", "validation_error", "baseline_artifact_integrity_failed", f"missing artifact hash record: {record_path}")
    recorded = read_json(record_path)
    mismatches = {}
    for rel, meta in recorded.items():
        if rel == "artifact-hashes.json":
            continue
        path = run_dir / rel
        if not path.exists():
            mismatches[rel] = {"expected": meta.get("sha256"), "actual": "missing"}
        else:
            actual = sha256_file(path)
            if actual != meta.get("sha256"):
                mismatches[rel] = {"expected": meta.get("sha256"), "actual": actual}
    return {"ok": not mismatches, "mismatches": mismatches, "checked_files": len(recorded)}


def baseline_reference(repo_root: Path, campaign: dict) -> dict[str, Any]:
    ref = campaign["stage3b1"]["baseline_reference"]
    run_dir = repo_root / ref["run_dir"]
    integrity = verify_artifact_hashes(run_dir)
    if not integrity["ok"]:
        raise Stage3B1Error("validation_failed", "validation_error", "baseline_artifact_integrity_failed", "baseline artifact hash mismatch")
    runner = read_json(run_dir / "runner-report.json")
    normalized = read_json(run_dir / "normalized-trades.json")
    input_freeze = read_json(run_dir / "input-fingerprint.json")
    strategy_hash = (input_freeze.get("strategy_file_sha256") or "").upper()
    trade_hash = normalized.get("sha256") or (runner.get("summary") or {}).get("normalized_trades_sha256")
    input_fingerprint = input_freeze.get("input_fingerprint") or runner.get("input_fingerprint")
    expected_input = campaign["stage3b1"]["expected_input_fingerprint"]
    if strategy_hash != BASE_STRATEGY_SHA256:
        raise Stage3B1Error("validation_failed", "validation_error", "baseline_strategy_hash_mismatch", f"baseline strategy hash mismatch: {strategy_hash}")
    if trade_hash != EXPECTED_BASELINE_TRADE_HASH:
        raise Stage3B1Error("validation_failed", "validation_error", "baseline_trade_hash_mismatch", f"baseline trade hash mismatch: {trade_hash}")
    if input_fingerprint != expected_input:
        raise Stage3B1Error("validation_failed", "validation_error", "baseline_input_fingerprint_mismatch", f"baseline input fingerprint mismatch: {input_fingerprint}")
    return {
        "run_dir": ref["run_dir"],
        "runner_report": repo_rel(repo_root, run_dir / "runner-report.json"),
        "summary": runner["summary"],
        "normalized_trade_hash": trade_hash,
        "input_fingerprint": input_fingerprint,
        "artifact_integrity": integrity,
    }


def runtime_python(repo_root: Path, campaign: dict) -> Path:
    runtime = load_simple_yaml(repo_root / campaign["fixed_backtest"]["runtime_config"])
    python_ref = Path(str(runtime["python_executable"]))
    return python_ref if python_ref.is_absolute() else repo_root / python_ref


def freqtrade_load_check(repo_root: Path, campaign: dict, candidate_dir: Path, candidate_class: str) -> dict[str, Any]:
    command = [
        str(runtime_python(repo_root, campaign)),
        "-m",
        "freqtrade",
        "list-strategies",
        "--strategy-path",
        str(candidate_dir),
        "--recursive-strategy-search",
        "--no-color",
        "-1",
    ]
    result = subprocess.run(command, cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, env=clean_network_env())
    output = result.stdout + "\n" + result.stderr
    ok = result.returncode == 0 and candidate_class in output
    return {"ok": ok, "command": command, "returncode": result.returncode, "candidate_seen": candidate_class in output, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}


def class_uniqueness(candidate_dir: Path, candidate_class: str) -> dict[str, Any]:
    matches = []
    legacy_matches = []
    pattern = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
    for path in candidate_dir.glob("*.py"):
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            if name == candidate_class:
                matches.append(path.name)
            if name == "RegimeAwareV6":
                legacy_matches.append(path.name)
    return {
        "ok": len(matches) == 1 and not legacy_matches,
        "candidate_class_matches": matches,
        "legacy_class_matches": legacy_matches,
    }


def static_validate_candidate(repo_root: Path, campaign: dict, experiment_id: str, candidate_class: str) -> dict[str, Any]:
    fixed = campaign["fixed_backtest"]
    root = candidate_root(repo_root, campaign["campaign_id"], experiment_id)
    candidate_file = root / f"{candidate_class}.py"
    py_compile.compile(str(candidate_file), doraise=True)
    for dep in ("regime_aware_base.py", "regime_detector.py", "risk_manager.py"):
        py_compile.compile(str(root / dep), doraise=True)
    source_validation = validate_candidate_source(repo_root, root, candidate_class)
    uniqueness = class_uniqueness(root, candidate_class)
    load_check = freqtrade_load_check(repo_root, campaign, root, candidate_class)
    contract = validate_contract(
        candidate_file,
        candidate_class,
        repo_root / fixed["config"],
        repo_root / fixed["dataset_manifest"],
        repo_root / campaign["sealed_offline_backtest"]["exchange_snapshot"],
    )
    checks = {
        "python_compile": {"ok": True},
        "source_diff": source_validation,
        "class_uniqueness": uniqueness,
        "freqtrade_strategy_load": load_check,
        "strategy_market_contract": contract,
        "base_strategy_hash": verify_base_strategy(repo_root, "static_validation"),
        "sealed_dataset_hash": load_simple_yaml(repo_root / fixed["dataset_manifest"]).get("aggregate_sha256"),
        "sealed_exchange_hash": load_simple_yaml(repo_root / campaign["sealed_offline_backtest"]["exchange_snapshot"] / "manifest.yaml").get("aggregate_sha256"),
    }
    ok = (
        source_validation["ok"]
        and uniqueness["ok"]
        and load_check["ok"]
        and contract["ok"]
    )
    checks["ok"] = ok
    if not ok:
        raise Stage3B1Error("validation_failed", "validation_error", "candidate_static_validation_failed", "candidate static validation failed")
    return checks


def run_candidate_backtest(repo_root: Path, campaign: dict, experiment_id: str, candidate_class: str) -> dict[str, Any]:
    root = candidate_root(repo_root, campaign["campaign_id"], experiment_id)
    candidate_file = root / f"{candidate_class}.py"
    candidate_campaign = json.loads(json.dumps(campaign))
    candidate_campaign["fixed_backtest"]["strategy"] = candidate_class
    candidate_campaign["fixed_backtest"]["strategy_file"] = repo_rel(repo_root, candidate_file)
    candidate_campaign["fixed_backtest"]["strategy_path"] = repo_rel(repo_root, root)
    snapshot = repo_root / candidate_campaign["sealed_offline_backtest"]["exchange_snapshot"]
    result = run_offline_backtest(repo_root, candidate_campaign, experiment_id, "CANDIDATE-RUN", snapshot)
    run_dir = repo_root / "research" / "results" / campaign["campaign_id"] / experiment_id / "CANDIDATE-RUN"
    if result["status"] != "accepted":
        raise Stage3B1Error("execution_failed", result.get("failure_type") or "backtest_error", result.get("reason_code") or "candidate_offline_execution_failed", result.get("message") or "candidate backtest failed")
    result_path = find_result_json(run_dir)
    metrics = read_json(run_dir / "metrics.json")
    trades = write_normalized_trades(run_dir, result_path, candidate_class)
    summary = metric_summary(metrics, trades)
    report_path = run_dir / "runner-report.json"
    runner_report = read_json(report_path)
    runner_report.update({"run_name": "CANDIDATE-RUN", "summary": summary, "cache": "none"})
    dump_json(report_path, runner_report)
    dump_json(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    non_loopback = [item for item in runner_report.get("network_attempts") or [] if not item.get("loopback")]
    if non_loopback:
        raise Stage3B1Error("escalated", "infra_permanent", "offline_contract_violation", f"candidate attempted non-loopback network: {non_loopback}")
    return {
        "run_dir": repo_rel(repo_root, run_dir),
        "runner_report": repo_rel(repo_root, report_path),
        "summary": summary,
        "normalized_trade_hash": trades["sha256"],
        "network_attempts": runner_report.get("network_attempts") or [],
    }


def compare_identity(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    comparison = compare_summaries(baseline["summary"], candidate["summary"])
    coverage = {
        "total_trades": baseline["summary"]["core"].get("total_trades") == 3 == candidate["summary"]["core"].get("total_trades"),
        "long_trades": baseline["summary"]["core"].get("long_trade_count") == 2 == candidate["summary"]["core"].get("long_trade_count"),
        "short_trades": baseline["summary"]["core"].get("short_trade_count") == 1 == candidate["summary"]["core"].get("short_trade_count"),
        "expected_trade_hash": candidate["normalized_trade_hash"] == EXPECTED_BASELINE_TRADE_HASH,
    }
    comparison["coverage"] = coverage
    comparison["compared_core_keys"] = list(CORE_COMPARE_KEYS)
    comparison["failure_type"] = None
    comparison["reason_code"] = None
    if not comparison["consistent"] or not all(coverage.values()):
        comparison["failure_type"] = "validation_error"
        comparison["reason_code"] = "candidate_identity_semantic_mismatch"
    return comparison


def run_stage3b1(repo_root: str | Path, campaign_path: str | Path, experiment_id: str = "1") -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    campaign = load_campaign(campaign_path)
    if campaign.get("runner_type") != "candidate_identity_equivalence":
        raise Stage3B1Error("validation_failed", "validation_error", "campaign_mode_mismatch", "runner_type must be candidate_identity_equivalence")
    campaign_id = campaign["campaign_id"]
    candidate_class = candidate_class_name(campaign_id, experiment_id)
    db_path = repo_root / "research" / "registry" / "research.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    started = utc_now()
    start_monotonic = time.monotonic()
    integrity_checks = []
    try:
        init_registry(conn)
        record_state(conn, campaign_id, experiment_id, "queued")
        record_state(conn, campaign_id, experiment_id, "claimed")
        integrity_checks.append(verify_base_strategy(repo_root, "start"))
        created = create_candidate_strategy(repo_root, campaign_path, experiment_id)
        record_state(conn, campaign_id, experiment_id, "candidate_created", created)
        upsert_lifecycle(
            conn,
            campaign_id,
            experiment_id,
            candidate_class,
            created["candidate_path"],
            created["base_strategy_sha256"],
            candidate_strategy_hash=created["candidate_strategy_sha256"],
            creation_status="created",
        )
        conn.commit()
        integrity_checks.append(verify_base_strategy(repo_root, "after_candidate_creation"))
        static_checks = static_validate_candidate(repo_root, campaign, experiment_id, candidate_class)
        record_state(conn, campaign_id, experiment_id, "static_validated", {"ok": True})
        upsert_lifecycle(
            conn,
            campaign_id,
            experiment_id,
            candidate_class,
            created["candidate_path"],
            created["base_strategy_sha256"],
            candidate_strategy_hash=created["candidate_strategy_sha256"],
            creation_status="created",
            static_validation_status="passed",
        )
        baseline = baseline_reference(repo_root, campaign)
        candidate = run_candidate_backtest(repo_root, campaign, experiment_id, candidate_class)
        record_state(conn, campaign_id, experiment_id, "executed", candidate)
        integrity_checks.append(verify_base_strategy(repo_root, "after_backtest"))
        comparison = compare_identity(baseline, candidate)
        comparison_path = repo_root / "research" / "results" / campaign_id / experiment_id / "baseline-candidate-comparison.json"
        dump_json(comparison_path, comparison)
        record_state(conn, campaign_id, experiment_id, "compared", comparison)
        if comparison["reason_code"]:
            final_state = "identity_mismatch"
            failure_class = comparison["failure_type"]
            failure_reason = comparison["reason_code"]
        else:
            final_state = "identity_verified"
            failure_class = None
            failure_reason = None
        if final_state not in FINAL_STATES:
            raise Stage3B1Error("execution_failed", "implementation_error", "invalid_candidate_final_state", final_state)
        final_root = repo_root / "research" / "results" / campaign_id / experiment_id
        final_report_path = final_root / "stage3b1-final-report.json"
        integrity_checks.append(verify_base_strategy(repo_root, "end"))
        final_report = {
            "schema_version": "stage3b1-final-report-v1",
            "campaign_id": campaign_id,
            "experiment_id": experiment_id,
            "status": final_state,
            "stage3b1_complete": final_state == "identity_verified",
            "candidate_class": candidate_class,
            "candidate_manifest": created["manifest_path"],
            "candidate_path": created["candidate_path"],
            "started_at": started,
            "completed_at": utc_now(),
            "wall_clock_seconds": round(time.monotonic() - start_monotonic, 3),
            "base_strategy_integrity_checks": integrity_checks,
            "static_validation": static_checks,
            "baseline_reference": baseline,
            "candidate_run": candidate,
            "comparison": comparison,
            "registry": {"db_path": repo_rel(repo_root, db_path), "table": "stage3b1_candidate_lifecycle", "final_state": final_state},
            "safety": {
                "hyperopt_run": False,
                "lookahead_analysis_run": False,
                "recursive_analysis_run": False,
                "new_hypotheses_generated": False,
                "champion_promoted": False,
                "sealed_holdout_accessed": False,
            },
        }
        dump_json(final_report_path, final_report)
        record_state(conn, campaign_id, experiment_id, "recorded", {"report": repo_rel(repo_root, final_report_path)})
        record_state(conn, campaign_id, experiment_id, final_state)
        upsert_lifecycle(
            conn,
            campaign_id,
            experiment_id,
            candidate_class,
            created["candidate_path"],
            created["base_strategy_sha256"],
            candidate_strategy_hash=created["candidate_strategy_sha256"],
            creation_status="created",
            static_validation_status="passed",
            execution_status="accepted",
            equivalence_verdict=final_state,
            baseline_trade_hash=baseline["normalized_trade_hash"],
            candidate_trade_hash=candidate["normalized_trade_hash"],
            result_artifact_path=repo_rel(repo_root, final_report_path),
            failure_class=failure_class,
            failure_reason=failure_reason,
        )
        conn.commit()
        return final_report
    except CandidateError as exc:
        conn.rollback()
        status = "creation_failed" if exc.reason_code != "base_strategy_integrity_violation" else "escalated"
        raise Stage3B1Error(status, exc.failure_type, exc.reason_code, exc.message) from exc
    except Stage3B1Error:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 3B.1 candidate identity equivalence.")
    parser.add_argument("--campaign", default="research/campaigns/active/demo-stage3b1-candidate-identity.yaml")
    parser.add_argument("--experiment-id", default="1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = run_stage3b1(Path.cwd(), args.campaign, args.experiment_id)
    except Stage3B1Error as exc:
        payload = {
            "status": exc.status,
            "stage3b1_complete": False,
            "failure_type": exc.failure_type,
            "reason_code": exc.reason_code,
            "message": exc.message,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["stage3b1_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
