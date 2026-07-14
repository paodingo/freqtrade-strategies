#!/usr/bin/env python3
"""Compile one non-forbidden Research Proposal into a dry-run Campaign Spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ranging_short_router_context import (
    build_context_contract,
    context_contract_fingerprint,
)
from research_control import load_campaign
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    proposal_fingerprint,
    sha256_file,
    utc_now,
    write_json,
    write_yaml,
)
from protected_manifest_hash import canonical_text_sha256
from route_research_approval import route_proposal


REQUIRED_PROPOSAL_FIELDS = {
    "proposal_id", "research_question", "supporting_evidence", "expected_information_gain",
    "proposed_method", "immutable_inputs", "allowed_changes", "forbidden_changes",
    "required_datasets", "required_runtime", "required_policy", "estimated_experiments",
    "estimated_wall_clock_minutes", "risk_class", "stop_conditions", "success_criteria",
    "required_artifacts", "required_tests", "semantic_fingerprint",
}

BRANCH_FACTORIZATION_PROPOSAL_ID = "regime-conditioned-branch-factorization-v1"
BRANCH_FACTORIZATION_APPROVAL = (
    "research/governance/approvals/"
    "regime-conditioned-branch-factorization-v1-compilation-approval.json"
)
BRANCH_ABLATION_PROPOSAL_ID = "branch-contribution-ablation-v1"
BRANCH_ABLATION_APPROVAL = (
    "research/governance/approvals/"
    "branch-contribution-ablation-v1-compilation-approval.json"
)
RANGING_SHORT_DECISION_PROPOSAL_ID = "ranging-short-branch-decision-review-v1"
RANGING_SHORT_DECISION_APPROVAL = (
    "research/governance/approvals/"
    "ranging-short-branch-decision-review-v1-compilation-approval.json"
)
REGIME_CONDITIONED_ROUTING_PROPOSAL_ID = "regime-conditioned-ranging-short-routing-v1"
REGIME_CONDITIONED_ROUTING_APPROVAL = (
    "research/governance/approvals/"
    "regime-conditioned-ranging-short-routing-v1-compilation-approval.json"
)
ROUTER_CARRY_CONTEXT_PROPOSAL_ID = "ranging-short-router-carry-context-review-v1"
ROUTER_CARRY_CONTEXT_APPROVAL = (
    "research/governance/approvals/"
    "ranging-short-router-carry-context-review-v1-compilation-approval.json"
)


def regime_conditioned_routing_plan(repo: Path, proposal: dict[str, Any]) -> dict[str, Any] | None:
    """Freeze a read-only routing evidence review without authorizing execution."""
    if proposal["proposal_id"] != REGIME_CONDITIONED_ROUTING_PROPOSAL_ID:
        return None

    retention_rel = "research/closures/ranging-short-branch-retention-review-v1.json"
    temporal_rel = "research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json"
    structure_rel = "research/analysis/regime-conditioned-branch-factorization/current-structure-map.json"
    equivalence_rel = (
        "research/analysis/regime-conditioned-branch-factorization/"
        "recertification-attempt-3-semantic-equivalence-result.json"
    )
    retention = load_document(repo / retention_rel)
    temporal = load_document(repo / temporal_rel)
    structure = load_document(repo / structure_rel)
    equivalence = load_document(repo / equivalence_rel)
    approval = load_document(repo / REGIME_CONDITIONED_ROUTING_APPROVAL)

    retention_status = retention.get("closure_status") or retention.get("research_status") or retention.get("status")
    if retention_status != "closed_mixed_temporal_dependency":
        raise ValueError("ranging-short retention closure is not frozen")
    formal_retained = retention.get("formal_branch_retained") is True or retention.get("formal_branch_action") == "retained_unchanged"
    if not formal_retained:
        raise ValueError("formal ranging_short_entry is not retained")
    if temporal.get("classification") != "branch_mixed_temporal_dependency":
        raise ValueError("temporal contribution evidence is not the approved mixed result")
    if temporal.get("validation_accesses") != 0 or temporal.get("holdout_accesses") != 0:
        raise ValueError("sealed data access detected in temporal contribution evidence")
    if approval.get("proposal_fingerprint") != proposal["semantic_fingerprint"]:
        raise ValueError("routing compilation approval fingerprint mismatch")
    if approval.get("approval_status") != "approved_for_compilation_only":
        raise ValueError("routing proposal is not approved for compilation")
    if approval.get("execution_authorized") is not False:
        raise ValueError("routing compilation approval cannot authorize execution")
    equivalence_status = equivalence.get("status") or equivalence.get("classification")
    if equivalence_status != "router_extraction_semantic_equivalence_verified":
        raise ValueError("router extraction is not a verified semantic baseline")

    expected_slices = {
        "ranging-short-ablation-s01": "inconclusive",
        "ranging-short-ablation-s02": "positive_contributor",
        "ranging-short-ablation-s03": "negative_contributor",
        "ranging-short-ablation-s04": "negative_contributor",
    }
    classification_aliases = {
        "branch_contribution_inconclusive": "inconclusive",
        "branch_positive_contributor": "positive_contributor",
        "branch_negative_contributor": "negative_contributor",
    }
    slice_conclusions: dict[str, str] = {}
    for full_id, expected in expected_slices.items():
        item = (temporal.get("slice_results") or {}).get(full_id)
        if not item:
            raise ValueError(f"missing frozen temporal slice: {full_id}")
        normalized = classification_aliases.get(item.get("classification"), item.get("classification"))
        if normalized != expected:
            raise ValueError(f"temporal slice conclusion drift: {full_id}")
        slice_conclusions[full_id.rsplit("-", 1)[-1]] = normalized

    evidence = [
        (retention_rel, "human_retention_closure"),
        (temporal_rel, "four_slice_mixed_temporal_contribution"),
        (structure_rel, "verified_router_and_branch_structure"),
        (equivalence_rel, "router_semantic_equivalence_baseline"),
    ]
    return {
        "schema_version": "regime-conditioned-ranging-short-routing-plan-v1",
        "research_unit": "regime_conditioned_routing_evidence_matrix_v1",
        "authority": "compile_and_human_review_only",
        "execution_authorized": False,
        "compilation_approval": {
            "path": REGIME_CONDITIONED_ROUTING_APPROVAL,
            "approval_status": approval["approval_status"],
            "approver_type": approval["approver_type"],
            "execution_authorized": False,
            "semantic_fingerprint": fingerprint(
                {key: value for key, value in approval.items() if key != "approved_at"}
            ),
        },
        "formal_branch_status": "retained_unchanged",
        "whole_branch_deletion_reopened": False,
        "threshold_research_reopened": False,
        "slice_conclusions": slice_conclusions,
        "evidence_sources": [
            {
                "path": path,
                "sha256": canonical_text_sha256(repo / path),
                "role": role,
            }
            for path, role in evidence
        ],
        "structure_inventory": {
            "condition_count": structure.get("condition_count"),
            "signal_group_count": structure.get("signal_group_count"),
            "source": structure_rel,
            "router_equivalence_status": equivalence_status,
        },
        "single_variable_rule": {
            "allowed_future_change_count": 1,
            "required": "one_predeclared_router_context_gate_for_ranging_short_entry_only",
            "forbidden": [
                "time_slice_used_as_regime_proxy",
                "threshold_change",
                "entry_or_exit_logic_change",
                "whole_branch_deletion",
                "multiple_router_or_branch_changes",
            ],
        },
        "current_execution_budget": {
            "max_candidates": 0,
            "max_backtest_calls": 0,
            "max_validation_accesses": 0,
            "max_holdout_accesses": 0,
            "max_wall_clock_minutes": 30,
        },
        "future_separate_approval_envelope": {
            "max_candidates": 1,
            "max_backtest_calls": 16,
            "backtest_formula": "4 frozen Development slices x Baseline/Candidate x RUN-A/RUN-B",
            "additional_temporal_slices": 0,
            "max_validation_accesses": 0,
            "max_holdout_accesses": 0,
            "requires_exact_router_context": True,
            "requires_new_proposal_and_campaign_fingerprints": True,
            "requires_human_execution_approval": True,
        },
        "decision_taxonomy": [
            "routing_hypothesis_worth_compiling",
            "insufficient_router_context_evidence",
            "retain_branch_no_routing_change",
            "closure_conflict",
        ],
        "preparation_recommendation": "insufficient_router_context_evidence",
        "recommendation_reason": (
            "The four frozen slices establish time dependency, but they do not attribute the sign change "
            "to a predeclared router context. A time slice cannot be substituted for a market regime."
        ),
    }


def router_carry_context_plan(
    repo: Path, proposal: dict[str, Any]
) -> dict[str, Any] | None:
    """Freeze the approved single router context without authorizing execution."""
    if proposal["proposal_id"] != ROUTER_CARRY_CONTEXT_PROPOSAL_ID:
        return None

    approval = load_document(repo / ROUTER_CARRY_CONTEXT_APPROVAL)
    context = build_context_contract(repo)
    temporal_path = (
        repo
        / "research/analysis/ranging-short-temporal-review-v1/"
        "temporal-contribution-result.json"
    )
    temporal = load_document(temporal_path)

    if proposal_fingerprint(proposal) != proposal["semantic_fingerprint"]:
        raise ValueError("router context proposal fingerprint drift")
    if proposal["proposed_method"].get("router_context") != context:
        raise ValueError("router context contract drift")
    if approval.get("proposal_fingerprint") != proposal["semantic_fingerprint"]:
        raise ValueError("router context compilation approval fingerprint mismatch")
    if (
        approval.get("approval_status") != "approved_for_compilation_only"
        or approval.get("execution_authorized") is not False
        or approval.get("candidate_creation_authorized") is not False
        or approval.get("backtest_authorized") is not False
        or approval.get("validation_authorized") is not False
        or approval.get("holdout_authorized") is not False
    ):
        raise ValueError("router context compilation approval scope mismatch")
    if temporal.get("classification") != "branch_mixed_temporal_dependency":
        raise ValueError("router context temporal evidence drift")
    if temporal.get("validation_accesses") != 0 or temporal.get("holdout_accesses") != 0:
        raise ValueError("router context sealed-data access detected")

    slice_order = ["s01", "s02", "s03", "s04"]
    expected = {
        "s01": "branch_contribution_inconclusive",
        "s02": "branch_positive_contributor",
        "s03": "branch_negative_contributor",
        "s04": "branch_negative_contributor",
    }
    for short_id in slice_order:
        full_id = f"ranging-short-ablation-{short_id}"
        item = (temporal.get("slice_results") or {}).get(full_id)
        if not item or item.get("classification") != expected[short_id]:
            raise ValueError(f"router context temporal slice drift: {short_id}")

    return {
        "schema_version": "ranging-short-router-carry-context-plan-v1",
        "research_unit": "ranging_state_without_current_range_signal",
        "authority": "compile_and_human_review_only",
        "execution_authorized": False,
        "context_contract": context,
        "context_contract_fingerprint": context_contract_fingerprint(context),
        "compilation_approval": {
            "path": ROUTER_CARRY_CONTEXT_APPROVAL,
            "approval_status": approval["approval_status"],
            "approver_type": approval["approver_type"],
            "execution_authorized": False,
            "semantic_fingerprint": fingerprint(
                {key: value for key, value in approval.items() if key != "approved_at"}
            ),
        },
        "slice_policy_fingerprint": temporal["slice_policy_fingerprint"],
        "slice_order": slice_order,
        "slice_conclusions": {
            "s01": "inconclusive",
            "s02": "positive_contributor",
            "s03": "negative_contributor",
            "s04": "negative_contributor",
        },
        "coverage_gate": {
            "required_before_backtest": True,
            "context_pre_gate_intersection_min": 1,
            "both_context_states_required": True,
            "result_independent_selection": True,
            "failure_code": "router_context_coverage_insufficient",
        },
        "single_variable_rule": {
            "allowed_future_change_count": 1,
            "allowed_future_change": (
                "gate ranging_short_entry only when the frozen context mask is true"
            ),
            "formal_branch_status": "retained_unchanged",
            "threshold_change_authorized": False,
            "router_change_authorized": False,
        },
        "current_execution_budget": {
            "max_candidates": 0,
            "max_backtest_calls": 0,
            "max_validation_accesses": 0,
            "max_holdout_accesses": 0,
        },
        "future_separate_approval_envelope": {
            "max_candidates": 1,
            "max_backtest_calls": 16,
            "backtest_formula": (
                "4 frozen Development slices x Baseline/Candidate x RUN-A/RUN-B"
            ),
            "additional_temporal_slices": 0,
            "max_validation_accesses": 0,
            "max_holdout_accesses": 0,
            "requires_new_human_execution_approval": True,
        },
        "decision_taxonomy": [
            "router_context_negative_contributor",
            "router_context_positive_contributor",
            "router_context_mixed_temporal_dependency",
            "router_context_redundant",
            "router_context_contribution_inconclusive",
            "router_context_execution_invalid",
        ],
    }


def _decision_review_proposal(repo: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    if proposal["proposal_id"] != RANGING_SHORT_DECISION_PROPOSAL_ID:
        return proposal
    approval = load_document(repo / RANGING_SHORT_DECISION_APPROVAL)
    if proposal_fingerprint(proposal) != proposal["semantic_fingerprint"]:
        raise ValueError("decision review proposal fingerprint drift")
    if approval.get("proposal_fingerprint") != proposal["semantic_fingerprint"]:
        raise ValueError("decision review compilation approval fingerprint mismatch")
    if approval.get("approval_status") != "approved_for_compilation_only" or approval.get("execution_authorized") is not False:
        raise ValueError("decision review is not compilation-only")
    return {
        **proposal,
        "title": "Ranging-short branch decision review",
        "supporting_evidence": [
            {"path": "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json", "claim": "The approved Development-only ablation completed with branch_negative_contributor."},
            {"path": "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-btc-contribution-comparison.json", "claim": "BTC Development supplies formal-policy-scope contribution evidence."},
            {"path": "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-eth-contribution-comparison.json", "claim": "ETH Development supplies descriptive cross-pair evidence."},
        ],
        "expected_information_gain": "high_decision_clarity_from_metric_and_policy_semantics",
        "proposed_method": {"type": "dry_run_decision_review", "steps": ["audit metric direction and units", "compare BTC evidence with Balanced Research Gate v1", "freeze Validation, temporal and retain options for human review"]},
        "immutable_inputs": ["formal_strategy", "frozen_candidate", "evaluation_policy", "development_datasets", "runtime", "exchange_snapshot", "ablation_evidence"],
        "allowed_changes": [f"research/director/compiled/{RANGING_SHORT_DECISION_PROPOSAL_ID}/**", "research/director/current-research-state.json", "research/director/current-research-state.md", "research/director/registry-records.json", f"reports/audits/{RANGING_SHORT_DECISION_PROPOSAL_ID}/**", "tests/test_ranging_short_branch_decision_review_compilation.py"],
        "forbidden_changes": ["formal strategy or base", "ranging_short_entry", "Candidate source or manifest", "Evaluation Policy", "Dataset or Snapshot", "Runtime", "new Candidate", "Backtest", "Validation", "Holdout", "temporal slices", "Hyperopt", "automatic execution"],
        "required_datasets": [
            {"dataset_id": "futures-dev-btc-usdt-usdt-20240101-20240830-v2", "access": "existing_development_evidence_only", "manifest_sha256": "e60ecbb9c28be5910bf1d33c6ed03bf46798228a343670b71a738b4b9150cc13"},
            {"dataset_id": "futures-dev-eth-usdt-usdt-20240101-20240830-v1", "access": "existing_descriptive_development_evidence_only", "manifest_sha256": "6557a265a1d2904452a236a84e1afeb9db4508e0ec6952a134ca494d2433b925"},
        ],
        "required_runtime": {"path": "research/runtime/freqtrade-runtime.yaml", "sha256": "e87e375a8c61d8b7eeae8e53fc0715840956ea617471ad9c7d06275d9726f76d"},
        "required_policy": {"path": "research/evaluation/evaluation-policy.yaml", "sha256": "ee4769e4c814e209e771c31fa35ff4d8c4719137fffe7291d3ae87d73c8e8b5e", "application": "BTC_formal_ETH_descriptive_no_policy_change"},
        "estimated_experiments": 3,
        "estimated_wall_clock_minutes": 30,
        "stop_conditions": ["metric_semantics_anomaly", "proposal_or_campaign_fingerprint_drift", "formal_strategy_candidate_policy_runtime_or_dataset_drift", "Validation_or_Holdout_access", "Backtest_or_Candidate_creation", "human_stop"],
        "success_criteria": ["metric semantics are deterministic", "Balanced Research Gate applicability is explicit", "three options have exact budgets", "recommendation uses the approved four-state taxonomy"],
        "required_artifacts": ["metric-semantics-audit.json", "decision-options.json", "human-decision-packet.json", "decision-review.md"],
        "required_tests": ["proposal fingerprint test", "metric arithmetic and unit test", "policy gate mapping test", "no execution or protected mutation test"],
    }


def ranging_short_decision_plan(repo: Path, proposal: dict[str, Any]) -> dict[str, Any] | None:
    if proposal["proposal_id"] != RANGING_SHORT_DECISION_PROPOSAL_ID:
        return None
    approval = load_document(repo / RANGING_SHORT_DECISION_APPROVAL)
    result_path = repo / "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json"
    result = load_document(result_path)
    policy = load_document(repo / "research/evaluation/evaluation-policy.yaml")
    candidate_path = repo / "research/candidates/branch-contribution-ablation-v1/1/candidate-manifest.json"
    candidate = load_document(candidate_path)
    if result.get("classification") != "branch_negative_contributor" or result.get("validation_accesses") != 0 or result.get("holdout_accesses") != 0:
        raise ValueError("ablation evidence is not the approved Development-only result")
    if candidate.get("source_sha256") != "e20dd42d2ba8a11ac2b832ad610c8f25cce28e6c92b74959ba0cce286c753eb0":
        raise ValueError("frozen ablation Candidate drift")
    if "ranging_short" not in (repo / "strategies/regime_aware_base.py").read_text(encoding="utf-8"):
        raise ValueError("formal strategy no longer contains ranging_short_entry")

    metric_audit: dict[str, Any] = {}
    arithmetic_ok = True
    for pair in ("btc", "eth"):
        evidence = result["pair_results"][pair]
        baseline, candidate_metrics = evidence["baseline_metrics"], evidence["candidate_metrics"]
        delta, cost_delta = evidence["candidate_minus_baseline"], evidence["candidate_minus_baseline_costs"]
        checks = {
            "total_profit": abs((candidate_metrics["total_profit"] - baseline["total_profit"]) - delta["total_profit"]) < 1e-9,
            "total_profit_pct": abs((candidate_metrics["total_profit_pct"] - baseline["total_profit_pct"]) - delta["total_profit_pct"]) < 1e-12,
            "profit_factor": abs((candidate_metrics["profit_factor"] - baseline["profit_factor"]) - delta["profit_factor"]) < 1e-12,
            "max_drawdown": abs((candidate_metrics["max_drawdown"] - baseline["max_drawdown"]) - delta["max_drawdown"]) < 1e-9,
            "funding_fees": abs((evidence["candidate_costs"]["funding_fees"] - evidence["baseline_costs"]["funding_fees"]) - cost_delta["funding_fees"]) < 1e-12,
            "trading_fee_cost": abs((evidence["candidate_costs"]["trading_fee_cost"] - evidence["baseline_costs"]["trading_fee_cost"]) - cost_delta["trading_fee_cost"]) < 1e-12,
        }
        arithmetic_ok = arithmetic_ok and all(checks.values())
        metric_audit[pair] = {
            "calculation_direction": "candidate_minus_baseline",
            "arithmetic_checks": checks,
            "metrics": {
                "total_profit": {"unit": "USDT", "kind": "absolute", "baseline": baseline["total_profit"], "candidate": candidate_metrics["total_profit"], "delta": delta["total_profit"]},
                "total_return": {"stored_unit": "ratio", "display_unit": "percent", "delta_kind": "percentage_points", "baseline_ratio": baseline["total_profit_pct"], "candidate_ratio": candidate_metrics["total_profit_pct"], "baseline_percent": baseline["total_profit_pct"] * 100, "candidate_percent": candidate_metrics["total_profit_pct"] * 100, "delta_percentage_points": delta["total_profit_pct"] * 100},
                "profit_factor": {"unit": "ratio", "kind": "dimensionless_absolute_difference", "baseline": baseline["profit_factor"], "candidate": candidate_metrics["profit_factor"], "delta": delta["profit_factor"]},
                "max_drawdown": {"unit": "USDT", "kind": "absolute_not_percentage_point", "baseline": baseline["max_drawdown"], "candidate": candidate_metrics["max_drawdown"], "delta": delta["max_drawdown"], "improvement_direction": "lower_is_better", "interpretation": "negative delta means Candidate reduced absolute drawdown; positive delta means absolute drawdown worsened"},
                "trading_fee_cost": {"unit": "USDT", "kind": "absolute", "baseline": evidence["baseline_costs"]["trading_fee_cost"], "candidate": evidence["candidate_costs"]["trading_fee_cost"], "delta": cost_delta["trading_fee_cost"]},
                "funding_fees": {"unit": "USDT", "kind": "absolute", "baseline": evidence["baseline_costs"]["funding_fees"], "candidate": evidence["candidate_costs"]["funding_fees"], "delta": cost_delta["funding_fees"]},
            },
        }
    metric_status = "passed" if arithmetic_ok else "metric_semantics_review_required"
    recommendation = "temporal_ablation_review_worth_authorizing" if arithmetic_ok else "metric_semantics_review_required"
    return {
        "schema_version": "ranging-short-branch-decision-review-plan-v1",
        "compilation_approval": {"path": RANGING_SHORT_DECISION_APPROVAL, "sha256": sha256_file(repo / RANGING_SHORT_DECISION_APPROVAL), "approval_status": approval["approval_status"], "execution_authorized": False},
        "metric_semantics_audit": {"status": metric_status, "all_arithmetic_consistent": arithmetic_ok, "pairs": metric_audit, "eth_max_drawdown_delta_meaning": "291.71629049 - 340.65008476 = -48.93379427 USDT; the Candidate reduced absolute max drawdown by 48.93379427 USDT. This is not a percentage or percentage-point delta."},
        "development_gate_audit": {
            "policy_id": policy["policy_id"], "formal_scope": "BTC/USDT:USDT 1h only", "eth_role": "descriptive_cross_pair_only",
            "coverage_gate": {"status": "partially_satisfied_not_formally_established", "passed_available_counts": {"total_trades": 25, "long_trades": 7, "short_trades": 18}, "missing_for_formal_gate": ["active_weeks", "complete_7_day_step_rolling_windows"]},
            "behavior_materiality": {"status": "satisfied", "evidence": "10 BTC signals and 2 BTC trades removed; normalized trade hash changed"},
            "no_material_degradation": {"status": "not_formally_established", "available": {"total_return_delta_percentage_points": result["pair_results"]["btc"]["candidate_minus_baseline"]["total_profit_pct"] * 100, "profit_factor_delta": result["pair_results"]["btc"]["candidate_minus_baseline"]["profit_factor"]}, "missing": ["max_drawdown_delta_percentage_points", "approved cost-stress outputs"]},
            "material_improvement": {"status": "not_met_on_available_metrics", "thresholds": policy["development_material_improvement_any"], "observed": {"total_return_delta_percentage_points": result["pair_results"]["btc"]["candidate_minus_baseline"]["total_profit_pct"] * 100, "profit_factor_delta": result["pair_results"]["btc"]["candidate_minus_baseline"]["profit_factor"], "max_drawdown_improvement_percentage_points": None}},
            "directional_coverage": {"status": "satisfied", "baseline": {"long": 7, "short": 20}, "candidate": {"long": 7, "short": 18}, "minimum_absolute": 2, "minimum_fraction_of_baseline": 0.5},
            "development_eligible": False,
            "reason": "The Campaign measured one branch contribution. It did not run the complete Balanced Research Gate evidence set, cost stress, lookahead/recursive checks, policy rolling windows or percentage-point drawdown projection.",
        },
        "evidence_scope": {"btc_development": "formal_policy_scope_contribution_only", "eth_development": "descriptive_cross_pair_only", "temporal_evidence": "insufficient_no_pre_frozen_ablation_slices", "validation": "not_run", "holdout": "not_run", "forward_dry_run": "not_run"},
        "frozen_candidate": {"reused": True, "new_candidate_required": False, "path": candidate["source_path"], "class_name": candidate["class_name"], "source_sha256": candidate["source_sha256"], "manifest_path": candidate_path.relative_to(repo).as_posix(), "manifest_sha256": sha256_file(candidate_path)},
        "options": {
            "A_validation": {"decision_state": "validation_review_worth_authorizing", "recommended_now": False, "budget": {"candidate_creation": 0, "backtest_calls": 2, "formula": "BTC Validation x Baseline/Candidate x one disclosed run", "validation_accesses": 1, "holdout_accesses": 0, "max_retries": 0, "max_wall_clock_minutes": 60}, "requires_new_human_approval": ["one BTC Validation access", "two frozen Baseline/Candidate Backtest calls", "limited disclosure and contamination handling"]},
            "B_temporal": {"decision_state": "temporal_ablation_review_worth_authorizing", "recommended_now": arithmetic_ok, "budget": {"candidate_creation": 0, "candidate_reused": 1, "pre_frozen_slices": 4, "backtest_calls": 16, "formula": "4 slices x Baseline/Candidate x RUN-A/RUN-B", "validation_accesses": 0, "holdout_accesses": 0, "max_retries": 0, "max_wall_clock_minutes": 240}, "requires_new_human_approval": ["four exact temporal boundaries", "16 Development-only Backtest calls", "240-minute budget"]},
            "C_retain": {"decision_state": "retain_branch_insufficient_evidence", "recommended_now": False, "budget": {"candidate_creation": 0, "backtest_calls": 0, "validation_accesses": 0, "holdout_accesses": 0}, "reopen_conditions": ["human-approved temporal ablation", "human-approved single BTC Validation review", "metric semantics defect discovery"]},
        },
        "recommendation": recommendation,
        "insufficient_to_remove_formal_branch": ["no Validation", "no pre-frozen temporal ablation", "no complete Development Gate classification", "ETH is descriptive only", "formal strategy remains execution baseline"],
        "execution_boundary": {"compiled_only": True, "campaign_executed": False, "candidate_created": False, "backtest_run": False, "validation_accesses": 0, "holdout_accesses": 0, "automatic_followup": False},
    }


def verify_evidence(repo: Path, proposal: dict[str, Any]) -> list[dict[str, Any]]:
    checked = []
    for item in proposal.get("supporting_evidence") or []:
        path = repo / item["path"]
        if not path.is_file():
            raise ValueError(f"proposal evidence missing: {item['path']}")
        checked.append({"path": item["path"], "sha256": sha256_file(path), "claim": item["claim"]})
    return checked


def branch_factorization_plan(repo: Path, proposal: dict[str, Any]) -> dict[str, Any] | None:
    if proposal["proposal_id"] != BRANCH_FACTORIZATION_PROPOSAL_ID:
        return None
    approval = load_document(repo / BRANCH_FACTORIZATION_APPROVAL)
    if approval.get("proposal_fingerprint") != proposal["semantic_fingerprint"]:
        raise ValueError("compilation approval proposal fingerprint mismatch")
    if approval.get("approval_status") != "approved_for_compilation_only":
        raise ValueError("proposal is not approved for compilation")
    if approval.get("execution_authorized") is not False:
        raise ValueError("compilation-only approval cannot authorize execution")

    graph = load_document(repo / "research/analysis/regime-aware-condition-graph.json")
    conditions = graph.get("conditions") or []
    groups = graph.get("signal_groups") or []
    if len(conditions) != 29 or len(groups) != 5:
        raise ValueError("condition graph is not the approved 29-condition/5-group structure")
    group_membership: dict[str, list[str]] = {}
    condition_by_id = {item["condition_id"]: item for item in conditions}
    for group in groups:
        for condition_id in group["conditions"]:
            group_membership.setdefault(condition_id, []).append(group["group_id"])
            for operand in condition_by_id.get(condition_id, {}).get("operands") or []:
                if operand in condition_by_id:
                    group_membership.setdefault(operand, []).append(group["group_id"])
        setup_id = f"{group['branch']}_setup"
        if setup_id in condition_by_id:
            group_membership.setdefault(setup_id, []).append(group["group_id"])
    ownership = []
    for condition in conditions:
        side = condition["side"]
        owner = "shared_router" if side == "both" else f"{side}_branch"
        memberships = sorted(set(group_membership.get(condition["condition_id"], [])))
        ownership.append(
            {
                "condition_id": condition["condition_id"],
                "owner": owner,
                "side": side,
                "signal": condition["signal"],
                "signal_groups": memberships,
                "regime_branches": sorted({item.split("_", 1)[0] for item in memberships}),
            }
        )
    owner_counts = {
        owner: sum(item["owner"] == owner for item in ownership)
        for owner in ("shared_router", "long_branch", "short_branch")
    }


def branch_contribution_ablation_plan(repo: Path, proposal: dict[str, Any]) -> dict[str, Any] | None:
    if proposal["proposal_id"] != BRANCH_ABLATION_PROPOSAL_ID:
        return None
    approval = load_document(repo / BRANCH_ABLATION_APPROVAL)
    if approval.get("proposal_fingerprint") != proposal["semantic_fingerprint"]:
        raise ValueError("compilation approval proposal fingerprint mismatch")
    if approval.get("approval_status") != "approved_for_compilation_only":
        raise ValueError("proposal is not approved for compilation")
    if approval.get("execution_authorized") is not False:
        raise ValueError("compilation-only approval cannot authorize execution")

    router_result_path = (
        repo
        / "research/analysis/regime-conditioned-branch-factorization/"
        "recertification-attempt-3-semantic-equivalence-result.json"
    )
    router_result = load_document(router_result_path)
    if router_result.get("status") != "router_extraction_semantic_equivalence_verified":
        raise ValueError("router extraction is not a verified structural baseline")
    structure = load_document(
        repo / "research/analysis/regime-conditioned-branch-factorization/current-structure-map.json"
    )
    condition_graph_path = repo / "research/analysis/regime-aware-condition-graph.json"
    condition_graph = load_document(condition_graph_path)
    groups = condition_graph.get("signal_groups") or []
    if len(groups) != 5 or structure.get("condition_count") != 29 or structure.get("signal_group_count") != 5:
        raise ValueError("ablation structure is not the approved 29-condition/5-group graph")
    units = [
        {
            "unit_id": group["group_id"],
            "branch": group["branch"],
            "regime": group["branch"].split("_", 1)[0],
            "side": group["side"],
            "signal": group["signal"],
            "conditions": group["conditions"],
            "eligible_as_single_candidate_unit": True,
            "source": "research/analysis/regime-aware-condition-graph.json",
        }
        for group in groups
    ]
    units.append(
        {
            "unit_id": "shared_regime_router",
            "branch": "shared_router",
            "regime": "shared",
            "side": "both",
            "signal": "dispatch",
            "conditions": [
                item["condition_id"]
                for item in structure.get("condition_ownership") or []
                if item.get("owner") == "shared_router"
            ],
            "eligible_as_single_candidate_unit": False,
            "ineligibility_reason": "router extraction is the verified structural baseline and cannot be ablated in this Campaign",
            "source": "research/analysis/regime-conditioned-branch-factorization/current-structure-map.json",
        }
    )
    return {
        "schema_version": "branch-contribution-ablation-plan-v1",
        "compilation_approval": {
            "path": BRANCH_ABLATION_APPROVAL,
            "sha256": sha256_file(repo / BRANCH_ABLATION_APPROVAL),
            "approval_status": "approved_for_compilation_only",
            "execution_authorized": False,
        },
        "verified_baseline": {
            "formal_execution_baseline": "RegimeAwareV6",
            "router_equivalent_structural_reference": "RegimeAwareRouterEquivalentV1",
            "router_result_path": router_result_path.relative_to(repo).as_posix(),
            "router_result_sha256": sha256_file(router_result_path),
            "router_result_status": router_result["status"],
            "btc_trade_count": router_result["comparisons"]["btc"]["total_trades"],
            "eth_trade_count": router_result["comparisons"]["eth"]["total_trades"],
        },
        "structure_source": {
            "path": "research/analysis/regime-conditioned-branch-factorization/current-structure-map.json",
            "sha256": sha256_file(repo / "research/analysis/regime-conditioned-branch-factorization/current-structure-map.json"),
            "condition_graph_path": "research/analysis/regime-aware-condition-graph.json",
            "condition_graph_sha256": sha256_file(condition_graph_path),
            "condition_count": 29,
            "signal_group_count": 5,
        },
        "ablation_units": units,
        "single_structural_variable_contract": {
            "candidate_count": 1,
            "selected_unit_count": 1,
            "selection_status": "requires_human_execution_approval",
            "forbidden_combinations": [
                "long_and_short_together",
                "multiple_regimes_together",
                "entry_and_exit_together",
                "router_and_branch_together",
                "threshold_or_risk_or_execution_change",
            ],
        },
        "reversible_ablation_mechanism": {
            "method": "preserve_and_gate_one_final_signal_group_in_isolated_candidate",
            "preserve": ["original_branch_code", "original_conditions", "original_tags", "original_source_locations"],
            "candidate_manifest_fields": ["selected_ablation_unit", "ablation_mechanism", "preserved_source_sha256", "single_variable_diff_allowlist"],
            "large_code_deletion_allowed": False,
        },
        "evaluation_design": {
            "pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
            "datasets": "sealed_development_only",
            "repetitions": ["RUN-A", "RUN-B"],
            "comparisons": ["Baseline_RUN_A_RUN_B", "Candidate_RUN_A_RUN_B", "Baseline_Candidate_per_pair"],
            "planned_backtest_invocations": 8,
            "formula": "2 roles x 2 pairs x 2 fresh-process repetitions",
            "temporal_slices_in_initial_campaign": 0,
            "temporal_policy": "rolling-window attribution from the approved full development runs; new slice backtests require separate human approval",
            "balanced_research_gate": "descriptive_context_only_not_a_promotion_gate",
            "formal_promotion_allowed": False,
        },
        "contribution_metrics": [
            "removed_branch_original_signal_count",
            "actual_trade_count_delta",
            "long_short_trade_delta",
            "return_delta",
            "profit_factor_delta",
            "max_drawdown_delta",
            "fee_and_funding_delta",
            "rolling_window_delta",
            "temporal_slice_delta_if_separately_approved",
            "pair_level_delta",
            "remaining_branch_behavior",
            "normalized_trade_hash",
        ],
        "decision_classifications": [
            "branch_positive_contributor",
            "branch_negative_contributor",
            "branch_mixed_regime_dependent",
            "branch_redundant",
            "branch_contribution_inconclusive",
            "ablation_execution_invalid",
        ],
        "budget": {
            "max_candidates": 1,
            "max_backtest_calls": 8,
            "max_wall_clock_minutes": 120,
            "max_infrastructure_failures": 1,
            "max_validation_accesses": 0,
            "max_holdout_accesses": 0,
        },
        "stop_conditions": [
            "more_than_one_branch_changed",
            "router_extraction_semantic_drift",
            "module_identity_mismatch",
            "output_namespace_contract_violation",
            "artifact_contamination_detected",
            "shared_condition_changed_by_ablation",
            "proposal_or_campaign_fingerprint_drift",
            "formal_strategy_or_sealed_input_hash_drift",
        ],
        "execution_boundary": {
            "candidate_created": False,
            "backtest_run": False,
            "execution_authorized": False,
            "next_required_event": "human_execution_approval_naming_exactly_one_eligible_ablation_unit",
        },
    }
    return {
        "schema_version": "regime-conditioned-branch-factorization-plan-v1",
        "compilation_approval": {
            "path": BRANCH_FACTORIZATION_APPROVAL,
            "sha256": sha256_file(repo / BRANCH_FACTORIZATION_APPROVAL),
            "approval_status": approval["approval_status"],
            "execution_authorized": False,
        },
        "current_structure": {
            "source": "research/analysis/regime-aware-condition-graph.json",
            "condition_count": len(conditions),
            "signal_group_count": len(groups),
            "condition_owner_counts": owner_counts,
            "condition_ownership": ownership,
            "signal_groups": [
                {
                    "group_id": item["group_id"],
                    "regime_branch": item["branch"].split("_", 1)[0],
                    "branch": item["branch"],
                    "side": item["side"],
                    "signal": item["signal"],
                    "conditions": item["conditions"],
                }
                for item in groups
            ],
        },
        "minimum_testable_hypothesis": {
            "hypothesis_id": "router-extraction-semantic-equivalence-v1",
            "statement": "Extract the existing shared regime dispatch into one Candidate without changing any condition, threshold, Boolean expression, signal tag, exit, risk or execution setting.",
            "single_structural_variable": "location_and_interface_of_regime_dispatch_only",
            "candidate_count": 1,
            "development_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
            "backtest_invocations": 8,
            "backtest_count_formula": "2 strategies x 2 pairs x 2 fresh-process repetitions",
        },
        "ordered_research_sequence": [
            {
                "phase": "compilation_and_read_only_mapping",
                "authority": "authorized_now",
                "candidate_created": False,
                "backtest_run": False,
            },
            {
                "phase": "structure_equivalence_candidate",
                "authority": "requires_new_human_execution_approval",
                "candidate_created": True,
                "candidate_count": 1,
                "backtest_invocations": 8,
            },
            {
                "phase": "branch_contribution_ablation",
                "authority": "not_compiled_requires_separate_proposal_and_human_approval",
                "candidate_created": False,
                "backtest_run": False,
            },
        ],
        "semantic_equivalence_gate": {
            "code_refactor_only_requires": [
                "identical normalized condition inventory and expressions",
                "identical signal-frame hashes for every pair and repetition",
                "identical enter/exit tags and timestamps",
                "identical normalized trade signatures",
                "identical fees, leverage, risk, ROI, stoploss, protections and Runtime",
            ],
            "semantic_change_if_any": [
                "condition, threshold or Boolean operator changes",
                "signal-frame or trade-signature mismatch",
                "entry, exit, ROI, stoploss, leverage, protection or execution-config drift",
            ],
            "on_mismatch": "stop_as_semantic_change_do_not_start_ablation",
        },
        "single_variable_controls": [
            "exactly one Candidate and one router-extraction diff",
            "no threshold, indicator, entry, exit or risk edits",
            "freeze the 29-condition inventory and five signal groups",
            "run BTC and ETH as separate experiment packs",
            "compile each future branch ablation as a separate Campaign",
        ],
        "baseline_role": "RegimeAwareV6 remains the immutable execution baseline and comparison reference; the Candidate cannot replace or modify it.",
        "decision_rules": {
            "retain": "Retain the execution baseline if equivalence fails or no stable branch contribution is later established.",
            "split_for_study": "Only a separately approved single-branch ablation with stable BTC/ETH contribution evidence may justify studying a split family.",
            "abandon_hypothesis": "Abandon factorization if router extraction cannot preserve exact semantics or later attribution adds no information.",
            "family_retirement": "Never automatic from development results; requires a separate human family decision.",
        },
    }


def compile_campaign(
    repo: Path,
    proposal: dict[str, Any],
    state: dict[str, Any],
    constitution: dict[str, Any],
    budget_override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    source_proposal = proposal
    proposal = _decision_review_proposal(repo, proposal)
    missing = sorted(REQUIRED_PROPOSAL_FIELDS - proposal.keys())
    if missing:
        raise ValueError(f"proposal missing fields: {', '.join(missing)}")
    route = route_proposal(proposal, constitution)
    if route["decision"] == "forbidden":
        raise ValueError("forbidden proposal cannot be compiled")
    if proposal.get("recommendation") == "no_research_recommended":
        raise ValueError("no_research_recommended cannot be compiled")
    checked_evidence = verify_evidence(repo, proposal)
    structural_plan = branch_factorization_plan(repo, proposal)
    ablation_plan = branch_contribution_ablation_plan(repo, proposal)
    decision_plan = ranging_short_decision_plan(repo, source_proposal)
    routing_plan = regime_conditioned_routing_plan(repo, source_proposal)
    carry_plan = router_carry_context_plan(repo, source_proposal)
    output_rel = f"research/director/compiled/{proposal['proposal_id']}"
    estimated = int(proposal["estimated_experiments"])
    constitution_budget = constitution.get("budget_limits") or {}
    requested = budget_override or {}
    max_experiments = min(
        estimated,
        int(requested.get("max_experiments", estimated)),
        int(constitution_budget.get("max_experiments", estimated)),
    )
    max_wall = min(
        int(proposal["estimated_wall_clock_minutes"]),
        int(requested.get("max_wall_clock_minutes", proposal["estimated_wall_clock_minutes"])),
        int(constitution_budget.get("max_wall_clock_minutes", proposal["estimated_wall_clock_minutes"])),
    )
    if ablation_plan:
        max_experiments = 3
        max_wall = ablation_plan["budget"]["max_wall_clock_minutes"]
    steps = proposal.get("proposed_method", {}).get("steps") or ["perform evidence-linked read-only audit"]
    if structural_plan:
        steps = [
            "create exactly one router-extraction Candidate after new human execution approval",
            "run the BTC baseline/Candidate equivalence pack in distinct fresh processes",
            "run the ETH baseline/Candidate equivalence pack in distinct fresh processes",
        ]
    if decision_plan:
        steps = [
            "audit BTC and ETH metric direction, units and arithmetic without executing research",
            "map existing BTC evidence to Balanced Research Gate v1 and preserve ETH as descriptive only",
            "freeze Validation, temporal and retain options plus exact budgets for human review",
        ]
    if routing_plan:
        steps = [
            "freeze the four approved temporal conclusions and verified router structure",
            "build a read-only router-context evidence matrix and expose attribution gaps",
            "prepare one single-variable future approval envelope without selecting or executing a Candidate",
        ]
    if carry_plan:
        steps = [
            "freeze the approved router context and source identity",
            "freeze a Development-only context coverage gate",
            "compile a future single-Candidate approval envelope without execution",
        ]
    if ablation_plan:
        steps = [
            "record the human-selected single eligible ablation unit and freeze its reversible Candidate diff allowlist",
            "run the four BTC fresh-process Baseline/Candidate executions and validate namespace plus identity",
            "run the four ETH fresh-process Baseline/Candidate executions and produce contribution attribution",
        ]
    queue = [
        {
            "experiment_id": f"{proposal['proposal_id']}-e{index:03d}",
            "priority": index,
            "status": "queued_unexecuted",
            "runner": "future_candidate_ablation_step" if ablation_plan else ("future_candidate_equivalence_step" if structural_plan else ("dry_run_regime_conditioned_routing_review" if routing_plan else ("dry_run_router_carry_context_review" if carry_plan else "dry_run_read_only_audit"))),
            "action": step,
            "guard_paths": proposal["allowed_changes"],
            "execution_authorized": False,
            "requires_new_human_execution_approval": bool(structural_plan or ablation_plan or decision_plan or routing_plan or carry_plan),
            "fingerprint": fingerprint({"proposal": proposal["semantic_fingerprint"], "index": index, "step": step}),
        }
        for index, step in enumerate(steps[:max_experiments], start=1)
    ]
    frozen_inputs = {
        "state": {"path": "research/director/current-research-state.json", "fingerprint": state["state_fingerprint"]},
        "constitution": {"path": "research/governance/research-constitution.yaml", "sha256": sha256_file(repo / "research/governance/research-constitution.yaml"), "status": constitution.get("status")},
        "strategy": state["formal_strategy"],
        "runtime": proposal["required_runtime"],
        "policy": proposal["required_policy"],
        "datasets": proposal["required_datasets"],
        "closures": [{"path": "research/closures/regime-aware-ranging-thresholds-v1.yaml", "sha256": sha256_file(repo / "research/closures/regime-aware-ranging-thresholds-v1.yaml"), "reopen_requested": False}],
        "evidence": checked_evidence,
    }
    if structural_plan:
        frozen_inputs["compilation_approval"] = structural_plan["compilation_approval"]
    if ablation_plan:
        frozen_inputs["compilation_approval"] = ablation_plan["compilation_approval"]
        frozen_inputs["router_equivalence_baseline"] = ablation_plan["verified_baseline"]
        frozen_inputs["structure_map"] = ablation_plan["structure_source"]
    if decision_plan:
        frozen_inputs["compilation_approval"] = decision_plan["compilation_approval"]
        frozen_inputs["frozen_candidate"] = decision_plan["frozen_candidate"]
        frozen_inputs["ablation_result"] = {"path": "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json", "sha256": sha256_file(repo / "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json"), "classification": "branch_negative_contributor", "evidence_scope": "development_only"}
    if routing_plan:
        frozen_inputs["routing_review_evidence"] = routing_plan["evidence_sources"]
        frozen_inputs["compilation_approval"] = routing_plan["compilation_approval"]
    if carry_plan:
        frozen_inputs["router_context_contract"] = {
            "context_id": carry_plan["context_contract"]["context_id"],
            "fingerprint": carry_plan["context_contract_fingerprint"],
            "source_sha256": carry_plan["context_contract"]["source_sha256"],
        }
        frozen_inputs["compilation_approval"] = carry_plan["compilation_approval"]
        frozen_inputs["temporal_slice_policy"] = {
            "fingerprint": carry_plan["slice_policy_fingerprint"],
            "slice_order": carry_plan["slice_order"],
        }
    campaign: dict[str, Any] = {
        "schema_version": "compiled-research-campaign-v1",
        "campaign_id": f"stage4a-{proposal['proposal_id']}",
        "proposal_id": proposal["proposal_id"],
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "compile_mode": "dry_run",
        "mode": "dry_run",
        "runner_type": "frozen_regime_conditioned_routing_review_plan" if routing_plan else ("frozen_router_carry_context_review_plan" if carry_plan else ("frozen_branch_decision_review_plan" if decision_plan else ("frozen_single_branch_ablation_plan" if ablation_plan else ("frozen_candidate_equivalence_plan" if structural_plan else "dry_run_read_only_audit")))),
        "execution_authorized": False,
        "approval_route": route["decision"],
        "approval_granted": False,
        "risk_class": proposal["risk_class"],
        "current_authority": "compile_and_review_only" if (structural_plan or ablation_plan or decision_plan or routing_plan or carry_plan) else "dry_run_only",
        "scope": {
            "allowed_paths": sorted(set(proposal["allowed_changes"] + [f"{output_rel}/**", "research/registry/**"])),
            "blocked_paths": [".env", "secrets/**", "deploy/**", "strategies/**", "user_data/**", "configs/**", "scripts/start_bot.sh", "scripts/refresh_data.sh", "research/data/holdout/**", "research/data/snapshots/futures-validation-*/data/**", "research/evaluation/evaluation-policy.yaml", "research/closures/**"],
        },
        "frozen_inputs": frozen_inputs,
        "budget": {
            "max_campaigns": 1,
            "max_experiments": max_experiments,
            "max_total_attempts": max_experiments,
            "max_consecutive_failures": min(1, int(constitution_budget.get("max_infrastructure_failures", 1))),
            "max_retries_per_experiment": 0,
            "max_wall_clock_minutes": max_wall,
            "max_validation_accesses": 0,
            "max_infrastructure_failures": int(constitution_budget.get("max_infrastructure_failures", 3)),
        },
        "autonomy": {
            "automatically_claim_next": True,
            "automatically_generate_hypotheses": False,
            "automatically_promote_champion": False,
            "access_sealed_holdout": False,
            "lease_seconds": 300,
        },
        "experiment_queue": queue,
        "stop_conditions": proposal["stop_conditions"],
        "escalation_conditions": ["blocked_path", "secret_access", "validation_or_holdout_access", "strategy_or_risk_change", "closure_conflict", "budget_exhausted", "human_stop"],
        "state_machine": {"campaign": ["draft", "human_review", "approved", "active", "completed", "stopped", "failed", "escalated"], "experiment": ["queued", "claimed", "preparing", "running", "validating", "recorded", "accepted", "rejected", "failed", "escalated"]},
        "failure_taxonomy": {
            "infra_transient": {"retryable": True, "consumes_attempt": True},
            "infra_permanent": {"retryable": False, "consumes_attempt": True},
            "implementation_error": {"retryable": False, "consumes_attempt": True},
            "validation_error": {"retryable": False, "consumes_attempt": True},
            "guard_violation": {"retryable": False, "consumes_attempt": True, "escalate": True},
            "budget_stop": {"retryable": False, "consumes_attempt": False},
        },
        "retry_policy": {"max_retries_per_experiment": 0, "fresh_process_required": True, "guard_violation_retryable": False},
        "artifact_requirements": proposal["required_artifacts"],
        "registry_events": ["campaign_compiled", "human_approval_recorded", "experiment_claimed", "artifact_recorded", "campaign_completed_or_stopped"],
        "test_requirements": proposal["required_tests"] + ["readiness", "baseline_verifier", "artifact_integrity", "registry_integrity"],
        "acceptance_criteria": proposal["success_criteria"] + ["no Campaign executed during Stage 4A", "no Candidate created", "no Validation/Holdout access"],
        "human_escalation_conditions": ["any scope expansion", "new dataset acquisition", "medium_or_high_risk_change", "Validation/Holdout request", "closure reopen request", "Constitution amendment"],
        "git_completion_requirements": ["targeted tests pass", "readiness pass", "baseline verifier pass", "logical commit", "clean versioned worktree"],
        "compiled_at": utc_now(),
    }
    if structural_plan:
        campaign["structural_research_plan"] = structural_plan
        campaign["budget"]["max_candidates"] = 1
        campaign["budget"]["planned_backtest_invocations"] = 8
        campaign["compilation_artifact_requirements"] = [
            "current-structure-map.json",
            "current-structure-map.md",
            "implementation-brief.md",
            "human-decision-packet.json",
        ]
        campaign["future_execution_artifact_requirements"] = list(campaign["artifact_requirements"])
        campaign["acceptance_criteria"] += [
            "formal RegimeAwareV6 remains the immutable execution baseline",
            "exact semantic equivalence is proven before any ablation is proposed",
            "branch contribution ablation is not part of this compiled Campaign",
            "a new human execution approval is recorded before Candidate creation or Backtest",
        ]
        campaign["human_escalation_conditions"] += [
            "semantic equivalence mismatch",
            "more than one Candidate or structural variable",
            "branch contribution ablation request",
        ]
    if ablation_plan:
        campaign["branch_contribution_ablation_plan"] = ablation_plan
        campaign["budget"].update(ablation_plan["budget"])
        campaign["budget"]["max_experiments"] = 3
        campaign["budget"]["max_total_attempts"] = 3
        campaign["compilation_artifact_requirements"] = [
            "ablation-unit-map.json",
            "ablation-unit-map.md",
            "implementation-brief.md",
            "human-decision-packet.json",
        ]
        campaign["future_execution_artifact_requirements"] = list(campaign["artifact_requirements"])
        campaign["acceptance_criteria"] += [
            "exactly one human-selected signal group is reversibly isolated",
            "formal RegimeAwareV6 remains the execution baseline",
            "router-equivalent source remains the structural reference",
            "contribution is classified by the frozen deterministic taxonomy",
            "Balanced Research Gate is descriptive context only and cannot promote",
        ]
        campaign["human_escalation_conditions"] += [
            "exact ablation unit has not been selected by a human",
            "more than one branch, regime, side, signal type or shared condition changes",
            "temporal slice backtests requested beyond the frozen eight-call budget",
            "Candidate path or reversible ablation mechanism not explicitly approved",
        ]
    if decision_plan:
        campaign["ranging_short_branch_decision_review_plan"] = decision_plan
        campaign["budget"].update({"max_experiments": 3, "max_total_attempts": 3, "max_backtest_calls": 0, "max_candidates": 0, "max_validation_accesses": 0, "max_holdout_accesses": 0})
        campaign["compilation_artifact_requirements"] = ["metric-semantics-audit.json", "decision-options.json", "implementation-brief.md", "human-decision-packet.json", "decision-review.md"]
        campaign["future_execution_artifact_requirements"] = ["new-human-approval.json", "frozen-scope-execution-authorization.json"]
        campaign["acceptance_criteria"] += ["formal ranging_short_entry remains present", "existing Candidate is frozen and reused", "no Backtest, Validation, Holdout or temporal slice is executed", "recommendation does not remove or promote strategy code"]
        campaign["human_escalation_conditions"] += ["any request to access BTC Validation", "any temporal boundary selection", "any Candidate or formal strategy change", "any attempt to treat ETH as formal policy evidence"]
    if routing_plan:
        campaign["regime_conditioned_routing_plan"] = routing_plan
        campaign["budget"].update(routing_plan["current_execution_budget"])
        campaign["budget"].update({"max_experiments": 3, "max_total_attempts": 3})
        campaign["compilation_artifact_requirements"] = [
            "routing-evidence-matrix.json",
            "implementation-brief.md",
            "human-decision-packet.json",
            "regime-conditioned-ranging-short-routing-v1-decision-report.md",
            "regime-conditioned-ranging-short-routing-v1-decision-report.html",
        ]
        campaign["future_execution_artifact_requirements"] = [
            "new-medium-risk-proposal.json",
            "new-compiled-campaign.yaml",
            "new-human-execution-approval.json",
        ]
        campaign["acceptance_criteria"] += [
            "formal ranging_short_entry remains retained and unchanged",
            "temporal slices are not treated as regime labels",
            "no Candidate or Backtest is created or executed",
            "no Validation/Holdout access occurs",
            "whole-branch deletion and threshold research remain closed",
        ]
        campaign["human_escalation_conditions"] += [
            "exact router context is not predeclared from existing evidence",
            "any request to create a Candidate or run a Backtest",
            "any request to reopen whole-branch deletion or threshold research",
            "any request to access Validation or Holdout",
        ]
    if carry_plan:
        campaign["router_carry_context_plan"] = carry_plan
        campaign["budget"].update(carry_plan["current_execution_budget"])
        campaign["budget"].update({"max_experiments": 3, "max_total_attempts": 3})
        campaign["compilation_artifact_requirements"] = [
            "router-context-evidence-matrix.json",
            "implementation-brief.md",
            "human-decision-packet.json",
            "ranging-short-router-carry-context-review-v1-decision-report.md",
            "ranging-short-router-carry-context-review-v1-decision-report.html",
        ]
        campaign["future_execution_artifact_requirements"] = [
            "new-human-execution-approval.json",
            "frozen-candidate-manifest.json",
            "context-coverage-preflight.json",
        ]
        campaign["acceptance_criteria"] += [
            "the approved router context is the only future structural variable",
            "formal ranging_short_entry remains retained and unchanged",
            "current Candidate and Backtest counts remain zero",
            "no Validation/Holdout access occurs",
            "time slices are not used as regime labels",
        ]
        campaign["human_escalation_conditions"] += [
            "router context contract or source identity drift",
            "context coverage is insufficient before Backtest",
            "any request to create a Candidate or run a Backtest",
            "any request to change thresholds, router output or formal strategy",
            "any request to access Validation or Holdout",
        ]
    campaign["campaign_fingerprint"] = fingerprint({key: value for key, value in campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}})
    metadata = {
        "schema_version": "campaign-compilation-metadata-v1",
        "proposal_id": proposal["proposal_id"],
        "campaign_id": campaign["campaign_id"],
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "compile_mode": "dry_run",
        "execution_authorized": False,
        "approval_route": route,
        "referenced_hashes": frozen_inputs,
        "existing_control_plane_validator": "scripts/research_control.py:load_campaign",
        "campaign_executed": False,
        "candidate_created": False,
    }
    brief = implementation_brief(campaign, proposal)
    return campaign, metadata, brief


def implementation_brief(campaign: dict[str, Any], proposal: dict[str, Any]) -> str:
    display_title = proposal.get("title", proposal["proposal_id"])
    queue = "\n".join(f"{index}. `{item['action']}`" for index, item in enumerate(campaign["experiment_queue"], start=1))
    carry = campaign.get("router_carry_context_plan")
    if carry:
        future = carry["future_separate_approval_envelope"]
        return f"""# 实施简报：{display_title}

