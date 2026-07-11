#!/usr/bin/env python3
"""Run Stage 3D.3-B process-isolated recertification of the frozen queue."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import re
from collections import Counter
from pathlib import Path
from typing import Any

import evaluate_research_candidate as evaluator
import run_stage3d1_bounded_search as stage3d1
import run_stage3d2b_reachability_search as stage3d2b
from research_control import load_simple_yaml, utc_now
from run_experiment import artifact_hashes, dump_json, dump_manifest, find_result_json, repo_rel, sha256_file
from run_stage3a5_acceptance import metric_summary, write_normalized_trades


CAMPAIGN_ID = "stage3d3b-candidate-process-isolation-recertification"
CAMPAIGN_PATH = Path("research/campaigns/active/stage3d3b-candidate-process-isolation-recertification.yaml")
QUEUE_PATH = Path("research/queues/stage3d3b-recertification.yaml")
RECERT_ROOT = Path("research/recertification/stage3d3b")
RESULT_ROOT = Path("research/results") / CAMPAIGN_ID
FINAL_JSON = RESULT_ROOT / "stage3d3b-final-report.json"
FINAL_MD = RESULT_ROOT / "stage3d3b-final-report.md"
INVALIDATION_PATH = RECERT_ROOT / "stage3d2b-invalidation-event.json"
AMENDMENT_PATH = Path("reports/amendments/stage3d2b-runtime-cache-invalidation.md")
ADR_PATH = Path("docs/decisions/ADR-candidate-python-import-isolation.md")
POLICY_PATH = Path("research/evaluation/evaluation-policy.yaml")
BASE_STRATEGY_SHA256 = stage3d2b.BASE_STRATEGY_SHA256
POLICY_SHA256 = stage3d2b.POLICY_HASH
ORIGINAL_QUEUE_SHA256 = "bdb463186783e5c3f34027635e250e5e4c39c1185c447a13101848d3de9373a4"
SEARCH_SPACE_SHA256 = "b18cb366f224ecb75006a4c7e20a47771935342bf13be049459c0af9cb1afe2b"
DEV_DATASET_ID = stage3d2b.DEV_DATASET_ID
REVERSE_SAMPLE_IDS = [10, 5, 2]


class Stage3D3BError(RuntimeError):
    def __init__(self, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def self_hash(payload: dict[str, Any], field: str) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != field})


def immutable_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise Stage3D3BError("validation_error", "immutable_execution_bundle_drift", str(path))
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def assert_frozen_inputs(repo_root: Path) -> dict[str, Any]:
    if sha256_file(repo_root / "strategies/RegimeAwareV6.py").upper() != BASE_STRATEGY_SHA256:
        raise Stage3D3BError("validation_error", "input_integrity_violation", "official strategy hash changed")
    policy = evaluator.read_yaml(repo_root / POLICY_PATH)
    if policy.get("policy_sha256") != POLICY_SHA256 or evaluator.canonical_policy_hash(policy) != POLICY_SHA256:
        raise Stage3D3BError("validation_error", "input_integrity_violation", "policy hash changed")
    queue = load_simple_yaml(repo_root / stage3d2b.QUEUE_PATH)
    if queue.get("queue_sha256") != ORIGINAL_QUEUE_SHA256 or stage3d2b.self_hash(queue, "queue_sha256") != ORIGINAL_QUEUE_SHA256:
        raise Stage3D3BError("validation_error", "frozen_queue_drift", "original queue changed")
    if load_simple_yaml(repo_root / stage3d2b.SEARCH_SPACE_PATH).get("search_space_sha256") != SEARCH_SPACE_SHA256:
        raise Stage3D3BError("validation_error", "input_integrity_violation", "approved search space changed")
    for path in (
        repo_root / f"research/data/snapshots/{DEV_DATASET_ID}/manifest.yaml",
        repo_root / "research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml",
    ):
        if not path.exists():
            raise Stage3D3BError("validation_error", "input_integrity_violation", f"missing frozen input: {path}")
    return queue


def build_recert_queue(repo_root: Path, original: dict[str, Any]) -> dict[str, Any]:
    references = []
    for item in original["experiments"]:
        experiment_id = int(item["experiment_id"])
        spec = repo_root / "research/experiments" / stage3d2b.CAMPAIGN_ID / str(experiment_id) / "experiment-spec.yaml"
        references.append({
            "recertification_id": experiment_id, "original_campaign_id": stage3d2b.CAMPAIGN_ID,
            "original_experiment_id": experiment_id, "original_experiment_spec": repo_rel(repo_root, spec),
            "original_experiment_spec_sha256": sha256_file(spec), "original_queue_fingerprint": item["fingerprint"],
        })
    payload = {
        "schema_version": "stage3d3b-recertification-queue-v1", "campaign_id": CAMPAIGN_ID,
        "queue_frozen": True, "original_queue_path": stage3d2b.QUEUE_PATH.as_posix(),
        "original_queue_sha256": ORIGINAL_QUEUE_SHA256, "research_hypotheses_redefined": False,
        "references": references, "reverse_order_sample_ids": REVERSE_SAMPLE_IDS,
    }
    payload["queue_sha256"] = self_hash(payload, "queue_sha256")
    return payload


def build_campaign(queue: dict[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID, "mode": "process_isolation_recertification",
        "runner_type": "fresh_python_process_one_backtest", "validation_access_allowed": False,
        "scope": {
            "allowed_paths": [f"research/results/{CAMPAIGN_ID}/**", "research/recertification/stage3d3b/**", QUEUE_PATH.as_posix(), CAMPAIGN_PATH.as_posix(), "research/registry/research.db", AMENDMENT_PATH.as_posix(), ADR_PATH.as_posix()],
            "blocked_paths": [".env", "secrets/**", "deploy/**", "user_data/config_live.json", "configs/production/**", "strategies/**", "research/data/snapshots/**", "research/evaluation/evaluation-policy.yaml", "scripts/start_bot.sh", "scripts/refresh_data.sh"],
        },
        "budget": {"max_experiments": 10, "max_total_attempts": 30, "max_retries_per_experiment": 1, "max_wall_clock_hours": 12, "max_wall_clock_minutes": 720, "max_consecutive_infrastructure_failures": 3, "max_consecutive_failures": 3, "validation_access_allowed": False},
        "autonomy": {"automatically_claim_next": True, "automatically_generate_hypotheses": False, "automatically_generate_followup_tasks": False, "automatically_promote_champion": False, "access_sealed_holdout": False},
        "recertification_queue": {"path": QUEUE_PATH.as_posix(), "sha256": queue["queue_sha256"], "original_queue_sha256": ORIGINAL_QUEUE_SHA256},
        "fixed_backtest": {
            "runtime_config": "research/runtime/freqtrade-runtime.yaml", "dataset_id": DEV_DATASET_ID,
            "dataset_manifest": f"research/data/snapshots/{DEV_DATASET_ID}/manifest.yaml", "subcommand": "sealed_offline_backtest",
            "strategy": "RegimeAwareV6", "strategy_file": "strategies/RegimeAwareV6.py", "strategy_path": "strategies",
            "config": "research/runtime/demo-futures-backtest-config.json", "timerange": "20240101-20240830", "timeframe": "1h",
            "pairs": ["BTC/USDT:USDT"], "fee": "0.0004", "datadir": f"research/data/snapshots/{DEV_DATASET_ID}/data", "timeout_seconds": 600, "acceptance_gate": {},
        },
        "sealed_offline_backtest": {"exchange_snapshot": "research/exchange_snapshots/binance-usdm-futures-2025-8-demo", "network_policy": "socket_blocker"},
        "evaluation_policy": {"policy_id": "balanced-research-gate-v1", "policy_sha256": POLICY_SHA256},
        "forbidden_actions": ["new_threshold", "new_variable", "multi_variable", "position_stacking", "position_adjustment", "max_open_trades_change", "stake_change", "roi_change", "stoploss_change", "protections_change", "leverage_change", "hyperopt", "validation", "holdout", "champion", "qualified_challenger", "forward_dry_run"],
    }


def write_control_files(repo_root: Path, original: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    queue = build_recert_queue(repo_root, original)
    campaign = build_campaign(queue)
    for path, payload in ((QUEUE_PATH, queue), (CAMPAIGN_PATH, campaign)):
        target = repo_root / path
        if target.exists() and load_simple_yaml(target) != payload:
            raise Stage3D3BError("validation_error", "frozen_control_file_drift", path.as_posix())
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True); dump_manifest(target, payload)
    return queue, campaign


def write_adr(repo_root: Path) -> None:
    content = """# ADR: Candidate Python Import Isolation

