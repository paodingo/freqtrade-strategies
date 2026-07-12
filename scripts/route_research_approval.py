#!/usr/bin/env python3
"""Route a Research Proposal through Constitution rules without approving it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_director_common import fingerprint, load_document, open_director_registry, utc_now, write_json


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


def route_proposal(
    proposal: dict[str, Any],
    constitution: dict[str, Any],
    human_selection: dict[str, Any] | None = None,
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
        rules.extend([
            {"rule": "constitution_approval", "passed": constitution_approved or constitution.get("status") == "pending_human_review", "details": {"status": constitution.get("status"), "approval_status": constitution.get("approval_status"), "approver_type": constitution.get("approver_type")}},
            {"rule": "human_proposal_selection", "passed": selection_matched if human_selection else True, "details": {"selection_supplied": human_selection is not None, "matched": selection_matched}},
            {"rule": "forbidden_scope", "passed": not forbidden_hits and proposal.get("risk_class") != "forbidden", "details": {"hits": forbidden_hits}},
            {"rule": "closed_branch", "passed": not closure.get("blocked", False), "details": closure},
            {"rule": "holdout_default_forbidden", "passed": proposal.get("holdout_requirement") == "none", "details": {"requirement": proposal.get("holdout_requirement")}},
            {"rule": "risk_execution_boundary", "passed": True, "details": {"stage4a_auto_execution": False, "low_risk_auto_execution": bool((constitution.get("approval") or {}).get("low_risk_auto_execution"))}},
            {"rule": "risk_evidence", "passed": True, "details": {"declared": proposal.get("risk_class"), "high_hits": high_hits, "medium_hits": medium_hits}},
        ])
        if forbidden_hits or proposal.get("risk_class") == "forbidden" or closure.get("blocked"):
            decision = "forbidden"
        elif proposal.get("risk_class") in {"medium", "high"} or high_hits or medium_hits:
            decision = "human_approval_required"
        elif proposal.get("risk_class") == "low":
            if constitution_approved and selection_matched and (constitution.get("approval") or {}).get("low_risk_auto_approval") is True:
                if str((human_selection or {}).get("selection_mode", "")).startswith("auto_selected_under_human_approved_stage4c1"):
                    decision = "auto_approved_under_stage4c1_portfolio"
                else:
                    decision = "auto_approved_under_constitution"
            else:
                decision = "auto_approvable_future"
        else:
            decision = "insufficient_information"
    approval_granted = decision in {"auto_approved_under_constitution", "auto_approved_under_stage4c1_portfolio"}
    payload = {
        "schema_version": "research-approval-route-v1",
        "route_id": f"route-{proposal.get('proposal_id', 'unknown')}-{fingerprint(rules)[:12]}",
        "proposal_id": proposal.get("proposal_id"),
        "decision": decision,
        "approval_granted": approval_granted,
        "stage4a_execution_authorized": False,
        "execution_authorized_under_constitution": approval_granted,
        "rule_decisions": rules,
        "created_at": utc_now(),
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--constitution", default="research/governance/research-constitution.yaml")
    parser.add_argument("--output")
    parser.add_argument("--director-registry")
    parser.add_argument("--human-selection")
    args = parser.parse_args(argv)
    proposal = load_document(args.proposal)
    constitution = load_document(args.constitution)
    human_selection = load_document(args.human_selection) if args.human_selection else None
    route = route_proposal(proposal, constitution, human_selection)
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