Campaign：`{campaign['campaign_id']}`
Fingerprint：`{campaign['campaign_fingerprint']}`
编译模式：`dry_run`
执行授权：`false`

## 唯一 Router Context

`{carry['context_contract']['context_id']}`

该 context 固定为 router 输出 `ranging`，但当前 ADX、BB width 与 ATR 原始投票不直接形成 ranging signal。时间切片不作为 market regime 标签。

## 当前不执行

{queue}

当前预算为 `0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`。正式 `ranging_short_entry`、`RegimeDetector`、router、阈值和执行配置均保持不变。

## 未来独立人工审批上限

最多 `1 Candidate / {future['max_backtest_calls']} Development-only Backtests / 0 Validation / 0 Holdout`，复用四个冻结切片且不增加第五个切片。执行前必须先通过 context coverage gate。
"""
    routing = campaign.get("regime_conditioned_routing_plan")
    if routing:
        slices = "\n".join(
            f"- `{slice_id}`：`{classification}`"
            for slice_id, classification in routing["slice_conclusions"].items()
        )
        future = routing["future_separate_approval_envelope"]
        return f"""# 实施简报：{display_title}

Campaign：`{campaign['campaign_id']}`
Fingerprint：`{campaign['campaign_fingerprint']}`
编译模式：`dry_run`
执行授权：`false`

