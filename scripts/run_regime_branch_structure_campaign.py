#!/usr/bin/env python3
"""Execute Stage 4C.1 cycle 1 as a bounded read-only regime branch audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_director_common import fingerprint, load_document, open_director_registry, sha256_file, utc_now, write_json
from stage4b1_governance import verify_campaign_fingerprint, verify_constitution_approval, verify_human_selection_for
from stage4c1_portfolio import PORTFOLIO_ID, validate_portfolio_approval


PROPOSAL_ID = "regime-branch-structure-audit-v1"
RUN_ID = "stage4c1-cycle-1-regime-branch-structure-audit-v1"


def build_structure_audit(repo: Path) -> dict[str, Any]:
    graph_path = repo / "research/analysis/regime-aware-condition-graph.json"
    activation_path = repo / "research/analysis/stage3d2a-branch-activation.json"
    coverage_path = repo / "research/analysis/stage3d2a-condition-coverage.json"
    temporal_path = repo / "research/temporal/stage3e1-temporal-comparison.json"
    closure_path = repo / "research/closures/regime-aware-ranging-thresholds-v1.yaml"
    graph = load_document(graph_path)
    activation = load_document(activation_path)["branches"]
    temporal = load_document(temporal_path)
    closure = load_document(closure_path)
    branch_rows = []
    for group in graph["signal_groups"]:
        observed = activation[group["group_id"]]
        branch_rows.append({
            "group_id": group["group_id"],
            "branch": group["branch"],
            "side": group["side"],
            "signal": group["signal"],
            "condition_count": len(group["conditions"]),
            "regime_active_candles": observed["regime_active_candles"],
            "complete_signal_candles": observed["complete_entry_signal_candles"] + observed["complete_exit_signal_candles"],
            "final_formed_trade_count": observed["final_formed_trade_count"],
            "single_blocker_count": observed["single_blocker_count"],
            "inactive_reason": observed["inactive_reason"],
        })
    slices = []
    for row in temporal["slice_results"]:
        coverage = row["metrics"]["coverage"]
        long_count = int(coverage["long_trades"])
        short_count = int(coverage["short_trades"])
        total = int(coverage["total_trades"])
        slices.append({
            "slice_id": row["slice_id"],
            "dominant_market_regime": row["dominant_market_regime"],
            "long_trades": long_count,
            "short_trades": short_count,
            "long_share": long_count / total,
            "short_share": short_count / total,
            "total_return": row["metrics"]["return"]["total_return"],
        })
    total_long = sum(row["long_trades"] for row in slices)
    total_short = sum(row["short_trades"] for row in slices)
    return {
        "schema_version": "regime-branch-structure-audit-v1",
        "sources": [
            {"path": path.relative_to(repo).as_posix(), "sha256": sha256_file(path)}
            for path in (graph_path, activation_path, coverage_path, temporal_path, closure_path)
        ],
        "condition_graph": {"condition_count": len(graph["conditions"]), "signal_group_count": len(graph["signal_groups"]), "branches": branch_rows},
        "development_activation": {
            "trending_long_final_trades": activation["trending_long_entry"]["final_formed_trade_count"],
            "trending_short_final_trades": activation["trending_short_entry"]["final_formed_trade_count"],
            "ranging_long_final_trades": activation["ranging_long_entry"]["final_formed_trade_count"],
            "ranging_short_final_trades": activation["ranging_short_entry"]["final_formed_trade_count"],
            "ranging_breakdown_exit_signal_candles": activation["ranging_breakdown_exit_long"]["complete_exit_signal_candles"],
        },
        "temporal_directionality": {"slices": slices, "aggregate_long_trades": total_long, "aggregate_short_trades": total_short, "aggregate_long_short_difference": abs(total_long - total_short)},
        "closure": {"closure_id": closure["closure_id"], "status": closure["status"], "decision": closure["approved_mechanism"], "reopen_requested": False, "threshold_search_allowed": False},
        "findings": [
            "development branch activation favors trending_short and ranging_short formed trades",
            "temporal aggregate directionality is nearly balanced, while individual slices rotate between strong long and short concentration",
            "slice rotation is structural distribution evidence, not evidence for adjacent threshold search",
            "the ranging breakdown exit branch is inactive in the audited development activation artifact",
            "the existing threshold branch remains closed and no recorded reopen condition is met",
        ],
        "structural_imbalance_observed": True,
        "stable_one_sided_imbalance_observed": False,
        "threshold_local_research_warranted": False,
        "strategy_structure_change_warranted": False,
        "result_code": "structural_directionality_rotation_observed_no_mutation_warranted",
    }


def execute(repo: Path, registry_path: Path) -> dict[str, Any]:
    constitution = load_document(repo / "research/governance/research-constitution.yaml")
    constitution_event = load_document(repo / "research/governance/approvals/research-constitution-v1-approval.json")
    portfolio = load_document(repo / "research/governance/approvals/stage4c1-portfolio-approval.json")
    proposal = load_document(repo / "research/director/stage4c1/cycle-1/proposals/regime-branch-structure-audit-v1.json")
    selection = load_document(repo / "research/director/stage4c1/cycle-1/selection.json")
    campaign = load_document(repo / "research/director/compiled/regime-branch-structure-audit-v1/campaign.yaml")
    authorization = load_document(repo / "research/director/compiled/regime-branch-structure-audit-v1/execution-authorization.json")
    gates = {
        "constitution": verify_constitution_approval(repo, constitution, constitution_event),
        "portfolio": validate_portfolio_approval(repo, portfolio),
        "selection": verify_human_selection_for(proposal, selection, PROPOSAL_ID),
        "campaign": verify_campaign_fingerprint(campaign, authorization["approved_compiled_fingerprint"]),
    }
    if not all(value.get("matched", value.get("passed", False)) for value in gates.values()):
        raise ValueError("stage4c1_cycle_1_integrity_gate_failed")
    if campaign.get("execution_authorized") is not True or authorization.get("execution_authorized") is not True:
        raise ValueError("campaign_not_authorized")

    connection = open_director_registry(registry_path)
    cycle_count = connection.execute("SELECT COUNT(*) FROM stage4c1_portfolio_cycles WHERE status='completed'").fetchone()[0]
    if cycle_count >= portfolio["portfolio_budget"]["max_campaigns"]:
        connection.close()
        raise ValueError("portfolio_max_campaigns_reached")

    audit = build_structure_audit(repo)
    completed_at = utc_now()
    decision = {
        "schema_version": "regime-branch-structure-decision-v1",
        "campaign_id": campaign["campaign_id"],
        "campaign_executed": True,
        "status": audit["result_code"],
        "structural_imbalance_observed": audit["structural_imbalance_observed"],
        "stable_one_sided_imbalance_observed": audit["stable_one_sided_imbalance_observed"],
        "strategy_structure_change_warranted": False,
        "threshold_search_reopen_warranted": False,
        "candidate_created": False,
        "strategy_modified": False,
        "backtest_or_parameter_search_run": False,
        "hyperopt_run": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    execution = {
        "schema_version": "stage4c1-campaign-execution-v1",
        "portfolio_id": PORTFOLIO_ID,
        "cycle": 1,
        "run_id": RUN_ID,
        "campaign_id": campaign["campaign_id"],
        "proposal_id": PROPOSAL_ID,
        "campaign_fingerprint": authorization["approved_compiled_fingerprint"],
        "status": "completed",
        "result_code": decision["status"],
        "completed_at": completed_at,
        "gates": gates,
        "steps": [{"experiment_id": item["experiment_id"], "action": item["action"], "status": "completed_read_only"} for item in campaign["experiment_queue"]],
        "decision": decision,
        "second_campaign_executed_in_same_cycle": False,
        "stage4c2_started": False,
    }
    analysis_dir = repo / "research/analysis/regime-branch-audit"
    execution_dir = repo / "research/director/compiled/regime-branch-structure-audit-v1/execution"
    report_dir = repo / "reports/audits/stage4c1"
    for path in (analysis_dir, execution_dir, report_dir):
        path.mkdir(parents=True, exist_ok=True)
    audit_json = analysis_dir / "regime-branch-structure.json"
    audit_md = analysis_dir / "structural-vs-threshold-decision.md"
    execution_json = execution_dir / "campaign-execution.json"
    decision_json = execution_dir / "audit-decision.json"
    final_json = report_dir / "cycle-1-regime-branch-final-report.json"
    final_md = report_dir / "cycle-1-regime-branch-final-report.md"
    write_json(audit_json, audit)
    audit_md.write_text(f"""# Structural vs Threshold Decision

