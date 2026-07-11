#!/usr/bin/env python3
"""Run Stage 3B.2 single-variable semantic mutation experiment."""

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
import subprocess
import time
from pathlib import Path
from typing import Any

from create_candidate_strategy import (
    BASE_STRATEGY_NAME,
    BASE_STRATEGY_PATH,
    BASE_STRATEGY_SHA256,
    DEPENDENCY_FILES,
    EXPECTED_BASELINE_TRADE_HASH,
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
from run_stage3a5_acceptance import CORE_COMPARE_KEYS, compare_summaries, metric_summary, write_normalized_trades
from run_stage3b1_candidate_identity import baseline_reference, verify_base_strategy
from validate_strategy_market_contract import validate_contract


GENERATOR_VERSION = "stage3b2-single-variable-runner-v1"
MUTATION_TOOL_VERSION = "ast-single-constant-rewrite-v1"
CAMPAIGN_ID = "demo-stage3b2-single-variable"
SELECTED_VARIABLE = {
    "name": "ranging_short_setup.bb_percent_min",
    "source_file": "regime_aware_base.py",
    "source_path": "strategies/regime_aware_base.py",
    "line": 231,
    "old_value": 0.80,
    "new_value": 0.85,
    "operator": "Gt",
    "left": 'dataframe["bb_percent"]',
    "decision_surface": "short entry",
    "transformation_rule": "increase the existing ranging-short bb_percent threshold by 0.05 within [0.0, 1.0]",
    "hypothesis": "Increasing this short-entry threshold may reduce some ranging short entry signals.",
}
FINAL_STATES = {
    "mutation_verified_behavior_changed",
    "mutation_verified_behavior_unchanged",
    "mutation_validation_failed",
    "execution_failed",
    "reproducibility_failed",
    "escalated",
}
FORBIDDEN_STATUS_TERMS = (
    "improved",
    "degraded",
    "rejected_for_performance",
    "qualified_challenger",
    "promoted",
    "champion",
)


class Stage3B2Error(RuntimeError):
    def __init__(self, status: str, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.status = status
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def pretty(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def candidate_class_name(experiment_id: str | int) -> str:
    match = re.search(r"(\d+)$", str(experiment_id))
    number = int(match.group(1)) if match else int(hashlib.sha256(str(experiment_id).encode("utf-8")).hexdigest()[:6], 16) % 10000
    return f"RegimeAware_C3B2_E{number:04d}"


def candidate_root(repo_root: Path, campaign_id: str, experiment_id: str | int) -> Path:
    return repo_root / "research" / "candidates" / campaign_id / str(experiment_id)


def experiment_root(repo_root: Path, campaign_id: str, experiment_id: str | int) -> Path:
    return repo_root / "research" / "experiments" / campaign_id / str(experiment_id)


def clean_network_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    return env


def ast_node_kind(node: ast.AST | None) -> str | None:
    return None if node is None else type(node).__name__


def is_dataframe_column(node: ast.AST, column: str) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "dataframe"
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == column
    )


def find_selected_constant(tree: ast.AST) -> ast.Constant:
    matches: list[ast.Constant] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not is_dataframe_column(node.left, "bb_percent"):
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Gt):
            continue
        if len(node.comparators) != 1 or not isinstance(node.comparators[0], ast.Constant):
            continue
        if node.comparators[0].value == SELECTED_VARIABLE["old_value"]:
            matches.append(node.comparators[0])
    if len(matches) != 1:
        raise Stage3B2Error("mutation_validation_failed", "implementation_error", "selected_ast_node_not_unique", f"expected one selected AST constant, found {len(matches)}")
    return matches[0]


def replace_ast_constant(source: str, node: ast.Constant, new_value: float) -> str:
    lines = source.splitlines(keepends=True)
    if node.lineno != node.end_lineno:
        raise Stage3B2Error("mutation_validation_failed", "implementation_error", "selected_ast_node_span_invalid", "selected constant spans multiple lines")
    line = lines[node.lineno - 1]
    old_text = line[node.col_offset : node.end_col_offset]
    if old_text not in {"0.80", "0.8"}:
        raise Stage3B2Error("mutation_validation_failed", "implementation_error", "selected_old_value_text_mismatch", f"unexpected old value text: {old_text}")
    lines[node.lineno - 1] = line[: node.col_offset] + f"{new_value:.2f}" + line[node.end_col_offset :]
    return "".join(lines)


def mutate_dependency_source(source: str) -> tuple[str, dict[str, Any]]:
    tree = ast.parse(source)
    node = find_selected_constant(tree)
    mutated = replace_ast_constant(source, node, float(SELECTED_VARIABLE["new_value"]))
    ast_diff = {
        "semantic_mutation_count": 1,
        "file": SELECTED_VARIABLE["source_file"],
        "lineno": node.lineno,
        "col_offset": node.col_offset,
        "end_lineno": node.end_lineno,
        "end_col_offset": node.end_col_offset,
        "old_value": SELECTED_VARIABLE["old_value"],
        "new_value": SELECTED_VARIABLE["new_value"],
        "node_type": ast_node_kind(node),
        "parent_operator": SELECTED_VARIABLE["operator"],
        "left": SELECTED_VARIABLE["left"],
    }
    return mutated, ast_diff


def expected_mutated_dependency(repo_root: Path) -> tuple[str, dict[str, Any]]:
    source = (repo_root / SELECTED_VARIABLE["source_path"]).read_text(encoding="utf-8")
    return mutate_dependency_source(source)


def source_scan(candidate_dir: Path) -> list[dict[str, str]]:
    hits = []
    for path in candidate_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8").replace("\\", "/")
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in text:
                hits.append({"path": path.name, "token": token})
    return hits


def verify_ast_single_mutation(repo_root: Path, candidate_dir: Path, candidate_class: str) -> dict[str, Any]:
    main_expected = expected_candidate_source(repo_root, candidate_class)
    main_actual = (candidate_dir / f"{candidate_class}.py").read_text(encoding="utf-8")
    dep_expected, ast_diff = expected_mutated_dependency(repo_root)
    dep_actual = (candidate_dir / SELECTED_VARIABLE["source_file"]).read_text(encoding="utf-8")
    dep_hashes = dependency_hashes(repo_root, candidate_dir)
    unmutated_deps_ok = all(
        item["base_sha256"] == item["candidate_sha256"]
        for name, item in dep_hashes.items()
        if name != SELECTED_VARIABLE["source_file"]
    )
    forbidden_hits = source_scan(candidate_dir)
    result = {
        "ok": main_actual == main_expected and dep_actual == dep_expected and unmutated_deps_ok and not forbidden_hits,
        "identity_diff_allowed": main_actual == main_expected,
        "semantic_mutation_count": 1 if dep_actual == dep_expected else 0,
        "semantic_diff_location": {
            "file": SELECTED_VARIABLE["source_file"],
            "line": ast_diff["lineno"],
            "old_value": SELECTED_VARIABLE["old_value"],
            "new_value": SELECTED_VARIABLE["new_value"],
        },
        "ast_diff": ast_diff,
        "unmutated_dependency_hashes": dep_hashes,
        "forbidden_source_hits": forbidden_hits,
        "reason_code": None,
    }
    if not result["ok"]:
        result["reason_code"] = "unauthorized_candidate_semantic_diff"
    return result


def audit_variable_selection(repo_root: Path) -> dict[str, Any]:
    source = (repo_root / "strategies" / "regime_aware_base.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.comparators) != 1:
            continue
        comparator = node.comparators[0]
        if not isinstance(comparator, ast.Constant) or not isinstance(comparator.value, (int, float)):
            continue
        left = ast.unparse(node.left) if hasattr(ast, "unparse") else type(node.left).__name__
        op = ast_node_kind(node.ops[0]) if node.ops else None
        allowed = is_dataframe_column(node.left, "bb_percent") and op == "Gt" and comparator.value == 0.80
        candidates.append(
            {
                "variable_name": "ranging_short_setup.bb_percent_min" if allowed else f"literal_threshold_line_{node.lineno}",
                "current_value": comparator.value,
                "source": f"strategies/regime_aware_base.py:{comparator.lineno}",
                "logic": "comparison threshold",
                "decision_surface": "short entry" if allowed else "entry/filter",
                "reused": False,
                "affects_risk_leverage_market_or_external_data": False,
                "recommended_range": "[0.0, 1.0]" if "bb_percent" in left else "local-neighborhood only",
                "change_risk": "low" if allowed else "medium",
                "allowed_by_stage3b2": allowed,
                "reason": "selected by deterministic priority" if allowed else "not selected",
                "left": left,
                "operator": op,
            }
        )
    forbidden = [
        {"variable_name": "can_short", "reason": "explicitly forbidden"},
        {"variable_name": "timeframe", "reason": "explicitly forbidden"},
        {"variable_name": "startup_candle_count", "reason": "explicitly forbidden"},
        {"variable_name": "stoploss", "reason": "explicitly forbidden"},
        {"variable_name": "minimal_roi", "reason": "explicitly forbidden"},
    ]
    selected = next(item for item in candidates if item["allowed_by_stage3b2"])
    audit = {
        "schema_version": "stage3b2-variable-selection-audit-v1",
        "strategy": BASE_STRATEGY_NAME,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "selection_priority": [
            "existing explicit threshold",
            "single business meaning",
            "single decision surface",
            "no market/risk/leverage/data-source impact",
            "AST-addressable single constant",
        ],
        "selected_variable": selected,
        "candidate_variables": candidates,
        "forbidden_variables_excluded": forbidden,
    }
    return audit


def write_variable_audit(repo_root: Path, audit: dict[str, Any]) -> Path:
    path = repo_root / "reports" / "audits" / "stage3b2_single_variable_selection.md"
    lines = [
        "# Stage 3B.2 Single Variable Selection",
        "",
        "This audit is read-only with respect to official strategy sources.",
        "",
        "## Selected Variable",
        "",
        f"- Variable: `{SELECTED_VARIABLE['name']}`",
        f"- Current value: `{SELECTED_VARIABLE['old_value']}`",
        f"- New value: `{SELECTED_VARIABLE['new_value']}`",
        f"- Source: `{SELECTED_VARIABLE['source_path']}:{SELECTED_VARIABLE['line']}`",
        f"- Decision surface: `{SELECTED_VARIABLE['decision_surface']}`",
        f"- Rule: {SELECTED_VARIABLE['transformation_rule']}",
        f"- Hypothesis: {SELECTED_VARIABLE['hypothesis']}",
        "",
        "## Excluded Forbidden Variables",
        "",
    ]
    for item in audit["forbidden_variables_excluded"]:
        lines.append(f"- `{item['variable_name']}`: {item['reason']}")
    lines.extend(["", "## Candidate Thresholds", ""])
    for item in audit["candidate_variables"]:
        flag = "selected" if item["allowed_by_stage3b2"] else "not selected"
        lines.append(f"- `{item['variable_name']}` at `{item['source']}` = `{item['current_value']}`: {flag}; surface `{item['decision_surface']}`; risk `{item['change_risk']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def create_experiment_spec(repo_root: Path, campaign: dict, experiment_id: str, audit: dict[str, Any]) -> dict[str, Any]:
    fixed = campaign["fixed_backtest"]
    dataset = load_simple_yaml(repo_root / fixed["dataset_manifest"])
    snapshot = load_simple_yaml(repo_root / campaign["sealed_offline_backtest"]["exchange_snapshot"] / "manifest.yaml")
    leverage = snapshot.get("leverage_tier_artifact") or {}
    spec = {
        "schema_version": "stage3b2-experiment-spec-v1",
        "experiment_type": "single_variable_semantic_mutation",
        "campaign_id": campaign["campaign_id"],
        "experiment_id": str(experiment_id),
        "strategy_family": "regime_aware",
        "base_strategy_name": BASE_STRATEGY_NAME,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "selected_variable": SELECTED_VARIABLE["name"],
        "source_location": {
            "path": SELECTED_VARIABLE["source_path"],
            "candidate_file": SELECTED_VARIABLE["source_file"],
            "line": SELECTED_VARIABLE["line"],
        },
        "old_value": SELECTED_VARIABLE["old_value"],
        "new_value": SELECTED_VARIABLE["new_value"],
        "transformation_rule": SELECTED_VARIABLE["transformation_rule"],
        "change_rationale": "Exercise one pre-authorized short-entry threshold mutation in an isolated candidate.",
        "hypothesis": SELECTED_VARIABLE["hypothesis"],
        "expected_affected_decision_surface": SELECTED_VARIABLE["decision_surface"],
        "explicitly_unaffected_surfaces": [
            "can_short",
            "timeframe",
            "startup_candle_count",
            "leverage",
            "fee",
            "funding_model",
            "margin_mode",
            "liquidation",
            "dataset",
            "exchange_snapshot",
            "long_entry_thresholds",
            "exit_logic",
        ],
        "allowed_ast_diff": {
            "file": SELECTED_VARIABLE["source_file"],
            "node": "Constant",
            "parent": "Compare",
            "left": SELECTED_VARIABLE["left"],
            "operator": SELECTED_VARIABLE["operator"],
            "old_value": SELECTED_VARIABLE["old_value"],
            "new_value": SELECTED_VARIABLE["new_value"],
            "semantic_mutation_count": 1,
        },
        "forbidden_changes": [
            "second semantic variable",
            "second source location",
            "operator changes",
            "import changes",
            "class inheritance changes",
            "function signature changes",
            "market/data/leverage/risk config changes",
        ],
        "fixture_id": "stage3a5-futures-f3-cert-003",
        "runtime_fingerprint": runtime_fingerprint(repo_root, fixed["runtime_config"]),
        "dataset_hash": dataset.get("aggregate_sha256"),
        "exchange_snapshot_hash": snapshot.get("aggregate_sha256"),
        "leverage_tier_hash": leverage.get("sha256"),
        "baseline_trade_hash": EXPECTED_BASELINE_TRADE_HASH,
        "quality_evaluation_enabled": False,
        "champion_promotion_enabled": False,
        "sealed_holdout_enabled": False,
        "selection_audit_sha256": stable_hash(audit),
        "created_at": utc_now(),
    }
    root = experiment_root(repo_root, campaign["campaign_id"], experiment_id)
    root.mkdir(parents=True, exist_ok=True)
    dump_manifest(root / "experiment-spec.yaml", spec)
    pretty(root / "experiment-spec.json", spec)
    return spec


def create_mutated_candidate(repo_root: Path, campaign: dict, experiment_id: str, spec: dict) -> dict[str, Any]:
    campaign_id = campaign["campaign_id"]
    candidate_class = candidate_class_name(experiment_id)
    root = candidate_root(repo_root, campaign_id, experiment_id)
    candidate_file = root / f"{candidate_class}.py"
    manifest_path = root / "candidate-manifest.yaml"
    validate_candidate_write_scope(repo_root, campaign, experiment_id, [candidate_file, manifest_path, root / "file-hashes.json", root / "generation-record.json"])
    assert_no_symlink_escape(root, repo_root / "research" / "candidates")
    if sha256_file(repo_root / BASE_STRATEGY_PATH).upper() != BASE_STRATEGY_SHA256:
        raise Stage3B2Error("escalated", "validation_error", "base_strategy_integrity_violation", "official base strategy hash changed")
    if root.exists() and any(root.iterdir()):
        raise Stage3B2Error("mutation_validation_failed", "validation_error", "candidate_directory_not_empty", repo_rel(repo_root, root))
    root.mkdir(parents=True, exist_ok=False)
    candidate_file.write_text(expected_candidate_source(repo_root, candidate_class), encoding="utf-8")
    for name in DEPENDENCY_FILES:
        shutil.copy2(repo_root / "strategies" / name, root / name)
    mutated_dep, ast_diff = expected_mutated_dependency(repo_root)
    (root / SELECTED_VARIABLE["source_file"]).write_text(mutated_dep, encoding="utf-8")
    verification = verify_ast_single_mutation(repo_root, root, candidate_class)
    if not verification["ok"]:
        raise Stage3B2Error("mutation_validation_failed", "implementation_error", "unauthorized_candidate_semantic_diff", "candidate diff exceeded single-variable spec")
    manifest = {
        "schema_version": "stage3b2-candidate-manifest-v1",
        "campaign_id": campaign_id,
        "experiment_id": str(experiment_id),
        "experiment_type": "single_variable_semantic_mutation",
        "candidate_strategy_class": candidate_class,
        "candidate_strategy_path": repo_rel(repo_root, candidate_file),
        "base_strategy_name": BASE_STRATEGY_NAME,
        "base_strategy_path": BASE_STRATEGY_PATH.as_posix(),
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "candidate_strategy_sha256": sha256_file(candidate_file),
        "candidate_dependency_hashes": dependency_hashes(repo_root, root),
        "experiment_spec_hash": stable_hash(spec),
        "selected_variable": SELECTED_VARIABLE["name"],
        "old_value": SELECTED_VARIABLE["old_value"],
        "new_value": SELECTED_VARIABLE["new_value"],
        "ast_diff": ast_diff,
        "semantic_mutation_count": 1,
        "generator_version": GENERATOR_VERSION,
        "mutation_tool_version": MUTATION_TOOL_VERSION,
        "created_at": utc_now(),
    }
    dump_manifest(manifest_path, manifest)
    pretty(root / "file-hashes.json", {"candidate_manifest_sha256": sha256_file(manifest_path), "candidate_strategy_sha256": sha256_file(candidate_file), "dependencies": dependency_hashes(repo_root, root)})
    pretty(root / "generation-record.json", {"generator_version": GENERATOR_VERSION, "mutation_tool_version": MUTATION_TOOL_VERSION, "ast_diff": ast_diff})
    return {
        "candidate_class": candidate_class,
        "candidate_dir": repo_rel(repo_root, root),
        "candidate_path": repo_rel(repo_root, candidate_file),
        "candidate_manifest": repo_rel(repo_root, manifest_path),
        "candidate_strategy_sha256": sha256_file(candidate_file),
        "diff_verification": verification,
    }


def runtime_python(repo_root: Path, campaign: dict) -> Path:
    runtime = load_simple_yaml(repo_root / campaign["fixed_backtest"]["runtime_config"])
    ref = Path(str(runtime["python_executable"]))
    return ref if ref.is_absolute() else repo_root / ref


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
    return {"ok": result.returncode == 0 and candidate_class in result.stdout, "returncode": result.returncode, "candidate_seen": candidate_class in result.stdout, "command": command, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}


def class_uniqueness(candidate_dir: Path, candidate_class: str) -> dict[str, Any]:
    pattern = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
    matches = []
    legacy = []
    for path in candidate_dir.glob("*.py"):
        for name in pattern.findall(path.read_text(encoding="utf-8")):
            if name == candidate_class:
                matches.append(path.name)
            if name == BASE_STRATEGY_NAME:
                legacy.append(path.name)
    return {"ok": len(matches) == 1 and not legacy, "candidate_class_matches": matches, "legacy_class_matches": legacy}


def static_validate(repo_root: Path, campaign: dict, experiment_id: str, candidate: dict, spec: dict) -> dict[str, Any]:
    fixed = campaign["fixed_backtest"]
    candidate_dir = repo_root / candidate["candidate_dir"]
    candidate_file = repo_root / candidate["candidate_path"]
    for path in candidate_dir.glob("*.py"):
        py_compile.compile(str(path), doraise=True)
    diff = verify_ast_single_mutation(repo_root, candidate_dir, candidate["candidate_class"])
    load_check = freqtrade_load_check(repo_root, campaign, candidate_dir, candidate["candidate_class"])
    uniqueness = class_uniqueness(candidate_dir, candidate["candidate_class"])
    contract = validate_contract(candidate_file, candidate["candidate_class"], repo_root / fixed["config"], repo_root / fixed["dataset_manifest"], repo_root / campaign["sealed_offline_backtest"]["exchange_snapshot"])
    manifest_integrity = {"path": candidate["candidate_manifest"], "sha256": sha256_file(repo_root / candidate["candidate_manifest"])}
    spec_path = repo_root / "research" / "experiments" / campaign["campaign_id"] / experiment_id / "experiment-spec.yaml"
    spec_integrity = {"path": repo_rel(repo_root, spec_path), "sha256": sha256_file(spec_path), "json_hash": stable_hash(spec)}
    dataset = load_simple_yaml(repo_root / fixed["dataset_manifest"])
    snapshot = load_simple_yaml(repo_root / campaign["sealed_offline_backtest"]["exchange_snapshot"] / "manifest.yaml")
    leverage = snapshot.get("leverage_tier_artifact") or {}
    checks = {
        "python_compile": {"ok": True},
        "freqtrade_strategy_load": load_check,
        "class_uniqueness": uniqueness,
        "strategy_market_contract": contract,
        "base_strategy_integrity": verify_base_strategy(repo_root, "stage3b2_static_validation"),
        "candidate_manifest_integrity": manifest_integrity,
        "experiment_spec_integrity": spec_integrity,
        "ast_single_mutation": diff,
        "fixture_integrity": {"fixture_id": "stage3a5-futures-f3-cert-003"},
        "dataset_integrity": {"aggregate_sha256": dataset.get("aggregate_sha256")},
        "exchange_snapshot_integrity": {"aggregate_sha256": snapshot.get("aggregate_sha256")},
        "leverage_tier_integrity": {"sha256": leverage.get("sha256")},
        "runtime_fingerprint": runtime_fingerprint(repo_root, fixed["runtime_config"]),
        "forbidden_import_path_scan": {"ok": not source_scan(candidate_dir), "hits": source_scan(candidate_dir)},
        "network_disabled": {"ok": True, "policy": "socket_blocker"},
    }
    ok = load_check["ok"] and uniqueness["ok"] and contract["ok"] and diff["ok"] and checks["forbidden_import_path_scan"]["ok"]
    checks["ok"] = ok
    if not ok:
        raise Stage3B2Error("mutation_validation_failed", "validation_error", "candidate_static_validation_failed", "candidate static validation failed")
    return checks


def run_candidate(repo_root: Path, campaign: dict, experiment_id: str, candidate: dict, run_name: str) -> dict[str, Any]:
    candidate_campaign = json.loads(json.dumps(campaign))
    candidate_campaign["fixed_backtest"]["strategy"] = candidate["candidate_class"]
    candidate_campaign["fixed_backtest"]["strategy_file"] = candidate["candidate_path"]
    candidate_campaign["fixed_backtest"]["strategy_path"] = candidate["candidate_dir"]
    snapshot = repo_root / candidate_campaign["sealed_offline_backtest"]["exchange_snapshot"]
    result = run_offline_backtest(repo_root, candidate_campaign, experiment_id, run_name, snapshot)
    run_dir = repo_root / "research" / "results" / campaign["campaign_id"] / experiment_id / run_name
    if result["status"] != "accepted":
        raise Stage3B2Error("execution_failed", result.get("failure_type") or "backtest_error", result.get("reason_code") or "candidate_execution_failed", result.get("message") or "candidate backtest failed")
    result_path = find_result_json(run_dir)
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    trades = write_normalized_trades(run_dir, result_path, candidate["candidate_class"])
    summary = metric_summary(metrics, trades)
    report_path = run_dir / "runner-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update({"run_name": run_name, "summary": summary, "cache": "none"})
    pretty(report_path, report)
    pretty(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    non_loopback = [item for item in report.get("network_attempts") or [] if not item.get("loopback")]
    if non_loopback:
        raise Stage3B2Error("escalated", "infra_permanent", "offline_contract_violation", f"non-loopback network attempt: {non_loopback}")
    return {"run_name": run_name, "run_dir": repo_rel(repo_root, run_dir), "runner_report": repo_rel(repo_root, report_path), "summary": summary, "normalized_trade_hash": trades["sha256"], "normalized_trades": trades, "input_fingerprint": report.get("input_fingerprint"), "network_attempts": report.get("network_attempts") or []}


def trade_key(row: dict[str, Any]) -> str:
    return "|".join(str(row.get(key, "")) for key in ("pair", "open_date", "close_date", "is_short", "enter_tag", "exit_reason"))


def trade_level_diff(baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    base_map = {trade_key(row): row for row in baseline_rows}
    cand_map = {trade_key(row): row for row in candidate_rows}
    added = [cand_map[key] for key in sorted(set(cand_map) - set(base_map))]
    deleted = [base_map[key] for key in sorted(set(base_map) - set(cand_map))]
    modified = []
    for key in sorted(set(base_map) & set(cand_map)):
        if base_map[key] != cand_map[key]:
            modified.append({"key": key, "baseline": base_map[key], "candidate": cand_map[key]})
    return {"added_trades": added, "deleted_trades": deleted, "modified_trades": modified}


def compare_baseline_candidate(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    comparison = compare_summaries(baseline["summary"], candidate["summary"])
    rows = trade_level_diff(
        json.loads((Path(baseline["run_dir"]) / "normalized-trades.json").read_text(encoding="utf-8")).get("rows", []) if Path(baseline["run_dir"]).exists() else [],
        candidate["normalized_trades"].get("rows", []),
    )
    comparison["trade_level_diff"] = rows
    comparison["behavior_verdict"] = "behavior_unchanged" if comparison["consistent"] and not rows["added_trades"] and not rows["deleted_trades"] and not rows["modified_trades"] else "behavior_changed"
    comparison["quality_evaluation"] = "not_evaluated"
    comparison["promotion_status"] = "not_allowed"
    return comparison


def init_registry(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stage3b2_single_variable_experiments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          campaign_id TEXT NOT NULL,
          experiment_id TEXT NOT NULL,
          experiment_spec_path TEXT NOT NULL,
          base_strategy_hash TEXT NOT NULL,
          candidate_strategy_hash TEXT,
          selected_variable TEXT NOT NULL,
          old_value TEXT NOT NULL,
          new_value TEXT NOT NULL,
          semantic_mutation_count INTEGER NOT NULL,
          candidate_class TEXT NOT NULL,
          candidate_path TEXT NOT NULL,
          static_validation TEXT,
          run_a_report TEXT,
          run_b_report TEXT,
          reproducibility_verdict TEXT,
          baseline_trade_hash TEXT,
          candidate_trade_hash TEXT,
          behavioral_diff_path TEXT,
          engineering_verdict TEXT,
          quality_evaluation_status TEXT NOT NULL DEFAULT 'not_evaluated',
          promotion_status TEXT NOT NULL DEFAULT 'not_allowed',
          artifacts_json TEXT NOT NULL DEFAULT '{}',
          failure_class TEXT,
          failure_reason TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(campaign_id, experiment_id)
        );
        """
    )


def record_registry(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO stage3b2_single_variable_experiments(
          campaign_id, experiment_id, experiment_spec_path, base_strategy_hash,
          candidate_strategy_hash, selected_variable, old_value, new_value,
          semantic_mutation_count, candidate_class, candidate_path, static_validation,
          run_a_report, run_b_report, reproducibility_verdict, baseline_trade_hash,
          candidate_trade_hash, behavioral_diff_path, engineering_verdict,
          quality_evaluation_status, promotion_status, artifacts_json,
          failure_class, failure_reason, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_evaluated', 'not_allowed', ?, ?, ?, ?, ?)
        ON CONFLICT(campaign_id, experiment_id) DO UPDATE SET
          candidate_strategy_hash = excluded.candidate_strategy_hash,
          static_validation = excluded.static_validation,
          run_a_report = excluded.run_a_report,
          run_b_report = excluded.run_b_report,
          reproducibility_verdict = excluded.reproducibility_verdict,
          candidate_trade_hash = excluded.candidate_trade_hash,
          behavioral_diff_path = excluded.behavioral_diff_path,
          engineering_verdict = excluded.engineering_verdict,
          artifacts_json = excluded.artifacts_json,
          failure_class = excluded.failure_class,
          failure_reason = excluded.failure_reason,
          updated_at = excluded.updated_at
        """,
        (
            payload["campaign_id"],
            payload["experiment_id"],
            payload["experiment_spec_path"],
            payload["base_strategy_hash"],
            payload["candidate_strategy_hash"],
            payload["selected_variable"],
            str(payload["old_value"]),
            str(payload["new_value"]),
            payload["semantic_mutation_count"],
            payload["candidate_class"],
            payload["candidate_path"],
            payload["static_validation"],
            payload["run_a_report"],
            payload["run_b_report"],
            payload["reproducibility_verdict"],
            payload["baseline_trade_hash"],
            payload["candidate_trade_hash"],
            payload["behavioral_diff_path"],
            payload["engineering_verdict"],
            json.dumps(payload.get("artifacts") or {}, sort_keys=True),
            payload.get("failure_class"),
            payload.get("failure_reason"),
            now,
            now,
        ),
    )


def run_stage3b2(repo_root: str | Path, campaign_path: str | Path, experiment_id: str = "1") -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    campaign = load_campaign(campaign_path)
    if campaign.get("runner_type") != "single_variable_semantic_mutation":
        raise Stage3B2Error("mutation_validation_failed", "validation_error", "campaign_mode_mismatch", "runner_type must be single_variable_semantic_mutation")
    if int((campaign.get("stage3b2") or {}).get("max_semantic_mutations", 1)) != 1:
        raise Stage3B2Error("mutation_validation_failed", "validation_error", "campaign_mutation_budget_invalid", "max_semantic_mutations must be 1")
    started = utc_now()
    start = time.monotonic()
    integrity = [verify_base_strategy(repo_root, "start")]
    audit = audit_variable_selection(repo_root)
    audit_path = write_variable_audit(repo_root, audit)
    spec = create_experiment_spec(repo_root, campaign, experiment_id, audit)
    spec_path = experiment_root(repo_root, campaign["campaign_id"], experiment_id) / "experiment-spec.yaml"
    candidate = create_mutated_candidate(repo_root, campaign, experiment_id, spec)
    integrity.append(verify_base_strategy(repo_root, "after_candidate_creation"))
    static_checks = static_validate(repo_root, campaign, experiment_id, candidate, spec)
    baseline = baseline_reference(repo_root, campaign)
    run_a = run_candidate(repo_root, campaign, experiment_id, candidate, "CANDIDATE-RUN-A")
    run_b = run_candidate(repo_root, campaign, experiment_id, candidate, "CANDIDATE-RUN-B")
    integrity.append(verify_base_strategy(repo_root, "after_candidate_runs"))
    repro = compare_summaries(run_a["summary"], run_b["summary"])
    repro["input_fingerprint_consistent"] = run_a["input_fingerprint"] == run_b["input_fingerprint"]
    repro["normalized_trade_hash_consistent"] = run_a["normalized_trade_hash"] == run_b["normalized_trade_hash"]
    if not repro["consistent"] or not repro["input_fingerprint_consistent"] or not repro["normalized_trade_hash_consistent"]:
        raise Stage3B2Error("reproducibility_failed", "validation_error", "candidate_reproducibility_mismatch", "CANDIDATE-RUN-A and CANDIDATE-RUN-B differ")
    root = repo_root / "research" / "results" / campaign["campaign_id"] / experiment_id
    pretty(root / "candidate-reproducibility-comparison.json", repro)
    behavior = compare_baseline_candidate(baseline, run_a)
    pretty(root / "baseline-candidate-behavioral-comparison.json", behavior)
    engineering_verdict = (
        "mutation_verified_behavior_changed"
        if behavior["behavior_verdict"] == "behavior_changed"
        else "mutation_verified_behavior_unchanged"
    )
    if engineering_verdict not in FINAL_STATES or any(term in engineering_verdict for term in FORBIDDEN_STATUS_TERMS):
        raise Stage3B2Error("mutation_validation_failed", "implementation_error", "invalid_engineering_verdict", engineering_verdict)
    final_report = {
        "schema_version": "stage3b2-final-report-v1",
        "campaign_id": campaign["campaign_id"],
        "experiment_id": str(experiment_id),
        "status": engineering_verdict,
        "stage3b2_complete": True,
        "started_at": started,
        "completed_at": utc_now(),
        "wall_clock_seconds": round(time.monotonic() - start, 3),
        "variable_selection_audit": repo_rel(repo_root, audit_path),
        "experiment_spec": repo_rel(repo_root, spec_path),
        "candidate": candidate,
        "base_strategy_integrity_checks": integrity + [verify_base_strategy(repo_root, "end")],
        "static_validation": static_checks,
        "baseline_reference": baseline,
        "candidate_run_a": run_a,
        "candidate_run_b": run_b,
        "candidate_reproducibility": repro,
        "baseline_candidate_behavior": behavior,
        "quality_evaluation_status": "not_evaluated",
        "promotion_status": "not_allowed",
        "safety": {
            "hyperopt_run": False,
            "lookahead_analysis_run": False,
            "recursive_analysis_run": False,
            "followup_hypotheses_generated": False,
            "champion_promoted": False,
            "sealed_holdout_accessed": False,
            "quality_ranking_enabled": False,
        },
    }
    final_path = root / "stage3b2-final-report.json"
    pretty(final_path, final_report)
    conn = sqlite3.connect(repo_root / "research" / "registry" / "research.db")
    try:
        init_registry(conn)
        record_registry(
            conn,
            {
                "campaign_id": campaign["campaign_id"],
                "experiment_id": str(experiment_id),
                "experiment_spec_path": repo_rel(repo_root, spec_path),
                "base_strategy_hash": BASE_STRATEGY_SHA256,
                "candidate_strategy_hash": candidate["candidate_strategy_sha256"],
                "selected_variable": SELECTED_VARIABLE["name"],
                "old_value": SELECTED_VARIABLE["old_value"],
                "new_value": SELECTED_VARIABLE["new_value"],
                "semantic_mutation_count": 1,
                "candidate_class": candidate["candidate_class"],
                "candidate_path": candidate["candidate_path"],
                "static_validation": "passed",
                "run_a_report": run_a["runner_report"],
                "run_b_report": run_b["runner_report"],
                "reproducibility_verdict": "passed",
                "baseline_trade_hash": baseline["normalized_trade_hash"],
                "candidate_trade_hash": run_a["normalized_trade_hash"],
                "behavioral_diff_path": repo_rel(repo_root, root / "baseline-candidate-behavioral-comparison.json"),
                "engineering_verdict": engineering_verdict,
                "artifacts": {
                    "final_report": repo_rel(repo_root, final_path),
                    "variable_selection_audit": repo_rel(repo_root, audit_path),
                    "experiment_spec": repo_rel(repo_root, spec_path),
                },
            },
        )
        conn.commit()
    finally:
        conn.close()
    final_report["registry"] = {"db_path": "research/registry/research.db", "table": "stage3b2_single_variable_experiments", "engineering_verdict": engineering_verdict}
    pretty(final_path, final_report)
    return final_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 3B.2 single-variable semantic mutation.")
    parser.add_argument("--campaign", default="research/campaigns/active/demo-stage3b2-single-variable.yaml")
    parser.add_argument("--experiment-id", default="1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = run_stage3b2(Path.cwd(), args.campaign, args.experiment_id)
    except Stage3B2Error as exc:
        payload = {"status": exc.status, "stage3b2_complete": False, "failure_type": exc.failure_type, "reason_code": exc.reason_code, "message": exc.message}
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
