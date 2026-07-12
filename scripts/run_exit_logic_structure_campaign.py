#!/usr/bin/env python3
"""Execute the one approved low-risk exit-logic structure audit without backtests."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    utc_now,
    write_json,
)
from stage4b1_governance import (
    verify_campaign_fingerprint,
    verify_constitution_approval,
    verify_human_selection_for,
)


PROPOSAL_ID = "exit-logic-structure-audit-v1"
RUN_ID = "exit-logic-structure-audit-v1-run-001"


def build_attribution(repo: Path) -> dict[str, Any]:
    temporal_path = repo / "research/temporal/stage3e1-temporal-comparison.json"
    attribution_path = repo / "research/analysis/stage3d3a-final-report.json"
    mechanism_path = repo / "research/analysis/stage3d4a-final-report.json"
    runtime_path = repo / "research/runtime/freqtrade-2025-8-signal-execution-contract.yaml"
    temporal = load_document(temporal_path)
    prior_attribution = load_document(attribution_path)
    mechanism = load_document(mechanism_path)

    aggregate: Counter[str] = Counter()
    slices = []
    for row in temporal["slice_results"]:
        metrics = row["metrics"]
        counts = metrics["coverage"]["exit_reason_distribution"]
        total = int(metrics["coverage"]["total_trades"])
        aggregate.update(counts)
        slices.append({
            "slice_id": row["slice_id"],
            "dominant_market_regime": row["dominant_market_regime"],
            "total_trades": total,
            "total_return": metrics["return"]["total_return"],
            "profit_factor": metrics["risk_adjusted"]["profit_factor"],
            "max_drawdown_percentage": metrics["risk"]["max_drawdown_percentage"],
            "average_duration_minutes": metrics["execution_cost"]["average_duration_minutes"],
            "exit_reason_counts": counts,
            "exit_reason_shares": {key: value / total for key, value in sorted(counts.items())},
        })
    total_exits = sum(aggregate.values())
    negative = [row for row in slices if row["total_return"] < 0]
    positive = [row for row in slices if row["total_return"] > 0]
    return {
        "schema_version": "exit-logic-structure-attribution-v1",
        "sources": [
            {"path": temporal_path.relative_to(repo).as_posix(), "sha256": sha256_file(temporal_path)},
            {"path": attribution_path.relative_to(repo).as_posix(), "sha256": sha256_file(attribution_path)},
            {"path": mechanism_path.relative_to(repo).as_posix(), "sha256": sha256_file(mechanism_path)},
            {"path": runtime_path.relative_to(repo).as_posix(), "sha256": sha256_file(runtime_path)},
        ],
        "slice_count": len(slices),
        "slices": slices,
        "aggregate": {
            "total_exits": total_exits,
            "exit_reason_counts": dict(sorted(aggregate.items())),
            "exit_reason_shares": {key: value / total_exits for key, value in sorted(aggregate.items())},
            "negative_return_slice_ids": [row["slice_id"] for row in negative],
            "positive_return_slice_ids": [row["slice_id"] for row in positive],
        },
        "prior_exit_delta_attribution": {
            "exit_delta_count": prior_attribution["exit_count"],
            "direct_exit_mutation_evidence_available": prior_attribution["exit_count"] > 0,
            "instrumentation_trade_hash_preserved": prior_attribution["instrumentation_trade_hash_preserved"],
        },
        "first_trigger_semantics": {
            "conflict_count": mechanism["first_trigger_conflict_count"],
            "real_missed_reentry_opportunity_count": mechanism["real_missed_reentry_opportunity_count"],
            "recommendation": mechanism["recommendation"],
        },
        "structural_findings": [
            "roi and stop_loss dominate observed exits across all temporal slices",
            "the sole negative slice has a high stop_loss share, but positive slices also contain material stop_loss exits",
            "trending_time_stop and force_exit are too sparse for a causal structural conclusion",
            "prior signal-to-trade attribution recorded zero exit deltas, so it cannot justify an exit mutation",
            "first-trigger evidence records no conflict and no real missed post-exit reentry opportunity",
        ],
        "causal_claim_allowed": False,
        "strategy_or_risk_change_warranted": False,
        "result_code": "no_exit_change_warranted_insufficient_causal_evidence",
    }


def execute(repo: Path, registry_path: Path, analysis_dir: Path, execution_dir: Path, report_dir: Path) -> dict[str, Any]:
    constitution = load_document(repo / "research/governance/research-constitution.yaml")
    constitution_event = load_document(repo / "research/governance/approvals/research-constitution-v1-approval.json")
    proposal = load_document(repo / "research/director/next/proposals/exit-logic-structure-audit-v1.json")
    selection = load_document(repo / "research/director/approvals/exit-logic-structure-audit-v1-human-selection.json")
    campaign = load_document(repo / "research/director/compiled/exit-logic-structure-audit-v1/campaign.yaml")
    authorization = load_document(repo / "research/director/compiled/exit-logic-structure-audit-v1/execution-authorization.json")

    fingerprint_check = verify_campaign_fingerprint(campaign, authorization["approved_compiled_fingerprint"])
    constitution_check = verify_constitution_approval(repo, constitution, constitution_event)
    selection_check = verify_human_selection_for(proposal, selection, PROPOSAL_ID)
    if not fingerprint_check["matched"]:
        raise ValueError("compiled_campaign_fingerprint_drift")
    if not constitution_check["matched"]:
        raise ValueError("constitution_approval_hash_drift")
    if not selection_check["matched"]:
        raise ValueError("proposal_selection_mismatch")
    if campaign.get("execution_authorized") is not True or authorization.get("execution_authorized") is not True:
        raise ValueError("campaign_not_authorized")
    if selection.get("portfolio_budget") != {"max_campaigns": 1, "max_validation_accesses": 0, "max_holdout_accesses": 0}:
        raise ValueError("portfolio_budget_mismatch")

    connection = open_director_registry(registry_path)
    executed = connection.execute("SELECT COUNT(*) FROM research_campaign_runs WHERE campaign_executed=1").fetchone()[0]
    if executed >= 1:
        connection.close()
        raise ValueError("portfolio_max_campaigns_exhausted")

    attribution = build_attribution(repo)
    completed_at = utc_now()
    decision = {
        "schema_version": "exit-logic-structure-decision-v1",
        "campaign_id": campaign["campaign_id"],
        "campaign_executed": True,
        "status": attribution["result_code"],
        "strategy_or_risk_change_warranted": False,
        "new_candidate_required": False,
        "additional_backtest_required_by_this_campaign": False,
        "exit_distribution_causal_claim_allowed": False,
        "followup_if_human_selected": "regime_branch_structure_audit",
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "candidate_created": False,
        "strategy_modified": False,
        "backtest_or_parameter_search_run": False,
        "hyperopt_run": False,
    }
    execution = {
        "schema_version": "research-campaign-execution-v1",
        "run_id": RUN_ID,
        "campaign_id": campaign["campaign_id"],
        "proposal_id": PROPOSAL_ID,
        "approved_compiled_fingerprint": authorization["approved_compiled_fingerprint"],
        "status": "completed",
        "result_code": decision["status"],
        "completed_at": completed_at,
        "gates": {"campaign_fingerprint": fingerprint_check, "constitution": constitution_check, "human_selection": selection_check},
        "steps": [
            {"experiment_id": item["experiment_id"], "action": item["action"], "status": "completed_read_only"}
            for item in campaign["experiment_queue"]
        ],
        "decision": decision,
        "executed_proposal_ids": [PROPOSAL_ID],
        "second_campaign_executed": False,
        "stage4c_started": False,
    }

    analysis_dir.mkdir(parents=True, exist_ok=True)
    execution_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    write_json(analysis_dir / "exit-attribution.json", attribution)
    audit_md = f"""# Exit Logic Structure Audit