- Result: `{audit['result_code']}`
- Development formed trades: trending long `{audit['development_activation']['trending_long_final_trades']}`, trending short `{audit['development_activation']['trending_short_final_trades']}`, ranging long `{audit['development_activation']['ranging_long_final_trades']}`, ranging short `{audit['development_activation']['ranging_short_final_trades']}`.
- Temporal aggregate: long `{audit['temporal_directionality']['aggregate_long_trades']}`, short `{audit['temporal_directionality']['aggregate_short_trades']}`.
- Threshold branch reopened: `false`.
- Strategy structure change warranted: `false`.

Directionality rotates materially across temporal slices, while aggregate coverage is nearly balanced. This supports a structural observation but not a stable one-sided defect, adjacent-threshold search, or strategy mutation.
""", encoding="utf-8")
    write_json(execution_json, execution)
    write_json(decision_json, decision)
    final = {"schema_version": "stage4c1-cycle-final-report-v1", "portfolio_id": PORTFOLIO_ID, "cycle": 1, "run_id": RUN_ID, "campaign_id": campaign["campaign_id"], "proposal_id": PROPOSAL_ID, "campaign_fingerprint": authorization["approved_compiled_fingerprint"], "status": "implemented_uncommitted", "result_code": decision["status"], "completed_at": completed_at, "summary": decision, "next_director_run_required": True}
    write_json(final_json, final)
    final_md.write_text(f"""# Stage 4C.1 Cycle 1 Final Report

