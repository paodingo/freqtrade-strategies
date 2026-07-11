#!/usr/bin/env python3
"""Build Stage 3C.2-R evaluation readiness artifacts without running strategies."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from research_control import load_simple_yaml, utc_now
from run_experiment import dump_json, dump_manifest, git_sha, repo_rel, sha256_file


PAIR = "BTC/USDT:USDT"
PAIR_STEM = "BTC_USDT_USDT"
DEV_V1_ID = "futures-dev-btc-usdt-usdt-20260301-20260328-v1"
VAL_V1_ID = "futures-validation-btc-usdt-usdt-20260503-20260628-v1"
ACCEPTANCE_IDS = {
    "demo-btc-usdt-usdt-futures-acceptance-202603-202606",
    "demo-btc-usdt-usdt-futures-acceptance-20260329-20260412",
}
REQUIRED_KEYS = {"futures_1h", "futures_4h", "mark_8h", "funding_rate_8h"}
MIN_EVALUATION_1H_CANDLES = 5000
STARTUP_CANDLES_4H = 200
EMBARGO_HOURS = 14 * 24
REGISTRY_PATH = Path("research/registry/research.db")

DEV_READINESS = {
    "status": "insufficient",
    "reason_codes": [
        "no_baseline_trades",
        "no_candidate_trades",
        "insufficient_for_relative_evaluation",
        "insufficient_for_lookahead_trade_coverage",
    ],
    "total_trades": 0,
    "suitable_for_execution_probe": True,
    "suitable_for_strategy_ranking": False,
    "suitable_for_cost_stress": False,
}


@dataclass(frozen=True)
class FrameSummary:
    key: str
    dataset_id: str
    path: Path
    candle_type: str
    timeframe: str
    rows: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    continuous_end: pd.Timestamp | None
    duplicates: int
    missing_intervals: list[dict[str, str]]
    bytes: int
    sha256: str
    sealed_snapshot: bool


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value.replace("Z", "+00:00"))


def iso(value: pd.Timestamp | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return value.tz_convert("UTC").isoformat().replace("+00:00", "Z")


def frame_key(path: Path) -> tuple[str, str, str] | None:
    name = path.name
    if not name.startswith(PAIR_STEM):
        return None
    if name.endswith("-1h-futures.feather"):
        return "futures_1h", "futures", "1h"
    if name.endswith("-4h-futures.feather"):
        return "futures_4h", "futures", "4h"
    if name.endswith("-8h-mark.feather"):
        return "mark_8h", "mark", "8h"
    if name.endswith("-8h-funding_rate.feather"):
        return "funding_rate_8h", "funding_rate", "8h"
    if name.endswith("-1h-mark.feather"):
        return "mark_1h", "mark", "1h"
    return None


def timeframe_delta(timeframe: str) -> pd.Timedelta:
    if not timeframe.endswith("h"):
        raise ValueError(f"unsupported timeframe: {timeframe}")
    return pd.to_timedelta(int(timeframe[:-1]), unit="h")


def normalize_dates(series: pd.Series, candle_type: str) -> pd.Series:
    dates = pd.to_datetime(series, utc=True)
    if candle_type == "funding_rate":
        return dates.dt.round("s")
    return dates


def summarize_frame(repo_root: Path, dataset_id: str, path: Path, manifest: dict[str, Any] | None) -> FrameSummary | None:
    parsed = frame_key(path)
    if parsed is None:
        return None
    key, candle_type, timeframe = parsed
    frame = pd.read_feather(path)
    if "date" not in frame.columns:
        raise ValueError(f"missing date column: {path}")
    dates = normalize_dates(frame["date"], candle_type).sort_values().reset_index(drop=True)
    duplicates = int(dates.duplicated().sum())
    expected = timeframe_delta(timeframe)
    missing: list[dict[str, str]] = []
    continuous_end = dates.iloc[-1] if len(dates) else None
    if len(dates) > 1:
        for idx in range(1, len(dates)):
            prev = dates.iloc[idx - 1]
            cur = dates.iloc[idx]
            if cur - prev != expected:
                missing.append({"from": iso(prev), "to": iso(cur), "expected_step": str(expected)})
                if len(missing) == 1:
                    continuous_end = prev
    return FrameSummary(
        key=key,
        dataset_id=dataset_id,
        path=path,
        candle_type=candle_type,
        timeframe=timeframe,
        rows=int(len(dates)),
        start=dates.iloc[0] if len(dates) else None,
        end=dates.iloc[-1] if len(dates) else None,
        continuous_end=continuous_end,
        duplicates=duplicates,
        missing_intervals=missing,
        bytes=path.stat().st_size,
        sha256=sha256_file(path),
        sealed_snapshot=bool((manifest or {}).get("sealed")),
    )


def summarize_manifest_frame(repo_root: Path, dataset_id: str, path: Path, manifest: dict[str, Any]) -> FrameSummary | None:
    parsed = frame_key(path)
    if parsed is None:
        return None
    key, candle_type, timeframe = parsed
    rel = repo_rel(repo_root, path)
    file_record = next((item for item in manifest.get("files", []) if item.get("path") == rel), {})
    coverage = next((item for item in manifest.get("coverage", []) if item.get("file") == path.name), {})
    checks = (manifest.get("validation_checks") or {}).get(key, {})
    start = pd.Timestamp(coverage.get("start") or checks.get("start")) if coverage.get("start") or checks.get("start") else None
    end = pd.Timestamp(coverage.get("end") or checks.get("end")) if coverage.get("end") or checks.get("end") else None
    missing_count = int(checks.get("missing_intervals") or 0)
    missing = [{"from": "manifest_recorded_gap", "to": "manifest_recorded_gap", "expected_step": str(timeframe_delta(timeframe))} for _ in range(missing_count)]
    return FrameSummary(
        key=key,
        dataset_id=dataset_id,
        path=path,
        candle_type=candle_type,
        timeframe=timeframe,
        rows=int(coverage.get("rows") or checks.get("rows") or 0),
        start=start.tz_convert("UTC") if start is not None and start.tzinfo else start,
        end=end.tz_convert("UTC") if end is not None and end.tzinfo else end,
        continuous_end=(end.tz_convert("UTC") if end is not None and end.tzinfo else end) if missing_count == 0 else None,
        duplicates=int(checks.get("duplicates") or 0),
        missing_intervals=missing,
        bytes=int(file_record.get("bytes") or 0),
        sha256=str(file_record.get("sha256") or ""),
        sealed_snapshot=bool(manifest.get("sealed")),
    )


def overlap(range_a: tuple[pd.Timestamp | None, pd.Timestamp | None], range_b: tuple[pd.Timestamp, pd.Timestamp]) -> bool:
    if range_a[0] is None or range_a[1] is None:
        return False
    return max(range_a[0], range_b[0]) <= min(range_a[1], range_b[1])


def audit_local_data(repo_root: Path) -> dict[str, Any]:
    snapshot_root = repo_root / "research" / "data" / "snapshots"
    manifests: dict[str, dict[str, Any]] = {}
    rows: list[FrameSummary] = []
    for manifest_path in snapshot_root.glob("*/manifest.yaml"):
        try:
            manifests[manifest_path.parent.name] = load_simple_yaml(manifest_path)
        except Exception:
            manifests[manifest_path.parent.name] = {}
    for path in snapshot_root.glob("*/data/futures/*.feather"):
        dataset_id = path.parents[2].name
        if dataset_id == VAL_V1_ID:
            summary = summarize_manifest_frame(repo_root, dataset_id, path, manifests.get(dataset_id, {}))
        else:
            summary = summarize_frame(repo_root, dataset_id, path, manifests.get(dataset_id))
        if summary is not None:
            rows.append(summary)

    grouped: dict[str, dict[str, FrameSummary]] = {}
    for row in rows:
        grouped.setdefault(row.dataset_id, {})[row.key] = row

    ranges = {
        "acceptance_fixture": (ts("2026-03-29T00:00:00Z"), ts("2026-04-12T00:00:00Z")),
        "development_v1": (ts("2026-03-01T00:00:00Z"), ts("2026-03-28T23:00:00Z")),
        "validation_v1": (ts("2026-05-03T00:00:00Z"), ts("2026-06-28T16:00:00Z")),
    }

    datasets: list[dict[str, Any]] = []
    complete_candidates: list[dict[str, Any]] = []
    for dataset_id, by_key in sorted(grouped.items()):
        entries = []
        for key, row in sorted(by_key.items()):
            row_range = (row.start, row.continuous_end)
            entries.append(
                {
                    "key": key,
                    "pair": PAIR,
                    "timeframe": row.timeframe,
                    "candle_type": row.candle_type,
                    "rows": row.rows,
                    "start": iso(row.start),
                    "end": iso(row.end),
                    "continuous_end": iso(row.continuous_end),
                    "duplicate_timestamps": row.duplicates,
                    "missing_intervals": row.missing_intervals,
                    "source_file": repo_rel(repo_root, row.path),
                    "bytes": row.bytes,
                    "sha256": row.sha256,
                    "sealed_snapshot": row.sealed_snapshot,
                    "audit_source": "manifest_only" if dataset_id == VAL_V1_ID else "file_read",
                    "overlaps": {name: overlap(row_range, rng) for name, rng in ranges.items()},
                }
            )
        complete = REQUIRED_KEYS.issubset(by_key)
        record = {
            "dataset_id": dataset_id,
            "manifest": f"research/data/snapshots/{dataset_id}/manifest.yaml" if dataset_id in manifests else None,
            "sealed_snapshot": bool(manifests.get(dataset_id, {}).get("sealed")),
            "keys_present": sorted(by_key),
            "complete_research_input": complete,
            "files": entries,
            "is_acceptance_fixture": dataset_id in ACCEPTANCE_IDS,
            "is_development_v1": dataset_id == DEV_V1_ID,
            "is_validation_v1": dataset_id == VAL_V1_ID,
            "sealed_validation_data_read": False if dataset_id == VAL_V1_ID else None,
        }
        if complete:
            start = max(by_key[key].start for key in REQUIRED_KEYS if by_key[key].start is not None)
            end = min(by_key[key].continuous_end for key in REQUIRED_KEYS if by_key[key].continuous_end is not None)
            main_rows = int(((end - start) / pd.to_timedelta(1, unit="h")) + 1) if start is not None and end is not None and start <= end else 0
            record["continuous_research_range"] = {"start": iso(start), "end": iso(end), "main_1h_candles": main_rows}
            complete_candidates.append({"dataset_id": dataset_id, "start": start, "end": end, "main_1h_candles": main_rows})
        datasets.append(record)

    best = max(complete_candidates, key=lambda item: item["main_1h_candles"], default=None)
    missing_candles = MIN_EVALUATION_1H_CANDLES - int(best["main_1h_candles"]) if best else MIN_EVALUATION_1H_CANDLES
    audit = {
        "schema_version": "stage3c2r-evaluation-data-coverage-audit-v1",
        "created_at": utc_now(),
        "pair": PAIR,
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "authorized_scope": "local sealed or staged Binance USD-M futures research data only",
        "strategy_results_used": False,
        "acceptance_fixture_can_be_development": False,
        "minimum_development_1h_candles": MIN_EVALUATION_1H_CANDLES,
        "required_inputs": sorted(REQUIRED_KEYS),
        "datasets": datasets,
        "max_continuous_research_range": {
            "source_dataset_id": best["dataset_id"] if best else None,
            "start": iso(best["start"]) if best else None,
            "end": iso(best["end"]) if best else None,
            "main_1h_candles": int(best["main_1h_candles"]) if best else 0,
            "meets_minimum": bool(best and best["main_1h_candles"] >= MIN_EVALUATION_1H_CANDLES),
            "missing_1h_candles": max(0, int(missing_candles)),
        },
        "verdict": "data_provisioning_blocked" if not best or best["main_1h_candles"] < MIN_EVALUATION_1H_CANDLES else "evaluation_ready",
    }
    return audit


def write_coverage_markdown(repo_root: Path, audit: dict[str, Any]) -> Path:
    path = repo_root / "reports" / "audits" / "stage3c2r_evaluation_data_coverage_audit.md"
    best = audit["max_continuous_research_range"]
    lines = [
        "# Stage 3C.2-R Evaluation Data Coverage Audit",
        "",
        "## 结论",
        "",
        f"- Verdict: `{audit['verdict']}`",
        f"- Strategy results used: `{str(audit['strategy_results_used']).lower()}`",
        f"- Acceptance fixture can be Development: `{str(audit['acceptance_fixture_can_be_development']).lower()}`",
        f"- Best complete source: `{best['source_dataset_id']}`",
        f"- Max continuous research range: `{best['start']}` to `{best['end']}`",
        f"- Main 1h candles available: `{best['main_1h_candles']}`",
        f"- Required main 1h candles: `{audit['minimum_development_1h_candles']}`",
        f"- Missing main 1h candles: `{best['missing_1h_candles']}`",
        "",
        "因此本地数据不足以创建真实 sealed Development/Validation v2。Stage 3C.2-R 只能冻结 split v2 政策和 provisioning blocker，不能运行策略 readiness probe。",
        "",
        "## Dataset Inventory",
        "",
        "| dataset | complete | sealed | acceptance | files | continuous range | 1h candles |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for dataset in audit["datasets"]:
        rng = dataset.get("continuous_research_range") or {}
        lines.append(
            f"| `{dataset['dataset_id']}` | `{str(dataset['complete_research_input']).lower()}` | `{str(dataset['sealed_snapshot']).lower()}` | `{str(dataset['is_acceptance_fixture']).lower()}` | {len(dataset['files'])} | `{rng.get('start')}` to `{rng.get('end')}` | {rng.get('main_1h_candles', 0)} |"
        )
    lines.extend(["", "## File Details", ""])
    for dataset in audit["datasets"]:
        if dataset.get("is_validation_v1"):
            lines.append("- Sealed Validation data audit mode: `manifest_only`; data files are not opened for candidate evaluation.")
            lines.append("")
        lines.extend([f"### `{dataset['dataset_id']}`", "", "| key | type | timeframe | audit | rows | start | end | continuous_end | dup | gaps | bytes | sha256 | source |", "|---|---|---|---|---:|---|---|---|---:|---:|---:|---|---|"])
        for item in dataset["files"]:
            lines.append(
                f"| `{item['key']}` | `{item['candle_type']}` | `{item['timeframe']}` | `{item['audit_source']}` | {item['rows']} | `{item['start']}` | `{item['end']}` | `{item['continuous_end']}` | {item['duplicate_timestamps']} | {len(item['missing_intervals'])} | {item['bytes']} | `{item['sha256']}` | `{item['source_file']}` |"
            )
        lines.append("")
    lines.extend(
        [
            "## Provisioning Plan",
            "",
            "- 需要 Campaign 明确授权 `provisioning_mode` 后，才允许通过 Binance public market-data endpoint 补充 USD-M futures 数据。",
            "- 目标是形成不少于 `5000` 根连续 Development 评价 1h K 线，另加完整 startup/warm-up。",
            "- 同期必须具备 `4h futures` informative、`8h mark` 和 `8h funding_rate` 完整数据。",
            "- 不得访问 account/private/trade API，不得读取 secret，不得使用 sealed holdout。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def mark_dev_v1_insufficient(repo_root: Path) -> dict[str, Any]:
    manifest_path = repo_root / "research" / "data" / "snapshots" / DEV_V1_ID / "manifest.yaml"
    manifest = load_simple_yaml(manifest_path)
    manifest["evaluation_readiness"] = dict(DEV_READINESS)
    dump_manifest(manifest_path, manifest)
    return manifest


def write_split_v2_policy(repo_root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    best = audit["max_continuous_research_range"]
    policy = {
        "schema_version": "stage3c2r-split-v2-policy-v1",
        "split_id": "futures-dev-validation-v2",
        "status": "data_provisioning_blocked",
        "created_at": utc_now(),
        "frozen_before_strategy_probe": True,
        "strategy_results_used": False,
        "strategy_probe_run": False,
        "selection_basis": "data_coverage_only_no_strategy_results",
        "pair": PAIR,
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "primary_timeframe": "1h",
        "informative_timeframes": ["4h"],
        "required_candle_types": ["futures", "mark", "funding_rate"],
        "minimum_requirements": {
            "development_evaluation_1h_candles": MIN_EVALUATION_1H_CANDLES,
            "startup_candles_4h": STARTUP_CANDLES_4H,
            "warmup_counted_in_evaluation": False,
            "embargo_hours": EMBARGO_HOURS,
            "validation_policy": "fixed_future_window_or_fixed_ratio_predeclared_before_strategy_run",
        },
        "chronological_rules": {
            "development_uses_earliest_continuous_history": True,
            "embargo_after_development": True,
            "validation_strictly_after_development": True,
            "development_validation_overlap_allowed": False,
            "acceptance_fixture_outside_evaluation": True,
        },
        "prohibited_selection_inputs": [
            "strategy_returns",
            "profit_factor",
            "sharpe",
            "drawdown",
            "long_short_performance",
            "baseline_candidate_comparison",
            "profitable_window_selection",
        ],
        "available_data_summary": best,
        "development_v2_dataset_id": None,
        "validation_v2_dataset_id": None,
        "development_v2_sealed": False,
        "validation_v2_sealed": False,
        "blocker_reasons": [
            "insufficient_continuous_1h_coverage",
            "development_v2_not_sealed",
            "validation_v2_not_sealed",
            "strategy_probe_not_allowed_until_v2_sealed",
        ],
    }
    path = repo_root / "research" / "data" / "splits" / "futures-dev-validation-v2-policy.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(path, policy)
    return policy


def write_policy_proposal(repo_root: Path, audit: dict[str, Any]) -> dict[str, Any]:
    proposal = {
        "schema_version": "stage3c2r-evaluation-policy-proposal-v1",
        "proposal_id": "stage3c2-futures-single-pair-policy-proposal-v1",
        "created_at": utc_now(),
        "policy_statuses": ["draft", "pending_human_review", "approved", "rejected", "superseded"],
        "policy_approval_status": "pending_human_review",
        "approver": None,
        "approval_timestamp": None,
        "approval_reason": None,
        "codex_may_approve": False,
        "current_data_verdict": audit["verdict"],
        "current_data_capability": {
            "development_v2_sealed": False,
            "validation_v2_sealed": False,
            "max_continuous_1h_candles": audit["max_continuous_research_range"]["main_1h_candles"],
            "single_pair_only": True,
            "validation_not_read": True,
            "holdout_not_accessed": True,
        },
        "pending_human_decisions": [
            "development_min_total_trades",
            "development_min_long_trades",
            "development_min_short_trades",
            "validation_min_total_trades",
            "max_drawdown_absolute_gate",
            "baseline_relative_drawdown_limit",
            "profit_factor_gate",
            "baseline_relative_return_rule",
            "worst_window_rule",
            "positive_window_rule",
            "cost_stress_scenarios",
            "tie_or_inconclusive_rule",
            "missing_metric_policy",
            "validation_pass_conditions",
        ],
        "options": [
            {
                "name": "coverage_first_research_gate",
                "status": "draft",
                "summary": "Prioritize non-degenerate trade coverage and metric computability before strong profitability gates.",
                "advantages": ["works with limited single-pair data", "reduces pressure to overfit return thresholds"],
                "risks": ["may pass weak candidates into deeper diagnostics"],
                "applicability_boundary": "research only; not champion promotion",
            },
            {
                "name": "balanced_research_gate",
                "status": "draft",
                "summary": "Require coverage plus moderate drawdown/profit-factor and baseline-relative checks.",
                "advantages": ["filters obvious weak candidates", "keeps risk controls visible"],
                "risks": ["may be unstable on short single-pair samples"],
                "applicability_boundary": "requires v2 Development/Validation and approved numeric thresholds",
            },
            {
                "name": "conservative_risk_gate",
                "status": "draft",
                "summary": "Require stronger drawdown, worst-window, cost-stress and long/short coverage before Validation pass.",
                "advantages": ["lowers promotion risk", "makes downside behavior explicit"],
                "risks": ["likely too strict for early single-variable research"],
                "applicability_boundary": "best after more pairs or longer data history exist",
            },
        ],
        "forbidden_until_approved": [
            "development_pass_fail",
            "validation_access",
            "cost_stress_promotion_gate",
            "champion_creation",
            "qualified_challenger_creation",
        ],
    }
    path = repo_root / "research" / "evaluation" / "evaluation-policy-proposal.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(path, proposal)
    return proposal


def write_decision_packet(repo_root: Path, audit: dict[str, Any], proposal: dict[str, Any]) -> Path:
    path = repo_root / "reports" / "decisions" / "stage3c2_evaluation_policy_decision_packet.md"
    best = audit["max_continuous_research_range"]
    lines = [
        "# Stage 3C.2 Evaluation Policy Decision Packet",
        "",
        "## Status",
        "",
        "- Policy approval: `pending_human_review`",
        "- Codex approval allowed: `false`",
        f"- Current data verdict: `{audit['verdict']}`",
        "- Validation accessed: `false`",
        "- Holdout accessed: `false`",
        "- Champion or Qualified Challenger created: `false`",
        "",
        "## Current Data Capability",
        "",
        "- Development v2: `not_sealed`",
        "- Validation v2: `not_sealed`",
        f"- Best available complete continuous range: `{best['start']}` to `{best['end']}`",
        f"- Available 1h candles: `{best['main_1h_candles']}`",
        f"- Required Development 1h candles: `{MIN_EVALUATION_1H_CANDLES}`",
        "- Baseline trades on current v1 Development: `0`",
        "- Candidate trades on current v1 Development: `0`",
        "- Rolling windows: `not_meaningful_with_zero_trades`",
        "- Market state coverage: `single_pair_limited`",
        "",
        "## Existing Policy Evidence",
        "",
        "| Source | Evidence | Approved for current v2? |",
        "|---|---|---|",
        "| `research/evaluation/evaluation-policy.yaml` | `policy_approval_status: pending_human_review`; numeric coverage gates are null. | no |",
        "| `reports/audits/stage3c2_evaluation_policy_audit.md` | Historical/report thresholds exist but are not approved for this single-pair futures split. | no |",
        "| `research/data/validation-access-policy.yaml` | Validation access is controlled and budgeted. | yes, access control only |",
        "| `AUTONOMY.md` / `WORKFLOW.md` | Model cannot lower standards, promote champion, or bypass gates. | yes, governance only |",
        "",
        "## Pending Human Decisions",
        "",
    ]
    for item in proposal["pending_human_decisions"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Policy Options", ""])
    for option in proposal["options"]:
        lines.extend(
            [
                f"### `{option['name']}`",
                "",
                f"- Status: `{option['status']}`",
                f"- Rule shape: {option['summary']}",
                f"- Advantages: {', '.join(option['advantages'])}",
                f"- Risks: {', '.join(option['risks'])}",
                f"- Boundary: {option['applicability_boundary']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Decision Required",
            "",
            "Human approval must choose or edit one policy and provide approver, timestamp, reason, applicable dataset IDs, and market scope. Until then, Development may compute metrics only; it cannot produce pass/fail, enter Validation, or create Champion/Qualified Challenger.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_stage3c3_readiness(repo_root: Path, audit: dict[str, Any], split: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    blockers = [
        "development_v2_not_sealed",
        "validation_v2_not_sealed",
        "insufficient_continuous_1h_coverage",
        "development_nonzero_trades_not_established",
        "development_metrics_not_computable_on_v2",
        "recursive_analysis_candle_coverage_insufficient",
        "lookahead_trade_coverage_insufficient",
        "cost_stress_requires_nonzero_trades",
        "policy_pending_human_review",
    ]
    readiness = {
        "schema_version": "stage3c3-readiness-v1",
        "created_at": utc_now(),
        "ready": False,
        "status": "blocked",
        "readiness_checks": {
            "development_v2_sealed": False,
            "validation_v2_sealed": False,
            "development_has_nonzero_trades": False,
            "development_metrics_computable": False,
            "recursive_analysis_time_coverage": False,
            "lookahead_analysis_signal_coverage": False,
            "cost_stress_has_real_trades": False,
            "policy_human_approved": proposal["policy_approval_status"] == "approved",
            "candidate_validation_not_read": True,
            "holdout_not_accessed": True,
        },
        "blockers": blockers,
        "non_blocking_satisfied": ["candidate_validation_not_read", "holdout_not_accessed", "strategy_not_modified", "candidate_not_modified", "hyperopt_not_run"],
        "data_verdict": audit["verdict"],
        "split_id": split["split_id"],
        "policy_proposal_id": proposal["proposal_id"],
    }
    path = repo_root / "research" / "evaluation" / "stage3c3-readiness.json"
    dump_json(path, readiness)
    return readiness


def write_final_report(repo_root: Path, audit: dict[str, Any], split: dict[str, Any], proposal: dict[str, Any], readiness: dict[str, Any], artifacts: dict[str, str]) -> dict[str, Any]:
    final = {
        "schema_version": "stage3c2r-final-report-v1",
        "created_at": utc_now(),
        "git_sha": git_sha(repo_root),
        "status": "blocked",
        "blocker": "insufficient_continuous_futures_data_for_v2",
        "current_v1_development_readiness": DEV_READINESS,
        "v1_snapshots_overwritten": False,
        "v2_snapshots_created": False,
        "strategy_probe_run": False,
        "validation_accessed": False,
        "holdout_accessed": False,
        "hyperopt_run": False,
        "strategy_modified": False,
        "candidate_modified": False,
        "stage3c3_started": False,
        "data_audit_verdict": audit["verdict"],
        "max_continuous_research_range": audit["max_continuous_research_range"],
        "split_v2_status": split["status"],
        "policy_approval_status": proposal["policy_approval_status"],
        "stage3c3_ready": readiness["ready"],
        "artifacts": artifacts,
    }
    out_dir = repo_root / "research" / "results" / "stage3c2r-readiness"
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_json(out_dir / "stage3c2r-final-report.json", final)
    md = repo_root / "reports" / "audits" / "stage3c2r_final_report.md"
    best = audit["max_continuous_research_range"]
    lines = [
        "# Stage 3C.2-R Final Report",
        "",
        f"- Status: `{final['status']}`",
        f"- Blocker: `{final['blocker']}`",
        f"- v1 Development readiness: `{DEV_READINESS['status']}`",
        f"- Max continuous 1h candles: `{best['main_1h_candles']}` / `{MIN_EVALUATION_1H_CANDLES}`",
        "- Development v2 sealed: `false`",
        "- Validation v2 sealed: `false`",
        "- Strategy probe run: `false`",
        "- Validation accessed: `false`",
        "- Holdout accessed: `false`",
        "- Hyperopt run: `false`",
        "- Strategy/candidate modified: `false`",
        "- Policy approval: `pending_human_review`",
        "- Stage 3C.3 ready: `false`",
        "",
        "No fake v2 sealed snapshot was created because the local complete futures coverage is below the 5000-candle Development requirement.",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    final["artifacts"]["final_markdown_report"] = repo_rel(repo_root, md)
    dump_json(out_dir / "stage3c2r-final-report.json", final)
    return final


def init_registry(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS dataset_readiness (
          dataset_id TEXT PRIMARY KEY,
          aggregate_sha256 TEXT,
          status TEXT NOT NULL,
          reason_codes_json TEXT NOT NULL,
          total_trades INTEGER,
          artifact_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS split_v2_records (
          split_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          split_hash TEXT NOT NULL,
          strategy_results_used INTEGER NOT NULL,
          artifact_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evaluation_readiness_probes (
          probe_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          reason_code TEXT NOT NULL,
          input_fingerprint TEXT,
          artifact_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS policy_proposals (
          proposal_id TEXT PRIMARY KEY,
          proposal_hash TEXT NOT NULL,
          approval_status TEXT NOT NULL,
          approver TEXT,
          artifact_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS policy_approval_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          proposal_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          approver TEXT,
          reason TEXT,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stage3c3_readiness (
          readiness_id TEXT PRIMARY KEY,
          ready INTEGER NOT NULL,
          blockers_json TEXT NOT NULL,
          artifact_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS provisioning_blockers (
          blocker_id TEXT PRIMARY KEY,
          reason_code TEXT NOT NULL,
          missing_ranges_json TEXT NOT NULL,
          artifact_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evaluation_artifact_refs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          artifact_type TEXT NOT NULL,
          path TEXT NOT NULL,
          sha256 TEXT,
          recorded_at TEXT NOT NULL
        );
        """
    )


