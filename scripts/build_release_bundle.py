#!/usr/bin/env python3
"""Build an immutable dry-run operational release directly from Git objects."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "runtime-deployment-manifest-v1"
RUNTIME_PREFIXES = (
    "dashboard/",
    "deploy/",
    "harness/",
    "scripts/",
    "strategies/",
    "runtime_snapshots/",
    "tests/",
)
ROOT_FILES = {
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "AUTONOMY.md",
    "README.md",
    "WORKFLOW.md",
}


def run_git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def release_files(repo: Path, ref: str) -> list[str]:
    names = str(run_git(repo, "ls-tree", "-r", "--name-only", ref)).splitlines()
    selected = []
    for name in names:
        if name in ROOT_FILES or name.startswith(RUNTIME_PREFIXES):
            selected.append(name)
        elif name.startswith("user_data/") and name.endswith(".json"):
            selected.append(name)
    return sorted(selected)


def git_blob(repo: Path, ref: str, name: str) -> bytes:
    return bytes(run_git(repo, "show", f"{ref}:{name}", text=False))


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_bundle(repo: Path, ref: str, output: Path, environment: str) -> dict:
    git_sha = str(run_git(repo, "rev-parse", f"{ref}^{{commit}}")).strip()
    commit_epoch = int(str(run_git(repo, "show", "-s", "--format=%ct", git_sha)).strip())
    names = release_files(repo, git_sha)
    files = []
    blobs: dict[str, bytes] = {}
    for name in names:
        data = git_blob(repo, git_sha, name)
        blobs[name] = data
        files.append({
            "path": name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        })

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "release_id": f"dry-run-{git_sha[:12]}",
        "git_sha": git_sha,
        "environment": environment,
        "dry_run_only": True,
        "built_at": iso_utc_now(),
        "deployed_at": None,
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for name in names:
            data = blobs[name]
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = commit_epoch
            info.mode = 0o755 if name.endswith((".sh", ".py", ".ps1")) else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            archive.addfile(info, io.BytesIO(data))
        manifest_data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
        manifest_info = tarfile.TarInfo("runtime-deployment-manifest.json")
        manifest_info.size = len(manifest_data)
        manifest_info.mtime = commit_epoch
        manifest_info.mode = 0o644
        manifest_info.uid = manifest_info.gid = 0
        manifest_info.uname = manifest_info.gname = "root"
        archive.addfile(manifest_info, io.BytesIO(manifest_data))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--environment", default="cloud-dry-run")
    args = parser.parse_args()
    manifest = build_bundle(args.repo.resolve(), args.ref, args.output.resolve(), args.environment)
    print(json.dumps({
        "output": str(args.output.resolve()),
        "release_id": manifest["release_id"],
        "git_sha": manifest["git_sha"],
        "file_count": len(manifest["files"]),
        "dry_run_only": manifest["dry_run_only"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
