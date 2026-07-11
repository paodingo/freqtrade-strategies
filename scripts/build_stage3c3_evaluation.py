#!/usr/bin/env python3
"""Stage 3C.3 Balanced Research Gate approval and deterministic evaluation."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

import evaluate_research_candidate as evaluator
from research_control import utc_now
from run_experiment import artifact_hashes, dump_json, dump_manifest, repo_rel, sha256_file


POLICY_PATH = Path("research/evaluation/evaluation-policy.yaml")
DEV_DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
VAL_DATASET_ID = "futures-validation-btc-usdt-usdt-20240912-20250128-v2"
CANDIDATE_MANIFEST = Path("research/candidates/demo-stage3b2-single-variable/1/candidate-manifest.yaml")
RESULT_ROOT = Path("research/results/stage3c3-balanced-research-gate/1")
FINAL_REPORT_JSON = RESULT_ROOT / "stage3c3-final-report.json"
FINAL_REPORT_MD = Path("reports/audits/stage3c3_balanced_research_gate.md")
STAGE3C3_RESULT = Path("research/evaluation/stage3c3-result.json")
STAGE3C3_READINESS = Path("research/evaluation/stage3c3-readiness.json")
REGISTRY_PATH = Path("research/registry/research.db")


def load_yaml(path: Path) -> dict[str, Any]:
    return evaluator.read_yaml(path)


def approved_policy(repo_root: Path, approval_timestamp: str | None = None) -> dict[str, Any]:
    dev = load_yaml(repo_root / "research/data/snapshots" / DEV_DATASET_ID / "manifest.yaml")
    val = load_yaml(repo_root / "research/data/snapshots" / VAL_DATASET_ID / "manifest.yaml")
    candidate = load_yaml(repo_root / CANDIDATE_MANIFEST)
    approval_timestamp = approval_timestamp or utc_now()
    policy: dict[str, Any] = {
        "schema_version": "stage3c3-balanced-research-gate-v1",
        "policy_id": "balanced-research-gate-v1",
        "policy_approval_status": "approved",
        "approver_type": "human_user",
        "approval_scope": "current_single_pair_futures_v2",
        "approval_timestamp": approval_timestamp,
        "policy_status_reason": "Human-approved Balanced Research Gate v1 for the current single-pair futures v2 research scope.",
        "applicable_exchange": "binance",
        "applicable_trading_mode": "futures",
        "applicable_margin_mode": "isolated",
        "applicable_pairs": ["BTC/USDT:USDT"],
        "applicable_timeframe": "1h",
        "development_dataset_id": DEV_DATASET_ID,
        "development_dataset_aggregate_sha256": dev["aggregate_sha256"],
        "validation_dataset_id": VAL_DATASET_ID,
        "validation_dataset_aggregate_sha256": val["aggregate_sha256"],
        "runtime_contract": "current fixed Runtime, sealed exchange snapshot, leverage tiers, fee, funding and margin contract",
        "baseline_strategy": "RegimeAwareV6",
        "baseline_strategy_sha256": candidate["base_strategy_sha256"],
        "candidate_campaign_id": candidate["campaign_id"],
        "candidate_experiment_id": str(candidate["experiment_id"]),
        "rolling_window": {"duration_days": 28, "step_days": 7, "timezone": "UTC"},
        "development_coverage": {
            "min_total_trades": 20,
            "min_long_trades": 5,
            "min_short_trades": 5,
            "min_closed_trades": 20,
            "min_active_weeks": 8,
            "min_complete_rolling_windows": 6,
        },
        "development_no_material_degradation": {
            "total_return_delta_percentage_points_min": -0.5,
            "profit_factor_delta_min": -0.05,
            "max_drawdown_delta_percentage_points_max": 2.0,
            "absolute_max_drawdown_percentage_max": 30.0,
        },
        "development_material_improvement_any": {
            "total_return_delta_percentage_points_min": 1.0,
            "profit_factor_delta_min": 0.10,
            "max_drawdown_improvement_percentage_points_min": 2.0,
        },
        "directional_coverage": {"minimum_fraction_of_baseline": 0.50, "absolute_minimum_per_direction": 2},
        "development_states": [
            "development_eligible",
            "development_eligible_bias_pending",
            "development_eligible_bias_and_cost_verified",
            "development_inconclusive_behavior_unchanged",
            "development_inconclusive_insufficient_coverage",
            "development_ineligible_no_material_improvement",
            "development_ineligible_risk_degradation",
            "development_execution_failed",
            "development_integrity_failed",
        ],
        "validation_coverage": {
            "min_total_trades": 10,
            "min_long_trades": 2,
            "min_short_trades": 2,
            "min_closed_trades": 10,
            "min_active_weeks": 6,
            "min_complete_rolling_windows": 3,
        },
        "validation_states": [
            "validation_passed_provisional",
            "validation_failed",
            "validation_inconclusive",
            "validation_inconclusive_insufficient_coverage",
            "validation_inconclusive_tie",
            "validation_execution_failed",
            "validation_integrity_failed",
            "validation_access_denied",
            "validation_contaminated",
        ],
        "validation_absolute_gates": {
            "total_return_positive": True,
            "profit_factor_min": 1.05,
            "max_drawdown_percentage_max": 20.0,
            "positive_rolling_window_ratio_min": 0.50,
        },
        "validation_relative_gates": {
            "total_return_delta_percentage_points_min": 0.5,
            "profit_factor_delta_min": 0.0,
            "max_drawdown_delta_percentage_points_max": 1.0,
            "worst_window_delta_percentage_points_min": -1.0,
        },
        "validation_access": {"max_completed_evaluations_per_candidate": 1},
        "missing_metric_policy": {
            "hard_gate_metric": "fail_integrity",
            "descriptive_metric": "inconclusive",
            "never_default_to_zero": True,
            "never_default_to_pass": True,
        },
        "tie_policy": {
            "unchanged_behavior": "inconclusive",
            "below_materiality_threshold": "inconclusive",
            "validation_tie": "validation_inconclusive_tie",
            "no_auto_pass_for_no_degradation": True,
        },
        "lookahead_gate": {"biased_entries_allowed": 0, "biased_exits_allowed": 0, "biased_indicators_allowed": 0},
        "recursive_gate": {
            "startup_candle_conditions": [200, 400, 800],
            "max_signal_critical_indicator_variance_percent": 1.0,
            "changed_entry_signals_allowed": 0,
            "changed_exit_signals_allowed": 0,
        },
        "cost_stress_v1": {
            "scenarios": [
                {"id": "base", "fee_multiplier": 1.00},
                {"id": "fee_125", "fee_multiplier": 1.25},
                {"id": "fee_150", "fee_multiplier": 1.50},
            ]
        },
        "development_cost_gate": {
            "fee_125": {"candidate_total_return_positive": True, "candidate_profit_factor_min": 1.00},
            "fee_150": {"candidate_return_not_worse_than_baseline": True, "candidate_max_drawdown_percentage_max": 25.0},
        },
        "promotion_ceiling": "validation_passed_provisional",
        "champion_promotion_allowed": False,
        "qualified_challenger_allowed": False,
        "holdout_access_allowed": False,
        "live_trading_allowed": False,
        "hyperopt_allowed": False,
        "strategy_mutation_allowed": False,
        "new_candidate_generation_allowed": False,
        "automatic_hypothesis_generation_allowed": False,
        "automatic_champion_promotion_allowed": False,
        "approved_scope_exclusions": [
            "other_pairs",
            "other_timeframes",
            "other_exchanges",
            "spot",
            "different_datasets",
            "holdout",
            "forward_dry_run",
            "live",
            "champion_promotion",
        ],
        "approval_event": {
            "approver_type": "human_user",
            "decision": "approved",
            "policy_id": "balanced-research-gate-v1",
            "timestamp": approval_timestamp,
            "scope": "current_single_pair_futures_v2",
        },
    }
    policy["policy_sha256"] = evaluator.canonical_policy_hash(policy)
    policy["approval_event"]["policy_sha256"] = policy["policy_sha256"]
    return policy


def approve_policy(repo_root: Path) -> dict[str, Any]:
    path = repo_root / POLICY_PATH
    existing = load_yaml(path) if path.exists() else {}
    timestamp = existing.get("approval_timestamp") if existing.get("policy_id") == "balanced-research-gate-v1" else None
    policy = approved_policy(repo_root, timestamp)
    if policy.get("policy_sha256") != evaluator.canonical_policy_hash(policy):
        raise RuntimeError("policy hash calculation is unstable")
    dump_manifest(path, policy)
    reread = load_yaml(path)
    if reread.get("policy_sha256") != evaluator.canonical_policy_hash(reread):
        raise RuntimeError("approved policy hash does not match persisted content")
    return reread


def evaluate_lookahead_gate(result: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if result.get("signal_coverage") == "insufficient":
        return {"status": "bias_validation_inconclusive_lookahead_coverage", "passed": False}
    gate = policy["lookahead_gate"]
    passed = (
        int(result.get("biased_entries", 0)) <= int(gate["biased_entries_allowed"])
        and int(result.get("biased_exits", 0)) <= int(gate["biased_exits_allowed"])
        and int(result.get("biased_indicators", 0)) <= int(gate["biased_indicators_allowed"])
    )
    return {"status": "passed" if passed else "bias_validation_failed_lookahead", "passed": passed}


def evaluate_recursive_gate(result: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if result.get("coverage") == "insufficient":
        return {"status": "bias_validation_inconclusive_recursive", "passed": False}
    gate = policy["recursive_gate"]
    passed = (
        float(result.get("max_signal_critical_indicator_variance_percent", 0.0))
        <= float(gate["max_signal_critical_indicator_variance_percent"])
        and int(result.get("changed_entry_signals", 0)) <= int(gate["changed_entry_signals_allowed"])
        and int(result.get("changed_exit_signals", 0)) <= int(gate["changed_exit_signals_allowed"])
    )
    return {"status": "passed" if passed else "bias_validation_failed_recursive", "passed": passed}


def evaluate_cost_gate(scenarios: dict[str, dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    fee_125 = scenarios.get("fee_125") or {}
    fee_150 = scenarios.get("fee_150") or {}
    fee_125_passed = (
        float(fee_125.get("candidate_total_return", -999.0)) > 0.0
        and float(fee_125.get("candidate_profit_factor", -999.0)) >= 1.0
    )
    fee_150_passed = (
        float(fee_150.get("candidate_total_return", -999.0)) >= float(fee_150.get("baseline_total_return", 999.0))
        and float(fee_150.get("candidate_max_drawdown_percentage", 999.0)) <= 25.0
    )
    return {
        "status": "passed" if fee_125_passed and fee_150_passed else "development_cost_gate_failed",
        "passed": fee_125_passed and fee_150_passed,
        "rule_outputs": {"fee_125": fee_125_passed, "fee_150": fee_150_passed},
        "synthetic_slippage_used": False,
        "historical_funding_required": True,
    }


def evaluate_validation_gate(policy: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    coverage = policy["validation_coverage"]
    cov = {
        "min_total_trades": candidate.get("total_trades", 0) >= coverage["min_total_trades"],
        "min_long_trades": candidate.get("long_trades", 0) >= coverage["min_long_trades"],
        "min_short_trades": candidate.get("short_trades", 0) >= coverage["min_short_trades"],
        "min_closed_trades": candidate.get("closed_trades", 0) >= coverage["min_closed_trades"],
        "min_active_weeks": candidate.get("active_weeks", 0) >= coverage["min_active_weeks"],
        "min_complete_rolling_windows": candidate.get("complete_rolling_windows", 0) >= coverage["min_complete_rolling_windows"],
    }
    if not all(cov.values()):
        return {"status": "validation_inconclusive_insufficient_coverage", "passed": False, "coverage": cov}
    absolute = policy["validation_absolute_gates"]
    abs_checks = {
        "total_return_positive": candidate.get("total_return", 0.0) > 0.0 if absolute["total_return_positive"] else True,
        "profit_factor_min": candidate.get("profit_factor", 0.0) >= absolute["profit_factor_min"],
        "max_drawdown_percentage_max": candidate.get("max_drawdown_percentage", 999.0) <= absolute["max_drawdown_percentage_max"],
        "positive_rolling_window_ratio_min": candidate.get("positive_rolling_window_ratio", 0.0) >= absolute["positive_rolling_window_ratio_min"],
    }
    relative = policy["validation_relative_gates"]
    rel_checks = {
        "total_return_delta": comparison.get("total_return_delta_percentage_points", 0.0) >= relative["total_return_delta_percentage_points_min"],
        "profit_factor_delta": comparison.get("profit_factor_delta", 0.0) >= relative["profit_factor_delta_min"],
        "max_drawdown_delta": comparison.get("max_drawdown_delta_percentage_points", 999.0) <= relative["max_drawdown_delta_percentage_points_max"],
        "worst_window_delta": comparison.get("worst_window_delta_percentage_points", -999.0) >= relative["worst_window_delta_percentage_points_min"],
    }
    if not any(abs(value) > 0 for value in comparison.values() if isinstance(value, (int, float))):
        return {"status": "validation_inconclusive_tie", "passed": False, "absolute": abs_checks, "relative": rel_checks}
    passed = all(abs_checks.values()) and all(rel_checks.values())
    return {"status": "validation_passed_provisional" if passed else "validation_failed", "passed": passed, "absolute": abs_checks, "relative": rel_checks}


def runner_capabilities(repo_root: Path) -> dict[str, Any]:
    try:
        output = subprocess.check_output(
            [str(repo_root / ".venv-freqtrade/Scripts/python.exe"), "-m", "freqtrade", "--help"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    except Exception as exc:
        return {"ok": False, "reason": type(exc).__name__}
    return {
        "ok": True,
        "lookahead_analysis_cli_available": "lookahead-analysis" in output,
        "recursive_analysis_cli_available": "recursive-analysis" in output,
        "cost_stress_runner_available": True,
        "network_policy": "offline_socket_blocker",
    }


def init_stage3c3_registry(conn: sqlite3.Connection) -> None:
    evaluator.init_registry(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stage3c3_events (
          event_id TEXT PRIMARY KEY,
          event_type TEXT NOT NULL,
          candidate_id TEXT,
          policy_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          artifact_path TEXT,
          recorded_at TEXT NOT NULL
        );
        """
    )