## 当前证据

{slices}

正式 `ranging_short_entry` 保持不变。Router extraction 的语义等价性已经验证，但现有四个时间切片只能证明贡献方向随时间变化，不能把时间切片直接解释为市场 regime。

## 当前只读范围

{queue}

当前预算为 `0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`。本次只冻结证据矩阵、缺口和人工决策边界，不执行编译后的 Campaign。

## 编译建议

`{routing['preparation_recommendation']}`

现有证据不足以预先声明一个可验证的 router context。若未来获得精确、事先声明且不依赖结果选择的 context，必须另建 medium-risk Proposal，并重新冻结 Proposal/Campaign fingerprint。

未来单独审批预算上限为 `1 Candidate / {future['max_backtest_calls']} Development-only Backtests / 0 Validation / 0 Holdout`；不得增加时间切片，不得修改阈值、entry/exit、风险或正式策略。

## 仍需人工批准

- 精确且可由运行代码观测的单一 router context；
- 新 Proposal 与 Compiled Campaign fingerprint；
- 唯一 Candidate 的路径、类名、源码 hash 和 diff allowlist；
- `{future['max_backtest_calls']}` 次 Development-only Backtest 的独立执行授权。

在这些事项获批前，系统应保持 `retain_branch_no_routing_change`。
"""
    decision = campaign.get("ranging_short_branch_decision_review_plan")
    if decision:
        temporal = decision["options"]["B_temporal"]["budget"]
        validation = decision["options"]["A_validation"]["budget"]
        return f"""# Implementation Brief: {display_title}