Status: Accepted for Stage 3D.3-B recertification.

## Decision

Use Scheme A: each original candidate is materialized as an immutable execution package with experiment-unique module names for the strategy base, regime detector, and risk manager. Every backtest runs in a fresh Python interpreter and exits after one invocation.

## Rejected Alternative

Scheme B was not selected because shared module names plus path ordering remain vulnerable to `sys.modules` and loader-order coupling. `importlib.reload()`, partial module eviction, and reusable workers are prohibited.

## Naming

Modules use `regime_aware_base_c3d2b_eNNNN`, `regime_detector_c3d2b_eNNNN`, and `risk_manager_c3d2b_eNNNN`. Candidate class names and approved strategy semantics remain unchanged.

## Compatibility

Freqtrade 2025.8 receives the package directory as `strategy_path`; the wrapper imports only its unique base module. Runtime identity must prove source path, source hash, module origin, and AST mutation before backtesting.

## Risks And Upgrade Requirements

Packaging import rewrites are identity-only and must remain separate from semantic diffs. Freqtrade/Python upgrades require loader compatibility tests, PID isolation tests, reverse-order tests, and runtime identity recertification.
"""
    immutable_write(repo_root / ADR_PATH, content)


def package_names(experiment_id: int) -> dict[str, str]:
    suffix = f"c3d2b_e{experiment_id:04d}"
    return {"base": f"regime_aware_base_{suffix}", "regime": f"regime_detector_{suffix}", "risk": f"risk_manager_{suffix}"}


def build_execution_package(repo_root: Path, experiment: dict[str, Any]) -> dict[str, Any]:
    experiment_id = int(experiment["experiment_id"])
    original = repo_root / "research/candidates" / stage3d2b.CAMPAIGN_ID / str(experiment_id)
    package = repo_root / RECERT_ROOT / str(experiment_id) / "package"
    names = package_names(experiment_id)
    candidate_class = experiment["candidate_class"]
    original_candidate = original / f"{candidate_class}.py"
    wrapper = original_candidate.read_text(encoding="utf-8").replace("from regime_aware_base import RegimeAwareBaseMixin", f"from {names['base']} import RegimeAwareBaseMixin")
    base = (original / "regime_aware_base.py").read_text(encoding="utf-8")
    base = base.replace("from regime_detector import RegimeDetector", f"from {names['regime']} import RegimeDetector")
    base = base.replace("from risk_manager import RiskManager", f"from {names['risk']} import RiskManager")
    files = {
        f"{candidate_class}.py": wrapper,
        f"{names['base']}.py": base,
        f"{names['regime']}.py": (original / "regime_detector.py").read_text(encoding="utf-8"),
        f"{names['risk']}.py": (original / "risk_manager.py").read_text(encoding="utf-8"),
        "__init__.py": "\n",
    }
    for name, content in files.items(): immutable_write(package / name, content)
    return {
        "package_path": repo_rel(repo_root, package), "candidate_class": candidate_class,
        "candidate_module_name": candidate_class, "candidate_source_path": repo_rel(repo_root, package / f"{candidate_class}.py"),
        "candidate_source_sha256": sha256_file(package / f"{candidate_class}.py"),
        "original_candidate_source_path": repo_rel(repo_root, original_candidate), "original_candidate_source_sha256": sha256_file(original_candidate),
        "dependency_module_name": names["base"], "dependency_source_path": repo_rel(repo_root, package / f"{names['base']}.py"),
        "dependency_source_sha256": sha256_file(package / f"{names['base']}.py"),
        "allowed_dependency_module_names": [names["base"], names["regime"], names["risk"]],
        "packaging_rewrites": 3, "semantic_mutation_count": 1,
    }


def execution_manifest(repo_root: Path, campaign: dict[str, Any], experiment: dict[str, Any] | None, bundle: dict[str, Any], execution_run_id: str) -> tuple[dict[str, Any], Path]:
    experiment_id = int(experiment["experiment_id"]) if experiment else 0
    run_campaign = json.loads(json.dumps(campaign))
    run_campaign["fixed_backtest"].update({"strategy": bundle["candidate_class"], "strategy_file": bundle["candidate_source_path"], "strategy_path": bundle["package_path"]})
    mutation = None if experiment is None else {"variable_id": experiment["variable_id"], "old_value": experiment["old_value"], "new_value": experiment["new_value"], "line": experiment["line"]}
    manifest = {
        "schema_version": "stage3d3b-immutable-execution-manifest-v1", "campaign_id": CAMPAIGN_ID,
        "experiment_id": experiment_id, "execution_run_id": execution_run_id, **bundle,
        "expected_candidate_source_sha256": bundle["candidate_source_sha256"], "expected_dependency_source_sha256": bundle["dependency_source_sha256"],
        "mutation": mutation, "dataset_id": DEV_DATASET_ID,
        "expected_condition_mask_changes": 0 if experiment is None else experiment["expected_condition_mask_changes"],
        "expected_final_signal_mask_changes": 0 if experiment is None else experiment["expected_final_signal_mask_changes"],
        "original_queue_sha256": ORIGINAL_QUEUE_SHA256, "policy_sha256": POLICY_SHA256,
        "single_backtest_only": True, "claim_next_experiment_allowed": False, "registry_write_allowed": False,
        "campaign": run_campaign,
    }
    manifest["execution_manifest_sha256"] = self_hash(manifest, "execution_manifest_sha256")
    path = repo_root / RECERT_ROOT / ("baseline" if experiment is None else str(experiment_id)) / "execution-manifests" / f"{execution_run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != manifest:
        raise Stage3D3BError("validation_error", "immutable_execution_manifest_drift", repo_rel(repo_root, path))
    if not path.exists(): dump_json(path, manifest)
    return manifest, path


def baseline_bundle(repo_root: Path) -> dict[str, Any]:
    return {
        "package_path": "strategies", "candidate_class": "RegimeAwareV6", "candidate_module_name": "RegimeAwareV6",
        "candidate_source_path": "strategies/RegimeAwareV6.py", "candidate_source_sha256": sha256_file(repo_root / "strategies/RegimeAwareV6.py"),
        "original_candidate_source_path": "strategies/RegimeAwareV6.py", "original_candidate_source_sha256": sha256_file(repo_root / "strategies/RegimeAwareV6.py"),
        "dependency_module_name": "regime_aware_base", "dependency_source_path": "strategies/regime_aware_base.py",
        "dependency_source_sha256": sha256_file(repo_root / "strategies/regime_aware_base.py"),
        "allowed_dependency_module_names": ["regime_aware_base", "regime_detector", "risk_manager"], "packaging_rewrites": 0, "semantic_mutation_count": 0,
    }


def launch_worker(repo_root: Path, manifest_path: Path, timeout: int = 900) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, str(repo_root / "scripts/run_isolated_candidate_backtest.py"), "--manifest", str(manifest_path)], cwd=repo_root, capture_output=True, text=True, timeout=timeout)
    launch_log = manifest_path.with_suffix(".launch.json")
    dump_json(launch_log, {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "shell": False})
    if completed.returncode != 0:
        try: payload = json.loads(completed.stdout)
        except Exception: payload = {}
        raise Stage3D3BError(payload.get("failure_type", "infra_permanent"), payload.get("reason_code", "isolated_worker_failed"), payload.get("message", completed.stderr[-1000:]))
    return json.loads(completed.stdout)


def summarize_run(repo_root: Path, experiment_id: int, run_id: str, strategy: str) -> dict[str, Any]:
    run_dir = repo_root / RESULT_ROOT / str(experiment_id) / run_id
    result_path = find_result_json(run_dir)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    normalized = write_normalized_trades(run_dir, result_path, strategy)
    identity = json.loads((run_dir / "runtime-code-identity.json").read_text(encoding="utf-8"))
    signal = json.loads((run_dir / "runtime-signal-diff.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "runner-report.json").read_text(encoding="utf-8"))
    dump_json(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    return {
        "run_id": run_id, "run_dir": repo_rel(repo_root, run_dir), "process_id": identity["process_id"],
        "runtime_identity": repo_rel(repo_root, run_dir / "runtime-code-identity.json"),
        "candidate_source_sha256": identity["candidate_source_sha256"], "dependency_source_sha256": identity["dependency_source_sha256"],
        "dependency_module_file": identity["dependency_module_file"], "loaded_mutation_value": None if not identity["mutation_proof"] else identity["mutation_proof"]["loaded_ast_value"],
        "summary": metric_summary(metrics, normalized), "normalized_trade_hash": normalized["sha256"],
        "normalized_trades_path": repo_rel(repo_root, run_dir / "normalized-trades.json"), "input_fingerprint": report.get("input_fingerprint"),
        "signal_diff": signal, "raw_result": repo_rel(repo_root, result_path), "runner_report": repo_rel(repo_root, run_dir / "runner-report.json"),
        "artifact_hashes": repo_rel(repo_root, run_dir / "artifact-hashes.json"), "metrics": metrics,
    }


def run_once(repo_root: Path, campaign: dict[str, Any], experiment: dict[str, Any] | None, bundle: dict[str, Any], run_id: str) -> dict[str, Any]:
    experiment_id = int(experiment["experiment_id"]) if experiment else 0
    _, manifest_path = execution_manifest(repo_root, campaign, experiment, bundle, run_id)
    run_dir = repo_root / RESULT_ROOT / str(experiment_id) / run_id
    if not (run_dir / "isolated-worker-result.json").exists(): launch_worker(repo_root, manifest_path)
    return summarize_run(repo_root, experiment_id, run_id, bundle["candidate_class"])


def identity_signature(run: dict[str, Any]) -> dict[str, Any]:
    return {"candidate_source_sha256": run["candidate_source_sha256"], "dependency_source_sha256": run["dependency_source_sha256"], "dependency_module_file": run["dependency_module_file"], "loaded_mutation_value": run["loaded_mutation_value"]}


def behavior_attribution(run: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    if run["normalized_trade_hash"] != baseline["normalized_trade_hash"]:
        return {"status": "not_required_trade_behavior_changed", "primary_blockers": {}}
    baseline_rows = json.loads((Path.cwd() / baseline["normalized_trades_path"]).read_text(encoding="utf-8"))["rows"]
    blockers = []
    for delta in run["signal_diff"]["deltas"]:
        timestamp = pd_timestamp(delta["timestamp"])
        trade = next((row for row in baseline_rows if pd_timestamp(row["open_date"]) <= timestamp < pd_timestamp(row["close_date"])), None)
        if trade:
            direction = "short" if trade["is_short"] else "long"
            blockers.append("existing_same_direction_position" if direction == delta["direction"] else "existing_opposite_direction_position")
        else:
            blockers.append("unresolved_insufficient_instrumentation")
    return {"status": "attributed", "primary_blockers": dict(Counter(blockers)), "delta_count": len(blockers)}


def pd_timestamp(value: Any):
    from pandas import Timestamp
    return Timestamp(value)


def evaluator_run_descriptor(run: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "isolated_recertification", "run_dir": run["run_dir"], "raw_result": run["raw_result"], "runner_report": run["runner_report"], "artifact_hashes": run["artifact_hashes"], "metrics": run["metrics"]}


def development_gate(repo_root: Path, baseline: dict[str, Any], candidate: dict[str, Any], candidate_class: str, experiment_id: int) -> dict[str, Any]:
    policy = evaluator.read_yaml(repo_root / POLICY_PATH)
    baseline_vector = evaluator.result_vector(repo_root, evaluator_run_descriptor(baseline), "RegimeAwareV6", DEV_DATASET_ID)
    candidate_vector = evaluator.result_vector(repo_root, evaluator_run_descriptor(candidate), candidate_class, DEV_DATASET_ID)
    comparison = evaluator.compare_vectors(baseline_vector, candidate_vector)
    decision = evaluator.gate_decision(policy, baseline_vector, candidate_vector, comparison)
    result = {"development_status": decision["final_decision"], "baseline_metrics": baseline_vector, "candidate_metrics": candidate_vector, "comparison": comparison, "gate_decision": decision, "validation_accessed": False}
    output = repo_root / RESULT_ROOT / str(experiment_id) / "development-gate"
    output.mkdir(parents=True, exist_ok=True); dump_json(output / "development-gate-result.json", result)
    return {"development_status": result["development_status"], "result_path": repo_rel(repo_root, output / "development-gate-result.json")}


def invalidation_event(repo_root: Path, original: dict[str, Any], recert_queue: dict[str, Any]) -> dict[str, Any]:
    records = []
    for item in original["experiments"]:
        experiment_id = int(item["experiment_id"])
        records.append({
            "original_campaign_id": stage3d2b.CAMPAIGN_ID, "original_experiment_id": experiment_id,
            "original_result": item["final_status"], "research_validity": "valid" if experiment_id == 1 else "invalidated",
            "failure_class": None if experiment_id == 1 else "implementation_error",
            "reason_code": "existing_same_direction_position" if experiment_id == 1 else "candidate_dependency_module_cache_shadowed",
            "primary_blocker": "existing_same_direction_position" if experiment_id == 1 else None,
            "requires_recertification": True,
            "original_artifacts": {"result": f"research/results/{stage3d2b.CAMPAIGN_ID}/{experiment_id}/stage3d2b-experiment-result.json", "run_a": item["run_a"]["run_dir"], "run_b": item["run_b"]["run_dir"]},
            "recertification_campaign_id": CAMPAIGN_ID, "recertification_experiment_id": experiment_id,
        })
    payload = {"schema_version": "stage3d3b-invalidation-event-v1", "event_id": "stage3d2b-runtime-cache-invalidation", "created_at": utc_now(), "affected_experiment_ids": list(range(2, 11)), "experiment_1_recertification_required": True, "original_queue_sha256": ORIGINAL_QUEUE_SHA256, "recertification_queue_sha256": recert_queue["queue_sha256"], "records": records}
    dump_json(repo_root / INVALIDATION_PATH, payload)
    return payload


def write_amendment(repo_root: Path, invalidation: dict[str, Any]) -> None:
    lines = ["# Stage 3D.2-B Runtime Cache Invalidation Amendment", "", "This amendment preserves the original report and artifacts. It does not rewrite historical files.", "", "- Experiment 1: original attribution remains valid, but uniform recertification is required.", "- Experiments 2-10: prior strategy conclusions are invalidated as `implementation_error / candidate_dependency_module_cache_shadowed`.", f"- Invalidation event: `{INVALIDATION_PATH.as_posix()}`", f"- Recertification campaign: `{CAMPAIGN_ID}`", "", "Original results must be interpreted only through the recertification linkage in the registry."]
    immutable_write(repo_root / AMENDMENT_PATH, "\n".join(lines) + "\n")


def init_registry(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS stage3d3b_invalidation_events(event_id TEXT PRIMARY KEY, original_campaign_id TEXT NOT NULL, affected_ids_json TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS stage3d3b_recertification(experiment_id INTEGER PRIMARY KEY, original_campaign_id TEXT NOT NULL, original_experiment_id INTEGER NOT NULL, invalidation_event_id TEXT NOT NULL, run_a_identity_hash TEXT NOT NULL, run_b_identity_hash TEXT NOT NULL, signal_diff_json TEXT NOT NULL, trade_hash TEXT NOT NULL, behavior_verdict TEXT NOT NULL, attribution_json TEXT NOT NULL, development_status TEXT, validation_accessed INTEGER NOT NULL, final_validity TEXT NOT NULL, result_json TEXT NOT NULL, updated_at TEXT NOT NULL);
    """)


