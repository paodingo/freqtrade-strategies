#!/usr/bin/env python3
"""Deterministic Stage 3C.2 candidate evaluator."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_control import load_simple_yaml, utc_now
from research_data_guard import DataAccessError, check_data_access
from run_experiment import (
    artifact_hashes,
    collect_trade_rows,
    dump_json,
    dump_manifest,
    find_result_json,
    locate_strategy_block,
    repo_rel,
    sha256_file,
)
from run_offline_backtest import run_offline_backtest


EVALUATOR_VERSION = "stage3c3-balanced-research-gate-v1"
RESULT_CAMPAIGN_ID = "stage3c3-balanced-research-gate"
REGISTRY_PATH = Path("research/registry/research.db")
EXCHANGE_SNAPSHOT = Path("research/exchange_snapshots/binance-usdm-futures-2025-8-demo")
RUNTIME_CONFIG = "research/runtime/freqtrade-runtime.yaml"
BACKTEST_CONFIG = "research/runtime/demo-futures-backtest-config.json"
FEE = "0.0004"
TIMEFRAME = "1h"
PAIR = "BTC/USDT:USDT"


class EvaluationError(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_policy_hash(policy: dict[str, Any]) -> str:
    payload = dict(policy)
    payload.pop("policy_sha256", None)
    approval_event = payload.get("approval_event")
    if isinstance(approval_event, dict):
        approval_copy = dict(approval_event)
        approval_copy.pop("policy_sha256", None)
        payload["approval_event"] = approval_copy
    return stable_hash(payload)


def read_yaml(path: Path) -> dict[str, Any]:
    return load_simple_yaml(path)


def policy_hash(policy_path: Path) -> str:
    policy = read_yaml(policy_path)
    if policy.get("policy_approval_status") == "approved" and policy.get("policy_sha256"):
        return canonical_policy_hash(policy)
    return sha256_file(policy_path)


def load_policy(policy_path: Path) -> dict[str, Any]:
    policy = read_yaml(policy_path)
    required = [
        "schema_version",
        "policy_id",
        "policy_approval_status",
        "development_dataset_id",
        "development_dataset_aggregate_sha256",
        "validation_dataset_id",
        "validation_dataset_aggregate_sha256",
        "promotion_ceiling",
        "champion_promotion_allowed",
        "qualified_challenger_allowed",
        "holdout_access_allowed",
    ]
    missing = [key for key in required if key not in policy]
    if missing:
        raise EvaluationError("policy_schema_invalid", f"policy missing keys: {missing}")
    if policy["champion_promotion_allowed"] is not False:
        raise EvaluationError("policy_schema_invalid", "champion_promotion_allowed must be false")
    if policy["qualified_challenger_allowed"] is not False:
        raise EvaluationError("policy_schema_invalid", "qualified_challenger_allowed must be false")
    if policy["holdout_access_allowed"] is not False:
        raise EvaluationError("policy_schema_invalid", "holdout_access_allowed must be false")
    return policy


def dataset_manifest_path(dataset_id: str) -> Path:
    return Path("research/data/snapshots") / dataset_id / "manifest.yaml"


def evaluation_timerange(dataset_manifest: dict[str, Any]) -> str:
    bounds = dataset_manifest["evaluation_range"]
    warmup = dataset_manifest.get("warmup_range") or {}
    start_source = warmup.get("start") or bounds["start"]
    start = str(start_source)[:10].replace("-", "")
    end_dt = datetime.fromisoformat(str(bounds["end"]).replace("Z", "+00:00"))
    exclusive_end = (end_dt + timedelta(days=1)).strftime("%Y%m%d")
    return f"{start}-{exclusive_end}"


def validate_dataset(repo_root: Path, dataset_id: str, policy: dict[str, Any], role: str) -> dict[str, Any]:
    if dataset_id == policy["development_dataset_id"]:
        expected_hash = policy["development_dataset_aggregate_sha256"]
    elif dataset_id == policy["validation_dataset_id"]:
        expected_hash = policy["validation_dataset_aggregate_sha256"]
    else:
        raise EvaluationError("dataset_not_in_policy", f"dataset not in policy: {dataset_id}")
    manifest_path = dataset_manifest_path(dataset_id)
    check_data_access(repo_root, manifest_path, role)
    manifest = read_yaml(repo_root / manifest_path)
    actual_hash = manifest.get("aggregate_sha256")
    if actual_hash != expected_hash:
        raise EvaluationError("dataset_hash_mismatch", f"{dataset_id} aggregate {actual_hash} != {expected_hash}")
    return manifest


def validate_candidate(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = read_yaml(manifest_path)
    strategy_path = repo_root / manifest["candidate_strategy_path"]
    actual = sha256_file(strategy_path)
    if actual.lower() != str(manifest["candidate_strategy_sha256"]).lower():
        raise EvaluationError("candidate_source_hash_mismatch", f"candidate source hash mismatch: {actual}")
    for name, hashes in (manifest.get("candidate_dependency_hashes") or {}).items():
        dep_path = strategy_path.parent / name
        dep_hash = sha256_file(dep_path)
        if dep_hash.lower() != str(hashes.get("candidate_sha256")).lower():
            raise EvaluationError("candidate_dependency_hash_mismatch", f"{name} hash mismatch: {dep_hash}")
    base_hash = sha256_file(repo_root / manifest["base_strategy_path"])
    if base_hash.lower() != str(manifest["base_strategy_sha256"]).lower():
        raise EvaluationError("base_strategy_hash_mismatch", f"base strategy hash mismatch: {base_hash}")
    return manifest


def make_campaign(dataset_manifest: dict[str, Any], strategy: str, strategy_file: str, strategy_path: str) -> dict[str, Any]:
    return {
        "campaign_id": RESULT_CAMPAIGN_ID,
        "fixed_backtest": {
            "strategy": strategy,
            "strategy_file": strategy_file,
            "strategy_path": strategy_path,
            "config": BACKTEST_CONFIG,
            "dataset_id": dataset_manifest["dataset_id"],
            "dataset_manifest": f"research/data/snapshots/{dataset_manifest['dataset_id']}/manifest.yaml",
            "datadir": dataset_manifest["data_path"],
            "timerange": evaluation_timerange(dataset_manifest),
            "timeframe": TIMEFRAME,
            "pairs": [PAIR],
            "fee": FEE,
            "acceptance_gate": {},
        },
        "sealed_offline_backtest": {"exchange_snapshot": str(EXCHANGE_SNAPSHOT), "network_policy": "socket_blocker"},
    }


def run_eval_backtest(repo_root: Path, dataset_manifest: dict[str, Any], kind: str, candidate_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    if kind == "baseline":
        strategy = "RegimeAwareV6"
        strategy_file = "strategies/RegimeAwareV6.py"
        strategy_path = "strategies"
        run_id = "DEVELOPMENT-BASELINE" if dataset_manifest["intended_use"] == "development" else "VALIDATION-BASELINE"
    else:
        if candidate_manifest is None:
            raise EvaluationError("candidate_manifest_missing", "candidate manifest required")
        strategy = candidate_manifest["candidate_strategy_class"]
        strategy_file = candidate_manifest["candidate_strategy_path"]
        strategy_path = str(Path(strategy_file).parent).replace("\\", "/")
        run_id = "DEVELOPMENT-CANDIDATE" if dataset_manifest["intended_use"] == "development" else "VALIDATION-CANDIDATE"
    campaign = make_campaign(dataset_manifest, strategy, strategy_file, strategy_path)
    experiment_id = 3303
    run_dir = repo_root / "research" / "results" / RESULT_CAMPAIGN_ID / str(experiment_id) / run_id
    if run_dir.exists():
        for path in run_dir.iterdir():
            if path.is_file():
                path.unlink()
    result = run_offline_backtest(repo_root, campaign, experiment_id, run_id, repo_root / EXCHANGE_SNAPSHOT)
    report_path = repo_root / result["report_path"]
    run_dir = report_path.parent
    if result["status"] not in {"accepted", "rejected"}:
        raise EvaluationError("backtest_execution_failed", f"{kind} backtest failed: {result}")
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    raw_result = find_result_json(run_dir)
    return {
        "kind": kind,
        "runner_result": result,
        "run_dir": repo_rel(repo_root, run_dir),
        "metrics": metrics,
        "raw_result": repo_rel(repo_root, raw_result),
        "runner_report": result["report_path"],
        "artifact_hashes": repo_rel(repo_root, run_dir / "artifact-hashes.json"),
    }


def metric_record(name: str, raw: Any, unit: str, direction: str, source: str, missing_reason: str | None = None) -> dict[str, Any]:
    normalized = raw
    if isinstance(raw, str):
        try:
            normalized = float(raw)
        except ValueError:
            normalized = raw
    return {
        "metric_name": name,
        "raw_value": raw,
        "normalized_value": normalized if missing_reason is None else None,
        "unit": unit,
        "direction": direction,
        "source": source,
        "calculation_version": EVALUATOR_VERSION,
        "missing_reason": missing_reason,
    }


def load_strategy_block(run_dir: Path, raw_result_rel: str, strategy: str) -> dict[str, Any]:
    payload = json.loads((run_dir / Path(raw_result_rel).name).read_text(encoding="utf-8"))
    return locate_strategy_block(payload, strategy)


def result_vector(repo_root: Path, run: dict[str, Any], strategy: str, dataset_id: str) -> dict[str, Any]:
    metrics = run["metrics"]
    normalized = metrics["normalized"]
    run_dir = repo_root / run["run_dir"]
    raw_result_path = repo_root / run["raw_result"]
    payload = json.loads(raw_result_path.read_text(encoding="utf-8"))
    block = locate_strategy_block(payload, strategy)
    trades = collect_trade_rows(payload, strategy)
    profits = [float(row.get("profit_abs") or 0.0) for row in trades if row.get("profit_abs") is not None]
    ratios = [float(row.get("profit_ratio") or 0.0) for row in trades if row.get("profit_ratio") is not None]
    long_profits = [float(row.get("profit_abs") or 0.0) for row in trades if not bool(row.get("is_short")) and row.get("profit_abs") is not None]
    short_profits = [float(row.get("profit_abs") or 0.0) for row in trades if bool(row.get("is_short")) and row.get("profit_abs") is not None]
    durations = [float(row.get("trade_duration") or row.get("duration")) for row in trades if row.get("trade_duration") is not None or row.get("duration") is not None]
    leverages = [float(row.get("leverage")) for row in trades if row.get("leverage") is not None]
    funding = [float(row.get("funding_fees", row.get("funding_fee"))) for row in trades if row.get("funding_fees", row.get("funding_fee")) is not None]
    exit_dist: dict[str, int] = {}
    enter_dist: dict[str, int] = {}
    for row in trades:
        exit_dist[str(row.get("exit_reason") or "missing")] = exit_dist.get(str(row.get("exit_reason") or "missing"), 0) + 1
        enter_dist[str(row.get("enter_tag") or "missing")] = enter_dist.get(str(row.get("enter_tag") or "missing"), 0) + 1
    total = normalized.get("total_trades")
    backtest_days = block.get("backtest_days")
    weekly_trades = (float(total) / float(backtest_days) * 7.0) if total is not None and backtest_days else None
    no_trades_reason = "no trades in dataset window" if not trades else None
    vector = [
        metric_record("total_trades", normalized.get("total_trades"), "count", "higher", "freqtrade"),
        metric_record("long_trades", normalized.get("long_trade_count"), "count", "higher", "trade_export"),
        metric_record("short_trades", normalized.get("short_trade_count"), "count", "higher", "trade_export"),
        metric_record("closed_trades", normalized.get("closed_trade_count"), "count", "higher", "trade_export"),
        metric_record("rejected_entry_signals", block.get("rejected_signals"), "count", "lower", "freqtrade"),
        metric_record("exposure_time", None, "ratio", "target-range", "not_available", "Freqtrade result does not expose reliable exposure time in this schema"),
        metric_record("weekly_trades", weekly_trades, "count/week", "higher", "derived"),
        metric_record("total_profit", normalized.get("total_profit"), "stake_currency", "higher", "freqtrade"),
        metric_record("total_profit_ratio", normalized.get("total_profit_pct"), "ratio", "higher", "freqtrade"),
        metric_record("long_profit", block.get("profit_total_long_abs"), "stake_currency", "higher", "freqtrade"),
        metric_record("short_profit", block.get("profit_total_short_abs"), "stake_currency", "higher", "freqtrade"),
        metric_record("average_profit_per_trade", statistics.mean(profits) if profits else None, "stake_currency", "higher", "derived", no_trades_reason),
        metric_record("median_profit_per_trade", statistics.median(profits) if profits else None, "stake_currency", "higher", "derived", no_trades_reason),
        metric_record("gross_profit", sum(item for item in profits if item > 0) if profits else None, "stake_currency", "higher", "derived", no_trades_reason),
        metric_record("gross_loss", sum(item for item in profits if item < 0) if profits else None, "stake_currency", "higher", "derived", no_trades_reason),
        metric_record("expectancy", block.get("expectancy"), "stake_currency", "higher", "freqtrade"),
        metric_record("max_drawdown_absolute", block.get("max_drawdown_abs"), "stake_currency", "lower", "freqtrade"),
        metric_record("max_drawdown_percentage", block.get("max_relative_drawdown"), "ratio", "lower", "freqtrade"),
        metric_record("drawdown_duration", None, "duration", "lower", "not_available", "drawdown duration not normalized by evaluator v1"),
        metric_record("worst_trade", min(profits) if profits else None, "stake_currency", "higher", "derived", no_trades_reason),
        metric_record("maximum_consecutive_losses", block.get("max_consecutive_losses"), "count", "lower", "freqtrade"),
        metric_record("minimum_balance", block.get("max_drawdown_low"), "stake_currency", "higher", "freqtrade"),
        metric_record("maximum_underwater_percentage", block.get("max_relative_drawdown"), "ratio", "lower", "freqtrade"),
        metric_record("profit_factor", normalized.get("profit_factor"), "ratio", "higher", "freqtrade"),
        metric_record("sharpe", block.get("sharpe"), "ratio", "higher", "freqtrade"),
        metric_record("sortino", block.get("sortino"), "ratio", "higher", "freqtrade"),
        metric_record("calmar", block.get("calmar"), "ratio", "higher", "freqtrade"),
        metric_record("fee_cost", None, "stake_currency", "lower", "not_available", "per-trade fee total not exposed in normalized schema"),
        metric_record("funding_fees", sum(funding) if funding else None, "stake_currency", "higher", "trade_export", "no funding fee field in trade rows" if not funding else None),
        metric_record("average_leverage", statistics.mean(leverages) if leverages else None, "ratio", "target-range", "trade_export", "no leverage field in trade rows" if not leverages else None),
        metric_record("average_duration", statistics.mean(durations) if durations else normalized.get("avg_duration"), "minutes", "target-range", "trade_export/freqtrade"),
        metric_record("long_duration", None, "minutes", "target-range", "derived", no_trades_reason),
        metric_record("short_duration", None, "minutes", "target-range", "derived", no_trades_reason),
        metric_record("exit_reason_distribution", exit_dist, "distribution", "target-range", "trade_export"),
        metric_record("enter_tag_distribution", enter_dist, "distribution", "target-range", "trade_export"),
    ]
    daily_profit = block.get("daily_profit_list")
    daily_periodic = []
    if isinstance(block.get("periodic_breakdown"), dict):
        daily_periodic = (block.get("periodic_breakdown") or {}).get("day") or []
    rolling = rolling_summary(daily_profit)
    rolling_28d = rolling_window_summary_from_days(daily_periodic, 28, 7)
    regime = regime_summary(repo_root, dataset_id, normalized.get("total_profit_pct"))
    vector.extend(
        [
            metric_record("weekly_result", weekly_result(block), "object", "higher", "derived"),
            metric_record("rolling_window_result", rolling, "object", "higher", "derived"),
            metric_record("rolling_window_28d_step_7d", rolling_28d, "object", "higher", "derived", rolling_28d.get("missing_reason")),
            metric_record("active_weeks", active_week_count(trades), "count", "higher", "trade_export"),
            metric_record("regime_level_result", regime, "object", "higher", "derived"),
            metric_record("worst_window", rolling.get("worst_window"), "object", "higher", "derived", rolling.get("missing_reason")),
            metric_record("best_window", rolling.get("best_window"), "object", "higher", "derived", rolling.get("missing_reason")),
            metric_record("positive_window_count", rolling.get("positive_window_count"), "count", "higher", "derived", rolling.get("missing_reason")),
            metric_record("negative_window_count", rolling.get("negative_window_count"), "count", "lower", "derived", rolling.get("missing_reason")),
            metric_record("long_short_stability", {"long_profit": sum(long_profits), "short_profit": sum(short_profits)} if trades else None, "object", "target-range", "derived", no_trades_reason),
        ]
    )
    normalized_trades = collect_trade_rows(payload, strategy)
    trade_hash = stable_hash(normalized_trades)
    return {
        "schema_version": "stage3c2-metric-vector-v1",
        "dataset_id": dataset_id,
        "strategy": strategy,
        "metrics": {item["metric_name"]: item for item in vector},
        "normalized_trade_hash": trade_hash,
        "normalized_trade_count": len(normalized_trades),
        "normalized_trades": normalized_trades,
        "source_runner_report": run["runner_report"],
        "source_raw_result": run["raw_result"],
        "input_fingerprint": json.loads((run_dir / "runner-report.json").read_text(encoding="utf-8")).get("input_fingerprint"),
    }


def parse_trade_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def active_week_count(trades: list[dict[str, Any]]) -> int:
    weeks = set()
    for trade in trades:
        when = parse_trade_time(trade.get("close_date") or trade.get("open_date"))
        if when is not None:
            iso = when.isocalendar()
            weeks.add((iso.year, iso.week))
    return len(weeks)


def rolling_window_summary_from_days(days: list[dict[str, Any]], duration_days: int = 28, step_days: int = 7) -> dict[str, Any]:
    if not days:
        return {
            "duration_days": duration_days,
            "step_days": step_days,
            "complete_window_count": 0,
            "incomplete_tail_reported": False,
            "positive_window_count": None,
            "negative_window_count": None,
            "positive_window_ratio": None,
            "worst_window": None,
            "best_window": None,
            "windows": [],
            "missing_reason": "daily periodic breakdown missing or empty",
        }
    ordered = sorted(days, key=lambda item: int(item.get("date_ts") or 0))
    windows = []
    for start in range(0, len(ordered) - duration_days + 1, step_days):
        chunk = ordered[start : start + duration_days]
        profit_abs = sum(float(item.get("profit_abs") or 0.0) for item in chunk)
        windows.append(
            {
                "start": chunk[0].get("date"),
                "end": chunk[-1].get("date"),
                "profit_abs": profit_abs,
                "trades": sum(int(item.get("trades") or 0) for item in chunk),
            }
        )
    positive = sum(1 for item in windows if item["profit_abs"] > 0)
    return {
        "duration_days": duration_days,
        "step_days": step_days,
        "complete_window_count": len(windows),
        "incomplete_tail_reported": len(ordered) < duration_days or ((len(ordered) - duration_days) % step_days != 0),
        "positive_window_count": positive,
        "negative_window_count": sum(1 for item in windows if item["profit_abs"] < 0),
        "positive_window_ratio": (positive / len(windows)) if windows else None,
        "worst_window": min((item["profit_abs"] for item in windows), default=None),
        "best_window": max((item["profit_abs"] for item in windows), default=None),
        "windows": windows,
        "missing_reason": None if windows else "not enough complete rolling windows",
    }


def rolling_summary(daily_profit: Any) -> dict[str, Any]:
    if not isinstance(daily_profit, list) or not daily_profit:
        return {
            "windows": {"14d": [], "30d": []},
            "worst_window": None,
            "best_window": None,
            "positive_window_count": None,
            "negative_window_count": None,
            "missing_reason": "daily_profit_list missing or empty",
        }
    values = [float(item) for item in daily_profit]
    windows: dict[str, list[float]] = {}
    for size in (14, 30):
        windows[f"{size}d"] = [sum(values[idx : idx + size]) for idx in range(0, max(0, len(values) - size + 1))]
    all_windows = windows["14d"] + windows["30d"]
    return {
        "windows": windows,
        "worst_window": min(all_windows) if all_windows else None,
        "best_window": max(all_windows) if all_windows else None,
        "positive_window_count": sum(1 for item in all_windows if item > 0),
        "negative_window_count": sum(1 for item in all_windows if item < 0),
        "missing_reason": None if all_windows else "not enough daily windows",
    }


def weekly_result(block: dict[str, Any]) -> dict[str, Any]:
    return {
        "backtest_days": block.get("backtest_days"),
        "trades_per_day": block.get("trades_per_day"),
        "winning_days": block.get("winning_days"),
        "draw_days": block.get("draw_days"),
        "losing_days": block.get("losing_days"),
    }


def regime_summary(repo_root: Path, dataset_id: str, total_profit_ratio: Any) -> dict[str, Any]:
    profile_path = repo_root / "research/data/profiles/futures-dev-validation-v1-market-profile.json"
    if not profile_path.exists():
        return {"missing_reason": "market profile missing"}
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    key = "development" if dataset_id.startswith("futures-dev-") else "validation_evaluation"
    window = profile.get("windows", {}).get(key)
    if not window:
        return {"missing_reason": f"profile window missing: {key}"}
    return {
        "profile_window": key,
        "labels": window.get("labels"),
        "dataset_total_return": window.get("stats", {}).get("total_return"),
        "strategy_total_profit_ratio": total_profit_ratio,
    }


def compare_vectors(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    deltas = {}
    favorable = 0
    comparable = 0
    for name, base_metric in baseline["metrics"].items():
        cand_metric = candidate["metrics"].get(name)
        if not cand_metric:
            continue
        bval = base_metric.get("normalized_value")
        cval = cand_metric.get("normalized_value")
        if isinstance(bval, (int, float)) and isinstance(cval, (int, float)):
            delta = cval - bval
            comparable += 1
            direction = cand_metric["direction"]
            is_favorable = delta > 0 if direction == "higher" else delta < 0 if direction == "lower" else delta == 0
            favorable += 1 if is_favorable else 0
            deltas[name] = {"baseline": bval, "candidate": cval, "delta": delta, "direction": direction, "favorable": is_favorable}
    trade_diff = {
        "baseline_trade_hash": baseline["normalized_trade_hash"],
        "candidate_trade_hash": candidate["normalized_trade_hash"],
        "same_trade_hash": baseline["normalized_trade_hash"] == candidate["normalized_trade_hash"],
        "baseline_trade_count": baseline["normalized_trade_count"],
        "candidate_trade_count": candidate["normalized_trade_count"],
        "field_level_trade_diff": [] if baseline["normalized_trades"] == candidate["normalized_trades"] else [{"reason": "trade_rows_differ"}],
    }
    return {
        "schema_version": "stage3c2-baseline-comparison-v1",
        "metric_deltas": deltas,
        "auxiliary_score": {"favorable_metric_count": favorable, "comparable_metric_count": comparable, "decides_gate": False},
        "trade_diff": trade_diff,
    }


def gate_decision(policy: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    coverage = candidate["metrics"]
    total = coverage["total_trades"]["normalized_value"]
    long_count = coverage["long_trades"]["normalized_value"]
    short_count = coverage["short_trades"]["normalized_value"]
    closed_count = coverage.get("closed_trades", {}).get("normalized_value")
    active_weeks = coverage.get("active_weeks", {}).get("normalized_value")
    rolling = coverage.get("rolling_window_28d_step_7d", {}).get("normalized_value") or {}
    complete_windows = rolling.get("complete_window_count")
    reasons = []
    rule_outputs = {"policy_approval_status": policy["policy_approval_status"]}
    if policy["policy_approval_status"] != "approved":
        reasons.append("evaluation policy pending human review")
    if policy["policy_approval_status"] != "approved":
        final = "development_evaluated_policy_pending"
    else:
        dev_cov = policy.get("development_coverage") or {}
        coverage_checks = {
            "min_total_trades": total is not None and total >= int(dev_cov.get("min_total_trades", 0)),
            "min_long_trades": long_count is not None and long_count >= int(dev_cov.get("min_long_trades", 0)),
            "min_short_trades": short_count is not None and short_count >= int(dev_cov.get("min_short_trades", 0)),
            "min_closed_trades": closed_count is not None and closed_count >= int(dev_cov.get("min_closed_trades", 0)),
            "min_active_weeks": active_weeks is not None and active_weeks >= int(dev_cov.get("min_active_weeks", 0)),
            "min_complete_rolling_windows": complete_windows is not None and complete_windows >= int(dev_cov.get("min_complete_rolling_windows", 0)),
        }
        rule_outputs["development_coverage"] = coverage_checks
        if not all(coverage_checks.values()):
            final = "development_inconclusive_insufficient_coverage"
            reasons.append("development_inconclusive_insufficient_coverage")
        else:
            trade_diff = comparison["trade_diff"]
            long_delta = comparison["metric_deltas"].get("long_trades", {}).get("delta", 0)
            short_delta = comparison["metric_deltas"].get("short_trades", {}).get("delta", 0)
            behavior_changed = not (
                trade_diff["same_trade_hash"]
                and trade_diff["baseline_trade_count"] == trade_diff["candidate_trade_count"]
                and not trade_diff["field_level_trade_diff"]
                and long_delta == 0
                and short_delta == 0
            )
            rule_outputs["behavior_materiality"] = {"behavior_changed": behavior_changed}
            if not behavior_changed:
                final = "development_inconclusive_behavior_unchanged"
                reasons.append("development_inconclusive_behavior_unchanged")
            else:
                hard_metrics = ("total_profit_ratio", "profit_factor", "max_drawdown_percentage")
                missing = [name for name in hard_metrics if coverage.get(name, {}).get("normalized_value") is None]
                if missing:
                    final = "development_integrity_failed"
                    reasons.append("development_integrity_failed_metric_missing")
                    rule_outputs["missing_hard_gate_metrics"] = missing
                else:
                    deltas = comparison["metric_deltas"]
                    risk = policy.get("development_no_material_degradation") or {}
                    improvement = policy.get("development_material_improvement_any") or {}
                    directional = policy.get("directional_coverage") or {}
                    return_delta_pp = float(deltas.get("total_profit_ratio", {}).get("delta", 0.0)) * 100.0
                    pf_delta = float(deltas.get("profit_factor", {}).get("delta", 0.0))
                    dd_delta_pp = float(deltas.get("max_drawdown_percentage", {}).get("delta", 0.0)) * 100.0
                    candidate_dd_pp = float(coverage["max_drawdown_percentage"]["normalized_value"] or 0.0) * 100.0
                    baseline_long = int(baseline["metrics"]["long_trades"]["normalized_value"] or 0)
                    baseline_short = int(baseline["metrics"]["short_trades"]["normalized_value"] or 0)
                    min_fraction = float(directional.get("minimum_fraction_of_baseline", 0.0))
                    abs_min = int(directional.get("absolute_minimum_per_direction", 0))
                    required_long = max(abs_min, int(baseline_long * min_fraction + 0.999999)) if baseline_long >= 5 else 0
                    required_short = max(abs_min, int(baseline_short * min_fraction + 0.999999)) if baseline_short >= 5 else 0
                    directional_ok = long_count >= required_long and short_count >= required_short
                    no_degradation = {
                        "total_return_delta": return_delta_pp >= float(risk.get("total_return_delta_percentage_points_min", -999)),
                        "profit_factor_delta": pf_delta >= float(risk.get("profit_factor_delta_min", -999)),
                        "max_drawdown_delta": dd_delta_pp <= float(risk.get("max_drawdown_delta_percentage_points_max", 999)),
                        "absolute_max_drawdown": candidate_dd_pp <= float(risk.get("absolute_max_drawdown_percentage_max", 999)),
                        "directional_coverage": directional_ok,
                    }
                    material_improvement = {
                        "total_return_delta": return_delta_pp >= float(improvement.get("total_return_delta_percentage_points_min", 999)),
                        "profit_factor_delta": pf_delta >= float(improvement.get("profit_factor_delta_min", 999)),
                        "max_drawdown_improvement": (-dd_delta_pp) >= float(improvement.get("max_drawdown_improvement_percentage_points_min", 999)),
                    }
                    rule_outputs["development_no_material_degradation"] = no_degradation
                    rule_outputs["development_material_improvement_any"] = material_improvement
                    rule_outputs["directional_coverage"] = {"required_long": required_long, "required_short": required_short, "passed": directional_ok}
                    if not all(no_degradation.values()):
                        final = "development_ineligible_risk_degradation"
                        reasons.append("development_ineligible_risk_degradation")
                    elif not any(material_improvement.values()):
                        final = "development_ineligible_no_material_improvement"
                        reasons.append("development_ineligible_no_material_improvement")
                    else:
                        final = "development_eligible_bias_pending"
    return {
        "schema_version": "stage3c3-balanced-research-gate-decision-v1",
        "policy_id": policy["policy_id"],
        "policy_approval_status": policy["policy_approval_status"],
        "evaluator_version": EVALUATOR_VERSION,
        "metric_inputs": {
            "total_trades": total,
            "long_trades": long_count,
            "short_trades": short_count,
            "closed_trades": closed_count,
            "active_weeks": active_weeks,
            "complete_rolling_windows": complete_windows,
            "same_trade_hash_as_baseline": comparison["trade_diff"]["same_trade_hash"],
        },
        "rule_outputs": rule_outputs,
        "hard_gates_override_score": True,
        "final_decision": final,
        "reasons": reasons,
        "decision_timestamp": utc_now(),
        "bias_validation": {"lookahead_analysis": "not_required_until_behavior_changed", "recursive_analysis": "not_required_until_behavior_changed"},
        "cost_stress": "not_required_until_behavior_changed",
        "promotion_limit_reason": ["bias_checks_pending", "holdout_not_run", "forward_dry_run_not_run"],
        "champion_promotion": "not_allowed",
        "qualified_challenger": "not_allowed",
        "holdout_accessed": False,
    }


def init_registry(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS evaluation_policies (
          policy_id TEXT PRIMARY KEY,
          policy_hash TEXT NOT NULL,
          approval_status TEXT NOT NULL,
          path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS candidate_freezes (
          candidate_id TEXT PRIMARY KEY,
          source_sha256 TEXT NOT NULL,
          manifest_sha256 TEXT NOT NULL,
          experiment_spec_sha256 TEXT NOT NULL,
          development_result_sha256 TEXT NOT NULL,
          development_dataset_hash TEXT NOT NULL,
          policy_hash TEXT NOT NULL,
          frozen_at TEXT NOT NULL,
          allowed_next_state TEXT NOT NULL,
          mutation_prohibited INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS development_evaluations (
          evaluation_id TEXT PRIMARY KEY,
          candidate_id TEXT NOT NULL,
          dataset_id TEXT NOT NULL,
          dataset_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          result_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS validation_evaluations (
          evaluation_id TEXT PRIMARY KEY,
          candidate_id TEXT NOT NULL,
          dataset_id TEXT NOT NULL,
          dataset_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          result_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metric_values (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          evaluation_id TEXT NOT NULL,
          subject TEXT NOT NULL,
          metric_name TEXT NOT NULL,
          raw_json TEXT NOT NULL,
          normalized_json TEXT NOT NULL,
          missing_reason TEXT
        );
        CREATE TABLE IF NOT EXISTS baseline_comparisons (
          comparison_id TEXT PRIMARY KEY,
          evaluation_id TEXT NOT NULL,
          candidate_id TEXT NOT NULL,
          dataset_id TEXT NOT NULL,
          comparison_json TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS validation_access_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          candidate_id TEXT NOT NULL,
          source_hash TEXT NOT NULL,
          policy_hash TEXT NOT NULL,
          evaluator_role TEXT NOT NULL,
          dataset_id TEXT NOT NULL,
          dataset_hash TEXT NOT NULL,
          access_timestamp TEXT NOT NULL,
          access_purpose TEXT NOT NULL,
          access_count_before INTEGER NOT NULL,
          access_count_after INTEGER NOT NULL,
          authorization_result TEXT NOT NULL,
          reason_code TEXT
        );
        CREATE TABLE IF NOT EXISTS contamination_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          candidate_id TEXT NOT NULL,
          previous_status TEXT NOT NULL,
          new_status TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evaluation_artifacts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          evaluation_id TEXT NOT NULL,
          artifact_type TEXT NOT NULL,
          path TEXT NOT NULL,
          sha256 TEXT,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gate_decisions (
          decision_id TEXT PRIMARY KEY,
          evaluation_id TEXT NOT NULL,
          policy_id TEXT NOT NULL,
          policy_hash TEXT NOT NULL,
          evaluator_version TEXT NOT NULL,
          candidate_hash TEXT NOT NULL,
          dataset_id TEXT NOT NULL,
          dataset_hash TEXT NOT NULL,
          metric_inputs_json TEXT NOT NULL,
          rule_outputs_json TEXT NOT NULL,
          final_decision TEXT NOT NULL,
          decision_timestamp TEXT NOT NULL
        );
        """
    )


