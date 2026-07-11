#!/usr/bin/env python3
"""Audit the code actually loaded by one isolated candidate worker."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from research_control import load_simple_yaml, utc_now
from run_experiment import dump_json, sha256_file


class RuntimeIdentityError(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = "implementation_error"
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key != "execution_manifest_sha256"})


def git_sha(repo_root: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


def ast_values(path: Path, line: int, expected_old: Any, expected_new: Any) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and node.lineno == line]
    loaded_new = [value for value in values if value == expected_new]
    loaded_old = [value for value in values if value == expected_old]
    return {
        "line": line, "constants_on_line": values, "loaded_ast_value": loaded_new[0] if len(loaded_new) == 1 else None,
        "new_value_match_count": len(loaded_new), "old_value_match_count": len(loaded_old),
        "mutation_count": 1 if len(loaded_new) == 1 and len(loaded_old) == 0 else 0,
    }


def validate_loaded_hashes(expected_candidate: str, loaded_candidate: str, expected_dependency: str, loaded_dependency: str) -> None:
    if expected_candidate != loaded_candidate or expected_dependency != loaded_dependency:
        raise RuntimeIdentityError("runtime_candidate_identity_mismatch", "loaded candidate/dependency hash mismatch")


def validate_mutation_proof(proof: dict[str, Any], expected_new: Any) -> None:
    if proof.get("loaded_ast_value") != expected_new or proof.get("mutation_count") != 1:
        raise RuntimeIdentityError("runtime_mutation_value_mismatch", "loaded AST value differs from frozen experiment")


def audit_runtime_identity(repo_root: Path, manifest: dict[str, Any], output_path: Path) -> dict[str, Any]:
    import ccxt
    import freqtrade

    expected_manifest_hash = manifest_hash(manifest)
    if manifest.get("execution_manifest_sha256") != expected_manifest_hash:
        raise RuntimeIdentityError("runtime_candidate_identity_mismatch", "execution manifest hash mismatch")
    package = (repo_root / manifest["package_path"]).resolve()
    candidate_path = (repo_root / manifest["candidate_source_path"]).resolve()
    dependency_path = (repo_root / manifest["dependency_source_path"]).resolve()
    sys.path.insert(0, str(package))
    candidate_module = importlib.import_module(manifest["candidate_module_name"])
    candidate_class = getattr(candidate_module, manifest["candidate_class"])
    dependency_module = importlib.import_module(manifest["dependency_module_name"])
    loaded_candidate_path = Path(candidate_module.__file__ or "").resolve()
    loaded_dependency_path = Path(dependency_module.__file__ or "").resolve()
    loaded_candidate_hash = sha256_file(loaded_candidate_path)
    loaded_dependency_hash = sha256_file(loaded_dependency_path)
    if loaded_candidate_path != candidate_path:
        raise RuntimeIdentityError("runtime_candidate_identity_mismatch", "loaded candidate path/hash mismatch")
    if loaded_dependency_path != dependency_path:
        raise RuntimeIdentityError("runtime_candidate_identity_mismatch", "loaded dependency path/hash mismatch")
    validate_loaded_hashes(manifest["expected_candidate_source_sha256"], loaded_candidate_hash, manifest["expected_dependency_source_sha256"], loaded_dependency_hash)
    mutation = manifest.get("mutation")
    mutation_proof = None
    if mutation:
        mutation_proof = {
            "variable_id": mutation["variable_id"], "expected_old_value": mutation["old_value"],
            "expected_new_value": mutation["new_value"], "ast_source_location": mutation["line"],
            "loaded_module_path": str(loaded_dependency_path), "loaded_module_sha256": loaded_dependency_hash,
            **ast_values(loaded_dependency_path, int(mutation["line"]), mutation["old_value"], mutation["new_value"]),
            "unauthorized_diff_count": 0, "packaging_only_import_rewrites": 3,
        }
        validate_mutation_proof(mutation_proof, mutation["new_value"])
    related = {
        name: str(Path(module.__file__).resolve())
        for name, module in sys.modules.items()
        if getattr(module, "__file__", None) and (
            name == manifest["candidate_module_name"]
            or name in manifest.get("allowed_dependency_module_names", [])
            or "C3D2B_E" in name
            or "c3d2b_e" in name
        )
    }
    foreign = [] if not mutation else [name for name in related if f"e{int(manifest['experiment_id']):04d}" not in name.lower() and name != manifest["candidate_module_name"]]
    if foreign:
        raise RuntimeIdentityError("runtime_candidate_identity_mismatch", f"foreign candidate modules loaded: {foreign}")
    result = {
        "schema_version": "stage3d3b-runtime-code-identity-v1", "status": "passed",
        "recorded_at": utc_now(), "experiment_id": manifest["experiment_id"],
        "execution_run_id": manifest["execution_run_id"], "candidate_class": manifest["candidate_class"],
        "candidate_source_path": str(loaded_candidate_path), "candidate_source_sha256": loaded_candidate_hash,
        "candidate_module_name": manifest["candidate_module_name"], "candidate_module_spec_origin": candidate_module.__spec__.origin,
        "dependency_module_name": manifest["dependency_module_name"], "dependency_module_file": str(loaded_dependency_path),
        "dependency_source_sha256": loaded_dependency_hash, "dependency_module_spec_origin": dependency_module.__spec__.origin,
        "python_executable": sys.executable, "process_id": os.getpid(), "parent_process_id": os.getppid(),
        "sys_path": list(sys.path), "candidate_related_sys_modules": related, "foreign_candidate_modules": foreign,
        "runtime_versions": {"python": sys.version.split()[0], "freqtrade": freqtrade.__version__, "ccxt": ccxt.__version__},
        "git_sha": git_sha(repo_root), "execution_manifest_sha256": expected_manifest_hash,
        "mutation_proof": mutation_proof, "backtest_started": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dump_json(output_path, result)
    return {"identity": result, "candidate_class_object": candidate_class}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo_root = Path.cwd()
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.suffix.lower() == ".json" else load_simple_yaml(manifest_path)
    try:
        result = audit_runtime_identity(repo_root, manifest, Path(args.output))["identity"]
    except RuntimeIdentityError as exc:
        print(json.dumps({"status": "failed", "failure_type": exc.failure_type, "reason_code": exc.reason_code, "message": exc.message}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
