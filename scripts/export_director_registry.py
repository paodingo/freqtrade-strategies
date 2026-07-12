#!/usr/bin/env python3
"""Export Stage 4A Director Registry records without inventing execution results."""

from __future__ import annotations

import argparse
import json

from research_director_common import open_director_registry, write_json


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
)


def export_registry(path: str) -> dict[str, object]:
    connection = open_director_registry(path)
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    records = {
        table: [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')]
        for table in TABLES
    }
    connection.close()
    execution_results_recorded = bool(records.get("stage4b1_campaign_runs"))
    return {
        "schema_version": "research-director-registry-export-v1",
        "integrity": integrity,
        "execution_results_recorded": execution_results_recorded,
        "fabricated_execution_results_recorded": False,
        "tables": records,
        "counts": {table: len(rows) for table, rows in records.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="research/registry/research.db")
    parser.add_argument("--output", default="research/director/registry-records.json")
    args = parser.parse_args(argv)
    payload = export_registry(args.registry)
    write_json(args.output, payload)
    print(json.dumps({"output": args.output, "integrity": payload["integrity"], "counts": payload["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
