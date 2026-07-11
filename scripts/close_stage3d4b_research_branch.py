#!/usr/bin/env python3
"""Approve A_keep_current and close the exhausted Stage 3D threshold branch."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_control import load_simple_yaml
from run_experiment import dump_json, dump_manifest, sha256_file


PROPOSAL = Path("research/proposals/stage3d4b-mechanism-proposal.yaml")
PREAPPROVAL = Path("research/closures/stage3d4b-preapproval-proposal-snapshot.yaml")
APPROVAL_EVENT = Path("research/closures/stage3d4b-mechanism-approval-event.json")
APPROVED_DECISION = Path("research/closures/stage3d4b-approved-mechanism-decision.yaml")
CLOSURE = Path("research/closures/regime-aware-ranging-thresholds-v1.yaml")
FINAL_JSON = Path("research/closures/stage3d4b-final-closure.json")
FINAL_MD = Path("reports/closures/stage3d4b_regime_aware_threshold_branch_closure.md")
REGISTRY = Path("research/registry/research.db")

STAGE3D4A = Path("research/analysis/stage3d4a-final-report.json")
STAGE3D3B = Path("research/results/stage3d3b-candidate-process-isolation-recertification/stage3d3b-final-report.json")
INVALIDATION = Path("research/recertification/stage3d3b/stage3d2b-invalidation-event.json")
AMENDMENT = Path("reports/amendments/stage3d2b-runtime-cache-invalidation.md")
ORIGINAL_QUEUE = Path("research/queues/stage3d2b-batch1-experiments.yaml")
RECERT_QUEUE = Path("research/queues/stage3d3b-recertification.yaml")
POLICY = Path("research/evaluation/evaluation-policy.yaml")
SPLIT = Path("research/data/splits/futures-dev-validation-v2.yaml")
STRATEGY = Path("strategies/RegimeAwareV6.py")

PREAPPROVAL_HASH = "6e17bd758f3bfaed17d9f84752830c849f510a642c9faee4034068baf3185745"
BASE_STRATEGY_HASH = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
POLICY_SEMANTIC_HASH = "aa1798f7eb002ed30ad5fff95be48f3a08bc42e54f6b0f9406cd39412b9cff71"
DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
DATASET_SEMANTIC_HASH = "edaa023013536069cc06a188f88a148dd60c784b1d9cc1dfd3575d32bd2bb330"
ORIGINAL_QUEUE_HASH = "bdb463186783e5c3f34027635e250e5e4c39c1185c447a13101848d3de9373a4"
RECERT_QUEUE_HASH = "85a02b01b59f97eb3489e74fb07b47aa8ddcc932964f9447b94904a2ea17604b"
VARIABLES = (
    "ranging_long_setup.rsi_max",
    "ranging_short_setup.bb_percent_min",
    "ranging_short_setup.rsi_min",
    "ranging_shared.adx_4h_max_long",
)
REOPEN_CONDITIONS = (
    "human_approved_new_dataset_or_market_scope",
    "new_pair_or_timeframe",
    "human_approved_strategy_structural_change",
    "new_evidence_of_uncaptured_independent_post_exit_reentry",
    "changed_first_trigger_execution_semantics",
    "human_approved_multivariable_mechanism_research",
    "newly_discovered_research_validity_defect",
)
INSUFFICIENT_REOPEN_REASONS = (
    "adjacent_thresholds",
    "poor_result",
    "wider_threshold_range",
    "more_backtests",
    "no_development_eligible_candidate",
    "llm_hunch",
)


class ClosureError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def self_hash(value: dict[str, Any], field: str) -> str:
    return stable_hash({key: item for key, item in value.items() if key != field})


def read_json(root: Path, path: Path) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def verify_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if sha256_file(root / STRATEGY).lower() != BASE_STRATEGY_HASH:
        raise ClosureError("base strategy hash drift")
    proposal = load_simple_yaml(root / PROPOSAL)
    if proposal.get("status") == "pending_human_review":
        if proposal.get("proposal_sha256") != PREAPPROVAL_HASH or self_hash(proposal, "proposal_sha256") != PREAPPROVAL_HASH:
            raise ClosureError("preapproval proposal hash drift")
    elif proposal.get("status") != "approved_no_change":
        raise ClosureError("proposal has an unsupported status")
    stage4a = read_json(root, STAGE3D4A)
    stage3b = read_json(root, STAGE3D3B)
    invalidation = read_json(root, INVALIDATION)
    split = load_simple_yaml(root / SPLIT)
    recert_queue = load_simple_yaml(root / RECERT_QUEUE)
    original_queue = load_simple_yaml(root / ORIGINAL_QUEUE)
    if stage4a.get("proposal_sha256") != PREAPPROVAL_HASH or not stage4a.get("single_threshold_search_closed"):
        raise ClosureError("Stage 3D.4-A closure evidence is invalid")
    if stage3b.get("status") != "completed" or stage3b.get("trade_changed_experiment_ids") != [6, 7, 8]:
        raise ClosureError("Stage 3D.3-B recertification evidence is invalid")
    if stage3b.get("development_eligible_experiment_ids") != [] or not stage3b.get("process_isolation_passed"):
        raise ClosureError("Stage 3D.3-B validity contract is invalid")
    if invalidation.get("affected_experiment_ids") != list(range(2, 11)):
        raise ClosureError("invalidation history is incomplete")
    if split.get("development_dataset_id") != DATASET_ID or split.get("split_sha256") != DATASET_SEMANTIC_HASH:
        raise ClosureError("Development dataset identity drift")
    if recert_queue.get("queue_sha256") != RECERT_QUEUE_HASH or recert_queue.get("original_queue_sha256") != ORIGINAL_QUEUE_HASH:
        raise ClosureError("recertification queue drift")
    if original_queue.get("queue_sha256") != ORIGINAL_QUEUE_HASH:
        raise ClosureError("original queue drift")
    return proposal, stage4a, stage3b, invalidation


def historical_hashes(root: Path) -> dict[str, str]:
    paths = (STAGE3D4A, STAGE3D3B, INVALIDATION, AMENDMENT, ORIGINAL_QUEUE, RECERT_QUEUE, POLICY, SPLIT, STRATEGY)
    return {path.as_posix(): sha256_file(root / path).lower() for path in paths}


def approve_proposal(root: Path, proposal: dict[str, Any], timestamp: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if proposal.get("status") == "pending_human_review":
        (root / PREAPPROVAL).parent.mkdir(parents=True, exist_ok=True)
        if not (root / PREAPPROVAL).exists():
            (root / PREAPPROVAL).write_text((root / PROPOSAL).read_text(encoding="utf-8"), encoding="utf-8")
        proposal.update({
            "status": "approved_no_change",
            "decision": "A_keep_current",
            "approval_status": "approved",
            "approver_type": "human_user",
            "approval_timestamp": timestamp,
            "approved_action": "preserve_existing_semantics",
            "code_change_authorized": False,
            "candidate_creation_authorized": False,
            "search_continuation_authorized": False,
            "mechanism_change_authorized": False,
            "preapproval_proposal_sha256": PREAPPROVAL_HASH,
        })
        proposal["proposal_sha256"] = self_hash(proposal, "proposal_sha256")
        dump_manifest(root / PROPOSAL, proposal)
    timestamp = proposal["approval_timestamp"]
    event = {
        "schema_version": "stage3d4b-mechanism-approval-event-v1",
        "event_id": "stage3d4b-a-keep-current-human-approval",
        "event_type": "mechanism_approval",
        "decision": "A_keep_current",
        "approval_status": "approved",
        "approver_type": "human_user",
        "approved_action": "preserve_existing_semantics",
        "mechanism_change_authorized": False,
        "code_change_authorized": False,
        "candidate_creation_authorized": False,
        "search_continuation_authorized": False,
        "preapproval_proposal_sha256": PREAPPROVAL_HASH,
        "approved_proposal_sha256": proposal["proposal_sha256"],
        "proposal_path": PROPOSAL.as_posix(),
        "preapproval_snapshot_path": PREAPPROVAL.as_posix(),
        "created_at": timestamp,
    }
    event["event_sha256"] = self_hash(event, "event_sha256")
    dump_json(root / APPROVAL_EVENT, event)
    decision = {
        "schema_version": "stage3d4b-approved-mechanism-decision-v1",
        "decision": "A_keep_current",
        "mechanism_decision": "keep_current",
        "status": "approved_no_change",
        "approved_action": "preserve_existing_semantics",
        "approval_event_id": event["event_id"],
        "approval_event_sha256": event["event_sha256"],
        "proposal_sha256": proposal["proposal_sha256"],
        "code_change_status": "not_required",
        "all_change_authorizations": False,
    }
    decision["decision_sha256"] = self_hash(decision, "decision_sha256")
    dump_manifest(root / APPROVED_DECISION, decision)
    return proposal, event


def build_closure(stage4a: dict[str, Any], stage3b: dict[str, Any], invalidation: dict[str, Any], proposal: dict[str, Any], event: dict[str, Any], history: dict[str, str], timestamp: str) -> dict[str, Any]:
    variables = {}
    for variable_id in VARIABLES:
        evidence = stage4a["variable_closures"][variable_id]
        variables[variable_id] = {
            "research_status": "closed_for_current_scope",
            "single_threshold_search_allowed": False,
            "tested_values": evidence["tested_values"],
            "signal_changed": evidence["final_signal_changed"],
            "trade_behavior_changed_experiment_ids": evidence["trade_behavior_changed_experiment_ids"],
            "development_status_by_value": evidence["development_status_by_value"],
            "conclusion": evidence["recommended_status"],
        }
    invalidated = [row["original_experiment_id"] for row in invalidation["records"] if row["research_validity"] == "invalidated"]
    closure = {
        "schema_version": "stage3d4b-research-branch-closure-v1",
        "closure_id": "regime-aware-ranging-thresholds-v1",
        "status": "closed_evidence_exhausted",
        "strategy_family": "RegimeAwareV6",
        "engineering_validity": "verified",
        "research_status": "closed_evidence_exhausted",
        "mechanism_decision": "keep_current",
        "approved_mechanism": "A_keep_current",
        "code_change_status": "not_required",
        "base_strategy_sha256": BASE_STRATEGY_HASH,
        "evaluation_policy_sha256": POLICY_SEMANTIC_HASH,
        "development_dataset": {"dataset_id": DATASET_ID, "dataset_sha256": DATASET_SEMANTIC_HASH},
        "variables": variables,
        "experiment_lineage": {
            "valid_original_experiment_ids": [1],
            "invalidated_original_experiment_ids": invalidated,
            "invalidation_reason": "candidate_dependency_module_cache_shadowed",
            "recertified_experiment_ids": list(range(1, 11)),
            "original_queue_sha256": ORIGINAL_QUEUE_HASH,
            "recertification_queue_sha256": RECERT_QUEUE_HASH,
        },
        "conclusions": {
            "signal_changed_experiment_ids": stage3b["signal_changed_experiment_ids"],
            "trade_changed_experiment_ids": stage3b["trade_changed_experiment_ids"],
            "development_eligible_experiment_ids": stage3b["development_eligible_experiment_ids"],
            "development_gate": {"6": "no_material_improvement", "7": "risk_degradation", "8": "no_material_improvement"},
            "duplicate_same_direction_signal_count": stage4a["duplicate_signal_count"],
            "duplicate_signal_primary_lifecycle": "signal_expired_before_flat",
            "missed_post_exit_reentry_opportunity_count": stage4a["real_missed_reentry_opportunity_count"],
            "later_independent_setup_reappearance_count": 2,
            "expired_before_flat_count": 10,
            "mechanism_recommendation": stage4a["recommendation"],
        },
        "closure_reason": "current_scope_single_threshold_and_duplicate_signal_evidence_exhausted",
        "reopen_conditions": list(REOPEN_CONDITIONS),
        "insufficient_reopen_reasons": list(INSUFFICIENT_REOPEN_REASONS),
        "approval_event": {"event_id": event["event_id"], "event_sha256": event["event_sha256"], "timestamp": event["created_at"]},
        "historical_artifact_integrity": history,
        "historical_artifacts_modified": False,
        "forbidden_actions": {
            "strategy_modified": False, "candidate_created": False, "candidate_modified": False,
            "backtest_run": False, "hyperopt_run": False, "validation_accessed": False,
            "holdout_accessed": False, "position_stacking_enabled": False,
            "position_adjustment_enabled": False, "execution_or_risk_config_modified": False,
        },
        "artifact_index": {
            "preapproval_snapshot": PREAPPROVAL.as_posix(), "approval_event": APPROVAL_EVENT.as_posix(),
            "approved_decision": APPROVED_DECISION.as_posix(), "proposal": PROPOSAL.as_posix(),
            "closure": CLOSURE.as_posix(), "final_json": FINAL_JSON.as_posix(), "final_markdown": FINAL_MD.as_posix(),
            "stage3d4a_evidence": STAGE3D4A.as_posix(), "stage3d3b_recertification": STAGE3D3B.as_posix(),
            "invalidation_event": INVALIDATION.as_posix(), "historical_amendment": AMENDMENT.as_posix(),
        },
        "closed_at": timestamp,
    }
    closure["closure_sha256"] = self_hash(closure, "closure_sha256")
    return closure


def write_registry(root: Path, closure: dict[str, Any], event: dict[str, Any], proposal: dict[str, Any]) -> None:
    conn = sqlite3.connect(root / REGISTRY)
    try:
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS stage3d4b_mechanism_approval_events (
                    event_id TEXT PRIMARY KEY, decision TEXT NOT NULL, approver_type TEXT NOT NULL,
                    proposal_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS stage3d4b_branch_closure_events (
                    closure_id TEXT PRIMARY KEY, research_status TEXT NOT NULL, mechanism_decision TEXT NOT NULL,
                    engineering_validity TEXT NOT NULL, code_change_status TEXT NOT NULL,
                    closure_artifact TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS stage3d4b_variable_governance_events (
                    closure_id TEXT NOT NULL, variable_id TEXT NOT NULL, research_status TEXT NOT NULL,
                    single_threshold_search_allowed INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (closure_id, variable_id));
            """)
            conn.execute("INSERT OR IGNORE INTO stage3d4b_mechanism_approval_events VALUES (?,?,?,?,?,?)", (
                event["event_id"], event["decision"], event["approver_type"], proposal["proposal_sha256"],
                json.dumps(event, sort_keys=True), event["created_at"]))
            conn.execute("INSERT OR IGNORE INTO stage3d4b_branch_closure_events VALUES (?,?,?,?,?,?,?,?)", (
                closure["closure_id"], closure["research_status"], closure["mechanism_decision"],
                closure["engineering_validity"], closure["code_change_status"], CLOSURE.as_posix(),
                json.dumps(closure, sort_keys=True), closure["closed_at"]))
            for variable_id, governance in closure["variables"].items():
                conn.execute("INSERT OR IGNORE INTO stage3d4b_variable_governance_events VALUES (?,?,?,?,?,?)", (
                    closure["closure_id"], variable_id, governance["research_status"], 0,
                    json.dumps(governance, sort_keys=True), closure["closed_at"]))
    finally:
        conn.close()


