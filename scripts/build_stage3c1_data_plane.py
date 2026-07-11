#!/usr/bin/env python3
"""Build Stage 3C.1 Futures Development / Validation data plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from profile_futures_market_regimes import build_profile, write_markdown as write_profile_markdown
from research_control import load_campaign, utc_now
from run_experiment import artifact_hashes, dump_json, dump_manifest, git_sha, repo_rel, sha256_file
from run_offline_backtest import run_offline_backtest


SOURCE_DATASET_ID = "demo-btc-usdt-usdt-futures-acceptance-20260329-20260412"
SOURCE_DATASET = Path("research/data/snapshots") / SOURCE_DATASET_ID
SPLIT_ID = "futures-dev-validation-v1"
DEV_DATASET_ID = "futures-dev-btc-usdt-usdt-20260301-20260328-v1"
VAL_DATASET_ID = "futures-validation-btc-usdt-usdt-20260503-20260628-v1"
PAIR = "BTC/USDT:USDT"
PAIR_STEM = "BTC_USDT_USDT"
EXCHANGE_SNAPSHOT = Path("research/exchange_snapshots/binance-usdm-futures-2025-8-demo")


SPLIT = {
    "development_start": "2026-03-01T00:00:00Z",
    "development_end": "2026-03-28T23:00:00Z",
    "development_evaluation_start": "2026-03-10T00:00:00Z",
    "embargo_start": "2026-03-29T00:00:00Z",
    "embargo_end": "2026-05-02T23:00:00Z",
    "validation_warmup_start": "2026-05-03T00:00:00Z",
    "validation_evaluation_start": "2026-06-06T00:00:00Z",
    "validation_evaluation_end": "2026-06-28T16:00:00Z",
}

FILES = {
    "futures_1h": ("futures", "1h", "BTC_USDT_USDT-1h-futures.feather", "1h"),
    "futures_4h": ("futures", "4h", "BTC_USDT_USDT-4h-futures.feather", "4h"),
    "mark_8h": ("mark", "8h", "BTC_USDT_USDT-8h-mark.feather", "8h"),
    "funding_rate_8h": ("funding_rate", "8h", "BTC_USDT_USDT-8h-funding_rate.feather", "8h"),
}


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value.replace("Z", "+00:00"))


def read_yamlish(path: Path) -> dict[str, Any]:
    from research_control import load_simple_yaml

    return load_simple_yaml(path)


def read_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_feather(path)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    return frame.sort_values("date").reset_index(drop=True)


def write_frame(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.reset_index(drop=True).to_feather(path, compression="lz4", compression_level=9)


def file_record(repo_root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": repo_rel(repo_root, path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def aggregate_hash(entries: list[dict[str, Any]]) -> str:
    return stable_hash([{k: item[k] for k in ("path", "bytes", "sha256")} for item in entries])


def interval_hours(timeframe: str) -> int:
    if timeframe.endswith("h"):
        return int(timeframe[:-1])
    raise ValueError(f"unsupported timeframe: {timeframe}")


def validate_frame(frame: pd.DataFrame, timeframe: str, candle_type: str) -> dict[str, Any]:
    issues = []
    dates = frame["date"]
    if not dates.is_monotonic_increasing:
        issues.append("timestamps_not_monotonic")
    duplicates = int(dates.duplicated().sum())
    if duplicates:
        issues.append("duplicate_timestamps")
    expected = pd.to_timedelta(interval_hours(timeframe), unit="h")
    diffs = dates.diff().dropna()
    tolerance = pd.to_timedelta(1 if candle_type == "funding_rate" else 0, unit="s")
    missing_intervals = int(((diffs - expected).abs() > tolerance).sum())
    if missing_intervals:
        issues.append("missing_or_irregular_candles")
    if candle_type in {"futures", "mark"}:
        bad_ohlc = int(((frame["high"] < frame[["open", "close"]].max(axis=1)) | (frame["low"] > frame[["open", "close"]].min(axis=1))).sum())
        if bad_ohlc:
            issues.append("invalid_ohlc")
    else:
        bad_ohlc = 0
    negative_volume = int((frame["volume"].astype(float) < 0).sum()) if "volume" in frame else 0
    if negative_volume:
        issues.append("negative_volume")
    return {
        "ok": not issues,
        "issues": issues,
        "rows": int(len(frame)),
        "start": str(dates.min()) if not frame.empty else None,
        "end": str(dates.max()) if not frame.empty else None,
        "duplicates": duplicates,
        "missing_intervals": missing_intervals,
        "invalid_ohlc": bad_ohlc,
        "negative_volume": negative_volume,
        "timezone": "UTC",
        "format": "feather",
    }


def source_files(repo_root: Path) -> dict[str, Path]:
    root = repo_root / SOURCE_DATASET / "data" / "futures"
    return {key: root / filename for key, (_ctype, _tf, filename, _interval) in FILES.items()}


def inventory(repo_root: Path) -> dict[str, Any]:
    files = {}
    for key, path in source_files(repo_root).items():
        candle_type, timeframe, _name, _interval = FILES[key]
        frame = read_frame(path)
        files[key] = {
            **file_record(repo_root, path),
            "candle_type": candle_type,
            "timeframe": timeframe,
            "validation": validate_frame(frame, timeframe, candle_type),
            "columns": list(frame.columns),
        }
    acceptance_start = ts("2026-03-29T00:00:00Z")
    acceptance_end = ts("2026-04-12T00:00:00Z")
    return {
        "schema_version": "stage3c1-data-inventory-v1",
        "created_at": utc_now(),
        "source_dataset_id": SOURCE_DATASET_ID,
        "source_dataset_manifest": repo_rel(repo_root, repo_root / SOURCE_DATASET / "manifest.yaml"),
        "exchange": "binance",
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "pairs": [PAIR],
        "timeframes": ["1h", "4h", "8h"],
        "candle_types": ["futures", "mark", "funding_rate"],
        "files": files,
        "acceptance_fixture_overlap": {
            "fixture_timerange": "20260329-20260412",
            "overlaps_development": False,
            "overlaps_validation_evaluation": False,
            "placed_in_embargo": True,
        },
        "development_candidate": {"start": SPLIT["development_start"], "end": SPLIT["development_end"]},
        "validation_candidate": {"warmup_start": SPLIT["validation_warmup_start"], "evaluation_start": SPLIT["validation_evaluation_start"], "evaluation_end": SPLIT["validation_evaluation_end"]},
        "unsuitable_assets": ["spot dataset demo-btc-usdt-1h-202401", "2024 futures demo lacking 4h informative coverage"],
    }


def write_inventory_markdown(repo_root: Path, inv: dict[str, Any]) -> Path:
    path = repo_root / "reports" / "audits" / "stage3c1_research_data_inventory.md"
    lines = [
        "# Stage 3C.1 Research Data Inventory",
        "",
        f"- Source dataset: `{inv['source_dataset_id']}`",
        "- Strategy results used for split selection: `false`",
        "- Acceptance fixture is not used for ranking and is placed in the embargo interval.",
        "",
        "## Files",
        "",
        "| key | candle type | timeframe | rows | start | end | bytes | sha256 | issues |",
        "|---|---|---|---:|---|---|---:|---|---|",
    ]
    for key, item in inv["files"].items():
        validation = item["validation"]
        lines.append(
            f"| `{key}` | `{item['candle_type']}` | `{item['timeframe']}` | {validation['rows']} | `{validation['start']}` | `{validation['end']}` | {item['bytes']} | `{item['sha256']}` | `{', '.join(validation['issues']) or 'none'}` |"
        )
    lines.extend(
        [
            "",
            "## Use Assessment",
            "",
            "- Development: allowed from the early source interval after deterministic time split.",
            "- Validation: allowed from the later source interval after embargo and warm-up separation.",
            "- Acceptance fixture: execution contract only, not ranking.",
            "- Unsuitable: spot data and incomplete futures demo data.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_final_markdown(repo_root: Path, final: dict[str, Any]) -> Path:
    path = repo_root / "reports" / "audits" / "stage3c1_research_data_plane.md"
    dev = final["development_dataset"]
    val = final["validation_dataset"]
    probes = final["data_readiness_probe"]
    lines = [
        "# Stage 3C.1 Research Data Plane",
        "",
        f"- Campaign: `{final['campaign_id']}`",
        f"- Complete: `{str(final['stage3c1_complete']).lower()}`",
        "- Strategy modified: `false`",
        "- Candidate created: `false`",
        "- Hyperopt run: `false`",
        "- Holdout accessed: `false`",
        "- Quality evaluation performed: `false`",
        "",
        "## Split",
        "",
        f"- Split manifest: `{final['split']}`",
        f"- Development dataset: `{dev['dataset_id']}`",
        f"- Development aggregate: `{dev['aggregate_sha256']}`",
        f"- Validation dataset: `{val['dataset_id']}`",
        f"- Validation aggregate: `{val['aggregate_sha256']}`",
        "- Acceptance fixture timerange `20260329-20260412` is inside embargo and is not used for ranking.",
        "",
        "## Governance",
        "",
        f"- Usage policy: `{final['usage_policy']}`",
        f"- Validation access policy: `{final['validation_access_policy']}`",
        f"- Pollution model: `{final['pollution_model']}`",
        f"- Evaluation schema reserved for Stage 3C.2: `{final['evaluation_schema']}`",
        f"- Lineage database: `{final['lineage_db']}`",
        "",
        "## Readiness Probes",
        "",
        f"- Purpose: `{probes['purpose']}`",
        f"- Quality verdict: `{probes['quality_verdict']}`",
        f"- Development probe status: `{probes['development']['runner_result'].get('status')}`",
        f"- Validation probe status: `{probes['validation']['runner_result'].get('status')}`",
        "",
        "These probes only verify that the sealed data can be consumed by the offline runner. They do not rank or approve strategy quality.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def subset_frame(path: Path, start: str, end: str) -> pd.DataFrame:
    frame = read_frame(path)
    return frame[(frame["date"] >= ts(start)) & (frame["date"] <= ts(end))].copy()


def build_snapshot(repo_root: Path, dataset_id: str, intended_use: str, data_start: str, data_end: str, eval_start: str, eval_end: str) -> dict[str, Any]:
    snapshot_root = repo_root / "research" / "data" / "snapshots" / dataset_id
    data_root = snapshot_root / "data" / "futures"
    if snapshot_root.exists():
        raise RuntimeError(f"snapshot already exists: {snapshot_root}")
    source = source_files(repo_root)
    entries = []
    coverage = []
    validations = {}
    for key, src in source.items():
        candle_type, timeframe, filename, _interval = FILES[key]
        frame = subset_frame(src, data_start, data_end)
        dst = data_root / filename
        write_frame(frame, dst)
        record = file_record(repo_root, dst)
        entries.append(record)
        validation = validate_frame(frame, timeframe, candle_type)
        validations[key] = validation
        coverage.append({"file": filename, "rows": validation["rows"], "start": validation["start"], "end": validation["end"], "candle_type": candle_type, "timeframe": timeframe})
    exchange_manifest = read_yamlish(repo_root / EXCHANGE_SNAPSHOT / "manifest.yaml")
    aggregate = aggregate_hash(entries)
    manifest = {
        "schema_version": "stage3c1-dataset-snapshot-v1",
        "dataset_id": dataset_id,
        "parent_dataset_id": SOURCE_DATASET_ID,
        "exchange": "binance",
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "pairs": [PAIR],
        "timeframes": ["1h", "4h", "8h"],
        "candle_types": ["futures", "mark", "funding_rate"],
        "data_path": repo_rel(repo_root, snapshot_root / "data"),
        "files": entries,
        "coverage": coverage,
        "validation_checks": validations,
        "aggregate_sha256": aggregate,
        "start": data_start,
        "end": data_end,
        "warmup_range": {"start": data_start, "end": pd.Timestamp(eval_start).tz_convert("UTC").isoformat() if pd.Timestamp(eval_start).tzinfo else eval_start},
        "evaluation_range": {"start": eval_start, "end": eval_end},
        "funding_model": "sealed_dataset",
        "pair_contract_metadata": {"exchange_snapshot_id": exchange_manifest.get("snapshot_id"), "aggregate_sha256": exchange_manifest.get("aggregate_sha256")},
        "leverage_tier_artifact": exchange_manifest.get("leverage_tier_artifact"),
        "source": "local sealed Binance USD-M futures monthly data, deterministic time subset",
        "provisioning_command": f"python scripts/build_stage3c1_data_plane.py --campaign research/campaigns/active/stage3c1-research-data-plane.yaml",
        "created_at": utc_now(),
        "campaign_mutable": False,
        "network_accessed_during_campaign": False,
        "sealed": True,
        "sealed_at": utc_now(),
        "sealed_by": "scripts/build_stage3c1_data_plane.py",
        "intended_use": intended_use,
        "agent_visibility": "full" if intended_use == "development" else "controlled",
        "suitable_for_strategy_iteration": intended_use == "development",
        "suitable_for_champion_promotion": False,
        "suitable_for_stage_promotion": intended_use == "validation",
        "execution_baseline_only": False,
    }
    dump_manifest(snapshot_root / "manifest.yaml", manifest)
    return manifest


def write_policy_files(repo_root: Path) -> dict[str, str]:
    usage_policy = {
        "schema_version": "stage3c1-data-usage-policy-v1",
        "execution_certification_fixture": {
            "allowed_uses": ["strategy_load", "futures_long_short_execution", "offline_adapter", "run_a_run_b", "candidate_engineering_validation"],
            "prohibited_uses": ["strategy_ranking", "parameter_selection", "profit_quality_judgment", "champion_promotion", "hyperopt"],
        },
        "development_dataset": {
            "allowed_uses": ["candidate_development", "failure_analysis", "hypothesis_validation", "parameter_prescreen", "structural_strategy_experiment"],
            "agent_visibility": "full",
        },
        "validation_dataset": {
            "allowed_uses": ["stage_evaluation_of_frozen_development_candidate"],
            "prohibited_uses": ["per_small_experiment_access", "same_candidate_adjustment_after_result", "unlimited_trade_detail_exposure", "development_loop_optimization"],
            "agent_visibility": "controlled",
        },
        "sealed_holdout": {
            "defined_only": True,
            "actual_path_created": False,
            "default_access": "blocked",
        },
    }
    validation_access = {
        "schema_version": "stage3c1-validation-access-policy-v1",
        "validation_dataset_id": VAL_DATASET_ID,
        "max_evaluations_per_campaign": 1,
        "max_evaluations_per_candidate": 1,
        "full_trade_details_exposed": False,
        "aggregate_metrics_returned": True,
        "access_event_logging": "research.registry.validation_access_events",
        "contamination_status_on_access": "validation_evaluated",
        "allowed_evaluator": "validation_evaluator",
        "prohibited_agent_roles": ["candidate_generator", "hypothesis_generator", "mutation_agent"],
        "candidate_must_be_frozen": True,
        "source_change_after_validation_requires_new_candidate_identity": True,
    }
    pollution = {
        "schema_version": "stage3c1-pollution-state-model-v1",
        "states": ["clean", "development_exposed", "validation_evaluated", "validation_contaminated", "holdout_evaluated", "holdout_contaminated"],
        "rules": [
            "development use does not contaminate",
            "validation run marks candidate validation_evaluated",
            "modifying same candidate after validation marks candidate and derivatives validation_contaminated",
            "contaminated candidates cannot claim independent validation",
            "holdout paths are not created in Stage 3C.1",
        ],
    }
    result_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Stage 3C.2 reserved evaluation result schema",
        "type": "object",
        "required": ["dataset_id", "dataset_aggregate_hash", "contamination_status", "metrics"],
        "properties": {
            "dataset_id": {"type": "string"},
            "dataset_aggregate_hash": {"type": "string"},
            "contamination_status": {"type": "string"},
            "metrics": {
                "type": "object",
                "properties": {
                    "total_trades": {"type": "number"},
                    "long_trades": {"type": "number"},
                    "short_trades": {"type": "number"},
                    "total_return": {"type": "number"},
                    "max_drawdown": {"type": "number"},
                    "profit_factor": {"type": "number"},
                    "sharpe": {"type": "number"},
                    "sortino": {"type": "number"},
                    "calmar": {"type": "number"},
                    "average_duration": {"type": "string"},
                    "worst_window": {"type": "object"},
                    "pair_level_results": {"type": "object"},
                    "regime_level_results": {"type": "object"},
                    "funding_costs": {"type": "number"},
                    "fee_stress": {"type": "object"},
                    "normalized_trade_hash": {"type": "string"},
                },
            },
        },
    }
    paths = {
        "usage_policy": repo_root / "research" / "data" / "data-usage-policy.yaml",
        "validation_access": repo_root / "research" / "data" / "validation-access-policy.yaml",
        "pollution_model": repo_root / "research" / "data" / "pollution-state-model.yaml",
        "evaluation_schema": repo_root / "research" / "data" / "evaluation-result.schema.json",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(paths["usage_policy"], usage_policy)
    dump_manifest(paths["validation_access"], validation_access)
    dump_manifest(paths["pollution_model"], pollution)
    dump_json(paths["evaluation_schema"], result_schema)
    return {key: repo_rel(repo_root, path) for key, path in paths.items()}


def write_split(repo_root: Path) -> dict[str, Any]:
    split = {
        "schema_version": "stage3c1-dev-validation-split-v1",
        "split_id": SPLIT_ID,
        "pair": PAIR,
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "timeframes": ["1h", "4h", "8h"],
        "development_start": SPLIT["development_start"],
        "development_end": SPLIT["development_end"],
        "development_evaluation_start": SPLIT["development_evaluation_start"],
        "embargo_start": SPLIT["embargo_start"],
        "embargo_end": SPLIT["embargo_end"],
        "validation_warmup_start": SPLIT["validation_warmup_start"],
        "validation_evaluation_start": SPLIT["validation_evaluation_start"],
        "validation_evaluation_end": SPLIT["validation_evaluation_end"],
        "development_dataset_id": DEV_DATASET_ID,
        "validation_dataset_id": VAL_DATASET_ID,
        "data_uses": {"development": "candidate iteration", "validation": "controlled frozen-candidate evaluation"},
        "selection_basis": "deterministic chronological split from complete local data coverage; no strategy returns, trades, Sharpe, or entry/exit results used",
        "embargo_rule": "35 calendar days covers 200x4h informative warm-up plus cross-boundary holding buffer",
        "created_at": utc_now(),
    }
    path = repo_root / "research" / "data" / "splits" / f"{SPLIT_ID}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(path, split)
    return split


def write_profile(repo_root: Path) -> dict[str, str]:
    source = source_files(repo_root)
    windows = {
        "development": {"start": SPLIT["development_start"], "end": SPLIT["development_end"]},
        "embargo": {"start": SPLIT["embargo_start"], "end": SPLIT["embargo_end"]},
        "validation_evaluation": {"start": SPLIT["validation_evaluation_start"], "end": SPLIT["validation_evaluation_end"]},
    }
    profile = build_profile(SPLIT_ID, source["futures_1h"], source["funding_rate_8h"], windows)
    out_json = repo_root / "research" / "data" / "profiles" / f"{SPLIT_ID}-market-profile.json"
    out_md = repo_root / "research" / "data" / "profiles" / f"{SPLIT_ID}-market-profile.md"
    dump_json(out_json, profile)
    write_profile_markdown(out_md, profile)
    return {"json": repo_rel(repo_root, out_json), "markdown": repo_rel(repo_root, out_md)}


def init_lineage(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS datasets (
          dataset_id TEXT PRIMARY KEY,
          parent_dataset_id TEXT,
          intended_use TEXT NOT NULL,
          sealed_status TEXT NOT NULL,
          aggregate_sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS data_lineage_files (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          dataset_id TEXT NOT NULL,
          source_path TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,
          output_path TEXT NOT NULL,
          output_sha256 TEXT NOT NULL,
          candle_type TEXT NOT NULL,
          timeframe TEXT NOT NULL,
          source_start TEXT,
          source_end TEXT,
          selected_start TEXT,
          selected_end TEXT,
          transformation TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS validation_access_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          campaign_id TEXT NOT NULL,
          candidate_id TEXT NOT NULL,
          dataset_id TEXT NOT NULL,
          access_role TEXT NOT NULL,
          contamination_status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          reason TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS contamination_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          candidate_id TEXT NOT NULL,
          previous_status TEXT NOT NULL,
          new_status TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )


def record_lineage(repo_root: Path, manifests: list[dict[str, Any]]) -> str:
    db_path = repo_root / "research" / "data" / "data-lineage.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        init_lineage(conn)
        src = source_files(repo_root)
        source_frames = {key: read_frame(path) for key, path in src.items()}
        for manifest in manifests:
            conn.execute(
                "INSERT OR REPLACE INTO datasets(dataset_id, parent_dataset_id, intended_use, sealed_status, aggregate_sha256, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (manifest["dataset_id"], manifest["parent_dataset_id"], manifest["intended_use"], "sealed" if manifest["sealed"] else "unsealed", manifest["aggregate_sha256"], manifest["created_at"]),
            )
            for record in manifest["files"]:
                filename = Path(record["path"]).name
                key = next(k for k, (_ctype, _tf, fname, _interval) in FILES.items() if fname == filename)
                ctype, timeframe, _fname, _interval = FILES[key]
                source_path = src[key]
                frame = source_frames[key]
                conn.execute(
                    """
                    INSERT INTO data_lineage_files(dataset_id, source_path, source_sha256, output_path, output_sha256,
                      candle_type, timeframe, source_start, source_end, selected_start, selected_end, transformation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest["dataset_id"],
                        repo_rel(repo_root, source_path),
                        sha256_file(source_path),
                        record["path"],
                        record["sha256"],
                        ctype,
                        timeframe,
                        str(frame["date"].min()),
                        str(frame["date"].max()),
                        manifest["start"],
                        manifest["end"],
                        "deterministic_time_subset_no_strategy_results",
                    ),
                )
        conn.commit()
    finally:
        conn.close()
    return repo_rel(repo_root, db_path)


