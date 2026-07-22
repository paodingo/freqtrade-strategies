#!/usr/bin/env python3
"""Create and verify an exact, portable research control-plane migration manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "research-control-plane-migration-manifest-v1"
DEFAULT_MANIFEST = "research-control-plane-migration-manifest.json"


class MigrationManifestError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _git_head(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, encoding="utf-8"
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MigrationManifestError("migration root is not a readable git checkout") from exc


def _inventory(root: Path, manifest_name: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative == manifest_name or relative == ".git" or relative.startswith(".git/"):
            continue
        if path.is_symlink():
            raise MigrationManifestError(f"symlink is not allowed in migration package: {relative}")
        if path.is_file():
            files.append({"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return files


def create_manifest(root: Path, output: Path, migration_id: str) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    try:
        manifest_name = output.relative_to(root).as_posix()
    except ValueError as exc:
        raise MigrationManifestError("manifest output must be inside migration root") from exc
    if not migration_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in migration_id):
        raise MigrationManifestError("migration_id is invalid")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "migration_id": migration_id,
        "git_head": _git_head(root),
        "files": _inventory(root, manifest_name),
    }
    payload["file_count"] = len(payload["files"])
    payload["total_bytes"] = sum(item["bytes"] for item in payload["files"])
    payload["manifest_fingerprint"] = _fingerprint(payload)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def verify_manifest(root: Path, manifest: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = manifest.resolve()
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationManifestError("migration manifest is unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise MigrationManifestError("migration manifest schema is invalid")
    unsigned = {key: value for key, value in payload.items() if key != "manifest_fingerprint"}
    if payload.get("manifest_fingerprint") != _fingerprint(unsigned):
        raise MigrationManifestError("migration manifest fingerprint mismatch")
    if payload.get("git_head") != _git_head(root):
        raise MigrationManifestError("migration git HEAD mismatch")
    manifest_name = manifest.relative_to(root).as_posix()
    actual = _inventory(root, manifest_name)
    if actual != payload.get("files"):
        raise MigrationManifestError("migration file inventory mismatch")
    if payload.get("file_count") != len(actual):
        raise MigrationManifestError("migration file_count mismatch")
    if payload.get("total_bytes") != sum(item["bytes"] for item in actual):
        raise MigrationManifestError("migration total_bytes mismatch")
    return {
        "status": "verified",
        "migration_id": payload["migration_id"],
        "git_head": payload["git_head"],
        "file_count": payload["file_count"],
        "total_bytes": payload["total_bytes"],
        "manifest_fingerprint": payload["manifest_fingerprint"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--migration-id", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = (
            create_manifest(args.root, args.output, args.migration_id)
            if args.command == "create"
            else verify_manifest(args.root, args.manifest)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (MigrationManifestError, OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
