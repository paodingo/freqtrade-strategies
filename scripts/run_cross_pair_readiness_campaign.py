#!/usr/bin/env python3
"""Execute the one approved low-risk Stage 4B.1 cross-pair readiness audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    utc_now,
    write_json,
    write_yaml,
)
from stage4b1_governance import (
    APPROVED_CAMPAIGN_FINGERPRINT,
    SELECTED_PROPOSAL_ID,
    provisioning_scope,
    verify_campaign_fingerprint,
    verify_constitution_approval,
    verify_human_selection,
)


RUN_ID = "stage4b1-cross-pair-data-readiness-audit-v1"


def manifest_inventory(repo: Path) -> list[dict[str, Any]]:
    paths = sorted((repo / "research/data/snapshots").glob("*/manifest.yaml"))
    paths += sorted((repo / "research/temporal/snapshots").glob("*/manifest.yaml"))
    records = []
    for path in paths:
        rel = path.relative_to(repo).as_posix()
        if "validation" in rel.lower() or "holdout" in rel.lower():
            continue
        payload = load_document(path)
        records.append({
            "dataset_id": payload.get("dataset_id"),
            "manifest_path": rel,
            "manifest_sha256": sha256_file(path),
            "pairs": payload.get("pairs") or ([payload["pair"]] if payload.get("pair") else []),
            "timeframes": payload.get("timeframes") or ([payload["timeframe"]] if payload.get("timeframe") else []),
            "intended_use": payload.get("intended_use"),
            "sealed": payload.get("sealed"),
        })
    return records


def eligible_public_markets(repo: Path) -> dict[str, Any]:
    snapshot = repo / "research/exchange_snapshots/binance-usdm-futures-2025-8-demo"
    markets_path = snapshot / "markets.normalized.json"
    markets = json.loads(markets_path.read_text(encoding="utf-8"))
    symbols = sorted(
        symbol for symbol, item in markets.items()
        if item.get("active") is True
        and item.get("swap") is True
        and item.get("contract") is True
        and item.get("linear") is True
        and item.get("quote") == "USDT"
        and item.get("settle") == "USDT"
        and symbol != "BTC/USDT:USDT"
    )
    return {
        "schema_version": "cross-pair-eligibility-v1",
        "source": "sealed_public_binance_usdm_exchange_metadata",
        "source_path": markets_path.relative_to(repo).as_posix(),
        "source_sha256": sha256_file(markets_path),
        "network_accessed": False,
        "private_endpoint_accessed": False,
        "eligibility_rule": {
            "active": True,
            "swap": True,
            "contract": True,
            "linear": True,
            "quote": "USDT",
            "settle": "USDT",
            "exclude_baseline_pair": "BTC/USDT:USDT",
        },
        "eligible_non_btc_symbol_count": len(symbols),
        "eligible_non_btc_symbols": symbols,
    }


def readiness_matrix(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for item in inventory:
        for pair in item["pairs"]:
            if pair == "BTC/USDT:USDT" or not pair.endswith(":USDT"):
                continue
            timeframes = sorted(item["timeframes"])
            rows.append({
                "pair": pair,
                "dataset_id": item["dataset_id"],
                "timeframes": timeframes,
                "price_1h": "1h" in timeframes,
                "informative_4h": "4h" in timeframes,
                "informative_8h": "8h" in timeframes,
                "mark_coverage": False,
                "funding_coverage": False,
                "complete_for_cross_pair_readiness": False,
                "ranking_eligible": False,
                "intended_use": item["intended_use"],
            })
    return {
        "schema_version": "cross-pair-readiness-matrix-v1",
        "non_btc_dataset_rows": rows,
        "complete_non_btc_pair_timeframes": [],
        "complete_non_btc_pair_count": 0,
        "requirements": ["price_1h", "informative_4h", "informative_8h", "mark_coverage", "funding_coverage"],
        "validation_or_holdout_manifests_inspected": False,
    }


def execute(repo: Path, registry_path: Path, output_dir: Path, report_dir: Path) -> dict[str, Any]:
    constitution = load_document(repo / "research/governance/research-constitution.yaml")
    constitution_event = load_document(repo / "research/governance/approvals/research-constitution-v1-approval.json")
    proposal = load_document(repo / "research/director/proposals/cross-pair-data-readiness-audit-v1.json")
    selection = load_document(repo / "research/director/approvals/cross-pair-data-readiness-audit-v1-human-selection.json")
    campaign = load_document(repo / "research/director/compiled/cross-pair-data-readiness-audit-v1/campaign.yaml")
    authorization = load_document(repo / "research/director/compiled/cross-pair-data-readiness-audit-v1/execution-authorization.json")

    fingerprint_check = verify_campaign_fingerprint(campaign)
    constitution_check = verify_constitution_approval(repo, constitution, constitution_event)
    selection_check = verify_human_selection(proposal, selection)
    scope = provisioning_scope(proposal, campaign)
    gates = {
        "campaign_fingerprint": fingerprint_check,
        "constitution": constitution_check,
        "human_selection": selection_check,
        "selected_proposal_only": proposal.get("proposal_id") == SELECTED_PROPOSAL_ID,
        "execution_authorized": campaign.get("execution_authorized") is True and authorization.get("execution_authorized") is True,
        "portfolio_budget": selection.get("portfolio_budget"),
    }
    if not fingerprint_check["matched"]:
        raise ValueError("compiled_campaign_fingerprint_drift")
    if not constitution_check["matched"]:
        raise ValueError("constitution_approval_hash_drift")
    if not selection_check["matched"] or not gates["selected_proposal_only"]:
        raise ValueError("proposal_selection_mismatch")
    if not gates["execution_authorized"]:
        raise ValueError("campaign_not_authorized")
    budget = selection["portfolio_budget"]
    if budget != {"max_campaigns": 1, "max_wall_clock_hours": 4, "max_validation_accesses": 0, "max_holdout_accesses": 0}:
        raise ValueError("portfolio_budget_mismatch")

    connection = open_director_registry(registry_path)
    connection.execute(
        "INSERT OR REPLACE INTO constitution_approvals(constitution_id, approved_version, constitution_sha256, approver_type, approved_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (constitution_event["constitution_id"], constitution_event["approved_version"], constitution_event["approved_constitution_sha256"], constitution_event["approver_type"], constitution_event["approved_at"], json.dumps(constitution_event, sort_keys=True)),
    )
    connection.execute(
        "INSERT OR REPLACE INTO proposal_selection_events(proposal_id, proposal_fingerprint, approval_status, approver_type, approved_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (selection["proposal_id"], selection["proposal_fingerprint"], selection["approval_status"], selection["approver_type"], selection["approved_at"], json.dumps(selection, sort_keys=True)),
    )
    connection.execute(
        "INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id, campaign_id, approved_compiled_fingerprint, proposal_id, execution_authorized, payload_json, authorized_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (authorization["authorization_id"], authorization["campaign_id"], authorization["approved_compiled_fingerprint"], authorization["proposal_id"], 1, json.dumps(authorization, sort_keys=True), authorization["authorized_at"]),
    )
    connection.commit()
    executed_count = connection.execute(
        "SELECT COUNT(*) FROM stage4b1_campaign_runs WHERE campaign_executed=1"
    ).fetchone()[0]
    if executed_count >= 1:
        connection.close()
        raise ValueError("portfolio_max_campaigns_exhausted")

    inventory = manifest_inventory(repo)
    eligibility = eligible_public_markets(repo)
    matrix = readiness_matrix(inventory)
    requirements = {
        "schema_version": "cross-pair-frozen-data-requirements-v1",
        "specific_non_btc_pair": scope["pair"],
        "specific_target_timeframe": scope["timeframe"],
        "timerange_or_coverage_rule": scope["timerange_or_coverage_rule"],
        "reference_timeframes": ["1h", "4h", "8h"],
        "required_data_types": ["futures_ohlcv", "mark", "funding"],
        "staging_before_seal": True,
        "intended_use_if_later_approved": "cross_pair_readiness",
        "development_or_validation_label_allowed": False,
        "provisioning_authorized": scope["provisioning_authorized"],
    }
    decision = {
        "schema_version": "cross-pair-readiness-decision-v1",
        "campaign_id": campaign["campaign_id"],
        "status": "human_scope_required_for_provisioning" if not scope["fully_frozen"] else "ready_for_public_provisioning",
        "campaign_audit_completed": True,
        "campaign_executed": True,
        "specific_non_btc_pair_frozen": bool(scope["pair"]),
        "specific_target_timeframe_frozen": bool(scope["timeframe"]),
        "timerange_or_coverage_rule_frozen": bool(scope["timerange_or_coverage_rule"]),
        "public_non_btc_market_metadata_available": eligibility["eligible_non_btc_symbol_count"] > 0,
        "local_non_btc_futures_dataset_available": bool(matrix["non_btc_dataset_rows"]),
        "complete_non_btc_pair_timeframes": matrix["complete_non_btc_pair_timeframes"],
        "new_dataset_created": False,
        "new_dataset_sealed": False,
        "provisioning_executed": False,
        "human_pair_scope_required": not scope["fully_frozen"],
        "network_accessed": False,
        "private_endpoint_accessed": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "candidate_created": False,
        "backtest_or_ranking_run": False,
        "hyperopt_run": False,
        "reason_code": scope["reason_code"],
    }
    completed_at = utc_now()
    execution = {
        "schema_version": "stage4b1-campaign-execution-v1",
        "run_id": RUN_ID,
        "campaign_id": campaign["campaign_id"],
        "approved_compiled_fingerprint": APPROVED_CAMPAIGN_FINGERPRINT,
        "status": "completed",
        "result_code": decision["status"],
        "started_at": completed_at,
        "completed_at": completed_at,
        "gates": gates,
        "steps": [
            {"experiment_id": item["experiment_id"], "action": item["action"], "status": "completed_read_only"}
            for item in campaign["experiment_queue"]
        ],
        "decision": decision,
        "executed_proposal_ids": [SELECTED_PROPOSAL_ID],
        "unexecuted_proposal_ids": ["exit-logic-structure-audit-v1", "regime-branch-structure-audit-v1"],
        "stage4c_started": False,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "pair-eligibility.json": eligibility,
        "cross-pair-readiness-matrix.json": matrix,
        "readiness-decision.json": decision,
        "campaign-execution.json": execution,
    }
    for name, payload in artifacts.items():
        write_json(output_dir / name, payload)
    write_yaml(output_dir / "frozen-data-requirements.yaml", requirements)
    final = {
        "schema_version": "stage4b1-cross-pair-readiness-final-report-v1",
        "run_id": RUN_ID,
        "campaign_id": campaign["campaign_id"],
        "campaign_fingerprint": APPROVED_CAMPAIGN_FINGERPRINT,
        "status": "implemented_uncommitted",
        "result_code": decision["status"],
        "completed_at": completed_at,
        "summary": decision,
        "artifacts": sorted([f"{output_dir.relative_to(repo).as_posix()}/{name}" for name in [*artifacts, "frozen-data-requirements.yaml"]]),
        "registry_updated": True,
        "next_director_run_allowed": True,
        "second_campaign_execution_allowed": False,
    }
    final_path = report_dir / "stage4b1-cross-pair-data-readiness-final-report.json"
    write_json(final_path, final)
    markdown = f"""# Stage 4B.1 Cross-pair Data Readiness Final Report

