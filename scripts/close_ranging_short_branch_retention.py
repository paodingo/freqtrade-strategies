#!/usr/bin/env python3
"""Record the human-approved ranging-short retention decision without execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from export_director_registry import export_registry
from protected_manifest_hash import checkout_stable_text_sha256_matches
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    proposal_fingerprint,
    sha256_file,
    utc_now,
    write_json,
)


PROPOSAL_ID = "ranging-short-branch-retention-review-v1"
PROPOSAL_FINGERPRINT = "5adaa2d58c0703fb049a28d0bed6387b6801366d20aa0fb90472070e20e71a0e"
DECISION = "retain_current_branch"
CLOSURE_STATUS = "closed_mixed_temporal_dependency"
PROPOSAL = Path("research/director/next-after-ranging-short-temporal/proposals/ranging-short-branch-retention-review-v1.json")
TEMPORAL_RESULT = Path("research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json")
APPROVAL = Path("research/governance/approvals/ranging-short-branch-retention-review-v1-approval.json")
CLOSURE = Path("research/closures/ranging-short-branch-retention-review-v1.json")
FINAL_JSON = Path("reports/closures/ranging-short-branch-retention-review-v1-final-report.json")
FINAL_MD = Path("reports/closures/ranging-short-branch-retention-review-v1-final-report.md")
STATE = Path("research/director/current-research-state.json")
REGISTRY = Path("research/registry/stage4a-director.db")
REGISTRY_EXPORT = Path("research/director/registry-records.json")
STRATEGY = Path("strategies/RegimeAwareV6.py")
CANDIDATE = Path("research/candidates/branch-contribution-ablation-v1/1/RegimeAware_Ablation_RangingShort_C1.py")
CANDIDATE_MANIFEST = Path("research/candidates/branch-contribution-ablation-v1/1/candidate-manifest.json")
RUN_ID = "ranging-short-branch-retention-review-v1-closure"
SLICE_CONCLUSIONS = {
    "s01": "inconclusive",
    "s02": "positive_contributor",
    "s03": "negative_contributor",
    "s04": "negative_contributor",
}
SOURCE_SLICE_CLASSIFICATIONS = {
    "ranging-short-ablation-s01": "branch_contribution_inconclusive",
    "ranging-short-ablation-s02": "branch_positive_contributor",
    "ranging-short-ablation-s03": "branch_negative_contributor",
    "ranging-short-ablation-s04": "branch_negative_contributor",
}
REOPEN_CONDITIONS = [
    "new_human_approved_regime_conditioned_routing_research_only",
]
INSUFFICIENT_REOPEN_REASONS = [
    "adjacent_thresholds",
    "additional_temporal_slices",
    "poor_or_disappointing_results",
    "development_only_negative_contribution",
    "llm_hunch",
]


class RetentionClosureError(RuntimeError):
    pass


def self_fingerprint(payload: dict[str, Any], field: str) -> str:
    return fingerprint({key: value for key, value in payload.items() if key != field})


def validate_evidence(repo: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    proposal = load_document(repo / PROPOSAL)
    temporal = load_document(repo / TEMPORAL_RESULT)
    candidate_manifest = load_document(repo / CANDIDATE_MANIFEST)
    if proposal.get("proposal_id") != PROPOSAL_ID:
        raise RetentionClosureError("proposal_id_mismatch")
    if proposal.get("semantic_fingerprint") != PROPOSAL_FINGERPRINT:
        raise RetentionClosureError("proposal_fingerprint_mismatch")
    if proposal_fingerprint(proposal) != PROPOSAL_FINGERPRINT:
        raise RetentionClosureError("proposal_semantic_fingerprint_mismatch")
    if proposal.get("status") != "pending_human_review" or proposal.get("risk_class") != "medium":
        raise RetentionClosureError("proposal_not_pending_medium_risk_review")
    if temporal.get("status") != "completed" or temporal.get("classification") != "branch_mixed_temporal_dependency":
        raise RetentionClosureError("temporal_conclusion_mismatch")
    if temporal.get("backtest_calls") != 16 or temporal.get("validation_accesses") != 0 or temporal.get("holdout_accesses") != 0:
        raise RetentionClosureError("temporal_evidence_scope_mismatch")
    actual = {key: value.get("classification") for key, value in temporal.get("slice_results", {}).items()}
    if actual != SOURCE_SLICE_CLASSIFICATIONS:
        raise RetentionClosureError("slice_conclusion_mismatch")
    if not checkout_stable_text_sha256_matches(
        repo / STRATEGY, candidate_manifest.get("formal_strategy_sha256", "")
    ):
        raise RetentionClosureError("formal_strategy_hash_drift")
    if not checkout_stable_text_sha256_matches(
        repo / CANDIDATE, candidate_manifest.get("source_sha256", "")
    ):
        raise RetentionClosureError("candidate_hash_drift")
    return proposal, temporal, candidate_manifest


def build_approval(completed_at: str) -> dict[str, Any]:
    payload = {
        "schema_version": "ranging-short-branch-retention-approval-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "decision": DECISION,
        "approval_status": "approved",
        "approver_type": "human_user",
        "approved_at": completed_at,
        "authorization": {
            "code_change_authorized": False,
            "candidate_creation_authorized": False,
            "additional_backtests_authorized": False,
            "validation_authorized": False,
            "holdout_authorized": False,
        },
        "approval_fingerprint": "",
    }
    payload["approval_fingerprint"] = self_fingerprint(payload, "approval_fingerprint")
    return payload


def build_closure(repo: Path, completed_at: str, candidate_manifest: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": "ranging-short-branch-retention-closure-v1",
        "closure_id": PROPOSAL_ID,
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "status": CLOSURE_STATUS,
        "research_status": CLOSURE_STATUS,
        "decision": DECISION,
        "formal_branch": "ranging_short_entry",
        "formal_branch_action": "retained_unchanged",
        "research_direction": "whole_branch_deletion",
        "temporal_classification": "branch_mixed_temporal_dependency",
        "temporally_stable_deletion_evidence": False,
        "slice_conclusions": SLICE_CONCLUSIONS,
        "evidence_scope": {
            "development_only": True,
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "forward_dry_run": False,
        },
        "future_evidence_reference": {
            "allowed_only_for": "new_human_approved_regime_conditioned_routing_research",
            "automatic_reopen_allowed": False,
        },
        "reopen_conditions": REOPEN_CONDITIONS,
        "insufficient_reopen_reasons": INSUFFICIENT_REOPEN_REASONS,
        "protected_identity": {
            "formal_strategy_path": STRATEGY.as_posix(),
            "formal_strategy_sha256": sha256_file(repo / STRATEGY),
            "candidate_path": CANDIDATE.as_posix(),
            "candidate_sha256": sha256_file(repo / CANDIDATE),
            "candidate_manifest_path": CANDIDATE_MANIFEST.as_posix(),
            "candidate_manifest_sha256": sha256_file(repo / CANDIDATE_MANIFEST),
            "approved_ablation_unit": candidate_manifest["selected_ablation_unit"],
        },
        "execution_boundaries": {
            "campaign_generated": False,
            "campaign_executed": False,
            "candidate_created": False,
            "candidate_modified": False,
            "strategy_modified": False,
            "router_modified": False,
            "threshold_modified": False,
            "execution_config_modified": False,
            "backtest_run": False,
            "hyperopt_run": False,
            "temporal_slices_run": False,
            "validation_accessed": False,
            "holdout_accessed": False,
            "next_campaign_generated": False,
            "next_campaign_executed": False,
        },
        "evidence": [
            PROPOSAL.as_posix(),
            TEMPORAL_RESULT.as_posix(),
            APPROVAL.as_posix(),
        ],
        "closed_at": completed_at,
        "closure_fingerprint": "",
    }
    payload["closure_fingerprint"] = self_fingerprint(payload, "closure_fingerprint")
    return payload


def build_final(closure: dict[str, Any], completed_at: str) -> dict[str, Any]:
    payload = {
        "schema_version": "ranging-short-branch-retention-final-report-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "status": "completed",
        "decision": DECISION,
        "closure_status": CLOSURE_STATUS,
        "formal_branch": "ranging_short_entry",
        "formal_branch_retained": True,
        "temporally_stable_deletion_evidence": False,
        "slice_conclusions": SLICE_CONCLUSIONS,
        "recommendation": "retain_current_branch_and_close_whole_branch_deletion_research",
        "future_reference_boundary": "new_human_approved_regime_conditioned_routing_research_only",
        "no_next_campaign_generated": True,
        "no_research_execution_performed": True,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "closure_fingerprint": closure["closure_fingerprint"],
        "completed_at": completed_at,
        "final_report_fingerprint": "",
    }
    payload["final_report_fingerprint"] = self_fingerprint(payload, "final_report_fingerprint")
    return payload


def final_markdown(final: dict[str, Any]) -> str:
    return "\n".join([
        "# Ranging-short Branch Retention Review — Final Report",
        "",
        f"- Proposal: `{PROPOSAL_ID}`",
        f"- Proposal fingerprint: `{PROPOSAL_FINGERPRINT}`",
        f"- Human decision: `{DECISION}`",
        f"- Closure status: `{CLOSURE_STATUS}`",
        "- Formal `ranging_short_entry`: retained unchanged",
        "- Temporally stable deletion evidence: `false`",
        "",
        "## Frozen slice conclusions",
        "",
        "- `s01`: `inconclusive`",
        "- `s02`: `positive_contributor`",
        "- `s03`: `negative_contributor`",
        "- `s04`: `negative_contributor`",
        "",
        "The mixed temporal direction does not support whole-branch deletion. The evidence may be referenced again only by a new, human-approved `regime-conditioned routing` study.",
        "Adjacent thresholds, additional slices, poor results, or an LLM suggestion are not valid reasons to reopen whole-branch deletion research.",
        "",
        "No Campaign, Candidate, Backtest, Hyperopt, temporal slice, Validation, Holdout, or next Proposal was generated or executed by this closure.",
        "",
        f"Final report fingerprint: `{final['final_report_fingerprint']}`",
        "",
    ])


def update_state(repo: Path, closure: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    state = load_document(repo / STATE)
    closed = [item for item in state.get("closed_branches", []) if item.get("closure_id") != PROPOSAL_ID]
    closed.append({
        "closure_id": PROPOSAL_ID,
        "status": CLOSURE_STATUS,
        "research_status": CLOSURE_STATUS,
        "decision": DECISION,
        "branch": "ranging_short_entry",
        "scope": "whole_branch_deletion",
        "slice_conclusions": SLICE_CONCLUSIONS,
        "temporally_stable_deletion_evidence": False,
        "reopen_conditions": REOPEN_CONDITIONS,
        "insufficient_reopen_reasons": INSUFFICIENT_REOPEN_REASONS,
        "evidence": [CLOSURE.as_posix(), TEMPORAL_RESULT.as_posix(), APPROVAL.as_posix()],
    })
    state["closed_branches"] = closed
    state["ranging_short_branch_retention_review"] = {
        "status": "completed",
        "decision": DECISION,
        "closure_status": CLOSURE_STATUS,
        "formal_branch_retained": True,
        "slice_conclusions": SLICE_CONCLUSIONS,
        "campaign_generated": False,
        "campaign_executed": False,
        "candidate_created": False,
        "strategy_modified": False,
        "additional_backtests": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "next_campaign_generated": False,
        "next_campaign_executed": False,
        "evidence": [CLOSURE.as_posix(), FINAL_JSON.as_posix()],
    }
    review = state.get("ranging_short_temporal_branch_contribution_review") or {}
    review["next_proposal_status"] = "resolved_human_retain_current_branch"
    state["ranging_short_temporal_branch_contribution_review"] = review
    history = [item for item in state.get("proposal_history", []) if item.get("proposal_id") != PROPOSAL_ID]
    for item in history:
        if item.get("proposal_id") == "ranging-short-branch-decision-review-v1":
            item["historical_status"] = "completed"
            item["resolved_by"] = "branch_mixed_temporal_dependency"
            item["evidence"] = [TEMPORAL_RESULT.as_posix()]
    history.append({
        "proposal_id": PROPOSAL_ID,
        "semantic_fingerprint": PROPOSAL_FINGERPRINT,
        "historical_status": "approved",
        "resolved_by": DECISION,
        "closure_status": CLOSURE_STATUS,
        "evidence": [PROPOSAL.as_posix(), APPROVAL.as_posix(), CLOSURE.as_posix()],
    })
    state["proposal_history"] = history
    for question in state.get("unresolved_research_questions", []):
        if question.get("question_id") == "branch-contribution-ablation":
            question["current_answer"] = CLOSURE_STATUS
            question["evidence"] = [TEMPORAL_RESULT.as_posix(), CLOSURE.as_posix()]
    state["possible_next_directions"] = [
        item for item in state.get("possible_next_directions", [])
        if "ranging_short" not in str(item.get("direction", ""))
    ]
    state.setdefault("allowed_research_scope", {})["ranging_short_evidence_reuse"] = (
        "new_human_approved_regime_conditioned_routing_research_only"
    )
    state.setdefault("forbidden_scope", {})["ranging_short_whole_branch_deletion_reopen"] = True
    approvals = state.setdefault("governance_inputs", {}).setdefault("approval_events", [])
    approvals = [item for item in approvals if item.get("path") != APPROVAL.as_posix()]
    approvals.append({"path": APPROVAL.as_posix(), "sha256": sha256_file(repo / APPROVAL)})
    state["governance_inputs"]["approval_events"] = approvals
    state["generated_at"] = approval["approved_at"]
    state["state_fingerprint"] = fingerprint({
        key: value for key, value in state.items() if key not in {"generated_at", "state_fingerprint", "snapshot_id"}
    })
    state["snapshot_id"] = f"research-state-{state['state_fingerprint'][:16]}"
    write_json(repo / STATE, state)
    return state


def record_registry(repo: Path, approval: dict[str, Any], closure: dict[str, Any], completed_at: str) -> None:
    connection = open_director_registry(repo / REGISTRY)
    connection.execute(
        "INSERT OR REPLACE INTO proposal_selection_events(proposal_id,proposal_fingerprint,approval_status,approver_type,approved_at,payload_json) VALUES(?,?,?,?,?,?)",
        (PROPOSAL_ID, PROPOSAL_FINGERPRINT, "approved", "human_user", completed_at, json.dumps(approval, sort_keys=True)),
    )
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs(run_id,campaign_id,proposal_id,status,result_code,campaign_executed,candidate_created,strategy_modified,validation_accesses,holdout_accesses,payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (RUN_ID, "governance-only-no-campaign", PROPOSAL_ID, "completed", CLOSURE_STATUS, 0, 0, 0, 0, 0, json.dumps(closure, sort_keys=True), completed_at),
    )
    assets = [APPROVAL, CLOSURE, FINAL_JSON, FINAL_MD, STATE, PROPOSAL, TEMPORAL_RESULT]
    for path in assets:
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets(asset_id,run_id,artifact_type,path,sha256,created_at) VALUES(?,?,?,?,?,?)",
            (f"{RUN_ID}:{path.as_posix()}", RUN_ID, "governance_closure", path.as_posix(), sha256_file(repo / path), completed_at),
        )
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise RetentionClosureError("registry_integrity_failed")
    write_json(repo / REGISTRY_EXPORT, export_registry(str(repo / REGISTRY)))


def close(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    _, _, candidate_manifest = validate_evidence(repo)
    completed_at = utc_now()
    approval = build_approval(completed_at)
    write_json(repo / APPROVAL, approval)
    closure = build_closure(repo, completed_at, candidate_manifest)
    write_json(repo / CLOSURE, closure)
    final = build_final(closure, completed_at)
    write_json(repo / FINAL_JSON, final)
    (repo / FINAL_MD).parent.mkdir(parents=True, exist_ok=True)
    (repo / FINAL_MD).write_text(final_markdown(final), encoding="utf-8")
    update_state(repo, closure, approval)
    record_registry(repo, approval, closure, completed_at)
    return final


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    final = close(repo)
    print(json.dumps({
        "status": final["status"],
        "decision": final["decision"],
        "closure_status": final["closure_status"],
        "final_report_fingerprint": final["final_report_fingerprint"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
