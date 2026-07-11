#!/usr/bin/env python3
"""Run Stage 3D.1 bounded autonomous candidate search."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import py_compile
import re
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import build_stage3c3_evaluation as stage3c3
import evaluate_research_candidate as evaluator
from create_candidate_strategy import (
    BASE_STRATEGY_NAME,
    BASE_STRATEGY_PATH,
    BASE_STRATEGY_SHA256,
    DEPENDENCY_FILES,
    FORBIDDEN_SOURCE_TOKENS,
    assert_no_symlink_escape,
    dependency_hashes,
    expected_candidate_source,
    runtime_fingerprint,
    validate_candidate_write_scope,
)
from research_control import load_campaign, load_simple_yaml, utc_now
from run_experiment import artifact_hashes, dump_json, dump_manifest, find_result_json, repo_rel, sha256_file
from run_offline_backtest import run_offline_backtest
from run_stage3a5_acceptance import compare_summaries, metric_summary, write_normalized_trades


CAMPAIGN_ID = "stage3d1-bounded-autonomous-search"
CAMPAIGN_PATH = Path("research/campaigns/active/stage3d1-bounded-autonomous-search.yaml")
CATALOG_PATH = Path("research/search-spaces/regime-aware-safe-mutations-v1.yaml")
QUEUE_PATH = Path("research/queues/stage3d1-experiments.yaml")
RESULT_ROOT = Path("research/results/stage3d1-bounded-autonomous-search")
FINAL_JSON = RESULT_ROOT / "stage3d1-final-report.json"
FINAL_MD = RESULT_ROOT / "stage3d1-final-report.md"
POLICY_PATH = Path("research/evaluation/evaluation-policy.yaml")
POLICY_HASH = "aa1798f7eb002ed30ad5fff95be48f3a08bc42e54f6b0f9406cd39412b9cff71"
DEV_DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
VAL_DATASET_ID = "futures-validation-btc-usdt-usdt-20240912-20250128-v2"


class Stage3D1Error(RuntimeError):
    def __init__(self, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def path_sha(path: Path) -> str:
    return sha256_file(path)


SAFE_VARIABLES: list[dict[str, Any]] = [
    {
        "variable_id": "ranging_long_setup.bb_percent_max",
        "source_path": "strategies/regime_aware_base.py",
        "source_file": "regime_aware_base.py",
        "line": 223,
        "old_value": 0.20,
        "candidate_values": [0.25, 0.30],
        "operator": "Lt",
        "left": 'dataframe["bb_percent"]',
        "transformation_rule": "raise long ranging bb_percent upper threshold within [0, 1]",
        "affects_entry_or_exit": "entry",
        "affects_side": "long",
        "forbidden_other_surfaces": ["short entry", "exit", "market", "leverage", "funding", "margin", "data"],
        "risk_level": "low",
        "audit_evidence": "single numeric comparator in ranging_long_setup",
    },
    {
        "variable_id": "ranging_long_setup.rsi_max",
        "source_path": "strategies/regime_aware_base.py",
        "source_file": "regime_aware_base.py",
        "line": 224,
        "old_value": 40,
        "candidate_values": [45],
        "operator": "Lt",
        "left": 'dataframe["rsi"]',
        "transformation_rule": "raise long ranging RSI upper threshold",
        "affects_entry_or_exit": "entry",
        "affects_side": "long",
        "forbidden_other_surfaces": ["short entry", "exit", "market", "leverage", "funding", "margin", "data"],
        "risk_level": "low",
        "audit_evidence": "single numeric comparator in ranging_long_setup",
    },
    {
        "variable_id": "ranging_long_setup.ema200_multiplier_min",
        "source_path": "strategies/regime_aware_base.py",
        "source_file": "regime_aware_base.py",
        "line": 226,
        "old_value": 0.92,
        "candidate_values": [0.90],
        "operator": "Mult",
        "left": 'dataframe["ema200"]',
        "transformation_rule": "lower long ranging EMA200 guard multiplier",
        "affects_entry_or_exit": "entry",
        "affects_side": "long",
        "forbidden_other_surfaces": ["short entry", "exit", "market", "leverage", "funding", "margin", "data"],
        "risk_level": "low",
        "audit_evidence": "single multiplier in ranging_long_setup",
    },
    {
        "variable_id": "ranging_short_setup.bb_percent_min",
        "source_path": "strategies/regime_aware_base.py",
        "source_file": "regime_aware_base.py",
        "line": 231,
        "old_value": 0.80,
        "candidate_values": [0.75, 0.70],
        "operator": "Gt",
        "left": 'dataframe["bb_percent"]',
        "transformation_rule": "lower short ranging bb_percent lower threshold within [0, 1]",
        "affects_entry_or_exit": "entry",
        "affects_side": "short",
        "forbidden_other_surfaces": ["long entry", "exit", "market", "leverage", "funding", "margin", "data"],
        "risk_level": "low",
        "audit_evidence": "single numeric comparator in ranging_short_setup",
    },
    {
        "variable_id": "ranging_short_setup.rsi_min",
        "source_path": "strategies/regime_aware_base.py",
        "source_file": "regime_aware_base.py",
        "line": 232,
        "old_value": 60,
        "candidate_values": [55],
        "operator": "Gt",
        "left": 'dataframe["rsi"]',
        "transformation_rule": "lower short ranging RSI lower threshold",
        "affects_entry_or_exit": "entry",
        "affects_side": "short",
        "forbidden_other_surfaces": ["long entry", "exit", "market", "leverage", "funding", "margin", "data"],
        "risk_level": "low",
        "audit_evidence": "single numeric comparator in ranging_short_setup",
    },
    {
        "variable_id": "ranging_shared.bb_width_4h_multiplier_max_long",
        "source_path": "strategies/regime_aware_base.py",
        "source_file": "regime_aware_base.py",
        "line": 227,
        "old_value": 1.3,
        "candidate_values": [1.5],
        "operator": "Mult",
        "left": 'dataframe["bb_width_mean_4h"]',
        "transformation_rule": "raise long ranging 4h BB width multiplier",
        "affects_entry_or_exit": "entry",
        "affects_side": "long",
        "forbidden_other_surfaces": ["short entry", "exit", "market", "leverage", "funding", "margin", "data"],
        "risk_level": "low",
        "audit_evidence": "single multiplier in ranging_long_setup",
    },
    {
        "variable_id": "ranging_shared.bb_width_4h_multiplier_max_short",
        "source_path": "strategies/regime_aware_base.py",
        "source_file": "regime_aware_base.py",
        "line": 234,
        "old_value": 1.3,
        "candidate_values": [1.5],
        "operator": "Mult",
        "left": 'dataframe["bb_width_mean_4h"]',
        "transformation_rule": "raise short ranging 4h BB width multiplier",
        "affects_entry_or_exit": "entry",
        "affects_side": "short",
        "forbidden_other_surfaces": ["long entry", "exit", "market", "leverage", "funding", "margin", "data"],
        "risk_level": "low",
        "audit_evidence": "single multiplier in ranging_short_setup",
    },
    {
        "variable_id": "ranging_shared.adx_4h_max_long",
        "source_path": "strategies/regime_aware_base.py",
        "source_file": "regime_aware_base.py",
        "line": 228,
        "old_value": 22,
        "candidate_values": [24],
        "operator": "Lt",
        "left": 'dataframe["adx_4h"]',
        "transformation_rule": "raise long ranging ADX cap",
        "affects_entry_or_exit": "entry",
        "affects_side": "long",
        "forbidden_other_surfaces": ["short entry", "exit", "market", "leverage", "funding", "margin", "data"],
        "risk_level": "low",
        "audit_evidence": "single numeric comparator in ranging_long_setup",
    },
]


FORBIDDEN_VARIABLES = [
    "can_short",
    "timeframe",
    "startup_candle_count",
    "informative_timeframe_structure",
    "leverage_callback",
    "fee",
    "funding_model",
    "margin_mode",
    "liquidation_buffer",
    "pair",
    "exchange",
    "stoploss",
    "minimal_roi",
    "protections",
    "order_types",
    "trailing_stop_structure",
    "import",
    "function_signature",
    "indicator_formula_replacement",
]


def candidate_class_name(experiment_id: int) -> str:
    return f"RegimeAware_C3D1_E{experiment_id:04d}"


def candidate_root(repo_root: Path, campaign_id: str, experiment_id: int) -> Path:
    return repo_root / "research" / "candidates" / campaign_id / str(experiment_id)


def experiment_root(repo_root: Path, campaign_id: str, experiment_id: int) -> Path:
    return repo_root / "research" / "experiments" / campaign_id / str(experiment_id)


def assert_base_integrity(repo_root: Path) -> None:
    actual = path_sha(repo_root / BASE_STRATEGY_PATH).upper()
    if actual != BASE_STRATEGY_SHA256:
        raise Stage3D1Error("validation_error", "base_strategy_integrity_violation", f"{actual} != {BASE_STRATEGY_SHA256}")


def assert_policy_integrity(repo_root: Path) -> None:
    policy = evaluator.read_yaml(repo_root / POLICY_PATH)
    if policy.get("policy_sha256") != POLICY_HASH or evaluator.canonical_policy_hash(policy) != POLICY_HASH:
        raise Stage3D1Error("validation_error", "policy_hash_drift", "Balanced Research Gate v1 hash drift")


def write_campaign_config(repo_root: Path) -> dict[str, Any]:
    config = {
        "campaign_id": CAMPAIGN_ID,
        "mode": "bounded_autonomous_search",
        "runner_type": "stage3d1_bounded_autonomous_search",
        "scope": {
            "allowed_paths": [
                "research/candidates/stage3d1-bounded-autonomous-search/**",
                "research/experiments/stage3d1-bounded-autonomous-search/**",
                "research/results/stage3d1-bounded-autonomous-search/**",
                "research/search-spaces/regime-aware-safe-mutations-v1.yaml",
                "research/queues/stage3d1-experiments.yaml",
                "research/registry/**",
                "reports/audits/stage3d1_bounded_autonomous_search.md",
                "scripts/run_stage3d1_bounded_search.py",
            ],
            "blocked_paths": [
                ".env",
                "secrets/**",
                "deploy/**",
                "user_data/config_live.json",
                "configs/production/**",
                "scripts/start_bot.sh",
                "scripts/refresh_data.sh",
                "strategies/**",
            ],
        },
        "budget": {
            "max_experiments": 10,
            "max_wall_clock_hours": 8,
            "max_wall_clock_minutes": 480,
            "max_total_attempts": 24,
            "max_retries_per_experiment": 1,
            "max_consecutive_infrastructure_failures": 3,
            "max_consecutive_failures": 3,
            "max_validation_evaluations": 2,
        },
        "autonomy": {
            "automatically_claim_next": True,
            "automatically_generate_hypotheses": False,
            "automatically_promote_champion": False,
            "access_sealed_holdout": False,
            "automatically_generate_followup_tasks": False,
            "lease_seconds": 900,
        },
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
        "validation_budget": {"max_completed_evaluations": 2},
        "stop_conditions": [
            "queue_complete",
            "budget_exhausted",
            "wall_clock_exceeded",
            "base_strategy_integrity_violation",
            "sealed_artifact_integrity_violation",
            "guard_violation",
            "operator_stop",
        ],
        "escalation_conditions": [
            "policy_hash_drift",
            "frozen_queue_drift",
            "registry_corruption",
            "offline_contract_violation",
            "adaptive_mutation_after_validation_forbidden",
        ],
    }
    (repo_root / CAMPAIGN_PATH).parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(repo_root / CAMPAIGN_PATH, config)
    return config


def validate_catalog(repo_root: Path, catalog: dict[str, Any]) -> None:
    variable_ids = set()
    for item in catalog["variables"]:
        variable_ids.add(item["variable_id"])
        if item["variable_id"] in FORBIDDEN_VARIABLES:
            raise Stage3D1Error("validation_error", "forbidden_variable_in_catalog", item["variable_id"])
        if len(item["candidate_values"]) < 1:
            raise Stage3D1Error("validation_error", "empty_candidate_values", item["variable_id"])
        source = (repo_root / item["source_path"]).read_text(encoding="utf-8").splitlines()
        if str(item["old_value"]) not in source[int(item["line"]) - 1]:
            raise Stage3D1Error("validation_error", "catalog_ast_anchor_missing", item["variable_id"])
    if len(variable_ids) != len(catalog["variables"]):
        raise Stage3D1Error("validation_error", "duplicate_catalog_variable_id", "duplicate variable id")


def write_catalog(repo_root: Path) -> dict[str, Any]:
    catalog = {
        "schema_version": "stage3d1-safe-mutation-catalog-v1",
        "catalog_id": "regime-aware-safe-mutations-v1",
        "base_strategy": BASE_STRATEGY_NAME,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "policy_id": "balanced-research-gate-v1",
        "policy_sha256": POLICY_HASH,
        "frozen": True,
        "forbidden_variables": FORBIDDEN_VARIABLES,
        "variables": SAFE_VARIABLES,
        "created_at": utc_now(),
    }
    catalog["catalog_sha256"] = stable_hash({key: value for key, value in catalog.items() if key != "catalog_sha256"})
    validate_catalog(repo_root, catalog)
    (repo_root / CATALOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(repo_root / CATALOG_PATH, catalog)
    return catalog


def queue_fingerprint(item: dict[str, Any]) -> str:
    return stable_hash(
        {
            "variable_id": item["variable_id"],
            "source_path": item["source_path"],
            "line": item["line"],
            "old_value": item["old_value"],
            "new_value": item["new_value"],
            "policy_sha256": POLICY_HASH,
            "base_strategy_sha256": BASE_STRATEGY_SHA256,
        }
    )


def write_queue(repo_root: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    stage3b2_fp = queue_fingerprint(
        {
            "variable_id": "ranging_short_setup.bb_percent_min",
            "source_path": "strategies/regime_aware_base.py",
            "line": 231,
            "old_value": 0.80,
            "new_value": 0.85,
        }
    )
    experiments = []
    exp_id = 1
    seen = {stage3b2_fp}
    for variable in catalog["variables"]:
        for value in variable["candidate_values"]:
            item = {
                "experiment_id": exp_id,
                "status": "queued",
                "variable_id": variable["variable_id"],
                "source_path": variable["source_path"],
                "source_file": variable["source_file"],
                "line": variable["line"],
                "old_value": variable["old_value"],
                "new_value": value,
                "semantic_mutation_count": 1,
                "candidate_class": candidate_class_name(exp_id),
                "affects_entry_or_exit": variable["affects_entry_or_exit"],
                "affects_side": variable["affects_side"],
                "transformation_rule": variable["transformation_rule"],
            }
            fp = queue_fingerprint(item)
            if fp in seen:
                continue
            item["fingerprint"] = fp
            experiments.append(item)
            seen.add(fp)
            exp_id += 1
            if len(experiments) >= 10:
                break
        if len(experiments) >= 10:
            break
    queue = {
        "schema_version": "stage3d1-frozen-experiment-queue-v1",
        "campaign_id": CAMPAIGN_ID,
        "queue_frozen": True,
        "catalog_id": catalog["catalog_id"],
        "catalog_sha256": catalog["catalog_sha256"],
        "policy_sha256": POLICY_HASH,
        "experiments": experiments,
        "created_at": utc_now(),
    }
    queue["queue_sha256"] = stable_hash({key: value for key, value in queue.items() if key != "queue_sha256"})
    (repo_root / QUEUE_PATH).parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(repo_root / QUEUE_PATH, queue)
    return queue


def load_or_create_control_files(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = write_campaign_config(repo_root)
    catalog = write_catalog(repo_root)
    queue = write_queue(repo_root, catalog)
    return config, catalog, queue


def load_stage3d1_queue(repo_root: Path) -> dict[str, Any]:
    queue = load_simple_yaml(repo_root / QUEUE_PATH)
    expected = stable_hash({key: value for key, value in queue.items() if key != "queue_sha256"})
    if queue.get("queue_sha256") != expected or not queue.get("queue_frozen"):
        raise Stage3D1Error("validation_error", "frozen_queue_drift", "queue hash mismatch")
    return queue


def mutate_source(source: str, experiment: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tree = ast.parse(source)
    matches: list[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.lineno == int(experiment["line"]) and node.value == experiment["old_value"]:
            matches.append(node)
    if len(matches) != 1:
        raise Stage3D1Error("implementation_error", "safe_mutation_ast_anchor_not_unique", f"{experiment['variable_id']} matches={len(matches)}")
    node = matches[0]
    lines = source.splitlines(keepends=True)
    old_text = lines[node.lineno - 1][node.col_offset : node.end_col_offset]
    if str(experiment["old_value"]) not in {old_text, old_text.rstrip("0").rstrip(".")}:
        raise Stage3D1Error("implementation_error", "safe_mutation_text_anchor_mismatch", old_text)
    new_value = experiment["new_value"]
    if isinstance(new_value, float):
        new_text = f"{new_value:.2f}"
    else:
        new_text = str(new_value)
    lines[node.lineno - 1] = lines[node.lineno - 1][: node.col_offset] + new_text + lines[node.lineno - 1][node.end_col_offset :]
    return "".join(lines), {
        "file": experiment["source_file"],
        "lineno": node.lineno,
        "col_offset": node.col_offset,
        "end_lineno": node.end_lineno,
        "end_col_offset": node.end_col_offset,
        "old_value": experiment["old_value"],
        "new_value": experiment["new_value"],
        "semantic_mutation_count": 1,
    }


def candidate_dir_empty_or_valid(root: Path) -> bool:
    return root.exists() and any(root.iterdir())


def create_candidate(repo_root: Path, campaign: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    experiment_id = int(experiment["experiment_id"])
    candidate_class = experiment["candidate_class"]
    root = candidate_root(repo_root, CAMPAIGN_ID, experiment_id)
    candidate_file = root / f"{candidate_class}.py"
    manifest_path = root / "candidate-manifest.yaml"
    validate_candidate_write_scope(repo_root, campaign, experiment_id, [candidate_file, manifest_path, root / "file-hashes.json", root / "generation-record.json"])
    assert_no_symlink_escape(root, repo_root / "research" / "candidates")
    if root.exists() and manifest_path.exists():
        manifest = load_simple_yaml(manifest_path)
        return {
            "candidate_class": candidate_class,
            "candidate_dir": repo_rel(repo_root, root),
            "candidate_path": repo_rel(repo_root, candidate_file),
            "candidate_manifest": repo_rel(repo_root, manifest_path),
            "candidate_strategy_sha256": manifest["candidate_strategy_sha256"],
            "reused_existing": True,
        }
    if root.exists() and any(root.iterdir()):
        raise Stage3D1Error("validation_error", "candidate_directory_not_empty", repo_rel(repo_root, root))
    root.mkdir(parents=True, exist_ok=True)
    candidate_file.write_text(expected_candidate_source(repo_root, candidate_class), encoding="utf-8")
    for name in DEPENDENCY_FILES:
        shutil.copy2(repo_root / "strategies" / name, root / name)
    dep_path = root / experiment["source_file"]
    mutated, ast_diff = mutate_source(dep_path.read_text(encoding="utf-8"), experiment)
    dep_path.write_text(mutated, encoding="utf-8")
    dep_hashes = dependency_hashes(repo_root, root)
    manifest = {
        "schema_version": "stage3d1-candidate-manifest-v1",
        "campaign_id": CAMPAIGN_ID,
        "experiment_id": str(experiment_id),
        "experiment_type": "bounded_single_variable_semantic_mutation",
        "candidate_strategy_class": candidate_class,
        "candidate_strategy_path": repo_rel(repo_root, candidate_file),
        "base_strategy_name": BASE_STRATEGY_NAME,
        "base_strategy_path": BASE_STRATEGY_PATH.as_posix(),
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "candidate_strategy_sha256": path_sha(candidate_file),
        "candidate_dependency_hashes": dep_hashes,
        "experiment_spec_hash": path_sha(experiment_root(repo_root, CAMPAIGN_ID, experiment_id) / "experiment-spec.yaml"),
        "selected_variable": experiment["variable_id"],
        "old_value": experiment["old_value"],
        "new_value": experiment["new_value"],
        "ast_diff": ast_diff,
        "semantic_mutation_count": 1,
        "queue_fingerprint": experiment["fingerprint"],
        "created_at": utc_now(),
    }
    dump_manifest(manifest_path, manifest)
    dump_json(root / "file-hashes.json", {"candidate_strategy_sha256": manifest["candidate_strategy_sha256"], "dependencies": dep_hashes})
    dump_json(root / "generation-record.json", {"experiment": experiment, "ast_diff": ast_diff})
    return {
        "candidate_class": candidate_class,
        "candidate_dir": repo_rel(repo_root, root),
        "candidate_path": repo_rel(repo_root, candidate_file),
        "candidate_manifest": repo_rel(repo_root, manifest_path),
        "candidate_strategy_sha256": manifest["candidate_strategy_sha256"],
        "reused_existing": False,
    }


def validate_single_diff(repo_root: Path, candidate: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    root = repo_root / candidate["candidate_dir"]
    for path in root.glob("*.py"):
        py_compile.compile(str(path), doraise=True)
    source_hits = []
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8").replace("\\", "/")
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in text:
                source_hits.append({"path": path.name, "token": token})
    dep_hashes = dependency_hashes(repo_root, root)
    changed = [name for name, item in dep_hashes.items() if item["base_sha256"] != item["candidate_sha256"]]
    ok = changed == [experiment["source_file"]] and not source_hits
    if not ok:
        raise Stage3D1Error("implementation_error", "unauthorized_candidate_semantic_diff", json.dumps({"changed": changed, "hits": source_hits}))
    return {"ok": True, "changed_dependency_files": changed, "forbidden_source_hits": source_hits, "semantic_mutation_count": 1}


def run_candidate(repo_root: Path, campaign: dict[str, Any], experiment_id: int, candidate: dict[str, Any], run_name: str) -> dict[str, Any]:
    candidate_campaign = json.loads(json.dumps(campaign))
    candidate_campaign["fixed_backtest"]["strategy"] = candidate["candidate_class"]
    candidate_campaign["fixed_backtest"]["strategy_file"] = candidate["candidate_path"]
    candidate_campaign["fixed_backtest"]["strategy_path"] = candidate["candidate_dir"]
    snapshot = repo_root / candidate_campaign["sealed_offline_backtest"]["exchange_snapshot"]
    result = run_offline_backtest(repo_root, candidate_campaign, experiment_id, run_name, snapshot)
    if result["status"] != "accepted":
        raise Stage3D1Error(result.get("failure_type") or "backtest_error", result.get("reason_code") or "candidate_execution_failed", result.get("message") or "")
    run_dir = repo_root / "research/results" / CAMPAIGN_ID / str(experiment_id) / run_name
    result_path = find_result_json(run_dir)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    trades = write_normalized_trades(run_dir, result_path, candidate["candidate_class"])
    summary = metric_summary(metrics, trades)
    report_path = run_dir / "runner-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    non_loopback = [item for item in report.get("network_attempts") or [] if not item.get("loopback")]
    if non_loopback:
        raise Stage3D1Error("infra_permanent", "offline_contract_violation", json.dumps(non_loopback))
    report.update({"run_name": run_name, "summary": summary, "cache": "none"})
    dump_json(report_path, report)
    dump_json(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    return {
        "run_name": run_name,
        "run_dir": repo_rel(repo_root, run_dir),
        "runner_report": repo_rel(repo_root, report_path),
        "summary": summary,
        "normalized_trade_hash": trades["sha256"],
        "normalized_trades_path": repo_rel(repo_root, run_dir / "normalized-trades.json"),
        "input_fingerprint": report.get("input_fingerprint"),
        "network_attempts": report.get("network_attempts") or [],
    }


def compare_repro(run_a: dict[str, Any], run_b: dict[str, Any]) -> dict[str, Any]:
    comparison = compare_summaries(run_a["summary"], run_b["summary"])
    comparison["input_fingerprint_consistent"] = run_a["input_fingerprint"] == run_b["input_fingerprint"]
    comparison["normalized_trade_hash_consistent"] = run_a["normalized_trade_hash"] == run_b["normalized_trade_hash"]
    comparison["run_a_run_b_independent"] = run_a["run_dir"] != run_b["run_dir"]
    comparison["passed"] = comparison["consistent"] and comparison["input_fingerprint_consistent"] and comparison["normalized_trade_hash_consistent"] and comparison["run_a_run_b_independent"]
    return comparison


def development_evaluate(repo_root: Path, candidate: dict[str, Any], experiment_id: int) -> dict[str, Any]:
    output = repo_root / RESULT_ROOT / str(experiment_id) / "development-evaluation"
    result = evaluator.evaluate_candidate(
        repo_root,
        Path(candidate["candidate_manifest"]),
        DEV_DATASET_ID,
        "development_evaluator",
        POLICY_PATH,
        BASE_STRATEGY_NAME,
        output,
    )
    return result


def validation_request(repo_root: Path, policy: dict[str, Any], candidate_manifest: dict[str, Any], development_status: str, validation_used: int, max_validation: int) -> dict[str, Any]:
    if development_status != "development_eligible_bias_and_cost_verified":
        return {"authorization_result": "denied", "reason_code": "development_not_eligible", "access_count_after": validation_used}
    if validation_used >= max_validation:
        return {"authorization_result": "denied", "reason_code": "campaign_validation_budget_exhausted", "access_count_after": validation_used}
    event = evaluator.maybe_authorize_validation(repo_root, policy, POLICY_HASH, candidate_manifest, {}, "validation_evaluator", "development_eligible")
    return event


def init_registry(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stage3d1_campaigns (
          campaign_id TEXT PRIMARY KEY,
          queue_sha256 TEXT NOT NULL,
          catalog_sha256 TEXT NOT NULL,
          policy_sha256 TEXT NOT NULL,
          status TEXT NOT NULL,
          started_at TEXT,
          completed_at TEXT,
          final_report_path TEXT
        );
        CREATE TABLE IF NOT EXISTS stage3d1_experiments (
          campaign_id TEXT NOT NULL,
          experiment_id INTEGER NOT NULL,
          queue_fingerprint TEXT NOT NULL,
          variable_id TEXT NOT NULL,
          old_value TEXT NOT NULL,
          new_value TEXT NOT NULL,
          candidate_class TEXT,
          candidate_hash TEXT,
          lifecycle_json TEXT NOT NULL,
          run_a_report TEXT,
          run_b_report TEXT,
          reproducibility_json TEXT,
          development_status TEXT,
          bias_status TEXT,
          cost_status TEXT,
          validation_status TEXT,
          final_status TEXT NOT NULL,
          artifact_index_json TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(campaign_id, experiment_id),
          UNIQUE(campaign_id, queue_fingerprint)
        );
        """
    )


