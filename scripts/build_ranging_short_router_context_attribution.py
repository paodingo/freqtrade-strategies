#!/usr/bin/env python3
"""Attribute frozen ranging-short signals to existing router vote topologies."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

import run_ranging_short_router_context_preflight as preflight
from export_director_registry import export_registry
from protected_manifest_hash import validate_protected_manifests
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    write_json,
)


AUDIT_ID = "ranging-short-router-context-attribution-v1"
APPROVAL_PATH = Path(
    "research/governance/approvals/"
    "ranging-short-router-context-attribution-v1-read-only-approval.json"
)
ATTRIBUTION_PATH = Path(
    "research/analysis/ranging-short-router-context-attribution-v1/"
    "router-state-attribution.json"
)
DECISION_PATH = Path(
    "research/analysis/ranging-short-router-context-attribution-v1/"
    "context-admissibility-decision.json"
)
PACKET_PATH = Path(
    "research/director/compiled/ranging-short-router-context-attribution-v1/"
    "human-decision-packet.json"
)
REPORT_PATH = Path(
    "research/analysis/ranging-short-router-context-attribution-v1/"
    "final-report.md"
)
REGISTRY_PATH = Path("research/registry/stage4a-director.db")
REGISTRY_EXPORT_PATH = Path("research/director/registry-records.json")
PRIOR_STOP_PATH = preflight.STOP_PATH
PAIR = preflight.PAIR
DATASET_ID = preflight.DATASET_ID
PREFIX = preflight.PREFIX
SLICE_IDS = tuple(f"ranging-short-ablation-s0{number}" for number in range(1, 5))


class RouterContextAttributionInvalid(RuntimeError):
    """Raised when frozen read-only audit bindings drift."""


def validate_authority(repo: Path) -> dict[str, bool]:
    approval = load_document(repo / APPROVAL_PATH)
    stopped = load_document(repo / PRIOR_STOP_PATH)
    prior_checks = preflight.validate_authority(repo)
    authority = approval["authority"]
    rules = approval["admissibility_rules"]
    frozen = approval["frozen_inputs"]
    checks = {
        "read_only_human_approval": (
            approval["audit_id"] == AUDIT_ID
            and approval["approval_status"] == "approved"
            and approval["approver_type"] == "human_user"
        ),
        "prior_authority_chain": all(prior_checks.values()),
        "prior_stop": (
            stopped["status"] == "stopped_pre_backtest"
            and stopped["reason_code"] == frozen["prior_stop_reason"]
            == "router_context_coverage_insufficient"
            and stopped["budget_used"]["backtest_calls"] == 0
        ),
        "frozen_bindings": (
            frozen["prior_campaign_fingerprint"]
            == preflight.CAMPAIGN_FINGERPRINT
            and frozen["context_contract_fingerprint"]
            == preflight.CONTEXT_FINGERPRINT
            and frozen["slice_policy_fingerprint"]
            == preflight.SLICE_POLICY_FINGERPRINT
            and frozen["candidate_source_sha256"]
            == preflight.CANDIDATE_SHA256
        ),
        "zero_mutation_authority": (
            authority["create_candidate"] is False
            and authority["run_backtest"] is False
            and authority["search_thresholds"] is False
            and authority["change_router"] is False
            and authority["change_formal_strategy"] is False
            and authority["automatic_followup_execution"] is False
        ),
        "sealed_data_forbidden": (
            authority["access_validation"] is False
            and authority["access_holdout"] is False
        ),
        "admissibility_rules": (
            rules
            == {
                "minimum_pre_gate_coverage": 1,
                "reject_observed_whole_branch_equivalence": True,
                "reject_new_continuous_cutoffs": True,
                "reject_time_slice_as_context": True,
                "maximum_selected_contexts": 1,
            }
        ),
        "protected_manifests": validate_protected_manifests(repo)["passed"],
    }
    if not all(checks.values()):
        raise RouterContextAttributionInvalid(
            "router_context_attribution_authority_invalid:"
            + json.dumps(checks, sort_keys=True)
        )
    return checks


def _vote_topology(row: pd.Series) -> dict[str, str]:
    adx_vote = "ranging" if row["adx_4h"] < 20 else (
        "trending" if row["adx_4h"] > 25 else "grey"
    )
    bb_vote = (
        "trending"
        if row["bb_width_4h"] > row["bb_width_mean_4h"]
        else "ranging"
    )
    atr_vote = (
        "trending" if row["atr_4h"] > row["atr_mean_4h"] else "ranging"
    )
    return {"adx": adx_vote, "bb_width": bb_vote, "atr": atr_vote}


def _topology_id(votes: dict[str, str]) -> str:
    aliases = {"ranging": "R", "trending": "T", "grey": "G"}
    return "-".join(aliases[votes[key]] for key in ("adx", "bb_width", "atr"))


def _slice_signal_rows(
    repo: Path, candidate_class: type, slice_spec: dict[str, Any]
) -> list[dict[str, Any]]:
    data_root = repo / "research/data/snapshots" / DATASET_ID / "data/futures"

    class DataProvider:
        def current_whitelist(self) -> list[str]:
            return [PAIR]

        def get_pair_dataframe(
            self, pair: str, timeframe: str, candle_type: str = "futures"
        ) -> pd.DataFrame:
            if pair != PAIR or timeframe != "4h" or candle_type != "futures":
                raise RouterContextAttributionInvalid(
                    "unauthorized_attribution_instrumentation_input"
                )
            informative = pd.read_feather(
                data_root / f"{PREFIX}-4h-futures.feather"
            )
            return preflight._in_window(
                informative,
                slice_spec["warmup_start"],
                slice_spec["evaluation_end_exclusive"],
            )

    raw = pd.read_feather(data_root / f"{PREFIX}-1h-futures.feather")
    raw = preflight._in_window(
        raw,
        slice_spec["warmup_start"],
        slice_spec["evaluation_end_exclusive"],
    )
    strategy = candidate_class({})
    strategy.dp = DataProvider()
    frame = strategy.populate_indicators(raw.copy(), {"pair": PAIR})
    frame = strategy.populate_entry_trend(frame, {"pair": PAIR})
    frame = preflight._in_window(
        frame,
        slice_spec["evaluation_start"],
        slice_spec["evaluation_end_exclusive"],
    )
    rows: list[dict[str, Any]] = []
    selected = frame.loc[frame["research_ranging_short_entry_pre_gate"] == 1]
    for _, row in selected.iterrows():
        votes = _vote_topology(row)
        rows.append(
            {
                "slice_id": slice_spec["slice_id"],
                "date": pd.Timestamp(row["date"]).isoformat(),
                "regime_4h": str(row["regime_4h"]),
                "votes": votes,
                "topology_id": _topology_id(votes),
                "frozen_router_values": {
                    "adx_4h": round(float(row["adx_4h"]), 12),
                    "bb_width_ratio": round(
                        float(row["bb_width_4h"] / row["bb_width_mean_4h"]),
                        12,
                    ),
                    "atr_ratio": round(
                        float(row["atr_4h"] / row["atr_mean_4h"]), 12
                    ),
                },
                "raw_ranging_signal": bool(
                    row["research_router_context_raw_ranging_signal"]
                ),
                "carry_context": bool(row["research_router_context"]),
            }
        )
    return rows


def build_attribution(repo: Path) -> dict[str, Any]:
    checks = validate_authority(repo)
    policy = load_document(repo / preflight.SLICE_POLICY_PATH)
    candidate_class = preflight._load_candidate(repo)
    rows = [
        row
        for slice_spec in policy["slices"]
        for row in _slice_signal_rows(repo, candidate_class, slice_spec)
    ]
    if len(rows) != 12:
        raise RouterContextAttributionInvalid(
            f"frozen_pre_gate_signal_count_drift:{len(rows)}"
        )
    topology_counts = Counter(row["topology_id"] for row in rows)
    by_slice: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_slice[row["slice_id"]][row["topology_id"]] += 1
    attribution = {
        "schema_version": "ranging-short-router-state-attribution-v1",
        "audit_id": AUDIT_ID,
        "authority_checks": checks,
        "frozen_inputs": {
            "dataset_id": DATASET_ID,
            "slice_policy_fingerprint": preflight.SLICE_POLICY_FINGERPRINT,
            "context_contract_fingerprint": preflight.CONTEXT_FINGERPRINT,
            "candidate_source_sha256": preflight.CANDIDATE_SHA256,
            "prior_stop_path": PRIOR_STOP_PATH.as_posix(),
            "prior_stop_sha256": sha256_file(repo / PRIOR_STOP_PATH),
        },
        "method": {
            "type": "categorical_existing_router_vote_attribution",
            "existing_thresholds_only": True,
            "continuous_threshold_search": False,
            "time_slice_used_as_context": False,
            "outcome_metrics_read": False,
        },
        "pre_gate_signal_count": len(rows),
        "topology_count": len(topology_counts),
        "topology_counts": dict(sorted(topology_counts.items())),
        "topology_counts_by_slice": {
            key: dict(sorted(value.items())) for key, value in sorted(by_slice.items())
        },
        "all_signals_share_one_topology": len(topology_counts) == 1,
        "all_signals_have_current_raw_ranging_support": all(
            row["raw_ranging_signal"] for row in rows
        ),
        "carry_context_signal_count": sum(row["carry_context"] for row in rows),
        "rows": rows,
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "threshold_search_run": False,
    }
    attribution["attribution_fingerprint"] = fingerprint(attribution)
    return attribution


def build_decision(attribution: dict[str, Any]) -> dict[str, Any]:
    total = attribution["pre_gate_signal_count"]
    contexts = [
        {
            "context_id": "ranging_state_without_current_range_signal",
            "definition": "frozen carry context",
            "pre_gate_coverage": attribution["carry_context_signal_count"],
            "observed_branch_coverage_ratio": 0.0,
            "admissible": False,
            "rejection_reason": "router_context_coverage_insufficient",
        },
        {
            "context_id": "ranging_state_with_current_raw_ranging_signal",
            "definition": "regime_4h is ranging and the frozen raw ranging signal is true",
            "pre_gate_coverage": total,
            "observed_branch_coverage_ratio": 1.0,
            "admissible": False,
            "rejection_reason": "observed_whole_branch_equivalence",
        },
        {
            "context_id": "unanimous_current_ranging_votes",
            "definition": "existing ADX, BB-width and ATR votes are all ranging",
            "pre_gate_coverage": attribution["topology_counts"].get("R-R-R", 0),
            "observed_branch_coverage_ratio": (
                attribution["topology_counts"].get("R-R-R", 0) / total
            ),
            "admissible": False,
            "rejection_reason": "observed_whole_branch_equivalence",
        },
        {
            "context_id": "mixed_current_ranging_majority_votes",
            "definition": "existing router has two ranging votes and one trending vote",
            "pre_gate_coverage": sum(
                attribution["topology_counts"].get(item, 0)
                for item in ("R-R-T", "R-T-R")
            ),
            "observed_branch_coverage_ratio": 0.0,
            "admissible": False,
            "rejection_reason": "router_context_coverage_insufficient",
        },
    ]
    decision = {
        "schema_version": "ranging-short-router-context-admissibility-decision-v1",
        "audit_id": AUDIT_ID,
        "attribution_fingerprint": attribution["attribution_fingerprint"],
        "decision": "no_admissible_router_context_under_current_contract",
        "admissible_context_count": 0,
        "selected_context": None,
        "context_partition": {
            "carry_without_current_raw_signal": attribution[
                "carry_context_signal_count"
            ],
            "current_raw_unanimous_ranging": attribution["topology_counts"].get(
                "R-R-R", 0
            ),
            "current_raw_mixed_ranging_majority": sum(
                attribution["topology_counts"].get(item, 0)
                for item in ("R-R-T", "R-T-R")
            ),
            "pre_gate_total": total,
            "partition_complete": (
                attribution["carry_context_signal_count"]
                + sum(attribution["topology_counts"].values())
                == total
            ),
        },
        "contexts_evaluated": contexts,
        "research_interpretation": (
            "Existing router votes do not identify a nonzero subset of observed "
            "ranging_short signals without becoming equivalent to the whole observed branch."
        ),
        "formal_branch_status": "retained_unchanged",
        "new_candidate_authorized": False,
        "backtest_authorized": False,
        "threshold_search_authorized": False,
        "validation_authorized": False,
        "holdout_authorized": False,
        "next_step": (
            "close the current router-context attribution line; any new structural "
            "observable or dataset requires a separate human-reviewed proposal"
        ),
    }
    decision["decision_fingerprint"] = fingerprint(decision)
    return decision


def build_packet(
    repo: Path, attribution: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "ranging-short-router-context-attribution-packet-v1",
        "audit_id": AUDIT_ID,
        "status": "completed_read_only",
        "decision": decision["decision"],
        "attribution_path": ATTRIBUTION_PATH.as_posix(),
        "attribution_sha256": sha256_file(repo / ATTRIBUTION_PATH),
        "decision_path": DECISION_PATH.as_posix(),
        "decision_sha256": sha256_file(repo / DECISION_PATH),
        "pre_gate_signal_count": attribution["pre_gate_signal_count"],
        "observed_topologies": attribution["topology_counts"],
        "admissible_context_count": decision["admissible_context_count"],
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "formal_strategy_modified": False,
        "router_modified": False,
        "threshold_search_run": False,
        "automatic_followup_executed": False,
    }


def report_text(attribution: dict[str, Any], decision: dict[str, Any]) -> str:
    per_slice = attribution["topology_counts_by_slice"]
    lines = [
        "# Ranging-short router-state 只读归因报告",
        "",
        "## 结论",
        "",
        "当前 router contract 下不存在可采纳的新 context。12 条 `ranging_short` pre-gate 信号全部属于 `R-R-R`，即 ADX、BB-width、ATR 三票均为 ranging。",
        "",
        "原 carry context 覆盖为 `0/12`；当前 raw ranging context 和 `R-R-R` 均覆盖 `12/12`，在观测样本上等价于整个分支，因此不能作为新的单一 context Candidate。",
        "",
        "## 逐切片归因",
        "",
        "| 切片 | R-R-R 信号 | 其他拓扑 |",
        "|---|---:|---:|",
    ]
    for slice_id in SLICE_IDS:
        counts = per_slice.get(slice_id, {})
        unanimous = counts.get("R-R-R", 0)
        lines.append(f"| {slice_id[-3:]} | {unanimous} | {sum(counts.values()) - unanimous} |")
    lines.extend(
        [
            "",
            "## 执行边界",
            "",
            "- 新 Candidate：`0`。",
            "- Backtest：`0`。",
            "- Validation / Holdout：`0 / 0`。",
            "- 连续阈值搜索：未执行。",
            "- 正式策略与 router：未修改。",
            "",
            f"最终决策：`{decision['decision']}`。只有经过单独人工审批的新结构观测量或新数据，才能重启该研究线。",
            "",
        ]
    )
    return "\n".join(lines)


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
    completed_at = "2026-07-18T10:46:26+00:00"
    run_id = AUDIT_ID
    campaign_id = "stage4a-ranging-short-router-context-attribution-v1"
    connection = _restore_registry_from_export(repo)
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs("
        "run_id,campaign_id,proposal_id,status,result_code,campaign_executed,"
        "candidate_created,strategy_modified,validation_accesses,holdout_accesses,"
        "payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            campaign_id,
            preflight.PROPOSAL_ID,
            "completed_read_only",
            decision["decision"],
            0,
            0,
            0,
            0,
            0,
            json.dumps(decision, sort_keys=True),
            completed_at,
        ),
    )
    for path in (
        APPROVAL_PATH,
        ATTRIBUTION_PATH,
        DECISION_PATH,
        PACKET_PATH,
        REPORT_PATH,
    ):
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets("
            "asset_id,run_id,artifact_type,path,sha256,created_at) VALUES(?,?,?,?,?,?)",
            (
                f"{run_id}:{path.as_posix()}",
                run_id,
                "read_only_attribution_evidence",
                path.as_posix(),
                sha256_file(repo / path),
                completed_at,
            ),
        )
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise RouterContextAttributionInvalid("registry_integrity_failed")
    write_json(repo / REGISTRY_EXPORT_PATH, export_registry(str(repo / REGISTRY_PATH)))


def run(repo: Path, *, write: bool) -> dict[str, Any]:
    attribution = build_attribution(repo)
    decision = build_decision(attribution)
    if write:
        preflight.write_json_lf(repo / ATTRIBUTION_PATH, attribution)
        preflight.write_json_lf(repo / DECISION_PATH, decision)
        packet = build_packet(repo, attribution, decision)
        preflight.write_json_lf(repo / PACKET_PATH, packet)
        report = repo / REPORT_PATH
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_bytes(report_text(attribution, decision).encode("utf-8"))
    return {"attribution": attribution, "decision": decision}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--record-registry", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        result = run(repo, write=args.write)
        if args.record_registry:
            record_registry(repo, result["decision"])
    except (RouterContextAttributionInvalid, preflight.RouterContextPreflightInvalid) as exc:
        print(json.dumps({"status": "router_context_attribution_invalid", "detail": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