def run_probe(repo_root: Path, campaign: dict, dataset_manifest: dict[str, Any], timerange: str, run_name: str) -> dict[str, Any]:
    probe_campaign = json.loads(json.dumps(campaign))
    probe_campaign["campaign_id"] = "stage3c1-research-data-plane"
    probe_campaign["fixed_backtest"]["strategy"] = "RegimeAwareV6"
    probe_campaign["fixed_backtest"]["strategy_file"] = "strategies/RegimeAwareV6.py"
    probe_campaign["fixed_backtest"]["strategy_path"] = "strategies"
    probe_campaign["fixed_backtest"]["dataset_id"] = dataset_manifest["dataset_id"]
    probe_campaign["fixed_backtest"]["dataset_manifest"] = f"research/data/snapshots/{dataset_manifest['dataset_id']}/manifest.yaml"
    probe_campaign["fixed_backtest"]["datadir"] = dataset_manifest["data_path"]
    probe_campaign["fixed_backtest"]["timerange"] = timerange
    probe_campaign["fixed_backtest"]["acceptance_gate"] = {}
    result = run_offline_backtest(repo_root, probe_campaign, dataset_manifest["dataset_id"], run_name, repo_root / probe_campaign["sealed_offline_backtest"]["exchange_snapshot"])
    run_dir = repo_root / "research" / "results" / "stage3c1-research-data-plane" / dataset_manifest["dataset_id"] / run_name
    report = {
        "purpose": "data_readiness_only",
        "quality_verdict": "not_evaluated",
        "dataset_id": dataset_manifest["dataset_id"],
        "timerange": timerange,
        "runner_result": result,
        "run_dir": repo_rel(repo_root, run_dir),
    }
    dump_json(run_dir / "data-readiness-probe-report.json", report)
    return report