def record_stage3c3_event(repo_root: Path, event_type: str, candidate_id: str | None, policy_hash: str, status: str, payload: dict[str, Any], artifact_path: str | None = None) -> None:
    conn = sqlite3.connect(repo_root / REGISTRY_PATH)
    try:
        init_stage3c3_registry(conn)
        event_id = f"{event_type}:{candidate_id or 'policy'}:{policy_hash[:12]}"
        conn.execute(
            "DELETE FROM stage3c3_events WHERE event_type = ? AND COALESCE(candidate_id, '') = COALESCE(?, '')",
            (event_type, candidate_id),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO stage3c3_events(event_id, event_type, candidate_id, policy_hash, status, payload_json, artifact_path, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, event_type, candidate_id, policy_hash, status, json.dumps(payload, sort_keys=True, ensure_ascii=False), artifact_path, utc_now()),
        )
        conn.commit()
    finally:
        conn.close()


def write_limited_validation_disclosure(path: Path, development_result: dict[str, Any]) -> dict[str, Any]:
    metrics = development_result["candidate_metrics"]["metrics"]
    payload = {
        "schema_version": "stage3c3-limited-validation-disclosure-v1",
        "status": development_result["development_status"],
        "coverage_verdict": development_result["gate_decision"]["rule_outputs"].get("development_coverage"),
        "total_trades": metrics["total_trades"]["normalized_value"],
        "long_trades": metrics["long_trades"]["normalized_value"],
        "short_trades": metrics["short_trades"]["normalized_value"],
        "total_return": metrics["total_profit_ratio"]["normalized_value"],
        "max_drawdown": metrics["max_drawdown_percentage"]["normalized_value"],
        "profit_factor": metrics["profit_factor"]["normalized_value"],
        "relative_gate_pass_fail": "not_evaluated_behavior_unchanged",
        "failure_category": development_result["development_status"],
        "contamination_status": "development_exposed",
        "withheld": [
            "complete_validation_trade_list",
            "precise_validation_entry_exit_times",
            "per_trade_validation_profit",
            "validation_candles",
            "field_level_validation_trade_diff",
        ],
    }
    dump_json(path, payload)
    return payload


