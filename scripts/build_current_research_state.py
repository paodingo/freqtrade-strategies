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
    fingerprint,
    load_document,
    open_director_registry,
    registry_summary,
    sha256_file,
    utc_now,
    write_json,
)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True, encoding="utf-8").strip()


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


def build_state(repo: Path, source_registry: Path | None, data_lineage: Path | None = None) -> dict[str, Any]:
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

    policy = load_document(policy_path)
    closure = load_document(closure_path)
    temporal = load_document(temporal_path)
    attribution = load_document(attribution_path)
    invalidation = load_document(invalidation_path)
    recertification = load_document(recertification_path) if recertification_path.exists() else {}
    stage4b1_decision = load_document(stage4b1_decision_path) if stage4b1_decision_path.exists() else {}
    exit_logic_decision = load_document(exit_logic_decision_path) if exit_logic_decision_path.exists() else {}
    regime_branch_decision = load_document(regime_branch_decision_path) if regime_branch_decision_path.exists() else {}
    registry = registry_summary(source_registry)
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
    capabilities = [
        {"capability": "sealed_offline_futures_backtesting", "status": "available", "evidence": ["research/runtime/offline-adapter-contract.yaml", "reports/audits/stage3a5_futures_online_offline_adapter_certification.md"]},
        {"capability": "candidate_process_isolation", "status": "available", "evidence": ["docs/decisions/ADR-candidate-python-import-isolation.md", "research/recertification/stage3d3b/stage3d2b-invalidation-event.json"]},
        {"capability": "balanced_research_gate", "status": "approved", "evidence": ["research/evaluation/evaluation-policy.yaml"]},
        {"capability": "branch_closure_governance", "status": "available", "evidence": ["research/closures/regime-aware-ranging-thresholds-v1.yaml"]},
        {"capability": "temporal_generalization_profile", "status": temporal.get("classification"), "evidence": ["research/temporal/stage3e1-temporal-comparison.json"]},
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
        {"question_id": "cross-pair-generalization", "question": "Does temporal consistency persist across additional Binance USD-M pairs?", "evidence": ["research/temporal/stage3e1-temporal-comparison.json", "research/director/compiled/cross-pair-data-readiness-audit-v1/execution/readiness-decision.json"], "current_answer": stage4b1_decision.get("status", "unknown_no_sealed_non_btc_strategy_dataset")},
        {"question_id": "exit-logic-structure", "question": "Which exit mechanisms explain regime-specific losses without changing risk semantics?", "evidence": ["research/analysis/stage3d3a-final-report.json", "research/temporal/stage3e1-temporal-comparison.json", "research/analysis/exit-logic-audit/exit-attribution.json"], "current_answer": exit_logic_decision.get("status", "attribution_incomplete")},
        {"question_id": "regime-branch-structure", "question": "Are regime branch activation and directionality imbalances structural rather than threshold-local?", "evidence": ["research/analysis/regime-aware-condition-graph.json", "research/temporal/stage3e1-temporal-comparison.json", "research/analysis/regime-branch-audit/regime-branch-structure.json"], "current_answer": regime_branch_decision.get("status", "read_only_audit_possible")},
    ]
    pending_proposals = [
        {"proposal_id": "stage3d3b-research-direction-proposal", "historical_status": attribution.get("proposal_status"), "resolved_by": "stage3d3b-recertification", "evidence": ["research/proposals/stage3d3b-research-direction-proposal.yaml", "research/closures/regime-aware-ranging-thresholds-v1.yaml"]},
        {"proposal_id": "stage3d4b-mechanism-proposal", "historical_status": "approved_no_change", "resolved_by": "A_keep_current", "evidence": ["research/proposals/stage3d4b-mechanism-proposal.yaml", "research/closures/stage3d4b-mechanism-approval-event.json"]},
    ]

    lineage_path = data_lineage or (repo / "research/data/data-lineage.sqlite")
    lineage_record = {
        "path": lineage_path.as_posix(),
        "exists": lineage_path.is_file(),
        "sha256": sha256_file(lineage_path) if lineage_path.is_file() else None,
    }

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
        }],
        "invalidated_research": [{"event_id": invalidation.get("event_id"), "reason": invalidation_reasons, "affected_experiment_ids": invalidation.get("affected_experiment_ids", []), "repair_status": "recertified", "evidence": ["research/recertification/stage3d3b/stage3d2b-invalidation-event.json", "research/closures/regime-aware-ranging-thresholds-v1.yaml"]}],
        "fixed_harness_defects": fixed_defects,
        "proposal_history": pending_proposals,
        "allowed_research_scope": {"read_only_analysis": True, "approved_market": "Binance USD-M Futures", "baseline_pair": "BTC/USDT:USDT", "baseline_timeframe": "1h", "strategy_mutation": False, "candidate_creation": False, "evidence": ["research/evaluation/evaluation-policy.yaml", "research/governance/research-constitution.yaml"]},
        "forbidden_scope": {"validation_feedback_mutation": True, "holdout": True, "live": True, "private_api": True, "strategy_or_risk_change": True, "closed_threshold_branch": True, "evidence": ["research/evaluation/evaluation-policy.yaml", "research/closures/regime-aware-ranging-thresholds-v1.yaml", "research/governance/research-constitution.yaml"]},
        "validation_holdout": {"validation_dataset_manifest_visible": True, "validation_result_feedback_available_to_director": False, "validation_access_budget": 0, "holdout_available": False, "accessed_by_stage4a": False, "evidence": ["research/evaluation/evaluation-policy.yaml", "research/data/validation-access-policy.yaml"]},
        "unresolved_research_questions": unresolved_questions,
        "data_capabilities": {"btc_development_dataset": True, "btc_validation_manifest": True, "sealed_exchange_metadata": True, "public_non_btc_market_metadata": stage4b1_decision.get("public_non_btc_market_metadata_available", True), "non_btc_sealed_strategy_dataset": stage4b1_decision.get("local_non_btc_futures_dataset_available", False), "cross_pair_readiness_audit_completed": stage4b1_decision.get("campaign_audit_completed", False), "human_pair_scope_required": stage4b1_decision.get("human_pair_scope_required", False), "temporal_slices": temporal.get("valid_slice_count", 0), "evidence": ["research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml", "research/temporal/stage3e1-temporal-comparison.json", "research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml", "research/director/compiled/cross-pair-data-readiness-audit-v1/execution/readiness-decision.json"]},
        "possible_next_directions": [
            {"direction": "cross_pair_data_readiness_audit", "evidence": ["research/temporal/stage3e1-temporal-comparison.json", "research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml"]},
            {"direction": "exit_logic_structure_audit", "evidence": ["research/analysis/stage3d3a-final-report.json", "research/temporal/stage3e1-temporal-comparison.json"]},
            {"direction": "regime_branch_structure_audit", "evidence": ["research/analysis/regime-aware-condition-graph.json", "research/closures/regime-aware-ranging-thresholds-v1.yaml"]},
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
    }
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
    return "\n".join(lines)


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
    state = build_state(repo, source_registry, data_lineage)
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
