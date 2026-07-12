#!/usr/bin/env python3
"""Generate a small deterministic, evidence-based Research Proposal set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_director_common import (
    fingerprint,
    load_document,
    normalized_question,
    open_director_registry,
    proposal_fingerprint,
    utc_now,
    write_json,
    write_yaml,
)
from route_research_approval import route_proposal


CLOSED_THRESHOLD_MARKERS = {
    "ranging-threshold", "ranging_threshold", "adjacent-threshold", "adjacent_threshold",
    "rsi_min", "rsi_max", "adx_4h_max_long", "bb_percent_min",
}


def branch_closure_check(
    direction: str,
    state: dict[str, Any],
    satisfied_reopen_conditions: list[str] | None = None,
) -> dict[str, Any]:
    """Apply recorded closure conditions to a proposed research direction."""
    closure = next(
        (item for item in state.get("closed_branches", []) if item.get("closure_id") == "regime-aware-ranging-thresholds-v1"),
        None,
    )
    normalized = direction.lower()
    targets_closed_branch = any(marker in normalized for marker in CLOSED_THRESHOLD_MARKERS)
    if not closure or not targets_closed_branch:
        return {"checked": True, "blocked": False, "reason_code": None, "closure_id": closure.get("closure_id") if closure else None, "reopen_requested": False}
    recorded = set(closure.get("reopen_conditions") or [])
    satisfied = set(satisfied_reopen_conditions or [])
    met = sorted(recorded & satisfied)
    return {
        "checked": True,
        "blocked": not bool(met),
        "reason_code": None if met else "closed_branch_no_reopen_evidence",
        "closure_id": closure["closure_id"],
        "reopen_requested": True,
        "recorded_reopen_conditions_met": met,
    }


def evidence(path: str, claim: str) -> dict[str, str]:
    return {"path": path, "claim": claim}


def proposal_base(
    proposal_id: str,
    title: str,
    question: str,
    uncertainty: str,
    supporting: list[dict[str, str]],
    method: dict[str, Any],
    information_gain: tuple[float, str, str],
    risk_class: str,
    experiments: int,
    minutes: int,
    datasets: list[dict[str, Any]],
    runtime: dict[str, Any],
    policy: dict[str, Any],
    allowed_changes: list[str],
    required_artifacts: list[str],
    required_tests: list[str],
    mechanisms: list[str],
) -> dict[str, Any]:
    proposal: dict[str, Any] = {
        "schema_version": "research-proposal-v1",
        "proposal_id": proposal_id,
        "title": title,
        "research_question": question,
        "current_uncertainty": uncertainty,
        "supporting_evidence": supporting,
        "contradictory_evidence": [],
        "expected_information_gain": {"score": information_gain[0], "level": information_gain[1], "rationale": information_gain[2]},
        "proposed_method": method,
        "immutable_inputs": ["RegimeAwareV6 strategy hash", "Balanced Research Gate v1", "sealed runtime contracts", "branch closures"],
        "allowed_changes": allowed_changes,
        "forbidden_changes": ["strategy_change", "risk_change", "candidate_creation", "validation_access", "holdout_access", "live_or_private_api", "closed_threshold_research"],
        "required_datasets": datasets,
        "required_runtime": runtime,
        "required_policy": policy,
        "estimated_experiments": experiments,
        "estimated_wall_clock_minutes": minutes,
        "estimated_compute_cost": "low" if experiments <= 4 else "medium",
        "risk_class": risk_class,
        "contamination_risk": "none",
        "validation_requirement": "none",
        "holdout_requirement": "none",
        "branch_closure_reopen_check": {"checked": True, "blocked": False, "reason_code": None, "closure_id": "regime-aware-ranging-thresholds-v1", "reopen_requested": False},
        "duplicate_research_check": {"checked": True, "duplicate": False, "reason_code": None},
        "stop_conditions": ["evidence_conflict", "missing_immutable_input", "budget_exhausted", "scope_expansion_required", "information_gain_resolved"],
        "success_criteria": ["all claims trace to evidence", "result is reproducible", "no strategy or risk semantics changed"],
        "failure_does_not_imply": ["strategy_is_unprofitable", "closed_threshold_branch_should_reopen", "promotion_is_allowed"],
        "required_artifacts": required_artifacts,
        "required_tests": required_tests,
        "approval_requirement": "auto_approvable_future" if risk_class == "low" else "human_approval_required",
        "recommendation_confidence": min(0.99, max(0.0, information_gain[0] - 0.04)),
        "recommendation": "research_recommended",
        "referenced_variables": [],
        "referenced_mechanisms": mechanisms,
        "market_scope": {"exchange": "binance", "trading_mode": "futures", "baseline_pair": "BTC/USDT:USDT", "timeframe": "1h"},
        "data_scope": {"validation": False, "holdout": False, "sealed_development_only": True},
        "quality_checks": {"evidence_real": True, "verifiable": True, "budget_executable": True, "lower_risk_alternative_used": True},
    }
    proposal["research_question_fingerprint"] = fingerprint(normalized_question(question))
    proposal["semantic_fingerprint"] = proposal_fingerprint(proposal)
    return proposal


def rank(proposal: dict[str, Any], objective: str | None) -> float:
    information = float(proposal["expected_information_gain"]["score"])
    evidence_strength = min(1.0, len(proposal["supporting_evidence"]) / 3)
    relevance = 1.0 if not objective else (1.0 if any(token in proposal["research_question"].lower() for token in objective.lower().split()) else 0.7)
    feasibility = 1.0 if proposal["quality_checks"]["verifiable"] else 0.0
    risk_penalty = {"low": 0.0, "medium": 0.15, "high": 0.35, "forbidden": 1.0}[proposal["risk_class"]]
    cost_penalty = {"low": 0.0, "medium": 0.08, "high": 0.2}[proposal["estimated_compute_cost"]]
    contamination_penalty = {"none": 0.0, "low": 0.03, "medium": 0.1, "high": 0.25}[proposal["contamination_risk"]]
    return round(0.35 * information + 0.2 * evidence_strength + 0.2 * relevance + 0.15 * feasibility - 0.05 * risk_penalty - 0.03 * cost_penalty - 0.02 * contamination_penalty, 6)


def generate(state: dict[str, Any], constitution: dict[str, Any], objective: str | None, budget: dict[str, Any], risk_tolerance: str, max_proposals: int = 5) -> dict[str, Any]:
    if state.get("state_conflicts"):
        return {"recommendation": "no_research_recommended", "reason": "state_conflict", "proposals": [], "rejected_proposals": [], "state_fingerprint": state["state_fingerprint"]}
    runtime = {"path": "research/runtime/freqtrade-runtime.yaml", "sha256": next(item["sha256"] for item in state["runtime_contracts"] if item["path"].endswith("freqtrade-runtime.yaml"))}
    policy = {"path": state["evaluation_policy"]["path"], "sha256": state["evaluation_policy"]["file_sha256"], "approval_status": state["evaluation_policy"]["approval_status"]}
    development = next(item for item in state["datasets"] if item.get("dataset_id") == "futures-dev-btc-usdt-usdt-20240101-20240830-v2")
    proposals = [
        proposal_base(
            "cross-pair-data-readiness-audit-v1",
            "Cross-pair generalization data readiness audit",
            "Can the next cross-pair generalization campaign be frozen and validated without acquiring or inspecting Validation/Holdout data?",
            "Temporal consistency is established for BTC, while no sealed non-BTC strategy dataset is currently available.",
            [evidence("research/temporal/stage3e1-temporal-comparison.json", "Classification is temporally_consistent and recommendation is cross_pair_generalization."), evidence("research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml", "Sealed futures market metadata is available for pair eligibility checks."), evidence("research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml", "Current sealed strategy-ranking dataset is BTC-only.")],
            {"type": "read_only_data_scope_audit", "steps": ["derive pair eligibility from sealed metadata", "define frozen data requirements", "produce no-download provisioning decision"], "execution": "no_campaign_run"},
            (0.92, "high", "It resolves the explicit Stage 3E recommendation while preventing premature cross-pair execution."),
            "low", 3, 35,
            [{"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "manifest_only"}, {"dataset_id": "binance-usdm-futures-2025-8-demo", "access": "sealed_metadata_only"}],
            runtime, policy,
            ["research/director/compiled/**", "reports/audits/cross-pair-data-readiness/**"],
            ["pair-eligibility.json", "frozen-data-requirements.yaml", "readiness-decision.json"],
            ["data scope guard", "no network test", "no Validation/Holdout access test"],
            ["cross_pair_generalization", "data_provisioning"],
        ),
        proposal_base(
            "exit-logic-structure-audit-v1",
            "Exit logic structure and attribution audit",
            "Which existing exit mechanisms explain regime-specific loss concentration without changing strategy or risk semantics?",
            "Signal attribution found no exit deltas, while temporal slices show materially different loss and exit-reason distributions.",
            [evidence("research/analysis/stage3d3a-final-report.json", "Recorded exit_count is zero in prior signal-delta attribution."), evidence("research/temporal/stage3e1-temporal-comparison.json", "Temporal slices contain different exit-reason and risk distributions."), evidence("research/runtime/freqtrade-2025-8-signal-execution-contract.yaml", "Execution semantics are frozen and auditable.")],
            {"type": "read_only_exit_attribution", "steps": ["map existing exit reasons to temporal regimes", "audit first-trigger and time-stop semantics", "produce structural findings only"], "execution": "no_backtest"},
            (0.81, "high", "Existing evidence leaves exit-specific attribution unresolved and the audit requires no mutation."),
            "low", 4, 45,
            [{"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "existing_artifacts_only"}],
            runtime, policy,
            ["research/director/compiled/**", "research/analysis/exit-logic-audit/**"],
            ["exit-attribution.json", "exit-structure-audit.md"],
            ["determinism test", "no strategy diff test", "artifact hash test"],
            ["exit_logic", "first_trigger_semantics"],
        ),
        proposal_base(
            "regime-branch-structure-audit-v1",
            "Regime branch structure audit",
            "Are directionality and regime activation imbalances structural rather than addressable by another threshold search?",
            "The threshold branch is closed, but condition-graph and temporal directionality evidence can still support a read-only structural diagnosis.",
            [evidence("research/closures/regime-aware-ranging-thresholds-v1.yaml", "Single-threshold search is closed and may not be reopened."), evidence("research/analysis/regime-aware-condition-graph.json", "A machine-readable branch condition graph exists."), evidence("research/temporal/stage3e1-temporal-comparison.json", "Long/short coverage differs across temporal slices.")],
            {"type": "read_only_condition_graph_audit", "steps": ["compare branch activation by regime", "separate structural gaps from threshold-local effects", "emit no-mutation recommendation"], "execution": "no_backtest"},
            (0.73, "medium", "It distinguishes structural research from prohibited adjacent-threshold work."),
            "low", 3, 30,
            [{"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "existing_analysis_only"}],
            runtime, policy,
            ["research/director/compiled/**", "research/analysis/regime-branch-audit/**"],
            ["regime-branch-structure.json", "structural-vs-threshold-decision.md"],
            ["closed branch guard test", "condition graph integrity test"],
            ["regime_branch_structure"],
        ),
    ]
    if (state.get("eth_cross_pair_generalization") or {}).get("campaign_executed") is True:
        eth_dataset = next(
            item for item in state["datasets"]
            if item.get("dataset_id") == "futures-dev-eth-usdt-usdt-20240101-20240830-v1"
        )
        proposals.append(
            proposal_base(
                "strategy-family-reassessment-v1",
                "Strategy family reassessment evidence audit",
                "Does the combined BTC temporal evidence and reproducible ETH development result justify reassessing the current regime-aware strategy family before any new Candidate design?",
                "RegimeAwareV6 is temporally consistent on BTC and reproducible on ETH, but ETH development behavior is materially weaker and no approved evidence synthesis has tested whether the current family assumptions remain the best research direction.",
                [
                    evidence("research/temporal/stage3e1-temporal-comparison.json", "BTC behavior is temporally consistent across four frozen slices."),
                    evidence("research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "ETH execution behavior is reproducible but does not prove profitable or policy-qualified generalization."),
                    evidence("research/analysis/regime-branch-audit/regime-branch-structure.json", "Directionality rotates across slices and no current strategy mutation is warranted."),
                ],
                {
                    "type": "strategy_family_reassessment_read_only",
                    "steps": [
                        "build an evidence matrix for the current regime-aware family assumptions",
                        "compare retain, retire, and future-family research directions without implementing any family",
                        "produce a human-review decision packet with explicit no-execution boundaries",
                    ],
                    "execution": "no_backtest_no_candidate_no_strategy_change",
                },
                (0.88, "high", "It resolves whether future research should remain inside the current family before any higher-risk implementation work is authorized."),
                "medium", 3, 60,
                [
                    {"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "existing_analysis_only"},
                    {"dataset_id": eth_dataset["dataset_id"], "manifest_sha256": eth_dataset["manifest_sha256"], "access": "existing_analysis_only"},
                ],
                runtime, policy,
                ["research/director/compiled/strategy-family-reassessment-v1/**", "research/analysis/strategy-family-reassessment/**", "reports/audits/strategy-family-reassessment/**"],
                ["family-evidence-matrix.json", "strategy-family-reassessment-decision.md", "human-review-packet.json"],
                ["evidence traceability test", "no strategy or Candidate diff test", "no backtest or protected-data access test"],
                ["strategy_family_reassessment", "new_strategy_branch"],
            )
        )
    if (state.get("strategy_family_reassessment") or {}).get("decision") == "restructure_family_worth_studying":
        eth_dataset = next(item for item in state["datasets"] if item.get("dataset_id") == "futures-dev-eth-usdt-usdt-20240101-20240830-v1")
        proposals.append(
            proposal_base(
                "regime-conditioned-branch-factorization-v1",
                "Regime-conditioned branch factorization study",
                "Can one explicitly approved structural Candidate isolate shared regime routing from direction-specific entry branches and explain the BTC/ETH behavior gap without reopening closed threshold or exit research?",
                "The family reassessment identified one untested structural hypothesis with high information value, but no Candidate or comparative development evidence exists.",
                [
                    evidence("research/analysis/strategy-family-reassessment/family-evidence-matrix.json", "The evidence matrix identifies unresolved shared-router versus direction-branch contribution."),
                    evidence("research/analysis/strategy-family-reassessment/human-review-packet.json", "Human review packet selects branch factorization as the unique priority structural direction."),
                    evidence("research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "ETH behavior is reproducible but materially weaker than the BTC reference."),
                ],
                {
                    "type": "new_strategy_branch_single_structural_candidate",
                    "steps": ["design one branch-factorized Candidate", "run fresh-process development-only BTC and ETH comparisons", "attribute changes by regime and direction branch"],
                    "execution": "future_candidate_and_development_backtest_requires_human_approval",
                },
                (0.91, "high", "It directly tests the only unresolved structural mechanism while holding risk, thresholds, exits, Runtime and data fixed."),
                "medium", 3, 120,
                [
                    {"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "development_only_after_human_approval"},
                    {"dataset_id": eth_dataset["dataset_id"], "manifest_sha256": eth_dataset["manifest_sha256"], "access": "development_only_after_human_approval"},
                ],
                runtime, policy,
                ["new_strategy_branch", "new_candidate", "research/candidates/regime-conditioned-branch-factorization-v1/**", "research/analysis/regime-conditioned-branch-factorization/**", "reports/audits/regime-conditioned-branch-factorization/**"],
                ["candidate-manifest.yaml", "branch-attribution.json", "btc-eth-development-comparison.json", "human-decision-report.md"],
                ["single Candidate identity test", "fresh-process reproducibility test", "no threshold/exit/risk diff test", "no Validation/Holdout access test"],
                ["new_strategy_branch", "regime_router", "direction_specific_entry_branches"],
            )
        )
    threshold_check = branch_closure_check("ranging-threshold-neighbor-search", state)
    rejected = [
        {"proposal_key": "ranging-threshold-neighbor-search", "reason_code": threshold_check["reason_code"], "details": threshold_check},
        {"proposal_key": "repeat-temporal-generalization-profile", "reason_code": "duplicate_research_question", "details": {"existing_evidence": "research/temporal/stage3e1-temporal-comparison.json"}},
        {"proposal_key": "direct-cross-pair-backtest", "reason_code": "duplicate_research_question" if (state.get("eth_cross_pair_generalization") or {}).get("campaign_executed") else "insufficient_data", "details": {"completed_dataset": (state.get("eth_cross_pair_generalization") or {}).get("dataset_id"), "missing": None if (state.get("eth_cross_pair_generalization") or {}).get("campaign_executed") else "sealed non-BTC strategy dataset", "lower_risk_alternative": "cross-pair-data-readiness-audit-v1"}},
        {"proposal_key": "automatic-risk-parameter-search", "reason_code": "forbidden_by_constitution", "details": {"risk_out_of_scope": True}},
    ]
    if (state.get("stage4b1_execution") or {}).get("campaign_executed") is True:
        proposals = [item for item in proposals if item["proposal_id"] != "cross-pair-data-readiness-audit-v1"]
        rejected.append({"proposal_key": "cross-pair-data-readiness-audit-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-cross-pair-data-readiness-audit-v1", "result_code": (state.get("stage4b1_execution") or {}).get("result_code")}})
    if (state.get("exit_logic_structure_audit") or {}).get("campaign_executed") is True:
        proposals = [item for item in proposals if item["proposal_id"] != "exit-logic-structure-audit-v1"]
        rejected.append({"proposal_key": "exit-logic-structure-audit-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-exit-logic-structure-audit-v1", "result_code": (state.get("exit_logic_structure_audit") or {}).get("result_code")}})
    if (state.get("regime_branch_structure_audit") or {}).get("campaign_executed") is True:
        proposals = [item for item in proposals if item["proposal_id"] != "regime-branch-structure-audit-v1"]
        rejected.append({"proposal_key": "regime-branch-structure-audit-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-regime-branch-structure-audit-v1", "result_code": (state.get("regime_branch_structure_audit") or {}).get("result_code")}})
    if (state.get("eth_cross_pair_generalization") or {}).get("campaign_executed") is True:
        rejected.append({"proposal_key": "eth-cross-pair-generalization-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-eth-cross-pair-generalization-v1", "result_code": (state.get("eth_cross_pair_generalization") or {}).get("result_code")}})
    if (state.get("strategy_family_reassessment") or {}).get("campaign_executed") is True:
        proposals = [item for item in proposals if item["proposal_id"] != "strategy-family-reassessment-v1"]
        rejected.append({"proposal_key": "strategy-family-reassessment-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-strategy-family-reassessment-v1", "result_code": (state.get("strategy_family_reassessment") or {}).get("decision")}})
    max_experiments = min(int(budget.get("max_experiments", 20)), int(constitution["budget_limits"]["max_experiments"]))
    proposals = [item for item in proposals if item["estimated_experiments"] <= max_experiments]
    if risk_tolerance == "low":
        proposals = [item for item in proposals if item["risk_class"] == "low"]
    for item in proposals:
        item["ranking_score"] = rank(item, objective)
        item["approval_route_preview"] = route_proposal(item, constitution)["decision"]
    proposals.sort(key=lambda item: (-item["ranking_score"], item["semantic_fingerprint"], item["proposal_id"]))
    proposals = proposals[:max_proposals]
    recommendation = "research_recommended" if proposals else "no_research_recommended"
    run = {
        "schema_version": "research-director-run-v1",
        "run_id": f"director-run-{fingerprint({'state': state['state_fingerprint'], 'objective': objective, 'budget': budget, 'risk': risk_tolerance})[:16]}",
        "created_at": utc_now(),
        "state_fingerprint": state["state_fingerprint"],
        "constitution_status": constitution.get("status"),
        "objective": objective,
        "budget": budget,
        "risk_tolerance": risk_tolerance,
        "recommendation": recommendation,
        "recommendation_reason": "ranked evidence-based proposals available" if proposals else "no proposal passed closure, duplication, data, risk and information-gain gates",
        "proposals": proposals,
        "rejected_proposals": rejected,
        "ranking_factors": ["expected_information_gain", "evidence_strength", "objective_relevance", "validation_feasibility", "risk", "cost", "contamination_risk", "duplication_penalty"],
        "model_preference_used": False,
        "execution_authorized": False,
    }
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="research/director/current-research-state.json")
    parser.add_argument("--constitution", default="research/governance/research-constitution.yaml")
    parser.add_argument("--objective")
    parser.add_argument("--budget", default='{"max_campaigns": 1, "max_experiments": 20, "max_wall_clock_minutes": 120, "max_validation_accesses": 0}')
    parser.add_argument("--risk-tolerance", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--max-proposals", type=int, default=5)
    parser.add_argument("--output", default="research/director/proposals/director-run.json")
    parser.add_argument("--director-registry")
    args = parser.parse_args(argv)
    state = load_document(args.state)
    constitution = load_document(args.constitution)
    budget = json.loads(args.budget)
    run = generate(state, constitution, args.objective, budget, args.risk_tolerance, args.max_proposals)
    write_json(args.output, run)
    proposal_dir = Path(args.output).parent
    for proposal in run["proposals"]:
        write_json(proposal_dir / f"{proposal['proposal_id']}.json", proposal)
        write_yaml(proposal_dir / f"{proposal['proposal_id']}.yaml", proposal)
    if args.director_registry:
        connection = open_director_registry(args.director_registry)
        connection.execute(
            "INSERT OR REPLACE INTO director_runs(run_id, state_fingerprint, objective, risk_tolerance, budget_json, recommendation, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run["run_id"], run["state_fingerprint"], run["objective"], run["risk_tolerance"], json.dumps(run["budget"], sort_keys=True), run["recommendation"], json.dumps(run, sort_keys=True), run["created_at"]),
        )
        for proposal in run["proposals"]:
            connection.execute(
                "INSERT OR REPLACE INTO director_proposals(proposal_id, run_id, semantic_fingerprint, risk_class, information_gain, status, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (proposal["proposal_id"], run["run_id"], proposal["semantic_fingerprint"], proposal["risk_class"], proposal["expected_information_gain"]["score"], "proposed_unapproved", json.dumps(proposal, sort_keys=True), run["created_at"]),
            )
        connection.execute("DELETE FROM director_rejections WHERE run_id=?", (run["run_id"],))
        for rejection in run["rejected_proposals"]:
            connection.execute(
                "INSERT INTO director_rejections(run_id, proposal_key, reason_code, details_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (run["run_id"], rejection["proposal_key"], rejection["reason_code"], json.dumps(rejection["details"], sort_keys=True), run["created_at"]),
            )
        connection.commit()
        connection.close()
    print(json.dumps({"run_id": run["run_id"], "recommendation": run["recommendation"], "proposal_count": len(run["proposals"]), "rejected_count": len(run["rejected_proposals"]), "output": args.output}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
