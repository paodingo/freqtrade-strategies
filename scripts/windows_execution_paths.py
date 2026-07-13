#!/usr/bin/env python3
"""Deterministic Windows path budgets and auditable short execution namespaces."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from research_director_common import load_document


CONTRACT_PATH = Path("research/governance/windows-execution-path-budget.yaml")
ATTEMPT_REQUEST_PATH = Path(
    "research/governance/approvals/ranging-short-branch-decision-review-v1-temporal-attempt-3-request.json"
)

REQUIRED_IDENTITY_FIELDS = (
    "proposal_id",
    "proposal_fingerprint",
    "campaign_id",
    "campaign_fingerprint",
    "attempt_id",
    "slice_id",
    "slice_fingerprint",
    "role",
    "repetition",
    "candidate_class",
    "candidate_path",
    "candidate_sha256",
    "formal_strategy_sha256",
    "dataset_id",
    "dataset_sha256",
    "runtime_asset_manifest_fingerprint",
    "evaluation_policy_sha256",
    "exchange_snapshot_sha256",
    "router_sha256",
)


class ExecutionPathContractError(RuntimeError):
    failure_class = "infrastructure_precondition"

    def __init__(self, reason_code: str, detail: str):
        super().__init__(detail)
        self.reason_code = reason_code


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contract_fingerprint(contract: dict[str, Any]) -> str:
    return canonical_hash({key: value for key, value in contract.items() if key != "contract_fingerprint"})


def _require_short_alias(value: str, label: str) -> None:
    if not value or len(value) > 8 or not value.isascii() or not all(character.isalnum() or character == "-" for character in value):
        raise ExecutionPathContractError("short_execution_namespace_collision", f"invalid short alias for {label}")


def _validate_contract(contract: dict[str, Any]) -> None:
    expected = {
        "contract_id": "windows-short-execution-path-v1",
        "long_paths_required": False,
        "max_absolute_path_chars": 220,
        "preflight_required": True,
    }
    if any(contract.get(key) != value for key, value in expected.items()):
        raise ExecutionPathContractError("execution_path_contract_invalid", "fixed contract fields differ")
    if contract.get("contract_fingerprint") != contract_fingerprint(contract):
        raise ExecutionPathContractError("execution_path_contract_invalid", "contract fingerprint mismatch")
    root = Path(str(contract.get("short_root", "")))
    if root.is_absolute() or root.as_posix() != ".runs" or ".." in root.parts:
        raise ExecutionPathContractError("execution_path_contract_invalid", "short root must be the repo-local .runs directory")
    if int(contract.get("execution_short_id_chars", 0)) != 10 or int(contract.get("execution_id_chars", 0)) != 16:
        raise ExecutionPathContractError("execution_path_contract_invalid", "execution ID lengths differ")
    aliases = contract.get("aliases") or {}
    for group in ("campaign", "attempt", "slice", "role", "repetition"):
        values = list((aliases.get(group) or {}).values())
        if not values or len(values) != len(set(values)):
            raise ExecutionPathContractError("short_execution_namespace_collision", f"duplicate or missing {group} aliases")
        for value in values:
            _require_short_alias(str(value), group)
    outputs = contract.get("anticipated_outputs") or {}
    required = {
        "raw_result_archive",
        "raw_result",
        "metadata",
        "runner_report",
        "normalized_trades",
        "signal_masks",
        "runtime_identity",
        "stdout",
        "stderr",
        "artifact_hashes",
    }
    if not required.issubset(outputs):
        raise ExecutionPathContractError("execution_path_contract_invalid", "anticipated output inventory incomplete")
    filenames = list(outputs.values())
    if len(filenames) != len(set(filenames)):
        raise ExecutionPathContractError("short_execution_namespace_collision", "anticipated output filename collision")


def load_contract(repo: Path) -> dict[str, Any]:
    path = repo / CONTRACT_PATH
    contract = load_document(path)
    if not isinstance(contract, dict):
        raise ExecutionPathContractError("execution_path_contract_invalid", "contract is not a mapping")
    _validate_contract(contract)
    return contract


def _identity(identity: dict[str, Any]) -> dict[str, str]:
    missing = [field for field in REQUIRED_IDENTITY_FIELDS if not identity.get(field)]
    if missing:
        raise ExecutionPathContractError("execution_identity_incomplete", "missing fields: " + ",".join(missing))
    return {field: str(identity[field]) for field in REQUIRED_IDENTITY_FIELDS}


def _alias(contract: dict[str, Any], group: str, full_value: str) -> str:
    try:
        return str(contract["aliases"][group][full_value])
    except KeyError as exc:
        raise ExecutionPathContractError("execution_identity_incomplete", f"unregistered {group} identity: {full_value}") from exc


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _reject_reparse_ancestors(repo: Path, target: Path) -> None:
    current = target.parent
    repo = repo.resolve(strict=False)
    while True:
        if _is_reparse_point(current):
            raise ExecutionPathContractError("short_execution_namespace_collision", "symlink or junction ancestor rejected")
        if current == repo or current.parent == current:
            return
        current = current.parent


def plan_execution(repo: Path, contract: dict[str, Any], full_identity: dict[str, Any]) -> dict[str, Any]:
    _validate_contract(contract)
    identity = _identity(full_identity)
    aliases = {
        "campaign_alias": _alias(contract, "campaign", identity["campaign_id"]),
        "attempt_alias": _alias(contract, "attempt", identity["attempt_id"]),
        "slice_alias": _alias(contract, "slice", identity["slice_id"]),
        "role_alias": _alias(contract, "role", identity["role"]),
        "repetition_alias": _alias(contract, "repetition", identity["repetition"]),
    }
    execution_id = str(full_identity.get("execution_id") or canonical_hash(identity)[: int(contract["execution_id_chars"])])
    if len(execution_id) != int(contract["execution_id_chars"]) or any(character not in "0123456789abcdef" for character in execution_id):
        raise ExecutionPathContractError("execution_identity_incomplete", "execution ID must be fixed-length lowercase hex")
    execution_short_id = hashlib.sha256(execution_id.encode("ascii")).hexdigest()[: int(contract["execution_short_id_chars"])]
    namespace_path = Path(str(contract["short_root"]))
    for key in ("campaign_alias", "attempt_alias", "slice_alias", "role_alias", "repetition_alias"):
        namespace_path /= aliases[key]
    namespace_path /= execution_short_id
    output_root = (repo / namespace_path).resolve(strict=False)
    relative_outputs = {
        key: str(template).format(execution_id=execution_id)
        for key, template in contract["anticipated_outputs"].items()
    }
    absolute_outputs = {
        key: str((output_root / filename).resolve(strict=False)) for key, filename in relative_outputs.items()
    }
    lengths = {key: len(value) for key, value in absolute_outputs.items()}
    worst_output_key = max(lengths, key=lengths.__getitem__)
    worst_chars = lengths[worst_output_key]
    budget = {
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "max_absolute_path_chars": contract["max_absolute_path_chars"],
        "long_paths_required": False,
        "preflight_completed": True,
        "relative_outputs": relative_outputs,
        "anticipated_outputs": absolute_outputs,
        "path_lengths": lengths,
        "worst_output_key": worst_output_key,
        "worst_absolute_path": absolute_outputs[worst_output_key],
        "worst_absolute_path_chars": worst_chars,
    }
    if worst_chars > int(contract["max_absolute_path_chars"]):
        raise ExecutionPathContractError(
            "execution_path_budget_exceeded",
            f"{worst_output_key} path length {worst_chars} exceeds {contract['max_absolute_path_chars']}",
        )
    attempt_root = Path(str(contract["short_root"])) / aliases["campaign_alias"] / aliases["attempt_alias"]
    return {
        "schema_version": "windows-short-execution-plan-v1",
        "namespace": namespace_path.as_posix(),
        "attempt_root": attempt_root.as_posix(),
        "alias_registry": (attempt_root / "alias-registry.json").as_posix(),
        "execution_id": execution_id,
        "execution_short_id": execution_short_id,
        "identity_fingerprint": canonical_hash(identity),
        "aliases": aliases,
        "path_budget": budget,
    }


def _new_registry(contract: dict[str, Any], plan: dict[str, Any], identity: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "windows-short-execution-alias-registry-v1",
        "contract_fingerprint": contract["contract_fingerprint"],
        "campaign": {plan["aliases"]["campaign_alias"]: identity["campaign_id"]},
        "attempt": {plan["aliases"]["attempt_alias"]: identity["attempt_id"]},
        "executions": {},
    }


def create_execution_namespace(repo: Path, contract: dict[str, Any], full_identity: dict[str, Any]) -> dict[str, Any]:
    # This must remain the first stateful operation: path failure is pre-Backtest and pre-directory.
    plan = plan_execution(repo, contract, full_identity)
    identity = _identity(full_identity)
    target = repo / plan["namespace"]
    registry_path = repo / plan["alias_registry"]
    _reject_reparse_ancestors(repo, target)
    if target.exists():
        raise ExecutionPathContractError("short_execution_namespace_collision", "execution directory already exists")
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if registry.get("contract_fingerprint") != contract["contract_fingerprint"]:
            raise ExecutionPathContractError("short_execution_namespace_collision", "alias registry contract mismatch")
    else:
        registry = _new_registry(contract, plan, identity)
    existing = registry.get("executions", {}).get(plan["execution_short_id"])
    mapping = {
        "execution_id": plan["execution_id"],
        "identity_fingerprint": plan["identity_fingerprint"],
        "namespace": plan["namespace"],
    }
    if existing is not None:
        raise ExecutionPathContractError("short_execution_namespace_collision", "execution short ID already registered")
    registry.setdefault("executions", {})[plan["execution_short_id"]] = mapping
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.mkdir(target)
    return plan


def build_execution_manifest(repo: Path, plan: dict[str, Any], full_identity: dict[str, Any]) -> dict[str, Any]:
    identity = _identity(full_identity)
    root = repo / plan["namespace"]
    bindings = {}
    for key in ("raw_result", "normalized_trades", "runner_report"):
        relative = plan["path_budget"]["relative_outputs"][key]
        path = root / relative
        if not path.is_file():
            raise ExecutionPathContractError("execution_binding_incomplete", f"missing {key}")
        bindings[key] = {"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return {
        "schema_version": "windows-short-execution-manifest-v1",
        "full_identity": {**identity, "execution_id": plan["execution_id"]},
        "short_namespace_mapping": {
            **plan["aliases"],
            "execution_short_id": plan["execution_short_id"],
            "namespace": plan["namespace"],
            "alias_registry": plan["alias_registry"],
        },
        "path_budget": plan["path_budget"],
        "bindings": bindings,
    }


def validate_binding_chain(repo: Path, manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve(strict=True)
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_root = (repo / manifest["short_namespace_mapping"]["namespace"]).resolve(strict=True)
    if root != expected_root:
        raise ExecutionPathContractError("execution_binding_incomplete", "manifest does not bind its namespace")
    verified = {}
    seen_paths: set[Path] = set()
    for key in ("raw_result", "normalized_trades", "runner_report"):
        binding = manifest["bindings"].get(key)
        if not binding:
            raise ExecutionPathContractError("execution_binding_incomplete", f"missing binding: {key}")
        path = (root / binding["path"]).resolve(strict=True)
        if not path.is_relative_to(root) or path in seen_paths:
            raise ExecutionPathContractError("execution_binding_incomplete", "binding escapes or collides")
        seen_paths.add(path)
        if path.stat().st_size != binding["bytes"] or sha256_file(path) != binding["sha256"]:
            raise ExecutionPathContractError("execution_binding_incomplete", f"binding drift: {key}")
        verified[key] = {"path": path.relative_to(repo.resolve()).as_posix(), "sha256": binding["sha256"]}
    return {"schema_version": "windows-short-execution-binding-audit-v1", "passed": True, "verified": verified}
