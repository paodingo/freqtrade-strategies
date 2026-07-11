#!/usr/bin/env python3
"""Create an isolated, identity-only research strategy candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from research_control import load_campaign, load_simple_yaml, utc_now
from research_guard import PathGuardError, check_path
from run_experiment import dump_json, dump_manifest, git_sha, repo_rel, sha256_file


GENERATOR_VERSION = "stage3b1-candidate-generator-v1"
BASE_STRATEGY_NAME = "RegimeAwareV6"
BASE_STRATEGY_PATH = Path("strategies") / "RegimeAwareV6.py"
BASE_STRATEGY_SHA256 = "1A422F41AB801746C2EE39F5D20722B26B674098BCA6AC1684E78BD8E7285509"
EXPECTED_BASELINE_TRADE_HASH = "74c40da36d57d452066e39e0425a83ae1ddc73be8069c91d184dd6afa5c4e6ee"
DEPENDENCY_FILES = (
    "regime_aware_base.py",
    "regime_detector.py",
    "risk_manager.py",
)
FORBIDDEN_SOURCE_TOKENS = (
    ".env",
    "secrets/",
    "deploy/",
    "config_live",
    "configs/production",
    "start_bot",
    "refresh_data",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "api_key",
    "secret",
)


class CandidateError(RuntimeError):
    def __init__(self, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def candidate_class_name(campaign_id: str, experiment_id: str | int) -> str:
    text = str(experiment_id)
    match = re.search(r"(\d+)$", text)
    if match:
        number = int(match.group(1))
    else:
        number = int(hashlib.sha256(f"{campaign_id}:{text}".encode("utf-8")).hexdigest()[:6], 16) % 10000
    return f"RegimeAware_C3B1_E{number:04d}"


def candidate_root(repo_root: Path, campaign_id: str, experiment_id: str | int) -> Path:
    return repo_root / "research" / "candidates" / campaign_id / str(experiment_id)


def assert_no_symlink_escape(path: Path, anchor: Path) -> None:
    anchor = anchor.resolve(strict=False)
    current = anchor
    target = path.resolve(strict=False)
    try:
        target.relative_to(anchor)
    except ValueError as exc:
        raise CandidateError("guard_violation", "candidate_path_escape", f"path escapes candidate namespace: {path}") from exc
    for part in path.resolve(strict=False).relative_to(anchor).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise CandidateError("guard_violation", "candidate_symlink_escape", f"symlink not allowed in candidate path: {current}")


def validate_candidate_write_scope(repo_root: Path, campaign: dict, experiment_id: str | int, paths: list[Path]) -> None:
    root = candidate_root(repo_root, campaign["campaign_id"], experiment_id)
    assert_no_symlink_escape(root, repo_root / "research" / "candidates")
    expected_prefix = repo_rel(repo_root, root)
    for path in paths:
        repo_path = check_path(repo_root, campaign, path)
        if repo_path != expected_prefix and not repo_path.startswith(expected_prefix + "/"):
            raise PathGuardError(repo_path, "candidate write path is outside this experiment namespace")


def build_candidate_source(base_text: str, candidate_class: str) -> str:
    marker = f"class {BASE_STRATEGY_NAME}("
    if marker not in base_text:
        raise CandidateError("implementation_error", "base_strategy_class_missing", f"{BASE_STRATEGY_NAME} class declaration missing")
    source = base_text.replace(marker, f"class {candidate_class}(", 1)
    metadata = (
        f"    candidate_identity_metadata = {{\n"
        f"        \"generator_version\": \"{GENERATOR_VERSION}\",\n"
        f"        \"legacy_base_name\": \"{BASE_STRATEGY_NAME}\",\n"
        f"        \"semantic_role\": \"identity_only_candidate\",\n"
        f"    }}\n\n"
    )
    source = source.replace("    enable_ranging_entries = True\n", metadata + "    enable_ranging_entries = True\n", 1)
    return source


def expected_candidate_source(repo_root: Path, candidate_class: str) -> str:
    base_text = (repo_root / BASE_STRATEGY_PATH).read_text(encoding="utf-8")
    return build_candidate_source(base_text, candidate_class)


def semantic_diff_summary(repo_root: Path, candidate_file: Path, candidate_class: str) -> dict[str, Any]:
    expected = expected_candidate_source(repo_root, candidate_class)
    actual = candidate_file.read_text(encoding="utf-8")
    allowed = actual == expected
    return {
        "allowed": allowed,
        "allowed_transformations": [
            "strategy_class_rename",
            "non_runtime_candidate_identity_metadata",
            "verbatim_dependency_copy",
        ],
        "actual_transformations": [
            {"type": "strategy_class_rename", "from": BASE_STRATEGY_NAME, "to": candidate_class},
            {"type": "non_runtime_candidate_identity_metadata", "field": "candidate_identity_metadata"},
        ],
        "unexpected_main_source_diff": [] if allowed else ["candidate main source does not match deterministic identity-only template"],
    }


def dependency_hashes(repo_root: Path, candidate_dir: Path) -> dict[str, dict[str, str]]:
    hashes: dict[str, dict[str, str]] = {}
    for name in DEPENDENCY_FILES:
        base = repo_root / "strategies" / name
        candidate = candidate_dir / name
        hashes[name] = {
            "base_sha256": sha256_file(base),
            "candidate_sha256": sha256_file(candidate) if candidate.exists() else "missing",
        }
    return hashes


def validate_candidate_source(repo_root: Path, candidate_dir: Path, candidate_class: str) -> dict[str, Any]:
    candidate_file = candidate_dir / f"{candidate_class}.py"
    diff = semantic_diff_summary(repo_root, candidate_file, candidate_class)
    deps = dependency_hashes(repo_root, candidate_dir)
    dependency_mismatches = {
        name: item
        for name, item in deps.items()
        if item["base_sha256"] != item["candidate_sha256"]
    }
    forbidden_hits = []
    for path in [candidate_file, *(candidate_dir / name for name in DEPENDENCY_FILES)]:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in text.replace("\\", "/"):
                forbidden_hits.append({"path": path.name, "token": token})
    ok = diff["allowed"] and not dependency_mismatches and not forbidden_hits
    return {
        "ok": ok,
        "failure_type": None if ok else "implementation_error",
        "reason_code": None if ok else "unexpected_candidate_semantic_diff",
        "source_diff_summary": diff,
        "dependency_hashes": deps,
        "dependency_mismatches": dependency_mismatches,
        "forbidden_source_hits": forbidden_hits,
    }


def runtime_fingerprint(repo_root: Path, runtime_config: str | Path) -> str:
    runtime = repo_root / runtime_config
    payload = {
        "runtime_config_sha256": sha256_file(runtime),
        "requirements_sha256": sha256_file(repo_root / "research/runtime/requirements-freqtrade.lock.txt"),
        "freeze_sha256": sha256_file(repo_root / "research/runtime/freqtrade-freeze.txt"),
    }
    return stable_hash(payload)


def create_candidate_strategy(repo_root: str | Path, campaign_path: str | Path, experiment_id: str | int = "1") -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    campaign = load_campaign(campaign_path)
    if campaign.get("runner_type") != "candidate_identity_equivalence":
        raise CandidateError("validation_error", "campaign_mode_mismatch", "campaign runner_type must be candidate_identity_equivalence")
    campaign_id = campaign["campaign_id"]
    fixed = campaign["fixed_backtest"]
    candidate_class = candidate_class_name(campaign_id, experiment_id)
    root = candidate_root(repo_root, campaign_id, experiment_id)
    candidate_file = root / f"{candidate_class}.py"
    manifest_path = root / "candidate-manifest.yaml"
    hash_record_path = root / "file-hashes.json"
    generation_record_path = root / "generation-record.json"
    validate_candidate_write_scope(repo_root, campaign, experiment_id, [candidate_file, manifest_path, hash_record_path, generation_record_path])

    base_file = repo_root / BASE_STRATEGY_PATH
    base_hash = sha256_file(base_file).upper()
    if base_hash != BASE_STRATEGY_SHA256:
        raise CandidateError("validation_error", "base_strategy_integrity_violation", f"base strategy hash changed: {base_hash}")
    if root.exists() and any(root.iterdir()):
        raise CandidateError("validation_error", "candidate_directory_not_empty", f"candidate directory already exists: {repo_rel(repo_root, root)}")
    root.mkdir(parents=True, exist_ok=False)

    candidate_file.write_text(expected_candidate_source(repo_root, candidate_class), encoding="utf-8")
    for name in DEPENDENCY_FILES:
        shutil.copy2(repo_root / "strategies" / name, root / name)

    validation = validate_candidate_source(repo_root, root, candidate_class)
    if not validation["ok"]:
        raise CandidateError(validation["failure_type"] or "implementation_error", validation["reason_code"] or "unexpected_candidate_semantic_diff", "candidate semantic diff exceeded allowed identity-only transformations")

    dataset = load_simple_yaml(repo_root / fixed["dataset_manifest"])
    snapshot = load_simple_yaml(repo_root / campaign["sealed_offline_backtest"]["exchange_snapshot"] / "manifest.yaml")
    leverage = snapshot.get("leverage_tier_artifact") or {}
    manifest = {
        "schema_version": "stage3b1-candidate-manifest-v1",
        "campaign_id": campaign_id,
        "experiment_id": str(experiment_id),
        "experiment_type": "candidate_identity_equivalence",
        "strategy_family": "regime_aware",
        "legacy_base_name": BASE_STRATEGY_NAME,
        "base_strategy_name": BASE_STRATEGY_NAME,
        "base_strategy_path": BASE_STRATEGY_PATH.as_posix(),
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "candidate_strategy_class": candidate_class,
        "candidate_strategy_path": repo_rel(repo_root, candidate_file),
        "candidate_strategy_sha256": sha256_file(candidate_file),
        "candidate_dependency_hashes": validation["dependency_hashes"],
        "git_sha": git_sha(repo_root),
        "generator_version": GENERATOR_VERSION,
        "allowed_source_transformations": validation["source_diff_summary"]["allowed_transformations"],
        "actual_source_diff_summary": validation["source_diff_summary"],
        "stage3a_fixture_id": "stage3a5-futures-f3-cert-003",
        "futures_config_id": fixed["config"],
        "dataset_id": dataset.get("dataset_id"),
        "dataset_aggregate_hash": dataset.get("aggregate_sha256"),
        "exchange_snapshot_id": snapshot.get("snapshot_id"),
        "exchange_snapshot_aggregate_hash": snapshot.get("aggregate_sha256"),
        "leverage_tier_artifact_hash": leverage.get("sha256"),
        "runtime_fingerprint": runtime_fingerprint(repo_root, fixed["runtime_config"]),
        "expected_baseline_normalized_trade_hash": EXPECTED_BASELINE_TRADE_HASH,
        "creation_time": utc_now(),
    }
    dump_manifest(manifest_path, manifest)
    hash_record = {
        "candidate_manifest_sha256": sha256_file(manifest_path),
        "candidate_strategy_sha256": manifest["candidate_strategy_sha256"],
        "dependencies": validation["dependency_hashes"],
    }
    dump_json(hash_record_path, hash_record)
    dump_json(
        generation_record_path,
        {
            "generator_version": GENERATOR_VERSION,
            "candidate_class": candidate_class,
            "created_at": manifest["creation_time"],
            "source_diff_summary": validation["source_diff_summary"],
        },
    )
    return {
        "status": "candidate_created",
        "campaign_id": campaign_id,
        "experiment_id": str(experiment_id),
        "candidate_class": candidate_class,
        "candidate_dir": repo_rel(repo_root, root),
        "candidate_path": repo_rel(repo_root, candidate_file),
        "manifest_path": repo_rel(repo_root, manifest_path),
        "base_strategy_sha256": base_hash,
        "candidate_strategy_sha256": manifest["candidate_strategy_sha256"],
        "source_validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an identity-only Stage 3B.1 strategy candidate.")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--experiment-id", default="1")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = create_candidate_strategy(Path.cwd(), args.campaign, args.experiment_id)
    except CandidateError as exc:
        result = {
            "status": "failed",
            "failure_type": exc.failure_type,
            "reason_code": exc.reason_code,
            "message": exc.message,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
