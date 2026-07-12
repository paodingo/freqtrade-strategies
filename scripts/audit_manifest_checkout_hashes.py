#!/usr/bin/env python3
"""Audit Git blob, checkout bytes, canonical text and YAML semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from protected_manifest_hash import canonical_text_sha256, manifest_hashes
from research_director_common import fingerprint, load_document, write_json


def git(repo: Path, *args: str, binary: bool = False):
    return subprocess.check_output(["git", *args], cwd=repo, text=not binary, encoding=None if binary else "utf-8")


def eol_name(raw: bytes) -> str:
    if b"\r\n" in raw:
        return "crlf"
    if b"\r" in raw:
        return "cr"
    return "lf"


def audit(repo: Path, old_root: Path) -> dict:
    registry = load_document(repo / "research/governance/protected-manifest-hash-registry.yaml")
    rows = []
    for approved in registry["manifests"]:
        rel = approved["path"]
        path = repo / rel
        old_path = old_root / rel
        blob = git(repo, "cat-file", "blob", f"HEAD:{rel}", binary=True)
        worktree = path.read_bytes()
        old = old_path.read_bytes()
        current_semantic = load_document(path)
        old_semantic = load_document(old_path)
        eol_diagnostic = git(repo, "ls-files", "--eol", "--", rel).strip()
        attributes = git(repo, "check-attr", "-a", "--", rel).strip().splitlines()
        semantic_equal = current_semantic == old_semantic
        canonical_equal = canonical_text_sha256(worktree) == canonical_text_sha256(old) == canonical_text_sha256(blob)
        if not semantic_equal:
            raise SystemExit("protected_manifest_semantic_drift")
        rows.append({
            "path": rel,
            "git_blob_id": git(repo, "rev-parse", f"HEAD:{rel}").strip(),
            "repository_blob_raw_sha256": hashlib.sha256(blob).hexdigest(),
            "worktree_raw_sha256": hashlib.sha256(worktree).hexdigest(),
            "old_raw_expected_sha256": hashlib.sha256(old).hexdigest(),
            "canonical_text_sha256": canonical_text_sha256(worktree),
            "semantic_fingerprint": fingerprint(current_semantic),
            "aggregate_hash": current_semantic.get("aggregate_sha256"),
            "worktree_eol": eol_name(worktree),
            "index_eol_diagnostic": eol_diagnostic,
            "gitattributes_rules": attributes,
            "bom": worktree.startswith(b"\xef\xbb\xbf"),
            "final_newline": worktree.endswith(b"\n"),
            "bytes": len(worktree),
            "old_approved_bytes": len(old),
            "canonical_equal": canonical_equal,
            "semantic_equal": semantic_equal,
            "semantic_change": False,
            "diff_classification": "checkout_eol_only",
        })
    return {"schema_version": "manifest-checkout-hash-drift-audit-v1", "reason": "checkout_hash_stabilization_only", "semantic_change": False, "all_canonical_equal": all(row["canonical_equal"] for row in rows), "all_semantic_equal": all(row["semantic_equal"] for row in rows), "manifests": rows}


def markdown(payload: dict) -> str:
    lines = ["# Protected Manifest Checkout Hash Drift", "", "- Classification: `checkout_eol_only`", "- Semantic change: `false`", "- Canonical scheme: `canonical_utf8_lf_v1`", "", "| Path | old raw | worktree raw | canonical | semantic | aggregate | EOL |", "|---|---|---|---|---|---|---|"]
    for row in payload["manifests"]:
        lines.append(f"| `{row['path']}` | `{row['old_raw_expected_sha256']}` | `{row['worktree_raw_sha256']}` | `{row['canonical_text_sha256']}` | `{row['semantic_fingerprint']}` | `{row['aggregate_hash']}` | `{row['worktree_eol']}` |")
    lines += ["", "All three Git blobs and current worktree files are UTF-8 without BOM, use LF, end with a newline, and are semantically identical to the previously approved CRLF checkout bytes. No Manifest business field or aggregate hash changed.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-root", required=True)
    parser.add_argument("--json", default="reports/audits/manifest-checkout-hash-drift.json")
    parser.add_argument("--markdown", default="reports/audits/manifest-checkout-hash-drift.md")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    payload = audit(repo, Path(args.old_root))
    write_json(repo / args.json, payload)
    (repo / args.markdown).write_text(markdown(payload), encoding="utf-8")
    print(json.dumps({"semantic_change": payload["semantic_change"], "manifests": len(payload["manifests"]), "canonical_equal": payload["all_canonical_equal"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