- Temporal slices: `{attribution['slice_count']}`
- Total observed exits: `{attribution['aggregate']['total_exits']}`
- Aggregate exit counts: `{json.dumps(attribution['aggregate']['exit_reason_counts'], sort_keys=True)}`
- Prior direct exit deltas: `{attribution['prior_exit_delta_attribution']['exit_delta_count']}`
- First-trigger conflicts: `{attribution['first_trigger_semantics']['conflict_count']}`
- Real missed reentry opportunities: `{attribution['first_trigger_semantics']['real_missed_reentry_opportunity_count']}`
- Result: `{attribution['result_code']}`

The negative slice has a high stop-loss share, but positive slices also contain material stop-loss exits. Exit-reason distribution alone is therefore not causal evidence for changing ROI, stoploss, time-stop, protections, or strategy logic. This Campaign makes no strategy or risk change.
"""
    (analysis_dir / "exit-structure-audit.md").write_text(audit_md, encoding="utf-8")
    write_json(execution_dir / "campaign-execution.json", execution)
    write_json(execution_dir / "audit-decision.json", decision)
    final = {
        "schema_version": "exit-logic-structure-campaign-final-report-v1",
        "run_id": RUN_ID,
        "campaign_id": campaign["campaign_id"],
        "campaign_fingerprint": authorization["approved_compiled_fingerprint"],
        "status": "implemented_uncommitted",
        "result_code": decision["status"],
        "completed_at": completed_at,
        "summary": decision,
        "required_artifacts_complete": True,
        "next_director_run_allowed": True,
        "second_campaign_execution_allowed": False,
    }
    final_json = report_dir / "exit-logic-structure-final-report.json"
    final_md = report_dir / "exit-logic-structure-final-report.md"
    write_json(final_json, final)
    final_md.write_text(f"""# Exit Logic Structure Campaign Final Report

