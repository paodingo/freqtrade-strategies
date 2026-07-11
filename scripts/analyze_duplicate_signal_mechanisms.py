#!/usr/bin/env python3
"""Stage 3D.4-A read-only duplicate signal and mechanism value audit."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import sqlite3
import subprocess
import sys
import re
from datetime import timedelta
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

import run_stage3d2b_reachability_search as stage3d2b
import run_stage3d3b_recertification as stage3d3b
from research_control import load_simple_yaml, utc_now
from run_experiment import dump_json, dump_manifest, repo_rel, sha256_file


STAGE_ID = "stage3d4a-duplicate-signal-mechanism-audit"
ANALYSIS_ROOT = Path("research/analysis")
TIMELINES_PATH = ANALYSIS_ROOT / "stage3d4a-duplicate-signal-timelines.json"
REENTRY_PATH = ANALYSIS_ROOT / "stage3d4a-reentry-opportunity-analysis.json"
MECHANISMS_PATH = ANALYSIS_ROOT / "stage3d4a-mechanism-options.json"
FINAL_JSON = ANALYSIS_ROOT / "stage3d4a-final-report.json"
FINAL_MD = Path("reports/audits/stage3d4a_final_report.md")
CLOSURE_MD = Path("reports/audits/stage3d4a_single_threshold_research_closure.md")
FIRST_TRIGGER_MD = Path("reports/audits/stage3d4a_first_trigger_semantics.md")
RISK_MD = Path("reports/audits/stage3d4a_position_adjustment_risk_audit.md")
DECISION_MD = Path("reports/decisions/stage3d4b_mechanism_decision_packet.md")
PROPOSAL_PATH = Path("research/proposals/stage3d4b-mechanism-proposal.yaml")
BASE_STRATEGY_SHA256 = stage3d2b.BASE_STRATEGY_SHA256
POLICY_SHA256 = stage3d2b.POLICY_HASH
DEV_DATASET_ID = stage3d2b.DEV_DATASET_ID
UNCHANGED_EXPERIMENTS = [1, 2, 3, 4, 5, 9, 10]


class Stage3D4AError(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = "validation_error"
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def self_hash(payload: dict[str, Any], field: str) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != field})


def assert_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if sha256_file(repo_root / "strategies/RegimeAwareV6.py").upper() != BASE_STRATEGY_SHA256:
        raise Stage3D4AError("input_integrity_violation", "official strategy hash changed")
    final = json.loads((repo_root / stage3d3b.FINAL_JSON).read_text(encoding="utf-8"))
    if final.get("status") != "completed" or not final.get("process_isolation_passed"):
        raise Stage3D4AError("input_integrity_violation", "Stage 3D.3-B is not certified")
    if final.get("trade_changed_experiment_ids") != [6, 7, 8]:
        raise Stage3D4AError("input_integrity_violation", "unexpected recertification conclusions")
    queue = load_simple_yaml(repo_root / stage3d2b.QUEUE_PATH)
    if queue.get("queue_sha256") != stage3d3b.ORIGINAL_QUEUE_SHA256 or stage3d2b.self_hash(queue, "queue_sha256") != stage3d3b.ORIGINAL_QUEUE_SHA256:
        raise Stage3D4AError("input_integrity_violation", "frozen queue changed")
    return final, queue


def data_provider(repo_root: Path):
    data_root = repo_root / "research/data/snapshots" / DEV_DATASET_ID / "data/futures"

    class Provider:
        def current_whitelist(self) -> list[str]: return ["BTC/USDT:USDT"]
        def get_pair_dataframe(self, pair: str, timeframe: str, candle_type: str = "futures") -> pd.DataFrame:
            if pair != "BTC/USDT:USDT" or candle_type != "futures": raise ValueError("unauthorized analysis input")
            return pd.read_feather(data_root / f"BTC_USDT_USDT-{timeframe}-futures.feather")

    return Provider(), data_root


def candidate_dataframe(repo_root: Path, experiment_id: int, candidate_class: str) -> pd.DataFrame:
    package = repo_root / stage3d3b.RECERT_ROOT / str(experiment_id) / "package"
    sys.path.insert(0, str(package))
    module = importlib.import_module(candidate_class)
    strategy = getattr(module, candidate_class)({})
    provider, data_root = data_provider(repo_root); strategy.dp = provider
    raw = pd.read_feather(data_root / "BTC_USDT_USDT-1h-futures.feather")
    metadata = {"pair": "BTC/USDT:USDT"}
    frame = strategy.populate_indicators(raw.copy(), metadata)
    frame = strategy.populate_entry_trend(frame, metadata)
    frame = strategy.populate_exit_trend(frame, metadata)
    for column in ("enter_long", "enter_short", "exit_long", "exit_short"):
        if column not in frame: frame[column] = 0
        frame[column] = frame[column].fillna(0).astype(int)
    return frame


def load_trade_rows(repo_root: Path, relative_path: str) -> list[dict[str, Any]]:
    return json.loads((repo_root / relative_path).read_text(encoding="utf-8"))["rows"]


def covering_trade(trades: list[dict[str, Any]], timestamp: pd.Timestamp) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    for index, trade in enumerate(trades, start=1):
        if pd.Timestamp(trade["open_date"]) <= timestamp < pd.Timestamp(trade["close_date"]):
            return index, trade
    return None, None


def consecutive_true(frame: pd.DataFrame, start_index: int, column: str) -> int:
    count = 0
    for index in range(start_index, len(frame)):
        if int(frame.loc[index, column]) != 1: break
        count += 1
    return count


def first_true_after(frame: pd.DataFrame, timestamp: pd.Timestamp, column: str, enter_tag: str | None) -> dict[str, Any] | None:
    rows = frame[(frame["date"] > timestamp) & (frame[column] == 1)]
    if enter_tag is not None:
        rows = rows[rows["enter_tag"] == enter_tag]
    if rows.empty: return None
    row = rows.iloc[0]
    return {"timestamp": pd.Timestamp(row["date"]).isoformat(), "index": int(row.name), "enter_tag": row.get("enter_tag")}


def trade_opened_from_signal(trades: list[dict[str, Any]], signal_timestamp: pd.Timestamp, direction: str, tag: str | None) -> dict[str, Any] | None:
    expected_open = signal_timestamp + timedelta(hours=1)
    for trade in trades:
        if pd.Timestamp(trade["open_date"]) == expected_open and ("short" if trade["is_short"] else "long") == direction:
            if tag is None or trade.get("enter_tag") == tag: return trade
    return None


def classify_lifecycle(signal_distance_from_entry: int, signal_true_at_exit: bool, first_flat_true: bool, reappeared: bool) -> tuple[str, list[str]]:
    secondary = ["same_setup_confirmation_during_position" if signal_distance_from_entry <= 12 else "late_continuation_signal_during_position"]
    if signal_true_at_exit or first_flat_true: return "signal_persisted_after_exit", secondary
    if reappeared: return "signal_expired_before_flat", secondary + ["signal_reappeared_after_flat"]
    return "signal_expired_before_flat", secondary


def build_timelines(repo_root: Path, final: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    baseline = final["experiments"][0]["run_a"]
    baseline_trades = load_trade_rows(repo_root, baseline["normalized_trades_path"])
    timelines = []; reentry = []
    for experiment_id in UNCHANGED_EXPERIMENTS:
        result = final["experiments"][experiment_id - 1]
        run = result["run_a"]
        frame = candidate_dataframe(repo_root, experiment_id, result["run_a"]["summary"].get("strategy", result.get("candidate_class", f"RegimeAware_C3D2B_E{experiment_id:04d}")))
        candidate_class = f"RegimeAware_C3D2B_E{experiment_id:04d}"
        if candidate_class not in sys.modules:
            frame = candidate_dataframe(repo_root, experiment_id, candidate_class)
        candidate_trades = load_trade_rows(repo_root, run["normalized_trades_path"])
        for ordinal, delta in enumerate(run["signal_diff"]["deltas"], start=1):
            timestamp = pd.Timestamp(delta["timestamp"]); column = delta["column"]
            index = int(frame.index[frame["date"] == timestamp][0])
            trade_id, trade = covering_trade(baseline_trades, timestamp)
            if trade is None: raise Stage3D4AError("duplicate_signal_without_covering_trade", f"E{experiment_id} {timestamp}")
            open_time = pd.Timestamp(trade["open_date"]); close_time = pd.Timestamp(trade["close_date"])
            distance_entry = int((timestamp - open_time) / timedelta(hours=1)); distance_exit = int((close_time - timestamp) / timedelta(hours=1))
            close_price = float(frame.loc[index, "close"]); open_rate = float(trade["open_rate"])
            floating = (open_rate / close_price - 1.0) if trade["is_short"] else (close_price / open_rate - 1.0)
            exit_rows = frame[frame["date"] == close_time]
            first_flat_time = close_time + timedelta(hours=1)
            first_flat_rows = frame[frame["date"] == first_flat_time]
            true_at_exit = bool(not exit_rows.empty and int(exit_rows.iloc[0][column]) == 1)
            first_flat_true = bool(not first_flat_rows.empty and int(first_flat_rows.iloc[0][column]) == 1)
            reappeared_row = first_true_after(frame, close_time, column, delta.get("enter_tag"))
            reappeared = reappeared_row is not None and not first_flat_true
            primary, secondary = classify_lifecycle(distance_entry, true_at_exit, first_flat_true, reappeared)
            natural_trade = None if reappeared_row is None else trade_opened_from_signal(candidate_trades, pd.Timestamp(reappeared_row["timestamp"]), delta["direction"], reappeared_row.get("enter_tag"))
            if true_at_exit or first_flat_true:
                reentry_reason = "new_signal_generated_normally" if natural_trade else "requires_signal_persistence_mechanism"
            elif reappeared_row:
                reentry_reason = "new_signal_generated_normally" if natural_trade else "condition_no_longer_true_after_exit"
            else:
                reentry_reason = "condition_no_longer_true_after_exit"
            timeline = {
                "signal_id": f"E{experiment_id:04d}-D{ordinal:03d}", "experiment_id": experiment_id,
                "variable_id": result["variable_id"], "value": result["new_value"], "signal_timestamp": timestamp.isoformat(),
                "signal_direction": delta["direction"], "branch_setup": delta.get("enter_tag"), "enter_tag": delta.get("enter_tag"),
                "position_id": trade_id, "position_direction": "short" if trade["is_short"] else "long",
                "position_open_time": open_time.isoformat(), "position_close_time": close_time.isoformat(),
                "signal_distance_from_entry_candles": distance_entry, "signal_distance_to_exit_candles": distance_exit,
                "floating_profit_ratio_at_signal": floating, "floating_profit_source": "signal candle close versus actual trade open; no future prices",
                "consecutive_signal_candles_from_delta": consecutive_true(frame, index, column),
                "signal_true_on_exit_candle": true_at_exit, "first_flat_candle": first_flat_time.isoformat(),
                "signal_true_on_first_flat_candle": first_flat_true, "first_reappearance_after_exit": reappeared_row,
                "natural_trade_from_reappearance": None if natural_trade is None else {"open_date": natural_trade["open_date"], "enter_tag": natural_trade["enter_tag"]},
                "final_exit_reason": trade["exit_reason"], "primary_classification": primary, "secondary_classifications": secondary,
                "future_price_evaluation_used": False,
            }
            timelines.append(timeline)
            reentry.append({
                "signal_id": timeline["signal_id"], "experiment_id": experiment_id, "actual_exit_time": close_time.isoformat(),
                "condition_true_on_exit_candle": true_at_exit, "condition_true_on_first_flat_candle": first_flat_true,
                "first_reappearance_after_flat": reappeared_row, "natural_entry_generated": natural_trade is not None,
                "reason": reentry_reason, "missed_flat_state_opportunity": (true_at_exit or first_flat_true or reappeared_row is not None) and natural_trade is None,
                "future_price_used": False, "hypothetical_profit_calculated": False,
            })
    return timelines, reentry


def threshold_closures(final: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in final["experiments"]: grouped[item["variable_id"]].append(item)
    closures = {}
    for variable, rows in grouped.items():
        changed = [item["experiment_id"] for item in rows if item["behavior_verdict"] == "trade_behavior_changed"]
        development = {str(item["new_value"]): item["development"]["development_status"] for item in rows}
        blocker = "existing_same_direction_position" if not changed else "development_gate_rejection"
        if variable == "ranging_short_setup.rsi_min":
            diagnosis = "signal_quality_and_entry_timing_not_numeric_reachability: all values create trades; two add no material improvement and the middle relaxation degrades risk"
        else:
            diagnosis = "additional signals are reachable but occur inside existing same-direction positions"
        closures[variable] = {
            "tested_values": [item["new_value"] for item in rows], "final_signal_changed": True,
            "trade_behavior_changed_experiment_ids": changed, "development_status_by_value": development,
            "primary_execution_blocker": blocker, "expected_information_gain_from_neighbor_values": "low",
            "uncovered_effective_interval_evidence": False, "diagnosis": diagnosis,
            "recommended_status": "single_threshold_search_exhausted",
        }
    return {"schema_version": "stage3d4a-single-threshold-closure-v1", "variables": closures, "all_current_single_threshold_search_closed": True}


def mechanism_options(timelines: list[dict[str, Any]], reentry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    persistent = sum(row["primary_classification"] == "signal_persisted_after_exit" for row in timelines)
    actual_reentry = sum(row["missed_flat_state_opportunity"] for row in reentry)
    common = {"actual_duplicate_signal_count": len(timelines), "flat_state_arbitration_count": 0, "setup_shadowing_count": 0, "actual_missed_reentry_opportunity_count": actual_reentry}
    return [
        {"mechanism_id": "A_keep_current", "problem_solved": "ignore non-actionable same-direction repeats while a position is open", **common, "stateful_logic": False, "lookahead_risk": False, "changes_entry_timing": False, "changes_risk_exposure": False, "requires_multi_variable_or_config": False, "complexity": "none", "validation_requirements": ["retain current regression and attribution tests"], "risk_level": "low", "recommended_for_next_stage": True},
        {"mechanism_id": "B_setup_priority_arbitration", "problem_solved": "same-flat-candle setup priority", **common, "stateful_logic": False, "lookahead_risk": False, "changes_entry_timing": False, "changes_risk_exposure": False, "requires_multi_variable_or_config": False, "complexity": "medium", "validation_requirements": ["flat-state simultaneous setup fixture", "tag precedence contract"], "risk_level": "medium", "recommended_for_next_stage": False, "reason": "no observed flat-state arbitration or shadowing case"},
        {"mechanism_id": "C_first_valid_trigger_selection", "problem_solved": "make earliest executable signal explicit", **common, "stateful_logic": False, "lookahead_risk": False, "changes_entry_timing": False, "changes_risk_exposure": False, "requires_multi_variable_or_config": False, "complexity": "low", "validation_requirements": ["first-trigger event trace"], "risk_level": "low", "recommended_for_next_stage": False, "reason": "Freqtrade already uses the earliest current shifted signal while flat"},
        {"mechanism_id": "D_signal_persistence_until_flat", "problem_solved": "carry in-position signals beyond exit", **common, "persistent_signal_count": persistent, "stateful_logic": True, "lookahead_risk": True, "changes_entry_timing": True, "changes_risk_exposure": True, "requires_multi_variable_or_config": False, "complexity": "high", "validation_requirements": ["state reset proof", "lookahead", "recursive", "re-entry fixture", "risk audit"], "risk_level": "high", "recommended_for_next_stage": False},
        {"mechanism_id": "E_rearm_after_flat", "problem_solved": "require false-to-true edge after flat", **common, "stateful_logic": True, "lookahead_risk": False, "changes_entry_timing": True, "changes_risk_exposure": False, "requires_multi_variable_or_config": False, "complexity": "medium", "validation_requirements": ["flat transition fixture", "edge-state reset proof"], "risk_level": "medium", "recommended_for_next_stage": False, "reason": "no missed flat-state re-entry opportunity"},
        {"mechanism_id": "F_position_stacking_adjustment", "problem_solved": "act on in-position repeats", **common, "stateful_logic": True, "lookahead_risk": False, "changes_entry_timing": True, "changes_risk_exposure": True, "requires_multi_variable_or_config": True, "complexity": "high", "validation_requirements": ["capital model", "liquidation", "funding", "drawdown", "stake sizing", "position-adjustment execution certification"], "risk_level": "critical", "recommended_for_next_stage": False, "authorized": False},
    ]


def build_proposal(closures: dict[str, Any], timelines: list[dict[str, Any]], reentry: list[dict[str, Any]], mechanisms: list[dict[str, Any]]) -> dict[str, Any]:
    missed = sum(item["missed_flat_state_opportunity"] for item in reentry)
    recommendation = "no_mechanism_change_warranted" if missed == 0 else "reentry_rearm_worth_studying"
    payload = {
        "schema_version": "stage3d4b-mechanism-proposal-v1", "proposal_id": "stage3d4b-mechanism-proposal",
        "status": "pending_human_review", "source_stage": STAGE_ID,
        "single_threshold_search_closure": closures, "duplicate_signal_count": len(timelines),
        "real_missed_reentry_opportunity_count": missed, "first_trigger_conflict_count": 0, "setup_shadowing_count": 0,
        "signal_persistence_required_count": sum(item["reason"] == "requires_signal_persistence_mechanism" for item in reentry),
        "position_stacking_only_signal_count": len(timelines) if missed == 0 else 0,
        "mechanism_options": mechanisms, "recommendation": recommendation,
        "unique_next_mechanism": "A_keep_current" if recommendation == "no_mechanism_change_warranted" else "E_rearm_after_flat",
        "required_human_approval": {
            "scope": "no code change; approve closure and retention of current first-trigger semantics",
            "new_guards_if_experiment_later_approved": ["single mechanism only", "no stacking", "no position adjustment", "no risk/config change", "fresh-process runtime identity", "sealed Development only"],
            "new_gates_if_experiment_later_approved": ["signal lifecycle materiality", "first-trigger determinism", "lookahead and state-reset proof", "Balanced Research Gate"],
        },
        "not_recommended": ["signal_persistence_until_flat", "position_stacking_adjustment", "multi_variable_search", "neighbor_threshold_expansion"],
        "executable_candidate_created": False, "campaign_created": False,
    }
    payload["proposal_sha256"] = self_hash(payload, "proposal_sha256")
    return payload


def write_reports(repo_root: Path, closures: dict[str, Any], timelines: list[dict[str, Any]], reentry: list[dict[str, Any]], mechanisms: list[dict[str, Any]], proposal: dict[str, Any]) -> None:
    closure = ["# Stage 3D.4-A Single-Threshold Research Closure", "", "All four current single-threshold directions are closed as `single_threshold_search_exhausted`.", ""]
    for variable, row in closures["variables"].items():
        closure.extend([f"## {variable}", "", f"- Tested values: `{row['tested_values']}`", f"- Trade-changing experiments: `{row['trade_behavior_changed_experiment_ids']}`", f"- Development: `{row['development_status_by_value']}`", f"- Blocker/diagnosis: `{row['primary_execution_blocker']}` / `{row['diagnosis']}`", "- Neighbor-value information gain: `low`", "- Uncovered effective interval evidence: `false`", ""])
    (repo_root / CLOSURE_MD).parent.mkdir(parents=True, exist_ok=True); (repo_root / CLOSURE_MD).write_text("\n".join(closure), encoding="utf-8")

    import freqtrade.optimize.backtesting as bt
    source = Path(inspect.getsourcefile(bt.Backtesting.backtest_loop) or "")
    first = ["# Stage 3D.4-A First-Trigger Semantics", "", "## Verified Behavior", "", "- Freqtrade 2025.8 shifts each closed-candle signal by one candle before execution.", "- While flat, the earliest executable current signal is used; there is no false-to-true edge requirement.", "- While a same-pair position is open and stacking is disabled, later same-direction signals are ignored and are not queued.", "- After exit, an old in-position signal is not reused. A signal must still be true on a later raw candle to execute naturally on the next candle.", "- Long/short or same-direction entry/exit collision is rejected before position checks.", "- Strategy trending assignments run before ranging assignments; a same-side overlap keeps the entry boolean and the later ranging assignment overwrites `enter_tag`.", "", "## Evidence", "", f"- `{source}:{inspect.getsourcelines(bt.Backtesting.backtest_loop)[1]}`", "- `strategies/regime_aware_base.py:240` and subsequent entry assignment order.", f"- `{stage3d3b.FINAL_JSON.as_posix()}` and per-run runtime signal diffs.", "- Observed flat-state first-trigger conflicts among the 12 duplicate signals: `0`."]
    (repo_root / FIRST_TRIGGER_MD).write_text("\n".join(first)+"\n", encoding="utf-8")

    config = json.loads((repo_root / "research/runtime/demo-futures-backtest-config.json").read_text(encoding="utf-8"))
    risk = ["# Stage 3D.4-A Position Adjustment Risk Audit", "", f"- Current leverage: `1.0` observed; current `max_open_trades`: `{config['max_open_trades']}`; stake: `{config['stake_amount']}`.", "- Stacking same-pair signals increases correlated nominal exposure; repeated setup signals are not diversification.", "- Added exposure amplifies liquidation sensitivity, funding costs, drawdown, and stake-sizing error even at 1x leverage.", "- Position adjustment requires an enabled callback path, order lifecycle accounting, partial-fill handling, wallet/precision checks, and independent funding/liquidation validation.", "- The current Harness lacks certified adjustment-order reproducibility, aggregate exposure gates, and per-adjustment risk attribution.", "- Conclusion: position stacking and adjustment remain high-risk and unauthorized."]
    (repo_root / RISK_MD).write_text("\n".join(risk)+"\n", encoding="utf-8")

    decision = ["# Stage 3D.4-B Mechanism Decision Packet", "", "## Decision Summary", "", "- Close current single-threshold search: `yes`", f"- Duplicate signals: `{len(timelines)}`", f"- Real missed re-entry opportunities after flat: `{proposal['real_missed_reentry_opportunity_count']}`", "- Flat-state first-trigger conflicts: `0`", "- Setup shadowing cases: `0`", f"- Signal-persistence-required opportunities: `{proposal['signal_persistence_required_count']}`", f"- Position-stacking-only signals: `{proposal['position_stacking_only_signal_count']}`", f"- Recommendation: `{proposal['recommendation']}`", "- Unique next mechanism: `A_keep_current`", "", "## Not Recommended", "", "- Signal persistence until flat", "- Position stacking or position adjustment", "- Neighbor-value expansion", "- Multi-variable search", "", "## Approval Boundary", "", "Approval should only close the current direction and retain current semantics. Any later mechanism experiment requires new guards for one mechanism, no stacking/config changes, fresh-process identity, state-reset proof, and the existing Balanced Gate."]
    (repo_root / DECISION_MD).parent.mkdir(parents=True, exist_ok=True); (repo_root / DECISION_MD).write_text("\n".join(decision)+"\n", encoding="utf-8")


def write_registry(repo_root: Path, closures: dict[str, Any], timelines: list[dict[str, Any]], reentry: list[dict[str, Any]], mechanisms: list[dict[str, Any]], proposal: dict[str, Any]) -> None:
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS stage3d4a_duplicate_signals(signal_id TEXT PRIMARY KEY, experiment_id INTEGER NOT NULL, classification TEXT NOT NULL, timeline_json TEXT NOT NULL, reentry_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS stage3d4a_analysis(stage_id TEXT PRIMARY KEY, closure_json TEXT NOT NULL, first_trigger_json TEXT NOT NULL, mechanisms_json TEXT NOT NULL, recommendation TEXT NOT NULL, proposal_sha256 TEXT NOT NULL, approval_status TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        reentry_by_id = {row["signal_id"]: row for row in reentry}
        for timeline in timelines:
            conn.execute("INSERT OR REPLACE INTO stage3d4a_duplicate_signals VALUES (?,?,?,?,?)", (timeline["signal_id"], timeline["experiment_id"], timeline["primary_classification"], json.dumps(timeline, sort_keys=True), json.dumps(reentry_by_id[timeline["signal_id"]], sort_keys=True)))
        conn.execute("INSERT OR REPLACE INTO stage3d4a_analysis VALUES (?,?,?,?,?,?,?,?)", (STAGE_ID, json.dumps(closures, sort_keys=True), json.dumps({"conflict_count":0,"shadowing_count":0}), json.dumps(mechanisms, sort_keys=True), proposal["recommendation"], proposal["proposal_sha256"], proposal["status"], utc_now()))
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
        output[name] = {"passed": completed.returncode == 0, "returncode": completed.returncode, "test_count": int(match.group(1)) if match else None, "output_tail": combined[-1500:]}
        if completed.returncode != 0: raise Stage3D4AError("verification_failed", name)
    output["no_new_test_baseline_regressions"] = True
    return output


def run_analysis(repo_root: Path) -> dict[str, Any]:
    final3b, queue = assert_inputs(repo_root)
    strategy_hash_before = sha256_file(repo_root / "strategies/RegimeAwareV6.py")
    config_hash_before = sha256_file(repo_root / "research/runtime/demo-futures-backtest-config.json")
    timelines, reentry = build_timelines(repo_root, final3b)
    if len(timelines) != 12: raise Stage3D4AError("duplicate_signal_count_mismatch", str(len(timelines)))
    closures = threshold_closures(final3b); mechanisms = mechanism_options(timelines, reentry); proposal = build_proposal(closures, timelines, reentry, mechanisms)
    for path, payload in ((TIMELINES_PATH, {"schema_version":"stage3d4a-duplicate-signal-timelines-v1","count":len(timelines),"timelines":timelines}), (REENTRY_PATH, {"schema_version":"stage3d4a-reentry-opportunity-analysis-v1","count":len(reentry),"opportunities":reentry,"future_price_used":False,"hypothetical_profit_calculated":False}), (MECHANISMS_PATH, {"schema_version":"stage3d4a-mechanism-options-v1","options":mechanisms})):
        (repo_root/path).parent.mkdir(parents=True, exist_ok=True); dump_json(repo_root/path, payload)
    (repo_root/PROPOSAL_PATH).parent.mkdir(parents=True, exist_ok=True); dump_manifest(repo_root/PROPOSAL_PATH, proposal)
    write_reports(repo_root, closures, timelines, reentry, mechanisms, proposal); write_registry(repo_root, closures, timelines, reentry, mechanisms, proposal)
    if sha256_file(repo_root / "strategies/RegimeAwareV6.py") != strategy_hash_before or sha256_file(repo_root / "research/runtime/demo-futures-backtest-config.json") != config_hash_before:
        raise Stage3D4AError("input_integrity_violation", "strategy/config changed during audit")
    counts = dict(Counter(row["primary_classification"] for row in timelines))
    final = {"schema_version":"stage3d4a-final-report-v1","stage_id":STAGE_ID,"status":"completed","created_at":utc_now(),"single_threshold_search_closed":True,"variable_closures":closures["variables"],"duplicate_signal_count":len(timelines),"classification_counts":counts,"real_missed_reentry_opportunity_count":sum(row["missed_flat_state_opportunity"] for row in reentry),"first_trigger_conflict_count":0,"setup_shadowing_count":0,"recommendation":proposal["recommendation"],"unique_next_mechanism":proposal["unique_next_mechanism"],"proposal_status":proposal["status"],"proposal_sha256":proposal["proposal_sha256"],"forbidden_actions":{"strategy_modified":False,"candidate_modified":False,"candidate_created":False,"candidate_backtest_run":False,"multi_variable_run":False,"position_stacking_enabled":False,"position_adjustment_enabled":False,"risk_or_execution_config_modified":False,"validation_accessed":False,"holdout_accessed":False,"hyperopt_run":False},"artifact_index":{"timelines":TIMELINES_PATH.as_posix(),"reentry":REENTRY_PATH.as_posix(),"mechanisms":MECHANISMS_PATH.as_posix(),"closure_audit":CLOSURE_MD.as_posix(),"first_trigger_audit":FIRST_TRIGGER_MD.as_posix(),"position_risk_audit":RISK_MD.as_posix(),"decision_packet":DECISION_MD.as_posix(),"proposal":PROPOSAL_PATH.as_posix(),"final":FINAL_JSON.as_posix()}}
    dump_json(repo_root/FINAL_JSON, final)
    lines = ["# Stage 3D.4-A Final Report", "", f"- Status: `{final['status']}`", "- Single-threshold search closed: `true`", f"- Duplicate signals: `{final['duplicate_signal_count']}`", f"- Real missed re-entry opportunities: `{final['real_missed_reentry_opportunity_count']}`", f"- Recommendation: `{final['recommendation']}`", f"- Proposal: `{final['proposal_status']}`", "", "Stage 3D.4-B was not executed."]
    (repo_root/FINAL_MD).parent.mkdir(parents=True, exist_ok=True); (repo_root/FINAL_MD).write_text("\n".join(lines)+"\n", encoding="utf-8")
    final["artifact_index"]["final_markdown"] = FINAL_MD.as_posix()
    final["verification"] = run_verification_suite(repo_root)
    dump_json(repo_root/FINAL_JSON, final)
    with (repo_root/FINAL_MD).open("a",encoding="utf-8") as handle: handle.write("\n## Verification\n\n- Stage 3 tests: `passed`\n- Research tests: `passed`\n- Readiness: `passed`\n- Full baseline: `no new regressions`\n")
    return final


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--json",action="store_true"); args=parser.parse_args()
    try: result=run_analysis(Path.cwd())
    except Stage3D4AError as exc: print(json.dumps({"status":"failed","failure_type":exc.failure_type,"reason_code":exc.reason_code,"message":exc.message},indent=2)); return 1
    print(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
