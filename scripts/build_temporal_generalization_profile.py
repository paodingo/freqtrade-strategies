#!/usr/bin/env python3
"""Build and execute the frozen Stage 3E.1 temporal generalization profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import subprocess
import sys
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from profile_futures_market_regimes import load_frame, profile_temporal_slice, write_temporal_markdown
from research_control import load_simple_yaml
from run_experiment import (
    artifact_hashes,
    compare_core_metrics,
    dump_json,
    dump_manifest,
    find_result_json,
    locate_strategy_block,
    sha256_file,
)
from run_stage3a5_acceptance import write_normalized_trades


CAMPAIGN_ID = "stage3e1-temporal-generalization-profile"
CAMPAIGN_PATH = Path("research/campaigns/active/stage3e1-temporal-generalization-profile.yaml")
POLICY_PATH = Path("research/temporal/stage3e1-slice-policy.yaml")
SLICES_PATH = Path("research/temporal/stage3e1-slices.yaml")
COMPARISON_PATH = Path("research/temporal/stage3e1-temporal-comparison.json")
PROFILE_ROOT = Path("research/temporal/profiles")
SNAPSHOT_ROOT = Path("research/temporal/snapshots")
MANIFEST_ROOT = Path("research/temporal/execution-manifests")
RESULT_ROOT = Path("research/results") / CAMPAIGN_ID
FINAL_JSON = RESULT_ROOT / "stage3e1-final-report.json"
FINAL_MD = RESULT_ROOT / "stage3e1-final-report.md"
AUDIT_MD = Path("reports/audits/stage3e1_temporal_data_coverage_audit.md")
REGISTRY = Path("research/registry/research.db")
STRATEGY = Path("strategies/RegimeAwareV6.py")
CONFIG = Path("research/runtime/demo-futures-backtest-config.json")
EXCHANGE_SNAPSHOT = Path("research/exchange_snapshots/binance-usdm-futures-2025-8-demo")
BASE_STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
SLICE_HOURS = 1512
WARMUP_HOURS = 800
MIN_VALID_SLICES = 4
MIN_TRADES_PER_SLICE = 5

SOURCE_DATASETS = {
    "development_v2": "futures-dev-btc-usdt-usdt-20240101-20240830-v2",
    "validation_v2_baseline_only": "futures-validation-btc-usdt-usdt-20240912-20250128-v2",
}
SLICE_BLUEPRINTS = (
    ("stage3e1-s01", "development_v2", "2024-02-04T00:00:00Z", "2024-04-07T00:00:00Z"),
    ("stage3e1-s02", "development_v2", "2024-04-07T00:00:00Z", "2024-06-09T00:00:00Z"),
    ("stage3e1-s03", "development_v2", "2024-06-09T00:00:00Z", "2024-08-11T00:00:00Z"),
    ("stage3e1-s04", "validation_v2_baseline_only", "2024-10-16T00:00:00Z", "2024-12-18T00:00:00Z"),
)


class TemporalProfileError(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = "validation_error"
        self.reason_code = reason_code
        self.message = message


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def self_hash(payload: dict[str, Any], field: str) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != field})


def immutable_manifest(path: Path, payload: dict[str, Any], hash_field: str) -> None:
    payload[hash_field] = self_hash(payload, hash_field)
    if path.exists():
        current = load_simple_yaml(path)
        if current != payload:
            raise TemporalProfileError("frozen_temporal_control_drift", path.as_posix())
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(path, payload)


def file_coverage(path: Path, hours: int) -> dict[str, Any]:
    frame = load_frame(path)
    dates = frame["date"]
    expected = pd.to_timedelta(hours, unit="h")
    differences = dates.diff()
    gaps = []
    for index in differences[differences > expected].index:
        gaps.append({"after": dates.iloc[index - 1].isoformat(), "before": dates.iloc[index].isoformat(), "hours": float(differences.iloc[index].total_seconds() / 3600)})
    return {
        "path": path.as_posix(), "rows": int(len(frame)), "start": dates.min().isoformat(), "end": dates.max().isoformat(),
        "duplicates": int(dates.duplicated().sum()), "missing_intervals": gaps, "sha256": sha256_file(path), "bytes": path.stat().st_size,
    }


def audit_sources(repo_root: Path) -> dict[str, Any]:
    sources = {}
    all_hashes = []
    for role, dataset_id in SOURCE_DATASETS.items():
        root = repo_root / "research/data/snapshots" / dataset_id
        manifest = load_simple_yaml(root / "manifest.yaml")
        if not manifest.get("sealed"):
            raise TemporalProfileError("temporal_source_not_sealed", dataset_id)
        files = {
            "futures_1h": file_coverage(root / "data/futures/BTC_USDT_USDT-1h-futures.feather", 1),
            "futures_4h": file_coverage(root / "data/futures/BTC_USDT_USDT-4h-futures.feather", 4),
            "mark_8h": file_coverage(root / "data/futures/BTC_USDT_USDT-8h-mark.feather", 8),
            "funding_rate_8h": file_coverage(root / "data/futures/BTC_USDT_USDT-8h-funding_rate.feather", 8),
        }
        if any(item["duplicates"] or item["missing_intervals"] for item in files.values()):
            raise TemporalProfileError("temporal_source_data_incomplete", dataset_id)
        all_hashes.extend(item["sha256"] for item in files.values())
        sources[role] = {"dataset_id": dataset_id, "manifest_sha256": sha256_file(root / "manifest.yaml"), "aggregate_sha256": manifest["aggregate_sha256"], "files": files}
    return {
        "schema_version": "stage3e1-temporal-data-audit-v1", "strategy_results_used": False,
        "sources": sources, "aggregate_sha256": stable_hash(sorted(all_hashes)),
        "maximum_continuous_ranges": [
            {"dataset_id": value["dataset_id"], "start": value["files"]["futures_1h"]["start"], "end": value["files"]["futures_1h"]["end"]}
            for value in sources.values()
        ],
        "acceptance_fixture_used_as_performance_slice": False,
        "development_v2_relationship": "three frozen baseline-only temporal slices",
        "validation_v2_relationship": "one frozen formal-strategy profiling slice; never candidate tuning feedback",
        "holdout_accessed": False, "additional_provisioning_required": False,
    }


def write_audit(repo_root: Path, audit: dict[str, Any]) -> None:
    lines = ["# Stage 3E.1 Temporal Data Coverage Audit", "", "Strategy results were not used for this audit.", ""]
    for role, source in audit["sources"].items():
        lines.extend([f"## {role}", "", f"- Dataset: `{source['dataset_id']}`", f"- Aggregate SHA-256: `{source['aggregate_sha256']}`", ""])
        for kind, item in source["files"].items():
            lines.append(f"- `{kind}`: `{item['rows']}` rows, `{item['start']}` to `{item['end']}`, duplicates `{item['duplicates']}`, gaps `{len(item['missing_intervals'])}`, SHA-256 `{item['sha256']}`")
        lines.append("")
    lines.extend([
        "## Governance", "", "- Acceptance Fixture is excluded from performance profiling.",
        "- Development v2 supplies three slices.", "- Validation v2 supplies one formal-strategy profiling slice and is not candidate tuning feedback.",
        "- Holdout is not accessed.", "- Additional provisioning required: `false`.", "",
    ])
    target = repo_root / AUDIT_MD
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")


def build_policy(frozen_at: str) -> dict[str, Any]:
    return {
        "schema_version": "stage3e1-slice-policy-v1", "policy_id": "stage3e1-fixed-63-day-slices",
        "selection_basis": "chronological fixed-length chunks aligned to UTC midnight within pre-existing v2 evaluation ranges",
        "selection_uses_strategy_results": False, "selection_uses_return_or_risk_metrics": False,
        "evaluation_candles_1h": SLICE_HOURS, "evaluation_hours": SLICE_HOURS, "warmup_hours": WARMUP_HOURS,
        "warmup_in_evaluation_metrics": False, "formal_intervals_non_overlapping": True, "boundaries_timezone": "UTC",
        "minimum_valid_slices": MIN_VALID_SLICES, "minimum_trades_per_slice_for_coverage": MIN_TRADES_PER_SLICE,
        "acceptance_fixture_allowed": False, "candidate_tuning_allowed": False, "holdout_access_allowed": False,
        "slice_mutation_after_first_backtest_allowed": False,
        "classification_order": ["execution_inconsistent", "coverage_insufficient", "temporally_fragile", "regime_dependent", "temporally_consistent"],
        "frozen_at": frozen_at, "frozen_before_first_backtest": True,
    }


def build_slices(frozen_at: str) -> dict[str, Any]:
    slices = []
    for number, (slice_id, source_role, start, end) in enumerate(SLICE_BLUEPRINTS, start=1):
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if int((end_ts - start_ts).total_seconds() / 3600) != SLICE_HOURS:
            raise TemporalProfileError("slice_length_mismatch", slice_id)
        warmup = start_ts - pd.to_timedelta(WARMUP_HOURS, unit="h")
        dataset_id = f"temporal-{slice_id}-btc-usdt-usdt-1h"
        slices.append({
            "slice_number": number, "slice_id": slice_id, "dataset_id": dataset_id, "source_role": source_role,
            "source_dataset_id": SOURCE_DATASETS[source_role], "warmup_start": warmup.isoformat().replace("+00:00", "Z"),
            "evaluation_start": start, "evaluation_end_exclusive": end, "evaluation_candles_1h": SLICE_HOURS,
            "timerange": f"{start_ts.strftime('%Y%m%d')}-{end_ts.strftime('%Y%m%d')}",
            "intended_use": "temporal_generalization_profile", "suitable_for_strategy_iteration": False,
            "suitable_for_candidate_tuning": False, "suitable_for_champion_promotion": False,
        })
    payload = {
        "schema_version": "stage3e1-frozen-slices-v1", "campaign_id": CAMPAIGN_ID, "status": "frozen",
        "frozen_at": frozen_at, "frozen_before_first_backtest": True, "slice_order_mutable": False,
        "slice_count": len(slices), "evaluation_candles_per_slice": SLICE_HOURS, "slices": slices,
    }
    return payload


def create_slice_snapshot(repo_root: Path, item: dict[str, Any]) -> dict[str, Any]:
    source = repo_root / "research/data/snapshots" / item["source_dataset_id"] / "data/futures"
    target_root = repo_root / SNAPSHOT_ROOT / item["dataset_id"]
    target_data = target_root / "data/futures"
    target_data.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(item["warmup_start"])
    end = pd.Timestamp(item["evaluation_end_exclusive"])
    file_specs = (
        ("BTC_USDT_USDT-1h-futures.feather", "futures", "1h"),
        ("BTC_USDT_USDT-4h-futures.feather", "futures", "4h"),
        ("BTC_USDT_USDT-8h-mark.feather", "mark", "8h"),
        ("BTC_USDT_USDT-8h-funding_rate.feather", "funding_rate", "8h"),
    )
    files, coverage = [], []
    for name, candle_type, timeframe in file_specs:
        frame = load_frame(source / name)
        sliced = frame[(frame["date"] >= start) & (frame["date"] < end)].reset_index(drop=True)
        output = target_data / name
        if not output.exists():
            sliced.to_feather(output)
        actual = load_frame(output)
        if len(actual) != len(sliced) or not actual["date"].equals(sliced["date"]):
            raise TemporalProfileError("sealed_temporal_snapshot_drift", item["slice_id"])
        files.append({"path": output.relative_to(repo_root).as_posix(), "bytes": output.stat().st_size, "sha256": sha256_file(output)})
        coverage.append({"file": name, "rows": len(actual), "start": actual["date"].min().isoformat(), "end": actual["date"].max().isoformat(), "candle_type": candle_type, "timeframe": timeframe})
    manifest = {
        "schema_version": "stage3e1-temporal-snapshot-v1", "dataset_id": item["dataset_id"], "source_dataset_id": item["source_dataset_id"],
        "slice_id": item["slice_id"], "exchange": "binance", "trading_mode": "futures", "margin_mode": "isolated",
        "pairs": ["BTC/USDT:USDT"], "timeframes": ["1h", "4h", "8h"], "candle_types": ["futures", "mark", "funding_rate"],
        "data_path": (SNAPSHOT_ROOT / item["dataset_id"] / "data").as_posix(), "files": files, "coverage": coverage,
        "warmup_range": {"start": item["warmup_start"], "end_exclusive": item["evaluation_start"]},
        "evaluation_range": {"start": item["evaluation_start"], "end_exclusive": item["evaluation_end_exclusive"], "main_1h_candles": SLICE_HOURS},
        "intended_use": "temporal_generalization_profile", "suitable_for_strategy_iteration": False,
        "suitable_for_candidate_tuning": False, "suitable_for_champion_promotion": False,
        "campaign_mutable": False, "network_accessed": False, "sealed": True,
    }
    manifest["aggregate_sha256"] = stable_hash(files)
    immutable_manifest(target_root / "manifest.yaml", manifest, "manifest_sha256")
    return load_simple_yaml(target_root / "manifest.yaml")


def build_market_profile(repo_root: Path, item: dict[str, Any]) -> dict[str, Any]:
    data = repo_root / SNAPSHOT_ROOT / item["dataset_id"] / "data/futures"
    profile = profile_temporal_slice(
        item["slice_id"], load_frame(data / "BTC_USDT_USDT-1h-futures.feather"),
        load_frame(data / "BTC_USDT_USDT-8h-funding_rate.feather"), item["evaluation_start"], item["evaluation_end_exclusive"],
    )
    path = repo_root / PROFILE_ROOT / f"{item['slice_id']}-market-profile.json"
    md = repo_root / PROFILE_ROOT / f"{item['slice_id']}-market-profile.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != profile:
        raise TemporalProfileError("market_profile_classifier_drift", item["slice_id"])
    dump_json(path, profile)
    write_temporal_markdown(md, profile)
    return profile


def build_campaign(slices: dict[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID, "mode": "temporal_generalization_profile", "runner_type": "fresh_python_process_one_backtest",
        "scope": {"allowed_paths": ["research/temporal/**", f"research/results/{CAMPAIGN_ID}/**", CAMPAIGN_PATH.as_posix(), REGISTRY.as_posix(), AUDIT_MD.as_posix()],
                  "blocked_paths": [".env", "secrets/**", "deploy/**", "user_data/config_live.json", "configs/production/**", "strategies/**", "research/data/snapshots/**", "scripts/start_bot.sh", "scripts/refresh_data.sh"]},
        "budget": {"max_slices": 6, "max_total_attempts": 16, "max_retries_per_slice": 1, "max_wall_clock_hours": 12, "max_consecutive_infrastructure_failures": 3},
        "autonomy": {"automatically_claim_next": True, "automatically_generate_hypotheses": False, "automatically_generate_followup_tasks": False, "automatically_promote_champion": False, "access_sealed_holdout": False},
        "slice_plan": {"path": SLICES_PATH.as_posix(), "sha256": slices["slices_sha256"], "frozen": True},
        "fixed_contract": {"strategy": "RegimeAwareV6", "strategy_sha256": BASE_STRATEGY_SHA256, "pair": "BTC/USDT:USDT", "timeframe": "1h", "fee": "0.0004", "trading_mode": "futures", "margin_mode": "isolated", "cache": "none", "network": "blocked"},
        "sealed_offline_backtest": {"exchange_snapshot": EXCHANGE_SNAPSHOT.as_posix(), "network_policy": "socket_blocker"},
        "stop_conditions": ["slice_queue_exhausted", "budget_exhausted", "strategy_hash_drift", "slice_plan_drift", "dataset_hash_drift", "execution_inconsistent", "guard_violation"],
        "forbidden_actions": ["strategy_change", "candidate_creation", "parameter_search", "hyperopt", "holdout", "champion", "qualified_challenger", "forward_dry_run", "automatic_followup_campaign"],
    }


def execution_manifest(repo_root: Path, campaign: dict[str, Any], item: dict[str, Any], run_id: str) -> Path:
    run_dir = RESULT_ROOT / str(item["slice_number"]) / run_id
    dependency_hashes = {name: sha256_file(repo_root / f"strategies/{name}.py") for name in ("regime_aware_base", "regime_detector", "risk_manager")}
    run_campaign = json.loads(json.dumps(campaign))
    run_campaign["fixed_backtest"] = {
        "runtime_config": "research/runtime/freqtrade-runtime.yaml", "dataset_id": item["dataset_id"],
        "dataset_manifest": (SNAPSHOT_ROOT / item["dataset_id"] / "manifest.yaml").as_posix(), "subcommand": "sealed_offline_backtest",
        "strategy": "RegimeAwareV6", "strategy_file": STRATEGY.as_posix(), "strategy_path": "strategies", "config": CONFIG.as_posix(),
        "timerange": item["timerange"], "timeframe": "1h", "pairs": ["BTC/USDT:USDT"], "fee": "0.0004",
        "datadir": (SNAPSHOT_ROOT / item["dataset_id"] / "data").as_posix(), "timeout_seconds": 600, "acceptance_gate": {},
    }
    payload = {
        "schema_version": "stage3e1-immutable-execution-manifest-v1", "campaign_id": CAMPAIGN_ID,
        "slice_number": item["slice_number"], "slice_id": item["slice_id"], "execution_run_id": run_id,
        "run_dir": run_dir.as_posix(), "strategy_file": STRATEGY.as_posix(), "expected_strategy_sha256": BASE_STRATEGY_SHA256,
        "dependency_hashes": dependency_hashes, "dataset_id": item["dataset_id"], "dataset_manifest_sha256": sha256_file(repo_root / SNAPSHOT_ROOT / item["dataset_id"] / "manifest.yaml"),
        "slice_plan_sha256": campaign["slice_plan"]["sha256"], "single_backtest_only": True,
        "claim_next_slice_allowed": False, "registry_write_allowed": False, "exchange_snapshot": EXCHANGE_SNAPSHOT.as_posix(), "campaign": run_campaign,
    }
    payload["execution_manifest_sha256"] = self_hash(payload, "execution_manifest_sha256")
    path = repo_root / MANIFEST_ROOT / item["slice_id"] / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != payload:
        raise TemporalProfileError("immutable_execution_manifest_drift", path.as_posix())
    if not path.exists():
        dump_json(path, payload)
    return path


def launch_worker(repo_root: Path, manifest: Path) -> None:
    completed = subprocess.run([sys.executable, str(repo_root / "scripts/run_temporal_slice_worker.py"), "--manifest", str(manifest)], cwd=repo_root, capture_output=True, text=True, timeout=900)
    dump_json(manifest.with_suffix(".launch.json"), {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "shell": False})
    if completed.returncode != 0:
        raise TemporalProfileError("temporal_slice_execution_failed", completed.stdout[-1000:] or completed.stderr[-1000:])


def nullable(value: Any, reason: str, missing: dict[str, str]) -> Any:
    if value is None:
        missing[reason] = "source field unavailable or metric not computable"
    return value


def temporal_metrics(result_path: Path, strategy: str, profile: dict[str, Any], evaluation_days: int) -> dict[str, Any]:
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    block = locate_strategy_block(payload, strategy)
    trades = list(block.get("trades") or [])
    missing: dict[str, str] = {}
    profit_abs = [float(row.get("profit_abs", 0.0)) for row in trades]
    profit_ratio = [float(row.get("profit_ratio", 0.0)) for row in trades]
    longs = [row for row in trades if not row.get("is_short")]
    shorts = [row for row in trades if row.get("is_short")]
    close_dates = pd.to_datetime([row.get("close_date") for row in trades], utc=True) if trades else pd.DatetimeIndex([])
    weekly_returns: list[dict[str, Any]] = []
    rolling: list[dict[str, Any]] = []
    if trades:
        series = pd.Series(profit_ratio, index=close_dates).sort_index()
        weekly = series.resample("7D", origin=pd.Timestamp(block["backtest_start"], tz="UTC")).sum()
        weekly_returns = [{"week_start": index.isoformat(), "return": float(value)} for index, value in weekly.items()]
        daily = series.resample("1D").sum()
        rolling_series = daily.rolling(28, min_periods=28).sum().dropna()
        rolling = [{"end": index.isoformat(), "return": float(value)} for index, value in rolling_series.items()]
    timeline = pd.DataFrame(profile["regime_timeline"])
    if not timeline.empty:
        timeline["timestamp"] = pd.to_datetime(timeline["timestamp"], utc=True)
        timeline = timeline.sort_values("timestamp")
    regime = defaultdict(lambda: {"trades": 0, "profit_abs": 0.0, "profit_ratio": 0.0})
    for row in trades:
        opened = pd.Timestamp(row["open_date"])
        candidates = timeline[timeline["timestamp"] <= opened] if not timeline.empty else timeline
        label = "unclassified" if candidates.empty else candidates.iloc[-1]["regime"]
        regime[label]["trades"] += 1
        regime[label]["profit_abs"] += float(row.get("profit_abs", 0.0))
        regime[label]["profit_ratio"] += float(row.get("profit_ratio", 0.0))
    durations = [float(row.get("trade_duration", row.get("duration", 0.0))) for row in trades if row.get("trade_duration", row.get("duration")) is not None]
    long_durations = [float(row.get("trade_duration", 0.0)) for row in longs if row.get("trade_duration") is not None]
    short_durations = [float(row.get("trade_duration", 0.0)) for row in shorts if row.get("trade_duration") is not None]
    fees = [float(row.get("fee_open_cost", 0.0) or 0.0) + float(row.get("fee_close_cost", 0.0) or 0.0) for row in trades]
    funding = [float(row.get("funding_fees", 0.0) or 0.0) for row in trades if row.get("funding_fees") is not None]
    active_weeks = len({date.to_period("W").start_time for date in close_dates.tz_localize(None)}) if trades else 0
    metric = {
        "schema_version": "stage3e1-per-slice-metrics-v1", "missing_metrics": missing,
        "coverage": {"total_trades": len(trades), "long_trades": len(longs), "short_trades": len(shorts), "closed_trades": sum(bool(row.get("close_date")) for row in trades), "active_weeks": active_weeks, "trades_per_week": len(trades) / (evaluation_days / 7), "enter_tag_distribution": dict(Counter(row.get("enter_tag") for row in trades)), "exit_reason_distribution": dict(Counter(row.get("exit_reason") for row in trades))},
        "return": {"total_return": nullable(block.get("profit_total"), "total_return", missing), "total_profit": nullable(block.get("profit_total_abs"), "total_profit", missing), "long_return": nullable(block.get("profit_total_long"), "long_return", missing), "short_return": nullable(block.get("profit_total_short"), "short_return", missing), "average_profit_per_trade": None if not profit_ratio else sum(profit_ratio) / len(profit_ratio), "median_profit_per_trade": None if not profit_ratio else float(pd.Series(profit_ratio).median()), "gross_profit": sum(value for value in profit_abs if value > 0), "gross_loss": sum(value for value in profit_abs if value < 0), "expectancy": nullable(block.get("expectancy"), "expectancy", missing)},
        "risk": {"max_drawdown_percentage": nullable(block.get("max_drawdown_account"), "max_drawdown_percentage", missing), "max_drawdown_absolute": nullable(block.get("max_drawdown_abs"), "max_drawdown_absolute", missing), "drawdown_duration": nullable(block.get("drawdown_duration"), "drawdown_duration", missing), "worst_trade": None if not profit_ratio else min(profit_ratio), "maximum_consecutive_losses": nullable(block.get("max_consecutive_losses"), "maximum_consecutive_losses", missing), "minimum_balance": nullable(block.get("max_drawdown_low"), "minimum_balance", missing), "underwater_duration": nullable(block.get("drawdown_duration"), "underwater_duration", missing)},
        "risk_adjusted": {"profit_factor": nullable(block.get("profit_factor"), "profit_factor", missing), "sharpe": nullable(block.get("sharpe"), "sharpe", missing), "sortino": nullable(block.get("sortino"), "sortino", missing), "calmar": nullable(block.get("calmar"), "calmar", missing)},
        "execution_cost": {"fee_cost": sum(fees) if trades else None, "funding_fees": sum(funding) if funding else None, "average_leverage": None if not trades else sum(float(row.get("leverage", 1.0)) for row in trades) / len(trades), "average_duration_minutes": None if not durations else sum(durations) / len(durations), "long_average_duration_minutes": None if not long_durations else sum(long_durations) / len(long_durations), "short_average_duration_minutes": None if not short_durations else sum(short_durations) / len(short_durations)},
        "internal_stability": {"weekly_returns": weekly_returns, "rolling_28_day_returns": rolling, "positive_rolling_window_count": sum(row["return"] > 0 for row in rolling), "negative_rolling_window_count": sum(row["return"] < 0 for row in rolling), "worst_rolling_window": None if not rolling else min(rolling, key=lambda row: row["return"]), "best_rolling_window": None if not rolling else max(rolling, key=lambda row: row["return"]), "regime_results": dict(regime)},
    }
    for section in metric.values():
        if isinstance(section, dict):
            for key, value in section.items():
                if value is None and key not in missing and section is not metric["missing_metrics"]:
                    missing.setdefault(key, "insufficient observations")
    return metric


def summarize_run(repo_root: Path, item: dict[str, Any], run_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    run_dir = repo_root / RESULT_ROOT / str(item["slice_number"]) / run_id
    result = find_result_json(run_dir)
    metrics = temporal_metrics(result, "RegimeAwareV6", profile, SLICE_HOURS // 24)
    dump_json(run_dir / "temporal-metrics.json", metrics)
    normalized = write_normalized_trades(run_dir, result, "RegimeAwareV6")
    identity = json.loads((run_dir / "runtime-code-identity.json").read_text(encoding="utf-8"))
    runner = json.loads((run_dir / "runner-report.json").read_text(encoding="utf-8"))
    dump_json(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    return {"run_id": run_id, "process_id": identity["process_id"], "runtime_identity": (run_dir / "runtime-code-identity.json").relative_to(repo_root).as_posix(), "input_fingerprint": runner["input_fingerprint"], "normalized_trade_hash": normalized["sha256"], "normalized_trades": (run_dir / "normalized-trades.json").relative_to(repo_root).as_posix(), "raw_result": result.relative_to(repo_root).as_posix(), "metrics_path": (run_dir / "temporal-metrics.json").relative_to(repo_root).as_posix(), "metrics": metrics}


def compare_runs(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    # Core parser comparison plus the richer temporal metrics and normalized trades.
    a = first["metrics"]
    b = second["metrics"]
    differences = {}
    for section in ("coverage", "return", "risk", "risk_adjusted", "execution_cost", "internal_stability"):
        if a[section] != b[section]: differences[section] = {"run_a": a[section], "run_b": b[section]}
    if first["normalized_trade_hash"] != second["normalized_trade_hash"]: differences["normalized_trade_hash"] = True
    if first["input_fingerprint"] != second["input_fingerprint"]: differences["input_fingerprint"] = True
    if first["process_id"] == second["process_id"]: differences["process_id"] = "not_independent"
    return {"consistent": not differences, "differences": differences, "run_a_pid": first["process_id"], "run_b_pid": second["process_id"]}


def classify_temporal_profile(slice_results: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if len(slice_results) < MIN_VALID_SLICES or any(not item.get("reproducibility", {}).get("consistent") for item in slice_results):
        reason = "fewer_than_four_valid_slices" if len(slice_results) < MIN_VALID_SLICES else "run_a_run_b_or_input_identity_mismatch"
        return ("coverage_insufficient", [reason]) if len(slice_results) < MIN_VALID_SLICES else ("execution_inconsistent", [reason])
    metrics = [item["run_a"]["metrics"] for item in slice_results]
    totals = [metric["coverage"]["total_trades"] for metric in metrics]
    if sum(value < MIN_TRADES_PER_SLICE for value in totals) >= 2:
        return "coverage_insufficient", ["multiple_slices_below_minimum_trade_coverage"]
    returns = [float(metric["return"]["total_return"] or 0.0) for metric in metrics]
    positive = [value for value in returns if value > 0]
    concentration = (max(positive) / sum(positive)) if positive else 1.0
    consecutive_negative = any(returns[index] < 0 and returns[index + 1] < 0 for index in range(len(returns) - 1))
    directional_disappearance = sum(metric["coverage"]["long_trades"] == 0 or metric["coverage"]["short_trades"] == 0 for metric in metrics)
    drawdowns = [metric["risk"]["max_drawdown_percentage"] for metric in metrics if metric["risk"]["max_drawdown_percentage"] is not None]
    risk_outlier = bool(drawdowns and max(drawdowns) > max(0.15, 2.5 * float(pd.Series(drawdowns).median())))
    if concentration > 0.65 or consecutive_negative or directional_disappearance >= 2 or risk_outlier:
        reasons = []
        if concentration > 0.65: reasons.append("profit_concentrated_in_few_slices")
        if consecutive_negative: reasons.append("consecutive_negative_slices")
        if directional_disappearance >= 2: reasons.append("long_short_coverage_unstable")
        if risk_outlier: reasons.append("slice_risk_outlier")
        return "temporally_fragile", reasons
    grouped: dict[str, list[float]] = defaultdict(list)
    for item, value in zip(slice_results, returns): grouped[item["market_profile"]["dominant_market_regime"]].append(value)
    repeat_groups = {key: values for key, values in grouped.items() if len(values) >= 2}
    if len(repeat_groups) >= 2:
        means = [sum(values) / len(values) for values in repeat_groups.values()]
        if max(means) - min(means) >= 0.03:
            return "regime_dependent", ["repeatable_dominant_regime_return_spread"]
    return "temporally_consistent", ["coverage_directionality_concentration_and_risk_checks_passed"]


def build_comparison(results: list[dict[str, Any]]) -> dict[str, Any]:
    classification, evidence = classify_temporal_profile(results)
    metrics = [item["run_a"]["metrics"] for item in results]
    returns = [metric["return"]["total_return"] for metric in metrics]
    totals = [metric["coverage"]["total_trades"] for metric in metrics]
    pf = [metric["risk_adjusted"]["profit_factor"] for metric in metrics]
    dd = [metric["risk"]["max_drawdown_percentage"] for metric in metrics]
    valid_returns = [float(value) for value in returns if value is not None]
    recommendation = {"temporally_consistent": "cross_pair_generalization", "regime_dependent": "regime_branch_structure_audit", "temporally_fragile": "strategy_family_reassessment", "coverage_insufficient": "additional_temporal_data_provisioning", "execution_inconsistent": "harness_execution_validity_repair"}[classification]
    payload = {
        "schema_version": "stage3e1-temporal-comparison-v1", "valid_slice_count": len(results),
        "slices_with_trades": sum(value > 0 for value in totals), "slices_without_trades": sum(value == 0 for value in totals),
        "positive_return_slices": sum(value is not None and value > 0 for value in returns), "negative_return_slices": sum(value is not None and value < 0 for value in returns),
        "long_coverage_by_slice": [metric["coverage"]["long_trades"] for metric in metrics], "short_coverage_by_slice": [metric["coverage"]["short_trades"] for metric in metrics],
        "trade_frequency": totals, "trade_frequency_coefficient_of_variation": None if not totals or sum(totals) == 0 else float(pd.Series(totals).std(ddof=0) / pd.Series(totals).mean()),
        "return_distribution": returns, "profit_factor_distribution": pf, "max_drawdown_distribution": dd,
        "best_slice": None if not valid_returns else results[valid_returns.index(max(valid_returns))]["slice_id"],
        "worst_slice": None if not valid_returns else results[valid_returns.index(min(valid_returns))]["slice_id"],
        "profit_concentration_largest_positive_share": None if not any(value > 0 for value in valid_returns) else max(value for value in valid_returns if value > 0) / sum(value for value in valid_returns if value > 0),
        "classification": classification, "classification_evidence": evidence, "recommendation": recommendation,
        "slice_results": [{"slice_id": item["slice_id"], "dominant_market_regime": item["market_profile"]["dominant_market_regime"], "metrics": item["run_a"]["metrics"], "reproducibility": item["reproducibility"]} for item in results],
    }
    payload["comparison_sha256"] = self_hash(payload, "comparison_sha256")
    return payload


def record_registry(repo_root: Path, slices: dict[str, Any], results: list[dict[str, Any]], comparison: dict[str, Any], timestamp: str) -> None:
    conn = sqlite3.connect(repo_root / REGISTRY)
    try:
        with conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS stage3e1_slice_policies(policy_sha256 TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS stage3e1_temporal_slices(slice_id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, dataset_manifest_sha256 TEXT NOT NULL, profile_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS stage3e1_temporal_runs(slice_id TEXT NOT NULL, run_id TEXT NOT NULL, process_id INTEGER NOT NULL, input_fingerprint TEXT NOT NULL, normalized_trade_hash TEXT NOT NULL, metrics_path TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(slice_id, run_id));
            CREATE TABLE IF NOT EXISTS stage3e1_temporal_conclusions(campaign_id TEXT PRIMARY KEY, classification TEXT NOT NULL, recommendation TEXT NOT NULL, comparison_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
            """)
            conn.execute("INSERT OR IGNORE INTO stage3e1_slice_policies VALUES (?,?,?)", (slices["slices_sha256"], json.dumps(slices, sort_keys=True), timestamp))
            for item in results:
                conn.execute("INSERT OR IGNORE INTO stage3e1_temporal_slices VALUES (?,?,?,?,?,?)", (item["slice_id"], item["dataset_id"], item["dataset_manifest_sha256"], item["market_profile_sha256"], json.dumps(item, sort_keys=True), timestamp))
                for run_key in ("run_a", "run_b"):
                    run = item[run_key]
                    conn.execute("INSERT OR IGNORE INTO stage3e1_temporal_runs VALUES (?,?,?,?,?,?,?,?)", (item["slice_id"], run["run_id"], run["process_id"], run["input_fingerprint"], run["normalized_trade_hash"], run["metrics_path"], json.dumps(run, sort_keys=True), timestamp))
            conn.execute("INSERT OR IGNORE INTO stage3e1_temporal_conclusions VALUES (?,?,?,?,?,?)", (CAMPAIGN_ID, comparison["classification"], comparison["recommendation"], comparison["comparison_sha256"], json.dumps(comparison, sort_keys=True), timestamp))
    finally:
        conn.close()


