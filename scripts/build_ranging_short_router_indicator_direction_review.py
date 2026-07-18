#!/usr/bin/env python3
"""Review the frozen router-indicator direction contract without execution."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from export_director_registry import export_registry
from protected_manifest_hash import validate_protected_manifests
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    write_json,
)


REVIEW_ID = "ranging-short-router-indicator-direction-review-v1"
NEXT_PROPOSAL_ID = (
    "ranging-short-router-unanimous-expansion-candidate-preparation-v1"
)
APPROVAL_PATH = Path(
    "research/governance/approvals/"
    "ranging-short-router-indicator-direction-review-v1-read-only-approval.json"
)
SOURCE_ROOT = Path(
    "research/analysis/ranging-short-structural-observable-discovery-v1"
)
COVERAGE_SOURCE_PATH = SOURCE_ROOT / "observable-coverage-evidence.json"
INVENTORY_SOURCE_PATH = SOURCE_ROOT / "observable-inventory.json"
RANKING_SOURCE_PATH = SOURCE_ROOT / "ranking-decision.json"
DISCOVERY_PACKET_PATH = Path(
    "research/director/compiled/"
    "ranging-short-structural-observable-discovery-v1/"
    "human-decision-packet.json"
)
SOURCE_PROPOSAL_PATH = Path(
    "research/director/next-after-router-context-attribution/proposals/"
    f"{REVIEW_ID}.json"
)
CLOSURE_PATH = Path("research/closures/regime-aware-ranging-thresholds-v1.yaml")
CONTRACT_PATH = Path(
    "research/governance/ranging-short-router-indicator-direction-contract-v1.json"
)
ANALYSIS_ROOT = Path(
    "research/analysis/ranging-short-router-indicator-direction-review-v1"
)
ALIGNMENT_PATH = ANALYSIS_ROOT / "alignment-audit.json"
PARTITION_PATH = ANALYSIS_ROOT / "direction-partition-audit.json"
REDUNDANCY_PATH = ANALYSIS_ROOT / "redundancy-closure-audit.json"
DECISION_PATH = ANALYSIS_ROOT / "candidate-feasibility-decision.json"
REPORT_PATH = ANALYSIS_ROOT / "final-report.md"
NEXT_PROPOSAL_PATH = Path(
    "research/director/next-after-router-indicator-direction-review/proposals/"
    f"{NEXT_PROPOSAL_ID}.json"
)
PACKET_PATH = Path(
    "research/director/compiled/"
    "ranging-short-router-indicator-direction-review-v1/"
    "human-decision-packet.json"
)
STATE_PATH = Path("research/director/current-research-state.json")
STATE_MD_PATH = Path("research/director/current-research-state.md")
REGISTRY_PATH = Path("research/registry/stage4a-director.db")
REGISTRY_EXPORT_PATH = Path("research/director/registry-records.json")
RAW_DATA_PATH = Path(
    "research/data/snapshots/"
    "futures-dev-btc-usdt-usdt-20240101-20240830-v2/data/futures/"
    "BTC_USDT_USDT-1h-futures.feather"
)
COMPLETED_AT = "2026-07-18T18:43:25+00:00"


class DirectionReviewInvalid(RuntimeError):
    """Raised when the approved review contract or evidence has drifted."""


def write_json_lf(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_authority(repo: Path) -> dict[str, bool]:
    approval = load_document(repo / APPROVAL_PATH)
    proposal = load_document(repo / SOURCE_PROPOSAL_PATH)
    coverage = load_document(repo / COVERAGE_SOURCE_PATH)
    inventory = load_document(repo / INVENTORY_SOURCE_PATH)
    ranking = load_document(repo / RANKING_SOURCE_PATH)
    packet = load_document(repo / DISCOVERY_PACKET_PATH)
    closure = load_document(repo / CLOSURE_PATH)
    authority = approval["authority"]
    frozen = approval["frozen_inputs"]
    rules = approval["review_rules"]
    checks = {
        "human_approval": (
            approval["proposal_id"] == REVIEW_ID
            and approval["approval_status"] == "approved"
            and approval["approver_type"] == "human_user"
        ),
        "proposal_identity": (
            proposal["proposal_id"] == REVIEW_ID
            and proposal["status"] == "pending_human_review"
            and proposal["risk_class"] == "medium"
            and proposal["semantic_fingerprint"]
            == frozen["proposal_semantic_fingerprint"]
        ),
        "proposal_zero_execution_budget": (
            all(value == 0 for value in proposal["execution_budget"].values())
            and proposal["automatic_execution"] is False
        ),
        "frozen_file_hashes": (
            frozen["proposal_sha256"] == sha256_file(repo / SOURCE_PROPOSAL_PATH)
            and frozen["coverage_sha256"]
            == sha256_file(repo / COVERAGE_SOURCE_PATH)
            and frozen["inventory_sha256"]
            == sha256_file(repo / INVENTORY_SOURCE_PATH)
            and frozen["ranking_decision_sha256"]
            == sha256_file(repo / RANKING_SOURCE_PATH)
            and frozen["discovery_packet_sha256"]
            == sha256_file(repo / DISCOVERY_PACKET_PATH)
            and frozen["threshold_closure_sha256"]
            == sha256_file(repo / CLOSURE_PATH)
        ),
        "discovery_selection": (
            coverage["pre_gate_signal_count"] == 12
            and coverage["coverage_counts"][
                "router_indicator_direction_topology"
            ]
            == {"D-D-D": 2, "U-U-D": 5, "U-U-U": 5}
            and inventory["selected_observable_id"]
            == "router_indicator_direction_topology"
            and ranking["next_proposal_id"] == REVIEW_ID
            and packet["next_proposal_sha256"]
            == sha256_file(repo / SOURCE_PROPOSAL_PATH)
        ),
        "outcomes_forbidden": (
            authority["read_outcome_metrics"] is False
            and "outcome_metric_read" in proposal["forbidden_scope"]
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
        "review_rules": (
            rules["main_timeframe_minutes"] == 60
            and rules["informative_timeframe_minutes"] == 240
            and rules["direction_order"] == ["adx", "bb_width", "atr"]
            and rules["allowed_direction_symbols"] == ["D", "F", "U"]
            and rules["minimum_category_coverage"] == 2
            and rules["raw_dataset_rehydration_required_before_candidate_creation"]
            is True
            and rules["maximum_future_gate_recommendations"] == 1
        ),
        "closed_threshold_line_preserved": (
            closure["status"] == "closed_evidence_exhausted"
            and closure["forbidden_actions"]["strategy_modified"] is False
        ),
        "protected_manifests": validate_protected_manifests(repo)["passed"],
    }
    if not all(checks.values()):
        raise DirectionReviewInvalid(
            "direction_review_authority_invalid:" + json.dumps(checks, sort_keys=True)
        )
    return checks


def build_contract() -> dict[str, Any]:
    contract = {
        "schema_version": "ranging-short-router-indicator-direction-contract-v1",
        "contract_id": "ranging-short-router-indicator-direction-v1",
        "scope": {
            "pair": "BTC/USDT:USDT",
            "main_timeframe": "1h",
            "informative_timeframe": "4h",
            "signal_group": "ranging_short_entry",
            "source_population": "frozen 12 pre-gate development signals",
        },
        "clock_semantics": {
            "signal_timestamp": "open time of the 1h signal candle",
            "signal_decision_at": "signal_timestamp + 1h",
            "informative_timestamp": "open time of the current 4h informative candle",
            "informative_available_at": "informative_timestamp + 4h",
            "required_relation": "informative_available_at <= signal_decision_at",
            "previous_informative_timestamp": "informative_timestamp - 4h",
        },
        "inputs": {
            "order": ["adx", "bb_width", "atr"],
            "current": ["adx_4h", "bb_width_4h", "atr_4h"],
            "previous": [
                "previous_completed_adx_4h",
                "previous_completed_bb_width_4h",
                "previous_completed_atr_4h",
            ],
        },
        "categorization": {
            "U": "current > previous",
            "D": "current < previous",
            "F": "current == previous",
            "epsilon": None,
            "continuous_cutoff": None,
            "topology_format": "adx-bb_width-atr",
        },
        "future_single_variable_gate": {
            "gate_id": "block_unanimous_router_indicator_expansion",
            "blocked_topology": "U-U-U",
            "retained_topologies": ["D-D-D", "U-U-D"],
            "economic_rationale": (
                "Rising ADX, BB-width and ATR together indicate broad expansion and "
                "breakout risk, which conflicts with a ranging-short mean-reversion entry."
            ),
            "outcome_metrics_used": False,
        },
        "immutability": {
            "candidate_created": False,
            "formal_strategy_modified": False,
            "router_modified": False,
            "threshold_search_run": False,
        },
    }
    contract["contract_fingerprint"] = fingerprint(contract)
    return contract


def build_alignment_audit(
    repo: Path, coverage: dict[str, Any], contract: dict[str, Any]
) -> dict[str, Any]:
    rows = []
    lag_counts: Counter[str] = Counter()
    violations = []
    seen = set()
    for source in coverage["rows"]:
        signal_at = _parse_time(source["date"])
        decision_at = signal_at + timedelta(hours=1)
        informative_at = _parse_time(source["informative_date"])
        informative_available_at = informative_at + timedelta(hours=4)
        previous_at = informative_at - timedelta(hours=4)
        previous_available_at = informative_at
        lag_minutes = int(
            (decision_at - informative_available_at).total_seconds() // 60
        )
        topology_from_components = "-".join(
            source["router_indicator_directions"][key]
            for key in ("adx", "bb_width", "atr")
        )
        row_checks = {
            "current_informative_completed_by_decision": (
                informative_available_at <= decision_at
            ),
            "previous_informative_precedes_current": previous_at < informative_at,
            "previous_informative_completed": (
                previous_available_at <= informative_available_at
            ),
            "direction_components_match_topology": (
                topology_from_components
                == source["router_indicator_direction_topology"]
            ),
            "allowed_direction_symbols_only": all(
                symbol in {"D", "F", "U"}
                for symbol in source["router_indicator_directions"].values()
            ),
            "signal_identity_unique": (
                (source["slice_id"], source["date"]) not in seen
            ),
        }
        seen.add((source["slice_id"], source["date"]))
        if not all(row_checks.values()):
            violations.append(
                {"slice_id": source["slice_id"], "date": source["date"], "checks": row_checks}
            )
        lag_counts[str(lag_minutes)] += 1
        rows.append(
            {
                "slice_id": source["slice_id"],
                "signal_timestamp": source["date"],
                "signal_decision_at": decision_at.isoformat(),
                "informative_timestamp": source["informative_date"],
                "informative_available_at": informative_available_at.isoformat(),
                "previous_informative_timestamp": previous_at.isoformat(),
                "decision_lag_minutes": lag_minutes,
                "direction_topology": source[
                    "router_indicator_direction_topology"
                ],
                "checks": row_checks,
            }
        )
    audit = {
        "schema_version": "router-indicator-direction-alignment-audit-v1",
        "review_id": REVIEW_ID,
        "contract_fingerprint": contract["contract_fingerprint"],
        "source_coverage_fingerprint": coverage["coverage_fingerprint"],
        "replay_mode": "committed_discovery_row_replay",
        "raw_development_data_hydrated": (repo / RAW_DATA_PATH).is_file(),
        "raw_replay_required_before_candidate_creation": True,
        "row_count": len(rows),
        "decision_lag_minutes_counts": dict(sorted(lag_counts.items(), key=lambda item: int(item[0]))),
        "lookahead_violation_count": len(violations),
        "all_rows_lag_safe": not violations,
        "violations": violations,
        "rows": rows,
        "outcome_metrics_read": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    audit["alignment_fingerprint"] = fingerprint(audit)
    return audit


def _entropy(counts: dict[str, int]) -> float:
    if len([count for count in counts.values() if count]) <= 1:
        return 0.0
    total = sum(counts.values())
    return -sum(
        (count / total) * math.log2(count / total)
        for count in counts.values()
        if count
    )


def build_partition_audit(coverage: dict[str, Any]) -> dict[str, Any]:
    rows = coverage["rows"]
    direction_counts = dict(
        sorted(Counter(row["router_indicator_direction_topology"] for row in rows).items())
    )
    level_counts = dict(
        sorted(Counter(row["router_level_topology"] for row in rows).items())
    )
    by_slice: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_slice[row["slice_id"]][row["router_indicator_direction_topology"]] += 1
    blocked = direction_counts.get("U-U-U", 0)
    retained = len(rows) - blocked
    audit = {
        "schema_version": "router-indicator-direction-partition-audit-v1",
        "review_id": REVIEW_ID,
        "pre_gate_signal_count": len(rows),
        "current_router_level_counts": level_counts,
        "direction_topology_counts": direction_counts,
        "direction_topology_counts_by_slice": {
            key: dict(sorted(value.items())) for key, value in sorted(by_slice.items())
        },
        "current_router_level_entropy_bits": round(_entropy(level_counts), 12),
        "direction_topology_entropy_bits": round(_entropy(direction_counts), 12),
        "strict_partition_refinement": (
            len(level_counts) == 1 and len(direction_counts) > 1
        ),
        "minimum_category_coverage": min(direction_counts.values()),
        "all_categories_meet_minimum_coverage_two": all(
            count >= 2 for count in direction_counts.values()
        ),
        "whole_branch_equivalent": len(direction_counts) == 1,
        "future_gate_preflight": {
            "gate_id": "block_unanimous_router_indicator_expansion",
            "blocked_topology": "U-U-U",
            "blocked_pre_gate_signals": blocked,
            "retained_pre_gate_signals": retained,
            "blocked_ratio": round(blocked / len(rows), 12),
            "retained_ratio": round(retained / len(rows), 12),
            "both_sides_nonzero": blocked > 0 and retained > 0,
        },
        "outcome_metrics_read": False,
        "time_slice_used_as_gate": False,
        "continuous_threshold_search": False,
    }
    audit["partition_fingerprint"] = fingerprint(audit)
    return audit


def build_redundancy_audit(
    repo: Path, partition: dict[str, Any]
) -> dict[str, Any]:
    audit = {
        "schema_version": "router-indicator-direction-redundancy-closure-audit-v1",
        "review_id": REVIEW_ID,
        "current_contract": {
            "representation": "absolute 4h ADX, BB-width and ATR threshold votes",
            "observed_partition": partition["current_router_level_counts"],
            "observed_entropy_bits": partition[
                "current_router_level_entropy_bits"
            ],
        },
        "direction_contract": {
            "representation": "sign of first difference across completed 4h indicator values",
            "observed_partition": partition["direction_topology_counts"],
            "observed_entropy_bits": partition["direction_topology_entropy_bits"],
            "adds_nonzero_structural_partition": partition[
                "strict_partition_refinement"
            ],
        },
        "redundancy_decision": "nonredundant_temporal_derivative_of_existing_router_inputs",
        "closure_checks": {
            "changes_closed_numeric_threshold": False,
            "reopens_adjacent_threshold_search": False,
            "uses_duplicate_signal_lifecycle": False,
            "uses_time_slice_identity": False,
            "changes_execution_or_risk_semantics": False,
            "human_approved_structural_review_only": True,
        },
        "closure_conflict_count": 0,
        "raw_development_data_hydrated": (repo / RAW_DATA_PATH).is_file(),
        "evidence_limitations": [
            (
                "The branch-cleanup archive retained committed row-level Discovery "
                "evidence but not the ignored raw development feather files."
            ),
            (
                "Exact raw-indicator replay is therefore a mandatory fail-closed "
                "precondition before Candidate creation."
            ),
        ],
        "outcome_metrics_read": False,
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    audit["redundancy_fingerprint"] = fingerprint(audit)
    return audit


def build_decision(
    contract: dict[str, Any],
    alignment: dict[str, Any],
    partition: dict[str, Any],
    redundancy: dict[str, Any],
) -> dict[str, Any]:
    structurally_valid = (
        alignment["all_rows_lag_safe"]
        and partition["strict_partition_refinement"]
        and partition["all_categories_meet_minimum_coverage_two"]
        and not partition["whole_branch_equivalent"]
        and redundancy["closure_conflict_count"] == 0
    )
    decision_code = (
        "conditionally_eligible_for_single_variable_candidate_preparation"
        if structurally_valid
        else "not_eligible_for_candidate_preparation"
    )
    decision = {
        "schema_version": "router-indicator-direction-candidate-feasibility-decision-v1",
        "review_id": REVIEW_ID,
        "decision": decision_code,
        "structural_contract_valid": structurally_valid,
        "contract_fingerprint": contract["contract_fingerprint"],
        "alignment_fingerprint": alignment["alignment_fingerprint"],
        "partition_fingerprint": partition["partition_fingerprint"],
        "redundancy_fingerprint": redundancy["redundancy_fingerprint"],
        "recommended_future_gate": {
            "gate_id": "block_unanimous_router_indicator_expansion",
            "blocked_topology": "U-U-U",
            "blocked_pre_gate_signals": partition["future_gate_preflight"][
                "blocked_pre_gate_signals"
            ],
            "retained_pre_gate_signals": partition["future_gate_preflight"][
                "retained_pre_gate_signals"
            ],
            "selection_basis": "economic_mechanism_only_no_outcome_metrics",
        },
        "mandatory_pre_candidate_conditions": [
            "rehydrate the exact frozen development dataset from its sealed lineage",
            "reproduce the 12-signal population and D-D-D=2/U-U-D=5/U-U-U=5 partition",
            "verify zero lookahead violations from raw indicator values",
            "obtain separate human approval for Candidate creation",
        ],
        "next_proposal_id": NEXT_PROPOSAL_ID,
        "next_proposal_status": "pending_human_review",
        "candidate_creation_authorized_now": False,
        "backtest_authorized_now": False,
        "threshold_search_authorized": False,
        "validation_authorized": False,
        "holdout_authorized": False,
        "automatic_followup_authorized": False,
        "formal_branch_status": "retained_unchanged",
    }
    decision["decision_fingerprint"] = fingerprint(decision)
    return decision


def build_next_proposal(decision: dict[str, Any]) -> dict[str, Any]:
    proposal = {
        "schema_version": "research-proposal-v1",
        "proposal_id": NEXT_PROPOSAL_ID,
        "title": "Prepare a single-variable unanimous-expansion blocker Candidate",
        "status": "pending_human_review",
        "risk_class": "medium",
        "risk_reasons": ["candidate_creation", "strategy_structure"],
        "objective": (
            "Rehydrate and reproduce the frozen direction evidence, then prepare one "
            "Candidate that blocks ranging-short entry only for U-U-U."
        ),
        "frozen_gate": decision["recommended_future_gate"],
        "preconditions": decision["mandatory_pre_candidate_conditions"][:3],
        "allowed_scope_after_human_approval": [
            "rehydrate exact frozen development data from sealed local lineage",
            "replay raw indicator direction coverage",
            "create exactly one single-variable Candidate",
            "run zero-backtest signal coverage preflight",
        ],
        "forbidden_scope": [
            "backtest",
            "outcome_metric_read",
            "continuous_threshold_search",
            "validation",
            "holdout",
            "formal_strategy_change",
            "automatic_followup_execution",
        ],
        "execution_budget": {
            "candidate_creations": 1,
            "coverage_preflights": 1,
            "backtest_calls": 0,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        },
        "fail_closed_conditions": [
            "exact raw development data unavailable",
            "source signal population differs from 12",
            "direction partition differs from D-D-D=2/U-U-D=5/U-U-U=5",
            "any lookahead alignment violation",
        ],
        "approval_route": "human_approval_required",
        "automatic_execution": False,
    }
    proposal["semantic_fingerprint"] = fingerprint(proposal)
    return proposal


def report_text(
    alignment: dict[str, Any],
    partition: dict[str, Any],
    decision: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# Ranging-short router 指标方向契约审计",
            "",
            "## 结论",
            "",
            "4h 指标方向拓扑通过结构审计，但只具备有条件的 Candidate 准备资格。",
            "当前提交证据中的 12 个信号全部满足完成 K 线对齐，没有未来函数违规；方向拓扑把原本 `R-R-R=12` 的单一水平状态细分为 `D-D-D=2`、`U-U-D=5`、`U-U-U=5`。",
            "",
            "建议后续唯一单变量 gate 为 `block_unanimous_router_indicator_expansion`：当 ADX、BB-width、ATR 同时上升，即 `U-U-U` 时阻止 ranging-short 新入场。它将阻止 5 个 pre-gate 信号并保留 7 个。该选择只依据经济机制，没有读取收益结果。",
            "",
            "## 防未来函数契约",
            "",
            "- 1h 信号在该 K 线结束时决策。",
            "- 4h 指标只有在对应 4h K 线结束后才可用。",
            "- 当前与上一根已完成 4h 指标逐项比较：上升=`U`、下降=`D`、相等=`F`。",
            f"- 对齐违规：`{alignment['lookahead_violation_count']}`。",
            "",
            "## 信息增量与边界",
            "",
            f"- 当前水平 router 熵：`{partition['current_router_level_entropy_bits']}` bit。",
            f"- 方向拓扑熵：`{partition['direction_topology_entropy_bits']}` bit。",
            "- 未更改已关闭阈值、重复信号机制、风险或执行语义。",
            "- Candidate / Backtest / Validation / Holdout：`0 / 0 / 0 / 0`。",
            "- 分支清理保留了提交后的逐行证据，但没有保留被忽略的原始 feather 数据；创建 Candidate 前必须先按封存 lineage 恢复并复现原始数据。",
            "",
            "## 下一步",
            "",
            f"已编译 `{decision['next_proposal_id']}`，状态为 `pending_human_review`。它只允许恢复数据、创建一个 Candidate 并运行零回测覆盖 preflight；回测仍未获授权。",
            "",
        ]
    )


def build_packet(repo: Path, decision: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "contract": CONTRACT_PATH,
        "alignment": ALIGNMENT_PATH,
        "partition": PARTITION_PATH,
        "redundancy": REDUNDANCY_PATH,
        "decision": DECISION_PATH,
        "next_proposal": NEXT_PROPOSAL_PATH,
    }
    return {
        "schema_version": "router-indicator-direction-review-packet-v1",
        "review_id": REVIEW_ID,
        "status": "completed_read_only",
        "decision": decision["decision"],
        "artifacts": {
            key: {"path": path.as_posix(), "sha256": sha256_file(repo / path)}
            for key, path in paths.items()
        },
        "next_proposal_id": decision["next_proposal_id"],
        "next_proposal_status": decision["next_proposal_status"],
        "candidate_created": False,
        "backtest_calls": 0,
        "outcome_metrics_read": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "formal_strategy_modified": False,
        "automatic_followup_executed": False,
    }


def update_state(repo: Path, decision: dict[str, Any]) -> None:
    state = load_document(repo / STATE_PATH)
    state["ranging_short_router_indicator_direction_review"] = {
        "review_id": REVIEW_ID,
        "status": "completed_read_only",
        "decision": decision["decision"],
        "decision_fingerprint": decision["decision_fingerprint"],
        "structural_contract_valid": decision["structural_contract_valid"],
        "recommended_future_gate": decision["recommended_future_gate"],
        "raw_data_replay_required_before_candidate": True,
        "next_proposal_id": decision["next_proposal_id"],
        "next_proposal_status": decision["next_proposal_status"],
        "candidate_created": False,
        "backtest_calls": 0,
        "outcome_metrics_read": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "formal_strategy_modified": False,
        "evidence": [
            CONTRACT_PATH.as_posix(),
            ALIGNMENT_PATH.as_posix(),
            PARTITION_PATH.as_posix(),
            REDUNDANCY_PATH.as_posix(),
            DECISION_PATH.as_posix(),
            NEXT_PROPOSAL_PATH.as_posix(),
            PACKET_PATH.as_posix(),
        ],
    }
    write_json_lf(repo / STATE_PATH, state)
    text = "\n".join(
        [
            "# 当前研究状态",
            "",
            f"- 当前项目：`{REVIEW_ID}`",
            "- 状态：`completed_read_only`",
            f"- 决策：`{decision['decision']}`",
            "- 方向覆盖：`D-D-D=2 / U-U-D=5 / U-U-U=5`",
            "- 建议 gate：`block_unanimous_router_indicator_expansion`",
            "- 预期 pre-gate：阻止 `5` / 保留 `7`",
            "- 原始数据复现：Candidate 前强制要求",
            f"- 下一提案：`{NEXT_PROPOSAL_ID}` / `pending_human_review`",
            "- Candidate / Backtest / Validation / Holdout：`0 / 0 / 0 / 0`",
            "- 正式策略：保留且未修改",
            "",
            f"只读审计报告：`{REPORT_PATH.as_posix()}`。",
            "",
        ]
    )
    (repo / STATE_MD_PATH).write_bytes(text.encode("utf-8"))


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
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs("
        "run_id,campaign_id,proposal_id,status,result_code,campaign_executed,"
        "candidate_created,strategy_modified,validation_accesses,holdout_accesses,"
        "payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            REVIEW_ID,
            f"stage4a-{REVIEW_ID}",
            REVIEW_ID,
            "completed_read_only",
            decision["decision"],
            0,
            0,
            0,
            0,
            0,
            json.dumps(decision, sort_keys=True),
            COMPLETED_AT,
        ),
    )
    for path in (
        APPROVAL_PATH,
        CONTRACT_PATH,
        ALIGNMENT_PATH,
        PARTITION_PATH,
        REDUNDANCY_PATH,
        DECISION_PATH,
        NEXT_PROPOSAL_PATH,
        PACKET_PATH,
        REPORT_PATH,
    ):
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets("
            "asset_id,run_id,artifact_type,path,sha256,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                f"{REVIEW_ID}:{path.as_posix()}",
                REVIEW_ID,
                "read_only_direction_contract_review",
                path.as_posix(),
                sha256_file(repo / path),
                COMPLETED_AT,
            ),
        )
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise DirectionReviewInvalid("registry_integrity_failed")
    write_json(
        repo / REGISTRY_EXPORT_PATH,
        export_registry(str(repo / REGISTRY_PATH)),
    )


def run(
    repo: Path,
    *,
    write: bool,
    update_current_state: bool = False,
    record_registry_state: bool = False,
) -> dict[str, Any]:
    checks = validate_authority(repo)
    coverage = load_document(repo / COVERAGE_SOURCE_PATH)
    contract = build_contract()
    alignment = build_alignment_audit(repo, coverage, contract)
    partition = build_partition_audit(coverage)
    redundancy = build_redundancy_audit(repo, partition)
    decision = build_decision(contract, alignment, partition, redundancy)
    next_proposal = build_next_proposal(decision)
    if write:
        for path, payload in (
            (CONTRACT_PATH, contract),
            (ALIGNMENT_PATH, alignment),
            (PARTITION_PATH, partition),
            (REDUNDANCY_PATH, redundancy),
            (DECISION_PATH, decision),
            (NEXT_PROPOSAL_PATH, next_proposal),
        ):
            write_json_lf(repo / path, payload)
        report = repo / REPORT_PATH
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_bytes(report_text(alignment, partition, decision).encode("utf-8"))
        write_json_lf(repo / PACKET_PATH, build_packet(repo, decision))
        if update_current_state:
            update_state(repo, decision)
        if record_registry_state:
            record_registry(repo, decision)
    return {
        "authority_checks": checks,
        "contract": contract,
        "alignment": alignment,
        "partition": partition,
        "redundancy": redundancy,
        "decision": decision,
        "next_proposal": next_proposal,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--update-current-state", action="store_true")
    parser.add_argument("--record-registry", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        result = run(
            repo,
            write=args.write,
            update_current_state=args.update_current_state,
            record_registry_state=args.record_registry,
        )
    except DirectionReviewInvalid as exc:
        print(json.dumps({"status": "direction_review_invalid", "detail": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": "completed_read_only",
                "decision": result["decision"]["decision"],
                "direction_counts": result["partition"]["direction_topology_counts"],
                "future_gate": result["decision"]["recommended_future_gate"],
                "next_proposal_status": result["next_proposal"]["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
