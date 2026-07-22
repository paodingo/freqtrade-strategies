#!/usr/bin/env python3
"""Build a complete evidence-linked Research Director state without chat context."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

from research_director_common import (
    discovery_registry_summary,
    fingerprint,
    load_document,
    open_director_registry,
    registry_summary,
    sha256_file,
    utc_now,
    write_json,
)
from open_source_knowledge import knowledge_state_summary


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True, encoding="utf-8").strip()


def previous_committed_state(repo: Path) -> dict[str, Any]:
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:research/director/current-research-state.json"],
            cwd=repo,
            text=True,
            encoding="utf-8",
        )
        return json.loads(raw)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def evidence(path: str, claim: str, repo: Path) -> dict[str, Any]:
    target = repo / path
    return {
        "path": path,
        "claim": claim,
        "exists": target.exists(),
        "sha256": sha256_file(target) if target.is_file() else None,
    }


def campaign_definitions(repo: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted((repo / "research/campaigns/active").glob("*.yaml")):
        config = load_document(path)
        result.append({
            "campaign_id": config.get("campaign_id"),
            "mode": config.get("mode"),
            "runner_type": config.get("runner_type", config.get("mode")),
            "definition_path": path.relative_to(repo).as_posix(),
            "definition_sha256": sha256_file(path),
            "automatic_hypothesis_generation": (config.get("autonomy") or {}).get("automatically_generate_hypotheses"),
            "automatic_champion_promotion": (config.get("autonomy") or {}).get("automatically_promote_champion"),
        })
    return result


def dataset_manifests(repo: Path) -> list[dict[str, Any]]:
    paths = sorted((repo / "research/data/snapshots").glob("*/manifest.yaml"))
    paths += sorted((repo / "research/temporal/snapshots").glob("*/manifest.yaml"))
    result = []
    for path in paths:
        payload = load_document(path)
        result.append({
            "dataset_id": payload.get("dataset_id"),
            "path": path.relative_to(repo).as_posix(),
            "manifest_sha256": sha256_file(path),
            "aggregate_sha256": payload.get("aggregate_sha256"),
            "pairs": payload.get("pairs", []),
            "timeframes": payload.get("timeframes", []),
            "intended_use": payload.get("intended_use"),
            "sealed": payload.get("sealed"),
            "agent_visibility": payload.get("agent_visibility"),
            "file_count": len(payload.get("files") or []),
        })
    return result


def build_state(repo: Path, source_registry: Path | None = None, data_lineage: Path | None = None, director_registry: Path | None = None) -> dict[str, Any]:
    strategy_path = repo / "strategies/RegimeAwareV6.py"
    policy_path = repo / "research/evaluation/evaluation-policy.yaml"
    closure_path = repo / "research/closures/regime-aware-ranging-thresholds-v1.yaml"
    temporal_path = repo / "research/temporal/stage3e1-temporal-comparison.json"
    attribution_path = repo / "research/analysis/stage3d3a-final-report.json"
    invalidation_path = repo / "research/recertification/stage3d3b/stage3d2b-invalidation-event.json"
    recertification_path = repo / "research/results/stage3d3b-candidate-process-isolation-recertification/stage3d3b-final-report.json"
    stage4b1_decision_path = repo / "research/director/compiled/cross-pair-data-readiness-audit-v1/execution/readiness-decision.json"
    exit_logic_decision_path = repo / "research/director/compiled/exit-logic-structure-audit-v1/execution/audit-decision.json"
    regime_branch_decision_path = repo / "research/director/compiled/regime-branch-structure-audit-v1/execution/audit-decision.json"
    eth_generalization_path = repo / "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json"
    strategy_family_path = repo / "research/director/compiled/strategy-family-reassessment-v1/execution/campaign-execution.json"
    router_equivalence_path = repo / "research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-semantic-equivalence-result.json"
    ablation_proposal_path = repo / "research/director/next-after-router-equivalence/proposals/branch-contribution-ablation-v1.json"
    ablation_result_path = repo / "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json"
    decision_proposal_path = repo / "research/director/next-after-branch-ablation/proposals/ranging-short-branch-decision-review-v1.json"
    temporal_review_result_path = repo / "research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json"
    retention_proposal_path = repo / "research/director/next-after-ranging-short-temporal/proposals/ranging-short-branch-retention-review-v1.json"
    retention_closure_path = repo / "research/closures/ranging-short-branch-retention-review-v1.json"
    bnb_xrp_scope_approval_path = repo / "research/governance/approvals/bnb-xrp-development-descriptive-research-scope-v1-approval.json"
    chan_reversal_report_path = repo / "reports/audits/chan-structure-reversal-v1/final-report.json"
    pair_inventory_path = repo / "research/analysis/discovery-additional-pair-manifest-inventory-v1-v2/analysis.json"
    distribution_profile_path = repo / "research/analysis/discovery-bnb-xrp-distribution-shift-profile-v1-v1/analysis.json"
    timeframe_coherence_path = repo / "research/analysis/discovery-bnb-xrp-timeframe-coherence-v1-v1/analysis.json"
    funding_mark_profile_path = repo / "research/analysis/discovery-bnb-xrp-funding-mark-stress-v1-v1/analysis.json"

    policy = load_document(policy_path)
    closure = load_document(closure_path)
    temporal = load_document(temporal_path)
    attribution = load_document(attribution_path)
    invalidation = load_document(invalidation_path)
    recertification = load_document(recertification_path) if recertification_path.exists() else {}
    stage4b1_decision = load_document(stage4b1_decision_path) if stage4b1_decision_path.exists() else {}
    exit_logic_decision = load_document(exit_logic_decision_path) if exit_logic_decision_path.exists() else {}
    regime_branch_decision = load_document(regime_branch_decision_path) if regime_branch_decision_path.exists() else {}
    eth_generalization = load_document(eth_generalization_path) if eth_generalization_path.exists() else {}
    strategy_family = load_document(strategy_family_path) if strategy_family_path.exists() else {}
    router_equivalence = load_document(router_equivalence_path) if router_equivalence_path.exists() else {}
    ablation_proposal = load_document(ablation_proposal_path) if ablation_proposal_path.exists() else {}
    ablation_result = load_document(ablation_result_path) if ablation_result_path.exists() else {}
    decision_proposal = load_document(decision_proposal_path) if decision_proposal_path.exists() else {}
    temporal_review_result = load_document(temporal_review_result_path) if temporal_review_result_path.exists() else {}
    retention_proposal = load_document(retention_proposal_path) if retention_proposal_path.exists() else {}
    retention_closure = load_document(retention_closure_path) if retention_closure_path.exists() else {}
    chan_reversal_report = load_document(chan_reversal_report_path) if chan_reversal_report_path.exists() else {}
    pair_inventory = load_document(pair_inventory_path) if pair_inventory_path.exists() else {}
    distribution_profile = load_document(distribution_profile_path) if distribution_profile_path.exists() else {}
    timeframe_coherence = load_document(timeframe_coherence_path) if timeframe_coherence_path.exists() else {}
    funding_mark_profile = load_document(funding_mark_profile_path) if funding_mark_profile_path.exists() else {}
    bnb_xrp_scope_approval = load_document(bnb_xrp_scope_approval_path)
    if (
        bnb_xrp_scope_approval.get("approval_status") != "approved"
        or (bnb_xrp_scope_approval.get("scope") or {}).get("pairs")
        != ["BNB/USDT:USDT", "XRP/USDT:USDT"]
    ):
        raise ValueError("BNB/XRP descriptive research scope approval is invalid")
    previous_state = previous_committed_state(repo)
    registry = registry_summary(source_registry)
    if not registry.get("available") and (previous_state.get("registry") or {}).get("available"):
        registry = previous_state["registry"]
    campaigns = campaign_definitions(repo)
    datasets = dataset_manifests(repo)

    closure_conflicts: list[dict[str, Any]] = []
    registry_closure = next(
        (item for item in registry.get("closures", []) if item.get("closure_id") == closure.get("closure_id")),
        None,
    )
    if registry_closure:
        comparisons = {
            "research_status": (closure.get("research_status"), registry_closure.get("research_status")),
            "mechanism_decision": (closure.get("mechanism_decision"), registry_closure.get("mechanism_decision")),
            "engineering_validity": (closure.get("engineering_validity"), registry_closure.get("engineering_validity")),
        }
        mismatches = {key: values for key, values in comparisons.items() if values[0] != values[1]}
        if mismatches:
            closure_conflicts.append({
                "conflict_type": "closure_registry_mismatch",
                "status": "state_conflict",
                "sources": ["research/closures/regime-aware-ranging-thresholds-v1.yaml", "Research Registry:stage3d4b_branch_closure_events"],
                "mismatches": mismatches,
            })

    git_status = git(repo, "status", "--porcelain=v2", "--branch", "--untracked-files=all").splitlines()
    versioned_changes = [line for line in git_status if not line.startswith("#")]
    runtime_paths = [
        "research/runtime/freqtrade-runtime.yaml",
        "research/runtime/offline-adapter-contract.yaml",
        "research/runtime/freqtrade-2025-8-signal-execution-contract.yaml",
        "research/runtime/requirements-freqtrade.lock.txt",
        "research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml",
    ]
    runtime_contracts = [evidence(path, "Immutable runtime or sealed execution input", repo) for path in runtime_paths]

    completed_stages = [
        {"stage": "Stage 3A", "status": "completed", "evidence": ["reports/audits/stage3a5_futures_online_offline_adapter_certification.md", "research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml"]},
        {"stage": "Stage 3B", "status": "completed", "evidence": ["reports/audits/stage3b1_candidate_identity_equivalence.md", "reports/audits/stage3b2_single_variable_semantic_mutation.md"]},
        {"stage": "Stage 3C", "status": "completed", "evidence": ["research/evaluation/evaluation-policy.yaml", "reports/audits/stage3c3_balanced_research_gate.md"]},
        {"stage": "Stage 3D", "status": "completed", "evidence": ["research/closures/regime-aware-ranging-thresholds-v1.yaml", "research/analysis/stage3d3a-final-report.json"]},
        {"stage": "Stage 3E.1", "status": "completed", "evidence": ["research/temporal/stage3e1-temporal-comparison.json", "reports/audits/stage3e1_temporal_data_coverage_audit.md"]},
    ]
    if stage4b1_decision.get("campaign_audit_completed") is True:
        completed_stages.append({"stage": "Stage 4B.1", "status": "completed", "evidence": ["research/director/compiled/cross-pair-data-readiness-audit-v1/execution/readiness-decision.json", "reports/audits/cross-pair-data-readiness/stage4b1-cross-pair-data-readiness-final-report.json"]})
    if exit_logic_decision.get("campaign_executed") is True:
        completed_stages.append({"stage": "Exit Logic Structure Campaign", "status": "completed", "evidence": ["research/analysis/exit-logic-audit/exit-attribution.json", "reports/audits/exit-logic-audit/exit-logic-structure-final-report.json"]})
    if regime_branch_decision.get("campaign_executed") is True:
        completed_stages.append({"stage": "Stage 4C.1 Cycle 1", "status": "completed", "evidence": ["research/analysis/regime-branch-audit/regime-branch-structure.json", "reports/audits/stage4c1/cycle-1-regime-branch-final-report.json"]})
    if eth_generalization.get("campaign_completed") is True:
        completed_stages.append({"stage": "ETH Cross-pair Generalization Campaign", "status": "completed", "evidence": ["research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "reports/audits/eth-cross-pair-generalization/eth-cross-pair-generalization-final-report.json"]})
    if strategy_family.get("status") == "completed":
        completed_stages.append({"stage": "Strategy Family Reassessment Campaign", "status": "completed", "evidence": ["research/analysis/strategy-family-reassessment/family-evidence-matrix.json", "research/analysis/strategy-family-reassessment/human-review-packet.json", "reports/audits/strategy-family-reassessment/strategy-family-reassessment-final-report.json"]})
    if router_equivalence.get("status") == "router_extraction_semantic_equivalence_verified":
        completed_stages.append({"stage": "Router Extraction Semantic Equivalence", "status": "completed", "evidence": ["research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-semantic-equivalence-result.json", "reports/audits/regime-conditioned-branch-factorization/router-extraction-semantic-equivalence-recertification-attempt-3-final-report.json"]})
    if ablation_result.get("status") == "completed":
        completed_stages.append({"stage": "Branch Contribution Ablation", "status": "completed", "evidence": ["research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json", "reports/audits/branch-contribution-ablation-v1/ablation-execution-attempt-2-final-report.json"]})
    if temporal_review_result.get("status") == "completed":
        completed_stages.append({"stage": "Ranging-short Temporal Branch Contribution Review", "status": "completed", "evidence": ["research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json", "reports/audits/ranging-short-temporal-review-v1/final-report.json"]})
    if retention_closure.get("status") == "closed_mixed_temporal_dependency":
        completed_stages.append({"stage": "Ranging-short Branch Retention Review", "status": "completed", "evidence": ["research/closures/ranging-short-branch-retention-review-v1.json", "reports/closures/ranging-short-branch-retention-review-v1-final-report.json"]})
    if chan_reversal_report.get("classification") == "development_rejected_material_degradation":
        completed_stages.append({"stage": "Chan Structure Reversal Candidate", "status": "rejected", "evidence": ["research/analysis/chan-structure-reversal-v1/development-comparison.json", "reports/audits/chan-structure-reversal-v1/final-report.json"]})
    if pair_inventory:
        completed_stages.append({"stage": "Additional-pair Manifest Inventory", "status": "completed_stopped", "evidence": ["research/analysis/discovery-additional-pair-manifest-inventory-v1-v2/analysis.json", "reports/audits/discovery-additional-pair-manifest-inventory-v1-v2/report.md"]})
    if distribution_profile:
        completed_stages.append({"stage": "BNB/XRP Distribution Shift Profile", "status": "completed", "evidence": ["research/analysis/discovery-bnb-xrp-distribution-shift-profile-v1-v1/analysis.json", "reports/audits/discovery-bnb-xrp-distribution-shift-profile-v1-v1/report.md"]})
    if timeframe_coherence:
        completed_stages.append({"stage": "BNB/XRP Timeframe Coherence Profile", "status": "completed", "evidence": ["research/analysis/discovery-bnb-xrp-timeframe-coherence-v1-v1/analysis.json", "reports/audits/discovery-bnb-xrp-timeframe-coherence-v1-v1/report.md"]})
    if funding_mark_profile:
        completed_stages.append({"stage": "BNB/XRP Funding/Mark Stress Profile", "status": "completed", "evidence": ["research/analysis/discovery-bnb-xrp-funding-mark-stress-v1-v1/analysis.json", "reports/audits/discovery-bnb-xrp-funding-mark-stress-v1-v1/report.md"]})
    capabilities = [
        {"capability": "sealed_offline_futures_backtesting", "status": "available", "evidence": ["research/runtime/offline-adapter-contract.yaml", "reports/audits/stage3a5_futures_online_offline_adapter_certification.md"]},
        {"capability": "candidate_process_isolation", "status": "available", "evidence": ["docs/decisions/ADR-candidate-python-import-isolation.md", "research/recertification/stage3d3b/stage3d2b-invalidation-event.json"]},
        {"capability": "balanced_research_gate", "status": "approved", "evidence": ["research/evaluation/evaluation-policy.yaml"]},
        {"capability": "branch_closure_governance", "status": "available", "evidence": ["research/closures/regime-aware-ranging-thresholds-v1.yaml"]},
        {"capability": "temporal_generalization_profile", "status": temporal.get("classification"), "evidence": ["research/temporal/stage3e1-temporal-comparison.json"]},
        {"capability": "immutable_backtest_execution_namespace", "status": "available", "evidence": ["research/governance/backtest-output-namespace-contract.yaml", "research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-lineage.json"]},
    ]
    invalidation_reasons = sorted({
        record.get("reason_code")
        for record in invalidation.get("records", [])
        if record.get("research_validity") == "invalidated" and record.get("reason_code")
    })
    fixed_defects = [{
        "defect": invalidation_reasons[0] if len(invalidation_reasons) == 1 else invalidation_reasons,
        "original_validity": "invalidated_experiments_2_to_10",
        "repair_status": recertification.get("status", "recertified_fresh_process_import_isolation"),
        "recertified_experiment_ids": closure.get("experiment_lineage", {}).get("recertified_experiment_ids", []),
        "evidence": ["research/recertification/stage3d3b/stage3d2b-invalidation-event.json", "docs/decisions/ADR-candidate-python-import-isolation.md", "research/closures/regime-aware-ranging-thresholds-v1.yaml"],
    }]
    unresolved_questions = [
        {"question_id": "cross-pair-generalization", "question": "Does temporal consistency persist across additional Binance USD-M pairs?", "evidence": ["research/temporal/stage3e1-temporal-comparison.json", "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "research/analysis/discovery-bnb-xrp-distribution-shift-profile-v1-v1/analysis.json", "research/analysis/discovery-bnb-xrp-timeframe-coherence-v1-v1/analysis.json"], "current_answer": "timeframe_coherent_economic_rankings_unstable_descriptive_only" if timeframe_coherence and distribution_profile else eth_generalization.get("status", stage4b1_decision.get("status", "unknown_no_sealed_non_btc_strategy_dataset"))},
        {"question_id": "exit-logic-structure", "question": "Which exit mechanisms explain regime-specific losses without changing risk semantics?", "evidence": ["research/analysis/stage3d3a-final-report.json", "research/temporal/stage3e1-temporal-comparison.json", "research/analysis/exit-logic-audit/exit-attribution.json"], "current_answer": exit_logic_decision.get("status", "attribution_incomplete")},
        {"question_id": "regime-branch-structure", "question": "Are regime branch activation and directionality imbalances structural rather than threshold-local?", "evidence": ["research/analysis/regime-aware-condition-graph.json", "research/temporal/stage3e1-temporal-comparison.json", "research/analysis/regime-branch-audit/regime-branch-structure.json"], "current_answer": regime_branch_decision.get("status", "read_only_audit_possible")},
        {"question_id": "strategy-family-reassessment", "question": "Should the current regime-aware family be retained, restructured or retired from active research?", "evidence": ["research/analysis/strategy-family-reassessment/family-evidence-matrix.json", "research/analysis/strategy-family-reassessment/human-review-packet.json"], "current_answer": strategy_family.get("decision", "not_audited")},
        {"question_id": "branch-contribution-ablation", "question": "Which single regime-direction signal group contributes incremental BTC/ETH development evidence?", "evidence": ["research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json", "research/closures/ranging-short-branch-retention-review-v1.json"] if retention_closure else ["research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json", "research/director/next-after-branch-ablation/proposals/ranging-short-branch-decision-review-v1.json"], "current_answer": retention_closure.get("status", temporal_review_result.get("classification", ablation_result.get("classification", "pending_compilation_and_human_execution_review" if ablation_proposal else "not_proposed")))},
    ]
    pending_proposals = [
        {"proposal_id": "stage3d3b-research-direction-proposal", "historical_status": attribution.get("proposal_status"), "resolved_by": "stage3d3b-recertification", "evidence": ["research/proposals/stage3d3b-research-direction-proposal.yaml", "research/closures/regime-aware-ranging-thresholds-v1.yaml"]},
        {"proposal_id": "stage3d4b-mechanism-proposal", "historical_status": "approved_no_change", "resolved_by": "A_keep_current", "evidence": ["research/proposals/stage3d4b-mechanism-proposal.yaml", "research/closures/stage3d4b-mechanism-approval-event.json"]},
        {"proposal_id": "branch-contribution-ablation-v1", "historical_status": "completed", "resolved_by": ablation_result.get("classification"), "semantic_fingerprint": ablation_proposal.get("semantic_fingerprint"), "evidence": ["research/director/next-after-router-equivalence/proposals/branch-contribution-ablation-v1.json", "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json"]},
        {"proposal_id": "ranging-short-branch-decision-review-v1", "historical_status": "completed" if temporal_review_result else "approved_for_compilation_only", "resolved_by": temporal_review_result.get("classification") if temporal_review_result else None, "semantic_fingerprint": decision_proposal.get("semantic_fingerprint"), "evidence": ["research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json"] if temporal_review_result else ["research/director/next-after-branch-ablation/proposals/ranging-short-branch-decision-review-v1.json", "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json"]},
    ]
    if retention_proposal:
        pending_proposals.append({
            "proposal_id": retention_proposal.get("proposal_id"),
            "historical_status": "approved" if retention_closure else retention_proposal.get("status"),
            "resolved_by": retention_closure.get("decision") if retention_closure else None,
            "closure_status": retention_closure.get("status") if retention_closure else None,
            "semantic_fingerprint": retention_proposal.get("semantic_fingerprint"),
            "evidence": ["research/director/next-after-ranging-short-temporal/proposals/ranging-short-branch-retention-review-v1.json", "research/closures/ranging-short-branch-retention-review-v1.json"] if retention_closure else ["research/director/next-after-ranging-short-temporal/proposals/ranging-short-branch-retention-review-v1.json"],
        })

    lineage_path = data_lineage or (repo / "research/data/data-lineage.sqlite")
    lineage_record = {
        "path": lineage_path.as_posix(),
        "exists": lineage_path.is_file(),
        "sha256": sha256_file(lineage_path) if lineage_path.is_file() else None,
    }
    if not lineage_record["exists"]:
        previous_lineage = ((previous_state.get("governance_inputs") or {}).get("data_lineage") or [])
        if previous_lineage:
            lineage_record = {**previous_lineage[0], "available_in_current_worktree": False}

    state: dict[str, Any] = {
        "schema_version": "current-research-state-v1",
        "generated_at": utc_now(),
        "formal_strategy": {"name": "RegimeAwareV6", "path": "strategies/RegimeAwareV6.py", "sha256": sha256_file(strategy_path), "evidence": ["strategies/RegimeAwareV6.py", "research/closures/regime-aware-ranging-thresholds-v1.yaml"]},
        "runtime_contracts": runtime_contracts,
        "evaluation_policy": {"policy_id": policy.get("policy_id"), "approval_status": policy.get("policy_approval_status"), "declared_sha256": policy.get("policy_sha256"), "file_sha256": sha256_file(policy_path), "path": "research/evaluation/evaluation-policy.yaml", "evidence": ["research/evaluation/evaluation-policy.yaml", "reports/decisions/stage3c2_evaluation_policy_decision_packet.md"]},
        "datasets": datasets,
        "completed_stages": completed_stages,
        "harness_capabilities": capabilities,
        "campaign_definitions": campaigns,
        "completed_campaigns": registry.get("campaigns", []),
        "closed_branches": [{
            "closure_id": closure.get("closure_id"),
            "status": closure.get("status"),
            "research_status": closure.get("research_status"),
            "decision": closure.get("approved_mechanism"),
            "variables": sorted((closure.get("variables") or {}).keys()),
            "reopen_conditions": closure.get("reopen_conditions", []),
            "insufficient_reopen_reasons": closure.get("insufficient_reopen_reasons", []),
            "evidence": ["research/closures/regime-aware-ranging-thresholds-v1.yaml", "research/closures/stage3d4b-final-closure.json", "Research Registry:stage3d4b_branch_closure_events"],
        }] + ([{
            "closure_id": retention_closure.get("closure_id"),
            "status": retention_closure.get("status"),
            "research_status": retention_closure.get("research_status"),
            "decision": retention_closure.get("decision"),
            "branch": retention_closure.get("formal_branch"),
            "scope": retention_closure.get("research_direction"),
            "slice_conclusions": retention_closure.get("slice_conclusions"),
            "temporally_stable_deletion_evidence": retention_closure.get("temporally_stable_deletion_evidence"),
            "reopen_conditions": retention_closure.get("reopen_conditions", []),
            "insufficient_reopen_reasons": retention_closure.get("insufficient_reopen_reasons", []),
            "evidence": ["research/closures/ranging-short-branch-retention-review-v1.json", "research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json"],
        }] if retention_closure else []),
        "invalidated_research": [{"event_id": invalidation.get("event_id"), "reason": invalidation_reasons, "affected_experiment_ids": invalidation.get("affected_experiment_ids", []), "repair_status": "recertified", "evidence": ["research/recertification/stage3d3b/stage3d2b-invalidation-event.json", "research/closures/regime-aware-ranging-thresholds-v1.yaml"]}],
        "fixed_harness_defects": fixed_defects,
        "proposal_history": pending_proposals,
        "allowed_research_scope": {"read_only_analysis": True, "campaign_compilation_only": True, "approved_market": "Binance USD-M Futures", "baseline_pair": "BTC/USDT:USDT", "human_approved_additional_pairs": ["ETH/USDT:USDT", "BNB/USDT:USDT", "XRP/USDT:USDT"], "baseline_timeframe": "1h", "strategy_mutation": False, "candidate_creation": False, "ranging_short_evidence_reuse": "new_human_approved_regime_conditioned_routing_research_only" if retention_closure else None, "evidence": ["research/evaluation/evaluation-policy.yaml", "research/governance/research-constitution.yaml", "research/governance/approvals/eth-cross-pair-generalization-v1-approval.json", "research/governance/approvals/bnb-xrp-development-descriptive-research-scope-v1-approval.json"]},
        "forbidden_scope": {"validation_feedback_mutation": True, "holdout": True, "live": True, "private_api": True, "strategy_or_risk_change": True, "closed_threshold_branch": True, "ranging_short_whole_branch_deletion_reopen": bool(retention_closure), "evidence": ["research/evaluation/evaluation-policy.yaml", "research/closures/regime-aware-ranging-thresholds-v1.yaml", "research/governance/research-constitution.yaml"]},
        "validation_holdout": {"validation_dataset_manifest_visible": True, "validation_result_feedback_available_to_director": False, "validation_access_budget": 0, "holdout_available": False, "accessed_by_stage4a": False, "evidence": ["research/evaluation/evaluation-policy.yaml", "research/data/validation-access-policy.yaml"]},
        "unresolved_research_questions": unresolved_questions,
        "data_capabilities": {"btc_development_dataset": True, "btc_validation_manifest": True, "sealed_exchange_metadata": True, "public_non_btc_market_metadata": stage4b1_decision.get("public_non_btc_market_metadata_available", True), "non_btc_sealed_strategy_dataset": eth_generalization.get("campaign_completed", False), "eth_development_dataset": eth_generalization.get("dataset_id"), "bnb_development_dataset": "futures-dev-bnb-usdt-usdt-20240101-20240830-v1", "xrp_development_dataset": "futures-dev-xrp-usdt-usdt-20240101-20240830-v1", "additional_pair_research_use": "development_descriptive_only", "cross_pair_readiness_audit_completed": stage4b1_decision.get("campaign_audit_completed", False), "human_pair_scope_required": False, "temporal_slices": temporal.get("valid_slice_count", 0), "evidence": ["research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml", "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml", "research/data/snapshots/futures-dev-bnb-usdt-usdt-20240101-20240830-v1/manifest.yaml", "research/data/snapshots/futures-dev-xrp-usdt-usdt-20240101-20240830-v1/manifest.yaml", "research/governance/approvals/bnb-xrp-development-descriptive-research-scope-v1-approval.json", "research/temporal/stage3e1-temporal-comparison.json", "research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml", "research/director/compiled/cross-pair-data-readiness-audit-v1/execution/readiness-decision.json"]},
        "possible_next_directions": [
            *([] if funding_mark_profile else [{"direction": "bnb_xrp_funding_mark_stress_profile", "evidence": ["research/discovery/runs/discovery-run-66c83d41c84027eb/shortlist.json", "research/data/snapshots/futures-dev-bnb-usdt-usdt-20240101-20240830-v1/manifest.yaml", "research/data/snapshots/futures-dev-xrp-usdt-usdt-20240101-20240830-v1/manifest.yaml"]}]),
            *([{"direction": "bnb_xrp_regime_occupancy_transfer_human_review", "evidence": ["research/discovery/runs/discovery-run-66c83d41c84027eb/shortlist.json", "research/analysis/discovery-bnb-xrp-timeframe-coherence-v1-v1/analysis.json"]}] if funding_mark_profile else []),
            {"direction": "exit_logic_structure_audit", "evidence": ["research/analysis/stage3d3a-final-report.json", "research/temporal/stage3e1-temporal-comparison.json"]},
            {"direction": "regime_branch_structure_audit", "evidence": ["research/analysis/regime-aware-condition-graph.json", "research/closures/regime-aware-ranging-thresholds-v1.yaml"]},
            *([] if retention_closure else [{"direction": "ranging_short_branch_decision_review_v1_compilation_only", "evidence": ["research/director/next-after-branch-ablation/proposals/ranging-short-branch-decision-review-v1.json", "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json"]}]),
        ],
        "governance_inputs": {
            "adrs": [{"path": "docs/decisions/ADR-candidate-python-import-isolation.md", "sha256": sha256_file(repo / "docs/decisions/ADR-candidate-python-import-isolation.md")}],
            "data_lineage": [lineage_record],
            "approval_events": [{"path": "research/closures/stage3d4b-mechanism-approval-event.json", "sha256": sha256_file(repo / "research/closures/stage3d4b-mechanism-approval-event.json")}],
        },
        "registry": registry,
        "state_conflicts": closure_conflicts,
        "git": {"head": git(repo, "rev-parse", "HEAD"), "branch": git(repo, "branch", "--show-current"), "versioned_worktree_clean": not versioned_changes, "status_lines": git_status, "evidence": ["git rev-parse HEAD", "git branch --show-current", "git status --porcelain=v2 --branch --untracked-files=all"]},
        "stage4a_boundaries": {"campaign_executed": False, "candidate_created": False, "backtest_run": False, "validation_accessed": False, "holdout_accessed": False, "constitution_approved": False, "stage4b_started": False},
        "stage4b1_execution": {
            "status": "completed" if stage4b1_decision.get("campaign_audit_completed") is True else "not_started",
            "result_code": stage4b1_decision.get("status"),
            "campaign_executed": stage4b1_decision.get("campaign_executed", False),
            "new_dataset_created": stage4b1_decision.get("new_dataset_created", False),
            "validation_accesses": stage4b1_decision.get("validation_accesses", 0),
            "holdout_accesses": stage4b1_decision.get("holdout_accesses", 0),
            "next_campaign_executed": False,
            "stage4c_started": False,
            "evidence": ["research/director/compiled/cross-pair-data-readiness-audit-v1/execution/readiness-decision.json"] if stage4b1_decision else [],
        },
        "exit_logic_structure_audit": {
            "status": "completed" if exit_logic_decision.get("campaign_executed") is True else "not_started",
            "result_code": exit_logic_decision.get("status"),
            "campaign_executed": exit_logic_decision.get("campaign_executed", False),
            "strategy_or_risk_change_warranted": exit_logic_decision.get("strategy_or_risk_change_warranted", False),
            "candidate_created": exit_logic_decision.get("candidate_created", False),
            "validation_accesses": exit_logic_decision.get("validation_accesses", 0),
            "holdout_accesses": exit_logic_decision.get("holdout_accesses", 0),
            "next_campaign_executed": False,
            "stage4c_started": False,
            "evidence": ["research/analysis/exit-logic-audit/exit-attribution.json", "research/director/compiled/exit-logic-structure-audit-v1/execution/audit-decision.json"] if exit_logic_decision else [],
        },
        "regime_branch_structure_audit": {
            "status": "completed" if regime_branch_decision.get("campaign_executed") is True else "not_started",
            "result_code": regime_branch_decision.get("status"),
            "campaign_executed": regime_branch_decision.get("campaign_executed", False),
            "structural_imbalance_observed": regime_branch_decision.get("structural_imbalance_observed", False),
            "stable_one_sided_imbalance_observed": regime_branch_decision.get("stable_one_sided_imbalance_observed", False),
            "strategy_structure_change_warranted": regime_branch_decision.get("strategy_structure_change_warranted", False),
            "threshold_search_reopen_warranted": regime_branch_decision.get("threshold_search_reopen_warranted", False),
            "candidate_created": regime_branch_decision.get("candidate_created", False),
            "validation_accesses": regime_branch_decision.get("validation_accesses", 0),
            "holdout_accesses": regime_branch_decision.get("holdout_accesses", 0),
            "next_campaign_executed": False,
            "stage4c2_started": False,
            "evidence": ["research/analysis/regime-branch-audit/regime-branch-structure.json", "research/director/compiled/regime-branch-structure-audit-v1/execution/audit-decision.json"] if regime_branch_decision else [],
        },
        "eth_cross_pair_generalization": {
            "status": "completed" if eth_generalization.get("campaign_completed") is True else "not_started",
            "result_code": eth_generalization.get("status"),
            "campaign_executed": eth_generalization.get("campaign_completed", False),
            "dataset_id": eth_generalization.get("dataset_id"),
            "reproducible": eth_generalization.get("reproducible", False),
            "cross_pair_execution_behavior_observed": eth_generalization.get("cross_pair_execution_behavior_observed", False),
            "cross_pair_generalization_proven": eth_generalization.get("cross_pair_generalization_proven", False),
            "strategy_change_warranted": eth_generalization.get("strategy_change_warranted", False),
            "candidate_created": eth_generalization.get("candidate_created", False),
            "validation_accesses": eth_generalization.get("validation_accesses", 0),
            "holdout_accesses": eth_generalization.get("holdout_accesses", 0),
            "evidence": ["research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "reports/audits/eth-cross-pair-generalization/eth-cross-pair-generalization-final-report.json"] if eth_generalization else [],
        },
        "strategy_family_reassessment": {
            "status": strategy_family.get("status", "not_started"),
            "decision": strategy_family.get("decision"),
            "campaign_executed": strategy_family.get("status") == "completed",
            "unique_priority_structure_direction": strategy_family.get("unique_priority_structure_direction"),
            "strategy_modified": strategy_family.get("strategy_modified", False),
            "candidate_created": strategy_family.get("candidate_created", False),
            "backtest_run": strategy_family.get("backtest_run", False),
            "hyperopt_run": strategy_family.get("hyperopt_run", False),
            "validation_accesses": strategy_family.get("validation_accesses", 0),
            "holdout_accesses": strategy_family.get("holdout_accesses", 0),
            "next_campaign_compiled": strategy_family.get("next_campaign_compiled", False),
            "next_campaign_executed": strategy_family.get("next_campaign_executed", False),
            "evidence": ["research/analysis/strategy-family-reassessment/family-evidence-matrix.json", "research/analysis/strategy-family-reassessment/human-review-packet.json", "reports/audits/strategy-family-reassessment/strategy-family-reassessment-final-report.json"] if strategy_family else [],
        },
        "router_extraction_semantic_equivalence": {
            "status": router_equivalence.get("status", "not_started"),
            "campaign_fingerprint": router_equivalence.get("campaign_fingerprint"),
            "formal_execution_baseline": "RegimeAwareV6",
            "router_equivalent_structural_reference": "RegimeAwareRouterEquivalentV1",
            "btc_trade_count": (router_equivalence.get("comparisons") or {}).get("btc", {}).get("total_trades"),
            "eth_trade_count": (router_equivalence.get("comparisons") or {}).get("eth", {}).get("total_trades"),
            "validation_accesses": router_equivalence.get("validation_accesses", 0),
            "holdout_accesses": router_equivalence.get("holdout_accesses", 0),
            "branch_ablation_run": router_equivalence.get("branch_ablation_run", False),
            "next_proposal_id": decision_proposal.get("proposal_id"),
            "next_proposal_fingerprint": decision_proposal.get("semantic_fingerprint"),
            "next_proposal_status": "approved_for_compilation_only" if decision_proposal else None,
            "evidence": ["research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-semantic-equivalence-result.json", "research/analysis/regime-conditioned-branch-factorization/current-structure-map.json"] if router_equivalence else [],
        },
        "branch_contribution_ablation": {
            "status": ablation_result.get("status", "not_started"),
            "classification": ablation_result.get("classification"),
            "research_unit": ablation_result.get("research_unit"),
            "candidate_reused": ablation_result.get("candidate_reused", False),
            "candidate_created_in_attempt": ablation_result.get("candidate_created_in_attempt", False),
            "backtest_calls": ablation_result.get("backtest_calls", 0),
            "validation_accesses": ablation_result.get("validation_accesses", 0),
            "holdout_accesses": ablation_result.get("holdout_accesses", 0),
            "formal_strategy_modified": ablation_result.get("strategy_modified", False),
            "next_proposal_id": decision_proposal.get("proposal_id"),
            "next_proposal_fingerprint": decision_proposal.get("semantic_fingerprint"),
            "next_proposal_status": "approved_for_compilation_only" if decision_proposal else None,
            "evidence": ["research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json", "reports/audits/branch-contribution-ablation-v1/ablation-execution-attempt-2-final-report.json"] if ablation_result else [],
        },
        "ranging_short_temporal_branch_contribution_review": {
            "status": temporal_review_result.get("status", "not_started"),
            "execution_attempt_id": temporal_review_result.get("execution_attempt_id"),
            "classification": temporal_review_result.get("classification"),
            "slice_count": len(temporal_review_result.get("slice_results") or {}),
            "backtest_calls": temporal_review_result.get("backtest_calls", 0),
            "candidate_reused": temporal_review_result.get("candidate_reused", False),
            "candidate_modified": temporal_review_result.get("candidate_modified", False),
            "formal_strategy_modified": temporal_review_result.get("strategy_modified", False),
            "validation_accesses": temporal_review_result.get("validation_accesses", 0),
            "holdout_accesses": temporal_review_result.get("holdout_accesses", 0),
            "next_proposal_id": retention_proposal.get("proposal_id"),
            "next_proposal_fingerprint": retention_proposal.get("semantic_fingerprint"),
            "next_proposal_status": "resolved_human_retain_current_branch" if retention_closure else retention_proposal.get("status"),
            "evidence": ["research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json", "reports/audits/ranging-short-temporal-review-v1/final-report.json"] if temporal_review_result else [],
        },
        "ranging_short_branch_retention_review": {
            "status": "completed" if retention_closure else "not_started",
            "decision": retention_closure.get("decision"),
            "closure_status": retention_closure.get("status"),
            "formal_branch_retained": retention_closure.get("formal_branch_action") == "retained_unchanged",
            "slice_conclusions": retention_closure.get("slice_conclusions", {}),
            "campaign_generated": False,
            "campaign_executed": False,
            "candidate_created": False,
            "strategy_modified": False,
            "additional_backtests": 0,
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "next_campaign_generated": False,
            "next_campaign_executed": False,
            "evidence": ["research/closures/ranging-short-branch-retention-review-v1.json", "reports/closures/ranging-short-branch-retention-review-v1-final-report.json"] if retention_closure else [],
        },
        "chan_structure_reversal_candidate": {
            "status": "closed_rejected" if chan_reversal_report.get("classification") == "development_rejected_material_degradation" else "not_started",
            "classification": chan_reversal_report.get("classification"),
            "candidate_created": bool(chan_reversal_report),
            "candidate_promoted": chan_reversal_report.get("candidate_promoted", False),
            "formal_strategy_modified": chan_reversal_report.get("formal_strategy_modified", False),
            "validation_accesses": (chan_reversal_report.get("budget_used") or {}).get("validation_accesses", 0),
            "holdout_accesses": (chan_reversal_report.get("budget_used") or {}).get("holdout_accesses", 0),
            "forward_dry_run_authorized": chan_reversal_report.get("forward_dry_run_authorized", False),
            "live_trading_authorized": chan_reversal_report.get("live_trading_authorized", False),
            "evidence": ["research/analysis/chan-structure-reversal-v1/development-comparison.json", "reports/audits/chan-structure-reversal-v1/final-report.json"] if chan_reversal_report else [],
        },
    }
    state["research_discovery"] = discovery_registry_summary(director_registry)
    state["open_source_knowledge"] = knowledge_state_summary(repo)
    state["state_fingerprint"] = fingerprint({key: value for key, value in state.items() if key not in {"generated_at", "state_fingerprint"}})
    state["snapshot_id"] = f"research-state-{state['state_fingerprint'][:16]}"
    return state


def markdown(state: dict[str, Any]) -> str:
    lines = [
        "# Current Research State", "",
        f"- Snapshot: `{state['snapshot_id']}`",
        f"- Fingerprint: `{state['state_fingerprint']}`",
        f"- Formal strategy: `{state['formal_strategy']['name']}` / `{state['formal_strategy']['sha256']}`",
        f"- Git: `{state['git']['branch']}` at `{state['git']['head']}`",
        f"- State conflicts: `{len(state['state_conflicts'])}`", "",
        "## Completed stages", "",
    ]
    lines.extend(f"- {item['stage']}: `{item['status']}` — {', '.join(item['evidence'])}" for item in state["completed_stages"])
    lines.extend(["", "## Closed branches", ""])
    for item in state["closed_branches"]:
        lines.append(f"- `{item['closure_id']}`: `{item['status']}`, decision `{item['decision']}`; evidence: {', '.join(item['evidence'])}")
    lines.extend(["", "## Unresolved questions", ""])
    lines.extend(f"- `{item['question_id']}`: {item['question']} Evidence: {', '.join(item['evidence'])}" for item in state["unresolved_research_questions"])
    lines.extend(["", "## Current boundaries", "", "- Validation feedback is not available to the Director.", "- Holdout, live trading, private API, Candidate creation, strategy mutation and closed-threshold reopening are forbidden.", "- Stage 4A has not executed a Campaign or accessed Validation/Holdout.", ""])
    knowledge = state.get("open_source_knowledge") or {}
    if knowledge.get("available"):
        counts = knowledge["counts"]
        maintenance = knowledge.get("maintenance") or {}
        lines.extend([
            "## Open-source knowledge", "",
            f"- Snapshot: `{knowledge['knowledge_id']}` / `{knowledge['knowledge_snapshot_fingerprint']}`.",
            f"- Catalog: `{counts['sources']}` fixed repositories, `{counts['patterns']}` clean-room pattern cards, and `{counts['lessons']}` internal lesson cards.",
            "- Public repositories remain Class C evidence and cannot independently authorize a proposal or Candidate.",
            "- Knowledge Broker injects deterministic Top-K context into Researcher packets; Idea, Critic, and Director binding checks remain mandatory.",
            "- Researcher and Critic tasks use a provider-neutral lease queue. Completed Campaigns create review-only lesson feedback drafts.",
            "- Source refreshes create human-approval-only update proposals; source updates and lesson promotion are never automatic.",
            f"- Retrieval evaluation: `{maintenance.get('retrieval_evaluation')}`; learning-loop health: `{maintenance.get('learning_loop_health')}`.",
            f"- Pending human review packet: `{maintenance.get('pending_review_packet')}`.",
            f"- Non-authoritative review recommendations: `{maintenance.get('review_recommendations')}`.",
            f"- Last human review batch: `{(maintenance.get('last_review_batch') or {}).get('status')}`; archive `{(maintenance.get('last_review_batch') or {}).get('archive')}`.",
            f"- Lesson curation: `{maintenance.get('lesson_curation')}`; promotion review packet: `{maintenance.get('promotion_review_packet')}`.",
            f"- Last lesson promotion batch: `{(maintenance.get('last_promotion_batch') or {}).get('status')}`; archive `{(maintenance.get('last_promotion_batch') or {}).get('archive')}`.",
            f"- Evidence context: `{knowledge['evidence'][0]}`.", "",
        ])
    return "\n".join(lines).replace("\ufffd\ufffd", "—")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--source-registry", default=os.getenv("RESEARCH_SOURCE_REGISTRY"))
    parser.add_argument("--data-lineage", default=os.getenv("RESEARCH_DATA_LINEAGE"))
    parser.add_argument("--director-registry")
    parser.add_argument("--output-json", default="research/director/current-research-state.json")
    parser.add_argument("--output-md", default="research/director/current-research-state.md")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    source_registry = Path(args.source_registry) if args.source_registry else None
    data_lineage = Path(args.data_lineage) if args.data_lineage else None
    state = build_state(
        repo,
        source_registry,
        data_lineage,
        Path(args.director_registry) if args.director_registry else None,
    )
    write_json(repo / args.output_json, state)
    md_path = repo / args.output_md
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown(state), encoding="utf-8")
    if args.director_registry:
        connection = open_director_registry(args.director_registry)
        connection.execute(
            "INSERT OR REPLACE INTO research_state_snapshots(snapshot_id, fingerprint, git_head, status, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (state["snapshot_id"], state["state_fingerprint"], state["git"]["head"], "generated", json.dumps(state, sort_keys=True), utc_now()),
        )
        connection.commit()
        connection.close()
    print(json.dumps({"snapshot_id": state["snapshot_id"], "fingerprint": state["state_fingerprint"], "conflicts": len(state["state_conflicts"]), "output_json": args.output_json, "output_md": args.output_md}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