def write_final_report(repo_root: Path, audit: dict[str, Any], slices: dict[str, Any], results: list[dict[str, Any]], comparison: dict[str, Any], timestamp: str) -> dict[str, Any]:
    final = {
        "schema_version": "stage3e1-final-report-v1", "campaign_id": CAMPAIGN_ID, "status": "completed",
        "strategy": "RegimeAwareV6", "strategy_sha256": BASE_STRATEGY_SHA256, "slice_policy_sha256": load_simple_yaml(repo_root / POLICY_PATH)["policy_sha256"],
        "slices_sha256": slices["slices_sha256"], "slice_count": len(results), "all_slices_reproducible": all(item["reproducibility"]["consistent"] for item in results),
        "all_worker_pids_unique": len({run["process_id"] for item in results for run in (item["run_a"], item["run_b"])}) == len(results) * 2,
        "classification": comparison["classification"], "classification_evidence": comparison["classification_evidence"], "recommendation": comparison["recommendation"],
        "results": results, "comparison": comparison,
        "governance": {"acceptance_fixture_used": False, "candidate_created": False, "strategy_modified": False, "parameter_search_run": False, "hyperopt_run": False, "holdout_accessed": False, "next_campaign_started": False, "validation_used_for_candidate_tuning": False},
        "budget": {"max_slices": 6, "max_total_attempts": 16, "attempts_used": len(results) * 2},
        "artifact_index": {"data_audit": AUDIT_MD.as_posix(), "slice_policy": POLICY_PATH.as_posix(), "slices": SLICES_PATH.as_posix(), "comparison": COMPARISON_PATH.as_posix(), "profiles": PROFILE_ROOT.as_posix(), "snapshots": SNAPSHOT_ROOT.as_posix(), "results": RESULT_ROOT.as_posix(), "campaign": CAMPAIGN_PATH.as_posix(), "final_json": FINAL_JSON.as_posix(), "final_markdown": FINAL_MD.as_posix()},
        "completed_at": timestamp,
    }
    final["final_sha256"] = self_hash(final, "final_sha256")
    dump_json(repo_root / FINAL_JSON, final)
    lines = ["# Stage 3E.1 Temporal Generalization Profile", "", f"- Classification: `{comparison['classification']}`", f"- Recommendation: `{comparison['recommendation']}`", f"- Frozen slices: `{len(results)}`", f"- All RUN-A/RUN-B reproducible: `{str(final['all_slices_reproducible']).lower()}`", "", "## Slice Results", ""]
    for item in results:
        metric = item["run_a"]["metrics"]
        lines.append(f"- `{item['slice_id']}` ({item['market_profile']['dominant_market_regime']}): trades `{metric['coverage']['total_trades']}` (long `{metric['coverage']['long_trades']}`, short `{metric['coverage']['short_trades']}`), return `{metric['return']['total_return']}`, max drawdown `{metric['risk']['max_drawdown_percentage']}`, Profit Factor `{metric['risk_adjusted']['profit_factor']}`")
    lines.extend(["", "## Classification Evidence", ""])
    lines.extend(f"- `{reason}`" for reason in comparison["classification_evidence"])
    lines.extend(["", "## Boundaries", "", "This profile does not establish live-trading readiness, statistical significance, Champion status, or a parameter-change recommendation. No Candidate, Hyperopt, Holdout access, or follow-up Campaign was used.", ""])
    (repo_root / FINAL_MD).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / FINAL_MD).write_text("\n".join(lines), encoding="utf-8")
    return final


