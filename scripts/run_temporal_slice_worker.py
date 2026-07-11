#!/usr/bin/env python3
"""One-shot fresh-process worker for one Stage 3E.1 temporal backtest run."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from run_experiment import dump_json, sha256_file
from run_offline_backtest import run_offline_backtest


BASE_STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
DEPENDENCIES = ("regime_aware_base", "regime_detector", "risk_manager")


class TemporalWorkerError(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = "implementation_error"
        self.reason_code = reason_code
        self.message = message


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def audit_runtime_identity(repo_root: Path, manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    expected_manifest_hash = stable_hash({key: value for key, value in manifest.items() if key != "execution_manifest_sha256"})
    if manifest.get("execution_manifest_sha256") != expected_manifest_hash:
        raise TemporalWorkerError("runtime_execution_manifest_mismatch", "execution manifest hash mismatch")
    strategy_path = (repo_root / manifest["strategy_file"]).resolve()
    if sha256_file(strategy_path).lower() != BASE_STRATEGY_SHA256:
        raise TemporalWorkerError("runtime_candidate_identity_mismatch", "official strategy source hash mismatch")
    strategy_dir = str(strategy_path.parent)
    if strategy_dir not in sys.path:
        sys.path.insert(0, strategy_dir)
    strategy_module = importlib.import_module("RegimeAwareV6")
    strategy_class = getattr(strategy_module, "RegimeAwareV6")
    loaded_strategy_path = Path(strategy_module.__file__).resolve()
    if loaded_strategy_path != strategy_path or sha256_file(loaded_strategy_path).lower() != BASE_STRATEGY_SHA256:
        raise TemporalWorkerError("runtime_candidate_identity_mismatch", "loaded strategy origin does not match frozen source")
    dependencies = {}
    for name in DEPENDENCIES:
        module = importlib.import_module(name)
        source = Path(module.__file__).resolve()
        expected = manifest["dependency_hashes"][name]
        if source != (repo_root / f"strategies/{name}.py").resolve() or sha256_file(source) != expected:
            raise TemporalWorkerError("runtime_candidate_identity_mismatch", f"loaded dependency mismatch: {name}")
        dependencies[name] = {"module_name": name, "file": str(source), "sha256": expected, "spec_origin": module.__spec__.origin}
    candidate_modules = sorted(name for name in sys.modules if "C3" in name or "candidate" in name.lower())
    if candidate_modules:
        raise TemporalWorkerError("cross_slice_module_contamination", f"candidate modules loaded: {candidate_modules}")
    try:
        import ccxt
        import freqtrade
    except ImportError as exc:
        raise TemporalWorkerError("runtime_dependency_missing", str(exc)) from exc
    identity = {
        "schema_version": "stage3e1-runtime-code-identity-v1",
        "status": "passed",
        "campaign_id": manifest["campaign_id"],
        "slice_id": manifest["slice_id"],
        "execution_run_id": manifest["execution_run_id"],
        "strategy_class": strategy_class.__name__,
        "strategy_source_path": str(loaded_strategy_path),
        "strategy_source_sha256": sha256_file(loaded_strategy_path),
        "strategy_module_origin": strategy_module.__spec__.origin,
        "dependencies": dependencies,
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "freqtrade_version": freqtrade.__version__,
        "ccxt_version": ccxt.__version__,
        "process_id": os.getpid(),
        "parent_process_id": os.getppid(),
        "sys_path": list(sys.path),
        "related_sys_modules": sorted(name for name in sys.modules if name in {"RegimeAwareV6", *DEPENDENCIES}),
        "candidate_modules": candidate_modules,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "single_backtest_only": True,
        "claimed_next_slice": False,
        "registry_write_allowed": False,
        "backtest_started": False,
    }
    dump_json(output, identity)
    return identity


def run_worker(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_dir = repo_root / manifest["run_dir"]
    run_dir.mkdir(parents=True, exist_ok=True)
    identity_path = run_dir / "runtime-code-identity.json"
    identity = audit_runtime_identity(repo_root, manifest, identity_path)
    identity["backtest_started"] = True
    dump_json(identity_path, identity)
    result = run_offline_backtest(
        repo_root,
        manifest["campaign"],
        int(manifest["slice_number"]),
        manifest["execution_run_id"],
        repo_root / manifest["exchange_snapshot"],
    )
    worker = {
        "schema_version": "stage3e1-temporal-worker-result-v1",
        "status": result["status"],
        "failure_type": result.get("failure_type"),
        "reason_code": result.get("reason_code"),
        "slice_id": manifest["slice_id"],
        "execution_run_id": manifest["execution_run_id"],
        "process_id": identity["process_id"],
        "parent_process_id": identity["parent_process_id"],
        "backtest_count": 1,
        "claimed_next_slice": False,
        "registry_modified": False,
        "network_accessed": False,
    }
    dump_json(run_dir / "temporal-worker-result.json", worker)
    return worker


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        result = run_worker(Path.cwd(), Path(args.manifest))
    except TemporalWorkerError as exc:
        print(json.dumps({"status": "failed", "failure_type": exc.failure_type, "reason_code": exc.reason_code, "message": exc.message}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"accepted", "rejected"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
