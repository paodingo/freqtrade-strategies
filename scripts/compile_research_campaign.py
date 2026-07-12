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


def verify_evidence(repo: Path, proposal: dict[str, Any]) -> list[dict[str, Any]]:
    checked = []
    for item in proposal.get("supporting_evidence") or []:
        path = repo / item["path"]
        if not path.is_file():
            raise ValueError(f"proposal evidence missing: {item['path']}")
        checked.append({"path": item["path"], "sha256": sha256_file(path), "claim": item["claim"]})
    return checked


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
    queue = [
        {
            "experiment_id": f"{proposal['proposal_id']}-e{index:03d}",
            "priority": index,
            "status": "queued_unexecuted",
            "runner": "dry_run_read_only_audit",
            "action": step,
            "guard_paths": proposal["allowed_changes"],
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
    campaign: dict[str, Any] = {
        "schema_version": "compiled-research-campaign-v1",
        "campaign_id": f"stage4a-{proposal['proposal_id']}",
        "proposal_id": proposal["proposal_id"],
        "proposal_fingerprint": proposal["semantic_fingerprint"],
        "compile_mode": "dry_run",
        "mode": "dry_run",
        "runner_type": "dry_run_read_only_audit",
        "execution_authorized": False,
        "approval_route": route["decision"],
        "approval_granted": False,
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
