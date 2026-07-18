#!/usr/bin/env python3
"""Canonical and semantic hash gates for protected text manifests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from research_director_common import fingerprint, load_document, sha256_file


CONTRACT_PATH = "research/governance/manifest-hash-contract.yaml"
REGISTRY_PATH = "research/governance/protected-manifest-hash-registry.yaml"


class ProtectedManifestError(RuntimeError):
    def __init__(self, reason_code: str, details: dict[str, Any]):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.details = details


def canonical_manifest_bytes(raw: bytes) -> bytes:
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return (text.rstrip("\n") + "\n").encode("utf-8")


def canonical_text_sha256(value: bytes | str | Path) -> str:
    raw = Path(value).read_bytes() if isinstance(value, (str, Path)) else value
    return hashlib.sha256(canonical_manifest_bytes(raw)).hexdigest()


def checkout_stable_text_sha256_matches(path: str | Path, expected_sha256: str) -> bool:
    """Accept only exact-byte or LF/CRLF projections of the same UTF-8 text."""
    raw = Path(path).read_bytes()
    canonical_lf = canonical_manifest_bytes(raw)
    canonical_crlf = canonical_lf.replace(b"\n", b"\r\n")
    projections = {
        hashlib.sha256(raw).hexdigest(),
        hashlib.sha256(canonical_lf).hexdigest(),
        hashlib.sha256(canonical_crlf).hexdigest(),
    }
    return expected_sha256.lower() in projections


def semantic_manifest_fingerprint(path: str | Path) -> str:
    return fingerprint(load_document(path))


def manifest_hashes(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    raw = path.read_bytes()
    return {
        "raw_worktree_sha256": sha256_file(path),
        "canonical_text_sha256": canonical_text_sha256(raw),
        "semantic_fingerprint": semantic_manifest_fingerprint(path),
        "bom": raw.startswith(b"\xef\xbb\xbf"),
        "eol": "mixed" if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b"") else ("crlf" if b"\r\n" in raw else ("cr" if b"\r" in raw else "lf")),
        "final_newline": raw.endswith((b"\n", b"\r")),
        "bytes": len(raw),
    }


def validate_protected_manifests(repo: str | Path, registry_path: str = REGISTRY_PATH) -> dict[str, Any]:
    repo = Path(repo).resolve()
    contract = load_document(repo / CONTRACT_PATH)
    registry = load_document(repo / registry_path)
    if contract.get("scheme_id") != registry.get("canonical_scheme_id"):
        raise ProtectedManifestError("protected_manifest_contract_mismatch", {"contract": contract.get("scheme_id"), "registry": registry.get("canonical_scheme_id")})
    results = []
    for approved in registry.get("manifests") or []:
        path = repo / approved["path"]
        current = manifest_hashes(path)
        payload = load_document(path)
        id_key = "dataset_id" if approved["artifact_type"] == "dataset" else "snapshot_id"
        checks = {
            "canonical_text_sha256": current["canonical_text_sha256"] == approved["canonical_text_sha256"],
            "semantic_fingerprint": current["semantic_fingerprint"] == approved["semantic_fingerprint"],
            "aggregate_hash": payload.get("aggregate_sha256") == approved["aggregate_hash"],
            "artifact_id": payload.get(id_key) == approved["artifact_id"],
        }
        result = {"path": approved["path"], "checks": checks, "approved": approved, "current": current, "aggregate_hash": payload.get("aggregate_sha256")}
        results.append(result)
        if not all(checks.values()):
            raise ProtectedManifestError("protected_manifest_semantic_drift", result)
    return {"scheme_id": contract["scheme_id"], "semantic_scheme_id": contract["semantic_scheme"]["scheme_id"], "raw_worktree_hash_gate": False, "passed": True, "manifests": results}