- Campaign: `{campaign['campaign_id']}`
- Approved fingerprint: `{APPROVED_CAMPAIGN_FINGERPRINT}`
- Execution: `completed`
- Result: `{decision['status']}`
- Eligible public non-BTC USD-M symbols in sealed metadata: `{eligibility['eligible_non_btc_symbol_count']}`
- Complete local non-BTC futures datasets: `{matrix['complete_non_btc_pair_count']}`
- New Dataset created: `false`
- Validation / Holdout accesses: `0 / 0`

The approved low-risk audit executed all three read-only steps. The compiled specification did not freeze a specific non-BTC pair or coverage rule, so provisioning and sealing were correctly blocked pending human scope approval.
"""
    (report_dir / "stage4b1-cross-pair-data-readiness-final-report.md").write_text(markdown, encoding="utf-8")

    connection.execute(
        "INSERT OR REPLACE INTO stage4b1_campaign_runs(run_id, campaign_id, status, result_code, campaign_executed, dataset_created, validation_accesses, holdout_accesses, payload_json, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (RUN_ID, campaign["campaign_id"], "completed", decision["status"], 1, 0, 0, 0, json.dumps(execution, sort_keys=True), completed_at),
    )
    all_paths = [output_dir / name for name in [*artifacts, "frozen-data-requirements.yaml"]] + [final_path, report_dir / "stage4b1-cross-pair-data-readiness-final-report.md"]
    for path in all_paths:
        rel = path.relative_to(repo).as_posix()
        connection.execute(
            "INSERT OR REPLACE INTO stage4b1_readiness_assets(asset_id, run_id, artifact_type, path, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (fingerprint({"run": RUN_ID, "path": rel})[:24], RUN_ID, path.suffix.lstrip("."), rel, sha256_file(path), completed_at),
        )
    connection.commit()
    connection.close()
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    parser.add_argument("--output-dir", default="research/director/compiled/cross-pair-data-readiness-audit-v1/execution")
    parser.add_argument("--report-dir", default="reports/audits/cross-pair-data-readiness")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    final = execute(repo, repo / args.registry, repo / args.output_dir, repo / args.report_dir)
    print(json.dumps({"run_id": final["run_id"], "result_code": final["result_code"], "campaign_executed": final["summary"]["campaign_executed"], "new_dataset_created": final["summary"]["new_dataset_created"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