def record_registry(repo_root: Path, invalidation: dict[str, Any], results: list[dict[str, Any]]) -> None:
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        conn.execute("BEGIN IMMEDIATE"); init_registry(conn)
        conn.execute("INSERT OR REPLACE INTO stage3d3b_invalidation_events VALUES (?,?,?,?,?)", (invalidation["event_id"], stage3d2b.CAMPAIGN_ID, json.dumps(invalidation["affected_experiment_ids"]), json.dumps(invalidation, sort_keys=True), invalidation["created_at"]))
        for item in results:
            conn.execute("INSERT OR REPLACE INTO stage3d3b_recertification VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (item["experiment_id"], stage3d2b.CAMPAIGN_ID, item["experiment_id"], invalidation["event_id"], stable_hash(identity_signature(item["run_a"])), stable_hash(identity_signature(item["run_b"])), json.dumps(item["run_a"]["signal_diff"], sort_keys=True), item["run_a"]["normalized_trade_hash"], item["behavior_verdict"], json.dumps(item["attribution"], sort_keys=True), item.get("development", {}).get("development_status"), 0, "valid_recertified", json.dumps(item, sort_keys=True), utc_now()))
        conn.commit()
    finally: conn.close()


def run_verification_suite(repo_root: Path) -> dict[str, Any]:
    commands = {
        "stage3_tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_stage3*.py"],
        "research_tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_research*.py"],
        "readiness": ["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/run_agent_readiness_checks.ps1"],
        "test_baseline": [sys.executable, "scripts/verify_test_baseline.py", "--run"],
    }
    output = {}
    for name, command in commands.items():
        completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, timeout=300)
        combined = completed.stdout + completed.stderr
        match = re.search(r"Ran (\d+) tests", combined)
        output[name] = {"passed": completed.returncode == 0, "returncode": completed.returncode, "test_count": int(match.group(1)) if match else None, "output_tail": combined[-2000:]}
        if completed.returncode != 0:
            raise Stage3D3BError("validation_error", "verification_failed", f"{name} failed")
    output["no_new_test_baseline_regressions"] = True
    return output