def run_verification(repo_root: Path) -> dict[str, Any]:
    commands = {
        "stage3_tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_stage3*.py"],
        "research_tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_research*.py"],
        "readiness": ["powershell", "-ExecutionPolicy", "Bypass", "-File", "scripts/run_agent_readiness_checks.ps1"],
        "full_baseline": [sys.executable, "scripts/verify_test_baseline.py", "--run"],
    }
    output = {}
    for name, command in commands.items():
        completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, timeout=180)
        combined = completed.stdout + completed.stderr
        match = re.search(r"Ran (\d+) tests", combined)
        if completed.returncode != 0:
            raise TemporalProfileError("verification_failed", f"{name}: {combined[-2000:]}")
        item = {"passed": True, "returncode": completed.returncode, "test_count": int(match.group(1)) if match else None}
        if name == "full_baseline":
            baseline = json.loads(completed.stdout)
            item.update({"python_known_failures": len(baseline["python_failures"]), "node_known_failures": len(baseline["node_failures"]), "new_regressions": len(baseline["errors"])})
        output[name] = item
    output["no_new_test_baseline_regressions"] = True
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    if sha256_file(repo_root / STRATEGY).lower() != BASE_STRATEGY_SHA256:
        raise TemporalProfileError("base_strategy_hash_drift", STRATEGY.as_posix())
    audit = audit_sources(repo_root)
    write_audit(repo_root, audit)
    existing = load_simple_yaml(repo_root / POLICY_PATH) if (repo_root / POLICY_PATH).exists() else None
    frozen_at = existing["frozen_at"] if existing else utc_now()
    policy = build_policy(frozen_at)
    immutable_manifest(repo_root / POLICY_PATH, policy, "policy_sha256")
    slices = build_slices(frozen_at)
    immutable_manifest(repo_root / SLICES_PATH, slices, "slices_sha256")
    slices = load_simple_yaml(repo_root / SLICES_PATH)
    snapshots, profiles = {}, {}
    for item in slices["slices"]:
        snapshots[item["slice_id"]] = create_slice_snapshot(repo_root, item)
        profiles[item["slice_id"]] = build_market_profile(repo_root, item)
    campaign = build_campaign(slices)
    immutable_manifest(repo_root / CAMPAIGN_PATH, campaign, "campaign_sha256")
    campaign = load_simple_yaml(repo_root / CAMPAIGN_PATH)
    results = []
    for item in slices["slices"]:
        runs = []
        for run_id in ("RUN-A", "RUN-B"):
            manifest = execution_manifest(repo_root, campaign, item, run_id)
            run_dir = repo_root / RESULT_ROOT / str(item["slice_number"]) / run_id
            if not (run_dir / "temporal-worker-result.json").exists():
                launch_worker(repo_root, manifest)
            runs.append(summarize_run(repo_root, item, run_id, profiles[item["slice_id"]]))
        reproducibility = compare_runs(runs[0], runs[1])
        results.append({"slice_id": item["slice_id"], "slice_number": item["slice_number"], "dataset_id": item["dataset_id"], "dataset_manifest_sha256": snapshots[item["slice_id"]]["manifest_sha256"], "market_profile": profiles[item["slice_id"]], "market_profile_sha256": sha256_file(repo_root / PROFILE_ROOT / f"{item['slice_id']}-market-profile.json"), "run_a": runs[0], "run_b": runs[1], "reproducibility": reproducibility})
    comparison = build_comparison(results)
    dump_json(repo_root / COMPARISON_PATH, comparison)
    timestamp = utc_now()
    record_registry(repo_root, slices, results, comparison, timestamp)
    final = write_final_report(repo_root, audit, slices, results, comparison, timestamp)
    if args.verify:
        final["verification"] = run_verification(repo_root)
        final["final_sha256"] = self_hash(final, "final_sha256")
        dump_json(repo_root / FINAL_JSON, final)
        with (repo_root / FINAL_MD).open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Verification\n\n"
                f"- Stage 3 tests: `{final['verification']['stage3_tests']['test_count']}` passed.\n"
                f"- Research tests: `{final['verification']['research_tests']['test_count']}` passed.\n"
                "- Readiness guards: `passed`.\n"
                f"- Full baseline: no new regressions; known Python failures `{final['verification']['full_baseline']['python_known_failures']}`, known Node failures `{final['verification']['full_baseline']['node_known_failures']}`.\n"
            )
    print(json.dumps({"status": final["status"], "classification": final["classification"], "recommendation": final["recommendation"], "slice_count": final["slice_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
