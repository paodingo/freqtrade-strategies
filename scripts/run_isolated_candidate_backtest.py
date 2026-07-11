#!/usr/bin/env python3
"""One-shot isolated worker: audit one code identity and run one backtest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_strategy_signal_reachability as reachability
from audit_candidate_runtime_identity import RuntimeIdentityError, audit_runtime_identity
from research_control import load_simple_yaml
from run_experiment import dump_json
from run_offline_backtest import run_offline_backtest


def analyze_loaded_signals(repo_root: Path, manifest: dict[str, Any], candidate_class: type) -> dict[str, Any]:
    if not manifest.get("mutation"):
        return {"kind": "baseline", "signal_diff_count": 0, "deltas": []}
    data_root = repo_root / "research/data/snapshots" / manifest["dataset_id"] / "data/futures"

    class DataProvider:
        def current_whitelist(self) -> list[str]:
            return ["BTC/USDT:USDT"]

        def get_pair_dataframe(self, pair: str, timeframe: str, candle_type: str = "futures") -> pd.DataFrame:
            if pair != "BTC/USDT:USDT" or candle_type != "futures":
                raise ValueError("unauthorized instrumentation input")
            return pd.read_feather(data_root / f"BTC_USDT_USDT-{timeframe}-futures.feather")

    raw = pd.read_feather(data_root / "BTC_USDT_USDT-1h-futures.feather")
    metadata = {"pair": "BTC/USDT:USDT"}
    candidate = candidate_class({})
    candidate.dp = DataProvider()
    candidate_df = candidate.populate_indicators(raw.copy(), metadata)
    candidate_df = candidate.populate_entry_trend(candidate_df, metadata)
    candidate_df = candidate.populate_exit_trend(candidate_df, metadata)
    baseline_df = reachability.load_strategy_dataframe(repo_root)
    deltas = []
    for column, direction, signal_type in (
        ("enter_long", "long", "entry"), ("enter_short", "short", "entry"),
        ("exit_long", "long", "exit"), ("exit_short", "short", "exit"),
    ):
        baseline = baseline_df[column].fillna(0).astype(int) if column in baseline_df else pd.Series(0, index=baseline_df.index)
        current = candidate_df[column].fillna(0).astype(int) if column in candidate_df else pd.Series(0, index=candidate_df.index)
        for index in candidate_df.index[baseline != current]:
            deltas.append({
                "column": column, "direction": direction, "signal_type": signal_type,
                "timestamp": pd.Timestamp(candidate_df.loc[index, "date"]).isoformat(),
                "baseline_value": int(baseline.loc[index]), "candidate_value": int(current.loc[index]),
                "enter_tag": candidate_df.loc[index].get("enter_tag"), "exit_tag": candidate_df.loc[index].get("exit_tag"),
            })
    return {
        "kind": "candidate", "signal_diff_count": len(deltas),
        "condition_mask_diff_count": manifest["expected_condition_mask_changes"],
        "final_signal_mask_diff_count": len(deltas), "deltas": deltas,
        "stage3d2a_expected_final_signal_mask_diff_count": manifest["expected_final_signal_mask_changes"],
        "reachability_status": "reachability_confirmed" if len(deltas) == int(manifest["expected_final_signal_mask_changes"]) else "reachability_prediction_miss",
    }


def run_worker(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.suffix.lower() == ".json" else load_simple_yaml(manifest_path)
    result_dir = repo_root / "research/results" / manifest["campaign_id"] / str(manifest["experiment_id"]) / manifest["execution_run_id"]
    identity_path = result_dir / "runtime-code-identity.json"
    audited = audit_runtime_identity(repo_root, manifest, identity_path)
    signal_diff = analyze_loaded_signals(repo_root, manifest, audited["candidate_class_object"])
    dump_json(result_dir / "runtime-signal-diff.json", signal_diff)
    identity = audited["identity"]
    identity["backtest_started"] = True
    dump_json(identity_path, identity)
    campaign = manifest["campaign"]
    result = run_offline_backtest(repo_root, campaign, int(manifest["experiment_id"]), manifest["execution_run_id"], repo_root / campaign["sealed_offline_backtest"]["exchange_snapshot"])
    report = {
        "schema_version": "stage3d3b-isolated-worker-result-v1", "status": result["status"],
        "failure_type": result.get("failure_type"), "reason_code": result.get("reason_code"),
        "experiment_id": manifest["experiment_id"], "execution_run_id": manifest["execution_run_id"],
        "process_id": identity["process_id"], "parent_process_id": identity["parent_process_id"],
        "runtime_identity_path": str(identity_path.relative_to(repo_root)).replace("\\", "/"),
        "runtime_signal_diff_path": str((result_dir / "runtime-signal-diff.json").relative_to(repo_root)).replace("\\", "/"),
        "backtest_count": 1, "claimed_next_experiment": False, "registry_modified": False,
    }
    dump_json(result_dir / "isolated-worker-result.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        result = run_worker(Path.cwd(), Path(args.manifest))
    except RuntimeIdentityError as exc:
        print(json.dumps({"status": "failed", "failure_type": exc.failure_type, "reason_code": exc.reason_code, "message": exc.message}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in {"accepted", "rejected"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
