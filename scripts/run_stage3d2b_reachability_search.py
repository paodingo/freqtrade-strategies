#!/usr/bin/env python3
"""Run the frozen Stage 3D.2-B reachability-informed search campaign."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import analyze_strategy_signal_reachability as reachability
import evaluate_research_candidate as evaluator
import run_stage3d1_bounded_search as stage3d1
from create_candidate_strategy import BASE_STRATEGY_NAME, BASE_STRATEGY_PATH, BASE_STRATEGY_SHA256
from research_control import load_simple_yaml, utc_now
from run_experiment import dump_json, dump_manifest, repo_rel, sha256_file


CAMPAIGN_ID = "stage3d2b-reachability-informed-batch1"
CAMPAIGN_PATH = Path("research/campaigns/active/stage3d2b-reachability-informed-batch1.yaml")
SEARCH_SPACE_PATH = Path("research/search-spaces/regime-aware-safe-mutations-v2-batch1.yaml")
PARENT_PROPOSAL_PATH = Path("research/search-spaces/regime-aware-safe-mutations-v2-proposal.yaml")
QUEUE_PATH = Path("research/queues/stage3d2b-batch1-experiments.yaml")
RESULT_ROOT = Path("research/results") / CAMPAIGN_ID
FINAL_JSON = RESULT_ROOT / "stage3d2b-final-report.json"
FINAL_MD = RESULT_ROOT / "stage3d2b-final-report.md"
POLICY_PATH = Path("research/evaluation/evaluation-policy.yaml")
POLICY_HASH = "aa1798f7eb002ed30ad5fff95be48f3a08bc42e54f6b0f9406cd39412b9cff71"
PARENT_PROPOSAL_HASH = "f79e5a1f216c8f1a64e0d7ed326b39c974121815191883fa13024794ab0cffbb"
BASELINE_TRADE_HASH = "c4b4ce5a34a1385f7ce05e1b6ceb249415574ef2c3d3cb9c7d284050450e4219"
BASELINE_RUNNER_TRADE_HASH = "94de8d81bea16a648a6f9a3e2c379cefde16e8240b71293ff724d19aecf45559"
DEV_DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
VAL_DATASET_ID = "futures-validation-btc-usdt-usdt-20240912-20250128-v2"
APPROVAL_TIMESTAMP = "2026-07-11T00:00:00+08:00"

APPROVED_ORDER = [
    ("ranging_long_setup.rsi_max", 41.10393009),
    ("ranging_long_setup.rsi_max", 42.42420359),
    ("ranging_long_setup.rsi_max", 45.0),
    ("ranging_short_setup.bb_percent_min", 0.79578426),
    ("ranging_short_setup.bb_percent_min", 0.75),
    ("ranging_short_setup.rsi_min", 57.29961157),
    ("ranging_short_setup.rsi_min", 56.88531804),
    ("ranging_short_setup.rsi_min", 55.0),
    ("ranging_shared.adx_4h_max_long", 22.16370727),
    ("ranging_shared.adx_4h_max_long", 22.90931181),
]

EXCLUDED_VALUES = [
    {"variable_id": "ranging_long_setup.rsi_max", "value": 45.42615404},
    {"variable_id": "ranging_short_setup.bb_percent_min", "value": 0.7},
    {"variable_id": "ranging_short_setup.rsi_min", "value": 53.32193184},
    {"variable_id": "ranging_shared.adx_4h_max_long", "value": 27.03320126},
    {"variable_id": "ranging_shared.adx_4h_max_long", "value": 27.42479576},
]

FORBIDDEN_VARIABLES = [
    "ranging_long_setup.bb_percent_max",
    "ranging_long_setup.ema200_multiplier_min",
    "ranging_shared.bb_width_4h_multiplier_max_long",
    "ranging_shared.bb_width_4h_multiplier_max_short",
]


class Stage3D2BError(RuntimeError):
    def __init__(self, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def self_hash(payload: dict[str, Any], field: str) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != field})


def configure_stage3d1_adapter() -> None:
    stage3d1.CAMPAIGN_ID = CAMPAIGN_ID
    stage3d1.CAMPAIGN_PATH = CAMPAIGN_PATH
    stage3d1.CATALOG_PATH = SEARCH_SPACE_PATH
    stage3d1.QUEUE_PATH = QUEUE_PATH
    stage3d1.RESULT_ROOT = RESULT_ROOT
    stage3d1.FINAL_JSON = FINAL_JSON
    stage3d1.FINAL_MD = FINAL_MD
    stage3d1.mutate_source = mutate_source_exact


def assert_frozen_inputs(repo_root: Path, search_space: dict[str, Any] | None = None, queue: dict[str, Any] | None = None) -> None:
    actual_strategy = sha256_file(repo_root / BASE_STRATEGY_PATH).upper()
    if actual_strategy != BASE_STRATEGY_SHA256:
        raise Stage3D2BError("validation_error", "input_integrity_violation", "official strategy hash changed")
    policy = evaluator.read_yaml(repo_root / POLICY_PATH)
    if policy.get("policy_sha256") != POLICY_HASH or evaluator.canonical_policy_hash(policy) != POLICY_HASH:
        raise Stage3D2BError("validation_error", "input_integrity_violation", "evaluation policy hash changed")
    proposal = load_simple_yaml(repo_root / PARENT_PROPOSAL_PATH)
    if proposal.get("proposal_sha256") != PARENT_PROPOSAL_HASH or self_hash(proposal, "proposal_sha256") != PARENT_PROPOSAL_HASH:
        raise Stage3D2BError("validation_error", "input_integrity_violation", "parent proposal hash changed")
    for dataset_id in (DEV_DATASET_ID, VAL_DATASET_ID):
        manifest = repo_root / "research/data/snapshots" / dataset_id / "manifest.yaml"
        if not manifest.exists():
            raise Stage3D2BError("validation_error", "input_integrity_violation", f"missing dataset manifest: {dataset_id}")
    if search_space and self_hash(search_space, "search_space_sha256") != search_space.get("search_space_sha256"):
        raise Stage3D2BError("validation_error", "input_integrity_violation", "approved search-space hash changed")
    if queue and (not queue.get("queue_frozen") or self_hash(queue, "queue_sha256") != queue.get("queue_sha256")):
        raise Stage3D2BError("validation_error", "frozen_queue_drift", "frozen queue hash changed")


def proposal_index(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["variable_id"]: item for item in proposal["proposed_variables"]}


def approved_value_set() -> set[tuple[str, str]]:
    return {(variable, str(value)) for variable, value in APPROVED_ORDER}


def build_search_space(repo_root: Path) -> dict[str, Any]:
    proposal = load_simple_yaml(repo_root / PARENT_PROPOSAL_PATH)
    indexed = proposal_index(proposal)
    grouped: dict[str, list[Any]] = {}
    for variable_id, value in APPROVED_ORDER:
        grouped.setdefault(variable_id, []).append(value)
    variables = []
    for variable_id, values in grouped.items():
        source = indexed[variable_id]
        suggested = {str(item["value"]): item for item in source["suggested_values"]}
        variables.append(
            {
                "variable_id": variable_id,
                "approved_values": values,
                "source_path": source["source_path"],
                "source_location": {"line": source["line"]},
                "ast_selector": {
                    "node_type": "Constant",
                    "line": source["line"],
                    "old_value": source["current_value"],
                    "expected_match_count": 1,
                },
                "current_baseline_value": source["current_value"],
                "condition_id": source["condition_id"],
                "reachability_evidence": "research/analysis/stage3d2a-counterfactual-signal-reachability.json",
                "single_blocker_evidence": {
                    "source": "research/analysis/stage3d2a-condition-coverage.json",
                    "count": source["single_blocker_count"],
                },
                "expected_changes": [
                    {
                        "value": value,
                        "condition_mask_candles": suggested[str(value)]["condition_mask_change_estimate"],
                        "final_signal_mask_candles": suggested[str(value)]["signal_mask_change_estimate"],
                    }
                    for value in values
                ],
                "risk_classification": source["risk_level"],
                "requires_multi_variable": False,
            }
        )
    payload = {
        "schema_version": "stage3d2b-approved-search-space-v1",
        "search_space_id": "regime-aware-safe-mutations-v2-batch1",
        "parent_proposal_id": proposal["proposal_id"],
        "parent_proposal_sha256": PARENT_PROPOSAL_HASH,
        "approval_status": "approved",
        "approver_type": "human_user",
        "approval_scope": "stage3d2b_batch1_only",
        "approval_timestamp": APPROVAL_TIMESTAMP,
        "base_strategy": BASE_STRATEGY_NAME,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "policy_sha256": POLICY_HASH,
        "development_dataset_id": DEV_DATASET_ID,
        "approved_variables": variables,
        "excluded_values": EXCLUDED_VALUES,
        "explicitly_forbidden_variables": FORBIDDEN_VARIABLES,
        "automatic_value_domain_expansion": False,
        "adaptive_search": False,
    }
    payload["search_space_sha256"] = self_hash(payload, "search_space_sha256")
    return payload


def candidate_class_name(experiment_id: int) -> str:
    return f"RegimeAware_C3D2B_E{experiment_id:04d}"


def queue_fingerprint(item: dict[str, Any], search_space_hash: str) -> str:
    return stable_hash(
        {
            "experiment_id": item["experiment_id"],
            "variable_id": item["variable_id"],
            "source_path": item["source_path"],
            "line": item["line"],
            "old_value": item["old_value"],
            "new_value": item["new_value"],
            "semantic_mutation_count": 1,
            "search_space_sha256": search_space_hash,
            "policy_sha256": POLICY_HASH,
            "base_strategy_sha256": BASE_STRATEGY_SHA256,
        }
    )


def build_queue(search_space: dict[str, Any]) -> dict[str, Any]:
    variables = {item["variable_id"]: item for item in search_space["approved_variables"]}
    experiments = []
    fingerprints: set[str] = set()
    for experiment_id, (variable_id, value) in enumerate(APPROVED_ORDER, start=1):
        variable = variables[variable_id]
        expected = next(item for item in variable["expected_changes"] if str(item["value"]) == str(value))
        item = {
            "experiment_id": experiment_id,
            "status": "queued",
            "variable_id": variable_id,
            "source_path": variable["source_path"],
            "source_file": Path(variable["source_path"]).name,
            "line": variable["source_location"]["line"],
            "old_value": variable["current_baseline_value"],
            "new_value": value,
            "semantic_mutation_count": 1,
            "candidate_class": candidate_class_name(experiment_id),
            "expected_condition_mask_changes": expected["condition_mask_candles"],
            "expected_final_signal_mask_changes": expected["final_signal_mask_candles"],
        }
        item["fingerprint"] = queue_fingerprint(item, search_space["search_space_sha256"])
        if item["fingerprint"] in fingerprints:
            raise Stage3D2BError("validation_error", "duplicate_frozen_experiment", variable_id)
        fingerprints.add(item["fingerprint"])
        experiments.append(item)
    payload = {
        "schema_version": "stage3d2b-frozen-experiment-queue-v1",
        "campaign_id": CAMPAIGN_ID,
        "queue_frozen": True,
        "search_space_id": search_space["search_space_id"],
        "search_space_sha256": search_space["search_space_sha256"],
        "policy_sha256": POLICY_HASH,
        "experiments": experiments,
        "adaptive_followups_allowed": False,
    }
    payload["queue_sha256"] = self_hash(payload, "queue_sha256")
    return payload


def build_campaign(search_space: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID,
        "mode": "bounded_autonomous_search",
        "runner_type": "stage3d2b_reachability_informed_search",
        "scope": {
            "allowed_paths": [
                f"research/candidates/{CAMPAIGN_ID}/**",
                f"research/experiments/{CAMPAIGN_ID}/**",
                f"research/results/{CAMPAIGN_ID}/**",
                SEARCH_SPACE_PATH.as_posix(),
                QUEUE_PATH.as_posix(),
                CAMPAIGN_PATH.as_posix(),
                "research/registry/research.db",
            ],
            "blocked_paths": [
                ".env", "secrets/**", "deploy/**", "user_data/config_live.json",
                "configs/production/**", "scripts/start_bot.sh", "scripts/refresh_data.sh",
                "strategies/**", "research/data/snapshots/**", "research/evaluation/evaluation-policy.yaml",
            ],
        },
        "budget": {
            "max_experiments": 10,
            "max_total_attempts": 26,
            "max_retries_per_experiment": 1,
            "max_wall_clock_hours": 12,
            "max_wall_clock_minutes": 720,
            "max_consecutive_infrastructure_failures": 3,
            "max_consecutive_failures": 3,
            "max_validation_evaluations": 2,
        },
        "autonomy": {
            "automatically_claim_next": True,
            "automatically_generate_hypotheses": False,
            "automatically_generate_followup_tasks": False,
            "automatically_promote_champion": False,
            "access_sealed_holdout": False,
            "lease_seconds": 900,
        },
        "approved_search_space": {"path": SEARCH_SPACE_PATH.as_posix(), "sha256": search_space["search_space_sha256"]},
        "frozen_queue": {"path": QUEUE_PATH.as_posix(), "sha256": queue["queue_sha256"]},
        "fixed_backtest": {
            "runtime_config": "research/runtime/freqtrade-runtime.yaml",
            "dataset_id": DEV_DATASET_ID,
            "dataset_manifest": f"research/data/snapshots/{DEV_DATASET_ID}/manifest.yaml",
            "subcommand": "sealed_offline_backtest",
            "strategy": BASE_STRATEGY_NAME,
            "strategy_file": BASE_STRATEGY_PATH.as_posix(),
            "strategy_path": "strategies",
            "config": "research/runtime/demo-futures-backtest-config.json",
            "timerange": "20240101-20240830",
            "timeframe": "1h",
            "pairs": ["BTC/USDT:USDT"],
            "fee": "0.0004",
            "datadir": f"research/data/snapshots/{DEV_DATASET_ID}/data",
            "timeout_seconds": 600,
            "acceptance_gate": {},
        },
        "sealed_offline_backtest": {
            "exchange_snapshot": "research/exchange_snapshots/binance-usdm-futures-2025-8-demo",
            "network_policy": "socket_blocker",
        },
        "evaluation_policy": {"policy_id": "balanced-research-gate-v1", "policy_sha256": POLICY_HASH},
        "validation": {"dataset_id": VAL_DATASET_ID, "max_completed_evaluations": 2, "result_feedback_to_queue": False},
        "stop_conditions": [
            "queue_complete", "wall_clock_exceeded", "input_integrity_violation",
            "consecutive_infrastructure_failures", "guard_violation", "operator_stop",
        ],
        "forbidden_actions": [
            "hyperopt", "adaptive_search", "holdout_access", "qualified_challenger",
            "champion", "forward_dry_run", "private_api", "non_loopback_network",
        ],
    }


def validate_approval(search_space: dict[str, Any], queue: dict[str, Any]) -> None:
    if search_space.get("approval_status") != "approved" or search_space.get("approval_scope") != "stage3d2b_batch1_only":
        raise Stage3D2BError("validation_error", "search_space_not_approved", "batch approval is missing")
    actual = {(item["variable_id"], str(value)) for item in search_space["approved_variables"] for value in item["approved_values"]}
    if actual != approved_value_set():
        raise Stage3D2BError("validation_error", "unapproved_mutation_value", "approved values differ from human decision")
    if any(item["variable_id"] in FORBIDDEN_VARIABLES for item in queue["experiments"]):
        raise Stage3D2BError("validation_error", "forbidden_multi_variable_dependency", "forbidden variable in queue")
    if len(queue["experiments"]) != 10 or [int(item["experiment_id"]) for item in queue["experiments"]] != list(range(1, 11)):
        raise Stage3D2BError("validation_error", "frozen_queue_order_invalid", "queue order is not 1..10")
    for item, approved in zip(queue["experiments"], APPROVED_ORDER):
        if (item["variable_id"], str(item["new_value"])) != (approved[0], str(approved[1])) or item["semantic_mutation_count"] != 1:
            raise Stage3D2BError("validation_error", "frozen_queue_content_invalid", str(item["experiment_id"]))


def write_control_files(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    expected_search = build_search_space(repo_root)
    expected_queue = build_queue(expected_search)
    expected_campaign = build_campaign(expected_search, expected_queue)
    for path, expected, hash_field in (
        (SEARCH_SPACE_PATH, expected_search, "search_space_sha256"),
        (QUEUE_PATH, expected_queue, "queue_sha256"),
    ):
        target = repo_root / path
        if target.exists():
            actual = load_simple_yaml(target)
            if actual != expected or self_hash(actual, hash_field) != actual.get(hash_field):
                raise Stage3D2BError("validation_error", "frozen_control_file_drift", path.as_posix())
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            dump_manifest(target, expected)
    campaign_target = repo_root / CAMPAIGN_PATH
    if campaign_target.exists() and load_simple_yaml(campaign_target) != expected_campaign:
        raise Stage3D2BError("validation_error", "frozen_control_file_drift", CAMPAIGN_PATH.as_posix())
    if not campaign_target.exists():
        campaign_target.parent.mkdir(parents=True, exist_ok=True)
        dump_manifest(campaign_target, expected_campaign)
    validate_approval(expected_search, expected_queue)
    assert_frozen_inputs(repo_root, expected_search, expected_queue)
    return expected_campaign, expected_search, expected_queue


def mutate_source_exact(source: str, experiment: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tree = ast.parse(source)
    matches = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.lineno == int(experiment["line"]) and node.value == experiment["old_value"]
    ]
    if len(matches) != 1:
        raise Stage3D2BError("implementation_error", "unauthorized_candidate_semantic_diff", f"AST matches={len(matches)}")
    node = matches[0]
    lines = source.splitlines(keepends=True)
    new_text = repr(experiment["new_value"])
    lines[node.lineno - 1] = lines[node.lineno - 1][:node.col_offset] + new_text + lines[node.lineno - 1][node.end_col_offset:]
    mutated = "".join(lines)
    reparsed = ast.parse(mutated)
    changed = [
        item for item in ast.walk(reparsed)
        if isinstance(item, ast.Constant) and item.lineno == int(experiment["line"]) and item.value == experiment["new_value"]
    ]
    if len(changed) != 1:
        raise Stage3D2BError("implementation_error", "unauthorized_candidate_semantic_diff", "new AST value is not unique")
    return mutated, {
        "file": experiment["source_file"], "lineno": node.lineno,
        "col_offset": node.col_offset, "end_lineno": node.end_lineno,
        "end_col_offset": node.end_col_offset, "old_value": experiment["old_value"],
        "new_value": experiment["new_value"], "semantic_mutation_count": 1,
    }


def reachability_preflight(df: Any, experiment: dict[str, Any]) -> dict[str, Any]:
    specs = reachability.condition_specs()
    groups = reachability.signal_groups()
    condition_id = reachability.variable_condition_map(specs).get(experiment["variable_id"])
    if not condition_id:
        raise Stage3D2BError("validation_error", "reachability_mapping_missing", experiment["variable_id"])
    masks = reachability.condition_mask_map(df, specs)
    spec = specs[condition_id]
    comparison = spec.comparison or {}
    values = reachability.comparable_series(df, comparison)
    new_condition = reachability.threshold_mask(values, comparison["operator"], float(experiment["new_value"])).fillna(False)
    old_condition = masks[condition_id]
    by_group: dict[str, int] = {}
    for group_id, group in groups.items():
        if condition_id not in group.conditions:
            continue
        old_group = reachability.group_mask(group, masks)
        new_group = reachability.group_mask(group, masks, (condition_id, new_condition))
        by_group[group_id] = int((old_group ^ new_group).sum())
    actual_condition = int((old_condition ^ new_condition).sum())
    actual_final = int(sum(by_group.values()))
    return {
        "condition_id": condition_id,
        "predicted_condition_mask_changes": int(experiment["expected_condition_mask_changes"]),
        "actual_condition_mask_changes": actual_condition,
        "predicted_final_signal_mask_changes": int(experiment["expected_final_signal_mask_changes"]),
        "actual_final_signal_mask_changes": actual_final,
        "final_signal_changes_by_group": by_group,
        "prediction_classification_accurate": (
            actual_condition == int(experiment["expected_condition_mask_changes"])
            and actual_final == int(experiment["expected_final_signal_mask_changes"])
        ),
        "status": "reachable" if actual_final > 0 else "reachability_prediction_miss",
    }


def classify_trade_behavior(run_a: dict[str, Any]) -> dict[str, Any]:
    # The evaluator and runner use different canonical envelopes. Compare hashes only
    # within the runner schema; retain the approved evaluator hash as a frozen reference.
    changed = run_a["normalized_trade_hash"] != BASELINE_RUNNER_TRADE_HASH
    return {
        "classification": "trade_behavior_changed" if changed else "signal_changed_no_trade_behavior_change",
        "baseline_normalized_trade_hash": BASELINE_TRADE_HASH,
        "baseline_runner_normalized_trade_hash": BASELINE_RUNNER_TRADE_HASH,
        "hash_schema": "normalized-futures-trades-runner-v1",
        "candidate_normalized_trade_hash": run_a["normalized_trade_hash"],
        "normalized_trade_hash_changed": changed,
        "trade_field_diff_empty": not changed,
    }


def reconcile_existing_result(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("run_a") or not payload.get("reachability"):
        return payload
    behavior = classify_trade_behavior(payload["run_a"])
    payload["trade_behavior"] = behavior
    if behavior["classification"] == "signal_changed_no_trade_behavior_change":
        payload["final_status"] = behavior["classification"]
        payload["bias"] = {"status": "not_run_behavior_unchanged"}
        payload["cost"] = {"status": "not_run_behavior_unchanged"}
        payload["validation"] = {"status": "not_run_behavior_unchanged"}
        payload["development_probe"] = {
            "executed": bool(payload.get("development")),
            "purpose": "cross_schema_trade_behavior_confirmation",
            "result": payload.get("development", {}).get("development_status"),
            "quality_gate_applied": False,
        }
    result_path = repo_root / RESULT_ROOT / str(payload["experiment_id"]) / "stage3d2b-experiment-result.json"
    dump_json(result_path, payload)
    record_experiment(repo_root, payload)
    return payload


def gate_route(behavior: str, development_status: str | None) -> dict[str, str]:
    if behavior != "trade_behavior_changed":
        return {"development": "not_run_behavior_unchanged", "bias": "not_run", "cost": "not_run", "validation": "not_run"}
    if not development_status or not development_status.startswith("development_eligible"):
        return {"development": development_status or "development_execution_failed", "bias": "not_run_development_not_eligible", "cost": "not_run", "validation": "not_run"}
    return {"development": development_status, "bias": "required", "cost": "pending_bias", "validation": "pending_bias_and_cost"}


def backtest_wall_seconds(repo_root: Path, results: list[dict[str, Any]]) -> float:
    total = 0.0
    for item in results:
        for run_key in ("run_a", "run_b"):
            report = item.get(run_key, {}).get("runner_report")
            if report:
                manifest_path = (repo_root / report).parent / "manifest.yaml"
                if manifest_path.exists():
                    manifest = load_simple_yaml(manifest_path)
                    started = datetime.fromisoformat(manifest["started_at"])
                    completed = datetime.fromisoformat(manifest["completed_at"])
                    total += (completed - started).total_seconds()
    return round(total, 3)


def init_registry(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stage3d2b_campaigns (
          campaign_id TEXT PRIMARY KEY, search_space_sha256 TEXT NOT NULL, queue_sha256 TEXT NOT NULL,
          policy_sha256 TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT, completed_at TEXT,
          validation_used INTEGER NOT NULL DEFAULT 0, final_report_path TEXT
        );
        CREATE TABLE IF NOT EXISTS stage3d2b_queue_registry (
          campaign_id TEXT PRIMARY KEY, queue_sha256 TEXT NOT NULL, queue_frozen INTEGER NOT NULL,
          experiment_count INTEGER NOT NULL, queue_json TEXT NOT NULL, registered_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stage3d2b_experiments (
          campaign_id TEXT NOT NULL, experiment_id INTEGER NOT NULL, fingerprint TEXT NOT NULL,
          variable_id TEXT NOT NULL, new_value TEXT NOT NULL, status TEXT NOT NULL,
          lease_owner TEXT, lease_expires_at REAL, attempts INTEGER NOT NULL DEFAULT 0,
          reachability_json TEXT, candidate_identity_json TEXT, ast_mutation_json TEXT,
          run_a_json TEXT, run_b_json TEXT, reproducibility_json TEXT, behavior_json TEXT,
          development_json TEXT, bias_json TEXT, cost_json TEXT, validation_json TEXT,
          pollution_json TEXT, artifact_index_json TEXT, lifecycle_json TEXT, updated_at TEXT NOT NULL,
          PRIMARY KEY(campaign_id, experiment_id), UNIQUE(campaign_id, fingerprint)
        );
        """
    )


