#!/usr/bin/env python3
"""Fixed Freqtrade backtest runner for Research Campaign experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_guard import PathGuardError, check_path, check_paths


ALLOWED_SUBCOMMANDS = {"backtesting"}
FORBIDDEN_ARGS = {
    "trade",
    "hyperopt",
    "lookahead-analysis",
    "recursive-analysis",
    "download-data",
    "webserver",
}
MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 25 * 1024 * 1024
CORE_METRIC_KEYS = (
    "total_trades",
    "long_trade_count",
    "short_trade_count",
    "total_profit",
    "total_profit_pct",
    "max_drawdown",
    "profit_factor",
    "winrate",
    "avg_leverage",
    "funding_fees",
    "trade_detail_count",
    "trade_detail_sha256",
)


class RunnerError(RuntimeError):
    def __init__(self, failure_type: str, message: str, reason_code: str | None = None):
        super().__init__(message)
        self.failure_type = failure_type
        self.message = message
        self.reason_code = reason_code or failure_type


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: str | Path, max_bytes: int | None = None) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise RunnerError("validation_error", f"artifact too large: {path}")
            digest.update(chunk)
    return digest.hexdigest()


def write_limited(path: Path, data: bytes, max_bytes: int = MAX_LOG_BYTES) -> None:
    if len(data) > max_bytes:
        path.write_bytes(data[:max_bytes] + b"\n[truncated]\n")
    else:
        path.write_bytes(data)


def repo_rel(repo_root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(repo_root.resolve()).as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def dump_manifest(path: Path, manifest: dict) -> None:
    lines = []
    for key, value in manifest.items():
        if isinstance(value, list):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        elif isinstance(value, dict):
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_command_record(result_dir: Path, command: list[str] | None, failure_type: str | None = None, message: str | None = None) -> None:
    path = result_dir / "command.json"
    if path.exists():
        return
    payload: dict[str, Any] = {
        "command": command,
        "shell": False,
    }
    if failure_type:
        payload["failure_type"] = failure_type
    if message:
        payload["message"] = message
    dump_json(path, payload)


def git_sha(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def is_python_executable(executable: Path) -> bool:
    return executable.name.lower() in {"python.exe", "python", "py.exe", "py"}


def validate_python_executable(repo_root: Path, spec: dict, runtime: dict | None = None) -> str:
    python_ref = None
    if runtime:
        python_ref = runtime.get("python_executable")
    if not python_ref:
        python_ref = spec.get("python_executable") or spec.get("executable")
    if not python_ref:
        raise RunnerError("validation_error", "fixed_backtest.runtime_config or python_executable is required")
    path = Path(str(python_ref))
    if not path.is_absolute():
        path = repo_root / path
    if not path.exists():
        raise RunnerError("infra_permanent", f"python executable missing: {python_ref}", "runtime_python_missing")
    if not is_python_executable(path):
        raise RunnerError("validation_error", f"python executable is not whitelisted: {python_ref}")
    return str(path)


def build_command(repo_root: Path, spec: dict, result_dir: Path, runtime: dict | None = None) -> list[str]:
    executable = validate_python_executable(repo_root, spec, runtime)
    subcommand = str(spec.get("subcommand", "backtesting"))
    if subcommand not in ALLOWED_SUBCOMMANDS:
        raise RunnerError("validation_error", f"subcommand not allowed: {subcommand}")

    strategy = str(spec["strategy"])
    config_path = str(spec["config"])
    timerange = str(spec["timerange"])
    timeframe = str(spec["timeframe"])
    datadir = str(spec["datadir"])
    strategy_path = str(spec.get("strategy_path", "strategies"))
    fee = str(spec["fee"])
    pairs = list(spec["pairs"])
    export_file = result_dir / "freqtrade-backtest-result.json"

    command = [
        executable,
        "-m",
        "freqtrade",
        subcommand,
        "--strategy",
        strategy,
        "--strategy-path",
        strategy_path,
        "--config",
        config_path,
        "--timerange",
        timerange,
        "--timeframe",
        timeframe,
        "--datadir",
        datadir,
        "--fee",
        fee,
        "--export",
        "trades",
        "--export-filename",
        str(export_file),
        "--export-directory",
        str(result_dir),
        "--breakdown",
        "day",
        "--cache",
        "none",
    ]
    for pair in pairs:
        command.extend(["--pairs", str(pair)])

    if spec.get("fake_freqtrade_script"):
        script = str(spec["fake_freqtrade_script"])
        command = [executable, script, subcommand, *command[4:]]

    forbidden_seen = [item for item in command if item in FORBIDDEN_ARGS]
    if forbidden_seen:
        raise RunnerError("validation_error", f"forbidden command args: {forbidden_seen}")
    return command


def kill_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            time.sleep(0.5)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_command(command: list[str], cwd: Path, timeout_seconds: int, env: dict[str, str] | None = None) -> tuple[int, bytes, bytes, bool]:
    kwargs: dict[str, Any] = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": False,
    }
    if env is not None:
        kwargs["env"] = env
    if os.name != "nt":
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        return int(process.returncode), stdout, stderr, False
    except subprocess.TimeoutExpired:
        kill_process_tree(process)
        stdout, stderr = process.communicate()
        return int(process.returncode if process.returncode is not None else -9), stdout, stderr, True


def find_result_json(result_dir: Path) -> Path:
    direct = result_dir / "freqtrade-backtest-result.json"
    if direct.exists():
        return direct
    preferred = sorted(
        path
        for path in result_dir.glob("backtest-result*.json")
        if not path.name.endswith(".meta.json")
    )
    if preferred:
        return preferred[0]
    zips = sorted(result_dir.glob("*.zip"))
    for item in zips:
        with zipfile.ZipFile(item) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.endswith(".json") and not name.endswith(".meta.json")
            ]
            if names:
                out = result_dir / Path(names[0]).name
                out.write_bytes(archive.read(names[0]))
                return out
    candidates = sorted(
        path
        for path in result_dir.glob("*.json")
        if path.name not in {".last_result.json", "artifact-hashes.json", "command.json", "runner-report.json"}
        and not path.name.endswith(".meta.json")
    )
    if candidates:
        return candidates[0]
    raise RunnerError("output_parse_error", "no Freqtrade result JSON found")


def dataset_files_signature(files: list[dict]) -> str:
    entries = [
        {"path": item.get("path"), "bytes": item.get("bytes"), "sha256": item.get("sha256")}
        for item in files
    ]
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def first_present(mapping: dict, keys: list[str]) -> tuple[str | None, Any]:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return key, mapping[key]
    return None, None


def normalize_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def locate_strategy_block(payload: Any, strategy: str) -> dict:
    if not isinstance(payload, dict):
        raise RunnerError("output_parse_error", "result JSON root is not an object")
    if payload.get("schema") == "fake-freqtrade-backtest-v1":
        return payload
    if isinstance(payload.get("strategy"), dict):
        strategies = payload["strategy"]
        if strategy in strategies and isinstance(strategies[strategy], dict):
            block = strategies[strategy]
            block["_schema_hint"] = "freqtrade-strategy-map"
            return block
        for value in strategies.values():
            if isinstance(value, dict):
                value["_schema_hint"] = "freqtrade-strategy-map"
                return value
    if payload.get("strategy_name") == strategy or payload.get("strategy") == strategy:
        return payload
    raise RunnerError("output_parse_error", "unsupported Freqtrade result schema")


def collect_trade_rows(payload: Any, strategy: str) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    candidates = []
    if isinstance(payload.get("trades"), list):
        candidates.append(payload["trades"])
    if isinstance(payload.get("strategy"), dict):
        block = payload["strategy"].get(strategy)
        if isinstance(block, dict) and isinstance(block.get("trades"), list):
            candidates.append(block["trades"])
        for value in payload["strategy"].values():
            if isinstance(value, dict) and isinstance(value.get("trades"), list):
                candidates.append(value["trades"])
    if isinstance(payload.get("all_trades"), list):
        candidates.append(payload["all_trades"])
    rows = next((item for item in candidates if item), [])
    normalized = []
    stable_keys = [
        "pair",
        "open_date",
        "close_date",
        "open_rate",
        "close_rate",
        "amount",
        "stake_amount",
        "profit_abs",
        "profit_ratio",
        "funding_fees",
        "funding_fee",
        "liquidation_price",
        "trade_duration",
        "duration",
        "enter_tag",
        "exit_reason",
        "is_short",
        "leverage",
    ]
    for row in rows:
        if isinstance(row, dict):
            normalized.append({key: row.get(key) for key in stable_keys if key in row})
    normalized.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    return normalized


def trade_detail_signature(payload: Any, strategy: str) -> dict:
    rows = collect_trade_rows(payload, strategy)
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "count": len(rows),
        "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    }


def trade_coverage_summary(payload: Any, strategy: str) -> dict:
    rows = collect_trade_rows(payload, strategy)
    long_count = 0
    short_count = 0
    closed_count = 0
    missing_enter_tag = 0
    missing_exit_reason = 0
    funding_total = 0.0
    funding_seen = False
    leverage_values = []
    for row in rows:
        is_short = bool(row.get("is_short"))
        if is_short:
            short_count += 1
        else:
            long_count += 1
        if row.get("close_date") or row.get("exit_reason"):
            closed_count += 1
        if not row.get("enter_tag"):
            missing_enter_tag += 1
        if not row.get("exit_reason"):
            missing_exit_reason += 1
        funding = normalize_number(row.get("funding_fees", row.get("funding_fee")))
        if funding is not None:
            funding_seen = True
            funding_total += float(funding)
        leverage = normalize_number(row.get("leverage"))
        if leverage is not None:
            leverage_values.append(float(leverage))
    return {
        "total": len(rows),
        "long": long_count,
        "short": short_count,
        "closed": closed_count,
        "missing_enter_tag": missing_enter_tag,
        "missing_exit_reason": missing_exit_reason,
        "funding_fees": funding_total if funding_seen else None,
        "avg_leverage": (sum(leverage_values) / len(leverage_values)) if leverage_values else None,
    }


def parse_metrics(result_path: Path, spec: dict) -> dict:
    payload = load_json(result_path)
    strategy = str(spec["strategy"])
    block = locate_strategy_block(payload, strategy)
    trade_sig = trade_detail_signature(payload, strategy)
    coverage = trade_coverage_summary(payload, strategy)
    schema_version = payload.get("schema") or block.get("_schema_hint") or "unknown"
    fields = {
        "total_trades": ["total_trades", "trades", "total_trade_count"],
        "total_profit": ["profit_total_abs", "total_profit", "profit_total"],
        "total_profit_pct": ["profit_total", "total_profit_pct", "profit_total_pct"],
        "max_drawdown": ["max_drawdown", "max_drawdown_abs", "max_drawdown_account"],
        "profit_factor": ["profit_factor"],
        "winrate": ["winrate", "win_rate"],
        "avg_duration": ["holding_avg", "avg_duration", "avg_trade_duration"],
        "start_time": ["backtest_start", "start_time", "timerange_start"],
        "end_time": ["backtest_end", "end_time", "timerange_end"],
    }
    raw: dict[str, Any] = {}
    normalized: dict[str, Any] = {}
    missing = []
    source_keys = {}
    for name, keys in fields.items():
        key, value = first_present(block, keys)
        source_keys[name] = key
        raw[name] = value
        if value is None:
            missing.append(name)
            normalized[name] = None
        elif name in {"start_time", "end_time", "avg_duration"}:
            normalized[name] = value
        else:
            normalized[name] = normalize_number(value)
            if normalized[name] is None:
                missing.append(name)
    normalized["pair_count"] = len(spec.get("pairs") or [])
    normalized["trade_detail_count"] = trade_sig["count"]
    normalized["trade_detail_sha256"] = trade_sig["sha256"]
    normalized["long_trade_count"] = coverage["long"]
    normalized["short_trade_count"] = coverage["short"]
    normalized["closed_trade_count"] = coverage["closed"]
    normalized["missing_enter_tag_count"] = coverage["missing_enter_tag"]
    normalized["missing_exit_reason_count"] = coverage["missing_exit_reason"]
    normalized["funding_fees"] = coverage["funding_fees"]
    normalized["avg_leverage"] = coverage["avg_leverage"]
    raw["pair_count"] = spec.get("pairs") or []
    raw["trade_detail_signature"] = trade_sig
    raw["trade_coverage"] = coverage
    metrics = {
        "schema_version": schema_version,
        "strategy": strategy,
        "timerange": spec["timerange"],
        "raw": raw,
        "normalized": normalized,
        "missing_fields": sorted(set(missing)),
        "source_keys": source_keys,
    }
    return metrics


def evaluate_gate(metrics: dict, gate: dict) -> tuple[str, list[str]]:
    reasons = []
    normalized = metrics["normalized"]
    min_trades = int(gate.get("min_trades", 0))
    max_drawdown = gate.get("max_drawdown")
    if normalized.get("total_trades") is None:
        reasons.append("missing total_trades")
    elif normalized["total_trades"] < min_trades:
        reasons.append(f"total_trades {normalized['total_trades']} < {min_trades}")
    if max_drawdown is not None:
        if normalized.get("max_drawdown") is None:
            reasons.append("missing max_drawdown")
        elif float(normalized["max_drawdown"]) > float(max_drawdown):
            reasons.append(f"max_drawdown {normalized['max_drawdown']} > {max_drawdown}")
    if metrics["missing_fields"]:
        reasons.append(f"missing metrics: {', '.join(metrics['missing_fields'])}")
    return ("rejected" if reasons else "accepted"), reasons


def evaluate_coverage_gate(metrics: dict, gate: dict) -> dict:
    normalized = metrics.get("normalized") or {}
    total = int(normalized.get("total_trades") or normalized.get("trade_detail_count") or 0)
    long_count = int(normalized.get("long_trade_count") or 0)
    short_count = int(normalized.get("short_trade_count") or 0)
    closed_count = int(normalized.get("closed_trade_count") or 0)
    reasons = []
    if total < int(gate.get("min_total_trades", 0)):
        reasons.append(f"total_trades {total} < {int(gate.get('min_total_trades', 0))}")
    if long_count < int(gate.get("min_long_trades", 0)):
        reasons.append(f"long_trade_count {long_count} < {int(gate.get('min_long_trades', 0))}")
    if short_count < int(gate.get("min_short_trades", 0)):
        reasons.append(f"short_trade_count {short_count} < {int(gate.get('min_short_trades', 0))}")
    if gate.get("require_closed_trades") and closed_count < total:
        reasons.append(f"closed_trade_count {closed_count} < total_trades {total}")
    if gate.get("require_enter_tag") and int(normalized.get("missing_enter_tag_count") or 0) > 0:
        reasons.append(f"missing_enter_tag_count {normalized.get('missing_enter_tag_count')}")
    if gate.get("require_exit_reason") and int(normalized.get("missing_exit_reason_count") or 0) > 0:
        reasons.append(f"missing_exit_reason_count {normalized.get('missing_exit_reason_count')}")
    status = "passed" if not reasons else "incomplete"
    reason_code = None if status == "passed" else ("acceptance_fixture_no_trades" if total == 0 else "baseline_coverage_insufficient")
    return {
        "status": status,
        "reason_code": reason_code,
        "failure_type": None if status == "passed" else "validation_error",
        "reasons": reasons,
        "coverage": {
            "total_trades": total,
            "long_trade_count": long_count,
            "short_trade_count": short_count,
            "closed_trade_count": closed_count,
            "missing_enter_tag_count": int(normalized.get("missing_enter_tag_count") or 0),
            "missing_exit_reason_count": int(normalized.get("missing_exit_reason_count") or 0),
        },
    }


def evaluate_acceptance(metrics: dict, gate: dict) -> tuple[str, str | None, str | None, list[str], dict]:
    if "coverage" in gate:
        verdict = evaluate_coverage_gate(metrics, gate["coverage"] or {})
        status = "accepted" if verdict["status"] == "passed" else "rejected"
        return status, verdict["failure_type"], verdict["reason_code"], verdict["reasons"], verdict
    status, reasons = evaluate_gate(metrics, gate)
    failure_type = "candidate_rejected" if status == "rejected" else None
    return status, failure_type, None, reasons, {
        "status": "passed" if status == "accepted" else "failed",
        "reason_code": "candidate_rejected" if status == "rejected" else None,
        "failure_type": failure_type,
        "reasons": reasons,
    }


def core_metrics_signature(metrics: dict) -> dict:
    normalized = metrics.get("normalized") or {}
    core = {key: normalized.get(key) for key in CORE_METRIC_KEYS}
    payload = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return {
        "core_metrics": core,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def compare_core_metrics(first: dict, second: dict) -> dict:
    first_sig = core_metrics_signature(first)
    second_sig = core_metrics_signature(second)
    differences = {
        key: {"first": first_sig["core_metrics"].get(key), "second": second_sig["core_metrics"].get(key)}
        for key in CORE_METRIC_KEYS
        if first_sig["core_metrics"].get(key) != second_sig["core_metrics"].get(key)
    }
    return {
        "consistent": not differences,
        "first_signature": first_sig["sha256"],
        "second_signature": second_sig["sha256"],
        "differences": differences,
        "allowed_different_fields": [
            "started_at",
            "completed_at",
            "duration",
            "stdout timing text",
            "execution_run_id",
            "artifact paths",
        ],
    }


def input_fingerprint(manifest: dict) -> str:
    stable = {
        "base_git_sha": manifest.get("base_git_sha"),
        "runtime_id": manifest.get("runtime_id"),
        "freqtrade_version": manifest.get("freqtrade_version"),
        "python_runtime_version": manifest.get("python_runtime_version"),
        "strategy": manifest.get("strategy"),
        "strategy_file_sha256": manifest.get("strategy_file_sha256"),
        "config_sha256": manifest.get("config_sha256"),
        "dataset_id": manifest.get("dataset_id"),
        "dataset_files_signature": manifest.get("dataset_files_signature"),
        "timerange": manifest.get("timerange"),
        "timeframe": manifest.get("timeframe"),
        "pairs": manifest.get("pairs"),
        "fee": manifest.get("fee"),
        "subcommand": manifest.get("subcommand"),
    }
    payload = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def artifact_hashes(result_dir: Path) -> dict:
    hashes = {}
    for path in sorted(result_dir.rglob("*")):
        if path.is_file():
            if path.stat().st_size > MAX_ARTIFACT_BYTES:
                raise RunnerError("validation_error", f"artifact exceeds size limit: {path}")
            hashes[path.relative_to(result_dir).as_posix()] = {
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
    return hashes


def data_manifest(repo_root: Path, datadir: str, pairs: list[str], timeframe: str) -> dict:
    root = (repo_root / datadir).resolve(strict=False)
    files = []
    if root.exists():
        stems = [pair.replace("/", "_").replace(":", "_") for pair in pairs]
        for path in sorted(root.rglob("*")):
            if path.is_file() and timeframe in path.name and any(stem in path.name for stem in stems):
                files.append(
                    {
                        "path": repo_rel(repo_root, path),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path, max_bytes=MAX_ARTIFACT_BYTES),
                    }
                )
    return {"datadir": datadir, "files": files}


def validate_spec(repo_root: Path, config: dict, spec: dict, result_dir: Path) -> dict:
    required = [
        "strategy",
        "strategy_file",
        "config",
        "timerange",
        "timeframe",
        "pairs",
        "fee",
        "datadir",
    ]
    if not spec.get("fake_freqtrade_script"):
        required.extend(["runtime_config", "dataset_manifest", "dataset_id"])
    missing = [key for key in required if key not in spec]
    if missing:
        raise RunnerError("validation_error", f"fixed_backtest missing keys: {missing}")
    if not isinstance(spec["pairs"], list) or not spec["pairs"]:
        raise RunnerError("validation_error", "fixed_backtest.pairs must be a non-empty list")

    paths = [
        spec["strategy_file"],
        spec.get("strategy_path", "strategies"),
        spec["config"],
        spec["datadir"],
        repo_rel(repo_root, result_dir),
    ]
    if not spec.get("fake_freqtrade_script"):
        paths.extend([spec["runtime_config"], spec["dataset_manifest"]])
    if spec.get("fake_freqtrade_script"):
        paths.append(spec["fake_freqtrade_script"])
    checked = check_paths(repo_root, config, paths)
    for path in [spec["strategy_file"], spec.get("strategy_path", "strategies"), spec["config"]]:
        if not (repo_root / path).exists():
            raise RunnerError("infra_permanent", f"required path missing: {path}", "environment_not_ready")
    return {"checked_paths": checked}


def run_fixed_backtest(
    repo_root: str | Path,
    config: dict,
    experiment_id: int,
    payload: dict,
    verification_run_id: str | None = None,
) -> dict:
    repo_root = Path(repo_root).resolve()
    campaign_id = config["campaign_id"]
    spec = dict(config.get("fixed_backtest") or {})
    spec.update(payload.get("fixed_backtest") or {})
    result_dir = repo_root / "research" / "results" / campaign_id / str(experiment_id)
    if verification_run_id:
        if any(part in verification_run_id for part in ("/", "\\", "..")):
            raise RunnerError("validation_error", f"invalid verification_run_id: {verification_run_id}")
        result_dir = result_dir / verification_run_id
    result_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    report_path = result_dir / "runner-report.json"

    if report_path.exists() and not verification_run_id:
        existing = load_json(report_path)
        if existing.get("idempotent_complete"):
            return {
                "status": existing["status"],
                "failure_type": existing.get("failure_type"),
                "reason_code": existing.get("reason_code"),
                "report_path": repo_rel(repo_root, report_path),
                "message": "existing runner report reused",
            }

    manifest: dict[str, Any] = {
        "campaign_id": campaign_id,
        "experiment_id": experiment_id,
        "base_git_sha": git_sha(repo_root),
        "execution_run_id": verification_run_id or "campaign-default",
        "verification_execution": bool(verification_run_id),
        "started_at": started_at,
        "python_version": sys.version,
    }
    try:
        if spec.get("fake_freqtrade_script"):
            preflight = {"facts": {"freqtrade_version": "fake-test-fixture", "python_version": sys.version.split()[0], "dataset_files": []}}
            runtime = {"runtime_id": "fake-test-runtime", "python_executable": spec.get("python_executable") or spec.get("executable")}
        else:
            from research_environment_doctor import load_runtime_config, run_environment_doctor

            preflight = run_environment_doctor(repo_root, config, runtime_path=spec.get("runtime_config"))
            if not preflight["ok"]:
                reason_codes = preflight["reason_codes"]
                raise RunnerError("infra_permanent", f"environment not ready: {', '.join(reason_codes)}", "environment_not_ready")
            runtime, runtime_issues, _runtime_path = load_runtime_config(repo_root, config, spec.get("runtime_config"))
            if runtime_issues or runtime is None:
                reason_codes = [item["reason_code"] for item in runtime_issues] or ["environment_not_ready"]
                raise RunnerError("infra_permanent", f"runtime not ready: {', '.join(reason_codes)}", "environment_not_ready")
        validation = validate_spec(repo_root, config, spec, result_dir)
        command = build_command(repo_root, spec, result_dir, runtime)
        command_json = {
            "command": command,
            "cwd": str(repo_root),
            "shell": False,
            "timeout_seconds": int(spec.get("timeout_seconds", 300)),
        }
        dump_json(result_dir / "command.json", command_json)

        manifest.update(
            {
                "strategy": spec["strategy"],
                "strategy_file": spec["strategy_file"],
                "strategy_file_sha256": sha256_file(repo_root / spec["strategy_file"]),
                "config": spec["config"],
                "config_sha256": sha256_file(repo_root / spec["config"]),
                "data_manifest": data_manifest(repo_root, spec["datadir"], spec["pairs"], spec["timeframe"]),
                "runtime_id": runtime.get("runtime_id"),
                "freqtrade_version": preflight["facts"].get("freqtrade_version"),
                "python_runtime_version": preflight["facts"].get("python_version"),
                "dataset_id": spec.get("dataset_id"),
                "dataset_manifest": spec.get("dataset_manifest"),
                "dataset_files": preflight["facts"].get("dataset_files"),
                "dataset_files_signature": dataset_files_signature(preflight["facts"].get("dataset_files") or []),
                "timerange": spec["timerange"],
                "timeframe": spec["timeframe"],
                "pairs": spec["pairs"],
                "fee": spec["fee"],
                "subcommand": spec.get("subcommand", "backtesting"),
                "command": command,
                "authorized_paths": validation["checked_paths"],
            }
        )
        manifest["input_fingerprint"] = input_fingerprint(manifest)
        exit_code, stdout, stderr, timed_out = run_command(command, repo_root, int(spec.get("timeout_seconds", 300)))
        write_limited(result_dir / "stdout.log", stdout)
        write_limited(result_dir / "stderr.log", stderr)
        manifest.update(
            {
                "completed_at": utc_now(),
                "exit_code": exit_code,
                "timed_out": timed_out,
                "termination_reason": "timeout" if timed_out else "process_exit",
            }
        )
        if timed_out:
            raise RunnerError("infra_transient", "backtest timed out")
        if exit_code != 0:
            raise RunnerError("backtest_error", f"backtest exited non-zero: {exit_code}")
        if not spec.get("fake_freqtrade_script"):
            postflight = run_environment_doctor(repo_root, config, runtime_path=spec.get("runtime_config"))
            if not postflight["ok"]:
                reason_codes = postflight["reason_codes"]
                raise RunnerError("infra_permanent", f"environment changed after backtest: {', '.join(reason_codes)}", "dataset_hash_mismatch")
            post_signature = dataset_files_signature(postflight["facts"].get("dataset_files") or [])
            if post_signature != manifest["dataset_files_signature"]:
                raise RunnerError("infra_permanent", "dataset hash changed during backtest", "dataset_hash_mismatch")

        result_path = find_result_json(result_dir)
        metrics = parse_metrics(result_path, spec)
        dump_json(result_dir / "metrics.json", metrics)
        status, failure_type, reason_code, gate_reasons, stage_acceptance = evaluate_acceptance(metrics, spec.get("acceptance_gate") or {})
        report = {
            "status": status,
            "failure_type": failure_type,
            "reason_code": reason_code,
            "gate_reasons": gate_reasons,
            "stage_acceptance": stage_acceptance,
            "metrics_path": "metrics.json",
            "result_path": result_path.relative_to(result_dir).as_posix(),
            "core_metrics_signature": core_metrics_signature(metrics),
            "input_fingerprint": manifest["input_fingerprint"],
            "execution_run_id": verification_run_id or "campaign-default",
            "verification_execution": bool(verification_run_id),
            "idempotent_complete": True,
        }
        dump_json(report_path, report)
        manifest["termination_reason"] = status
        manifest["exit_code"] = exit_code
        dump_manifest(result_dir / "manifest.yaml", manifest)
        dump_json(result_dir / "artifact-hashes.json", artifact_hashes(result_dir))
        return {
            "status": status,
            "failure_type": failure_type,
            "reason_code": reason_code,
            "report_path": repo_rel(repo_root, report_path),
            "input_fingerprint": manifest["input_fingerprint"],
            "message": "; ".join(gate_reasons),
        }
    except PathGuardError as exc:
        ensure_command_record(result_dir, None, "guard_violation", str(exc))
        report = {
            "status": "escalated",
            "failure_type": "guard_violation",
            "reason_code": "guard_violation",
            "message": str(exc),
            "idempotent_complete": True,
        }
        dump_json(report_path, report)
        manifest.update({"completed_at": utc_now(), "exit_code": None, "termination_reason": "guard_violation"})
        dump_manifest(result_dir / "manifest.yaml", manifest)
        dump_json(result_dir / "artifact-hashes.json", artifact_hashes(result_dir))
        return {
            "status": "escalated",
            "failure_type": "guard_violation",
            "reason_code": "guard_violation",
            "report_path": repo_rel(repo_root, report_path),
            "message": str(exc),
        }
    except RunnerError as exc:
        ensure_command_record(result_dir, None, exc.failure_type, exc.message)
        report = {
            "status": "failed",
            "failure_type": exc.failure_type,
            "reason_code": exc.reason_code,
            "message": exc.message,
            "idempotent_complete": True,
        }
        dump_json(report_path, report)
        manifest.update({"completed_at": utc_now(), "exit_code": manifest.get("exit_code"), "termination_reason": exc.failure_type})
        dump_manifest(result_dir / "manifest.yaml", manifest)
        dump_json(result_dir / "artifact-hashes.json", artifact_hashes(result_dir))
        return {
            "status": "failed",
            "failure_type": exc.failure_type,
            "reason_code": exc.reason_code,
            "report_path": repo_rel(repo_root, report_path),
            "message": exc.message,
        }


def main() -> int:
    from research_control import load_campaign

    parser = argparse.ArgumentParser(description="Run one fixed backtest experiment outside the orchestrator.")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--experiment-id", type=int, required=True)
    parser.add_argument("--verification-rerun")
    args = parser.parse_args()
    config = load_campaign(args.campaign)
    result = run_fixed_backtest(Path.cwd(), config, args.experiment_id, {}, verification_run_id=args.verification_rerun)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in {"accepted", "rejected"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
