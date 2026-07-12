#!/usr/bin/env python3
"""Run the one human-approved ETH development-only cross-pair Campaign."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from research_director_common import fingerprint, load_document, open_director_registry, sha256_file, utc_now, write_json, write_yaml


PROPOSAL_ID = "eth-cross-pair-generalization-v1"
CAMPAIGN_ID = "stage4a-eth-cross-pair-generalization-v1"
DATASET_ID = "futures-dev-eth-usdt-usdt-20240101-20240830-v1"
PAIR = "ETH/USDT:USDT"
STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
CONSTITUTION_SHA256 = "ff0ca1b7f3aa4f7f0a7d6b893095ba618d1ecf50cf7044dfeb3152bd91826722"
POLICY_SHA256 = "ee4769e4c814e209e771c31fa35ff4d8c4719137fffe7291d3ae87d73c8e8b5e"
COMPILED_FINGERPRINT = "12338df116617891e268d88bebff193adecb80847a8070615eb37a0f6b6bdc3b"
START = pd.Timestamp("2024-01-01T00:00:00Z")
END_1H = pd.Timestamp("2024-08-29T15:00:00Z")
END_4H = pd.Timestamp("2024-08-29T12:00:00Z")
END_8H = pd.Timestamp("2024-08-29T08:00:00Z")


def dated(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], utc=True)
    return result.sort_values("date").drop_duplicates("date").reset_index(drop=True)


def slice_exact(frame: pd.DataFrame, end: pd.Timestamp, rows: int, cadence: str) -> pd.DataFrame:
    result = dated(frame)
    result = result[(result["date"] >= START) & (result["date"] <= end)].reset_index(drop=True)
    if len(result) != rows or result.iloc[0]["date"] != START or result.iloc[-1]["date"] != end:
        raise ValueError(f"coverage_mismatch:{cadence}:{len(result)}:{result.iloc[0]['date']}:{result.iloc[-1]['date']}")
    expected = pd.date_range(START, end, freq=cadence)
    if list(result["date"]) != list(expected):
        raise ValueError(f"cadence_or_gap_mismatch:{cadence}")
    return result


def resample_mark_8h(frame: pd.DataFrame) -> pd.DataFrame:
    source = dated(frame).set_index("date")
    clipped = source[(source.index >= START) & (source.index <= END_1H)]
    result = clipped.resample("8h", origin=START, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna().reset_index()
    return slice_exact(result, END_8H, 725, "8h")


def coverage(frame: pd.DataFrame, candle_type: str, timeframe: str) -> dict[str, Any]:
    dates = pd.to_datetime(frame["date"], utc=True)
    return {
        "rows": len(frame),
        "start": dates.iloc[0].isoformat().replace("+00:00", "Z"),
        "end": dates.iloc[-1].isoformat().replace("+00:00", "Z"),
        "duplicates": int(dates.duplicated().sum()),
        "missing_intervals": 0,
        "timezone": "UTC",
        "format": "feather",
        "candle_type": candle_type,
        "timeframe": timeframe,
        "ok": True,
    }


def build_snapshot(repo: Path, source_dir: Path) -> dict[str, Any]:
    source_names = {
        "futures_1h": "ETH_USDT_USDT-1h-futures.feather",
        "futures_4h": "ETH_USDT_USDT-4h-futures.feather",
        "mark_source_1h": "ETH_USDT_USDT-1h-mark.feather",
        "funding_source": "ETH_USDT_USDT-1h-funding_rate.feather",
    }
    source_paths = {key: source_dir / name for key, name in source_names.items()}
    missing = [str(path) for path in source_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing_source_files:" + ",".join(missing))
    frames = {
        "ETH_USDT_USDT-1h-futures.feather": slice_exact(pd.read_feather(source_paths["futures_1h"]), END_1H, 5800, "1h"),
        "ETH_USDT_USDT-4h-futures.feather": slice_exact(pd.read_feather(source_paths["futures_4h"]), END_4H, 1450, "4h"),
        "ETH_USDT_USDT-8h-mark.feather": resample_mark_8h(pd.read_feather(source_paths["mark_source_1h"])),
        "ETH_USDT_USDT-8h-funding_rate.feather": slice_exact(pd.read_feather(source_paths["funding_source"]), END_8H, 725, "8h"),
    }
    snapshot_root = repo / "research/data/snapshots" / DATASET_ID
    data_root = snapshot_root / "data/futures"
    data_root.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_feather(data_root / name)
    file_specs = []
    coverage_rows = []
    types = {
        "ETH_USDT_USDT-1h-futures.feather": ("futures", "1h"),
        "ETH_USDT_USDT-4h-futures.feather": ("futures", "4h"),
        "ETH_USDT_USDT-8h-mark.feather": ("mark", "8h"),
        "ETH_USDT_USDT-8h-funding_rate.feather": ("funding_rate", "8h"),
    }
    for name, frame in frames.items():
        path = data_root / name
        rel = path.relative_to(repo).as_posix()
        file_specs.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        candle_type, timeframe = types[name]
        coverage_rows.append({"file": name, **coverage(frame, candle_type, timeframe)})
    manifest = {
        "schema_version": "cross-pair-development-snapshot-v1",
        "dataset_id": DATASET_ID,
        "parent_boundary_dataset": "futures-dev-btc-usdt-usdt-20240101-20240830-v2",
        "exchange": "binance",
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "pairs": [PAIR],
        "timeframes": ["1h", "4h", "8h"],
        "candle_types": ["futures", "mark", "funding_rate"],
        "data_path": f"research/data/snapshots/{DATASET_ID}/data",
        "files": file_specs,
        "coverage": coverage_rows,
        "aggregate_sha256": fingerprint(file_specs),
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-08-29T15:00:00Z",
        "warmup_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-02-03T07:00:00Z"},
        "evaluation_range": {"start": "2024-02-03T08:00:00Z", "end": "2024-08-29T15:00:00Z", "main_1h_candles": 5000},
        "source_lineage": [{"source_file": name, "sha256": sha256_file(path)} for name, path in source_paths.items()],
        "source_access": "existing_local_public_market_cache_read_only",
        "network_accessed_during_campaign": False,
        "intended_use": "development_descriptive_cross_pair_generalization_only",
        "validation_or_holdout": False,
        "suitable_for_strategy_iteration": False,
        "suitable_for_strategy_ranking": False,
        "suitable_for_stage_promotion": False,
        "campaign_mutable": False,
        "sealed": True,
        "sealed_at": utc_now(),
        "sealed_by": "scripts/run_eth_cross_pair_generalization_campaign.py",
    }
    write_yaml(snapshot_root / "manifest.yaml", manifest)
    return manifest


def validate_authority(repo: Path) -> dict[str, Any]:
    approval = load_document(repo / "research/governance/approvals/eth-cross-pair-generalization-v1-approval.json")
    authorization = load_document(repo / "research/director/compiled/eth-cross-pair-generalization-v1/execution-authorization.json")
    campaign = load_document(repo / "research/director/compiled/eth-cross-pair-generalization-v1/campaign.yaml")
    checks = {
        "human_approval": approval.get("approval_status") == "approved" and approval.get("approver_type") == "human_user",
        "pair": approval.get("scope", {}).get("pair") == PAIR,
        "timeframe": approval.get("scope", {}).get("timeframe") == "1h",
        "constitution": sha256_file(repo / "research/governance/research-constitution.yaml") == CONSTITUTION_SHA256 == approval.get("constitution_sha256"),
        "policy_unchanged": sha256_file(repo / "research/evaluation/evaluation-policy.yaml") == POLICY_SHA256,
        "strategy_unchanged": sha256_file(repo / "strategies/RegimeAwareV6.py") == STRATEGY_SHA256,
        "compiled_fingerprint": campaign.get("campaign_fingerprint") == authorization.get("approved_compiled_fingerprint") == COMPILED_FINGERPRINT,
        "execution_authorized": authorization.get("execution_authorized") is True,
        "protected_access_zero": authorization.get("validation_accesses_authorized") == authorization.get("holdout_accesses_authorized") == 0,
        "no_mutation_or_search": not any(authorization.get(key) for key in ("strategy_mutation_authorized", "candidate_creation_authorized", "hyperopt_authorized")),
    }
    if not all(checks.values()):
        raise ValueError("authority_validation_failed:" + json.dumps(checks, sort_keys=True))
    return checks


def execution_spec(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": CAMPAIGN_ID,
        "fixed_backtest": {
            "strategy": "RegimeAwareV6",
            "strategy_file": "strategies/RegimeAwareV6.py",
            "strategy_path": "strategies",
            "config": "research/runtime/demo-futures-backtest-config.json",
            "dataset_id": DATASET_ID,
            "dataset_manifest": f"research/data/snapshots/{DATASET_ID}/manifest.yaml",
            "datadir": manifest["data_path"],
            "timerange": "20240203-20240830",
            "timeframe": "1h",
            "pairs": [PAIR],
            "fee": "0.0004",
            "acceptance_gate": {},
        },
    }


def run_worker(repo: Path, spec_path: Path, run_id: str) -> int:
    from run_offline_backtest import run_offline_backtest

    spec = load_document(spec_path)
    result = run_offline_backtest(repo, spec, 1, run_id, repo / "research/exchange_snapshots/binance-usdm-futures-2025-8-demo")
    print(json.dumps({"pid": os.getpid(), **result}, sort_keys=True))
    return 0 if result["status"] in {"accepted", "rejected"} else 1


def run_fresh(repo: Path, spec_path: Path, run_id: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", "--execution-spec", str(spec_path), "--run-id", run_id],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"fresh_process_run_failed:{run_id}:{completed.stderr}:{completed.stdout}")
    return json.loads(completed.stdout.strip().splitlines()[-1])


def metric_summary(repo: Path, result: dict[str, Any]) -> dict[str, Any]:
    report_path = repo / result["report_path"]
    runner_report = load_document(report_path)
    metrics = load_document(report_path.parent / runner_report["metrics_path"])
    normalized = metrics.get("normalized") or {}
    selected = {key: normalized.get(key) for key in ("total_trades", "closed_trade_count", "long_trade_count", "short_trade_count", "total_profit", "total_profit_pct", "profit_factor", "max_drawdown", "winrate", "funding_fees")}
    return {"pid": result["pid"], "status": result["status"], "report_path": result["report_path"], "core_metrics_signature": runner_report["core_metrics_signature"], "network_attempts": runner_report["network_attempts"], "metrics": selected}


def record_registry(repo: Path, result: dict[str, Any], artifact_paths: list[str]) -> None:
    approval = load_document(repo / "research/governance/approvals/eth-cross-pair-generalization-v1-approval.json")
    authorization = load_document(repo / "research/director/compiled/eth-cross-pair-generalization-v1/execution-authorization.json")
    proposal = load_document(repo / "research/director/proposals/eth-cross-pair-generalization-v1.json")
    completed_at = utc_now()
    run_id = "eth-cross-pair-generalization-v1-run"
    connection = open_director_registry(repo / "research/registry/stage4a-director.db")
    connection.execute(
        "INSERT OR REPLACE INTO proposal_selection_events(proposal_id, proposal_fingerprint, approval_status, approver_type, approved_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (PROPOSAL_ID, proposal["semantic_fingerprint"], "approved", "human_user", approval["approved_at"], json.dumps(approval, sort_keys=True)),
    )
    connection.execute(
        "INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id, campaign_id, approved_compiled_fingerprint, proposal_id, execution_authorized, payload_json, authorized_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (authorization["authorization_id"], CAMPAIGN_ID, COMPILED_FINGERPRINT, PROPOSAL_ID, 1, json.dumps(authorization, sort_keys=True), approval["approved_at"]),
    )
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs(run_id, campaign_id, proposal_id, status, result_code, campaign_executed, candidate_created, strategy_modified, validation_accesses, holdout_accesses, payload_json, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, CAMPAIGN_ID, PROPOSAL_ID, "completed", result["status"], 1, 0, 0, 0, 0, json.dumps(result, sort_keys=True), completed_at),
    )
    for path in artifact_paths:
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets(asset_id, run_id, artifact_type, path, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"{run_id}:{path}", run_id, "campaign_evidence", path, sha256_file(repo / path), completed_at),
        )
    connection.commit()
    connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--execution-spec")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    if args.worker:
        return run_worker(repo, Path(args.execution_spec), args.run_id)
    if not args.source_dir:
        parser.error("--source-dir is required")
    checks = validate_authority(repo)
    manifest = build_snapshot(repo, Path(args.source_dir).resolve())
    output_dir = repo / "research/director/compiled/eth-cross-pair-generalization-v1/execution"
    analysis_dir = repo / "research/analysis/eth-cross-pair-generalization"
    report_dir = repo / "reports/audits/eth-cross-pair-generalization"
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    spec = execution_spec(manifest)
    spec_path = output_dir / "execution-spec.json"
    write_json(spec_path, spec)
    raw_a = run_fresh(repo, spec_path, "ETH-GENERALIZATION-RUN-A-RETRY1")
    raw_b = run_fresh(repo, spec_path, "ETH-GENERALIZATION-RUN-B")
    run_a, run_b = metric_summary(repo, raw_a), metric_summary(repo, raw_b)
    reproducible = run_a["pid"] != run_b["pid"] and run_a["core_metrics_signature"] == run_b["core_metrics_signature"] and run_a["metrics"] == run_b["metrics"]
    if not reproducible:
        raise RuntimeError("run_reproducibility_failure")
    btc = load_document(repo / "research/data/provisioning/stage3c2p-development-probe.json").get("baseline") or {}
    comparison = {
        "schema_version": "eth-cross-pair-run-comparison-v1",
        "proposal_id": PROPOSAL_ID,
        "campaign_id": CAMPAIGN_ID,
        "pair": PAIR,
        "timeframe": "1h",
        "dataset_id": DATASET_ID,
        "dataset_aggregate_sha256": manifest["aggregate_sha256"],
        "run_a": run_a,
        "run_b": run_b,
        "distinct_fresh_processes": run_a["pid"] != run_b["pid"],
        "reproducible": reproducible,
        "btc_reference": {"dataset_id": "futures-dev-btc-usdt-usdt-20240101-20240830-v2", "metrics": btc.get("metrics"), "total_trades": btc.get("total_trades")},
        "formal_policy_gate_applied": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    write_json(analysis_dir / "run-comparison.json", comparison)
    eth_trades = run_a["metrics"].get("total_trades") or 0
    result_code = "reproducible_eth_trade_behavior_observed" if eth_trades > 0 else "reproducible_eth_zero_trade_behavior_observed"
    result = {
        "schema_version": "eth-cross-pair-generalization-result-v1",
        "status": result_code,
        "campaign_completed": True,
        "proposal_id": PROPOSAL_ID,
        "campaign_id": CAMPAIGN_ID,
        "campaign_fingerprint": COMPILED_FINGERPRINT,
        "authority_checks": checks,
        "dataset_id": DATASET_ID,
        "dataset_aggregate_sha256": manifest["aggregate_sha256"],
        "reproducible": reproducible,
        "eth_metrics": run_a["metrics"],
        "conclusion_scope": "descriptive_development_only",
        "cross_pair_execution_behavior_observed": eth_trades > 0,
        "cross_pair_generalization_proven": False,
        "profitability_claimed": False,
        "strategy_change_warranted": False,
        "candidate_created": False,
        "hyperopt_run": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "evaluation_policy_modified": False,
        "stage_promotion_allowed": False,
    }
    write_json(analysis_dir / "cross-pair-generalization-result.json", result)
    write_json(output_dir / "campaign-execution.json", {"schema_version": "eth-cross-pair-campaign-execution-v1", **result, "run_comparison": "research/analysis/eth-cross-pair-generalization/run-comparison.json"})
    write_json(report_dir / "eth-cross-pair-generalization-final-report.json", result)
    markdown = f"""# ETH Cross-pair Generalization Final Report

- Pair/timeframe: `{PAIR}` / `1h`
- Dataset: `{DATASET_ID}`
- Dataset aggregate SHA-256: `{manifest['aggregate_sha256']}`
- RUN-A/RUN-B distinct PIDs: `{run_a['pid']}` / `{run_b['pid']}`
- Reproducible: `{str(reproducible).lower()}`
- ETH total trades: `{eth_trades}`
- Result: `{result_code}`

This is a descriptive development-only cross-pair result. It does not apply the BTC-only formal Evaluation Policy gates, claim profitability, create a Candidate, modify the strategy, run Hyperopt, or access Validation/Holdout.
"""
    (report_dir / "eth-cross-pair-generalization-final-report.md").write_text(markdown, encoding="utf-8")
    record_registry(repo, result, [
        f"research/data/snapshots/{DATASET_ID}/manifest.yaml",
        "research/analysis/eth-cross-pair-generalization/run-comparison.json",
        "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json",
        "reports/audits/eth-cross-pair-generalization/eth-cross-pair-generalization-final-report.json",
        "reports/audits/eth-cross-pair-generalization/eth-cross-pair-generalization-final-report.md",
    ])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
