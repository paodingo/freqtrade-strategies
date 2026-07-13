#!/usr/bin/env python3
"""Compile one non-forbidden Research Proposal into a dry-run Campaign Spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_control import load_campaign
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    utc_now,
    write_json,
    write_yaml,
)
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
    steps = proposal.get("proposed_method", {}).get("steps") or ["perform evidence-linked read-only audit"]
    if structural_plan:
        steps = [
            "create exactly one router-extraction Candidate after new human execution approval",
            "run the BTC baseline/Candidate equivalence pack in distinct fresh processes",
            "run the ETH baseline/Candidate equivalence pack in distinct fresh processes",
        ]
    queue = [
        {
            "experiment_id": f"{proposal['proposal_id']}-e{index:03d}",
            "priority": index,
            "status": "queued_unexecuted",
            "runner": "future_candidate_equivalence_step" if structural_plan else "dry_run_read_only_audit",
            "action": step,
            "guard_paths": proposal["allowed_changes"],
            "execution_authorized": False,
            "requires_new_human_execution_approval": bool(structural_plan),
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
    campaign: dict[str, Any] = {
        "schema_version": "compiled-research-campaign-v1",
        "campaign_id": f"stage4a-{proposal['proposal_id']}",
        "proposal_id": proposal["proposal_id"],
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "compile_mode": "dry_run",
        "mode": "dry_run",
        "runner_type": "frozen_candidate_equivalence_plan" if structural_plan else "dry_run_read_only_audit",
        "execution_authorized": False,
        "approval_route": route["decision"],
        "approval_granted": False,
        "risk_class": proposal["risk_class"],
        "current_authority": "compile_and_review_only" if structural_plan else "dry_run_only",
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
    queue = "\n".join(f"{index}. `{item['action']}`" for index, item in enumerate(campaign["experiment_queue"], start=1))
    structural = campaign.get("structural_research_plan")
    if structural:
        hypothesis = structural["minimum_testable_hypothesis"]
        return f"""# Implementation Brief: {proposal['title']}

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
    return f"""# Implementation Brief: {proposal['title']}

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