def validation_access_count(conn: sqlite3.Connection, candidate_id: str, dataset_id: str, source_hash: str | None = None) -> int:
    if source_hash:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM validation_access_events WHERE dataset_id = ? AND authorization_result = 'authorized' AND (candidate_id = ? OR source_hash = ?)",
                (dataset_id, candidate_id, source_hash),
            ).fetchone()[0]
        )
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM validation_access_events WHERE candidate_id = ? AND dataset_id = ? AND authorization_result = 'authorized'",
            (candidate_id, dataset_id),
        ).fetchone()[0]
    )


def record_validation_access(
    conn: sqlite3.Connection,
    candidate_id: str,
    source_hash: str,
    policy_hash_value: str,
    role: str,
    dataset_id: str,
    dataset_hash: str,
    authorized: bool,
    reason_code: str | None,
) -> dict[str, Any]:
    before = validation_access_count(conn, candidate_id, dataset_id, source_hash)
    after = before + (1 if authorized else 0)
    event = {
        "candidate_id": candidate_id,
        "source_hash": source_hash,
        "policy_hash": policy_hash_value,
        "evaluator_role": role,
        "dataset_id": dataset_id,
        "dataset_hash": dataset_hash,
        "access_timestamp": utc_now(),
        "access_purpose": "stage3c2_validation_evaluation",
        "access_count_before": before,
        "access_count_after": after,
        "authorization_result": "authorized" if authorized else "denied",
        "reason_code": reason_code,
    }
    conn.execute(
        """
        INSERT INTO validation_access_events(candidate_id, source_hash, policy_hash, evaluator_role, dataset_id,
          dataset_hash, access_timestamp, access_purpose, access_count_before, access_count_after,
          authorization_result, reason_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            source_hash,
            policy_hash_value,
            role,
            dataset_id,
            dataset_hash,
            event["access_timestamp"],
            event["access_purpose"],
            before,
            after,
            event["authorization_result"],
            reason_code,
        ),
    )
    return event


def deny_validation_access(repo_root: Path, policy: dict[str, Any], phash: str, candidate: dict[str, Any], role: str, reason_code: str) -> dict[str, Any]:
    db_path = repo_root / REGISTRY_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        init_registry(conn)
        event = record_validation_access(
            conn,
            f"{candidate['campaign_id']}:{candidate['experiment_id']}",
            candidate["candidate_strategy_sha256"],
            phash,
            role,
            policy["validation_dataset_id"],
            policy["validation_dataset_aggregate_sha256"],
            False,
            reason_code,
        )
        conn.commit()
        return event
    finally:
        conn.close()


def experiment_spec_path_for_candidate(candidate: dict[str, Any]) -> Path:
    return Path("research/experiments") / str(candidate["campaign_id"]) / str(candidate["experiment_id"]) / "experiment-spec.yaml"


def write_registry(repo_root: Path, policy: dict[str, Any], policy_path: Path, phash: str, candidate: dict[str, Any], dataset: dict[str, Any], outputs: dict[str, Any]) -> None:
    db_path = repo_root / REGISTRY_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        init_registry(conn)
        evaluation_id = outputs["evaluation_id"]
        candidate_id = outputs["candidate_id"]
        conn.execute(
            "INSERT OR REPLACE INTO evaluation_policies(policy_id, policy_hash, approval_status, path, recorded_at) VALUES (?, ?, ?, ?, ?)",
            (policy["policy_id"], phash, policy["policy_approval_status"], repo_rel(repo_root, policy_path), utc_now()),
        )
        if outputs.get("evaluation_stage") == "validation":
            conn.execute(
                "INSERT OR REPLACE INTO validation_evaluations(evaluation_id, candidate_id, dataset_id, dataset_hash, status, result_path, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (evaluation_id, candidate_id, dataset["dataset_id"], dataset["aggregate_sha256"], outputs["validation_status"], outputs["result_path"], utc_now()),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO development_evaluations(evaluation_id, candidate_id, dataset_id, dataset_hash, status, result_path, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (evaluation_id, candidate_id, dataset["dataset_id"], dataset["aggregate_sha256"], outputs["development_status"], outputs["result_path"], utc_now()),
            )
        for subject, vector in (("baseline", outputs["baseline_metrics"]), ("candidate", outputs["candidate_metrics"])):
            for metric in vector["metrics"].values():
                conn.execute(
                    "INSERT INTO metric_values(evaluation_id, subject, metric_name, raw_json, normalized_json, missing_reason) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        evaluation_id,
                        subject,
                        metric["metric_name"],
                        json.dumps(metric["raw_value"], sort_keys=True, ensure_ascii=False),
                        json.dumps(metric["normalized_value"], sort_keys=True, ensure_ascii=False),
                        metric.get("missing_reason"),
                    ),
                )
        conn.execute(
            "INSERT OR REPLACE INTO baseline_comparisons(comparison_id, evaluation_id, candidate_id, dataset_id, comparison_json, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"{evaluation_id}:comparison", evaluation_id, candidate_id, dataset["dataset_id"], json.dumps(outputs["comparison"], sort_keys=True, ensure_ascii=False), utc_now()),
        )
        decision = outputs["gate_decision"]
        conn.execute(
            """
            INSERT OR REPLACE INTO gate_decisions(decision_id, evaluation_id, policy_id, policy_hash, evaluator_version,
              candidate_hash, dataset_id, dataset_hash, metric_inputs_json, rule_outputs_json, final_decision,
              decision_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"{evaluation_id}:gate",
                evaluation_id,
                policy["policy_id"],
                phash,
                EVALUATOR_VERSION,
                candidate["candidate_strategy_sha256"],
                dataset["dataset_id"],
                dataset["aggregate_sha256"],
                json.dumps(decision["metric_inputs"], sort_keys=True, ensure_ascii=False),
                json.dumps(decision["rule_outputs"], sort_keys=True, ensure_ascii=False),
                decision["final_decision"],
                decision["decision_timestamp"],
            ),
        )
        conn.execute(
            "INSERT INTO contamination_events(candidate_id, previous_status, new_status, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            (candidate_id, "clean", "development_exposed", "development evaluation executed", utc_now()),
        )
        for artifact_type, path in outputs["artifact_paths"].items():
            full = repo_root / path
            conn.execute(
                "INSERT INTO evaluation_artifacts(evaluation_id, artifact_type, path, sha256, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (evaluation_id, artifact_type, path, sha256_file(full) if full.exists() and full.is_file() else None, utc_now()),
            )
        conn.commit()
    finally:
        conn.close()