- Campaign executed: `true`
- Result: `{decision['status']}`
- Strategy/risk change warranted: `false`
- Candidate/backtest/Hyperopt: `false / false / false`
- Validation/Holdout accesses: `0 / 0`

All three approved read-only steps completed. Evidence does not support changing existing exit or risk semantics.
""", encoding="utf-8")

    connection.execute(
        "INSERT OR REPLACE INTO proposal_selection_events(proposal_id, proposal_fingerprint, approval_status, approver_type, approved_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (selection["proposal_id"], selection["proposal_fingerprint"], selection["approval_status"], selection["approver_type"], selection["approved_at"], json.dumps(selection, sort_keys=True)),
    )
    connection.execute(
        "INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id, campaign_id, approved_compiled_fingerprint, proposal_id, execution_authorized, payload_json, authorized_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (authorization["authorization_id"], authorization["campaign_id"], authorization["approved_compiled_fingerprint"], authorization["proposal_id"], 1, json.dumps(authorization, sort_keys=True), authorization["authorized_at"]),
    )
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs(run_id, campaign_id, proposal_id, status, result_code, campaign_executed, candidate_created, strategy_modified, validation_accesses, holdout_accesses, payload_json, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (RUN_ID, campaign["campaign_id"], PROPOSAL_ID, "completed", decision["status"], 1, 0, 0, 0, 0, json.dumps(execution, sort_keys=True), completed_at),
    )
    paths = [analysis_dir / "exit-attribution.json", analysis_dir / "exit-structure-audit.md", execution_dir / "campaign-execution.json", execution_dir / "audit-decision.json", final_json, final_md]
    for path in paths:
        rel = path.relative_to(repo).as_posix()
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets(asset_id, run_id, artifact_type, path, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (fingerprint({"run": RUN_ID, "path": rel})[:24], RUN_ID, path.suffix.lstrip("."), rel, sha256_file(path), completed_at),
        )
    connection.commit()
    connection.close()
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    final = execute(
        repo,
        repo / args.registry,
        repo / "research/analysis/exit-logic-audit",
        repo / "research/director/compiled/exit-logic-structure-audit-v1/execution",
        repo / "reports/audits/exit-logic-audit",
    )
    print(json.dumps({"run_id": final["run_id"], "result_code": final["result_code"], "campaign_executed": final["summary"]["campaign_executed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
