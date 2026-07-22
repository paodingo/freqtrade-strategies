#!/usr/bin/env python3
"""Export Stage 4A Director Registry records without inventing execution results."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from research_director_common import (
    KNOWLEDGE_TABLE_CONTRACTS,
    LEARNING_TABLE_CONTRACTS,
    open_director_registry,
    write_json,
)


TABLES = (
    "research_state_snapshots",
    "director_runs",
    "director_proposals",
    "director_rejections",
    "approval_routes",
    "compiled_campaigns",
    "constitution_approvals",
    "proposal_selection_events",
    "campaign_execution_authorizations",
    "stage4b1_campaign_runs",
    "stage4b1_readiness_assets",
    "research_campaign_runs",
    "research_campaign_assets",
    "stage4c1_portfolios",
    "stage4c1_portfolio_cycles",
    "research_discovery_runs",
    "research_discovery_ideas",
    "research_discovery_critiques",
    "research_discovery_shortlists",
    "research_discovery_approvals",
    "research_discovery_handoffs",
    "research_discovery_events",
    "open_source_knowledge_sources",
    "open_source_strategy_patterns",
    "open_source_research_lessons",
    "open_source_knowledge_lineage",
    "research_supervisor_locks",
    "research_supervisor_runs",
    "research_supervisor_run_events",
    "research_review_sla_events",
    "research_worker_jobs",
    "research_descriptive_execution_results",
    "research_lesson_feedback_drafts",
    "research_knowledge_lifecycle",
    "research_knowledge_update_proposals",
    "research_knowledge_review_events",
    "research_lesson_curation_candidates",
)


def export_connection(connection: object) -> dict[str, object]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    records = {
        table: [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')]
        for table in TABLES
    }
    execution_results_recorded = bool(records.get("stage4b1_campaign_runs"))
    return {
        "schema_version": "research-director-registry-export-v1",
        "integrity": integrity,
        "execution_results_recorded": execution_results_recorded,
        "fabricated_execution_results_recorded": False,
        "tables": records,
        "counts": {table: len(rows) for table, rows in records.items()},
    }


def export_registry(path: str) -> dict[str, object]:
    connection = open_director_registry(path)
    try:
        return export_connection(connection)
    finally:
        connection.close()


def merge_knowledge_tables(
    base_payload: dict[str, object],
    registry_payload: dict[str, object],
) -> dict[str, object]:
    """Merge only knowledge tables while preserving authoritative research history."""
    merged = json.loads(json.dumps(base_payload))
    merged_tables = merged.setdefault("tables", {})
    merged_counts = merged.setdefault("counts", {})
    registry_tables = registry_payload["tables"]
    for table in {**KNOWLEDGE_TABLE_CONTRACTS, **LEARNING_TABLE_CONTRACTS}:
        rows = registry_tables[table]
        merged_tables[table] = rows
        merged_counts[table] = len(rows)
    if "research_campaign_runs" in merged_tables:
        base_feedback_by_run = {
            row["run_id"]: row
            for row in base_payload.get("tables", {}).get("research_lesson_feedback_drafts", [])
        }
        local_feedback_by_run = {
            row["run_id"]: row
            for row in registry_tables["research_lesson_feedback_drafts"]
        }
        feedback_by_run = {**base_feedback_by_run, **local_feedback_by_run}
        for row in merged_tables["research_campaign_runs"]:
            if row["status"] != "completed":
                continue
            feedback_by_run.setdefault(row["run_id"], {
                "feedback_id": row["run_id"],
                "run_id": row["run_id"],
                "campaign_id": row["campaign_id"],
                "proposal_id": row["proposal_id"],
                "result_code": row["result_code"],
                "review_status": "pending_human_review",
                "payload_json": row["payload_json"],
                "created_at": row["completed_at"],
            })
        feedback_rows = list(feedback_by_run.values())
        feedback_rows.sort(key=lambda row: row["feedback_id"])
        merged_tables["research_lesson_feedback_drafts"] = feedback_rows
        merged_counts["research_lesson_feedback_drafts"] = len(feedback_rows)
    merged["integrity"] = registry_payload["integrity"]
    merged["execution_results_recorded"] = bool(merged_tables.get("stage4b1_campaign_runs"))
    merged["fabricated_execution_results_recorded"] = False
    return merged


def read_export_from_git_ref(output: str, ref: str) -> dict[str, object]:
    root = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            encoding="utf-8",
        ).strip()
    )
    relative_output = Path(output).resolve().relative_to(root.resolve()).as_posix()
    raw = subprocess.check_output(
        ["git", "show", f"{ref}:{relative_output}"],
        text=True,
        encoding="utf-8",
    )
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="research/registry/research.db")
    parser.add_argument("--output", default="research/director/registry-records.json")
    parser.add_argument(
        "--merge-knowledge-into-ref",
        metavar="GIT_REF",
        help="preserve all non-knowledge tables from this Git ref and replace only knowledge tables",
    )
    args = parser.parse_args(argv)
    payload = export_registry(args.registry)
    if args.merge_knowledge_into_ref:
        base_payload = read_export_from_git_ref(args.output, args.merge_knowledge_into_ref)
        payload = merge_knowledge_tables(base_payload, payload)
    write_json(args.output, payload)
    print(json.dumps({"output": args.output, "integrity": payload["integrity"], "counts": payload["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