Campaign: `{campaign['campaign_id']}`
Fingerprint: `{campaign['campaign_fingerprint']}`
Compile mode: `dry_run`
Execution authorized: `false`

## Metric semantics

All recorded deltas use `Candidate - Baseline`. Profit and fee/funding values are absolute USDT; `total_profit_pct` is stored as a ratio and is converted to percentage points by multiplying by 100. Profit Factor is dimensionless. `max_drawdown` in this artifact is absolute USDT, not a percentage or percentage-point value; lower is better.

ETH max drawdown is `291.71629049 - 340.65008476 = -48.93379427 USDT`, meaning the Candidate reduced absolute drawdown by 48.93379427 USDT.

## Policy and evidence boundary

- BTC Development is inside Balanced Research Gate v1 scope, but the ablation did not produce the complete policy gate evidence set.
- ETH Development is descriptive cross-pair evidence only.
- Validation, Holdout, temporal ablation slices and Forward Dry-run were not run.
- The current finding is branch contribution evidence, not `development_eligible`.

## Recommendation

`{decision['recommendation']}`

- Option A Validation: `{validation['backtest_calls']}` calls, `{validation['validation_accesses']}` Validation access, `{validation['max_wall_clock_minutes']}` minutes.
- Option B Temporal: `{temporal['backtest_calls']}` calls (`{temporal['formula']}`), `0` Validation/Holdout, `{temporal['max_wall_clock_minutes']}` minutes.
- Option C Retain: `0` calls.