def write_report(root: Path, closure: dict[str, Any]) -> None:
    tested = "\n".join(f"- `{key}`: `{value['tested_values']}`" for key, value in closure["variables"].items())
    reopen = "\n".join(f"- `{item}`" for item in closure["reopen_conditions"])
    artifacts = "\n".join(f"- `{key}`: `{value}`" for key, value in closure["artifact_index"].items())
    text = f"""# Stage 3D.4-B Research Branch Closure

## Decision

The human-approved decision is `A_keep_current`. Existing first-trigger and entry execution semantics remain unchanged. The branch status is `closed_evidence_exhausted`; engineering validity remains `verified`, and no code change is required.

## Research Scope And Tested Values

{tested}

The Stage 3D.2-B module-cache defect invalidated original experiments 2-10. Stage 3D.3-B preserved that history, introduced fresh-process runtime identity checks, and recertified experiments 1-10. All ten changed reachable signals. Experiments 6, 7, and 8 changed trades; none passed the Development Gate (no material improvement, risk degradation, no material improvement).

## Signal-To-Trade And Lifecycle Conclusion

Twelve same-direction signals occurred while positions were already open. Ten expired before flat. Two setups later appeared independently and were opened by current semantics. There were zero uncaptured post-exit re-entry opportunities. Signal persistence, carry-over, position stacking, and position adjustment therefore have no demonstrated low-risk value in this scope.

## Governance

All four variables are `closed_for_current_scope` and `single_threshold_search_allowed: false`. Adjacent values, wider ranges, more backtests, lack of an eligible candidate, poor results, or an LLM hunch do not reopen the branch.

## Reopen Conditions

{reopen}

## Approval And Integrity

Approval event: `{closure['approval_event']['event_id']}`. Proposal preapproval and postapproval hashes are explicit. Historical Stage 3D.1, 3D.2-B, 3D.3-B, and 3D.4-A evidence remains referenced and unmodified by this closure operation.

## Artifact Index

{artifacts}
"""
    (root / FINAL_MD).parent.mkdir(parents=True, exist_ok=True)
    (root / FINAL_MD).write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repo_root.resolve()
    proposal, stage4a, stage3b, invalidation = verify_inputs(root)
    history_before = historical_hashes(root)
    timestamp = proposal.get("approval_timestamp") or utc_now()
    proposal, event = approve_proposal(root, proposal, timestamp)
    closure = build_closure(stage4a, stage3b, invalidation, proposal, event, history_before, timestamp)
    dump_manifest(root / CLOSURE, closure)
    write_registry(root, closure, event, proposal)
    write_report(root, closure)
    final = dict(closure)
    final["schema_version"] = "stage3d4b-final-closure-v1"
    final["status"] = "completed"
    final["closure_record_sha256"] = closure["closure_sha256"]
    final["final_sha256"] = self_hash(final, "final_sha256")
    dump_json(root / FINAL_JSON, final)
    if historical_hashes(root) != history_before:
        raise ClosureError("historical artifact changed during closure")
    print(json.dumps({"status": "completed", "closure_id": closure["closure_id"], "proposal_sha256": proposal["proposal_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
