#!/usr/bin/env python3
"""Build a deterministic Development-only funding/mark stress profile."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from research_director_common import fingerprint, load_document, sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
APPROVAL_PATH = Path("research/governance/approvals/bnb-xrp-funding-mark-stress-v1-approval.json")
SLICE_POLICY_PATH = Path("research/temporal/ranging-short-ablation-temporal-slices-v1.yaml")
ANALYSIS_PATH = Path("research/analysis/discovery-bnb-xrp-funding-mark-stress-v1-v1/analysis.json")
REPORT_PATH = Path("reports/audits/discovery-bnb-xrp-funding-mark-stress-v1-v1/report.md")

DATASETS = {
    "BTC": ("futures-dev-btc-usdt-usdt-20240101-20240830-v2", "BTC_USDT_USDT"),
    "ETH": ("futures-dev-eth-usdt-usdt-20240101-20240830-v1", "ETH_USDT_USDT"),
    "BNB": ("futures-dev-bnb-usdt-usdt-20240101-20240830-v1", "BNB_USDT_USDT"),
    "XRP": ("futures-dev-xrp-usdt-usdt-20240101-20240830-v1", "XRP_USDT_USDT"),
}

EXPECTED_MANIFESTS = {
    "BTC": "e60ecbb9c28be5910bf1d33c6ed03bf46798228a343670b71a738b4b9150cc13",
    "ETH": "6557a265a1d2904452a236a84e1afeb9db4508e0ec6952a134ca494d2433b925",
    "BNB": "3b80e09dd36c5a32f229b7f53db7a5f2a2c38eb849a65956aadc97b5f4ea6f2d",
    "XRP": "dceed5d26a42256bed7a5e6819473414506d6e023e9556cba44a556b292e3e97",
}


def _approval(repo: Path) -> dict[str, Any]:
    approval = load_document(repo / APPROVAL_PATH)
    payload = {key: value for key, value in approval.items() if key != "approval_fingerprint"}
    checks = {
        "status": approval.get("approval_status") == "approved",
        "human": approval.get("approver_type") == "human_user",
        "explicit_instruction": approval.get("authorization_source") == "explicit_user_instruction",
        "idea": approval.get("idea_semantic_fingerprint") == "01cdba1de4f514e3eac41ca02285de8365f97de56ba8f8df7c042ae8a44dcfcc",
        "critic": approval.get("critic_fingerprint") == "fc1c354499b1df0814b9b0d3effd8f35117bf62655c198f37fd1142b384879c3",
        "rank": approval.get("selected_rank") == 2,
        "paths": approval.get("exact_artifact_paths") == [ANALYSIS_PATH.as_posix(), REPORT_PATH.as_posix()],
        "descriptive_only": approval.get("descriptive_analysis_authorized") is True,
        "protected_zero": all(approval.get(key) in (False, 0) for key in (
            "network_access_authorized", "backtest_authorized", "candidate_creation_authorized",
            "strategy_mutation_authorized", "validation_accesses_authorized",
            "holdout_accesses_authorized", "trading_execution_authorized",
            "automatic_promotion_authorized",
        )),
        "fingerprint": approval.get("approval_fingerprint") == fingerprint(payload),
    }
    if not all(checks.values()):
        raise ValueError(f"funding/mark approval failed closed: {checks}")
    return approval


def _file_record(manifest: dict[str, Any], suffix: str) -> dict[str, Any]:
    matches = [item for item in manifest.get("files", []) if str(item.get("path", "")).endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"manifest must bind exactly one {suffix}")
    return matches[0]


def _read_asset(repo: Path, record: dict[str, Any]) -> pd.DataFrame:
    path = repo / record["path"]
    if not path.is_file() or path.stat().st_size != int(record["bytes"]) or sha256_file(path) != record["sha256"]:
        raise ValueError(f"sealed asset identity mismatch: {record['path']}")
    frame = pd.read_feather(path)
    required = {"date", "open", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"sealed asset columns are incomplete: {record['path']}")
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    frame = frame.sort_values("date").reset_index(drop=True)
    cadence_seconds = frame["date"].diff().dropna().dt.total_seconds()
    if frame["date"].duplicated().any() or cadence_seconds.ne(8 * 60 * 60).any():
        raise ValueError(f"sealed asset cadence failed: {record['path']}")
    return frame


def load_frames(repo: Path) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    frames: dict[str, pd.DataFrame] = {}
    integrity: list[dict[str, Any]] = []
    for asset, (dataset_id, stem) in DATASETS.items():
        manifest_path = repo / f"research/data/snapshots/{dataset_id}/manifest.yaml"
        if sha256_file(manifest_path) != EXPECTED_MANIFESTS[asset]:
            raise ValueError(f"{asset} manifest hash mismatch")
        manifest = load_document(manifest_path)
        if manifest.get("sealed") is not True or manifest.get("campaign_mutable") is not False:
            raise ValueError(f"{asset} dataset is not sealed and immutable")
        funding_record = _file_record(manifest, f"{stem}-8h-funding_rate.feather")
        mark_record = _file_record(manifest, f"{stem}-8h-mark.feather")
        funding = _read_asset(repo, funding_record)
        mark = _read_asset(repo, mark_record)
        if not funding["date"].equals(mark["date"]):
            raise ValueError(f"{asset} funding and mark timestamps do not align")
        frame = pd.DataFrame({
            "date": funding["date"],
            "funding_rate": pd.to_numeric(funding["open"], errors="raise"),
            "mark_close": pd.to_numeric(mark["close"], errors="raise"),
        })
        frame["mark_return"] = frame["mark_close"].pct_change(fill_method=None)
        if not all(math.isfinite(float(value)) for value in frame["funding_rate"]):
            raise ValueError(f"{asset} funding values are not finite")
        frames[asset] = frame
        integrity.append({
            "asset": asset,
            "dataset_id": dataset_id,
            "manifest_path": manifest_path.relative_to(repo).as_posix(),
            "manifest_sha256": EXPECTED_MANIFESTS[asset],
            "rows": len(frame),
            "start": frame["date"].iloc[0].isoformat(),
            "end": frame["date"].iloc[-1].isoformat(),
            "funding_path": funding_record["path"],
            "funding_sha256": funding_record["sha256"],
            "mark_path": mark_record["path"],
            "mark_sha256": mark_record["sha256"],
            "timestamp_alignment": True,
        })
    identities = {(row["rows"], row["start"], row["end"]) for row in integrity}
    if len(identities) != 1:
        raise ValueError("cross-asset 8h coverage does not match")
    return frames, integrity


def longest_true_run(values: pd.Series) -> int:
    best = current = 0
    for value in values.astype(bool):
        current = current + 1 if value else 0
        best = max(best, current)
    return best


def window_metrics(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, funding_threshold: float, mark_threshold: float) -> dict[str, Any]:
    data = frame[(frame["date"] >= start) & (frame["date"] < end)].dropna(subset=["mark_return"]).copy()
    funding_stress = data["funding_rate"].abs() >= funding_threshold
    mark_stress = data["mark_return"].abs() >= mark_threshold
    joint = funding_stress & mark_stress
    funding_rate = float(funding_stress.mean())
    mark_rate = float(mark_stress.mean())
    joint_rate = float(joint.mean())
    expected = funding_rate * mark_rate
    return {
        "rows": int(len(data)),
        "funding_stress_count": int(funding_stress.sum()),
        "mark_stress_count": int(mark_stress.sum()),
        "joint_stress_count": int(joint.sum()),
        "funding_stress_rate": funding_rate,
        "mark_stress_rate": mark_rate,
        "joint_stress_rate": joint_rate,
        "joint_lift_vs_independence": None if expected == 0 else joint_rate / expected,
        "mark_stress_given_funding_stress": None if not funding_stress.any() else float(joint.sum() / funding_stress.sum()),
        "longest_joint_stress_run_8h_bars": longest_true_run(joint),
        "funding_abs_p95": float(data["funding_rate"].abs().quantile(0.95)),
        "mark_abs_return_p95": float(data["mark_return"].abs().quantile(0.95)),
    }


def build_analysis(repo: Path) -> dict[str, Any]:
    approval = _approval(repo)
    frames, integrity = load_frames(repo)
    slice_policy = load_document(repo / SLICE_POLICY_PATH)
    slices = [{
        "window_id": item["slice_id"],
        "start": pd.Timestamp(item["evaluation_start"]),
        "end": pd.Timestamp(item["evaluation_end_exclusive"]),
    } for item in slice_policy["slices"]]
    full = {"window_id": "full-evaluation", "start": slices[0]["start"], "end": slices[-1]["end"]}
    baseline = pd.concat([
        frames[asset][(frames[asset]["date"] >= full["start"]) & (frames[asset]["date"] < full["end"])]
        for asset in ("BTC", "ETH")
    ], ignore_index=True)
    quantile = float(approval["baseline_quantile"])
    funding_threshold = float(baseline["funding_rate"].abs().quantile(quantile))
    mark_threshold = float(baseline["mark_return"].abs().dropna().quantile(quantile))
    windows = []
    slice_support = []
    for window in [full, *slices]:
        metrics = {
            asset: window_metrics(frame, window["start"], window["end"], funding_threshold, mark_threshold)
            for asset, frame in frames.items()
        }
        baseline_max = max(metrics["BTC"]["joint_stress_rate"], metrics["ETH"]["joint_stress_rate"])
        additional_exceeds = [asset for asset in ("BNB", "XRP") if metrics[asset]["joint_stress_rate"] > baseline_max]
        windows.append({
            "window_id": window["window_id"],
            "start": window["start"].isoformat(),
            "end_exclusive": window["end"].isoformat(),
            "asset_metrics": metrics,
            "baseline_max_joint_stress_rate": baseline_max,
            "additional_assets_exceeding_baseline_max": additional_exceeds,
        })
        if window["window_id"] != "full-evaluation":
            slice_support.append(len(additional_exceeds) == 2)
    supported_slice_count = sum(slice_support)
    conclusion = "persistent_additional_pair_joint_stress" if supported_slice_count >= 3 else "no_persistent_additional_pair_joint_stress"
    result = {
        "schema_version": "bnb-xrp-funding-mark-stress-profile-v1",
        "proposal_id": "discovery-bnb-xrp-funding-mark-stress-v1-v1",
        "status": "completed",
        "classification": conclusion,
        "generated_at": approval["approved_at"],
        "approval_path": APPROVAL_PATH.as_posix(),
        "approval_fingerprint": approval["approval_fingerprint"],
        "method": {
            "funding_value_field": "open",
            "mark_return": "8h close-to-close simple return",
            "threshold_source": "pooled BTC/ETH full Development evaluation window",
            "quantile": quantile,
            "absolute_funding_threshold": funding_threshold,
            "absolute_mark_return_threshold": mark_threshold,
            "persistent_rule": "both BNB and XRP exceed max(BTC, ETH) joint-stress rate in at least 3 of 4 frozen slices",
            "slice_policy_path": SLICE_POLICY_PATH.as_posix(),
            "slice_policy_sha256": sha256_file(repo / SLICE_POLICY_PATH),
        },
        "data_integrity": integrity,
        "windows": windows,
        "hypothesis_result": {
            "supported_slice_count": supported_slice_count,
            "total_slice_count": len(slice_support),
            "persistent": supported_slice_count >= 3,
        },
        "governance": {
            "development_only": True,
            "network_accesses": 0,
            "backtests": 0,
            "signals_or_trades_generated": 0,
            "candidates_created": 0,
            "strategy_changes": 0,
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "promotion_authorized": False,
        },
        "limitations": [
            "No spot basis, order book, or realized execution-cost data is included.",
            "Co-occurrence is descriptive and does not establish causality, profitability, or arbitrage capacity.",
            "Thresholds are fixed from the BTC/ETH Development baseline and are not trading parameters.",
        ],
    }
    result["result_fingerprint"] = fingerprint(result)
    return result


def render_report(result: dict[str, Any]) -> str:
    lines = [
        "# BNB/XRP Funding and Mark Stress Profile", "",
        f"- Classification: `{result['classification']}`",
        f"- Persistent slices: `{result['hypothesis_result']['supported_slice_count']}/{result['hypothesis_result']['total_slice_count']}`",
        f"- Absolute funding threshold: `{result['method']['absolute_funding_threshold']:.12g}`",
        f"- Absolute mark-return threshold: `{result['method']['absolute_mark_return_threshold']:.12g}`", "",
        "## Full-window joint stress", "",
        "| Asset | Funding stress | Mark stress | Joint stress | Joint lift | Longest run |", "|---|---:|---:|---:|---:|---:|",
    ]
    full = result["windows"][0]["asset_metrics"]
    for asset in ("BTC", "ETH", "BNB", "XRP"):
        row = full[asset]
        lift = "n/a" if row["joint_lift_vs_independence"] is None else f"{row['joint_lift_vs_independence']:.3f}"
        lines.append(f"| {asset} | {row['funding_stress_rate']:.3%} | {row['mark_stress_rate']:.3%} | {row['joint_stress_rate']:.3%} | {lift} | {row['longest_joint_stress_run_8h_bars']} |")
    lines.extend(["", "## Frozen-slice decision", "", "| Slice | BTC | ETH | BNB | XRP | Both additional pairs exceed baseline max |", "|---|---:|---:|---:|---:|---|"])
    for window in result["windows"][1:]:
        metrics = window["asset_metrics"]
        both = len(window["additional_assets_exceeding_baseline_max"]) == 2
        lines.append(f"| {window['window_id']} | {metrics['BTC']['joint_stress_rate']:.3%} | {metrics['ETH']['joint_stress_rate']:.3%} | {metrics['BNB']['joint_stress_rate']:.3%} | {metrics['XRP']['joint_stress_rate']:.3%} | {'yes' if both else 'no'} |")
    lines.extend([
        "", "## Governance conclusion", "",
        "This is Development-only descriptive evidence. It does not authorize a backtest, Candidate, strategy change, Validation/Holdout access, promotion, or trading.", "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    result = build_analysis(repo)
    write_json(repo / ANALYSIS_PATH, result)
    report = repo / REPORT_PATH
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(result), encoding="utf-8")
    print(json.dumps({"status": result["status"], "classification": result["classification"], "result_fingerprint": result["result_fingerprint"], "analysis": ANALYSIS_PATH.as_posix(), "report": REPORT_PATH.as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