The existing Candidate is reused and frozen at `{decision['frozen_candidate']['source_sha256']}`. No result in this compilation is sufficient to delete `ranging_short_entry` from the formal strategy.

## Human approval still required

- Select exactly one option.
- For temporal review, approve four exact slice boundaries, 16 Development-only calls and 240 minutes.
- For Validation review, approve one limited BTC Validation disclosure and two frozen Baseline/Candidate calls.
- Any strategy/Candidate modification, Holdout, Hyperopt or automatic follow-up remains forbidden.

No Campaign step is executed by this compilation.
"""
    ablation = campaign.get("branch_contribution_ablation_plan")
    if ablation:
        units = "\n".join(
            f"- `{item['unit_id']}`: {item['regime']} / {item['side']} / {item['signal']} "
            f"(eligible: `{str(item['eligible_as_single_candidate_unit']).lower()}`)"
            for item in ablation["ablation_units"]
        )
        metrics = "\n".join(f"- `{item}`" for item in ablation["contribution_metrics"])
        decisions = "\n".join(f"- `{item}`" for item in ablation["decision_classifications"])
        return f"""# Implementation Brief: {display_title}

Campaign: `{campaign['campaign_id']}`
Fingerprint: `{campaign['campaign_fingerprint']}`
Compile mode: `dry_run`
Execution authorized: `false`

