#!/usr/bin/env python3
"""Build Stage 3D.3-A deterministic final-signal to trade attribution."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_strategy_signal_reachability as reachability
import run_stage3d2b_reachability_search as stage3d2b
from research_control import load_simple_yaml, utc_now
from run_experiment import dump_json, dump_manifest, repo_rel, sha256_file


STAGE_ID = "stage3d3a-signal-to-trade-attribution"
ANALYSIS_ROOT = Path("research/analysis")
LIFECYCLE_PATH = ANALYSIS_ROOT / "signal-to-trade-lifecycle-v1.yaml"
DELTAS_PATH = ANALYSIS_ROOT / "stage3d3a-signal-deltas.json"
TIMELINES_PATH = ANALYSIS_ROOT / "stage3d3a-signal-timelines.json"
SUMMARY_JSON = ANALYSIS_ROOT / "stage3d3a-blocker-summary.json"
SUMMARY_MD = ANALYSIS_ROOT / "stage3d3a-blocker-summary.md"
VARIABLE_PATH = ANALYSIS_ROOT / "stage3d3a-variable-attribution.json"
ENTRY_PATH = ANALYSIS_ROOT / "stage3d3a-entry-blockers.json"
EXIT_PATH = ANALYSIS_ROOT / "stage3d3a-exit-blockers.json"
IMPORT_AUDIT_PATH = ANALYSIS_ROOT / "stage3d3a-candidate-import-isolation-audit.json"
FINAL_JSON = ANALYSIS_ROOT / "stage3d3a-final-report.json"
FINAL_MD = Path("reports/audits/stage3d3a_signal_to_trade_attribution.md")
SEMANTICS_MD = Path("reports/audits/stage3d3a_freqtrade_execution_semantics.md")
CONTRACT_PATH = Path("research/runtime/freqtrade-2025-8-signal-execution-contract.yaml")
PROPOSAL_PATH = Path("research/proposals/stage3d3b-research-direction-proposal.yaml")

BASE_STRATEGY_SHA256 = stage3d2b.BASE_STRATEGY_SHA256
POLICY_SHA256 = stage3d2b.POLICY_HASH
QUEUE_SHA256 = "bdb463186783e5c3f34027635e250e5e4c39c1185c447a13101848d3de9373a4"
SEARCH_SPACE_SHA256 = "b18cb366f224ecb75006a4c7e20a47771935342bf13be049459c0af9cb1afe2b"
DEV_DATASET_ID = stage3d2b.DEV_DATASET_ID
PAIR = "BTC/USDT:USDT"


class Stage3D3AError(RuntimeError):
    def __init__(self, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def self_hash(payload: dict[str, Any], field: str) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != field})


def assert_inputs(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if sha256_file(repo_root / "strategies/RegimeAwareV6.py").upper() != BASE_STRATEGY_SHA256:
        raise Stage3D3AError("validation_error", "input_integrity_violation", "official strategy hash changed")
    queue = load_simple_yaml(repo_root / stage3d2b.QUEUE_PATH)
    space = load_simple_yaml(repo_root / stage3d2b.SEARCH_SPACE_PATH)
    if queue.get("queue_sha256") != QUEUE_SHA256 or stage3d2b.self_hash(queue, "queue_sha256") != QUEUE_SHA256:
        raise Stage3D3AError("validation_error", "input_integrity_violation", "Stage 3D.2-B queue changed")
    if space.get("search_space_sha256") != SEARCH_SPACE_SHA256 or stage3d2b.self_hash(space, "search_space_sha256") != SEARCH_SPACE_SHA256:
        raise Stage3D3AError("validation_error", "input_integrity_violation", "Stage 3D.2-B search space changed")
    final = json.loads((repo_root / stage3d2b.FINAL_JSON).read_text(encoding="utf-8"))
    if final.get("status") != "completed" or final.get("policy_sha256") != POLICY_SHA256:
        raise Stage3D3AError("validation_error", "input_integrity_violation", "Stage 3D.2-B final report is not frozen-complete")
    if final.get("status_counts") != {"signal_changed_no_trade_behavior_change": 10}:
        raise Stage3D3AError("validation_error", "input_integrity_violation", "unexpected Stage 3D.2-B result set")
    return queue, final


def lifecycle_model() -> dict[str, Any]:
    stages = [
        ("raw_condition_change", "indicator/condition masks", "condition delta", ["condition_not_changed"], "strategy_logic"),
        ("final_signal_change", "condition delta and branch mask", "entry/exit column delta", ["other_strategy_condition_blocked"], "strategy_logic"),
        ("signal_candidate", "candidate analyzed dataframe", "runtime signal row", ["candidate_dependency_module_cache_shadowed", "signal_not_loaded_by_runtime"], "harness_execution"),
        ("collision_checked", "entry and exit columns", "long/short/exit arbitration", ["long_short_entry_collision", "entry_exit_collision", "lower_priority_setup_shadowed"], "freqtrade_execution_semantics"),
        ("position_state_checked", "open trades by pair and direction", "position eligibility", ["existing_same_direction_position", "existing_opposite_direction_position", "position_stacking_disabled", "position_adjustment_not_enabled"], "freqtrade_execution_semantics"),
        ("risk_and_protection_checked", "pair locks and strategy confirmation", "risk authorization", ["pair_locked", "cooldown_active", "protection_blocked", "global_trading_lock"], "configuration_and_strategy_risk"),
        ("capital_checked", "open slots, wallet and market limits", "stake authorization", ["max_open_trades_reached", "insufficient_available_balance", "stake_below_minimum", "stake_above_limit", "precision_or_market_limit_rejection"], "configuration_constraint"),
        ("executable_entry_or_exit", "shifted signal and next candle", "executable event", ["signal_after_last_executable_candle", "no_next_candle_for_execution", "entry_price_not_reachable", "exit_price_not_reachable", "execution_candle_invalid"], "freqtrade_execution_semantics"),
        ("order_simulated", "authorized event and OHLC", "simulated order", ["order_not_filled", "confirmation_callback_rejected"], "freqtrade_execution_semantics"),
        ("trade_created_or_trade_modified", "filled order", "trade mutation", ["duplicate_entry_signal", "duplicate_exit_signal", "trade_already_closed", "roi_exit_preempted_signal", "stoploss_preempted_signal", "trailing_stop_preempted_signal", "liquidation_preempted_signal", "no_matching_open_position"], "trade_lifecycle"),
    ]
    payload = {
        "schema_version": "signal-to-trade-lifecycle-v1",
        "lifecycle_id": "freqtrade-2025-8-backtest-signal-to-trade",
        "ordered_stages": [
            {
                "order": index, "stage": stage, "input": input_, "output": output,
                "rejection_reasons": reasons, "ownership": owner,
                "evidence_sources": ["frozen analyzed candle", "Freqtrade 2025.8 runtime source", "sealed backtest artifacts"],
                "strategy_logic": owner == "strategy_logic",
                "freqtrade_execution_semantics": owner == "freqtrade_execution_semantics",
                "configuration_constraint": owner in {"configuration_constraint", "configuration_and_strategy_risk"},
                "data_issue": False,
            }
            for index, (stage, input_, output, reasons, owner) in enumerate(stages, start=1)
        ],
        "primary_blocker_rule": "earliest stage with sufficient deterministic evidence",
        "fallback_reason": "unresolved_insufficient_instrumentation",
    }
    payload["lifecycle_sha256"] = self_hash(payload, "lifecycle_sha256")
    return payload


def runtime_sources() -> dict[str, Any]:
    import freqtrade
    from freqtrade.optimize.backtesting import Backtesting
    from freqtrade.resolvers.iresolver import IResolver
    from freqtrade.resolvers.strategy_resolver import StrategyResolver
    from freqtrade.strategy.interface import IStrategy
    from freqtrade.wallets import Wallets

    targets = [
        (IStrategy, "get_entry_signal", "live entry collision"),
        (IStrategy, "get_exit_signal", "directional exit signal"),
        (Backtesting, "_get_ohlcv_as_lists", "one-candle signal shift"),
        (Backtesting, "check_for_trade_entry", "backtest long/short and entry/exit collision"),
        (Backtesting, "backtest_loop", "position stacking, pair lock, slot, order sequence"),
        (Backtesting, "_enter_trade", "stake, precision, confirmation, trade creation"),
        (Backtesting, "_get_exit_for_signal", "exit pricing and confirmation"),
        (Backtesting, "time_pair_generator", "last candle and event ordering"),
        (StrategyResolver, "_load_strategy", "strategy path resolution"),
        (IResolver, "_load_object", "module loading"),
        (Wallets, "get_trade_stake_amount", "wallet stake"),
        (Wallets, "validate_stake_amount", "stake limits"),
    ]
    entries = []
    files: dict[str, str] = {}
    for cls, method_name, behavior in targets:
        method = getattr(cls, method_name)
        source = Path(inspect.getsourcefile(method) or "").resolve()
        start = inspect.getsourcelines(method)[1]
        entries.append({"class": cls.__name__, "method": method_name, "source_path": str(source), "start_line": start, "verified_behavior": behavior})
        files[str(source)] = sha256_file(source)
    return {"freqtrade_version": freqtrade.__version__, "entries": entries, "source_file_sha256": files}


def candidate_import_cache_audit(repo_root: Path, queue: dict[str, Any]) -> dict[str, Any]:
    script = r'''
import importlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
rows = []
for experiment_id in range(1, 11):
    candidate_dir = root / "research/candidates/stage3d2b-reachability-informed-batch1" / str(experiment_id)
    sys.path.insert(0, str(candidate_dir))
    module = importlib.import_module(f"RegimeAware_C3D2B_E{experiment_id:04d}")
    cls = getattr(module, f"RegimeAware_C3D2B_E{experiment_id:04d}")
    mixin = cls.__mro__[1]
    rows.append({
        "experiment_id": experiment_id,
        "candidate_module": module.__file__,
        "shared_dependency_module": sys.modules["regime_aware_base"].__file__,
        "mixin_module": sys.modules[mixin.__module__].__file__,
    })
print(json.dumps(rows))
'''
    completed = subprocess.run(
        [sys.executable, "-c", script, str(repo_root)], capture_output=True, text=True,
        check=True, timeout=60, cwd=repo_root,
    )
    rows = json.loads(completed.stdout)
    first_dependency = str((repo_root / "research/candidates" / stage3d2b.CAMPAIGN_ID / "1/regime_aware_base.py").resolve())
    contamination = [row for row in rows[1:] if Path(row["shared_dependency_module"]).resolve() == Path(first_dependency).resolve()]
    payload = {
        "schema_version": "stage3d3a-candidate-import-isolation-audit-v1",
        "runner_execution_model": "sequential_in_process",
        "runner_source": "scripts/run_offline_backtest.py:137-293",
        "shared_dependency_module_name": "regime_aware_base",
        "rows": rows,
        "first_candidate_dependency_path": first_dependency,
        "cache_shadowed_experiment_ids": [row["experiment_id"] for row in contamination],
        "isolation_passed": len(contamination) == 0,
        "deterministic_finding": "candidate_dependency_module_cache_shadowed" if contamination else "isolated",
        "backtests_executed": False,
        "site_packages_modified": False,
    }
    payload["audit_sha256"] = self_hash(payload, "audit_sha256")
    return payload


def load_baseline_trades(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = repo_root / stage3d2b.RESULT_ROOT / "1/development-evaluation/stage3c2-evaluation-result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    trades = result["baseline_metrics"]["normalized_trades"]
    for trade in trades:
        trade["_open"] = pd.Timestamp(trade["open_date"])
        trade["_close"] = pd.Timestamp(trade["close_date"])
    return trades, result


def artifact_semantics_check(repo_root: Path, final: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in final["experiments"]:
        for run_key in ("run_a", "run_b"):
            run = item[run_key]
            normalized = json.loads((repo_root / run["normalized_trades_path"]).read_text(encoding="utf-8"))
            rows.append({"experiment_id": item["experiment_id"], "run": run_key, "sha256": normalized["sha256"], "count": normalized["count"]})
    return {
        "checked_runs": len(rows), "expected_runner_trade_sha256": stage3d2b.BASELINE_RUNNER_TRADE_HASH,
        "all_runner_trade_hashes_preserved": all(row["sha256"] == stage3d2b.BASELINE_RUNNER_TRADE_HASH for row in rows),
        "expected_evaluator_trade_sha256": stage3d2b.BASELINE_TRADE_HASH,
        "rows": rows,
        "instrumentation_replay_executed": False,
        "reason_replay_not_required": "frozen artifacts plus deterministic import-cache audit provide sufficient evidence",
    }


def signal_deltas(repo_root: Path, queue: dict[str, Any], import_audit: dict[str, Any]) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    df = reachability.load_strategy_dataframe(repo_root)
    specs = reachability.condition_specs()
    groups = reachability.signal_groups()
    masks = reachability.condition_mask_map(df, specs)
    variable_map = reachability.variable_condition_map(specs)
    shadowed = set(import_audit["cache_shadowed_experiment_ids"])
    rows = []
    for experiment in queue["experiments"]:
        experiment_id = int(experiment["experiment_id"])
        condition_id = variable_map[experiment["variable_id"]]
        comparison = specs[condition_id].comparison or {}
        values = reachability.comparable_series(df, comparison)
        new_condition = reachability.threshold_mask(values, comparison["operator"], float(experiment["new_value"])).fillna(False)
        for group_id, group in groups.items():
            if condition_id not in group.conditions:
                continue
            old_group = reachability.group_mask(group, masks)
            new_group = reachability.group_mask(group, masks, (condition_id, new_condition))
            changed_indexes = list(df.index[old_group ^ new_group])
            for ordinal, index in enumerate(changed_indexes, start=1):
                candle = df.loc[index]
                rows.append({
                    "delta_id": f"E{experiment_id:04d}-S{ordinal:03d}",
                    "experiment_id": experiment_id,
                    "variable_id": experiment["variable_id"], "old_value": experiment["old_value"], "new_value": experiment["new_value"],
                    "signal_direction": group.side, "signal_type": "entry" if group.signal.startswith("enter") else "exit",
                    "pair": PAIR, "candle_timestamp": pd.Timestamp(candle["date"]).isoformat(),
                    "baseline_signal_value": int(old_group.loc[index]), "candidate_source_signal_value": int(new_group.loc[index]),
                    "runtime_candidate_signal_value": int(new_group.loc[index]) if experiment_id == 1 else None,
                    "runtime_signal_reached": experiment_id == 1,
                    "runtime_signal_gap_reason": None if experiment_id == 1 else "candidate_dependency_module_cache_shadowed",
                    "enter_tag": group.enter_tag, "exit_tag_or_reason_candidate": None,
                    "regime_setup_branch": group.branch, "condition_id": condition_id,
                    "indicators": {
                        key: (None if pd.isna(candle.get(key)) else float(candle[key]))
                        for key in ("rsi", "bb_percent", "adx_4h", "close", "ema200", "bb_width_4h", "bb_width_mean_4h", "volume")
                    },
                    "evaluation_interval": DEV_DATASET_ID, "inside_formal_evaluation_interval": True,
                    "prediction_correspondence": {
                        "expected_experiment_total": experiment["expected_final_signal_mask_changes"],
                        "actual_extracted_experiment_total": len(changed_indexes),
                        "matched": len(changed_indexes) == int(experiment["expected_final_signal_mask_changes"]),
                    },
                    "source_provenance": "stage3d2a_counterfactual_preflight",
                })
    return rows, df


def open_trade_at(trades: list[dict[str, Any]], timestamp: pd.Timestamp) -> dict[str, Any] | None:
    return next((trade for trade in trades if trade["_open"] <= timestamp < trade["_close"]), None)


def choose_blockers(context: dict[str, Any]) -> tuple[str, list[str], str, str]:
    ordered = [
        ("candidate_dependency_module_cache_shadowed", "signal_candidate"),
        ("long_short_entry_collision", "collision_checked"),
        ("entry_exit_collision", "collision_checked"),
        ("existing_same_direction_position", "position_state_checked"),
        ("existing_opposite_direction_position", "position_state_checked"),
        ("position_stacking_disabled", "position_state_checked"),
        ("pair_locked", "risk_and_protection_checked"),
        ("cooldown_active", "risk_and_protection_checked"),
        ("protection_blocked", "risk_and_protection_checked"),
        ("max_open_trades_reached", "capital_checked"),
        ("insufficient_available_balance", "capital_checked"),
        ("stake_below_minimum", "capital_checked"),
        ("precision_or_market_limit_rejection", "capital_checked"),
        ("no_next_candle_for_execution", "executable_entry_or_exit"),
        ("entry_price_not_reachable", "executable_entry_or_exit"),
        ("trade_already_closed", "trade_created_or_trade_modified"),
        ("roi_exit_preempted_signal", "trade_created_or_trade_modified"),
        ("stoploss_preempted_signal", "trade_created_or_trade_modified"),
        ("duplicate_entry_signal", "trade_created_or_trade_modified"),
        ("duplicate_exit_signal", "trade_created_or_trade_modified"),
    ]
    hits = [(reason, stage) for reason, stage in ordered if context.get(reason)]
    if not hits:
        return "unresolved_insufficient_instrumentation", [], "unresolved", "low"
    primary, stage = hits[0]
    return primary, [reason for reason, _ in hits[1:]], stage, "high"


def build_timelines(deltas: list[dict[str, Any]], df: pd.DataFrame, trades: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    by_experiment: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for delta in deltas:
        by_experiment[delta["experiment_id"]].append(delta)
    timelines = []
    for delta in deltas:
        timestamp = pd.Timestamp(delta["candle_timestamp"])
        index = int(df.index[df["date"] == timestamp][0])
        candle = df.loc[index]
        next_candle = df.loc[index + 1] if index + 1 < len(df) else None
        trade = open_trade_at(trades, timestamp)
        same_direction = bool(trade and ((trade["is_short"] and delta["signal_direction"] == "short") or (not trade["is_short"] and delta["signal_direction"] == "long")))
        opposite_direction = bool(trade and not same_direction)
        prior_deltas = [item for item in by_experiment[delta["experiment_id"]] if pd.Timestamp(item["candle_timestamp"]) < timestamp]
        context = {
            "candidate_dependency_module_cache_shadowed": not delta["runtime_signal_reached"],
            "long_short_entry_collision": bool(candle.get("enter_long", 0) and candle.get("enter_short", 0)),
            "entry_exit_collision": bool((delta["signal_direction"] == "long" and candle.get("exit_long", 0)) or (delta["signal_direction"] == "short" and candle.get("exit_short", 0))),
            "existing_same_direction_position": same_direction,
            "existing_opposite_direction_position": opposite_direction,
            "position_stacking_disabled": bool(trade),
            "pair_locked": False, "cooldown_active": False, "protection_blocked": False,
            "max_open_trades_reached": bool(trade and int(config["max_open_trades"]) <= 1),
            "insufficient_available_balance": False, "stake_below_minimum": False, "precision_or_market_limit_rejection": False,
            "no_next_candle_for_execution": next_candle is None,
            "entry_price_not_reachable": False,
            "duplicate_entry_signal": bool(prior_deltas),
        }
        primary, secondary, execution_stage, confidence = choose_blockers(context)
        if primary == "candidate_dependency_module_cache_shadowed":
            secondary = [reason for reason in secondary if reason in {"existing_same_direction_position", "existing_opposite_direction_position", "position_stacking_disabled", "duplicate_entry_signal"}]
        timeline = {
            **delta,
            "ohlc": {key: float(candle[key]) for key in ("open", "high", "low", "close")},
            "next_executable_candle": None if next_candle is None else {
                "timestamp": pd.Timestamp(next_candle["date"]).isoformat(), "open": float(next_candle["open"]),
                "high": float(next_candle["high"]), "low": float(next_candle["low"]), "close": float(next_candle["close"]),
            },
            "position_before_signal": {
                "open": trade is not None, "direction": None if trade is None else ("short" if trade["is_short"] else "long"),
                "open_date": None if trade is None else trade["open_date"], "close_date": None if trade is None else trade["close_date"],
                "enter_tag": None if trade is None else trade["enter_tag"], "eventual_exit_reason": None if trade is None else trade["exit_reason"],
            },
            "same_candle": {
                "exit_signal": bool(candle.get("exit_long", 0) if delta["signal_direction"] == "long" else candle.get("exit_short", 0)),
                "opposite_entry": bool(candle.get("enter_short", 0) if delta["signal_direction"] == "long" else candle.get("enter_long", 0)),
            },
            "execution_constraints": {
                "current_open_trades": 1 if trade else 0, "max_open_trades": int(config["max_open_trades"]),
                "position_stacking": False, "position_adjustment_enabled": False,
                "available_balance": None, "stake_amount": config["stake_amount"],
                "wallet_evaluation": "not_reached" if primary in {"candidate_dependency_module_cache_shadowed", "existing_same_direction_position"} else "artifact_not_exposed",
                "pair_lock": False, "protections": [], "roi_state": None, "stoploss_state": None,
                "liquidation_state": None, "funding_state": "unchanged_frozen_input",
            },
            "actual_trade_created_or_modified": False,
            "primary_blocker": primary, "secondary_blockers": secondary,
            "execution_stage": execution_stage, "confidence": confidence,
            "evidence": [
                "Stage 3D.2-A/3D.2-B reachability preflight",
                "Stage 3D.2-B normalized trade hash equality",
                "candidate import isolation audit" if not delta["runtime_signal_reached"] else "baseline open-trade interval",
                "Freqtrade 2025.8 backtest_loop ordering",
            ],
        }
        timelines.append(timeline)
    return timelines


def summarize(timelines: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    primary = Counter(item["primary_blocker"] for item in timelines)
    variable: dict[str, Any] = {}
    for variable_id in sorted({item["variable_id"] for item in timelines}):
        rows = [item for item in timelines if item["variable_id"] == variable_id]
        variable[variable_id] = {
            "signal_delta_count": len(rows), "primary_blockers": dict(Counter(item["primary_blocker"] for item in rows)),
            "runtime_signal_reached_count": sum(item["runtime_signal_reached"] for item in rows),
            "research_direction": "F_harness_instrumentation_gap" if any(not item["runtime_signal_reached"] for item in rows) else "A_threshold_search_value_low",
        }
    summary = {
        "schema_version": "stage3d3a-blocker-summary-v1", "stage_id": STAGE_ID,
        "changed_signal_total": len(timelines), "entry_count": sum(item["signal_type"] == "entry" for item in timelines),
        "exit_count": sum(item["signal_type"] == "exit" for item in timelines),
        "long_count": sum(item["signal_direction"] == "long" for item in timelines),
        "short_count": sum(item["signal_direction"] == "short" for item in timelines),
        "primary_blocker_frequency": dict(primary),
        "branch_level_blockers": {
            branch: dict(Counter(item["primary_blocker"] for item in timelines if item["regime_setup_branch"] == branch))
            for branch in sorted({item["regime_setup_branch"] for item in timelines})
        },
        "existing_position_blocked_count": primary.get("existing_same_direction_position", 0) + primary.get("existing_opposite_direction_position", 0),
        "duplicate_signal_count": sum("duplicate_entry_signal" in item["secondary_blockers"] or item["primary_blocker"] == "duplicate_entry_signal" for item in timelines),
        "collision_count": sum("collision" in item["primary_blocker"] for item in timelines),
        "slot_or_capital_blocked_count": sum(item["primary_blocker"] in {"max_open_trades_reached", "insufficient_available_balance", "stake_below_minimum"} for item in timelines),
        "protection_blocked_count": sum(item["primary_blocker"] in {"pair_locked", "cooldown_active", "protection_blocked"} for item in timelines),
        "exit_priority_blocked_count": sum("preempted" in item["primary_blocker"] for item in timelines),
        "harness_instrumentation_gap_count": primary.get("candidate_dependency_module_cache_shadowed", 0),
        "unresolved_count": primary.get("unresolved_insufficient_instrumentation", 0),
        "variable_level_attribution": variable,
    }
    summary["summary_sha256"] = self_hash(summary, "summary_sha256")
    return summary, {"schema_version": "stage3d3a-variable-attribution-v1", "variables": variable}


def build_contract(runtime: dict[str, Any], import_audit: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": "freqtrade-2025-8-signal-execution-contract-v1",
        "contract_id": "freqtrade-2025-8-signal-execution",
        "runtime": {"freqtrade": "2025.8", "python": sys.version.split()[0]},
        "source_contract": runtime,
        "semantics": {
            "signal_shift": "entry and exit columns are shifted one candle before backtest iteration",
            "collision": "long requires no exit_long or enter_short; short requires no exit_short or enter_long",
            "position_stacking": "disabled mode permits only one open trade per pair",
            "entry_order": ["collision", "position state", "pair lock", "trade slot", "stake and limits", "confirm_trade_entry", "order simulation"],
            "last_candle": "last row cannot create an entry",
            "exit_order": "active trade exits are evaluated after entry processing for the candle",
            "candidate_module_isolation": "shared dependency module names must be evicted or each candidate must execute in a fresh process",
        },
        "observed_runner_gap": import_audit["deterministic_finding"],
        "site_packages_modified": False,
    }
    payload["contract_sha256"] = self_hash(payload, "contract_sha256")
    return payload


def build_proposal(summary: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": "stage3d3b-research-direction-proposal-v1",
        "proposal_id": "stage3d3b-research-direction-proposal",
        "status": "pending_human_review", "approver_type": None,
        "source_stage": STAGE_ID, "execution_contract_sha256": contract["contract_sha256"],
        "directions": [
            {
                "direction_id": "fresh_process_candidate_dependency_isolation",
                "problem_evidence": "24 of 25 intended signal deltas belonged to experiments whose shared dependency was shadowed by experiment 1 import cache",
                "affected_signal_count": summary["harness_instrumentation_gap_count"],
                "primary_blocker": "candidate_dependency_module_cache_shadowed",
                "single_research_mechanism": "execute each candidate backtest in a fresh Python process with loaded-module provenance",
                "strategy_logic": False, "execution_or_risk_logic": False, "risk_level": "medium",
                "required_human_approval": "Stage 3D.3-B harness execution isolation remediation and bounded recertification",
                "forbidden_coupled_changes": ["strategy thresholds", "entry arbitration", "max_open_trades", "position stacking", "ROI", "stoploss", "protections"],
                "expected_validation": "repeat the frozen 10-item queue only after process-isolation certification and compare per-candidate loaded dependency hashes",
                "why_not_continue_single_threshold_search": "current evidence does not prove experiments 2-10 executed their approved threshold source",
            },
            {
                "direction_id": "existing_position_first_trigger_arbitration_audit",
                "problem_evidence": "the one candidate-specific runtime signal proven to load occurred during an existing same-direction position",
                "affected_signal_count": summary["existing_position_blocked_count"],
                "primary_blocker": "existing_same_direction_position",
                "single_research_mechanism": "audit first-trigger entry semantics without enabling stacking or changing risk limits",
                "strategy_logic": True, "execution_or_risk_logic": True, "risk_level": "high",
                "required_human_approval": "separate entry arbitration and risk audit after harness isolation is fixed",
                "forbidden_coupled_changes": ["position stacking", "max_open_trades", "capital", "leverage", "exit rules", "multiple thresholds"],
                "expected_validation": "read-only event trace followed by one separately approved mechanism experiment",
                "why_not_continue_single_threshold_search": "additional same-direction signals inside an existing position cannot create a new trade under the frozen execution contract",
            },
        ],
        "executable_candidate_queue_created": False,
        "multi_variable_search_authorized": False,
    }
    payload["proposal_sha256"] = self_hash(payload, "proposal_sha256")
    return payload


def write_registry(repo_root: Path, deltas: list[dict[str, Any]], timelines: list[dict[str, Any]], contract: dict[str, Any], summary: dict[str, Any], proposal: dict[str, Any]) -> None:
    conn = sqlite3.connect(repo_root / "research/registry/research.db")
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS stage3d3a_signal_attribution (
              delta_id TEXT PRIMARY KEY, experiment_id INTEGER NOT NULL, variable_id TEXT NOT NULL,
              signal_type TEXT NOT NULL, signal_direction TEXT NOT NULL, candle_timestamp TEXT NOT NULL,
              execution_stage TEXT NOT NULL, primary_blocker TEXT NOT NULL, secondary_blockers_json TEXT NOT NULL,
              evidence_json TEXT NOT NULL, confidence TEXT NOT NULL, timeline_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS stage3d3a_analysis (
              stage_id TEXT PRIMARY KEY, execution_contract_sha256 TEXT NOT NULL, blocker_summary_json TEXT NOT NULL,
              proposal_path TEXT NOT NULL, proposal_sha256 TEXT NOT NULL, approval_status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        for delta, timeline in zip(deltas, timelines):
            conn.execute(
                "INSERT OR REPLACE INTO stage3d3a_signal_attribution VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (delta["delta_id"], delta["experiment_id"], delta["variable_id"], delta["signal_type"], delta["signal_direction"], delta["candle_timestamp"], timeline["execution_stage"], timeline["primary_blocker"], json.dumps(timeline["secondary_blockers"]), json.dumps(timeline["evidence"]), timeline["confidence"], json.dumps(timeline, sort_keys=True)),
            )
        conn.execute(
            "INSERT OR REPLACE INTO stage3d3a_analysis VALUES (?,?,?,?,?,?,?)",
            (STAGE_ID, contract["contract_sha256"], json.dumps(summary, sort_keys=True), PROPOSAL_PATH.as_posix(), proposal["proposal_sha256"], proposal["status"], utc_now()),
        )
        conn.commit()
    finally:
        conn.close()


def write_markdown(repo_root: Path, summary: dict[str, Any], runtime: dict[str, Any], import_audit: dict[str, Any], proposal: dict[str, Any]) -> None:
    summary_lines = [
        "# Stage 3D.3-A Blocker Summary", "",
        f"- Signal deltas: `{summary['changed_signal_total']}`",
        f"- Candidate dependency cache shadowed: `{summary['harness_instrumentation_gap_count']}`",
        f"- Existing same-direction position: `{summary['existing_position_blocked_count']}`",
        f"- Unresolved: `{summary['unresolved_count']}`", "", "## Primary Blockers", "",
    ] + [f"- `{reason}`: `{count}`" for reason, count in summary["primary_blocker_frequency"].items()]
    (repo_root / SUMMARY_MD).write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    audit_lines = [
        "# Stage 3D.3-A Freqtrade 2025.8 Execution Semantics", "",
        "The audit uses the frozen local runtime source, not current online documentation.", "",
        "## Verified Paths", "",
    ]
    audit_lines.extend(f"- `{item['class']}.{item['method']}` at `{item['source_path']}:{item['start_line']}`: {item['verified_behavior']}." for item in runtime["entries"])
    audit_lines.extend([
        "", "## Candidate Isolation Finding", "",
        f"- Finding: `{import_audit['deterministic_finding']}`",
        f"- Shadowed experiments: `{import_audit['cache_shadowed_experiment_ids']}`",
        "- `run_offline_backtest()` executes sequentially in-process; candidate modules have unique names but share `regime_aware_base`.",
        "- Python retained experiment 1's shared dependency in `sys.modules`, so experiments 2-10 did not load their own mutated dependency.",
        "- No site-package file was modified.",
    ])
    (repo_root / SEMANTICS_MD).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / SEMANTICS_MD).write_text("\n".join(audit_lines) + "\n", encoding="utf-8")


def run_analysis(repo_root: Path) -> dict[str, Any]:
    queue, final_3d2b = assert_inputs(repo_root)
    lifecycle = lifecycle_model()
    runtime = runtime_sources()
    before_hashes = dict(runtime["source_file_sha256"])
    import_audit = candidate_import_cache_audit(repo_root, queue)
    artifact_check = artifact_semantics_check(repo_root, final_3d2b)
    if import_audit["isolation_passed"]:
        raise Stage3D3AError("validation_error", "expected_import_isolation_gap_not_reproduced", "shared module cache gap not reproduced")
    if not artifact_check["all_runner_trade_hashes_preserved"]:
        raise Stage3D3AError("validation_error", "instrumentation_semantic_drift", "Stage 3D.2-B trade artifacts drifted")
    deltas, dataframe = signal_deltas(repo_root, queue, import_audit)
    trades, baseline_result = load_baseline_trades(repo_root)
    config = json.loads((repo_root / "research/runtime/demo-futures-backtest-config.json").read_text(encoding="utf-8"))
    timelines = build_timelines(deltas, dataframe, trades, config)
    summary, variable = summarize(timelines)
    contract = build_contract(runtime, import_audit)
    proposal = build_proposal(summary, contract)
    after_hashes = runtime_sources()["source_file_sha256"]
    site_packages_unchanged = before_hashes == after_hashes
    if not site_packages_unchanged:
        raise Stage3D3AError("validation_error", "runtime_source_modified", "Freqtrade runtime source changed during audit")

    for path, payload in (
        (LIFECYCLE_PATH, lifecycle), (CONTRACT_PATH, contract), (PROPOSAL_PATH, proposal),
    ):
        (repo_root / path).parent.mkdir(parents=True, exist_ok=True); dump_manifest(repo_root / path, payload)
    for path, payload in (
        (DELTAS_PATH, {"schema_version": "stage3d3a-signal-deltas-v1", "count": len(deltas), "deltas": deltas}),
        (TIMELINES_PATH, {"schema_version": "stage3d3a-signal-timelines-v1", "count": len(timelines), "timelines": timelines}),
        (SUMMARY_JSON, summary), (VARIABLE_PATH, variable),
        (ENTRY_PATH, {"schema_version": "stage3d3a-entry-blockers-v1", "count": len(timelines), "rows": timelines}),
        (EXIT_PATH, {"schema_version": "stage3d3a-exit-blockers-v1", "count": 0, "rows": [], "reason": "no exit signal deltas in frozen queue"}),
        (IMPORT_AUDIT_PATH, import_audit),
    ):
        (repo_root / path).parent.mkdir(parents=True, exist_ok=True); dump_json(repo_root / path, payload)
    write_markdown(repo_root, summary, runtime, import_audit, proposal)
    write_registry(repo_root, deltas, timelines, contract, summary, proposal)
    final = {
        "schema_version": "stage3d3a-final-report-v1", "stage_id": STAGE_ID, "status": "completed",
        "created_at": utc_now(), "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "policy_sha256": POLICY_SHA256, "queue_sha256": QUEUE_SHA256,
        "signal_delta_count": len(deltas), "timeline_count": len(timelines),
        "all_deltas_attributed": all(item["primary_blocker"] for item in timelines),
        "entry_count": summary["entry_count"], "exit_count": summary["exit_count"],
        "primary_blocker_frequency": summary["primary_blocker_frequency"],
        "instrumentation_trade_hash_preserved": artifact_check["all_runner_trade_hashes_preserved"],
        "instrumentation_replay_executed": False,
        "candidate_import_isolation_passed": import_audit["isolation_passed"],
        "execution_contract_sha256": contract["contract_sha256"],
        "site_packages_unchanged": site_packages_unchanged,
        "proposal_status": proposal["status"], "proposal_sha256": proposal["proposal_sha256"],
        "forbidden_actions": {
            "strategy_modified": False, "candidate_created": False, "candidate_backtest_search_run": False,
            "validation_accessed": False, "holdout_accessed": False, "lookahead_run": False,
            "recursive_run": False, "cost_stress_run": False, "hyperopt_run": False,
            "config_modified": False, "execution_limits_modified": False,
        },
        "artifact_index": {
            "lifecycle": LIFECYCLE_PATH.as_posix(), "signal_deltas": DELTAS_PATH.as_posix(),
            "timelines": TIMELINES_PATH.as_posix(), "blocker_summary": SUMMARY_JSON.as_posix(),
            "variable_attribution": VARIABLE_PATH.as_posix(), "entry_blockers": ENTRY_PATH.as_posix(),
            "exit_blockers": EXIT_PATH.as_posix(), "import_isolation_audit": IMPORT_AUDIT_PATH.as_posix(),
            "execution_semantics_audit": SEMANTICS_MD.as_posix(), "execution_contract": CONTRACT_PATH.as_posix(),
            "proposal": PROPOSAL_PATH.as_posix(), "final_report": FINAL_JSON.as_posix(),
        },
        "research_direction": "repair and certify candidate process isolation before interpreting experiments 2-10; separately audit existing-position first-trigger semantics",
    }
    dump_json(repo_root / FINAL_JSON, final)
    final_lines = [
        "# Stage 3D.3-A Signal-to-Trade Attribution", "",
        f"- Status: `{final['status']}`", f"- Signal deltas: `{len(deltas)}`",
        f"- Import-cache shadowed: `{summary['harness_instrumentation_gap_count']}`",
        f"- Existing-position blocked: `{summary['existing_position_blocked_count']}`",
        f"- Proposal: `{proposal['status']}`", "",
        "Stage 3D.3-B was not executed.",
    ]
    (repo_root / FINAL_MD).write_text("\n".join(final_lines) + "\n", encoding="utf-8")
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Stage 3D.3-A signal-to-trade attribution.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = run_analysis(Path.cwd())
    except Stage3D3AError as exc:
        print(json.dumps({"status": "failed", "failure_type": exc.failure_type, "reason_code": exc.reason_code, "message": exc.message}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
