#!/usr/bin/env python3
"""Execute the approved read-only strategy family reassessment Campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from protected_manifest_hash import validate_protected_manifests
from research_director_common import load_document, open_director_registry, proposal_fingerprint, sha256_file, utc_now, write_json


PROPOSAL_ID = "strategy-family-reassessment-v1"
CAMPAIGN_ID = "stage4a-strategy-family-reassessment-v1"
PROPOSAL_FINGERPRINT = "32c5b3c956bbb33ccbc9e8d3d509add58183dc7faa51524458562d5136b3e8f6"
CAMPAIGN_FINGERPRINT = "1b3900b566df7a07313a9e9832e30c1e9a16efeade246c486b3a052b38a2b8a1"
STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
CONSTITUTION_SHA256 = "ff0ca1b7f3aa4f7f0a7d6b893095ba618d1ecf50cf7044dfeb3152bd91826722"
POLICY_SHA256 = "ee4769e4c814e209e771c31fa35ff4d8c4719137fffe7291d3ae87d73c8e8b5e"
RUNTIME_SHA256 = "e87e375a8c61d8b7eeae8e53fc0715840956ea617471ad9c7d06275d9726f76d"


def validate_authority(repo: Path) -> dict[str, Any]:
    proposal = load_document(repo / "research/director/strategy-family-reassessment-v1/proposals/strategy-family-reassessment-v1.json")
    campaign = load_document(repo / "research/director/compiled/strategy-family-reassessment-v1/campaign.yaml")
    approval = load_document(repo / "research/governance/approvals/strategy-family-reassessment-v1-execution-approval.json")
    authorization = load_document(repo / "research/director/compiled/strategy-family-reassessment-v1/execution-authorization.json")
    protected = validate_protected_manifests(repo)
    checks = {
        "proposal_fingerprint": proposal_fingerprint(proposal) == proposal["semantic_fingerprint"] == approval["proposal_fingerprint"] == PROPOSAL_FINGERPRINT,
        "campaign_fingerprint": campaign["campaign_fingerprint"] == approval["compiled_campaign_fingerprint"] == authorization["approved_compiled_fingerprint"] == CAMPAIGN_FINGERPRINT,
        "human_approval": approval["approval_status"] == "approved" and approval["approver_type"] == "human_user",
        "read_only_execution_authorized": approval["execution_authorized"] is True and approval["execution_scope"] == "read_only_audit_only" and authorization["execution_authorized"] is True,
        "strategy": sha256_file(repo / "strategies/RegimeAwareV6.py") == STRATEGY_SHA256,
        "constitution": sha256_file(repo / "research/governance/research-constitution.yaml") == CONSTITUTION_SHA256,
        "policy": sha256_file(repo / "research/evaluation/evaluation-policy.yaml") == POLICY_SHA256,
        "runtime": sha256_file(repo / "research/runtime/freqtrade-runtime.yaml") == RUNTIME_SHA256,
        "protected_manifests": protected["passed"],
        "forbidden_authority_zero": not any(approval[key] for key in ("strategy_modification_authorized", "candidate_creation_authorized", "backtest_authorized", "hyperopt_authorized", "automatic_followup_campaign_authorized")),
        "protected_access_zero": approval["validation_accesses_authorized"] == approval["holdout_accesses_authorized"] == 0,
    }
    if not all(checks.values()):
        raise RuntimeError("strategy_family_reassessment_preflight_failed:" + json.dumps(checks, sort_keys=True))
    return {"checks": checks, "protected_manifests": protected}


def build_evidence_matrix(repo: Path) -> dict[str, Any]:
    temporal = load_document(repo / "research/temporal/stage3e1-temporal-comparison.json")
    eth = load_document(repo / "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json")
    regime = load_document(repo / "research/analysis/regime-branch-audit/regime-branch-structure.json")
    exit_audit = load_document(repo / "research/analysis/exit-logic-audit/exit-attribution.json")
    attribution = load_document(repo / "research/analysis/stage3d3a-final-report.json")
    graph = load_document(repo / "research/analysis/regime-aware-condition-graph.json")
    closure = load_document(repo / "research/closures/regime-aware-ranging-thresholds-v1.yaml")
    btc = load_document(repo / "research/data/provisioning/stage3c2p-development-probe.json")["baseline"]
    dimensions = [
        {"dimension": "cross_time", "observation": "BTC classification is temporally_consistent; 3 of 4 frozen slices are positive and one is negative.", "facts": {"classification": temporal["classification"], "positive_slices": temporal["positive_return_slices"], "negative_slices": temporal["negative_return_slices"], "profit_factors": temporal["profit_factor_distribution"]}, "implication": "do_not_retire_from_loss_alone_but_family_is_regime_sensitive"},
        {"dimension": "cross_pair", "observation": "ETH behavior is reproducible with the same 27 trades but materially weaker descriptive development metrics than BTC.", "facts": {"btc_total_profit_pct": btc["metrics"]["total_profit_pct"], "btc_profit_factor": btc["metrics"]["profit_factor"], "eth_total_profit_pct": eth["eth_metrics"]["total_profit_pct"], "eth_profit_factor": eth["eth_metrics"]["profit_factor"], "eth_reproducible": eth["reproducible"]}, "implication": "unchanged_family_generalization_is_not_established"},
        {"dimension": "long_short", "observation": "Aggregate temporal directionality is nearly balanced, but individual slices rotate sharply; full development and ETH are short-heavy.", "facts": {"temporal_long": regime["temporal_directionality"]["aggregate_long_trades"], "temporal_short": regime["temporal_directionality"]["aggregate_short_trades"], "eth_long": eth["eth_metrics"]["long_trade_count"], "eth_short": eth["eth_metrics"]["short_trade_count"]}, "implication": "do_not_remove_one_side_globally_investigate_router_to_direction_interaction"},
        {"dimension": "regime_branches", "observation": "Structural directionality rotates and the ranging breakdown exit is inactive, while no stable one-sided defect was found.", "facts": {"structural_imbalance": regime["structural_imbalance_observed"], "stable_one_sided": regime["stable_one_sided_imbalance_observed"], "findings": regime["findings"]}, "implication": "shared_router_and_branch_contribution_remain_unisolated"},
        {"dimension": "entry_exit_contribution", "observation": "Signal attribution completed, but exit audit found insufficient causal evidence for an exit change.", "facts": {"entry_count": attribution["entry_count"], "exit_count": attribution["exit_count"], "exit_result": exit_audit["result_code"], "exit_change_warranted": exit_audit["strategy_or_risk_change_warranted"]}, "implication": "prioritize_entry_router_structure_not_exit_rewrite"},
        {"dimension": "risk_drawdown", "observation": "BTC slice drawdowns remain bounded but dispersion and ETH absolute drawdown/negative return show pair sensitivity.", "facts": {"btc_slice_max_drawdown_pct": temporal["max_drawdown_distribution"], "eth_max_drawdown": eth["eth_metrics"]["max_drawdown"], "eth_total_profit_pct": eth["eth_metrics"]["total_profit_pct"]}, "implication": "future_structure_study_must_hold_risk_configuration_fixed"},
        {"dimension": "complexity", "observation": "The family contains multiple regime and direction-specific branches with a non-trivial condition graph.", "facts": {"condition_count": len(graph["conditions"]), "signal_group_count": len(graph["signal_groups"]), "groups": [item["branch"] for item in graph["signal_groups"]]}, "implication": "branch_level_factorization_has_information_value"},
        {"dimension": "closed_research", "observation": "Single-threshold and duplicate-signal research is closed and cannot be reopened by poor results.", "facts": {"closure_status": closure["status"], "closure_reason": closure["closure_reason"], "insufficient_reopen_reasons": closure["insufficient_reopen_reasons"]}, "implication": "no_adjacent_threshold_search"},
        {"dimension": "untested_structure_hypothesis", "observation": "No existing artifact isolates shared regime routing from direction-specific entry branches across BTC and ETH.", "facts": {"hypothesis": "regime_conditioned_branch_factorization", "existing_direct_evidence": False}, "implication": "unique_high_information_next_direction"},
    ]
    return {"schema_version": "strategy-family-evidence-matrix-v1", "campaign_id": CAMPAIGN_ID, "strategy_family": "RegimeAwareV6", "dimensions": dimensions, "source_paths": ["research/temporal/stage3e1-temporal-comparison.json", "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "research/analysis/regime-branch-audit/regime-branch-structure.json", "research/analysis/exit-logic-audit/exit-attribution.json", "research/analysis/stage3d3a-final-report.json", "research/analysis/regime-aware-condition-graph.json", "research/closures/regime-aware-ranging-thresholds-v1.yaml", "research/data/provisioning/stage3c2p-development-probe.json"]}


def decision_packet(matrix: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "strategy-family-human-decision-packet-v1",
        "proposal_id": PROPOSAL_ID,
        "campaign_id": CAMPAIGN_ID,
        "decision": "restructure_family_worth_studying",
        "active_research_recommendation": "retain_current_only_as_execution_baseline_while_one_structure_hypothesis_is_reviewed",
        "retire_rejected_reason": "BTC temporal evidence is reproducible and mostly positive by slice; ETH loss alone is insufficient for retirement.",
        "retain_unchanged_rejected_reason": "ETH weakness and unresolved router-to-branch contribution make unchanged active-family research lower information than one structural study.",
        "unique_priority_structure_direction": {
            "hypothesis_id": "regime-conditioned-branch-factorization-v1",
            "hypothesis": "Factor the shared regime router from direction-specific entry branches and measure branch contribution across the existing BTC and ETH development datasets.",
            "supporting_evidence": ["cross-time long/short rotation", "ETH reproducible but weaker metrics", "29-condition/5-group graph", "exit change unsupported", "threshold branch closed"],
            "risk_class": "medium",
            "new_candidate_required": True,
            "new_data_required": False,
            "backtest_required": True,
            "validation_required": False,
            "holdout_required": False,
            "allowed_next_campaign_scope": ["one explicitly approved structural Candidate", "existing BTC and ETH development datasets only", "branch-level attribution and ablation", "fixed Runtime, fee, leverage, risk and Evaluation Policy", "fresh-process reproducibility"],
            "forbidden_next_campaign_scope": ["threshold search", "exit rewrite", "risk parameter change", "Hyperopt", "Validation", "Holdout", "live or forward dry-run", "automatic second Candidate", "automatic execution"],
        },
        "evidence_matrix": "research/analysis/strategy-family-reassessment/family-evidence-matrix.json",
        "candidate_created": False,
        "strategy_modified": False,
        "backtest_run": False,
        "hyperopt_run": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "next_campaign_compiled": False,
        "next_campaign_executed": False,
        "human_approval_required": True,
    }


def record_registry(repo: Path, result: dict[str, Any], artifacts: list[str]) -> None:
    approval = load_document(repo / "research/governance/approvals/strategy-family-reassessment-v1-execution-approval.json")
    authorization = load_document(repo / "research/director/compiled/strategy-family-reassessment-v1/execution-authorization.json")
    completed_at = utc_now()
    run_id = "strategy-family-reassessment-v1-run"
    connection = open_director_registry(repo / "research/registry/stage4a-director.db")
    connection.execute("INSERT OR REPLACE INTO proposal_selection_events(proposal_id, proposal_fingerprint, approval_status, approver_type, approved_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)", (PROPOSAL_ID, PROPOSAL_FINGERPRINT, "approved", "human_user", "not_supplied", json.dumps(approval, sort_keys=True)))
    connection.execute("INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id, campaign_id, approved_compiled_fingerprint, proposal_id, execution_authorized, payload_json, authorized_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (authorization["authorization_id"], CAMPAIGN_ID, CAMPAIGN_FINGERPRINT, PROPOSAL_ID, 1, json.dumps(authorization, sort_keys=True), "not_supplied"))
    connection.execute("INSERT OR REPLACE INTO research_campaign_runs(run_id, campaign_id, proposal_id, status, result_code, campaign_executed, candidate_created, strategy_modified, validation_accesses, holdout_accesses, payload_json, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (run_id, CAMPAIGN_ID, PROPOSAL_ID, "completed", result["decision"], 1, 0, 0, 0, 0, json.dumps(result, sort_keys=True), completed_at))
    for path in artifacts:
        connection.execute("INSERT OR REPLACE INTO research_campaign_assets(asset_id, run_id, artifact_type, path, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?)", (f"{run_id}:{path}", run_id, "campaign_evidence", path, sha256_file(repo / path), completed_at))
    connection.commit()
    connection.close()


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    authority = validate_authority(repo)
    analysis_dir = repo / "research/analysis/strategy-family-reassessment"
    report_dir = repo / "reports/audits/strategy-family-reassessment"
    execution_dir = repo / "research/director/compiled/strategy-family-reassessment-v1/execution"
    for path in (analysis_dir, report_dir, execution_dir):
        path.mkdir(parents=True, exist_ok=True)
    matrix = build_evidence_matrix(repo)
    packet = decision_packet(matrix)
    write_json(analysis_dir / "family-evidence-matrix.json", matrix)
    write_json(analysis_dir / "human-review-packet.json", packet)
    decision_md = """# Strategy Family Reassessment Decision\n\n- Decision: `restructure_family_worth_studying`\n- Current family role: retain only as the execution baseline pending human review\n- Unique priority direction: `regime-conditioned-branch-factorization-v1`\n- Risk: `medium`\n- Candidate/new data/backtest: `future approval required / no / future approval required`\n\nBTC temporal evidence prevents retirement based on losses alone. ETH weakness and unresolved shared-router versus direction-branch contribution justify studying exactly one structural hypothesis. Threshold and exit branches remain closed. No strategy, Candidate, backtest, Hyperopt, Validation, or Holdout action occurred.\n"""
    (analysis_dir / "strategy-family-reassessment-decision.md").write_text(decision_md, encoding="utf-8")
    result = {"schema_version": "strategy-family-reassessment-result-v1", "status": "completed", "decision": packet["decision"], "campaign_id": CAMPAIGN_ID, "proposal_id": PROPOSAL_ID, "campaign_fingerprint": CAMPAIGN_FINGERPRINT, "authority": authority, "unique_priority_structure_direction": packet["unique_priority_structure_direction"], "strategy_modified": False, "candidate_created": False, "backtest_run": False, "hyperopt_run": False, "validation_accesses": 0, "holdout_accesses": 0, "next_campaign_compiled": False, "next_campaign_executed": False}
    write_json(execution_dir / "campaign-execution.json", result)
    write_json(report_dir / "strategy-family-reassessment-final-report.json", result)
    report_md = """# Strategy Family Reassessment Final Report\n\n- Final decision: `restructure_family_worth_studying`\n- Current family: retain as execution baseline only\n- Unique next direction: `regime-conditioned-branch-factorization-v1`\n- Next direction risk: `medium`\n- Strategy/Candidate/backtest/Hyperopt: `false / false / false / false`\n- Validation/Holdout: `0 / 0`\n\nThe approved read-only audit completed all three steps. No follow-up Campaign was compiled or executed.\n"""
    (report_dir / "strategy-family-reassessment-final-report.md").write_text(report_md, encoding="utf-8")
    artifacts = ["research/analysis/strategy-family-reassessment/family-evidence-matrix.json", "research/analysis/strategy-family-reassessment/human-review-packet.json", "research/analysis/strategy-family-reassessment/strategy-family-reassessment-decision.md", "research/director/compiled/strategy-family-reassessment-v1/execution/campaign-execution.json", "reports/audits/strategy-family-reassessment/strategy-family-reassessment-final-report.json", "reports/audits/strategy-family-reassessment/strategy-family-reassessment-final-report.md"]
    record_registry(repo, result, artifacts)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
