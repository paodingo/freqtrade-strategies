#!/usr/bin/env python3
"""Inventory structural ranging-short observables without outcomes or execution."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

import build_ranging_short_router_context_attribution as prior_attribution
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


AUDIT_ID = "ranging-short-structural-observable-discovery-v1"
NEXT_PROPOSAL_ID = "ranging-short-router-indicator-direction-review-v1"
APPROVAL_PATH = Path(
    "research/governance/approvals/"
    "ranging-short-structural-observable-discovery-v1-read-only-approval.json"
)
ANALYSIS_ROOT = Path(
    "research/analysis/ranging-short-structural-observable-discovery-v1"
)
COVERAGE_PATH = ANALYSIS_ROOT / "observable-coverage-evidence.json"
INVENTORY_PATH = ANALYSIS_ROOT / "observable-inventory.json"
DECISION_PATH = ANALYSIS_ROOT / "ranking-decision.json"
REPORT_PATH = ANALYSIS_ROOT / "final-report.md"
PROPOSAL_PATH = Path(
    "research/director/next-after-router-context-attribution/proposals/"
    f"{NEXT_PROPOSAL_ID}.json"
)
PACKET_PATH = Path(
    "research/director/compiled/"
    "ranging-short-structural-observable-discovery-v1/"
    "human-decision-packet.json"
)
STATE_PATH = Path("research/director/current-research-state.json")
STATE_MD_PATH = Path("research/director/current-research-state.md")
REGISTRY_PATH = Path("research/registry/stage4a-director.db")
REGISTRY_EXPORT_PATH = Path("research/director/registry-records.json")
PRIOR_DECISION_PATH = prior_attribution.DECISION_PATH
PRIOR_ATTRIBUTION_PATH = prior_attribution.ATTRIBUTION_PATH
CLOSURE_PATH = Path("research/closures/regime-aware-ranging-thresholds-v1.yaml")
ALPHA_TAKER_INVENTORY_PATH = Path(
    "reports/ranging_short_research/"
    "ranging_short_alpha_taker_data_source_inventory.json"
)
DATASET_MANIFEST_PATH = Path(
    "research/data/snapshots/"
    f"{preflight.DATASET_ID}/manifest.yaml"
)
COMPLETED_AT = "2026-07-18T11:10:35+00:00"


class StructuralDiscoveryInvalid(RuntimeError):
    """Raised when the read-only Discovery authority or evidence drifts."""


def validate_authority(repo: Path) -> dict[str, bool]:
    approval = load_document(repo / APPROVAL_PATH)
    authority = approval["authority"]
    frozen = approval["frozen_inputs"]
    rules = approval["selection_rules"]
    prior_decision = load_document(repo / PRIOR_DECISION_PATH)
    prior = load_document(repo / PRIOR_ATTRIBUTION_PATH)
    closure = load_document(repo / CLOSURE_PATH)
    source_inventory = load_document(repo / ALPHA_TAKER_INVENTORY_PATH)
    checks = {
        "human_read_only_approval": (
            approval["audit_id"] == AUDIT_ID
            and approval["approval_status"] == "approved"
            and approval["approver_type"] == "human_user"
        ),
        "prior_router_line_closed": (
            prior_decision["decision"]
            == "no_admissible_router_context_under_current_contract"
            and prior_decision["new_candidate_authorized"] is False
            and prior_decision["backtest_authorized"] is False
        ),
        "prior_signal_population_frozen": (
            prior["pre_gate_signal_count"] == 12
            and prior["topology_counts"] == {"R-R-R": 12}
            and prior["method"]["outcome_metrics_read"] is False
        ),
        "frozen_hashes": (
            frozen["prior_decision_sha256"]
            == sha256_file(repo / PRIOR_DECISION_PATH)
            and frozen["prior_attribution_sha256"]
            == sha256_file(repo / PRIOR_ATTRIBUTION_PATH)
            and frozen["dataset_manifest_sha256"]
            == sha256_file(repo / DATASET_MANIFEST_PATH)
            and frozen["threshold_closure_sha256"]
            == sha256_file(repo / CLOSURE_PATH)
            and frozen["alpha_taker_inventory_sha256"]
            == sha256_file(repo / ALPHA_TAKER_INVENTORY_PATH)
        ),
        "closed_mechanisms_respected": (
            closure["status"] == "closed_evidence_exhausted"
            and closure["conclusions"]["mechanism_recommendation"]
            == "no_mechanism_change_warranted"
        ),
        "missing_sources_not_invented": (
            source_inventory["decision"]["can_reconstruct_alpha_taker_now"]
            is False
        ),
        "zero_execution_authority": (
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
        "selection_rules": (
            rules["outcome_metrics_forbidden"] is True
            and rules["reject_continuous_cutoff_search"] is True
            and rules["reject_observed_whole_branch_equivalence"] is True
            and rules["respect_closed_duplicate_signal_mechanism"] is True
            and rules["maximum_next_proposals"] == 1
        ),
        "protected_manifests": validate_protected_manifests(repo)["passed"],
    }
    if not all(checks.values()):
        raise StructuralDiscoveryInvalid(
            "structural_discovery_authority_invalid:"
            + json.dumps(checks, sort_keys=True)
        )
    return checks


def _direction(current: float, previous: float) -> str:
    if pd.isna(current) or pd.isna(previous):
        return "unknown"
    if current > previous:
        return "U"
    if current < previous:
        return "D"
    return "F"


def _sign(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def _slice_signal_rows(
    repo: Path, candidate_class: type, slice_spec: dict[str, Any]
) -> list[dict[str, Any]]:
    data_root = (
        repo
        / "research/data/snapshots"
        / preflight.DATASET_ID
        / "data/futures"
    )

    class DataProvider:
        def current_whitelist(self) -> list[str]:
            return [preflight.PAIR]

        def get_pair_dataframe(
            self, pair: str, timeframe: str, candle_type: str = "futures"
        ) -> pd.DataFrame:
            if (
                pair != preflight.PAIR
                or timeframe != "4h"
                or candle_type != "futures"
            ):
                raise StructuralDiscoveryInvalid(
                    "unauthorized_structural_discovery_input"
                )
            informative = pd.read_feather(
                data_root / f"{preflight.PREFIX}-4h-futures.feather"
            )
            return preflight._in_window(
                informative,
                slice_spec["warmup_start"],
                slice_spec["evaluation_end_exclusive"],
            )

    raw = pd.read_feather(
        data_root / f"{preflight.PREFIX}-1h-futures.feather"
    )
    raw = preflight._in_window(
        raw,
        slice_spec["warmup_start"],
        slice_spec["evaluation_end_exclusive"],
    )
    strategy = candidate_class({})
    strategy.dp = DataProvider()
    frame = strategy.populate_indicators(raw.copy(), {"pair": preflight.PAIR})
    frame = strategy.populate_entry_trend(frame, {"pair": preflight.PAIR})

    indicator_columns = ("adx_4h", "bb_width_4h", "atr_4h")
    router_columns = (
        *indicator_columns,
        "bb_width_mean_4h",
        "atr_mean_4h",
    )
    informative_rows = (
        frame[["date_4h", *router_columns]]
        .dropna(subset=["date_4h"])
        .drop_duplicates("date_4h", keep="first")
        .sort_values("date_4h")
        .copy()
    )
    for column in indicator_columns:
        informative_rows[f"{column}_direction"] = [
            _direction(current, previous)
            for current, previous in zip(
                informative_rows[column], informative_rows[column].shift(1)
            )
        ]
    informative_rows["direction_topology"] = informative_rows.apply(
        lambda row: "-".join(
            row[f"{column}_direction"] for column in indicator_columns
        ),
        axis=1,
    )
    informative_rows["router_topology"] = informative_rows.apply(
        lambda row: prior_attribution._topology_id(
            prior_attribution._vote_topology(row)
        ),
        axis=1,
    )
    informative_rows["previous_router_topology"] = informative_rows[
        "router_topology"
    ].shift(1)
    informative_rows["router_transition_state"] = informative_rows.apply(
        lambda row: (
            "newly_changed_to_R-R-R"
            if row["router_topology"] == "R-R-R"
            and row["previous_router_topology"] != "R-R-R"
            else "persisted_R-R-R"
            if row["router_topology"] == "R-R-R"
            else "outside_R-R-R"
        ),
        axis=1,
    )
    derived_columns = [
        "date_4h",
        "direction_topology",
        "router_transition_state",
        *[f"{column}_direction" for column in indicator_columns],
    ]
    frame = frame.merge(
        informative_rows[derived_columns], on="date_4h", how="left"
    )
    frame["volume_mean_direction"] = [
        _direction(current, previous)
        for current, previous in zip(
            frame["volume_mean"], frame["volume_mean"].shift(1)
        )
    ]
    frame["close_return_direction"] = [
        _direction(current, previous)
        for current, previous in zip(frame["close"], frame["close"].shift(1))
    ]
    frame = preflight._in_window(
        frame,
        slice_spec["evaluation_start"],
        slice_spec["evaluation_end_exclusive"],
    )
    selected = frame.loc[
        frame["research_ranging_short_entry_pre_gate"] == 1
    ]
    rows = []
    for _, row in selected.iterrows():
        rows.append(
            {
                "slice_id": slice_spec["slice_id"],
                "date": pd.Timestamp(row["date"]).isoformat(),
                "informative_date": pd.Timestamp(row["date_4h"]).isoformat(),
                "router_level_topology": "R-R-R",
                "router_indicator_direction_topology": row[
                    "direction_topology"
                ],
                "router_indicator_directions": {
                    "adx": row["adx_4h_direction"],
                    "bb_width": row["bb_width_4h_direction"],
                    "atr": row["atr_4h_direction"],
                },
                "router_transition_state": row["router_transition_state"],
                "volume_mean_direction": row["volume_mean_direction"],
                "close_return_direction": row["close_return_direction"],
            }
        )
    return rows


def _add_funding_and_basis(repo: Path, rows: list[dict[str, Any]]) -> None:
    root = (
        repo
        / "research/data/snapshots"
        / preflight.DATASET_ID
        / "data/futures"
    )
    signals = pd.DataFrame(rows)
    signals["signal_date"] = pd.to_datetime(signals["date"], utc=True)
    signals = signals.sort_values("signal_date")

    funding = pd.read_feather(
        root / f"{preflight.PREFIX}-8h-funding_rate.feather"
    )[["date", "close"]].rename(
        columns={"date": "funding_time", "close": "funding_rate"}
    )
    funding = funding.sort_values("funding_time")
    aligned = pd.merge_asof(
        signals[["signal_date"]],
        funding,
        left_on="signal_date",
        right_on="funding_time",
        direction="backward",
    )

    mark = pd.read_feather(root / f"{preflight.PREFIX}-8h-mark.feather")[[
        "date",
        "close",
    ]].rename(columns={"close": "mark_close"})
    mark["available_at"] = mark["date"] + pd.Timedelta(8, unit="h")
    futures = pd.read_feather(
        root / f"{preflight.PREFIX}-1h-futures.feather"
    )[["date", "close"]]
    futures["bucket"] = futures["date"].dt.floor("8h")
    futures_8h = (
        futures.groupby("bucket", as_index=False)
        .last()
        .rename(columns={"close": "futures_close"})
    )
    futures_8h["available_at"] = futures_8h["bucket"] + pd.Timedelta(8, unit="h")
    basis = mark.merge(
        futures_8h[["available_at", "futures_close"]],
        on="available_at",
        how="inner",
    )
    basis["basis_bps"] = (
        basis["mark_close"] / basis["futures_close"] - 1.0
    ) * 10000.0
    aligned_basis = pd.merge_asof(
        signals[["signal_date"]],
        basis[["available_at", "basis_bps"]].sort_values("available_at"),
        left_on="signal_date",
        right_on="available_at",
        direction="backward",
    )

    by_date = {row["date"]: row for row in rows}
    for index, signal in signals.reset_index(drop=True).iterrows():
        target = by_date[pd.Timestamp(signal["signal_date"]).isoformat()]
        target["funding_state"] = _sign(float(aligned.iloc[index]["funding_rate"]))
        target["funding_rate"] = round(
            float(aligned.iloc[index]["funding_rate"]), 12
        )
        target["funding_available_at"] = pd.Timestamp(
            aligned.iloc[index]["funding_time"]
        ).isoformat()
        target["completed_mark_futures_basis_sign"] = _sign(
            float(aligned_basis.iloc[index]["basis_bps"])
        )
        target["completed_mark_futures_basis_bps"] = round(
            float(aligned_basis.iloc[index]["basis_bps"]), 12
        )
        target["basis_available_at"] = pd.Timestamp(
            aligned_basis.iloc[index]["available_at"]
        ).isoformat()


def _counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row[field] for row in rows).items()))


def build_coverage(repo: Path) -> dict[str, Any]:
    checks = validate_authority(repo)
    policy = load_document(repo / preflight.SLICE_POLICY_PATH)
    candidate_class = preflight._load_candidate(repo)
    rows = [
        row
        for slice_spec in policy["slices"]
        for row in _slice_signal_rows(repo, candidate_class, slice_spec)
    ]
    prior_rows = load_document(repo / PRIOR_ATTRIBUTION_PATH)["rows"]
    expected = sorted((row["slice_id"], row["date"]) for row in prior_rows)
    observed = sorted((row["slice_id"], row["date"]) for row in rows)
    if observed != expected:
        raise StructuralDiscoveryInvalid("frozen_signal_population_drift")
    _add_funding_and_basis(repo, rows)
    coverage = {
        "schema_version": "ranging-short-structural-observable-coverage-v1",
        "audit_id": AUDIT_ID,
        "authority_checks": checks,
        "method": {
            "type": "lag_safe_categorical_development_data_inventory",
            "outcome_metrics_read": False,
            "continuous_threshold_search": False,
            "time_slice_used_as_observable": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        },
        "alignment_contract": {
            "router_indicator_direction": (
                "sign of current completed 4h indicator minus the prior completed "
                "4h indicator, propagated by informative date"
            ),
            "funding_state": (
                "latest sealed 8h funding observation at or before the signal candle open"
            ),
            "mark_futures_basis": (
                "sign of the last fully completed 8h mark close minus the matching "
                "aggregated futures close; available only after the 8h bucket ends"
            ),
        },
        "pre_gate_signal_count": len(rows),
        "coverage_counts": {
            "router_indicator_direction_topology": _counts(
                rows, "router_indicator_direction_topology"
            ),
            "funding_sign": _counts(rows, "funding_state"),
            "completed_mark_futures_basis_sign": _counts(
                rows, "completed_mark_futures_basis_sign"
            ),
            "router_transition_state": _counts(
                rows, "router_transition_state"
            ),
            "volume_mean_direction": _counts(rows, "volume_mean_direction"),
            "close_return_direction": _counts(
                rows, "close_return_direction"
            ),
        },
        "rows": rows,
        "candidate_created": False,
        "backtest_calls": 0,
        "threshold_search_run": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    coverage["coverage_fingerprint"] = fingerprint(coverage)
    return coverage


def _ranked_observable(
    observable_id: str,
    definition: str,
    mechanism: str,
    source_fields: list[str],
    counts: dict[str, int],
    scores: dict[str, int],
    caveats: list[str],
) -> dict[str, Any]:
    return {
        "observable_id": observable_id,
        "definition": definition,
        "economic_mechanism": mechanism,
        "source_fields": source_fields,
        "available_now": True,
        "requires_new_dataset": False,
        "natural_categories": list(counts),
        "pre_gate_coverage": counts,
        "whole_branch_equivalent": len(counts) == 1,
        "continuous_cutoff_required": False,
        "outcome_metrics_read": False,
        "scores": scores,
        "score_total": sum(scores.values()),
        "caveats": caveats,
        "selection_status": "eligible_for_read_only_contract_review",
    }


def build_inventory(coverage: dict[str, Any]) -> dict[str, Any]:
    counts = coverage["coverage_counts"]
    eligible = [
        _ranked_observable(
            "router_indicator_direction_topology",
            "categorical U/D/F direction of ADX, BB-width and ATR versus the prior completed 4h candle",
            "distinguishes expanding, contracting and mixed regime phases even when all current router votes remain ranging",
            ["adx_4h", "bb_width_4h", "atr_4h", "date_4h"],
            counts["router_indicator_direction_topology"],
            {
                "data_readiness": 4,
                "mechanism_alignment": 4,
                "novelty_vs_current_contract": 4,
                "partition_evidence": 4,
                "governance_readiness": 3,
            },
            ["future strategy use would be a medium-risk structural change requiring human approval"],
        ),
        _ranked_observable(
            "completed_mark_futures_basis_sign",
            "sign of lag-safe completed 8h mark close relative to the matching futures close",
            "captures premium/discount pressure not represented by OHLCV router levels",
            ["8h mark close", "aggregated 1h futures close"],
            counts["completed_mark_futures_basis_sign"],
            {
                "data_readiness": 3,
                "mechanism_alignment": 3,
                "novelty_vs_current_contract": 4,
                "partition_evidence": 4,
                "governance_readiness": 3,
            },
            ["timestamp and near-zero measurement semantics need a separate contract review"],
        ),
        _ranked_observable(
            "funding_sign",
            "sign of the latest sealed 8h funding rate available before the signal",
            "separates long-crowded carry from short-crowded squeeze context",
            ["8h funding_rate close"],
            counts["funding_sign"],
            {
                "data_readiness": 4,
                "mechanism_alignment": 4,
                "novelty_vs_current_contract": 4,
                "partition_evidence": 2,
                "governance_readiness": 3,
            },
            ["minority category has only one observed pre-gate signal"],
        ),
        _ranked_observable(
            "volume_mean_direction",
            "direction of the existing rolling 1h volume mean",
            "approximates whether participation is building or fading",
            ["volume_mean"],
            counts["volume_mean_direction"],
            {
                "data_readiness": 4,
                "mechanism_alignment": 2,
                "novelty_vs_current_contract": 2,
                "partition_evidence": 4,
                "governance_readiness": 2,
            },
            ["overlaps the existing entry volume condition and has weaker causal specificity"],
        ),
        _ranked_observable(
            "close_return_direction",
            "sign of the latest 1h close-to-close move",
            "describes immediate approach direction into a mean-reversion setup",
            ["close"],
            counts["close_return_direction"],
            {
                "data_readiness": 4,
                "mechanism_alignment": 2,
                "novelty_vs_current_contract": 1,
                "partition_evidence": 4,
                "governance_readiness": 2,
            },
            ["high overlap with the existing price-extreme trigger and high noise risk"],
        ),
    ]
    eligible.sort(
        key=lambda item: (
            -item["score_total"],
            -item["scores"]["partition_evidence"],
            item["observable_id"],
        )
    )
    for rank, item in enumerate(eligible, 1):
        item["rank"] = rank

    rejected_or_deferred = [
        {
            "observable_id": "router_transition_state",
            "available_now": True,
            "pre_gate_coverage": counts["router_transition_state"],
            "selection_status": "rejected_whole_branch_equivalence",
            "reason": "all 12 signals occur in persisted R-R-R state",
        },
        {
            "observable_id": "duplicate_signal_episode_phase",
            "available_now": True,
            "selection_status": "rejected_closed_mechanism_not_reopened",
            "reason": "duplicate-signal lifecycle was already closed with no mechanism change warranted",
        },
        {
            "observable_id": "alpha_taker_open_interest_orderbook",
            "available_now": False,
            "selection_status": "blocked_missing_committed_history",
            "reason": "committed historical alpha/taker state is missing and OI/order-book history is not sealed",
        },
        {
            "observable_id": "cross_pair_relative_state",
            "available_now": False,
            "selection_status": "deferred_scope_expansion",
            "reason": "requires a separately governed pair-relative alignment contract",
        },
    ]
    inventory = {
        "schema_version": "ranging-short-structural-observable-inventory-v1",
        "audit_id": AUDIT_ID,
        "coverage_fingerprint": coverage["coverage_fingerprint"],
        "ranking_rubric": {
            "dimensions": [
                "data_readiness",
                "mechanism_alignment",
                "novelty_vs_current_contract",
                "partition_evidence",
                "governance_readiness",
            ],
            "dimension_range": [0, 4],
            "outcome_metrics_used": False,
            "tie_break": "higher partition evidence, then observable_id",
        },
        "eligible_observables": eligible,
        "rejected_or_deferred_observables": rejected_or_deferred,
        "selected_observable_id": eligible[0]["observable_id"],
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    inventory["inventory_fingerprint"] = fingerprint(inventory)
    return inventory


def build_decision(inventory: dict[str, Any]) -> dict[str, Any]:
    selected = inventory["eligible_observables"][0]
    decision = {
        "schema_version": "ranging-short-structural-observable-ranking-decision-v1",
        "audit_id": AUDIT_ID,
        "inventory_fingerprint": inventory["inventory_fingerprint"],
        "decision": "prioritize_router_indicator_direction_contract_review",
        "selected_observable_id": selected["observable_id"],
        "selected_rank": selected["rank"],
        "selected_pre_gate_coverage": selected["pre_gate_coverage"],
        "selection_basis": [
            "three nonzero natural categories",
            "no continuous cutoff",
            "no new dataset",
            "mechanism-aligned extension of the exhausted current-level router topology",
            "no outcome metrics used",
        ],
        "next_proposal_id": NEXT_PROPOSAL_ID,
        "next_proposal_status": "pending_human_review",
        "new_candidate_authorized": False,
        "backtest_authorized": False,
        "threshold_search_authorized": False,
        "validation_authorized": False,
        "holdout_authorized": False,
        "automatic_followup_authorized": False,
        "formal_branch_status": "retained_unchanged",
    }
    decision["decision_fingerprint"] = fingerprint(decision)
    return decision


def build_proposal(
    coverage: dict[str, Any], inventory: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    proposal = {
        "schema_version": "research-proposal-v1",
        "proposal_id": NEXT_PROPOSAL_ID,
        "title": "Ranging-short router indicator direction contract review",
        "status": "pending_human_review",
        "risk_class": "medium",
        "risk_reasons": ["strategy_structure", "new_structural_observable"],
        "objective": (
            "Freeze and audit a lag-safe categorical direction topology for "
            "ADX, BB-width and ATR before any Candidate or Backtest is considered."
        ),
        "hypothesis": (
            "The direction of existing 4h router indicators can distinguish "
            "structural ranging phases that current level votes collapse into R-R-R."
        ),
        "frozen_discovery_evidence": {
            "coverage_fingerprint": coverage["coverage_fingerprint"],
            "inventory_fingerprint": inventory["inventory_fingerprint"],
            "decision_fingerprint": decision["decision_fingerprint"],
            "observed_pre_gate_partition": decision[
                "selected_pre_gate_coverage"
            ],
        },
        "allowed_scope": [
            "formalize completed-4h anti-lookahead alignment",
            "replay categorical U-D-F coverage on the frozen 12-signal population",
            "audit redundancy against current router levels and closed mechanisms",
            "produce a candidate-feasibility decision for human review",
        ],
        "forbidden_scope": [
            "candidate_creation",
            "backtest",
            "outcome_metric_read",
            "continuous_threshold_search",
            "formal_strategy_change",
            "validation",
            "holdout",
            "automatic_followup_execution",
        ],
        "execution_budget": {
            "campaigns": 0,
            "experiments": 0,
            "candidate_creations": 0,
            "backtest_calls": 0,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        },
        "approval_route": "human_approval_required",
        "automatic_execution": False,
        "success_criteria": [
            "deterministic lag-safe direction contract",
            "nonzero and non-whole-branch categorical coverage",
            "no conflict with existing closure conditions",
            "explicit human decision before Candidate creation",
        ],
    }
    proposal["semantic_fingerprint"] = fingerprint(proposal)
    return proposal


def build_packet(
    repo: Path, coverage: dict[str, Any], inventory: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": "ranging-short-structural-discovery-packet-v1",
        "audit_id": AUDIT_ID,
        "status": "completed_read_only",
        "decision": decision["decision"],
        "selected_observable_id": decision["selected_observable_id"],
        "selected_pre_gate_coverage": decision["selected_pre_gate_coverage"],
        "coverage_path": COVERAGE_PATH.as_posix(),
        "coverage_sha256": sha256_file(repo / COVERAGE_PATH),
        "inventory_path": INVENTORY_PATH.as_posix(),
        "inventory_sha256": sha256_file(repo / INVENTORY_PATH),
        "decision_path": DECISION_PATH.as_posix(),
        "decision_sha256": sha256_file(repo / DECISION_PATH),
        "next_proposal_path": PROPOSAL_PATH.as_posix(),
        "next_proposal_sha256": sha256_file(repo / PROPOSAL_PATH),
        "next_proposal_status": "pending_human_review",
        "candidate_created": False,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "formal_strategy_modified": False,
        "automatic_followup_executed": False,
    }


def report_text(inventory: dict[str, Any], decision: dict[str, Any]) -> str:
    lines = [
        "# Ranging-short 结构观测量 Discovery 报告",
        "",
        "## 结论",
        "",
        "本批只做只读 Discovery，不创建 Candidate、不回测，也不读取收益结果。",
        "",
        "优先进入下一次人工审阅的是 `router_indicator_direction_topology`：",
        "比较 ADX、BB-width、ATR 相对上一根已完成 4h K 线的方向，现有 12 个 pre-gate 信号自然分成 `D-D-D=2`、`U-U-D=5`、`U-U-U=5`。",
        "",
        "## 排名",
        "",
        "| 排名 | 观测量 | 分数 | 覆盖 |",
        "|---:|---|---:|---|",
    ]
    for item in inventory["eligible_observables"]:
        coverage = ", ".join(
            f"{key}={value}" for key, value in item["pre_gate_coverage"].items()
        )
        lines.append(
            f"| {item['rank']} | `{item['observable_id']}` | "
            f"{item['score_total']}/20 | {coverage} |"
        )
    lines.extend(
        [
            "",
            "## 明确排除",
            "",
            "- router 状态切换：12/12 都是持续 `R-R-R`，等价于整个观测分支。",
            "- 重复信号 episode：旧机制审计已经闭环，本批不自动重开。",
            "- Alpha/Taker/OI/Order book：没有封存的历史源，不能编造。",
            "- 跨币种相对状态：需要单独的数据对齐与作用域审批。",
            "",
            "## 下一步边界",
            "",
            f"已编译 `{decision['next_proposal_id']}`，状态为 `pending_human_review`。",
            "该提案预算仍为零：只允许固化防未来函数的方向语义与覆盖复核；任何 Candidate、Backtest、Validation 或 Holdout 都要另行批准。",
            "",
        ]
    )
    return "\n".join(lines)


def update_state(
    repo: Path, coverage: dict[str, Any], inventory: dict[str, Any], decision: dict[str, Any]
) -> None:
    state = load_document(repo / STATE_PATH)
    state["ranging_short_structural_observable_discovery"] = {
        "audit_id": AUDIT_ID,
        "status": "completed_read_only",
        "decision": decision["decision"],
        "coverage_fingerprint": coverage["coverage_fingerprint"],
        "inventory_fingerprint": inventory["inventory_fingerprint"],
        "decision_fingerprint": decision["decision_fingerprint"],
        "pre_gate_signal_count": coverage["pre_gate_signal_count"],
        "selected_observable_id": decision["selected_observable_id"],
        "selected_pre_gate_coverage": decision["selected_pre_gate_coverage"],
        "next_proposal_id": decision["next_proposal_id"],
        "next_proposal_status": decision["next_proposal_status"],
        "candidate_created": False,
        "backtest_calls": 0,
        "threshold_search_run": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "formal_strategy_modified": False,
        "evidence": [
            COVERAGE_PATH.as_posix(),
            INVENTORY_PATH.as_posix(),
            DECISION_PATH.as_posix(),
            PROPOSAL_PATH.as_posix(),
            PACKET_PATH.as_posix(),
        ],
    }
    preflight.write_json_lf(repo / STATE_PATH, state)
    state_md = "\n".join(
        [
            "# 当前研究状态",
            "",
            f"- 当前项目：`{AUDIT_ID}`",
            "- 状态：`completed_read_only`",
            f"- 决策：`{decision['decision']}`",
            "- 已审计 pre-gate 信号：`12`",
            "- 首选结构观测量：`router_indicator_direction_topology`",
            "- 覆盖：`D-D-D=2 / U-U-D=5 / U-U-U=5`",
            f"- 下一提案：`{NEXT_PROPOSAL_ID}` / `pending_human_review`",
            "- Candidate / Backtest / Validation / Holdout：`0 / 0 / 0 / 0`",
            "- 正式 `ranging_short_entry`：保留且未修改",
            "",
            f"只读 Discovery 报告：`{REPORT_PATH.as_posix()}`。",
            "",
            "下一提案尚未获准执行；任何 Candidate 或回测仍需单独人工批准。",
            "",
        ]
    )
    (repo / STATE_MD_PATH).write_bytes(state_md.encode("utf-8"))


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
            AUDIT_ID,
            "stage4a-ranging-short-structural-observable-discovery-v1",
            AUDIT_ID,
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
        COVERAGE_PATH,
        INVENTORY_PATH,
        DECISION_PATH,
        PROPOSAL_PATH,
        PACKET_PATH,
        REPORT_PATH,
    ):
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets("
            "asset_id,run_id,artifact_type,path,sha256,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                f"{AUDIT_ID}:{path.as_posix()}",
                AUDIT_ID,
                "read_only_structural_discovery",
                path.as_posix(),
                sha256_file(repo / path),
                COMPLETED_AT,
            ),
        )
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise StructuralDiscoveryInvalid("registry_integrity_failed")
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
    coverage = build_coverage(repo)
    inventory = build_inventory(coverage)
    decision = build_decision(inventory)
    proposal = build_proposal(coverage, inventory, decision)
    if write:
        preflight.write_json_lf(repo / COVERAGE_PATH, coverage)
        preflight.write_json_lf(repo / INVENTORY_PATH, inventory)
        preflight.write_json_lf(repo / DECISION_PATH, decision)
        preflight.write_json_lf(repo / PROPOSAL_PATH, proposal)
        packet = build_packet(repo, coverage, inventory, decision)
        preflight.write_json_lf(repo / PACKET_PATH, packet)
        report = repo / REPORT_PATH
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_bytes(report_text(inventory, decision).encode("utf-8"))
        if update_current_state:
            update_state(repo, coverage, inventory, decision)
        if record_registry_state:
            record_registry(repo, decision)
    return {
        "coverage": coverage,
        "inventory": inventory,
        "decision": decision,
        "proposal": proposal,
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
    except (StructuralDiscoveryInvalid, preflight.RouterContextPreflightInvalid) as exc:
        print(json.dumps({"status": "structural_discovery_invalid", "detail": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": "completed_read_only",
                "decision": result["decision"]["decision"],
                "selected": result["decision"]["selected_observable_id"],
                "coverage": result["decision"]["selected_pre_gate_coverage"],
                "next_proposal_status": result["proposal"]["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
