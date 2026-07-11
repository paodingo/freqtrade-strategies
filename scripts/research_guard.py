#!/usr/bin/env python3
"""Campaign-aware path guard for research control-plane dry runs."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterable


PERMANENT_BLOCKED_PATHS = (
    ".env",
    "secrets/**",
    "deploy/**",
    "user_data/config_live.json",
    "configs/production/**",
    "scripts/start_bot.sh",
    "scripts/refresh_data.sh",
)


class PathGuardError(RuntimeError):
    def __init__(self, path: str, reason: str):
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def _casefold(value: str) -> str:
    return value.replace("\\", "/").casefold()


def _matches(pattern: str, repo_path: str) -> bool:
    return fnmatch.fnmatchcase(_casefold(repo_path), _casefold(pattern))


def normalize_repo_path(repo_root: str | Path, candidate: str | Path) -> str:
    root = Path(repo_root).resolve()
    raw = Path(candidate)
    full = raw if raw.is_absolute() else root / raw
    resolved = full.resolve(strict=False)
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise PathGuardError(str(candidate), "path escapes repository root") from exc
    repo_path = rel.as_posix()
    if repo_path in ("", "."):
        raise PathGuardError(str(candidate), "repository root is not a valid experiment path")
    return repo_path


def validate_campaign_paths(config: dict) -> None:
    scope = config.get("scope") or {}
    allowed = scope.get("allowed_paths") or []
    blocked = scope.get("blocked_paths") or []
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise ValueError("scope.allowed_paths must be a list of strings")
    if not isinstance(blocked, list) or not all(isinstance(item, str) for item in blocked):
        raise ValueError("scope.blocked_paths must be a list of strings")
    if not allowed:
        raise ValueError("scope.allowed_paths must not be empty")


def check_path(repo_root: str | Path, config: dict, candidate: str | Path) -> str:
    validate_campaign_paths(config)
    repo_path = normalize_repo_path(repo_root, candidate)
    scope = config.get("scope") or {}
    blocked = [*PERMANENT_BLOCKED_PATHS, *(scope.get("blocked_paths") or [])]
    allowed = scope.get("allowed_paths") or []

    for pattern in blocked:
        if _matches(pattern, repo_path):
            raise PathGuardError(repo_path, f"blocked by pattern {pattern}")

    for pattern in allowed:
        if _matches(pattern, repo_path):
            return repo_path

    raise PathGuardError(repo_path, "not allowed by active campaign scope")


def check_paths(repo_root: str | Path, config: dict, candidates: Iterable[str | Path]) -> list[str]:
    return [check_path(repo_root, config, candidate) for candidate in candidates]


def main() -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Check campaign path authorization.")
    parser.add_argument("--repo-root", default=os.getcwd())
    parser.add_argument("--campaign-json", required=True)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    config = json.loads(Path(args.campaign_json).read_text(encoding="utf-8"))
    checked = check_paths(args.repo_root, config, args.paths)
    print(json.dumps({"authorized": checked}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