def write_registry(repo_root: Path, dev_manifest: dict[str, Any], split: dict[str, Any], proposal: dict[str, Any], readiness: dict[str, Any], final: dict[str, Any], artifacts: dict[str, str]) -> None:
    db_path = repo_root / REGISTRY_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        init_registry(conn)
        conn.execute(
            "INSERT OR REPLACE INTO dataset_readiness(dataset_id, aggregate_sha256, status, reason_codes_json, total_trades, artifact_path, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                DEV_V1_ID,
                dev_manifest.get("aggregate_sha256"),
                DEV_READINESS["status"],
                json.dumps(DEV_READINESS["reason_codes"], sort_keys=True),
                DEV_READINESS["total_trades"],
                artifacts["dev_v1_manifest"],
                utc_now(),
            ),
        )
        split_path = repo_root / artifacts["split_v2_policy"]
        proposal_path = repo_root / artifacts["policy_proposal"]
        readiness_path = repo_root / artifacts["stage3c3_readiness"]
        conn.execute(
            "INSERT OR REPLACE INTO split_v2_records(split_id, status, split_hash, strategy_results_used, artifact_path, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            (split["split_id"], split["status"], sha256_file(split_path), 0, artifacts["split_v2_policy"], utc_now()),
        )
        conn.execute(
            "INSERT OR REPLACE INTO evaluation_readiness_probes(probe_id, status, reason_code, input_fingerprint, artifact_path, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "stage3c2r-development-v2-probe",
                "not_run",
                "data_provisioning_blocked",
                stable_hash({"split_id": split["split_id"], "data": split["available_data_summary"], "candidate": "demo-stage3b2-single-variable:1"}),
                artifacts["stage3c3_readiness"],
                utc_now(),
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO policy_proposals(proposal_id, proposal_hash, approval_status, approver, artifact_path, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            (proposal["proposal_id"], sha256_file(proposal_path), proposal["policy_approval_status"], proposal.get("approver"), artifacts["policy_proposal"], utc_now()),
        )
        conn.execute(
            "INSERT OR REPLACE INTO stage3c3_readiness(readiness_id, ready, blockers_json, artifact_path, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("stage3c3-readiness", 1 if readiness["ready"] else 0, json.dumps(readiness["blockers"], sort_keys=True), artifacts["stage3c3_readiness"], utc_now()),
        )
        conn.execute(
            "INSERT OR REPLACE INTO provisioning_blockers(blocker_id, reason_code, missing_ranges_json, artifact_path, recorded_at) VALUES (?, ?, ?, ?, ?)",
            (
                "stage3c2r-insufficient-futures-history",
                final["blocker"],
                json.dumps(final["max_continuous_research_range"], sort_keys=True),
                artifacts["coverage_audit"],
                utc_now(),
            ),
        )
        for artifact_type, rel_path in artifacts.items():
            full = repo_root / rel_path
            conn.execute(
                "INSERT INTO evaluation_artifact_refs(artifact_type, path, sha256, recorded_at) VALUES (?, ?, ?, ?)",
                (artifact_type, rel_path, sha256_file(full) if full.exists() and full.is_file() else None, utc_now()),
            )
        conn.commit()
    finally:
        conn.close()


def build(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    dev_manifest = mark_dev_v1_insufficient(repo_root)
    audit = audit_local_data(repo_root)
    coverage_md = write_coverage_markdown(repo_root, audit)
    split = write_split_v2_policy(repo_root, audit)
    proposal = write_policy_proposal(repo_root, audit)
    decision_packet = write_decision_packet(repo_root, audit, proposal)
    readiness = write_stage3c3_readiness(repo_root, audit, split, proposal)
    artifacts = {
        "dev_v1_manifest": f"research/data/snapshots/{DEV_V1_ID}/manifest.yaml",
        "coverage_audit": repo_rel(repo_root, coverage_md),
        "split_v2_policy": "research/data/splits/futures-dev-validation-v2-policy.yaml",
        "policy_proposal": "research/evaluation/evaluation-policy-proposal.yaml",
        "decision_packet": repo_rel(repo_root, decision_packet),
        "stage3c3_readiness": "research/evaluation/stage3c3-readiness.json",
        "final_json_report": "research/results/stage3c2r-readiness/stage3c2r-final-report.json",
    }
    final = write_final_report(repo_root, audit, split, proposal, readiness, artifacts)
    artifacts = final["artifacts"]
    write_registry(repo_root, dev_manifest, split, proposal, readiness, final, artifacts)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Stage 3C.2-R readiness and policy artifacts.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build(Path.cwd())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{result['status']}: {result['blocker']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