## Verified baseline

`RegimeAwareV6` remains the formal execution baseline. `RegimeAwareRouterEquivalentV1` is only the verified structural reference. BTC and ETH each have 27 exact-equivalence trades in the frozen router recertification.

## Real ablation units

{units}

Only one eligible signal group may be selected in a future human execution approval. The shared router is mapped but is not eligible in this Campaign.

## Reversible single-variable mechanism

Preserve the original branch code, conditions, tags and source locations. A future isolated Candidate may gate exactly one final signal group and must record the selected unit, mechanism, preserved source hash and exact diff allowlist. Large deletion is forbidden.

## Frozen future execution design

- Candidate count: `1`
- Backtest calls: `8` (`2 roles x 2 pairs x 2 fresh-process repetitions`)
- Pairs: BTC and ETH Development only
- Initial temporal slice Backtests: `0`; rolling-window attribution uses the same approved runs
- Validation/Holdout: `0 / 0`
- Balanced Research Gate: descriptive context only, never a promotion gate

Planned queue (not executable under current authority):

{queue}

## Contribution metrics

{metrics}

## Deterministic classifications

{decisions}

## Human approval still required

- Name exactly one eligible `unit_id`.
- Approve one Candidate class/path, reversible gating mechanism and exact diff allowlist.
- Approve the eight development-only Backtest calls and 120-minute budget.
- Confirm no temporal-slice expansion, Validation, Holdout, threshold, exit, router, risk or execution change.

