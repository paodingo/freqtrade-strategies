#!/usr/bin/env python3
"""Build, hydrate, and verify the minimal portable baseline fixture pack."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
from pathlib import Path
from typing import Any

from research_control import load_simple_yaml


CONTRACT = Path("research/testing/portable-baseline-fixture-contract.yaml")
COMMITTED_PACK = Path("tests/fixtures/portable-baseline")
HYDRATED_PACK = Path("research/testing/fixture-packs/portable-baseline-v1")
MANIFEST_NAME = "manifest.json"
ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|(?:^|[\"'])/[A-Za-z0-9_.-]+/)")
SENSITIVE = re.compile(r"(?i)(?:api[_-]?key|secret|password|proxy[_-]?auth|account[_-]?id)\s*[:=]\s*[\"']?[^\s\"']+")


class PortableFixtureError(RuntimeError):
    def __init__(self, reason_code: str, detail: str):
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def load_contract(root: Path) -> dict[str, Any]:
    path = root / CONTRACT
    text = path.read_text(encoding="utf-8-sig")
    contract = json.loads(text) if text.lstrip().startswith("{") else load_simple_yaml(path)
    if contract.get("contract_id") != "portable-baseline-fixtures-v1":
        raise PortableFixtureError("portable_baseline_contract_invalid", "unexpected contract_id")
    return contract


def _assert_plain_directory(path: Path) -> None:
    if _is_link_like(path):
        raise PortableFixtureError("portable_baseline_symlink_forbidden", str(path))
    current = path
    while current.exists() and current != current.parent:
        if _is_link_like(current):
            raise PortableFixtureError("portable_baseline_symlink_forbidden", str(current))
        current = current.parent


def _is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.stat(), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except FileNotFoundError:
        return False


def _source_file(root: Path, relative: str, expected_sha: str) -> Path:
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise PortableFixtureError("portable_baseline_source_missing", relative)
    actual = sha256_file(path)
    if actual != expected_sha:
        raise PortableFixtureError("portable_baseline_source_hash_mismatch", f"{relative}: {actual}")
    return path


def _v1_projection(source: Path, item: dict[str, Any]) -> dict[str, Any]:
    manifest = load_simple_yaml(_source_file(source, item["source_artifact"], item["source_sha256"]))
    records = []
    for row in manifest["files"]:
        path = source / row["path"]
        ok = path.is_file() and path.stat().st_size == row["bytes"] and sha256_file(path) == row["sha256"]
        if not ok:
            raise PortableFixtureError("portable_baseline_source_hash_mismatch", row["path"])
        records.append({"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"], "verified": True})
    return {
        "schema_version": "portable-stage3c2-v1-integrity-v1",
        "dataset_id": manifest["dataset_id"],
        "evaluation_readiness": manifest["evaluation_readiness"],
        "files": records,
        "source_files_verified": True,
    }


def _registry_projection(source: Path, item: dict[str, Any]) -> dict[str, Any]:
    database = _source_file(source, item["source_artifact"], item["source_sha256"])
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        queries = {
            "stage3c2p_provisioning_events": "SELECT * FROM stage3c2p_provisioning_events WHERE event_id='stage3c2p-provisioning'",
            "split_policy_decision_events": "SELECT * FROM split_policy_decision_events WHERE event_id='stage3c2p-human-split-policy-decision'",
            "dataset_readiness": "SELECT * FROM dataset_readiness",
            "split_v2_records": "SELECT * FROM split_v2_records",
            "evaluation_readiness_probes": "SELECT * FROM evaluation_readiness_probes",
            "policy_proposals": "SELECT * FROM policy_proposals",
            "policy_approval_events": "SELECT * FROM policy_approval_events",
            "stage3c3_readiness": "SELECT * FROM stage3c3_readiness",
            "provisioning_blockers": "SELECT * FROM provisioning_blockers",
            "evaluation_artifact_refs": "SELECT * FROM evaluation_artifact_refs",
            "stage3d4b_mechanism_approval_events": "SELECT * FROM stage3d4b_mechanism_approval_events",
            "stage3d4b_branch_closure_events": "SELECT * FROM stage3d4b_branch_closure_events",
            "stage3d4b_variable_governance_events": "SELECT * FROM stage3d4b_variable_governance_events",
        }
        tables: dict[str, Any] = {}
        for table, query in queries.items():
            cursor = connection.execute(query)
            columns = [row[0] for row in cursor.description]
            create_sql = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
            tables[table] = {"create_sql": create_sql, "columns": columns, "rows": [list(row) for row in cursor.fetchall()]}
    finally:
        connection.close()
    return {"schema_version": "portable-registry-rows-v1", "tables": tables}


def _d3b_projection(source: Path, item: dict[str, Any]) -> dict[str, Any]:
    final = json.loads(_source_file(source, item["source_artifact"], item["source_sha256"]).read_text(encoding="utf-8"))
    experiments = []
    identities = []
    for experiment in final["experiments"]:
        projected = {key: experiment[key] for key in ("experiment_id", "new_value", "attribution", "final_validity", "reproducibility")}
        for run_name in ("run_a", "run_b"):
            run = experiment[run_name]
            identity_path = source / run["runtime_identity"]
            worker_path = source / run["run_dir"] / "isolated-worker-result.json"
            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            worker = json.loads(worker_path.read_text(encoding="utf-8"))
            dependency = Path(identity["dependency_module_file"])
            dependency_ok = dependency.is_file() and sha256_file(dependency) == identity["dependency_source_sha256"]
            if not dependency_ok:
                raise PortableFixtureError("portable_baseline_source_hash_mismatch", str(dependency))
            projected[run_name] = {
                "process_id": run["process_id"],
                "dependency_source_sha256": run["dependency_source_sha256"],
                "dependency_identity": f"experiment-{experiment['experiment_id']}",
                "worker": {"backtest_count": worker["backtest_count"], "claimed_next_experiment": worker["claimed_next_experiment"], "registry_modified": worker["registry_modified"]},
            }
            identities.append({
                "experiment_id": experiment["experiment_id"],
                "foreign_candidate_modules": identity["foreign_candidate_modules"],
                "mutation_proof": {
                    "loaded_ast_value": identity["mutation_proof"]["loaded_ast_value"],
                    "mutation_count": identity["mutation_proof"]["mutation_count"],
                },
                "backtest_started": identity["backtest_started"],
                "dependency_source_sha256": identity["dependency_source_sha256"],
                "dependency_source_verified": True,
            })
        experiments.append(projected)
    return {
        "schema_version": "portable-stage3d3b-summary-v1",
        "status": final["status"],
        "all_worker_pids_unique": final["all_worker_pids_unique"],
        "worker_pids": final["worker_pids"],
        "order_independence_passed": final["order_independence_passed"],
        "reverse_order_samples": [{"consistent": row["consistent"]} for row in final["reverse_order_samples"]],
        "validation_access_allowed": final["validation_access_allowed"],
        "validation_access_count": final["validation_access_count"],
        "forbidden_actions": final["forbidden_actions"],
        "experiments": experiments,
        "identities": identities,
    }


def _d4b_projection(source: Path, item: dict[str, Any]) -> dict[str, Any]:
    closure = load_simple_yaml(_source_file(source, item["source_artifact"], item["source_sha256"]))
    verified = []
    for relative, expected in closure["historical_artifact_integrity"].items():
        path = source / relative
        actual = sha256_file(path)
        if actual.lower() != expected.lower():
            blob = subprocess.run(
                ["git", "-C", str(source), "show", f"HEAD:{relative}"],
                capture_output=True,
                check=False,
            )
            if blob.returncode == 0:
                actual = sha256_bytes(blob.stdout)
        if actual.lower() != expected.lower():
            raise PortableFixtureError("portable_baseline_source_hash_mismatch", relative)
        verified.append({"path": relative, "sha256": expected.lower(), "verified": True})
    return {"schema_version": "portable-stage3d4b-integrity-v1", "historical_artifacts": verified, "historical_artifacts_modified": False}


def _e1_projection(source: Path, item: dict[str, Any]) -> dict[str, Any]:
    final = json.loads(_source_file(source, item["source_artifact"], item["source_sha256"]).read_text(encoding="utf-8"))
    results = []
    for row in final["results"]:
        projected = {"slice_id": row["slice_id"], "reproducibility": row["reproducibility"]}
        for run_name in ("run_a", "run_b"):
            run = row[run_name]
            identity = json.loads((source / run["runtime_identity"]).read_text(encoding="utf-8"))
            projected[run_name] = {
                "process_id": run["process_id"],
                "normalized_trade_hash": run["normalized_trade_hash"],
                "metrics": {"internal_stability": {
                    "weekly_returns": [],
                    "rolling_28_day_returns": [],
                    "regime_results": {},
                }},
                "identity": {"candidate_modules": identity["candidate_modules"], "related_sys_modules": identity["related_sys_modules"]},
            }
        results.append(projected)
    profiles = {}
    snapshots = {}
    for row in load_simple_yaml(source / "research/temporal/stage3e1-slices.yaml")["slices"]:
        profile = json.loads((source / "research/temporal/profiles" / f"{row['slice_id']}-market-profile.json").read_text(encoding="utf-8"))
        profiles[row["slice_id"]] = {
            "strategy_independent": profile["strategy_independent"],
            "uses_strategy_results": profile["uses_strategy_results"],
        }
        manifest = load_simple_yaml(source / "research/temporal/snapshots" / row["dataset_id"] / "manifest.yaml")
        snapshots[row["dataset_id"]] = {"sealed": manifest["sealed"], "suitable_for_candidate_tuning": manifest["suitable_for_candidate_tuning"], "evaluation_range": manifest["evaluation_range"]}
    return {"schema_version": "portable-stage3e1-summary-v1", "governance": final["governance"], "results": results, "profiles": profiles, "snapshots": snapshots}


PROJECTIONS = {
    "stage3c2_v1": _v1_projection,
    "registry_rows": _registry_projection,
    "stage3d3b": _d3b_projection,
    "stage3d4b": _d4b_projection,
    "stage3e1": _e1_projection,
}


def build(repo: Path, source: Path, output: Path) -> dict[str, Any]:
    contract = load_contract(repo)
    _assert_plain_directory(source)
    head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    if head != contract["source_checkpoint"]:
        raise PortableFixtureError("portable_baseline_source_checkpoint_mismatch", head)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    records = []
    for item in contract["fixtures"]:
        target = output / item["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if item["extraction"] == "copy":
            data = _source_file(source, item["source_artifact"], item["source_sha256"]).read_bytes()
        else:
            data = canonical_bytes(PROJECTIONS[item["extraction"]](source, item))
        target.write_bytes(data)
        records.append({
            "fixture_id": item["fixture_id"], "path": item["target"], "bytes": len(data),
            "sha256": sha256_bytes(data), "semantic_fingerprint": sha256_bytes(data),
            "source_artifact": item["source_artifact"], "source_sha256": item["source_sha256"],
            "committed": True, "external_ignored_pack": True, "readonly_required": True,
        })
    manifest = {"schema_version": "portable-baseline-fixture-pack-v1", "contract_id": contract["contract_id"], "source_checkpoint": head, "files": records}
    (output / MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
    return manifest


def verify(pack: Path, require_readonly: bool = True) -> dict[str, Any]:
    _assert_plain_directory(pack)
    manifest_path = pack / MANIFEST_NAME
    if not manifest_path.is_file():
        raise PortableFixtureError("portable_baseline_fixture_pack_missing", str(pack))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = {MANIFEST_NAME}
    for record in manifest["files"]:
        relative = record["path"]
        declared.add(Path(relative).as_posix())
        path = pack / relative
        if not path.is_file() or path.is_symlink():
            raise PortableFixtureError("portable_baseline_fixture_missing", relative)
        data = path.read_bytes()
        if len(data) != record["bytes"] or sha256_bytes(data) != record["sha256"]:
            raise PortableFixtureError("portable_baseline_fixture_hash_mismatch", relative)
        if record.get("semantic_fingerprint") != sha256_bytes(data):
            raise PortableFixtureError("portable_baseline_fixture_semantic_mismatch", relative)
        text = data.decode("utf-8", errors="ignore")
        if ABSOLUTE_PATH.search(text):
            raise PortableFixtureError("portable_baseline_absolute_path_forbidden", relative)
        if SENSITIVE.search(text):
            raise PortableFixtureError("portable_baseline_sensitive_material", relative)
        if require_readonly and os.access(path, os.W_OK):
            mode = path.stat().st_mode
            if mode & stat.S_IWUSR:
                raise PortableFixtureError("portable_baseline_fixture_not_readonly", relative)
    actual = {p.relative_to(pack).as_posix() for p in pack.rglob("*") if p.is_file()}
    extra = sorted(actual - declared)
    if extra:
        raise PortableFixtureError("portable_baseline_fixture_extra_file", extra[0])
    return {"status": "passed", "pack": str(pack), "file_count": len(manifest["files"]), "manifest_sha256": sha256_file(manifest_path)}


def hydrate(repo: Path, target: Path) -> dict[str, Any]:
    source = repo / COMMITTED_PACK
    verify(source, require_readonly=False)
    _assert_plain_directory(target)
    if target.exists():
        result = verify(target, require_readonly=True)
        result["source_pack"] = str(COMMITTED_PACK)
        result["existing_pack_reused"] = True
        return result
    target.mkdir(parents=True)
    for path in source.rglob("*"):
        if path.is_file():
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            destination.chmod(stat.S_IREAD)
    result = verify(target, require_readonly=True)
    result["source_pack"] = str(COMMITTED_PACK)
    return result