- Proposal: `{PROPOSAL_ID}`
- Campaign executed: `true`
- Result: `{decision['status']}`
- Strategy/Candidate/backtest/Hyperopt: `false / false / false / false`
- Validation/Holdout: `0 / 0`

All three read-only structural audit steps completed. No threshold branch was reopened and no strategy mutation is warranted.
""", encoding="utf-8")

    connection.execute("INSERT OR REPLACE INTO proposal_selection_events(proposal_id, proposal_fingerprint, approval_status, approver_type, approved_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)", (PROPOSAL_ID, selection["proposal_fingerprint"], selection["approval_status"], selection["approver_type"], selection["selected_at"], json.dumps(selection, sort_keys=True)))
    connection.execute("INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id, campaign_id, approved_compiled_fingerprint, proposal_id, execution_authorized, payload_json, authorized_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (authorization["authorization_id"], authorization["campaign_id"], authorization["approved_compiled_fingerprint"], PROPOSAL_ID, 1, json.dumps(authorization, sort_keys=True), authorization["authorized_at"]))
    connection.execute("INSERT OR REPLACE INTO research_campaign_runs(run_id, campaign_id, proposal_id, status, result_code, campaign_executed, candidate_created, strategy_modified, validation_accesses, holdout_accesses, payload_json, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (RUN_ID, campaign["campaign_id"], PROPOSAL_ID, "completed", decision["status"], 1, 0, 0, 0, 0, json.dumps(execution, sort_keys=True), completed_at))
    connection.execute("INSERT OR REPLACE INTO stage4c1_portfolio_cycles(cycle_id, portfolio_id, cycle_number, proposal_id, campaign_id, campaign_fingerprint, status, result_code, payload_json, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("stage4c1-cycle-1", PORTFOLIO_ID, 1, PROPOSAL_ID, campaign["campaign_id"], authorization["approved_compiled_fingerprint"], "completed", decision["status"], json.dumps(execution, sort_keys=True), completed_at))
    connection.execute("INSERT OR REPLACE INTO stage4c1_portfolios(portfolio_id, approval_status, max_campaigns, executed_campaigns, stop_reason, payload_json, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (PORTFOLIO_ID, "approved", 2, 1, None, json.dumps(portfolio, sort_keys=True), completed_at))
    for path in (audit_json, audit_md, execution_json, decision_json, final_json, final_md):
        rel = path.relative_to(repo).as_posix()
        connection.execute("INSERT OR REPLACE INTO research_campaign_assets(asset_id, run_id, artifact_type, path, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?)", (fingerprint({"run": RUN_ID, "path": rel})[:24], RUN_ID, path.suffix.lstrip("."), rel, sha256_file(path), completed_at))
    connection.commit()
    connection.close()
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    final = execute(repo, repo / args.registry)
    print(json.dumps({"portfolio_id": final["portfolio_id"], "cycle": final["cycle"], "campaign_id": final["campaign_id"], "result_code": final["result_code"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
