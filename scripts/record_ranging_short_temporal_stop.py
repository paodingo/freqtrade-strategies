#!/usr/bin/env python3
"""Record an immutable temporal execution stop in the Research Registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from export_director_registry import export_registry
from research_director_common import open_director_registry, sha256_file, write_json


REGISTRY_PATH = Path("research/registry/stage4a-director.db")
REGISTRY_EXPORT_PATH = Path("research/director/registry-records.json")


def record_stop(
    repo: Path,
    *,
    approval_path: Path,
    stop_path: Path,
    asset_paths: list[Path],
    completed_at: str,
) -> dict[str, object]:
    approval = json.loads((repo / approval_path).read_text(encoding="utf-8"))
    stop = json.loads((repo / stop_path).read_text(encoding="utf-8"))
    run_id = f"ranging-short-temporal-review-v1-attempt-{approval['execution_attempt_id'].rsplit('-', 1)[-1]}"

    connection = open_director_registry(repo / REGISTRY_PATH)
    connection.execute(
        "INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id,campaign_id,approved_compiled_fingerprint,proposal_id,execution_authorized,payload_json,authorized_at) VALUES(?,?,?,?,?,?,?)",
        (
            approval["execution_attempt_id"],
            stop["campaign_id"],
            stop["campaign_fingerprint"],
            stop["proposal_id"],
            1,
            json.dumps(approval, sort_keys=True),
            completed_at,
        ),
    )
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs(run_id,campaign_id,proposal_id,status,result_code,campaign_executed,candidate_created,strategy_modified,validation_accesses,holdout_accesses,payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            stop["campaign_id"],
            stop["proposal_id"],
            "stopped",
            stop["reason_code"],
            1,
            0,
            0,
            stop["validation_accesses"],
            stop["holdout_accesses"],
            json.dumps(stop, sort_keys=True),
            completed_at,
        ),
    )
    for path in asset_paths:
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets(asset_id,run_id,artifact_type,path,sha256,created_at) VALUES(?,?,?,?,?,?)",
            (
                f"{run_id}:{path.as_posix()}",
                run_id,
                "campaign_stop_evidence",
                path.as_posix(),
                sha256_file(repo / path),
                completed_at,
            ),
        )
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise RuntimeError(f"registry_integrity_failed:{integrity}")

    write_json(repo / REGISTRY_EXPORT_PATH, export_registry(str(repo / REGISTRY_PATH)))
    return {
        "run_id": run_id,
        "status": "stopped",
        "result_code": stop["reason_code"],
        "asset_count": len(asset_paths),
        "registry_integrity": integrity,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--approval", required=True)
    parser.add_argument("--stop", required=True)
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--completed-at", required=True)
    args = parser.parse_args()
    result = record_stop(
        Path(args.repo).resolve(),
        approval_path=Path(args.approval),
        stop_path=Path(args.stop),
        asset_paths=[Path(item) for item in args.asset],
        completed_at=args.completed_at,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
