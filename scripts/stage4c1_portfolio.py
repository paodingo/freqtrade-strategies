#!/usr/bin/env python3
"""Deterministic selector and stop gate for the approved Stage 4C.1 portfolio."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_director_common import load_document, open_director_registry, sha256_file, utc_now, write_json


PORTFOLIO_ID = "stage4c1-low-risk-autonomous-portfolio"


def validate_portfolio_approval(repo: Path, approval: dict[str, Any]) -> dict[str, Any]:
    constitution = repo / "research/governance/research-constitution.yaml"
    budget = approval.get("portfolio_budget") or {}
    autonomy = approval.get("autonomy") or {}
    checks = {
        "approved": approval.get("approval_status") == "approved" and approval.get("approver_type") == "human_user",
        "constitution_hash": sha256_file(constitution) == approval.get("constitution_sha256"),
        "max_campaigns": budget.get("max_campaigns") == 2,
        "zero_validation": budget.get("max_validation_accesses") == 0,
        "zero_holdout": budget.get("max_holdout_accesses") == 0,
        "failure_limit": budget.get("max_consecutive_infrastructure_failures") == 2,
        "low_risk_autonomy": all(autonomy.get(key) is True for key in ("auto_select_low_risk_proposals", "auto_approve_low_risk_proposals", "auto_compile_campaigns", "auto_execute_compiled_campaigns", "update_research_state_after_each_campaign")),
        "no_risk_expansion": approval.get("risk_or_scope_expansion_allowed") is False,
    }
    return {"checks": checks, "passed": all(checks.values())}


def eligible_proposals(director_run: dict[str, Any], executed_proposal_ids: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = []
    excluded = []
    executed = set(executed_proposal_ids)
    for proposal in director_run.get("proposals") or []:
        reasons = []
        if proposal.get("proposal_id") in executed:
            reasons.append("duplicate_research_question")
        if proposal.get("risk_class") != "low":
            reasons.append("human_approval_required_for_risk")
        if proposal.get("approval_route_preview") != "auto_approvable_future":
            reasons.append("approval_route_not_auto_approvable_future")
        if (proposal.get("branch_closure_reopen_check") or {}).get("blocked"):
            reasons.append("closed_branch_no_reopen_evidence")
        if (proposal.get("duplicate_research_check") or {}).get("duplicate"):
            reasons.append("duplicate_research_question")
        if proposal.get("validation_requirement") != "none" or proposal.get("holdout_requirement") != "none":
            reasons.append("forbidden_data_access_required")
        quality = proposal.get("quality_checks") or {}
        if not all(quality.get(key) is True for key in ("evidence_real", "verifiable", "budget_executable", "lower_risk_alternative_used")):
            reasons.append("proposal_quality_gate_failed")
        if reasons:
            excluded.append({"proposal_id": proposal.get("proposal_id"), "reason_codes": sorted(set(reasons))})
        else:
            eligible.append(proposal)
    return eligible, excluded


def portfolio_decision(approval: dict[str, Any], director_run: dict[str, Any], executed_proposal_ids: list[str], infrastructure_failures: int = 0) -> dict[str, Any]:
    budget = approval["portfolio_budget"]
    if len(executed_proposal_ids) >= budget["max_campaigns"]:
        return {"action": "stop", "stop_reason": "portfolio_max_campaigns_reached", "selected_proposal_id": None, "eligible": [], "excluded": []}
    if infrastructure_failures >= budget["max_consecutive_infrastructure_failures"]:
        return {"action": "stop", "stop_reason": "max_consecutive_infrastructure_failures_reached", "selected_proposal_id": None, "eligible": [], "excluded": []}
    eligible, excluded = eligible_proposals(director_run, executed_proposal_ids)
    if not eligible:
        return {"action": "stop", "stop_reason": "no_eligible_low_risk_proposal", "selected_proposal_id": None, "eligible": [], "excluded": excluded}
    return {"action": "execute", "stop_reason": None, "selected_proposal_id": eligible[0]["proposal_id"], "eligible": [item["proposal_id"] for item in eligible], "excluded": excluded}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", default="research/governance/approvals/stage4c1-portfolio-approval.json")
    parser.add_argument("--director-run", required=True)
    parser.add_argument("--executed", action="append", default=[])
    parser.add_argument("--infrastructure-failures", type=int, default=0)
    parser.add_argument("--output", required=True)
    parser.add_argument("--registry")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    approval = load_document(repo / args.approval)
    validation = validate_portfolio_approval(repo, approval)
    if not validation["passed"]:
        raise SystemExit("stage4c1_portfolio_approval_invalid")
    decision = portfolio_decision(approval, load_document(repo / args.director_run), args.executed, args.infrastructure_failures)
    payload = {"schema_version": "stage4c1-portfolio-decision-v1", "portfolio_id": PORTFOLIO_ID, "approval_validation": validation, "executed_proposal_ids": args.executed, **decision}
    write_json(repo / args.output, payload)
    if args.registry:
        connection = open_director_registry(repo / args.registry)
        connection.execute(
            "INSERT OR REPLACE INTO stage4c1_portfolios(portfolio_id, approval_status, max_campaigns, executed_campaigns, stop_reason, payload_json, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (PORTFOLIO_ID, "completed" if decision["action"] == "stop" else "active", approval["portfolio_budget"]["max_campaigns"], len(args.executed), decision["stop_reason"], json.dumps(payload, sort_keys=True), utc_now()),
        )
        connection.commit()
        connection.close()
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