No Candidate, Backtest or ablation is created by this compilation.
"""
    structural = campaign.get("structural_research_plan")
    if structural:
        hypothesis = structural["minimum_testable_hypothesis"]
        return f"""# Implementation Brief: {display_title}

Campaign: `{campaign['campaign_id']}`
Fingerprint: `{campaign['campaign_fingerprint']}`
Compile mode: `dry_run`
Execution authorized: `false`

## Minimum research unit

`{hypothesis['hypothesis_id']}` changes only `{hypothesis['single_structural_variable']}`. The future execution scope is exactly one Candidate and {hypothesis['backtest_invocations']} Backtest invocations ({hypothesis['backtest_count_formula']}).

## Frozen order

1. Current authorized work is read-only mapping, compilation and human review only.
2. A new human execution approval is required before creating the one equivalence Candidate.
3. Prove exact BTC and ETH semantic equivalence in fresh processes.
4. Stop on any mismatch. Branch contribution ablation is not compiled here and requires a separate Proposal and approval.

## Planned queue (not authorized)

{queue}

## Equivalence boundary

Code movement is a refactor only when the normalized 29-condition inventory, five signal groups, signal-frame hashes, tags, timestamps, trade signatures and all risk/execution settings are identical. Any mismatch is a real semantic change and stops the Campaign.