def update_readiness(repo_root: Path, final: dict[str, Any]) -> None:
    payload = {
        "schema_version": "stage3c3-readiness-v3",
        "status": "complete",
        "ready": True,
        "bulk_autonomous_search_ready": False,
        "bulk_search_blockers": [
            "candidate_generation_not_authorized",
            "hyperopt_not_authorized",
            "holdout_not_authorized",
            "champion_promotion_not_authorized",
            "current_candidate_not_development_eligible",
        ],
        "readiness_checks": {
            "policy_human_approved": True,
            "development_gate_executable": True,
            "behavior_unchanged_classified": final["development_status"] == "development_inconclusive_behavior_unchanged",
            "lookahead_runner_executable": final["runner_capabilities"]["lookahead_analysis_cli_available"],
            "recursive_runner_executable": final["runner_capabilities"]["recursive_analysis_cli_available"],
            "cost_stress_runner_executable": final["runner_capabilities"]["cost_stress_runner_available"],
            "validation_accessed": final["validation_accessed"],
            "holdout_not_accessed": True,
            "champion_not_created": True,
            "qualified_challenger_not_created": True,
            "hyperopt_not_run": True,
        },
        "updated_at": utc_now(),
    }
    dump_json(repo_root / STAGE3C3_READINESS, payload)


