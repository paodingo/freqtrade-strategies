#!/usr/bin/env python3
"""Immutable execution namespaces for governed backtest workers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path
from typing import Any


class NamespaceContractError(RuntimeError):
    failure_class = "implementation_error"

    def __init__(self, reason_code: str, detail: str):
        super().__init__(detail)
        self.reason_code = reason_code


NAMESPACE_FIELDS = (
    "campaign_id",
    "proposal_id",
    "research_unit",
    "attempt_id",
    "pair_id",
    "role",
    "repetition",
    "execution_id",
)


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_inventory(root: Path) -> dict[str, Any]:
    if not root.exists():
        rows: list[dict[str, Any]] = []
    else:
        rows = [
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(item for item in root.rglob("*") if item.is_file())
        ]
    return {"root": root.as_posix(), "file_count": len(rows), "tree_sha256": canonical_hash(rows), "files": rows}


def tree_inventory_excluding(root: Path, excluded_roots: list[Path]) -> dict[str, Any]:
    excluded = [item.resolve(strict=False) for item in excluded_roots]
    rows = []
    if root.exists():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            resolved = path.resolve(strict=False)
            if any(resolved == item or resolved.is_relative_to(item) for item in excluded):
                continue
            rows.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return {"root": root.as_posix(), "file_count": len(rows), "tree_sha256": canonical_hash(rows), "files": rows}


def _is_reparse_point(path: Path) -> bool:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _ancestor_chain(repo: Path, path: Path) -> list[dict[str, Any]]:
    chain = []
    current = path
    while True:
        chain.append({"path": current.as_posix(), "exists": current.exists(), "reparse_point": _is_reparse_point(current)})
        if current == repo or current.parent == current:
            break
        current = current.parent
    return chain


def expected_execution_root(repo: Path, fields: dict[str, str]) -> Path:
    missing = [field for field in NAMESPACE_FIELDS if not fields.get(field)]
    if missing:
        raise NamespaceContractError("output_root_contract_violation", "missing namespace fields: " + ",".join(missing))
    for field, value in fields.items():
        if field in NAMESPACE_FIELDS and (value in {".", ".."} or any(token in value for token in ("/", "\\"))):
            raise NamespaceContractError("output_root_contract_violation", f"unsafe namespace field {field}")
    return (
        repo
        / "research/results"
        / fields["campaign_id"]
        / fields["research_unit"]
        / fields["attempt_id"]
        / fields["pair_id"]
        / fields["role"]
        / fields["repetition"]
        / fields["execution_id"]
    )


def validate_output_root(repo: Path, approved_attempt_root: Path, output_root: Path, fields: dict[str, str]) -> dict[str, Any]:
    repo = repo.resolve()
    lexical = str(output_root)
    if ".." in output_root.parts or re.search(r"(^|[\\/])[^\\/]*~\d+([\\/]|$)", lexical):
        raise NamespaceContractError("output_root_contract_violation", "relative escape or Windows short-path alias")
    if "//" in lexical.replace("\\", "/"):
        raise NamespaceContractError("output_root_contract_violation", "duplicate path separator")
    resolved = output_root.resolve(strict=False)
    approved = approved_attempt_root.resolve(strict=False)
    expected = expected_execution_root(repo, fields).resolve(strict=False)
    if os.path.normcase(str(resolved)) != os.path.normcase(str(expected)):
        raise NamespaceContractError("output_root_contract_violation", "output root differs from immutable namespace")
    if not resolved.is_relative_to(approved) or not resolved.is_relative_to(repo):
        raise NamespaceContractError("output_root_contract_violation", "output root is outside approved attempt root")
    forbidden = [
        repo / "research/results" / fields["campaign_id"] / "2",
        repo / "research/results" / fields["campaign_id"] / "3",
        repo / "research/results" / fields["campaign_id"] / fields["research_unit"] / "recertification-attempt-2",
    ]
    if any(resolved == path.resolve(strict=False) or resolved.is_relative_to(path.resolve(strict=False)) for path in forbidden):
        raise NamespaceContractError("output_root_contract_violation", "output root intersects a contaminated or stale attempt")
    ancestors = _ancestor_chain(repo, resolved.parent)
    if any(item["reparse_point"] for item in ancestors):
        raise NamespaceContractError("output_root_contract_violation", "symlink or junction ancestor rejected")
    return {
        "schema_version": "backtest-output-root-audit-v1",
        "lexical_path": lexical,
        "resolved_path": resolved.as_posix(),
        "repo_relative_path": resolved.relative_to(repo).as_posix(),
        "approved_attempt_root": approved.as_posix(),
        "ancestor_chain": ancestors,
        "symlink_or_junction_present": False,
        "namespace_fields": {field: fields[field] for field in NAMESPACE_FIELDS},
        "validation_verdict": "approved",
    }


def create_execution_namespace(repo: Path, approved_attempt_root: Path, fields: dict[str, str]) -> tuple[Path, dict[str, Any]]:
    output_root = expected_execution_root(repo.resolve(), fields)
    audit = validate_output_root(repo, approved_attempt_root, output_root, fields)
    if output_root.exists():
        raise NamespaceContractError("output_root_contract_violation", "execution output root already exists")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    os.mkdir(output_root)
    return output_root, audit


def require_current_artifact(path: Path, output_root: Path, started_ns: int, reason_code: str) -> None:
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise NamespaceContractError(reason_code, f"required current execution artifact missing: {path.name}") from exc
    if not resolved.is_relative_to(output_root.resolve(strict=True)):
        raise NamespaceContractError(reason_code, "artifact is outside current execution root")
    if path.stat().st_mtime_ns < started_ns:
        raise NamespaceContractError(reason_code, "artifact predates current execution")


def extract_exact_result(archive_path: Path, result_path: Path, expected_member: str, output_root: Path, started_ns: int) -> dict[str, Any]:
    require_current_artifact(archive_path, output_root, started_ns, "current_execution_result_missing")
    if result_path.exists():
        raise NamespaceContractError("current_execution_result_missing", "raw result path already exists")
    with zipfile.ZipFile(archive_path) as archive:
        if expected_member not in archive.namelist():
            raise NamespaceContractError("current_execution_result_missing", "expected raw result member missing")
        result_path.write_bytes(archive.read(expected_member))
    require_current_artifact(result_path, output_root, started_ns, "current_execution_result_missing")
    return {
        "raw_result_path": result_path.as_posix(),
        "raw_result_sha256": sha256_file(result_path),
        "raw_archive_path": archive_path.as_posix(),
        "raw_archive_sha256": sha256_file(archive_path),
    }


def assert_tree_unchanged(before: dict[str, Any], after: dict[str, Any], reason_code: str = "cross_attempt_artifact_write") -> None:
    if before["tree_sha256"] != after["tree_sha256"]:
        raise NamespaceContractError(reason_code, f"tree changed outside execution namespace: {before['root']}")


def validate_report_bindings(report: dict[str, Any], output_root: Path, attempt_id: str, execution_id: str) -> dict[str, Any]:
    if report.get("attempt_id") != attempt_id or report.get("execution_id") != execution_id:
        raise NamespaceContractError("stale_runner_report_reference", "attempt or execution ID differs")
    path_fields = {
        "raw_result_path": "raw_result_sha256",
        "metrics_path": None,
        "normalized_trades_path": "normalized_trades_sha256",
        "runtime_identity_path": "runtime_identity_sha256",
        "signal_mask_path": "signal_mask_sha256",
    }
    verified = {}
    for field, hash_field in path_fields.items():
        value = report.get(field)
        if not value:
            raise NamespaceContractError("stale_runner_report_reference", f"missing report path: {field}")
        path = (output_root / value).resolve(strict=True)
        if not path.is_relative_to(output_root.resolve(strict=True)):
            raise NamespaceContractError("stale_runner_report_reference", f"report path escapes namespace: {field}")
        actual_hash = sha256_file(path)
        if hash_field and report.get(hash_field) != actual_hash:
            raise NamespaceContractError("stale_runner_report_reference", f"report hash mismatch: {field}")
        verified[field] = {"path": path.as_posix(), "sha256": actual_hash}
    return {"schema_version": "runner-report-binding-audit-v1", "passed": True, "verified": verified}


def validate_trade_counts(raw_count: int, normalized_count: int, runner_count: int) -> None:
    if raw_count != normalized_count or normalized_count != runner_count:
        raise NamespaceContractError(
            "normalized_trade_count_mismatch",
            f"raw={raw_count}, normalized={normalized_count}, runner={runner_count}",
        )