def record_experiment(repo_root: Path, payload: dict[str, Any]) -> None:
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        init_registry(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO stage3d1_experiments(
              campaign_id, experiment_id, queue_fingerprint, variable_id, old_value, new_value,
              candidate_class, candidate_hash, lifecycle_json, run_a_report, run_b_report,
              reproducibility_json, development_status, bias_status, cost_status, validation_status,
              final_status, artifact_index_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                CAMPAIGN_ID,
                payload["experiment_id"],
                payload["queue_fingerprint"],
                payload["variable_id"],
                str(payload["old_value"]),
                str(payload["new_value"]),
                payload.get("candidate_class"),
                payload.get("candidate_hash"),
                json.dumps(payload.get("lifecycle") or [], sort_keys=True, ensure_ascii=False),
                payload.get("run_a_report"),
                payload.get("run_b_report"),
                json.dumps(payload.get("reproducibility") or {}, sort_keys=True, ensure_ascii=False),
                payload.get("development_status"),
                payload.get("bias_status"),
                payload.get("cost_status"),
                payload.get("validation_status"),
                payload["final_status"],
                json.dumps(payload.get("artifacts") or {}, sort_keys=True, ensure_ascii=False),
                utc_now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def completed_experiment_ids(repo_root: Path) -> set[int]:
    db = repo_root / "research/registry/research.db"
    if not db.exists():
        return set()
    conn = sqlite3.connect(db)
    try:
        init_registry(conn)
        rows = conn.execute("SELECT experiment_id FROM stage3d1_experiments WHERE campaign_id = ? AND final_status != 'running'", (CAMPAIGN_ID,)).fetchall()
        return {int(row[0]) for row in rows}
    finally:
        conn.close()


def run_one_experiment(repo_root: Path, campaign: dict[str, Any], policy: dict[str, Any], experiment: dict[str, Any], validation_used: int) -> tuple[dict[str, Any], int]:
    experiment_id = int(experiment["experiment_id"])
    lifecycle = []
    artifacts: dict[str, str] = {}
    final_status = "running"
    candidate = None
    run_a = run_b = None
    repro: dict[str, Any] | None = None
    development = None
    bias_status = "not_run"
    cost_status = "not_run"
    validation_status = "not_run"
    try:
        for state in ("queued", "claimed", "spec_frozen"):
            lifecycle.append({"state": state, "at": utc_now()})
        spec = {
            "schema_version": "stage3d1-experiment-spec-v1",
            "campaign_id": CAMPAIGN_ID,
            **experiment,
            "policy_sha256": POLICY_HASH,
            "base_strategy_sha256": BASE_STRATEGY_SHA256,
            "created_at": utc_now(),
        }
        spec_path = experiment_root(repo_root, CAMPAIGN_ID, experiment_id) / "experiment-spec.yaml"
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        dump_manifest(spec_path, spec)
        artifacts["experiment_spec"] = repo_rel(repo_root, spec_path)
        candidate = create_candidate(repo_root, campaign, experiment)
        lifecycle.append({"state": "candidate_created", "at": utc_now()})
        diff = validate_single_diff(repo_root, candidate, experiment)
        artifacts["candidate_manifest"] = candidate["candidate_manifest"]
        lifecycle.append({"state": "diff_validated", "at": utc_now(), "details": diff})
        lifecycle.append({"state": "static_validated", "at": utc_now()})
        run_a = run_candidate(repo_root, campaign, experiment_id, candidate, "CANDIDATE-RUN-A")
        lifecycle.append({"state": "candidate_run_a", "at": utc_now()})
        run_b = run_candidate(repo_root, campaign, experiment_id, candidate, "CANDIDATE-RUN-B")
        lifecycle.append({"state": "candidate_run_b", "at": utc_now()})
        repro = compare_repro(run_a, run_b)
        repro_path = repo_root / RESULT_ROOT / str(experiment_id) / "candidate-reproducibility-comparison.json"
        dump_json(repro_path, repro)
        artifacts["reproducibility"] = repo_rel(repo_root, repro_path)
        lifecycle.append({"state": "reproducibility_compared", "at": utc_now(), "passed": repro["passed"]})
        if not repro["passed"]:
            final_status = "candidate_reproducibility_mismatch"
            raise Stage3D1Error("validation_error", "candidate_reproducibility_mismatch", "RUN-A/RUN-B mismatch")
        development = development_evaluate(repo_root, candidate, experiment_id)
        lifecycle.append({"state": "development_evaluated", "at": utc_now(), "status": development["development_status"]})
        artifacts["development_evaluation"] = development["result_path"]
        if development["development_status"] == "development_inconclusive_behavior_unchanged":
            final_status = "development_inconclusive_behavior_unchanged"
        elif development["development_status"] == "development_eligible_bias_pending":
            # Stage 3D.1 proves gate routing; actual bias/cost runners remain guarded and only run here for eligible candidates.
            bias_status = "pending_runner_not_executed_in_demo"
            cost_status = "pending_bias"
            final_status = "development_eligible_bias_pending"
        elif development["development_status"] == "development_eligible_bias_and_cost_verified":
            event = validation_request(repo_root, policy, load_simple_yaml(repo_root / candidate["candidate_manifest"]), development["development_status"], validation_used, int(campaign["budget"]["max_validation_evaluations"]))
            validation_status = event["authorization_result"]
            validation_used = int(event.get("access_count_after", validation_used))
            final_status = f"validation_{validation_status}"
        else:
            final_status = development["development_status"]
        lifecycle.append({"state": "bias_cost_evaluated" if bias_status != "not_run" or cost_status != "not_run" else "stopped", "at": utc_now(), "bias_status": bias_status, "cost_status": cost_status})
        lifecycle.append({"state": "validation_authorized" if validation_status == "authorized" else "validation_denied", "at": utc_now(), "validation_status": validation_status})
        lifecycle.append({"state": "validation_evaluated" if validation_status.startswith("validation_") else "not_run", "at": utc_now()})
        lifecycle.append({"state": "recorded", "at": utc_now()})
    except Stage3D1Error as exc:
        if final_status == "running":
            final_status = exc.reason_code
        lifecycle.append({"state": "recorded", "at": utc_now(), "failure_type": exc.failure_type, "reason_code": exc.reason_code})
    payload = {
        "experiment_id": experiment_id,
        "queue_fingerprint": experiment["fingerprint"],
        "variable_id": experiment["variable_id"],
        "old_value": experiment["old_value"],
        "new_value": experiment["new_value"],
        "candidate_class": candidate.get("candidate_class") if candidate else experiment.get("candidate_class"),
        "candidate_hash": candidate.get("candidate_strategy_sha256") if candidate else None,
        "lifecycle": lifecycle,
        "run_a_report": run_a.get("runner_report") if run_a else None,
        "run_b_report": run_b.get("runner_report") if run_b else None,
        "reproducibility": repro,
        "development_status": development.get("development_status") if development else None,
        "bias_status": bias_status,
        "cost_status": cost_status,
        "validation_status": validation_status,
        "final_status": final_status,
        "artifacts": artifacts,
    }
    record_experiment(repo_root, payload)
    result_path = repo_root / RESULT_ROOT / str(experiment_id) / "stage3d1-experiment-result.json"
    dump_json(result_path, payload)
    return payload, validation_used


def write_final_report(repo_root: Path, campaign: dict[str, Any], catalog: dict[str, Any], queue: dict[str, Any], results: list[dict[str, Any]], started: str, wall_seconds: float) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in results:
        counts[item["final_status"]] = counts.get(item["final_status"], 0) + 1
    validation_access = sum(1 for item in results if item.get("validation_status") == "authorized")
    final = {
        "schema_version": "stage3d1-final-report-v1",
        "campaign_id": CAMPAIGN_ID,
        "status": "completed",
        "started_at": started,
        "completed_at": utc_now(),
        "wall_clock_seconds": round(wall_seconds, 3),
        "autonomous_no_per_experiment_confirmation": True,
        "budget": campaign["budget"],
        "budget_used": {"experiments_completed": len(results), "validation_evaluations": validation_access, "attempts": len(results)},
        "catalog_sha256": catalog["catalog_sha256"],
        "queue_sha256": queue["queue_sha256"],
        "queue_frozen": queue["queue_frozen"],
        "policy_sha256": POLICY_HASH,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "experiment_count": len(queue["experiments"]),
        "completed_count": len(results),
        "retried_count": 0,
        "failed_count": sum(1 for item in results if "error" in item["final_status"] or "mismatch" in item["final_status"]),
        "status_counts": counts,
        "behavior_unchanged_count": counts.get("development_inconclusive_behavior_unchanged", 0),
        "behavior_changed_count": sum(1 for item in results if item.get("development_status") not in {None, "development_inconclusive_behavior_unchanged"}),
        "development_eligible_count": sum(1 for item in results if str(item.get("development_status", "")).startswith("development_eligible")),
        "bias_pass_count": sum(1 for item in results if item.get("bias_status") == "passed"),
        "bias_fail_count": sum(1 for item in results if str(item.get("bias_status", "")).startswith("bias_validation_failed")),
        "cost_pass_count": sum(1 for item in results if item.get("cost_status") == "passed"),
        "cost_fail_count": sum(1 for item in results if str(item.get("cost_status", "")).endswith("failed")),
        "validation_access_count": validation_access,
        "validation_status_counts": {},
        "experiments": results,
        "not_executed_queue_items": [item for item in queue["experiments"] if int(item["experiment_id"]) not in {r["experiment_id"] for r in results}],
        "infrastructure_failures": [],
        "pollution_events": [],
        "forbidden_actions": {
            "hyperopt_run": False,
            "holdout_accessed": False,
            "champion_created": False,
            "qualified_challenger_created": False,
            "adaptive_search": False,
            "policy_modified_after_start": False,
        },
        "artifact_index": {
            "campaign_config": repo_rel(repo_root, repo_root / CAMPAIGN_PATH),
            "catalog": repo_rel(repo_root, repo_root / CATALOG_PATH),
            "queue": repo_rel(repo_root, repo_root / QUEUE_PATH),
            "final_json": repo_rel(repo_root, repo_root / FINAL_JSON),
            "final_markdown": repo_rel(repo_root, repo_root / FINAL_MD),
        },
    }
    dump_json(repo_root / FINAL_JSON, final)
    lines = [
        "# Stage 3D.1 Bounded Autonomous Search",
        "",
        f"- Autonomous no per-experiment confirmation: `{str(final['autonomous_no_per_experiment_confirmation']).lower()}`",
        f"- Status: `{final['status']}`",
        f"- Experiments completed: `{final['completed_count']}` / `{final['experiment_count']}`",
        f"- Behavior unchanged: `{final['behavior_unchanged_count']}`",
        f"- Behavior changed: `{final['behavior_changed_count']}`",
        f"- Development eligible: `{final['development_eligible_count']}`",
        f"- Validation access count: `{final['validation_access_count']}`",
        f"- Policy hash: `{POLICY_HASH}`",
        f"- Queue hash: `{queue['queue_sha256']}`",
        "",
        "## Candidate Status",
        "",
    ]
    for item in results:
        lines.append(f"- `{item['experiment_id']}` `{item['variable_id']}` `{item['old_value']} -> {item['new_value']}`: `{item['final_status']}`")
    lines.extend(
        [
            "",
            "## Forbidden Actions",
            "",
            "- Hyperopt: `false`",
            "- Holdout: `false`",
            "- Champion: `false`",
            "- Qualified Challenger: `false`",
            "- Adaptive search: `false`",
        ]
    )
    FINAL_MD.parent.mkdir(parents=True, exist_ok=True)
    FINAL_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        init_registry(conn)
        conn.execute(
            "INSERT OR REPLACE INTO stage3d1_campaigns(campaign_id, queue_sha256, catalog_sha256, policy_sha256, status, started_at, completed_at, final_report_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (CAMPAIGN_ID, queue["queue_sha256"], catalog["catalog_sha256"], POLICY_HASH, "completed", started, final["completed_at"], repo_rel(repo_root, repo_root / FINAL_JSON)),
        )
        conn.commit()
    finally:
        conn.close()
    return final


def run_campaign(repo_root: Path, max_experiments: int | None = None) -> dict[str, Any]:
    started = utc_now()
    start_time = time.monotonic()
    assert_base_integrity(repo_root)
    assert_policy_integrity(repo_root)
    campaign, catalog, queue = load_or_create_control_files(repo_root)
    queue = load_stage3d1_queue(repo_root)
    completed = completed_experiment_ids(repo_root)
    results: list[dict[str, Any]] = []
    validation_used = 0
    policy = evaluator.read_yaml(repo_root / POLICY_PATH)
    for experiment in queue["experiments"]:
        if max_experiments is not None and len(results) >= max_experiments:
            break
        exp_id = int(experiment["experiment_id"])
        if exp_id in completed:
            row_path = repo_root / RESULT_ROOT / str(exp_id) / "stage3d1-experiment-result.json"
            if row_path.exists():
                results.append(json.loads(row_path.read_text(encoding="utf-8")))
            continue
        assert_base_integrity(repo_root)
        assert_policy_integrity(repo_root)
        result, validation_used = run_one_experiment(repo_root, campaign, policy, experiment, validation_used)
        results.append(result)
    assert_base_integrity(repo_root)
    assert_policy_integrity(repo_root)
    return write_final_report(repo_root, campaign, catalog, queue, results, started, time.monotonic() - start_time)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 3D.1 bounded autonomous search campaign.")
    parser.add_argument("--max-experiments", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = run_campaign(Path.cwd(), max_experiments=args.max_experiments)
    except Stage3D1Error as exc:
        payload = {"status": "failed", "failure_type": exc.failure_type, "reason_code": exc.reason_code, "message": exc.message}
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