## Baseline and single-variable control

`RegimeAwareV6` remains the immutable execution baseline. No condition, threshold, entry, exit, ROI, stoploss, leverage, protection or execution configuration may change. Each future ablation must be a separate Campaign and Candidate.

## Human approval still required

- Candidate class/path and exact diff allowlist.
- Eight Backtest invocations on the two frozen development pairs.
- Runtime and wall-clock budget for execution.
- Any later single-branch contribution ablation.

## Definition of done for this compilation

- Campaign Spec, structure map and decision packet agree on counts and boundaries.
- Targeted tests, readiness, baseline and Registry integrity pass.
- No Candidate, Backtest, Validation or Holdout access occurs.
- Commit logically and leave the version-controlled worktree clean.
"""
    return f"""# Implementation Brief: {display_title}

Campaign: `{campaign['campaign_id']}`
Fingerprint: `{campaign['campaign_fingerprint']}`
Compile mode: `dry_run`
Execution authorized: `false`

## Objective

{proposal['research_question']}

## Machine authority

Use `campaign.yaml`, its frozen input hashes, the approved Evaluation Policy, and the approved Research Constitution as the facts. This brief is explanatory only.

## Queue

{queue}

## Required boundaries

- Do not run this Campaign until human approval is recorded.
- Do not create a Candidate or modify strategy/risk semantics.
- Do not access Validation, Holdout, live/server/deploy, private API, or secrets.
- Stop on any scope expansion, missing hash, closure conflict, or budget breach.

## Definition of done

- Emit every required artifact and Registry event.
- Pass targeted tests, readiness, baseline verification and integrity checks.
- Commit logically and leave the version-controlled worktree clean.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--state", default="research/director/current-research-state.json")
    parser.add_argument("--constitution", default="research/governance/research-constitution.yaml")
    parser.add_argument("--budget")
    parser.add_argument("--output-dir")
    parser.add_argument("--director-registry")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    proposal = load_document(args.proposal)
    state = load_document(args.state)
    constitution = load_document(args.constitution)
    budget = json.loads(args.budget) if args.budget else None
    campaign, metadata, brief = compile_campaign(repo, proposal, state, constitution, budget)
    output = Path(args.output_dir or f"research/director/compiled/{proposal['proposal_id']}")
    output.mkdir(parents=True, exist_ok=True)
    campaign_path = output / "campaign.yaml"
    write_yaml(campaign_path, campaign)
    write_json(output / "experiment-queue.json", campaign["experiment_queue"])
    write_json(output / "compilation-metadata.json", metadata)
    (output / "implementation-brief.md").write_text(brief, encoding="utf-8")
    ablation = campaign.get("branch_contribution_ablation_plan")
    if ablation:
        write_json(
            output / "ablation-unit-map.json",
            {
                "schema_version": "branch-contribution-ablation-unit-map-v1",
                "structure_source": ablation["structure_source"],
                "units": ablation["ablation_units"],
                "selected_unit": None,
                "selection_status": "pending_human_execution_approval",
            },
        )
        unit_lines = [
            "# Branch Contribution Ablation Unit Map",
            "",
            "The units below are derived from the committed 29-condition / 5-signal-group structure map.",
            "",
        ]
        unit_lines.extend(
            f"- `{item['unit_id']}`: `{item['regime']}` / `{item['side']}` / `{item['signal']}`; eligible `{str(item['eligible_as_single_candidate_unit']).lower()}`"
            for item in ablation["ablation_units"]
        )
        (output / "ablation-unit-map.md").write_text("\n".join(unit_lines) + "\n", encoding="utf-8")
        write_json(
            output / "human-decision-packet.json",
            {
                "schema_version": "branch-contribution-ablation-human-decision-packet-v1",
                "proposal_id": proposal["proposal_id"],
                "proposal_fingerprint": proposal["semantic_fingerprint"],
                "campaign_fingerprint": campaign["campaign_fingerprint"],
                "risk_class": proposal["risk_class"],
                "approval_status": "pending_human_execution_approval",
                "execution_authorized": False,
                "required_human_decisions": [
                    "select exactly one eligible ablation unit",
                    "approve one Candidate class and exact path",
                    "approve the reversible gating mechanism and exact diff allowlist",
                    "approve eight BTC/ETH development-only Backtest calls",
                ],
                "budget": ablation["budget"],
                "forbidden": proposal["forbidden_changes"],
                "decision_classifications": ablation["decision_classifications"],
                "candidate_created": False,
                "backtest_run": False,
                "validation_accesses": 0,
                "holdout_accesses": 0,
            },
        )
    decision = campaign.get("ranging_short_branch_decision_review_plan")
    if decision:
        write_json(output / "metric-semantics-audit.json", decision["metric_semantics_audit"])
        write_json(output / "decision-options.json", {"recommendation": decision["recommendation"], "options": decision["options"], "insufficient_to_remove_formal_branch": decision["insufficient_to_remove_formal_branch"]})
        packet = {
            "schema_version": "ranging-short-branch-human-decision-packet-v1",
            "proposal_id": proposal["proposal_id"], "proposal_fingerprint": proposal["semantic_fingerprint"],
            "campaign_fingerprint": campaign["campaign_fingerprint"], "risk_class": proposal["risk_class"],
            "approval_status": "pending_human_execution_review", "execution_authorized": False,
            "metric_semantics_status": decision["metric_semantics_audit"]["status"],
            "development_gate_audit": decision["development_gate_audit"], "evidence_scope": decision["evidence_scope"],
            "frozen_candidate": decision["frozen_candidate"], "options": decision["options"],
            "recommendation": decision["recommendation"],
            "insufficient_to_remove_formal_branch": decision["insufficient_to_remove_formal_branch"],
            "required_human_decisions": ["select Option A, B or C", "approve exact future data access and Backtest budget", "confirm no strategy or Candidate modification"],
            "campaign_executed": False, "candidate_created": False, "backtest_run": False, "validation_accesses": 0, "holdout_accesses": 0,
        }
        write_json(output / "human-decision-packet.json", packet)
        (output / "decision-review.md").write_text(implementation_brief(campaign, proposal), encoding="utf-8")
    load_campaign(campaign_path)
    if args.director_registry:
        connection = open_director_registry(args.director_registry)
        compilation_id = f"compile-{campaign['campaign_fingerprint'][:16]}"
        connection.execute(
            "INSERT OR REPLACE INTO compiled_campaigns(compilation_id, proposal_id, campaign_id, campaign_fingerprint, compile_mode, execution_authorized, referenced_hashes_json, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (compilation_id, proposal["proposal_id"], campaign["campaign_id"], campaign["campaign_fingerprint"], "dry_run", 0, json.dumps(metadata["referenced_hashes"], sort_keys=True), json.dumps(campaign, sort_keys=True), utc_now()),
        )
        connection.commit()
        connection.close()
    print(json.dumps({"campaign_id": campaign["campaign_id"], "campaign_fingerprint": campaign["campaign_fingerprint"], "output_dir": output.as_posix(), "validated_by_existing_control_plane": True, "executed": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
