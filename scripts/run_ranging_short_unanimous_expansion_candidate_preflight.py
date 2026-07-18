#!/usr/bin/env python3
"""Run the approved Development-only, zero-backtest Candidate coverage preflight."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from export_director_registry import export_registry
from protected_manifest_hash import validate_protected_manifests
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
)


PROPOSAL_ID = "ranging-short-router-unanimous-expansion-candidate-preparation-v1"
DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
PAIR = "BTC/USDT:USDT"
PREFIX = "BTC_USDT_USDT"
APPROVAL_PATH = Path(
    "research/governance/approvals/"
    f"{PROPOSAL_ID}-approval.json"
)
PROPOSAL_PATH = Path(
    "research/director/next-after-router-indicator-direction-review/proposals/"
    f"{PROPOSAL_ID}.json"
)
CONTRACT_PATH = Path(
    "research/governance/ranging-short-router-indicator-direction-contract-v1.json"
)
SLICE_POLICY_PATH = Path(
    "research/temporal/ranging-short-ablation-temporal-slices-v1.yaml"
)
DATASET_MANIFEST_PATH = Path(
    f"research/data/snapshots/{DATASET_ID}/manifest.yaml"
)
REHYDRATION_PATH = Path(
    f"research/analysis/{PROPOSAL_ID}/data-rehydration-audit.json"
)
OUTPUT_ROOT = Path(f"research/analysis/{PROPOSAL_ID}")
PREFLIGHT_PATH = OUTPUT_ROOT / "coverage-preflight.json"
DECISION_PATH = OUTPUT_ROOT / "candidate-preparation-decision.json"
REPORT_PATH = OUTPUT_ROOT / "final-report.md"
NEXT_PROPOSAL_PATH = Path(
    "research/director/next-after-unanimous-expansion-candidate-preparation/"
    "proposals/ranging-short-router-unanimous-expansion-development-evaluation-v1.json"
)
STATE_PATH = Path("research/director/current-research-state.json")
STATE_MD_PATH = Path("research/director/current-research-state.md")
REGISTRY_PATH = Path("research/registry/stage4a-director.db")
REGISTRY_EXPORT_PATH = Path("research/director/registry-records.json")
COMPLETED_AT = "2026-07-18T18:58:08Z"


class CandidatePreflightInvalid(RuntimeError):
    """Raised when authority, data, direction replay or Candidate coverage drifts."""


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _in_window(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    timestamps = pd.to_datetime(frame["date"], utc=True)
    return frame.loc[
        (timestamps >= pd.Timestamp(start)) & (timestamps < pd.Timestamp(end))
    ].copy()


def _load_candidate(repo: Path, approval: dict[str, Any]):
    binding = approval["candidate_binding"]
    source = repo / binding["source_path"]
    spec = importlib.util.spec_from_file_location(
        "unanimous_expansion_candidate", source
    )
    if spec is None or spec.loader is None:
        raise CandidatePreflightInvalid("candidate_import_spec_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, binding["class_name"])


def validate_authority(repo: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    approval = load_document(repo / APPROVAL_PATH)
    proposal = load_document(repo / PROPOSAL_PATH)
    manifest = load_document(repo / approval["candidate_binding"]["manifest_path"])
    direction_contract = load_document(repo / CONTRACT_PATH)
    dataset = load_document(repo / DATASET_MANIFEST_PATH)
    rehydration = load_document(repo / REHYDRATION_PATH)
    authority = approval["authority"]
    frozen = approval["frozen_inputs"]
    binding = approval["candidate_binding"]
    checks = {
        "human_approval": (
            approval["proposal_id"] == PROPOSAL_ID
            and approval["approval_status"] == "approved"
            and approval["approver_type"] == "human_user"
        ),
        "proposal_identity_and_budget": (
            proposal["proposal_id"] == PROPOSAL_ID
            and proposal["status"] == "pending_human_review"
            and proposal["execution_budget"]
            == {
                "backtest_calls": 0,
                "candidate_creations": 1,
                "coverage_preflights": 1,
                "holdout_accesses": 0,
                "validation_accesses": 0,
            }
        ),
        "authority_scope": (
            authority["create_candidate"] is True
            and authority["maximum_candidates"] == 1
            and authority["maximum_coverage_preflights"] == 1
            and authority["run_backtest"] is False
            and authority["read_outcome_metrics"] is False
            and authority["search_thresholds"] is False
            and authority["access_validation"] is False
            and authority["access_holdout"] is False
            and authority["automatic_followup_execution"] is False
        ),
        "frozen_input_hashes": (
            sha256_file(repo / PROPOSAL_PATH) == frozen["proposal_sha256"]
            and sha256_file(repo / CONTRACT_PATH)
            == frozen["direction_contract_sha256"]
            and sha256_file(repo / SLICE_POLICY_PATH)
            == frozen["slice_policy_sha256"]
            and sha256_file(repo / DATASET_MANIFEST_PATH)
            == frozen["dataset_manifest_sha256"]
        ),
        "direction_contract": (
            direction_contract["future_single_variable_gate"]["gate_id"]
            == "block_unanimous_router_indicator_expansion"
            and direction_contract["future_single_variable_gate"]["blocked_topology"]
            == "U-U-U"
            and direction_contract["inputs"]["order"]
            == ["adx", "bb_width", "atr"]
        ),
        "candidate_binding": (
            manifest["candidate_count"] == 1
            and manifest["source_path"] == binding["source_path"]
            and manifest["source_sha256"] == binding["source_sha256"]
            and sha256_file(repo / binding["source_path"])
            == binding["source_sha256"]
            and sha256_file(repo / binding["manifest_path"])
            == binding["manifest_sha256"]
        ),
        "formal_sources_unchanged": all(
            sha256_file(repo / path) == expected
            for path, expected in approval["formal_source_hashes"].items()
        ),
        "dataset_identity": (
            dataset["dataset_id"] == DATASET_ID
            and dataset["intended_use"] == "development"
            and dataset["sealed"] is True
            and dataset["aggregate_sha256"]
            == "3e86474ba634c3779389d818997d1626357090da7fef6b9f007ad0f9bbcfdd5c"
        ),
        "exact_local_rehydration": (
            rehydration["dataset_id"] == DATASET_ID
            and rehydration["passed"] is True
            and rehydration["network_accessed"] is False
            and rehydration["validation_accesses"] == 0
            and rehydration["holdout_accesses"] == 0
            and len(rehydration["files"]) == 4
            and all(item["passed"] for item in rehydration["files"])
            and all(
                sha256_file(repo / item["target"]) == item["expected"]["sha256"]
                for item in rehydration["files"]
            )
        ),
        "protected_manifests": validate_protected_manifests(repo)["passed"],
    }
    if not all(checks.values()):
        raise CandidatePreflightInvalid(
            "candidate_preflight_authority_invalid:"
            + json.dumps(checks, sort_keys=True)
        )
    return checks, approval


def _direction(current: float, previous: float) -> str:
    if current > previous:
        return "U"
    if current < previous:
        return "D"
    return "F"


def evaluate_slice(
    repo: Path, candidate_class: type, slice_spec: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data_root = repo / f"research/data/snapshots/{DATASET_ID}/data/futures"

    class DataProvider:
        def current_whitelist(self) -> list[str]:
            return [PAIR]

        def get_pair_dataframe(
            self, pair: str, timeframe: str, candle_type: str = "futures"
        ) -> pd.DataFrame:
            if pair != PAIR or timeframe != "4h" or candle_type != "futures":
                raise CandidatePreflightInvalid("unauthorized_preflight_data_input")
            informative = pd.read_feather(
                data_root / f"{PREFIX}-4h-futures.feather"
            )
            return _in_window(
                informative,
                slice_spec["warmup_start"],
                slice_spec["evaluation_end_exclusive"],
            )

    raw = pd.read_feather(data_root / f"{PREFIX}-1h-futures.feather")
    raw = _in_window(
        raw,
        slice_spec["warmup_start"],
        slice_spec["evaluation_end_exclusive"],
    )
    strategy = candidate_class({})
    strategy.dp = DataProvider()
    frame = strategy.populate_indicators(raw.copy(), {"pair": PAIR})
    frame = strategy.populate_entry_trend(frame, {"pair": PAIR})

    columns = ("adx_4h", "bb_width_4h", "atr_4h")
    informative = (
        frame[["date_4h", *columns]]
        .dropna(subset=["date_4h"])
        .drop_duplicates("date_4h", keep="first")
        .sort_values("date_4h")
        .copy()
    )
    for column in columns:
        informative[f"previous_{column}"] = informative[column].shift(1)
        informative[f"replay_{column}_direction"] = [
            _direction(current, previous)
            for current, previous in zip(
                informative[column], informative[f"previous_{column}"]
            )
        ]
    informative["replay_topology"] = informative[
        [f"replay_{column}_direction" for column in columns]
    ].agg("-".join, axis=1)
    frame = frame.merge(
        informative[
            [
                "date_4h",
                "replay_topology",
                *[f"previous_{column}" for column in columns],
            ]
        ],
        on="date_4h",
        how="left",
    )
    frame = _in_window(
        frame,
        slice_spec["evaluation_start"],
        slice_spec["evaluation_end_exclusive"],
    )
    if len(frame) != slice_spec["evaluation_1h_candle_count"]:
        raise CandidatePreflightInvalid(
            f"coverage_slice_row_count_mismatch:{slice_spec['slice_id']}:{len(frame)}"
        )

    pre_gate = frame["research_ranging_short_entry_pre_gate"].astype(bool)
    blocked = frame["research_unanimous_expansion_blocked"].astype(bool)
    candidate_remaining = (
        (frame["enter_short"].fillna(0).astype(int) == 1)
        & (frame["enter_tag"] == "ranging_short")
    )
    rows = []
    for _, row in frame.loc[pre_gate].iterrows():
        signal_at = pd.Timestamp(row["date"])
        informative_at = pd.Timestamp(row["date_4h"])
        topology = row["replay_topology"]
        row_checks = {
            "candidate_topology_matches_raw_replay": (
                row["research_router_indicator_direction_topology"] == topology
            ),
            "current_informative_completed_by_decision": (
                informative_at + timedelta(hours=4)
                <= signal_at + timedelta(hours=1)
            ),
            "blocked_iff_unanimous_expansion": bool(row["research_unanimous_expansion_blocked"])
            == (topology == "U-U-U"),
        }
        rows.append(
            {
                "slice_id": slice_spec["slice_id"],
                "signal_timestamp": signal_at.isoformat(),
                "signal_decision_at": (signal_at + timedelta(hours=1)).isoformat(),
                "informative_timestamp": informative_at.isoformat(),
                "informative_available_at": (
                    informative_at + timedelta(hours=4)
                ).isoformat(),
                "topology": topology,
                "candidate_topology": row[
                    "research_router_indicator_direction_topology"
                ],
                "current": {
                    column.replace("_4h", ""): float(row[column])
                    for column in columns
                },
                "previous": {
                    column.replace("_4h", ""): float(
                        row[f"previous_{column}"]
                    )
                    for column in columns
                },
                "blocked": bool(row["research_unanimous_expansion_blocked"]),
                "checks": row_checks,
            }
        )
    return (
        {
            "slice_id": slice_spec["slice_id"],
            "split_fingerprint": slice_spec["split_fingerprint"],
            "evaluation_rows": int(len(frame)),
            "pre_gate_signals": int(pre_gate.sum()),
            "blocked_signals": int(blocked.sum()),
            "candidate_remaining_signals": int(candidate_remaining.sum()),
            "direction_counts": dict(
                sorted(Counter(row["topology"] for row in rows).items())
            ),
        },
        rows,
    )


def run_preflight(repo: Path) -> dict[str, Any]:
    authority_checks, approval = validate_authority(repo)
    policy = load_document(repo / SLICE_POLICY_PATH)
    candidate_class = _load_candidate(repo, approval)
    slices = []
    rows = []
    for slice_spec in policy["slices"]:
        result, result_rows = evaluate_slice(repo, candidate_class, slice_spec)
        slices.append(result)
        rows.extend(result_rows)
    counts = dict(sorted(Counter(row["topology"] for row in rows).items()))
    by_slice: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_slice[row["slice_id"]][row["topology"]] += 1
    violations = [
        row for row in rows if not all(row["checks"].values())
    ]
    totals = {
        "evaluation_rows": sum(item["evaluation_rows"] for item in slices),
        "pre_gate_signals": len(rows),
        "blocked_signals": sum(row["blocked"] for row in rows),
        "candidate_remaining_signals": sum(not row["blocked"] for row in rows),
    }
    gate_checks = {
        "source_population_exact": totals["pre_gate_signals"] == 12,
        "direction_partition_exact": counts
        == {"D-D-D": 2, "U-U-D": 5, "U-U-U": 5},
        "blocked_population_exact": totals["blocked_signals"] == 5,
        "retained_population_exact": totals["candidate_remaining_signals"] == 7,
        "raw_candidate_alignment_exact": not violations,
        "zero_lookahead_violations": not violations,
        "four_slices_complete": totals["evaluation_rows"] == 5000,
    }
    passed = all(gate_checks.values())
    result = {
        "schema_version": "unanimous-expansion-candidate-coverage-preflight-v1",
        "proposal_id": PROPOSAL_ID,
        "dataset_id": DATASET_ID,
        "authority_checks": authority_checks,
        "candidate": approval["candidate_binding"],
        "data_access": {
            "development_only": True,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        },
        "gate": {
            "gate_id": "block_unanimous_router_indicator_expansion",
            "blocked_topology": "U-U-U",
            "checks": gate_checks,
            "passed": passed,
            "failure_code": None if passed else "candidate_coverage_preflight_failed",
        },
        "direction_counts": counts,
        "direction_counts_by_slice": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_slice.items())
        },
        "totals": totals,
        "alignment_violation_count": len(violations),
        "rows": rows,
        "slices": slices,
        "execution": {
            "backtest_calls": 0,
            "outcome_metrics_read": False,
            "threshold_search_run": False,
            "formal_strategy_modified": False,
            "router_modified": False,
            "automatic_followup_executed": False,
        },
    }
    result["preflight_fingerprint"] = fingerprint(result)
    if not passed:
        raise CandidatePreflightInvalid(
            "candidate_coverage_preflight_failed:"
            + json.dumps(gate_checks, sort_keys=True)
        )
    return result


def build_decision(preflight: dict[str, Any]) -> dict[str, Any]:
    decision = {
        "schema_version": "unanimous-expansion-candidate-preparation-decision-v1",
        "proposal_id": PROPOSAL_ID,
        "decision": "candidate_frozen_coverage_preflight_passed_backtest_not_authorized",
        "candidate_status": "frozen_ready_for_separate_development_evaluation_review",
        "coverage_preflight_passed": True,
        "pre_gate_signals": 12,
        "blocked_signals": 5,
        "retained_signals": 7,
        "direction_partition": preflight["direction_counts"],
        "lookahead_violation_count": preflight["alignment_violation_count"],
        "backtest_authorized_now": False,
        "backtest_calls": 0,
        "outcome_metrics_read": False,
        "validation_authorized": False,
        "holdout_authorized": False,
        "formal_strategy_modified": False,
        "automatic_followup_authorized": False,
        "next_proposal_id": "ranging-short-router-unanimous-expansion-development-evaluation-v1",
        "next_proposal_status": "pending_human_review",
    }
    decision["decision_fingerprint"] = fingerprint(decision)
    return decision


def build_next_proposal(decision: dict[str, Any]) -> dict[str, Any]:
    proposal = {
        "schema_version": "research-proposal-v1",
        "proposal_id": decision["next_proposal_id"],
        "title": "Evaluate the frozen unanimous-expansion blocker on Development",
        "status": "pending_human_review",
        "automatic_execution": False,
        "risk_class": "high",
        "objective": "Measure the frozen Candidate against the unchanged formal strategy on the four Development slices without validation or holdout access.",
        "preconditions": [
            "candidate source and manifest hashes remain frozen",
            "coverage preflight remains passed with 12/5/7 source-blocked-retained signals",
            "separate human approval is recorded before any backtest call",
        ],
        "allowed_scope_after_human_approval": [
            "compile a Development-only paired baseline/Candidate campaign",
            "run bounded paired backtests on the four frozen Development slices",
            "compare branch and portfolio outcomes under the frozen evaluation policy",
        ],
        "forbidden_scope": [
            "validation",
            "holdout",
            "candidate mutation",
            "continuous threshold search",
            "formal strategy change",
            "automatic followup execution",
        ],
        "execution_budget": {
            "candidate_creations": 0,
            "backtest_calls": 8,
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "retries": 0,
        },
    }
    proposal["semantic_fingerprint"] = fingerprint(proposal)
    return proposal


def update_state(repo: Path, decision: dict[str, Any]) -> None:
    state = load_document(repo / STATE_PATH)
    state["ranging_short_router_unanimous_expansion_candidate_preparation"] = {
        "proposal_id": PROPOSAL_ID,
        "status": "completed_candidate_frozen",
        "decision": decision["decision"],
        "decision_fingerprint": decision["decision_fingerprint"],
        "candidate_count": 1,
        "pre_gate_signals": 12,
        "blocked_signals": 5,
        "retained_signals": 7,
        "direction_partition": decision["direction_partition"],
        "lookahead_violation_count": 0,
        "backtest_calls": 0,
        "outcome_metrics_read": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "formal_strategy_modified": False,
        "next_proposal_id": decision["next_proposal_id"],
        "next_proposal_status": decision["next_proposal_status"],
        "evidence": [
            REHYDRATION_PATH.as_posix(),
            PREFLIGHT_PATH.as_posix(),
            DECISION_PATH.as_posix(),
            REPORT_PATH.as_posix(),
            NEXT_PROPOSAL_PATH.as_posix(),
        ],
    }
    write_json(repo / STATE_PATH, state)
    (repo / STATE_MD_PATH).write_text(
        "\n".join(
            [
                "# 当前研究状态",
                "",
                f"- 当前项目：`{PROPOSAL_ID}`",
                "- 状态：`completed_candidate_frozen`",
                f"- 决策：`{decision['decision']}`",
                "- 原始 Development 数据：已从本地封存谱系精确恢复，4/4 文件哈希一致",
                "- 方向覆盖：`D-D-D=2 / U-U-D=5 / U-U-U=5`",
                "- Candidate gate：阻止 `U-U-U=5`，保留 `7` 个 ranging-short pre-gate 信号",
                "- Lookahead 违规：`0`",
                "- Backtest / Validation / Holdout：`0 / 0 / 0`",
                "- 正式策略：保留且未修改",
                f"- 下一提案：`{decision['next_proposal_id']}` / `pending_human_review`",
                "",
                f"报告：`{REPORT_PATH.as_posix()}`。",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )


def _restore_registry_from_export(repo: Path) -> sqlite3.Connection:
    connection = open_director_registry(repo / REGISTRY_PATH)
    tracked = load_document(repo / REGISTRY_EXPORT_PATH)
    for table, rows in (tracked.get("tables") or {}).items():
        columns = {
            row[1]
            for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
        if not columns:
            continue
        for row in rows:
            names = [name for name in row if name in columns]
            placeholders = ",".join("?" for _ in names)
            quoted = ",".join(f'"{name}"' for name in names)
            connection.execute(
                f'INSERT OR REPLACE INTO "{table}" ({quoted}) VALUES ({placeholders})',
                [row[name] for name in names],
            )
    connection.commit()
    return connection


def record_registry(repo: Path, decision: dict[str, Any]) -> None:
    connection = _restore_registry_from_export(repo)
    run_id = f"{PROPOSAL_ID}-coverage-preflight-1"
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs("
        "run_id,campaign_id,proposal_id,status,result_code,campaign_executed,"
        "candidate_created,strategy_modified,validation_accesses,holdout_accesses,"
        "payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            f"stage4a-{PROPOSAL_ID}",
            PROPOSAL_ID,
            "completed_candidate_frozen",
            decision["decision"],
            1,
            1,
            0,
            0,
            0,
            json.dumps(decision, sort_keys=True),
            COMPLETED_AT,
        ),
    )
    assets = [
        APPROVAL_PATH,
        REHYDRATION_PATH,
        PREFLIGHT_PATH,
        DECISION_PATH,
        REPORT_PATH,
        NEXT_PROPOSAL_PATH,
    ]
    for optional in (
        OUTPUT_ROOT / "data-layer-reliability-audit.json",
        OUTPUT_ROOT / "data-layer-reliability-audit.md",
    ):
        if (repo / optional).is_file():
            assets.append(optional)
    for path in assets:
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets("
            "asset_id,run_id,artifact_type,path,sha256,created_at) VALUES(?,?,?,?,?,?)",
            (
                f"{PROPOSAL_ID}:{path.as_posix()}",
                run_id,
                "candidate_preparation_and_data_reliability_audit",
                path.as_posix(),
                sha256_file(repo / path),
                COMPLETED_AT,
            ),
        )
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise CandidatePreflightInvalid("registry_integrity_failed")
    write_json(repo / REGISTRY_EXPORT_PATH, export_registry(str(repo / REGISTRY_PATH)))


def report_text(decision: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# U-U-U Candidate 准备报告",
            "",
            "## 结论",
            "",
            "已从本地封存谱系精确恢复 development v2 原始数据，4 个 Feather 文件的字节数和 SHA-256 均与冻结清单一致。",
            "",
            "唯一 Candidate 已冻结。原始指标复现得到 12 个 `ranging_short` pre-gate 信号，方向分区为 `D-D-D=2 / U-U-D=5 / U-U-U=5`；Candidate 仅阻止 `U-U-U` 的 5 个信号并保留 7 个，完成 K 线对齐违规为 0。",
            "",
            "## 执行边界",
            "",
            "本批没有运行回测、没有读取收益指标、没有访问 validation 或 holdout、没有搜索阈值，也没有修改正式策略。",
            "",
            "## 下一步",
            "",
            f"下一提案 `{decision['next_proposal_id']}` 需要单独人工审批；当前不自动执行。",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--update-current-state", action="store_true")
    parser.add_argument("--record-registry", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    preflight = run_preflight(repo)
    decision = build_decision(preflight)
    if args.write:
        write_json(repo / PREFLIGHT_PATH, preflight)
        write_json(repo / DECISION_PATH, decision)
        write_json(repo / NEXT_PROPOSAL_PATH, build_next_proposal(decision))
        report = repo / REPORT_PATH
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(report_text(decision), encoding="utf-8", newline="\n")
        if args.update_current_state:
            update_state(repo, decision)
        if args.record_registry:
            record_registry(repo, decision)
    print(
        json.dumps(
            {
                "status": decision["decision"],
                "direction_partition": decision["direction_partition"],
                "blocked": decision["blocked_signals"],
                "retained": decision["retained_signals"],
                "backtest_calls": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