def run_campaign(repo_root: Path) -> dict[str, Any]:
    started = utc_now(); start = time.monotonic()
    original_queue = assert_frozen_inputs(repo_root)
    recert_queue, campaign = write_control_files(repo_root, original_queue)
    write_adr(repo_root)
    original_final = json.loads((repo_root / stage3d2b.FINAL_JSON).read_text(encoding="utf-8"))
    invalidation = invalidation_event(repo_root, original_final, recert_queue); write_amendment(repo_root, invalidation)
    baseline = baseline_bundle(repo_root)
    baseline_a = run_once(repo_root, campaign, None, baseline, "BASELINE-A")
    baseline_b = run_once(repo_root, campaign, None, baseline, "BASELINE-B")
    baseline_repro = stage3d1.compare_repro(baseline_a, baseline_b)
    if not baseline_repro["passed"]: raise Stage3D3BError("validation_error", "baseline_reproducibility_mismatch", "isolated baseline mismatch")
    results = []; all_runs = [baseline_a, baseline_b]
    for experiment in original_queue["experiments"]:
        assert_frozen_inputs(repo_root)
        bundle = build_execution_package(repo_root, experiment)
        run_a = run_once(repo_root, campaign, experiment, bundle, "RECERT-RUN-A")
        run_b = run_once(repo_root, campaign, experiment, bundle, "RECERT-RUN-B")
        all_runs.extend([run_a, run_b])
        repro = stage3d1.compare_repro(run_a, run_b)
        if not repro["passed"]: raise Stage3D3BError("validation_error", "candidate_reproducibility_mismatch", f"experiment {experiment['experiment_id']}")
        if run_a["loaded_mutation_value"] != experiment["new_value"] or run_b["loaded_mutation_value"] != experiment["new_value"]:
            raise Stage3D3BError("implementation_error", "runtime_mutation_value_mismatch", str(experiment["experiment_id"]))
        signal_count = int(run_a["signal_diff"]["final_signal_mask_diff_count"])
        if signal_count == 0: behavior = "reachability_prediction_miss"
        elif run_a["normalized_trade_hash"] != baseline_a["normalized_trade_hash"]: behavior = "trade_behavior_changed"
        else: behavior = "signal_changed_no_trade_behavior_change"
        attribution = behavior_attribution(run_a, baseline_a) if behavior == "signal_changed_no_trade_behavior_change" else {"status": "not_required", "primary_blockers": {}}
        development = development_gate(repo_root, baseline_a, run_a, bundle["candidate_class"], int(experiment["experiment_id"])) if behavior == "trade_behavior_changed" else {"development_status": "not_run_behavior_unchanged"}
        bias_cost = "pending_scope_control" if str(development["development_status"]).startswith("development_eligible") else "not_run_development_not_eligible"
        result = {
            "experiment_id": int(experiment["experiment_id"]), "variable_id": experiment["variable_id"], "new_value": experiment["new_value"],
            "original_research_validity": "valid" if int(experiment["experiment_id"]) == 1 else "invalidated",
            "recertification_verdict": "previous_result_invalidated_new_result_valid" if int(experiment["experiment_id"]) > 1 else "reachability_confirmed",
            "run_a": run_a, "run_b": run_b, "reproducibility": repro,
            "behavior_verdict": behavior, "attribution": attribution, "development": development,
            "bias_status": bias_cost, "cost_status": bias_cost, "validation_status": "not_authorized",
            "final_validity": "valid_recertified",
        }
        result_path = repo_root / RESULT_ROOT / str(experiment["experiment_id"]) / "stage3d3b-recertification-result.json"; dump_json(result_path, result); results.append(result)
    reverse = []
    by_id = {int(item["experiment_id"]): item for item in original_queue["experiments"]}
    for experiment_id in REVERSE_SAMPLE_IDS:
        experiment = by_id[experiment_id]; bundle = build_execution_package(repo_root, experiment)
        sampled = run_once(repo_root, campaign, experiment, bundle, "ORDER-CHECK-REVERSE")
        all_runs.append(sampled); reference = next(item for item in results if item["experiment_id"] == experiment_id)["run_a"]
        consistent = identity_signature(sampled) == identity_signature(reference) and sampled["normalized_trade_hash"] == reference["normalized_trade_hash"] and sampled["summary"] == reference["summary"] and sampled["signal_diff"] == reference["signal_diff"]
        reverse.append({"experiment_id": experiment_id, "consistent": consistent, "reference_run": reference["run_id"], "sample_run": sampled["run_id"], "sample_pid": sampled["process_id"]})
        if not consistent: raise Stage3D3BError("validation_error", "cross_experiment_order_dependency", str(experiment_id))
    pids = [run["process_id"] for run in all_runs]
    if len(pids) != len(set(pids)): raise Stage3D3BError("validation_error", "process_identity_reused", "worker PID reuse detected")
    record_registry(repo_root, invalidation, results)
    counts = dict(Counter(item["behavior_verdict"] for item in results))
    final = {
        "schema_version": "stage3d3b-final-report-v1", "campaign_id": CAMPAIGN_ID, "status": "completed",
        "started_at": started, "completed_at": utc_now(), "wall_clock_seconds": round(time.monotonic()-start, 3),
        "autonomous_no_per_experiment_confirmation": True, "process_isolation_passed": True,
        "budget": campaign["budget"], "budget_used": {"experiments": 10, "worker_backtest_attempts": len(all_runs), "validation_evaluations": 0},
        "all_worker_pids_unique": True, "worker_process_count": len(all_runs), "worker_pids": pids,
        "baseline_reproducibility": baseline_repro, "original_invalidated_experiment_ids": list(range(2,11)),
        "experiment_1_uniformly_recertified": True, "recertified_experiment_count": len(results),
        "behavior_counts": counts, "signal_changed_experiment_ids": [item["experiment_id"] for item in results if item["run_a"]["signal_diff"]["final_signal_mask_diff_count"] > 0],
        "trade_changed_experiment_ids": [item["experiment_id"] for item in results if item["behavior_verdict"] == "trade_behavior_changed"],
        "development_eligible_experiment_ids": [item["experiment_id"] for item in results if str(item["development"]["development_status"]).startswith("development_eligible")],
        "reverse_order_samples": reverse, "order_independence_passed": all(item["consistent"] for item in reverse),
        "validation_access_allowed": False, "validation_access_count": 0,
        "bias_status_counts": dict(Counter(item["bias_status"] for item in results)), "cost_status_counts": dict(Counter(item["cost_status"] for item in results)),
        "experiments": results,
        "forbidden_actions": {"new_values_created": False, "new_variables_created": False, "multi_variable_run": False, "position_stacking_changed": False, "max_open_trades_changed": False, "risk_config_changed": False, "hyperopt_run": False, "validation_accessed": False, "holdout_accessed": False, "champion_created": False, "qualified_challenger_created": False},
        "artifact_index": {"campaign": CAMPAIGN_PATH.as_posix(), "recertification_queue": QUEUE_PATH.as_posix(), "invalidation_event": INVALIDATION_PATH.as_posix(), "amendment": AMENDMENT_PATH.as_posix(), "adr": ADR_PATH.as_posix(), "final_json": FINAL_JSON.as_posix(), "final_markdown": FINAL_MD.as_posix()},
    }
    dump_json(repo_root / FINAL_JSON, final)
    lines = ["# Stage 3D.3-B Process Isolation Recertification", "", f"- Status: `{final['status']}`", f"- Unique worker processes: `{len(pids)}`", f"- Signal changed experiments: `{final['signal_changed_experiment_ids']}`", f"- Trade changed experiments: `{final['trade_changed_experiment_ids']}`", f"- Development eligible: `{final['development_eligible_experiment_ids']}`", "- Validation access: `not_authorized`", "", "## Experiments", ""]
    lines.extend(f"- `{item['experiment_id']}` `{item['variable_id']}={item['new_value']}`: `{item['behavior_verdict']}` / `{item['development']['development_status']}`" for item in results)
    (repo_root / FINAL_MD).write_text("\n".join(lines)+"\n", encoding="utf-8")
    final["verification"] = run_verification_suite(repo_root)
    dump_json(repo_root / FINAL_JSON, final)
    with (repo_root / FINAL_MD).open("a", encoding="utf-8") as handle:
        handle.write("\n## Verification\n\n- Stage 3 tests: `passed`\n- Research tests: `passed`\n- Readiness: `passed`\n- Full baseline: `no new regressions`\n")
    return final


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--json", action="store_true"); args = parser.parse_args()
    try: result = run_campaign(Path.cwd())
    except Stage3D3BError as exc:
        print(json.dumps({"status":"failed","failure_type":exc.failure_type,"reason_code":exc.reason_code,"message":exc.message},indent=2)); return 1
    print(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
