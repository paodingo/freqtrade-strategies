#!/usr/bin/env python3
"""Route a Research Proposal through Constitution rules without approving it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_director_common import fingerprint, load_document, open_director_registry, sha256_file, utc_now, write_json


HIGH_RISK_TERMS = {
    "leverage", "stake", "stoploss", "roi", "protections", "position_stacking",
    "position_adjustment", "holdout", "forward_dry_run", "champion_promotion", "live_trading",
}
FORBIDDEN_TERMS = {
    "private_api", "secret_access", "gate_bypass", "validation_feedback_mutation",
    "approved_policy_change", "sealed_artifact_change", "automatic_closed_branch_reopen",
}
MEDIUM_RISK_TERMS = {
    "new_pair", "new_timeframe", "new_dataset", "new_search_space", "new_strategy_branch",
    "limited_multivariable", "strategy_structure", "bounded_hyperopt",
}

L1_CONTRACT_SCHEMA = "low-risk-development-descriptive-execution-contract-v1"
L1_AUTHORIZATION_MODE = "standing_l1_development_descriptive_contract"


def flattened_terms(proposal: dict[str, Any]) -> set[str]:
    """Return only positively requested scope, never prohibitions or denial text."""
    values = []
    for key in ("allowed_changes", "referenced_variables", "referenced_mechanisms"):
        values.extend(str(item).lower() for item in proposal.get(key) or [])
    method = proposal.get("proposed_method") or {}
    values.extend(str(method.get(key, "")).lower() for key in ("type", "execution"))
    return set(values)


def contains_term(values: set[str], terms: set[str]) -> list[str]:
    return sorted(term for term in terms if any(term in value for value in values))


def low_risk_descriptive_contract_check(
    proposal: dict[str, Any],
    constitution: dict[str, Any],
    contract: dict[str, Any] | None,
    contract_approval: dict[str, Any] | None = None,
    *,
    constitution_sha256: str | None = None,
    contract_sha256: str | None = None,
) -> dict[str, Any]:
    proposal_id = str(proposal.get("proposal_id", ""))
    expected_artifacts = [
        f"research/analysis/{proposal_id}/analysis.json",
        f"reports/audits/{proposal_id}/report.md",
    ]
    eligibility = (contract or {}).get("eligibility") or {}
    authority = (contract or {}).get("authority") or {}
    semantics = (contract or {}).get("execution_semantics") or {}
    required_prohibitions = set((contract or {}).get("prohibited_actions") or [])
    declared_prohibitions = set(proposal.get("forbidden_changes") or [])
    datasets = proposal.get("required_datasets") or []
    data_scope = proposal.get("data_scope") or {}
    checks = {
        "contract_active": bool(
            contract
            and contract.get("schema_version") == L1_CONTRACT_SCHEMA
            and contract.get("status") == "active"
        ),
        "contract_human_approval": bool(
            contract
            and contract_approval
            and contract_approval.get("approval_status") == "approved"
            and contract_approval.get("approver_type") == "human_user"
            and contract_approval.get("approval_id") == contract.get("contract_id")
            and contract_approval.get("approved_contract_path")
            == "research/governance/low-risk-development-descriptive-execution-contract-v1.json"
            and contract_approval.get("approved_contract_sha256") == contract_sha256
            and contract_approval.get("campaign_execution_authorized") is False
            and contract_approval.get("trading_execution_authorized") is False
            and contract_approval.get("strategy_mutation_authorized") is False
            and contract_approval.get("candidate_creation_authorized") is False
            and contract_approval.get("validation_accesses_authorized") == 0
            and contract_approval.get("holdout_accesses_authorized") == 0
            and contract_approval.get("silent_contract_amendment_allowed") is False
        ),
        "constitution_binding": bool(
            contract
            and constitution_sha256
            and authority.get("constitution_id") == constitution.get("constitution_id")
            and authority.get("approved_version") == constitution.get("approved_version")
            and authority.get("approved_constitution_sha256") == constitution_sha256
        ),
        "constitution_auto_authority": bool(
            constitution.get("approval_status") == "approved"
            and constitution.get("approver_type") == "human_user"
            and (constitution.get("approval") or {}).get("low_risk_auto_approval") is True
            and (constitution.get("approval") or {}).get("low_risk_auto_execution") is True
        ),
        "risk_and_budget": bool(
            proposal.get("risk_class") == eligibility.get("risk_class") == "low"
            and proposal.get("estimated_experiments") == eligibility.get("estimated_experiments") == 0
            and proposal.get("estimated_compute_cost") == eligibility.get("estimated_compute_cost") == "low"
            and proposal.get("contamination_risk") == eligibility.get("contamination_risk") == "none"
            and isinstance(proposal.get("estimated_wall_clock_minutes"), int)
            and proposal["estimated_wall_clock_minutes"]
            <= int(eligibility.get("max_wall_clock_minutes", -1))
        ),
        "development_only_data": bool(
            datasets
            and all(
                isinstance(item, dict)
                and item.get("access") == eligibility.get("required_dataset_access") == "development_only"
                and isinstance(item.get("manifest_sha256"), str)
                and len(item["manifest_sha256"]) == 64
                and "validation" not in str(item.get("manifest_path", "")).lower()
                and "holdout" not in str(item.get("manifest_path", "")).lower()
                for item in datasets
            )
            and data_scope.get("sealed_development_only") is eligibility.get("sealed_development_only") is True
            and data_scope.get("validation") is False
            and data_scope.get("holdout") is False
            and proposal.get("validation_requirement") == eligibility.get("validation_requirement") == "none"
            and proposal.get("holdout_requirement") == eligibility.get("holdout_requirement") == "none"
        ),
        "exact_artifacts": bool(
            proposal.get("allowed_changes") == expected_artifacts
            and proposal.get("required_artifacts") == expected_artifacts
            and ((contract or {}).get("artifact_contract") or {}).get("exact_paths_only") is True
            and ((contract or {}).get("artifact_contract") or {}).get(
                "allowed_changes_must_equal_required_artifacts"
            )
            is True
        ),
        "prohibitions_complete": bool(required_prohibitions and required_prohibitions <= declared_prohibitions),
        "non_campaign_semantics": bool(
            semantics.get("descriptive_execution_authorized") is True
            and semantics.get("campaign_execution_authorized") is False
            and semantics.get("trading_execution_authorized") is False
            and semantics.get("strategy_mutation_authorized") is False
        ),
        "closure_and_duplicate_clear": bool(
            (proposal.get("branch_closure_reopen_check") or {}).get("checked") is True
            and (proposal.get("branch_closure_reopen_check") or {}).get("blocked") is False
            and (proposal.get("duplicate_research_check") or {}).get("checked") is True
            and (proposal.get("duplicate_research_check") or {}).get("duplicate") is False
        ),
    }
    eligible = all(checks.values())
    return {
        "eligible": eligible,
        "checks": checks,
        "contract_id": (contract or {}).get("contract_id"),
        "contract_sha256": contract_sha256,
        "exact_artifact_paths": expected_artifacts if eligible else [],
        "authorization_mode": L1_AUTHORIZATION_MODE if eligible else None,
    }


def route_proposal(
    proposal: dict[str, Any],
    constitution: dict[str, Any],
    human_selection: dict[str, Any] | None = None,
    low_risk_contract: dict[str, Any] | None = None,
    low_risk_contract_approval: dict[str, Any] | None = None,
    *,
    constitution_sha256: str | None = None,
    contract_sha256: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    required = ["proposal_id", "risk_class", "required_datasets", "required_runtime", "required_policy"]
    missing = [key for key in required if key not in proposal]
    rules.append({"rule": "required_information", "passed": not missing, "details": {"missing": missing}})
    if missing:
        decision = "insufficient_information"
    else:
        terms = flattened_terms(proposal)
        forbidden_hits = contains_term(terms, FORBIDDEN_TERMS)
        high_hits = contains_term(terms, HIGH_RISK_TERMS)
        medium_hits = contains_term(terms, MEDIUM_RISK_TERMS)
        closure = proposal.get("branch_closure_reopen_check") or {}
        constitution_approved = constitution.get("approval_status") == "approved" and constitution.get("approver_type") == "human_user"
        selection_matched = bool(
            human_selection
            and human_selection.get("approval_status") == "approved"
            and human_selection.get("approver_type") == "human_user"
            and human_selection.get("proposal_id") == proposal.get("proposal_id")
            and human_selection.get("only_selected_proposal") is True
        )
        l1_contract = low_risk_descriptive_contract_check(
            proposal,
            constitution,
            low_risk_contract,
            low_risk_contract_approval,
            constitution_sha256=constitution_sha256,
            contract_sha256=contract_sha256,
        )
        rules.extend([
            {"rule": "constitution_approval", "passed": constitution_approved or constitution.get("status") == "pending_human_review", "details": {"status": constitution.get("status"), "approval_status": constitution.get("approval_status"), "approver_type": constitution.get("approver_type")}},
            {"rule": "human_proposal_selection", "passed": selection_matched if human_selection else True, "details": {"selection_supplied": human_selection is not None, "matched": selection_matched}},
            {"rule": "forbidden_scope", "passed": not forbidden_hits and proposal.get("risk_class") != "forbidden", "details": {"hits": forbidden_hits}},
            {"rule": "closed_branch", "passed": not closure.get("blocked", False), "details": closure},
            {"rule": "holdout_default_forbidden", "passed": proposal.get("holdout_requirement") == "none", "details": {"requirement": proposal.get("holdout_requirement")}},
            {"rule": "risk_execution_boundary", "passed": True, "details": {"stage4a_auto_execution": False, "low_risk_auto_execution": bool((constitution.get("approval") or {}).get("low_risk_auto_execution"))}},
            {"rule": "risk_evidence", "passed": True, "details": {"declared": proposal.get("risk_class"), "high_hits": high_hits, "medium_hits": medium_hits}},
            {"rule": "standing_l1_development_descriptive_contract", "passed": l1_contract["eligible"], "details": l1_contract},
        ])
        if forbidden_hits or proposal.get("risk_class") == "forbidden" or closure.get("blocked"):
            decision = "forbidden"
        elif proposal.get("risk_class") in {"medium", "high"} or high_hits or medium_hits:
            decision = "human_approval_required"
        elif proposal.get("risk_class") == "low":
            if l1_contract["eligible"]:
                decision = "auto_approved_under_constitution"
            elif constitution_approved and selection_matched and (constitution.get("approval") or {}).get("low_risk_auto_approval") is True:
                if str((human_selection or {}).get("selection_mode", "")).startswith("auto_selected_under_human_approved_stage4c1"):
                    decision = "auto_approved_under_stage4c1_portfolio"
                else:
                    decision = "auto_approved_under_constitution"
            else:
                decision = "auto_approvable_future"
        else:
            decision = "insufficient_information"
    approval_granted = decision in {"auto_approved_under_constitution", "auto_approved_under_stage4c1_portfolio"}
    l1_details = next(
        (
            item["details"]
            for item in rules
            if item.get("rule") == "standing_l1_development_descriptive_contract"
        ),
        {"eligible": False, "exact_artifact_paths": [], "authorization_mode": None},
    )
    descriptive_authorized = bool(approval_granted and l1_details.get("eligible"))
    authorization = {
        "authorization_mode": l1_details.get("authorization_mode") if descriptive_authorized else None,
        "contract_id": l1_details.get("contract_id") if descriptive_authorized else None,
        "contract_sha256": l1_details.get("contract_sha256") if descriptive_authorized else None,
        "exact_artifact_paths": l1_details.get("exact_artifact_paths") if descriptive_authorized else [],
        "descriptive_execution_authorized": descriptive_authorized,
        "campaign_execution_authorized": False,
        "trading_execution_authorized": False,
        "strategy_mutation_authorized": False,
    }
    authorization["authorization_fingerprint"] = fingerprint(authorization)
    payload = {
        "schema_version": "research-approval-route-v1",
        "route_id": f"route-{proposal.get('proposal_id', 'unknown')}-{fingerprint(rules)[:12]}",
        "proposal_id": proposal.get("proposal_id"),
        "decision": decision,
        "approval_granted": approval_granted,
        "stage4a_execution_authorized": False,
        "execution_authorized_under_constitution": approval_granted and not descriptive_authorized,
        "descriptive_execution_authorized_under_contract": descriptive_authorized,
        "authorization": authorization,
        "rule_decisions": rules,
        "created_at": created_at or utc_now(),
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--constitution", default="research/governance/research-constitution.yaml")
    parser.add_argument("--output")
    parser.add_argument("--director-registry")
    parser.add_argument("--human-selection")
    parser.add_argument("--low-risk-contract")
    parser.add_argument("--low-risk-contract-approval")
    args = parser.parse_args(argv)
    proposal = load_document(args.proposal)
    constitution = load_document(args.constitution)
    human_selection = load_document(args.human_selection) if args.human_selection else None
    low_risk_contract = load_document(args.low_risk_contract) if args.low_risk_contract else None
    low_risk_contract_approval = (
        load_document(args.low_risk_contract_approval)
        if args.low_risk_contract_approval
        else None
    )
    route = route_proposal(
        proposal,
        constitution,
        human_selection,
        low_risk_contract,
        low_risk_contract_approval,
        constitution_sha256=sha256_file(args.constitution),
        contract_sha256=sha256_file(args.low_risk_contract) if args.low_risk_contract else None,
    )
    output = args.output or f"research/director/approvals/{proposal.get('proposal_id', 'unknown')}.json"
    write_json(output, route)
    if args.director_registry:
        connection = open_director_registry(args.director_registry)
        connection.execute(
            "INSERT OR REPLACE INTO approval_routes(route_id, proposal_id, decision, rules_json, approval_granted, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (route["route_id"], route["proposal_id"], route["decision"], json.dumps(route["rule_decisions"], sort_keys=True), int(route["approval_granted"]), route["created_at"]),
        )
        connection.commit()
        connection.close()
    print(json.dumps(route, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
