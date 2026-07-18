#!/usr/bin/env python3
"""Audit branch/worktree sprawl and optionally archive safe merged branches."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "harness" / "lifecycle-policy.json"


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def worktrees(cwd: Path = ROOT) -> list[dict[str, Any]]:
    blocks = git("worktree", "list", "--porcelain", cwd=cwd).split("\n\n")
    result = []
    for block in blocks:
        item: dict[str, Any] = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            if key in {"bare", "detached", "locked", "prunable"}:
                item[key] = value or True
            else:
                item[key] = value
        if item.get("worktree"):
            path = Path(item["worktree"])
            item["dirty"] = bool(git("status", "--porcelain", cwd=path, check=False))
            if item.get("branch", "").startswith("refs/heads/"):
                item["branch"] = item["branch"].removeprefix("refs/heads/")
            result.append(item)
    return result


def branch_rows(cwd: Path = ROOT) -> list[dict[str, str]]:
    delimiter = "\x1f"
    output = git(
        "for-each-ref",
        f"--format=%(refname:short){delimiter}%(objectname){delimiter}%(committerdate:iso8601-strict){delimiter}%(upstream:short)",
        "refs/heads",
        cwd=cwd,
    )
    rows = []
    for line in output.splitlines():
        if not line:
            continue
        name, sha, committed_at, upstream = (line.split(delimiter) + ["", "", "", ""])[:4]
        rows.append({"name": name, "sha": sha, "committed_at": committed_at, "upstream": upstream})
    return rows


def protected(branch: str, policy: dict[str, Any], current: str) -> bool:
    return (
        branch == current
        or branch in policy.get("protected_branches", [])
        or any(branch.startswith(prefix) for prefix in policy.get("protected_prefixes", []))
    )


def is_ancestor(branch: str, base: str, cwd: Path = ROOT) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", branch, base], cwd=cwd, capture_output=True).returncode == 0


def build_report(policy: dict[str, Any], cwd: Path = ROOT) -> dict[str, Any]:
    current = git("branch", "--show-current", cwd=cwd)
    base = policy.get("base_branch", "master")
    trees = worktrees(cwd)
    checked_out = {item.get("branch") for item in trees}
    branches = branch_rows(cwd)
    sha_groups: dict[str, list[str]] = {}
    for branch in branches:
        sha_groups.setdefault(branch["sha"], []).append(branch["name"])
        branch["protected"] = protected(branch["name"], policy, current)
        branch["checked_out"] = branch["name"] in checked_out
        branch["merged_to_base"] = is_ancestor(branch["name"], base, cwd)
        branch["cleanup_eligible"] = bool(
            branch["merged_to_base"] and not branch["protected"] and not branch["checked_out"]
        )
    duplicates = [names for names in sha_groups.values() if len(names) > 1]
    violations = []
    if len(branches) > int(policy.get("max_local_branches", 8)):
        violations.append(f"local branches {len(branches)} exceed {policy.get('max_local_branches')}")
    if len(trees) > int(policy.get("max_worktrees", 5)):
        violations.append(f"worktrees {len(trees)} exceed {policy.get('max_worktrees')}")
    return {
        "schema_version": "git-lifecycle-audit-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": str(cwd.resolve()),
        "current_branch": current,
        "base_branch": base,
        "summary": {
            "local_branches": len(branches),
            "worktrees": len(trees),
            "dirty_worktrees": sum(bool(item.get("dirty")) for item in trees),
            "cleanup_eligible_branches": sum(bool(item["cleanup_eligible"]) for item in branches),
            "duplicate_head_groups": len(duplicates),
        },
        "violations": violations,
        "duplicate_heads": duplicates,
        "branches": branches,
        "worktrees": trees,
    }


def archive_eligible(report: dict[str, Any], policy: dict[str, Any], cwd: Path = ROOT) -> list[dict[str, str]]:
    actions = []
    prefix = policy.get("archive_tag_prefix", "archive/branch-cleanup")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for branch in report["branches"]:
        if not branch["cleanup_eligible"]:
            continue
        safe_name = branch["name"].replace("/", "-")
        tag = f"{prefix}/{stamp}/{safe_name}"
        git("tag", tag, branch["sha"], cwd=cwd)
        git("branch", "-d", branch["name"], cwd=cwd)
        actions.append({"branch": branch["name"], "archive_tag": tag, "sha": branch["sha"]})
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true", help="Archive and delete only merged, protected-safe, non-checked-out local branches")
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    report = build_report(policy)
    if args.apply:
        report["actions"] = archive_eligible(report, policy)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 1 if report["violations"] and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