def register_frozen_queue(repo_root: Path, queue: dict[str, Any]) -> None:
    db = repo_root / "research/registry/research.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        init_registry(conn)
        existing = conn.execute("SELECT queue_sha256 FROM stage3d2b_queue_registry WHERE campaign_id=?", (CAMPAIGN_ID,)).fetchone()
        if existing and existing[0] != queue["queue_sha256"]:
            raise Stage3D2BError("validation_error", "frozen_queue_drift", "registry queue hash mismatch")
        conn.execute(
            "INSERT OR IGNORE INTO stage3d2b_queue_registry VALUES (?, ?, 1, ?, ?, ?)",
            (CAMPAIGN_ID, queue["queue_sha256"], len(queue["experiments"]), json.dumps(queue, sort_keys=True), utc_now()),
        )
        for item in queue["experiments"]:
            conn.execute(
                """INSERT OR IGNORE INTO stage3d2b_experiments(
                campaign_id,experiment_id,fingerprint,variable_id,new_value,status,updated_at,
                pollution_json,artifact_index_json,lifecycle_json) VALUES (?,?,?,?,?,'queued',?,'[]','{}','[]')""",
                (CAMPAIGN_ID, item["experiment_id"], item["fingerprint"], item["variable_id"], str(item["new_value"]), utc_now()),
            )
        conn.commit()
    finally:
        conn.close()