def maybe_authorize_validation(repo_root: Path, policy: dict[str, Any], phash: str, candidate: dict[str, Any], dataset: dict[str, Any], role: str, development_decision: str) -> dict[str, Any]:
    db_path = repo_root / REGISTRY_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        init_registry(conn)
        candidate_id = f"{candidate['campaign_id']}:{candidate['experiment_id']}"
        reason = None
        authorized = True
        if role != "validation_evaluator":
            authorized = False
            reason = "validation_role_denied"
        elif policy["policy_approval_status"] != "approved":
            authorized = False
            reason = "policy_pending_human_review"
        elif development_decision != "development_eligible":
            authorized = False
            reason = "development_not_eligible"
        elif validation_access_count(conn, candidate_id, policy["validation_dataset_id"], candidate["candidate_strategy_sha256"]) >= 1:
            authorized = False
            reason = "validation_budget_exhausted"
        event = record_validation_access(
            conn,
            candidate_id,
            candidate["candidate_strategy_sha256"],
            phash,
            role,
            policy["validation_dataset_id"],
            policy["validation_dataset_aggregate_sha256"],
            authorized,
            reason,
        )
        conn.commit()
        return event
    finally:
        conn.close()


def create_candidate_freeze(
    repo_root: Path,
    candidate: dict[str, Any],
    candidate_manifest_path: Path,
    experiment_spec_path: Path,
    development_result_path: Path,
    development_dataset_hash: str,
    phash: str,
    output_path: Path,
) -> dict[str, Any]:
    record = {
        "schema_version": "stage3c2-candidate-freeze-v1",
        "candidate_id": f"{candidate['campaign_id']}:{candidate['experiment_id']}",
        "source_sha256": sha256_file(repo_root / candidate["candidate_strategy_path"]),
        "manifest_sha256": sha256_file(candidate_manifest_path),
        "experiment_spec_sha256": sha256_file(experiment_spec_path),
        "development_result_sha256": sha256_file(development_result_path),
        "development_dataset_hash": development_dataset_hash,
        "freeze_timestamp": utc_now(),
        "evaluation_policy_hash": phash,
        "allowed_next_state": "validation_access_request",
        "mutation_prohibited": True,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(output_path, record)
    return record


def validate_candidate_freeze(repo_root: Path, freeze_path: Path, candidate: dict[str, Any], candidate_manifest_path: Path, experiment_spec_path: Path) -> dict[str, Any]:
    freeze = read_yaml(freeze_path)
    mismatches = []
    current_source = sha256_file(repo_root / candidate["candidate_strategy_path"])
    current_manifest = sha256_file(candidate_manifest_path)
    current_spec = sha256_file(experiment_spec_path)
    if current_source != freeze.get("source_sha256"):
        mismatches.append("candidate_changed_after_freeze")
    if current_manifest != freeze.get("manifest_sha256"):
        mismatches.append("candidate_manifest_changed_after_freeze")
    if current_spec != freeze.get("experiment_spec_sha256"):
        mismatches.append("experiment_spec_changed_after_freeze")
    return {
        "valid": not mismatches,
        "mismatches": mismatches,
        "allowed_next_state": freeze.get("allowed_next_state") if not mismatches else "validation_access_denied",
    }


def write_limited_disclosure(path: Path, result: dict[str, Any]) -> None:
    candidate = result["candidate_metrics"]["metrics"]
    comparison = result["comparison"]
    payload = {
        "schema_version": "stage3c2-limited-disclosure-v1",
        "evaluation_status": result["development_status"],
        "policy_gate_verdict": result["gate_decision"]["final_decision"],
        "total_trades": candidate["total_trades"]["normalized_value"],
        "long_trades": candidate["long_trades"]["normalized_value"],
        "short_trades": candidate["short_trades"]["normalized_value"],
        "total_return": candidate["total_profit_ratio"]["normalized_value"],
        "max_drawdown": candidate["max_drawdown_absolute"]["normalized_value"],
        "profit_factor": candidate["profit_factor"]["normalized_value"],
        "baseline_relative_summary": {
            key: value
            for key, value in comparison["metric_deltas"].items()
            if key in {"total_profit", "total_profit_ratio", "max_drawdown_absolute", "profit_factor", "total_trades"}
        },
        "failure_reason_category": result["gate_decision"]["reasons"],
        "contamination_status": "development_exposed",
        "withheld": [
            "complete_trade_list",
            "exact_entry_exit_times",
            "per_trade_profit",
            "complete_enter_exit_tag_details",
            "validation_candles",
            "field_level_validation_trade_diff",
        ],
    }
    dump_json(path, payload)


def write_final_markdown(path: Path, result: dict[str, Any]) -> None:
    status = result.get("validation_status") or result.get("development_status")
    lines = [
        "# Stage 3C.2 Candidate Evaluation",
        "",
        f"- Evaluation ID: `{result['evaluation_id']}`",
        f"- Candidate: `{result['candidate_id']}`",
        f"- Dataset: `{result['dataset_id']}`",
        f"- Policy approval: `{result['policy_approval_status']}`",
        f"- Status: `{status}`",
        f"- Validation accessed: `{str(result['validation_accessed']).lower()}`",
        f"- Champion promotion: `not_allowed`",
        f"- Qualified Challenger: `not_allowed`",
        f"- Holdout accessed: `false`",
        "",
        "## Development Result",
        "",
        f"- Baseline trade hash: `{result['baseline_metrics']['normalized_trade_hash']}`",
        f"- Candidate trade hash: `{result['candidate_metrics']['normalized_trade_hash']}`",
        f"- Same trade hash: `{str(result['comparison']['trade_diff']['same_trade_hash']).lower()}`",
        f"- Gate decision: `{result['gate_decision']['final_decision']}`",
        "",
        "## Validation",
        "",
        "- Validation is only executed when policy is approved, candidate freeze is valid, and the one-use budget is available.",
        "",
        "## Pending Checks",
        "",
        "- Lookahead Analysis: `not_run`",
        "- Recursive Analysis: `not_run`",
        "- Sealed holdout: `not_run`",
        "- Forward dry-run: `not_run`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate_candidate(repo_root: Path, candidate_manifest_path: Path, dataset_id: str, role: str, policy_path: Path, baseline: str, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    policy = load_policy(policy_path)
    phash = policy_hash(policy_path)
    candidate = validate_candidate(repo_root, candidate_manifest_path)
    if role == "validation_evaluator":
        freeze_path = Path(candidate["candidate_strategy_path"]).parent / "candidate-freeze.yaml"
        if policy["policy_approval_status"] == "approved":
            if not (repo_root / freeze_path).exists():
                event = deny_validation_access(repo_root, policy, phash, candidate, role, "candidate_not_frozen")
                result = {
                    "schema_version": "stage3c2-evaluation-result-v1",
                    "evaluation_id": f"{candidate['campaign_id']}-{candidate['experiment_id']}-{dataset_id}",
                    "candidate_id": f"{candidate['campaign_id']}:{candidate['experiment_id']}",
                    "dataset_id": dataset_id,
                    "policy_hash": phash,
                    "validation_status": "validation_access_denied",
                    "validation_access_event": event,
                    "validation_accessed": False,
                }
                dump_json(output / "stage3c2-evaluation-result.json", result)
                return result
            freeze_check = validate_candidate_freeze(repo_root, repo_root / freeze_path, candidate, candidate_manifest_path, repo_root / experiment_spec_path_for_candidate(candidate))
            if not freeze_check["valid"]:
                event = deny_validation_access(repo_root, policy, phash, candidate, role, "candidate_changed_after_freeze")
                result = {
                    "schema_version": "stage3c2-evaluation-result-v1",
                    "evaluation_id": f"{candidate['campaign_id']}-{candidate['experiment_id']}-{dataset_id}",
                    "candidate_id": f"{candidate['campaign_id']}:{candidate['experiment_id']}",
                    "dataset_id": dataset_id,
                    "policy_hash": phash,
                    "validation_status": "validation_integrity_failed",
                    "freeze_check": freeze_check,
                    "validation_access_event": event,
                    "validation_accessed": False,
                }
                dump_json(output / "stage3c2-evaluation-result.json", result)
                return result
        event = maybe_authorize_validation(repo_root, policy, phash, candidate, {}, role, "development_not_run")
        if event["authorization_result"] != "authorized":
            result = {
                "schema_version": "stage3c2-evaluation-result-v1",
                "evaluation_id": f"{candidate['campaign_id']}-{candidate['experiment_id']}-{dataset_id}",
                "candidate_id": f"{candidate['campaign_id']}:{candidate['experiment_id']}",
                "dataset_id": dataset_id,
                "policy_hash": phash,
                "development_status": "validation_access_denied",
                "validation_access_event": event,
                "validation_accessed": False,
            }
            dump_json(output / "stage3c2-evaluation-result.json", result)
            return result
        dataset = validate_dataset(repo_root, dataset_id, policy, role)
        baseline_run = run_eval_backtest(repo_root, dataset, "baseline")
        candidate_run = run_eval_backtest(repo_root, dataset, "candidate", candidate)
        baseline_vector = result_vector(repo_root, baseline_run, baseline, dataset_id)
        candidate_vector = result_vector(repo_root, candidate_run, candidate["candidate_strategy_class"], dataset_id)
        comparison = compare_vectors(baseline_vector, candidate_vector)
        total = candidate_vector["metrics"]["total_trades"]["normalized_value"]
        long_count = candidate_vector["metrics"]["long_trades"]["normalized_value"]
        short_count = candidate_vector["metrics"]["short_trades"]["normalized_value"]
        validation_status = "validation_passed_provisional" if total and long_count and short_count else "validation_inconclusive"
        decision = gate_decision(policy, baseline_vector, candidate_vector, comparison)
        decision["final_decision"] = validation_status
        evaluation_id = f"{candidate['campaign_id']}-{candidate['experiment_id']}-{dataset_id}"
        candidate_id = f"{candidate['campaign_id']}:{candidate['experiment_id']}"
        result = {
            "schema_version": "stage3c2-evaluation-result-v1",
            "evaluation_stage": "validation",
            "evaluation_id": evaluation_id,
            "candidate_id": candidate_id,
            "candidate_manifest": repo_rel(repo_root, candidate_manifest_path),
            "candidate_source_sha256": candidate["candidate_strategy_sha256"],
            "dataset_id": dataset_id,
            "dataset_aggregate_sha256": dataset["aggregate_sha256"],
            "policy_id": policy["policy_id"],
            "policy_hash": phash,
            "policy_approval_status": policy["policy_approval_status"],
            "evaluator_version": EVALUATOR_VERSION,
            "baseline_run": baseline_run,
            "candidate_run": candidate_run,
            "baseline_metrics": baseline_vector,
            "candidate_metrics": candidate_vector,
            "comparison": comparison,
            "gate_decision": decision,
            "validation_status": validation_status,
            "validation_access_event": event,
            "validation_accessed": True,
            "bias_validation": {"lookahead_analysis": "not_run", "recursive_analysis": "not_run"},
            "promotion_limit_reason": ["bias_checks_pending", "holdout_not_run", "forward_dry_run_not_run"],
            "champion_promotion": "not_allowed",
            "qualified_challenger": "not_allowed",
            "holdout_accessed": False,
            "created_at": utc_now(),
        }
        artifacts = {
            "baseline_metrics": output / "baseline-validation-metrics.json",
            "candidate_metrics": output / "candidate-validation-metrics.json",
            "comparison": output / "validation-comparison.json",
            "gate_decision": output / "validation-gate-decision.json",
            "limited_disclosure": output / "limited-disclosure.json",
            "final_report": output / "stage3c2-final-report.md",
            "evaluation_result": output / "stage3c2-evaluation-result.json",
        }
        dump_json(artifacts["baseline_metrics"], baseline_vector)
        dump_json(artifacts["candidate_metrics"], candidate_vector)
        dump_json(artifacts["comparison"], comparison)
        dump_json(artifacts["gate_decision"], decision)
        write_limited_disclosure(artifacts["limited_disclosure"], {**result, "development_status": validation_status})
        write_final_markdown(artifacts["final_report"], result)
        result["artifact_paths"] = {key: repo_rel(repo_root, path) for key, path in artifacts.items()}
        result["result_path"] = result["artifact_paths"]["evaluation_result"]
        dump_json(artifacts["evaluation_result"], result)
        dump_json(output / "artifact-hashes.json", artifact_hashes(output))
        result["artifact_paths"]["artifact_hashes"] = repo_rel(repo_root, output / "artifact-hashes.json")
        dump_json(artifacts["evaluation_result"], result)
        write_registry(repo_root, policy, policy_path, phash, candidate, dataset, result)
        return result
    dataset = validate_dataset(repo_root, dataset_id, policy, role)
    if role != "development_evaluator":
        raise EvaluationError("role_not_allowed", f"role not allowed for development evaluation: {role}")
    baseline_run = run_eval_backtest(repo_root, dataset, "baseline")
    candidate_run = run_eval_backtest(repo_root, dataset, "candidate", candidate)
    baseline_vector = result_vector(repo_root, baseline_run, baseline, dataset_id)
    candidate_vector = result_vector(repo_root, candidate_run, candidate["candidate_strategy_class"], dataset_id)
    comparison = compare_vectors(baseline_vector, candidate_vector)
    decision = gate_decision(policy, baseline_vector, candidate_vector, comparison)
    evaluation_id = f"{candidate['campaign_id']}-{candidate['experiment_id']}-{dataset_id}"
    candidate_id = f"{candidate['campaign_id']}:{candidate['experiment_id']}"
    result = {
        "schema_version": "stage3c2-evaluation-result-v1",
        "evaluation_id": evaluation_id,
        "candidate_id": candidate_id,
        "candidate_manifest": repo_rel(repo_root, candidate_manifest_path),
        "candidate_source_sha256": candidate["candidate_strategy_sha256"],
        "candidate_manifest_sha256": sha256_file(candidate_manifest_path),
        "experiment_spec_sha256": candidate["experiment_spec_hash"],
        "dataset_id": dataset_id,
        "dataset_aggregate_sha256": dataset["aggregate_sha256"],
        "policy_id": policy["policy_id"],
        "policy_hash": phash,
        "policy_approval_status": policy["policy_approval_status"],
        "evaluator_version": EVALUATOR_VERSION,
        "baseline_run": baseline_run,
        "candidate_run": candidate_run,
        "baseline_metrics": baseline_vector,
        "candidate_metrics": candidate_vector,
        "comparison": comparison,
        "gate_decision": decision,
        "development_status": decision["final_decision"],
        "validation_accessed": False,
        "validation_access_event": None,
        "bias_validation": {"lookahead_analysis": "not_run", "recursive_analysis": "not_run"},
        "promotion_limit_reason": ["bias_checks_pending", "holdout_not_run", "forward_dry_run_not_run"],
        "champion_promotion": "not_allowed",
        "qualified_challenger": "not_allowed",
        "holdout_accessed": False,
        "created_at": utc_now(),
    }
    artifacts = {
        "baseline_metrics": output / "baseline-development-metrics.json",
        "candidate_metrics": output / "candidate-development-metrics.json",
        "comparison": output / "development-comparison.json",
        "gate_decision": output / "development-gate-decision.json",
        "limited_disclosure": output / "limited-disclosure.json",
        "final_report": output / "stage3c2-final-report.md",
        "evaluation_result": output / "stage3c2-evaluation-result.json",
    }
    dump_json(artifacts["baseline_metrics"], baseline_vector)
    dump_json(artifacts["candidate_metrics"], candidate_vector)
    dump_json(artifacts["comparison"], comparison)
    dump_json(artifacts["gate_decision"], decision)
    write_limited_disclosure(artifacts["limited_disclosure"], result)
    write_final_markdown(artifacts["final_report"], result)
    result["artifact_paths"] = {key: repo_rel(repo_root, path) for key, path in artifacts.items()}
    result["result_path"] = result["artifact_paths"]["evaluation_result"]
    dump_json(artifacts["evaluation_result"], result)
    dump_json(output / "artifact-hashes.json", artifact_hashes(output))
    result["artifact_paths"]["artifact_hashes"] = repo_rel(repo_root, output / "artifact-hashes.json")
    dump_json(artifacts["evaluation_result"], result)
    write_registry(repo_root, policy, policy_path, phash, candidate, dataset, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a frozen research candidate on a sealed dataset.")
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--role", required=True, choices=["development_evaluator", "validation_evaluator"])
    parser.add_argument("--policy", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        result = evaluate_candidate(
            Path.cwd(),
            Path(args.candidate_manifest),
            args.dataset_id,
            args.role,
            Path(args.policy),
            args.baseline,
            Path(args.output),
        )
    except (EvaluationError, DataAccessError) as exc:
        payload = {
            "status": "failed",
            "reason_code": getattr(exc, "reason_code", "evaluation_error"),
            "message": str(exc),
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        else:
            print(f"{payload['reason_code']}: {payload['message']}")
        return 1 if args.strict else 0
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(result["development_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