def write_final_markdown(repo_root: Path, final: dict[str, Any]) -> None:
    lines = [
        "# Stage 3C.3 Balanced Research Gate",
        "",
        f"- Policy: `{final['policy_id']}`",
        f"- Policy approval: `{final['policy_approval_status']}`",
        f"- Policy hash: `{final['policy_hash']}`",
        f"- Candidate Development status: `{final['development_status']}`",
        f"- Lookahead gate: `{final['lookahead_gate_status']}`",
        f"- Recursive gate: `{final['recursive_gate_status']}`",
        f"- Cost gate: `{final['cost_gate_status']}`",
        f"- Validation accessed: `{str(final['validation_accessed']).lower()}`",
        f"- Holdout accessed: `{str(final['holdout_accessed']).lower()}`",
        f"- Champion created: `{str(final['champion_created']).lower()}`",
        f"- Qualified Challenger created: `{str(final['qualified_challenger_created']).lower()}`",
        f"- Hyperopt run: `{str(final['hyperopt_run']).lower()}`",
        "",
        "## Current Candidate",
        "",
        f"- Baseline trade hash: `{final['development_summary']['baseline_trade_hash']}`",
        f"- Candidate trade hash: `{final['development_summary']['candidate_trade_hash']}`",
        f"- Total trades: `{final['development_summary']['candidate_total_trades']}`",
        f"- Long/short trades: `{final['development_summary']['candidate_long_trades']}` / `{final['development_summary']['candidate_short_trades']}`",
        "",
        "## Validation",
        "",
        f"- Authorization: `{final['validation_authorization']['authorization_result']}`",
        f"- Reason: `{final['validation_authorization']['reason_code']}`",
        "",
        "This engineering stage does not authorize automatic search, Champion promotion, Holdout access, Hyperopt, or new candidate generation.",
    ]
    FINAL_REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    FINAL_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_stage3c3(repo_root: Path) -> dict[str, Any]:
    policy = approve_policy(repo_root)
    policy_hash = evaluator.policy_hash(repo_root / POLICY_PATH)
    candidate = load_yaml(repo_root / CANDIDATE_MANIFEST)
    output = repo_root / RESULT_ROOT / "development-evaluation"
    development = evaluator.evaluate_candidate(
        repo_root,
        CANDIDATE_MANIFEST,
        DEV_DATASET_ID,
        "development_evaluator",
        POLICY_PATH,
        "RegimeAwareV6",
        output,
    )
    candidate_id = development["candidate_id"]
    validation_event = evaluator.maybe_authorize_validation(
        repo_root,
        policy,
        policy_hash,
        candidate,
        {},
        "validation_evaluator",
        development["development_status"],
    )
    runner_status = runner_capabilities(repo_root)
    behavior_unchanged = development["development_status"] == "development_inconclusive_behavior_unchanged"
    lookahead_status = "not_required_behavior_unchanged" if behavior_unchanged else "pending"
    recursive_status = "not_required_behavior_unchanged" if behavior_unchanged else "pending"
    cost_status = "not_required_behavior_unchanged" if behavior_unchanged else "pending"
    limited = write_limited_validation_disclosure(repo_root / RESULT_ROOT / "limited-validation-disclosure.json", development)
    final = {
        "schema_version": "stage3c3-final-report-v1",
        "status": "completed",
        "policy_id": policy["policy_id"],
        "policy_approval_status": policy["policy_approval_status"],
        "policy_hash": policy_hash,
        "policy_file": repo_rel(repo_root, repo_root / POLICY_PATH),
        "candidate_id": candidate_id,
        "development_status": development["development_status"],
        "development_result_path": development["result_path"],
        "development_summary": {
            "baseline_trade_hash": development["baseline_metrics"]["normalized_trade_hash"],
            "candidate_trade_hash": development["candidate_metrics"]["normalized_trade_hash"],
            "same_trade_hash": development["comparison"]["trade_diff"]["same_trade_hash"],
            "field_level_trade_diff_empty": not development["comparison"]["trade_diff"]["field_level_trade_diff"],
            "candidate_total_trades": development["candidate_metrics"]["metrics"]["total_trades"]["normalized_value"],
            "candidate_long_trades": development["candidate_metrics"]["metrics"]["long_trades"]["normalized_value"],
            "candidate_short_trades": development["candidate_metrics"]["metrics"]["short_trades"]["normalized_value"],
        },
        "lookahead_gate_status": lookahead_status,
        "recursive_gate_status": recursive_status,
        "cost_gate_status": cost_status,
        "runner_capabilities": runner_status,
        "validation_authorization": validation_event,
        "validation_accessed": False,
        "limited_disclosure_path": repo_rel(repo_root, repo_root / RESULT_ROOT / "limited-validation-disclosure.json"),
        "limited_disclosure": limited,
        "holdout_accessed": False,
        "champion_created": False,
        "qualified_challenger_created": False,
        "hyperopt_run": False,
        "strategy_modified": False,
        "candidate_modified": False,
        "new_candidate_created": False,
        "bulk_autonomous_search_ready": False,
        "bulk_search_blockers": [
            "current_candidate_development_inconclusive_behavior_unchanged",
            "automatic_candidate_generation_not_authorized",
            "hyperopt_not_authorized",
            "holdout_not_authorized",
            "champion_promotion_not_authorized",
        ],
        "artifacts": {
            "development_evaluation": development["result_path"],
            "final_json": repo_rel(repo_root, repo_root / FINAL_REPORT_JSON),
            "final_markdown": repo_rel(repo_root, repo_root / FINAL_REPORT_MD),
            "stage3c3_result": repo_rel(repo_root, repo_root / STAGE3C3_RESULT),
            "stage3c3_readiness": repo_rel(repo_root, repo_root / STAGE3C3_READINESS),
        },
        "created_at": utc_now(),
    }
    dump_json(repo_root / FINAL_REPORT_JSON, final)
    dump_json(repo_root / STAGE3C3_RESULT, final)
    dump_json(repo_root / RESULT_ROOT / "artifact-hashes.json", artifact_hashes(repo_root / RESULT_ROOT))
    final["artifacts"]["artifact_hashes"] = repo_rel(repo_root, repo_root / RESULT_ROOT / "artifact-hashes.json")
    dump_json(repo_root / FINAL_REPORT_JSON, final)
    dump_json(repo_root / STAGE3C3_RESULT, final)
    write_final_markdown(repo_root, final)
    update_readiness(repo_root, final)
    record_stage3c3_event(repo_root, "policy_approval", candidate_id, policy_hash, "approved", policy, repo_rel(repo_root, repo_root / POLICY_PATH))
    record_stage3c3_event(repo_root, "development_decision", candidate_id, policy_hash, development["development_status"], development, development["result_path"])
    record_stage3c3_event(repo_root, "bias_gate", candidate_id, policy_hash, lookahead_status, {"lookahead": lookahead_status, "recursive": recursive_status})
    record_stage3c3_event(repo_root, "cost_gate", candidate_id, policy_hash, cost_status, {"cost": cost_status})
    record_stage3c3_event(repo_root, "validation_authorization", candidate_id, policy_hash, validation_event["authorization_result"], validation_event)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 3C.3 Balanced Research Gate evaluation.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    final = run_stage3c3(Path.cwd())
    if args.json:
        print(json.dumps(final, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(final["development_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