def build_data_plane(repo_root: str | Path, campaign_path: str | Path) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    campaign = load_campaign(campaign_path)
    inv = inventory(repo_root)
    inventory_md = write_inventory_markdown(repo_root, inv)
    policies = write_policy_files(repo_root)
    split = write_split(repo_root)
    profile_paths = write_profile(repo_root)
    dev_manifest = build_snapshot(
        repo_root,
        DEV_DATASET_ID,
        "development",
        SPLIT["development_start"],
        SPLIT["development_end"],
        SPLIT["development_evaluation_start"],
        SPLIT["development_end"],
    )
    val_manifest = build_snapshot(
        repo_root,
        VAL_DATASET_ID,
        "validation",
        SPLIT["validation_warmup_start"],
        SPLIT["validation_evaluation_end"],
        SPLIT["validation_evaluation_start"],
        SPLIT["validation_evaluation_end"],
    )
    lineage_db = record_lineage(repo_root, [dev_manifest, val_manifest])
    dev_probe = run_probe(repo_root, campaign, dev_manifest, "20260310-20260329", "DEVELOPMENT-DATA-READINESS")
    val_probe = run_probe(repo_root, campaign, val_manifest, "20260606-20260629", "VALIDATION-DATA-READINESS")
    final = {
        "schema_version": "stage3c1-final-report-v1",
        "campaign_id": campaign["campaign_id"],
        "stage3c1_complete": True,
        "created_at": utc_now(),
        "git_sha": git_sha(repo_root),
        "strategy_modified": False,
        "candidate_created": False,
        "hyperopt_run": False,
        "holdout_accessed": False,
        "quality_evaluation_performed": False,
        "inventory_report": repo_rel(repo_root, inventory_md),
        "usage_policy": policies["usage_policy"],
        "validation_access_policy": policies["validation_access"],
        "pollution_model": policies["pollution_model"],
        "evaluation_schema": policies["evaluation_schema"],
        "split": repo_rel(repo_root, repo_root / "research" / "data" / "splits" / f"{SPLIT_ID}.yaml"),
        "market_profile": profile_paths,
        "development_dataset": {
            "dataset_id": DEV_DATASET_ID,
            "manifest": f"research/data/snapshots/{DEV_DATASET_ID}/manifest.yaml",
            "aggregate_sha256": dev_manifest["aggregate_sha256"],
            "sealed": dev_manifest["sealed"],
        },
        "validation_dataset": {
            "dataset_id": VAL_DATASET_ID,
            "manifest": f"research/data/snapshots/{VAL_DATASET_ID}/manifest.yaml",
            "aggregate_sha256": val_manifest["aggregate_sha256"],
            "sealed": val_manifest["sealed"],
        },
        "lineage_db": lineage_db,
        "data_readiness_probe": {
            "purpose": "data_readiness_only",
            "quality_verdict": "not_evaluated",
            "development": dev_probe,
            "validation": val_probe,
        },
    }
    out = repo_root / "research" / "results" / "stage3c1-research-data-plane" / "stage3c1-final-report.json"
    final["final_markdown_report"] = repo_rel(repo_root, write_final_markdown(repo_root, final))
    dump_json(out, final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Stage 3C.1 research data plane.")
    parser.add_argument("--campaign", default="research/campaigns/active/stage3c1-research-data-plane.yaml")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build_data_plane(Path.cwd(), args.campaign)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
