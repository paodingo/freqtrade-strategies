#!/usr/bin/env python3
"""Research data access guard for Development / Validation / Holdout layers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_guard import PathGuardError, normalize_repo_path


VALIDATION_ALLOWED_ROLES = {"validation_evaluator"}
DEVELOPMENT_ALLOWED_ROLES = {"candidate_runner", "candidate_generator", "hypothesis_generator", "development_evaluator", "validation_evaluator", "operator"}
HOLDOUT_ALLOWED_ROLES: set[str] = set()


class DataAccessError(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def _has_symlink(path: Path, repo_root: Path) -> bool:
    resolved = path.resolve(strict=False)
    try:
        rel = resolved.relative_to(repo_root.resolve(strict=False))
    except ValueError:
        return True
    current = repo_root.resolve(strict=False)
    for part in rel.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            return True
    return False


def classify_path(repo_path: str) -> str:
    if repo_path.startswith("research/data/snapshots/futures-dev-"):
        return "development"
    if repo_path.startswith("research/data/snapshots/futures-validation-"):
        return "validation"
    if repo_path.startswith("research/data/snapshots/futures-holdout-") or repo_path.startswith("research/data/holdout/"):
        return "holdout"
    if repo_path.startswith("research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-"):
        return "acceptance_fixture"
    return "unknown"


def check_data_access(repo_root: str | Path, path: str | Path, role: str, operation: str = "read") -> dict:
    repo_root = Path(repo_root).resolve()
    try:
        repo_path = normalize_repo_path(repo_root, path)
    except PathGuardError as exc:
        raise DataAccessError("data_path_escape", str(exc)) from exc
    full_path = repo_root / repo_path
    if _has_symlink(full_path, repo_root):
        raise DataAccessError("data_symlink_or_junction_blocked", f"symlink or junction not allowed: {repo_path}")
    layer = classify_path(repo_path)
    if operation != "read":
        if layer in {"development", "validation", "acceptance_fixture", "holdout"}:
            raise DataAccessError("sealed_dataset_write_blocked", f"{layer} dataset is sealed and read-only")
    if layer == "development":
        allowed = role in DEVELOPMENT_ALLOWED_ROLES
    elif layer == "validation":
        allowed = role in VALIDATION_ALLOWED_ROLES
    elif layer == "holdout":
        allowed = role in HOLDOUT_ALLOWED_ROLES
    elif layer == "acceptance_fixture":
        allowed = role in {"candidate_runner", "validation_evaluator", "operator"}
    else:
        allowed = False
    if not allowed:
        raise DataAccessError(f"{layer}_access_denied", f"role {role} may not access {repo_path}")
    return {"authorized": True, "layer": layer, "path": repo_path, "role": role, "operation": operation}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check research data access policy.")
    parser.add_argument("--repo-root", default=Path.cwd())
    parser.add_argument("--role", required=True)
    parser.add_argument("--operation", default="read")
    parser.add_argument("path")
    args = parser.parse_args()
    try:
        result = check_data_access(args.repo_root, args.path, args.role, args.operation)
    except DataAccessError as exc:
        print(json.dumps({"authorized": False, "reason_code": exc.reason_code, "message": exc.message}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
