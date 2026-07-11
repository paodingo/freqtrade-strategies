#!/usr/bin/env python3
"""Read-only environment doctor for fixed Freqtrade research backtests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from research_control import load_campaign, load_simple_yaml, parse_scalar
from research_guard import PathGuardError, check_path
from run_experiment import sha256_file


ENVIRONMENT_REASON_CODES = {
    "runtime_python_missing",
    "freqtrade_module_missing",
    "freqtrade_version_mismatch",
    "dataset_missing",
    "dataset_manifest_missing",
    "dataset_hash_mismatch",
    "environment_not_ready",
}


def load_yaml_or_json(path: str | Path) -> dict:
    path = Path(path)
    text = path.read_text(encoding="utf-8").lstrip()
    if text.startswith("{"):
        payload = json.loads(text)
    else:
        try:
            import yaml  # type: ignore

            payload = yaml.safe_load(text)
        except Exception:
            payload = load_simple_yaml_with_lists(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping")
    return payload


def load_simple_yaml_with_lists(path: str | Path) -> dict:
    root = load_simple_yaml(path)
    return root


def issue(reason_code: str, message: str, field: str | None = None, details: dict | None = None) -> dict:
    failure_type = "infra_permanent" if reason_code in ENVIRONMENT_REASON_CODES else "validation_error"
    return {
        "reason_code": reason_code,
        "failure_type": failure_type,
        "field": field,
        "message": message,
        "details": details or {},
    }


def repo_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def run_python(python_executable: Path, code: str, timeout: int = 15, cwd: Path | None = None) -> tuple[int, str]:
    try:
        result = subprocess.run(
            [str(python_executable), "-c", code],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            shell=False,
            cwd=cwd,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def parse_yyyymmdd(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return None


def timerange_contains(snapshot_range: str, requested_range: str) -> bool:
    if "-" not in snapshot_range or "-" not in requested_range:
        return False
    snap_start, snap_end = snapshot_range.split("-", 1)
    req_start, req_end = requested_range.split("-", 1)
    snap_start_dt = parse_yyyymmdd(snap_start)
    snap_end_dt = parse_yyyymmdd(snap_end)
    req_start_dt = parse_yyyymmdd(req_start)
    req_end_dt = parse_yyyymmdd(req_end)
    if not all([snap_start_dt, snap_end_dt, req_start_dt, req_end_dt]):
        return False
    return snap_start_dt <= req_start_dt and req_end_dt <= snap_end_dt


def load_runtime_config(repo_root: Path, config: dict, runtime_path: str | Path | None = None) -> tuple[dict | None, list[dict], Path | None]:
    issues: list[dict] = []
    fixed = config.get("fixed_backtest") or {}
    runtime_ref = runtime_path or fixed.get("runtime_config") or config.get("runtime_config")
    if not runtime_ref:
        return None, [issue("environment_not_ready", "fixed_backtest.runtime_config is required", "runtime_config")], None
    try:
        checked = check_path(repo_root, config, runtime_ref)
        path = repo_root / checked
    except PathGuardError as exc:
        return None, [issue("environment_not_ready", str(exc), "runtime_config")], None
    if not path.exists():
        return None, [issue("environment_not_ready", f"runtime config missing: {checked}", "runtime_config")], path
    try:
        runtime = load_yaml_or_json(path)
    except Exception as exc:
        return None, [issue("environment_not_ready", f"runtime config is not parseable: {exc}", "runtime_config")], path
    return runtime, issues, path


def check_runtime(repo_root: Path, config: dict, runtime: dict | None, runtime_path: Path | None) -> tuple[list[dict], dict]:
    issues: list[dict] = []
    facts: dict[str, Any] = {"runtime_config_path": str(runtime_path) if runtime_path else None}
    if runtime is None:
        return issues, facts
    required = ["runtime_id", "python_executable", "expected_freqtrade_version", "dependency_lock_file", "dependency_lock_sha256", "network_access"]
    for key in required:
        if key not in runtime:
            issues.append(issue("environment_not_ready", f"runtime.{key} is required", f"runtime.{key}"))
    runtime_id = runtime.get("runtime_id")
    facts["runtime_id"] = runtime_id
    python_ref = runtime.get("python_executable")
    python_path: Path | None = None
    if python_ref:
        try:
            checked = check_path(repo_root, config, python_ref)
            python_path = repo_root / checked
            facts["python_executable"] = checked
        except PathGuardError as exc:
            issues.append(issue("runtime_python_missing", str(exc), "runtime.python_executable"))
    if not python_path or not python_path.exists():
        issues.append(issue("runtime_python_missing", f"python executable missing: {python_ref}", "runtime.python_executable"))
    elif not python_path.is_file():
        issues.append(issue("runtime_python_missing", f"python executable is not a file: {python_ref}", "runtime.python_executable"))
    else:
        code, output = run_python(python_path, "import sys; print(sys.version.split()[0])", cwd=repo_root)
        if code != 0:
            issues.append(issue("runtime_python_missing", f"python is not executable: {output}", "runtime.python_executable"))
        else:
            facts["python_version"] = output
            expected_python = runtime.get("expected_python_version")
            if expected_python and not output.startswith(str(expected_python)):
                issues.append(issue("environment_not_ready", f"python version mismatch: {output} != {expected_python}", "runtime.expected_python_version"))
        code, output = run_python(
            python_path,
            "import importlib.util, sys; spec = importlib.util.find_spec('freqtrade'); print('present' if spec else 'missing')",
            cwd=repo_root,
        )
        if code != 0 or output != "present":
            issues.append(issue("freqtrade_module_missing", "freqtrade module is not importable", "runtime.python_executable"))
        else:
            code, version = run_python(
                python_path,
                "import freqtrade; print(getattr(freqtrade, '__version__', 'unknown'))",
                cwd=repo_root,
            )
            facts["freqtrade_version"] = version if code == 0 else None
            expected = str(runtime.get("expected_freqtrade_version"))
            if code != 0:
                issues.append(issue("freqtrade_module_missing", f"cannot read freqtrade version: {version}", "runtime.expected_freqtrade_version"))
            elif version != expected:
                issues.append(issue("freqtrade_version_mismatch", f"freqtrade version mismatch: {version} != {expected}", "runtime.expected_freqtrade_version"))
    lock_ref = runtime.get("dependency_lock_file")
    if lock_ref:
        try:
            checked = check_path(repo_root, config, lock_ref)
            lock_path = repo_root / checked
            facts["dependency_lock_file"] = checked
            if not lock_path.exists():
                issues.append(issue("environment_not_ready", f"dependency lock file missing: {checked}", "runtime.dependency_lock_file"))
            else:
                digest = sha256_file(lock_path)
                facts["dependency_lock_sha256"] = digest
                if runtime.get("dependency_lock_sha256") and digest != runtime["dependency_lock_sha256"]:
                    issues.append(issue("environment_not_ready", "dependency lock hash mismatch", "runtime.dependency_lock_sha256"))
        except PathGuardError as exc:
            issues.append(issue("environment_not_ready", str(exc), "runtime.dependency_lock_file"))
    if runtime.get("network_access") != "disabled":
        issues.append(issue("environment_not_ready", "runtime.network_access must be disabled", "runtime.network_access"))
    if runtime.get("invocation") not in {"python_module"}:
        issues.append(issue("environment_not_ready", "runtime.invocation must be python_module", "runtime.invocation"))
    freeze_ref = runtime.get("dependency_freeze_file")
    if freeze_ref:
        try:
            checked = check_path(repo_root, config, freeze_ref)
            freeze_path = repo_root / checked
            facts["dependency_freeze_file"] = checked
            if not freeze_path.exists():
                issues.append(issue("environment_not_ready", f"dependency freeze file missing: {checked}", "runtime.dependency_freeze_file"))
            else:
                digest = sha256_file(freeze_path)
                facts["dependency_freeze_sha256"] = digest
                if runtime.get("dependency_freeze_sha256") and digest != runtime["dependency_freeze_sha256"]:
                    issues.append(issue("environment_not_ready", "dependency freeze hash mismatch", "runtime.dependency_freeze_sha256"))
        except PathGuardError as exc:
            issues.append(issue("environment_not_ready", str(exc), "runtime.dependency_freeze_file"))
    return issues, facts


def check_dataset(repo_root: Path, config: dict) -> tuple[list[dict], dict]:
    issues: list[dict] = []
    facts: dict[str, Any] = {}
    fixed = config.get("fixed_backtest") or {}
    manifest_ref = fixed.get("dataset_manifest")
    if not manifest_ref:
        return [issue("dataset_manifest_missing", "fixed_backtest.dataset_manifest is required", "fixed_backtest.dataset_manifest")], facts
    try:
        checked_manifest = check_path(repo_root, config, manifest_ref)
        manifest_path = repo_root / checked_manifest
        facts["dataset_manifest"] = checked_manifest
    except PathGuardError as exc:
        return [issue("dataset_manifest_missing", str(exc), "fixed_backtest.dataset_manifest")], facts
    if not manifest_path.exists():
        return [issue("dataset_manifest_missing", f"dataset manifest missing: {checked_manifest}", "fixed_backtest.dataset_manifest")], facts
    try:
        manifest = load_yaml_or_json(manifest_path)
    except Exception as exc:
        return [issue("dataset_manifest_missing", f"dataset manifest is not parseable: {exc}", "fixed_backtest.dataset_manifest")], facts
    facts["dataset_id"] = manifest.get("dataset_id")
    expected_dataset_id = fixed.get("dataset_id")
    if expected_dataset_id and manifest.get("dataset_id") != expected_dataset_id:
        issues.append(issue("environment_not_ready", f"dataset_id mismatch: {manifest.get('dataset_id')} != {expected_dataset_id}", "fixed_backtest.dataset_id"))
    data_path_ref = manifest.get("data_path") or fixed.get("datadir")
    if not data_path_ref:
        issues.append(issue("dataset_missing", "dataset data_path is required", "dataset.data_path"))
        return issues, facts
    try:
        checked_data = check_path(repo_root, config, data_path_ref)
        data_path = repo_root / checked_data
        facts["dataset_data_path"] = checked_data
    except PathGuardError as exc:
        issues.append(issue("dataset_missing", str(exc), "dataset.data_path"))
        return issues, facts
    if not data_path.exists() or not data_path.is_dir():
        issues.append(issue("dataset_missing", f"dataset data directory missing: {checked_data}", "dataset.data_path"))
    if manifest.get("campaign_mutable") is not False:
        issues.append(issue("environment_not_ready", "dataset must be campaign_mutable: false", "dataset.campaign_mutable"))
    if manifest.get("network_accessed_during_campaign") is not False:
        issues.append(issue("environment_not_ready", "dataset must record network_accessed_during_campaign: false", "dataset.network_accessed_during_campaign"))
    pairs = set(manifest.get("pairs") or [])
    requested_pairs = set(fixed.get("pairs") or [])
    missing_pairs = sorted(requested_pairs - pairs)
    if missing_pairs:
        issues.append(issue("environment_not_ready", f"pairs not in dataset manifest: {', '.join(missing_pairs)}", "fixed_backtest.pairs"))
    timeframes = set(manifest.get("timeframes") or [])
    if fixed.get("timeframe") not in timeframes:
        issues.append(issue("environment_not_ready", f"timeframe not in dataset manifest: {fixed.get('timeframe')}", "fixed_backtest.timeframe"))
    if not timerange_contains(str(manifest.get("timerange", "")), str(fixed.get("timerange", ""))):
        issues.append(issue("environment_not_ready", f"timerange not covered by dataset: {fixed.get('timerange')}", "fixed_backtest.timerange"))
    files = manifest.get("files") or []
    if not files:
        issues.append(issue("dataset_missing", "dataset manifest has no files", "dataset.files"))
    facts["dataset_files"] = []
    for item in files:
        if not isinstance(item, dict):
            issues.append(issue("dataset_manifest_missing", "dataset file entry must be an object", "dataset.files"))
            continue
        rel_path = item.get("path")
        if not rel_path:
            issues.append(issue("dataset_manifest_missing", "dataset file path is required", "dataset.files.path"))
            continue
        try:
            checked_file = check_path(repo_root, config, rel_path)
            file_path = repo_root / checked_file
        except PathGuardError as exc:
            issues.append(issue("dataset_missing", str(exc), "dataset.files.path"))
            continue
        if not file_path.exists():
            issues.append(issue("dataset_missing", f"dataset file missing: {checked_file}", "dataset.files.path"))
            continue
        size = file_path.stat().st_size
        digest = sha256_file(file_path)
        facts["dataset_files"].append({"path": checked_file, "bytes": size, "sha256": digest})
        if int(item.get("bytes", -1)) != size or item.get("sha256") != digest:
            issues.append(issue("dataset_hash_mismatch", f"dataset hash/size mismatch: {checked_file}", "dataset.files"))
    return issues, facts


def check_campaign(repo_root: Path, config: dict) -> tuple[list[dict], dict]:
    issues: list[dict] = []
    facts: dict[str, Any] = {}
    if config.get("runner_type") != "fixed_backtest" or config.get("mode") != "fixed_backtest":
        issues.append(issue("validation_error", "campaign runner type must be fixed_backtest", "runner_type"))
    fixed = config.get("fixed_backtest") or {}
    for field in ["strategy_file", "config"]:
        value = fixed.get(field)
        if not value:
            issues.append(issue("validation_error", f"fixed_backtest.{field} is required", f"fixed_backtest.{field}"))
            continue
        try:
            checked = check_path(repo_root, config, value)
            facts[field] = checked
            if not (repo_root / checked).exists():
                issues.append(issue("environment_not_ready", f"{field} missing: {checked}", f"fixed_backtest.{field}"))
        except PathGuardError as exc:
            issues.append(issue("environment_not_ready", str(exc), f"fixed_backtest.{field}"))
    try:
        check_path(repo_root, config, "user_data/config_live.json")
        issues.append(issue("environment_not_ready", "live config guard did not block user_data/config_live.json", "scope.blocked_paths"))
    except PathGuardError:
        facts["live_guard"] = "blocked"
    try:
        check_path(repo_root, config, "scripts/start_bot.sh")
        issues.append(issue("environment_not_ready", "server/bot guard did not block scripts/start_bot.sh", "scope.blocked_paths"))
    except PathGuardError:
        facts["server_guard"] = "blocked"
    result_root = repo_root / "research" / "results"
    facts["output_parent"] = "research/results"
    if result_root.exists():
        writable = os.access(result_root, os.W_OK)
    else:
        writable = os.access(result_root.parent, os.W_OK)
    if not writable:
        issues.append(issue("environment_not_ready", "research/results is not writable", "research/results"))
    return issues, facts


def run_environment_doctor(repo_root: str | Path, campaign_config_or_path: dict | str | Path, runtime_path: str | Path | None = None) -> dict:
    repo_root = Path(repo_root).resolve()
    if isinstance(campaign_config_or_path, dict):
        config = campaign_config_or_path
        campaign_path = None
    else:
        campaign_path = Path(campaign_config_or_path)
        config = load_campaign(campaign_path)
    issues: list[dict] = []
    facts: dict[str, Any] = {
        "campaign_id": config.get("campaign_id"),
        "campaign_path": str(campaign_path) if campaign_path else None,
    }
    runtime, runtime_issues, resolved_runtime_path = load_runtime_config(repo_root, config, runtime_path)
    issues.extend(runtime_issues)
    runtime_errors, runtime_facts = check_runtime(repo_root, config, runtime, resolved_runtime_path)
    dataset_errors, dataset_facts = check_dataset(repo_root, config)
    campaign_errors, campaign_facts = check_campaign(repo_root, config)
    issues.extend(runtime_errors)
    issues.extend(dataset_errors)
    issues.extend(campaign_errors)
    facts.update(runtime_facts)
    facts.update(dataset_facts)
    facts.update(campaign_facts)
    return {
        "ok": not issues,
        "issues": issues,
        "facts": facts,
        "reason_codes": sorted({item["reason_code"] for item in issues}),
    }


def print_human(report: dict) -> None:
    print(f"environment doctor: {'pass' if report['ok'] else 'fail'}")
    print(f"campaign_id: {report['facts'].get('campaign_id')}")
    if report["issues"]:
        print("issues:")
        for item in report["issues"]:
            print(f"- {item['reason_code']} [{item['failure_type']}]: {item['message']}")
    else:
        print("issues: none")
    print("facts:")
    for key in sorted(report["facts"]):
        print(f"- {key}: {report['facts'][key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only fixed Freqtrade research environment doctor.")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--runtime")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run_environment_doctor(Path.cwd(), args.campaign, runtime_path=args.runtime)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print_human(report)
    return 1 if args.strict and not report["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