def claim_experiment(repo_root: Path, experiment_id: int, owner: str, lease_seconds: int = 900) -> bool:
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        conn.execute("BEGIN IMMEDIATE")
        init_registry(conn)
        now = time.time()
        changed = conn.execute(
            """UPDATE stage3d2b_experiments SET status='claimed', lease_owner=?, lease_expires_at=?,
            attempts=attempts+1, updated_at=? WHERE campaign_id=? AND experiment_id=? AND
            (status='queued' OR (status='claimed' AND lease_expires_at < ?))""",
            (owner, now + lease_seconds, utc_now(), CAMPAIGN_ID, experiment_id, now),
        ).rowcount
        conn.commit()
        return changed == 1
    finally:
        conn.close()


def record_experiment(repo_root: Path, payload: dict[str, Any]) -> None:
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        conn.execute("BEGIN IMMEDIATE")
        init_registry(conn)
        conn.execute(
            """UPDATE stage3d2b_experiments SET status=?,lease_owner=NULL,lease_expires_at=NULL,
            reachability_json=?,candidate_identity_json=?,ast_mutation_json=?,run_a_json=?,run_b_json=?,
            reproducibility_json=?,behavior_json=?,development_json=?,bias_json=?,cost_json=?,validation_json=?,
            pollution_json=?,artifact_index_json=?,lifecycle_json=?,updated_at=?
            WHERE campaign_id=? AND experiment_id=?""",
            (
                payload["final_status"], json.dumps(payload.get("reachability") or {}, sort_keys=True),
                json.dumps(payload.get("candidate_identity") or {}, sort_keys=True), json.dumps(payload.get("ast_mutation") or {}, sort_keys=True),
                json.dumps(payload.get("run_a") or {}, sort_keys=True), json.dumps(payload.get("run_b") or {}, sort_keys=True),
                json.dumps(payload.get("reproducibility") or {}, sort_keys=True), json.dumps(payload.get("trade_behavior") or {}, sort_keys=True),
                json.dumps(payload.get("development") or {}, sort_keys=True), json.dumps(payload.get("bias") or {}, sort_keys=True),
                json.dumps(payload.get("cost") or {}, sort_keys=True), json.dumps(payload.get("validation") or {}, sort_keys=True),
                json.dumps(payload.get("pollution_events") or [], sort_keys=True), json.dumps(payload.get("artifacts") or {}, sort_keys=True),
                json.dumps(payload.get("lifecycle") or [], sort_keys=True), utc_now(), CAMPAIGN_ID, payload["experiment_id"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def completed_ids(repo_root: Path) -> set[int]:
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        init_registry(conn)
        rows = conn.execute(
            "SELECT experiment_id FROM stage3d2b_experiments WHERE campaign_id=? AND status NOT IN ('queued','claimed','running')",
            (CAMPAIGN_ID,),
        ).fetchall()
        return {int(row[0]) for row in rows}
    finally:
        conn.close()


def load_existing_result(repo_root: Path, experiment_id: int) -> dict[str, Any] | None:
    path = repo_root / RESULT_ROOT / str(experiment_id) / "stage3d2b-experiment-result.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def run_one_experiment(repo_root: Path, campaign: dict[str, Any], experiment: dict[str, Any], df: Any) -> dict[str, Any]:
    experiment_id = int(experiment["experiment_id"])
    lifecycle: list[dict[str, Any]] = [{"state": "claimed", "at": utc_now()}]
    artifacts: dict[str, str] = {}
    candidate: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    run_a = run_b = repro = behavior = development = None
    bias = {"status": "not_run"}
    cost = {"status": "not_run"}
    validation = {"status": "not_run"}
    final_status = "running"
    try:
        spec = {
            "schema_version": "stage3d2b-experiment-spec-v1", "campaign_id": CAMPAIGN_ID,
            **experiment, "policy_sha256": POLICY_HASH, "base_strategy_sha256": BASE_STRATEGY_SHA256,
            "queue_sha256": campaign["frozen_queue"]["sha256"], "created_at": utc_now(),
        }
        spec_path = repo_root / "research/experiments" / CAMPAIGN_ID / str(experiment_id) / "experiment-spec.yaml"
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        dump_manifest(spec_path, spec)
        artifacts["experiment_spec"] = repo_rel(repo_root, spec_path)
        lifecycle.append({"state": "spec_frozen", "at": utc_now()})

        candidate = stage3d1.create_candidate(repo_root, campaign, experiment)
        diff = stage3d1.validate_single_diff(repo_root, candidate, experiment)
        manifest = load_simple_yaml(repo_root / candidate["candidate_manifest"])
        if manifest["ast_diff"]["new_value"] != experiment["new_value"] or manifest["semantic_mutation_count"] != 1:
            raise Stage3D2BError("implementation_error", "unauthorized_candidate_semantic_diff", "candidate manifest differs from queue")
        artifacts["candidate_manifest"] = candidate["candidate_manifest"]
        lifecycle.append({"state": "candidate_frozen", "at": utc_now(), "candidate_hash": candidate["candidate_strategy_sha256"], "diff": diff})

        preflight = reachability_preflight(df, experiment)
        preflight_path = repo_root / RESULT_ROOT / str(experiment_id) / "reachability-preflight.json"
        dump_json(preflight_path, preflight)
        artifacts["reachability_preflight"] = repo_rel(repo_root, preflight_path)
        lifecycle.append({"state": "reachability_preflight", "at": utc_now(), "status": preflight["status"]})
        if preflight["actual_final_signal_mask_changes"] == 0:
            final_status = "reachability_prediction_miss"
        else:
            run_a = stage3d1.run_candidate(repo_root, campaign, experiment_id, candidate, "CANDIDATE-RUN-A")
            lifecycle.append({"state": "candidate_run_a", "at": utc_now()})
            run_b = stage3d1.run_candidate(repo_root, campaign, experiment_id, candidate, "CANDIDATE-RUN-B")
            lifecycle.append({"state": "candidate_run_b", "at": utc_now()})
            repro = stage3d1.compare_repro(run_a, run_b)
            repro_path = repo_root / RESULT_ROOT / str(experiment_id) / "candidate-reproducibility-comparison.json"
            dump_json(repro_path, repro)
            artifacts["reproducibility"] = repo_rel(repo_root, repro_path)
            if not repro["passed"]:
                raise Stage3D2BError("validation_error", "candidate_reproducibility_mismatch", "RUN-A/RUN-B mismatch")
            behavior = classify_trade_behavior(run_a)
            lifecycle.append({"state": "trade_behavior_classified", "at": utc_now(), "classification": behavior["classification"]})
            if behavior["classification"] == "signal_changed_no_trade_behavior_change":
                final_status = behavior["classification"]
            else:
                development = stage3d1.development_evaluate(repo_root, candidate, experiment_id)
                artifacts["development_evaluation"] = development["result_path"]
                route = gate_route(behavior["classification"], development["development_status"])
                lifecycle.append({"state": "development_evaluated", "at": utc_now(), "status": route["development"]})
                if route["bias"] == "required":
                    # Existing certified bias/cost execution remains mandatory. Reaching this branch without
                    # its concrete run artifacts is an execution failure, never a fabricated pass.
                    bias = {"status": "development_execution_failed", "reason_code": "certified_bias_runner_not_integrated"}
                    cost = {"status": "not_run_bias_not_passed"}
                    final_status = "development_execution_failed"
                else:
                    bias = {"status": route["bias"]}
                    cost = {"status": route["cost"]}
                    validation = {"status": route["validation"]}
                    final_status = development["development_status"]
        lifecycle.append({"state": "recorded", "at": utc_now()})
    except (Stage3D2BError, stage3d1.Stage3D1Error) as exc:
        final_status = getattr(exc, "reason_code", "implementation_error")
        lifecycle.append({"state": "recorded", "at": utc_now(), "failure_type": getattr(exc, "failure_type", "implementation_error"), "reason_code": final_status})
    payload = {
        "experiment_id": experiment_id, "fingerprint": experiment["fingerprint"],
        "variable_id": experiment["variable_id"], "old_value": experiment["old_value"], "new_value": experiment["new_value"],
        "candidate_identity": candidate or {}, "ast_mutation": (load_simple_yaml(repo_root / candidate["candidate_manifest"])["ast_diff"] if candidate else {}),
        "reachability": preflight or {}, "run_a": run_a or {}, "run_b": run_b or {}, "reproducibility": repro or {},
        "trade_behavior": behavior or {}, "development": development or {}, "bias": bias, "cost": cost, "validation": validation,
        "pollution_events": [], "final_status": final_status, "artifacts": artifacts, "lifecycle": lifecycle,
    }
    result_path = repo_root / RESULT_ROOT / str(experiment_id) / "stage3d2b-experiment-result.json"
    dump_json(result_path, payload)
    record_experiment(repo_root, payload)
    return payload


def write_final_report(repo_root: Path, campaign: dict[str, Any], search_space: dict[str, Any], queue: dict[str, Any], results: list[dict[str, Any]], started: str, elapsed: float) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for item in results:
        status_counts[item["final_status"]] = status_counts.get(item["final_status"], 0) + 1
    prediction_hits = sum(1 for item in results if item.get("reachability", {}).get("prediction_classification_accurate"))
    signal_changed = [item for item in results if item.get("reachability", {}).get("actual_final_signal_mask_changes", 0) > 0]
    trade_changed = [item for item in results if item.get("trade_behavior", {}).get("classification") == "trade_behavior_changed"]
    development_passed = [item for item in results if str(item.get("development", {}).get("development_status", "")).startswith("development_eligible")]
    final = {
        "schema_version": "stage3d2b-final-report-v1", "campaign_id": CAMPAIGN_ID,
        "status": "completed" if len(results) == len(queue["experiments"]) else "stopped",
        "started_at": started, "completed_at": utc_now(), "wall_clock_seconds": round(elapsed, 3),
        "autonomous_no_per_experiment_confirmation": True,
        "budget": campaign["budget"],
        "budget_used": {"experiments_completed": len(results), "attempts": len(results), "validation_evaluations": 0},
        "search_space_sha256": search_space["search_space_sha256"], "queue_sha256": queue["queue_sha256"],
        "queue_frozen": True, "base_strategy_sha256": BASE_STRATEGY_SHA256, "policy_sha256": POLICY_HASH,
        "status_counts": status_counts, "reachability_prediction_miss_count": status_counts.get("reachability_prediction_miss", 0),
        "signal_changed_no_trade_count": status_counts.get("signal_changed_no_trade_behavior_change", 0),
        "trade_behavior_changed_count": len(trade_changed), "development_eligible_count": len(development_passed),
        "bias_access_count": sum(1 for item in results if not str(item.get("bias", {}).get("status", "not_run")).startswith("not_run")),
        "cost_access_count": sum(1 for item in results if not str(item.get("cost", {}).get("status", "not_run")).startswith("not_run")),
        "validation_access_count": 0,
        "backtest_wall_clock_seconds": backtest_wall_seconds(repo_root, results),
        "reachability_prediction_precision": prediction_hits / len(results) if results else None,
        "reachability_prediction_hits": prediction_hits,
        "signal_changed_experiments": [item["experiment_id"] for item in signal_changed],
        "trade_changed_experiments": [item["experiment_id"] for item in trade_changed],
        "development_eligible_experiments": [item["experiment_id"] for item in development_passed],
        "experiments": results,
        "infrastructure_issues": [], "pollution_events": [],
        "forbidden_actions": {
            "unapproved_values_used": False, "multi_variable_candidates": False, "adaptive_search": False,
            "hyperopt_run": False, "holdout_accessed": False, "qualified_challenger_created": False,
            "champion_created": False, "forward_dry_run": False,
        },
        "artifact_index": {
            "campaign": CAMPAIGN_PATH.as_posix(), "approved_search_space": SEARCH_SPACE_PATH.as_posix(),
            "frozen_queue": QUEUE_PATH.as_posix(), "final_json": FINAL_JSON.as_posix(), "final_markdown": FINAL_MD.as_posix(),
        },
        "next_search_evidence": "single_variable_results_complete; no automatic follow-up authorized",
    }
    dump_json(repo_root / FINAL_JSON, final)
    lines = [
        "# Stage 3D.2-B Reachability-Informed Batch 1", "",
        f"- Status: `{final['status']}`", f"- Autonomous: `{str(final['autonomous_no_per_experiment_confirmation']).lower()}`",
        f"- Experiments: `{len(results)}/10`", f"- Prediction precision: `{final['reachability_prediction_precision']}`",
        f"- Signal changed: `{len(signal_changed)}`", f"- Trade changed: `{len(trade_changed)}`",
        f"- Development eligible: `{len(development_passed)}`", f"- Validation access: `{final['validation_access_count']}`", "", "## Experiments", "",
    ]
    for item in results:
        lines.append(f"- `{item['experiment_id']}` `{item['variable_id']}={item['new_value']}`: `{item['final_status']}`")
    (repo_root / FINAL_MD).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / FINAL_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        conn.execute("BEGIN IMMEDIATE")
        init_registry(conn)
        conn.execute(
            "INSERT OR REPLACE INTO stage3d2b_campaigns VALUES (?,?,?,?,?,?,?,?,?)",
            (CAMPAIGN_ID, search_space["search_space_sha256"], queue["queue_sha256"], POLICY_HASH, final["status"], started, final["completed_at"], 0, FINAL_JSON.as_posix()),
        )
        conn.commit()
    finally:
        conn.close()
    return final


def run_campaign(repo_root: Path, owner: str = "stage3d2b-local", max_experiments: int | None = None, simulate_crash_after: int | None = None) -> dict[str, Any]:
    configure_stage3d1_adapter()
    started = utc_now()
    start = time.monotonic()
    campaign, search_space, queue = write_control_files(repo_root)
    register_frozen_queue(repo_root, queue)
    df = reachability.load_strategy_dataframe(repo_root)
    results: list[dict[str, Any]] = []
    done = completed_ids(repo_root)
    for experiment in queue["experiments"]:
        if max_experiments is not None and len(results) >= max_experiments:
            break
        experiment_id = int(experiment["experiment_id"])
        existing = load_existing_result(repo_root, experiment_id)
        if experiment_id in done and existing:
            results.append(reconcile_existing_result(repo_root, existing))
            continue
        if time.monotonic() - start > float(campaign["budget"]["max_wall_clock_hours"]) * 3600:
            break
        assert_frozen_inputs(repo_root, search_space, queue)
        if not claim_experiment(repo_root, experiment_id, owner, int(campaign["autonomy"]["lease_seconds"])):
            continue
        result = run_one_experiment(repo_root, campaign, experiment, df)
        results.append(result)
        if simulate_crash_after is not None and len(results) >= simulate_crash_after:
            raise RuntimeError("simulated_stage3d2b_crash")
    assert_frozen_inputs(repo_root, search_space, queue)
    return write_final_report(repo_root, campaign, search_space, queue, results, started, time.monotonic() - start)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 3D.2-B frozen reachability-informed search.")
    parser.add_argument("--owner", default="stage3d2b-local")
    parser.add_argument("--max-experiments", type=int)
    parser.add_argument("--simulate-crash-after", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = run_campaign(Path.cwd(), args.owner, args.max_experiments, args.simulate_crash_after)
    except Stage3D2BError as exc:
        print(json.dumps({"status": "failed", "failure_type": exc.failure_type, "reason_code": exc.reason_code, "message": exc.message}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
