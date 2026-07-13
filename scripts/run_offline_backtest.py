#!/usr/bin/env python3
"""Run a real Freqtrade backtest with a sealed offline exchange snapshot."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import socket
import sys
import traceback
from pathlib import Path
from typing import Any

from backtest_execution_namespace import NamespaceContractError, extract_exact_result
from research_control import load_campaign
from run_experiment import (
    artifact_hashes,
    compare_core_metrics,
    core_metrics_signature,
    dump_json,
    dump_manifest,
    evaluate_acceptance,
    find_result_json,
    git_sha,
    input_fingerprint,
    parse_metrics,
    repo_rel,
    sha256_file,
    utc_now,
)
from sealed_exchange_factory import OfflineContractViolation, create_sealed_exchange
from validate_exchange_snapshot import validate_snapshot


class NetworkBlocked(RuntimeError):
    pass


class NetworkBlocker:
    def __init__(self):
        self.attempts: list[dict[str, Any]] = []
        self._orig_socket_connect = None
        self._orig_create_connection = None

    def _address(self, address) -> tuple[str, int | None]:
        host = None
        port = None
        if isinstance(address, tuple) and address:
            host = address[0]
            port = address[1] if len(address) > 1 else None
        return str(host or address), port

    def _is_loopback(self, host: str) -> bool:
        return host in {"127.0.0.1", "::1", "localhost"}

    def _record_blocked(self, address):
        host, port = self._address(address)
        self.attempts.append({"host": host, "port": port, "blocked": True})
        raise NetworkBlocked(f"network disabled for offline backtest: {address}")

    def _record_allowed_loopback(self, address):
        host, port = self._address(address)
        self.attempts.append({"host": host, "port": port, "blocked": False, "loopback": True})

    def __enter__(self):
        self._orig_socket_connect = socket.socket.connect
        self._orig_create_connection = socket.create_connection
        blocker = self

        def blocked_connect(sock, address):
            host, _port = blocker._address(address)
            if blocker._is_loopback(host):
                blocker._record_allowed_loopback(address)
                return blocker._orig_socket_connect(sock, address)
            return blocker._record_blocked(address)

        def blocked_create_connection(address, *args, **kwargs):
            host, _port = blocker._address(address)
            if blocker._is_loopback(host):
                blocker._record_allowed_loopback(address)
                return blocker._orig_create_connection(address, *args, **kwargs)
            return blocker._record_blocked(address)

        socket.socket.connect = blocked_connect
        socket.create_connection = blocked_create_connection
        return self

    def __exit__(self, exc_type, exc, tb):
        socket.socket.connect = self._orig_socket_connect
        socket.create_connection = self._orig_create_connection
        return False


def stable_input_hash(manifest: dict) -> str:
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def setup_backtest_config(spec: dict, result_dir: Path) -> dict:
    from freqtrade.commands.optimize_commands import setup_optimize_configuration
    from freqtrade.enums import RunMode

    args = {
        "config": [spec["config"]],
        "strategy": spec["strategy"],
        "strategy_path": spec.get("strategy_path", "strategies"),
        "timerange": spec["timerange"],
        "timeframe": spec["timeframe"],
        "datadir": spec["datadir"],
        "fee": float(spec["fee"]),
        "pairs": list(spec["pairs"]),
        "export": "trades",
        "exportfilename": str(result_dir / "freqtrade-backtest-result.json"),
        "exportdirectory": str(result_dir),
        "backtest_breakdown": ["day"],
        "backtest_cache": "none",
        "verbosity": 0,
        "print_colorized": False,
    }
    config = setup_optimize_configuration(args, RunMode.BACKTEST)
    config["fee"] = float(spec["fee"])
    config["timeframe"] = spec["timeframe"]
    config["pairs"] = list(spec["pairs"])
    config["exchange"]["pair_whitelist"] = list(spec["pairs"])
    config["export"] = "trades"
    config["exportfilename"] = result_dir / "freqtrade-backtest-result.json"
    config["exportdirectory"] = result_dir
    config["backtest_cache"] = "none"
    config.pop("freqai", None)
    config.pop("telegram", None)
    config.pop("api_server", None)
    config["exchange"]["enable_ws"] = False
    return config


def run_offline_backtest(
    repo_root: str | Path,
    campaign: dict,
    experiment_id: int,
    execution_run_id: str,
    snapshot_dir: str | Path,
    *,
    output_root: str | Path | None = None,
    execution_context: dict[str, Any] | None = None,
) -> dict:
    repo_root = Path(repo_root).resolve()
    spec = dict(campaign.get("fixed_backtest") or {})
    campaign_id = campaign["campaign_id"]
    strict_namespace = output_root is not None or execution_context is not None
    if strict_namespace and (output_root is None or execution_context is None):
        raise NamespaceContractError("output_root_contract_violation", "output_root and execution_context are both required")
    if strict_namespace:
        result_dir = Path(output_root).resolve()
        if not result_dir.is_dir():
            raise NamespaceContractError("output_root_contract_violation", "pre-created execution namespace is missing")
        if execution_context["execution_id"] != execution_run_id:
            raise NamespaceContractError("output_root_contract_violation", "execution ID differs across call boundary")
    else:
        result_dir = repo_root / "research" / "results" / campaign_id / str(experiment_id) / execution_run_id
        result_dir.mkdir(parents=True, exist_ok=True)
    report_path = result_dir / "runner-report.json"
    started = utc_now()
    started_ns = int((execution_context or {}).get("started_ns") or 0)
    manifest: dict[str, Any] = {
        "campaign_id": campaign_id,
        "experiment_id": experiment_id,
        "execution_run_id": execution_run_id,
        "runner_type": "sealed_offline_backtest",
        "base_git_sha": git_sha(repo_root),
        "started_at": started,
        "strategy": spec["strategy"],
        "strategy_file": spec["strategy_file"],
        "strategy_file_sha256": sha256_file(repo_root / spec["strategy_file"]),
        "config": spec["config"],
        "config_sha256": sha256_file(repo_root / spec["config"]),
        "dataset_id": spec.get("dataset_id"),
        "dataset_manifest": spec.get("dataset_manifest"),
        "dataset_manifest_sha256": sha256_file(repo_root / spec["dataset_manifest"]),
        "timerange": spec["timerange"],
        "timeframe": spec["timeframe"],
        "pairs": spec["pairs"],
        "fee": spec["fee"],
        "exchange_snapshot": str(snapshot_dir),
        "network_policy_id": f"socket-blocker-{execution_run_id}",
        "network_policy_enabled": True,
        "output_root": repo_rel(repo_root, result_dir),
        "expected_output_root": (execution_context or {}).get("expected_output_root"),
        "received_output_root": repo_rel(repo_root, result_dir),
        "resolved_output_root": result_dir.as_posix(),
        "attempt_id": (execution_context or {}).get("attempt_id"),
        "execution_id": (execution_context or {}).get("execution_id", execution_run_id),
    }
    snapshot_validation = validate_snapshot(snapshot_dir, "2025.8", "4.5.64", "3.12")
    manifest["exchange_snapshot_aggregate_sha256"] = snapshot_validation["manifest"].get("aggregate_sha256")
    manifest["offline_input_sha256"] = stable_input_hash(manifest)
    manifest["input_fingerprint"] = input_fingerprint(
        {
            "base_git_sha": manifest["base_git_sha"],
            "runtime_id": "local-freqtrade-2025-8",
            "freqtrade_version": "2025.8",
            "python_runtime_version": sys.version.split()[0],
            "strategy": spec["strategy"],
            "strategy_file_sha256": manifest["strategy_file_sha256"],
            "config_sha256": manifest["config_sha256"],
            "dataset_id": spec.get("dataset_id"),
            "dataset_files_signature": manifest.get("dataset_manifest_sha256"),
            "timerange": spec["timerange"],
            "timeframe": spec["timeframe"],
            "pairs": spec["pairs"],
            "fee": spec["fee"],
            "subcommand": "sealed_offline_backtest",
        }
    )

    command_record = {
        "entrypoint": "scripts/run_offline_backtest.py",
        "shell": False,
        "execution_run_id": execution_run_id,
        "snapshot_dir": str(snapshot_dir),
        "output_root": repo_rel(repo_root, result_dir),
        "attempt_id": (execution_context or {}).get("attempt_id"),
        "execution_id": (execution_context or {}).get("execution_id", execution_run_id),
    }
    dump_json(result_dir / "command.json", command_record)

    network = NetworkBlocker()
    exit_code = 0
    try:
        with (result_dir / "stdout.log").open("w", encoding="utf-8") as stdout, (result_dir / "stderr.log").open("w", encoding="utf-8") as stderr:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with network:
                    config = setup_backtest_config(spec, result_dir)
                    if strict_namespace:
                        config["export"] = "none"
                    exchange = create_sealed_exchange(config, snapshot_dir)
                    try:
                        from freqtrade.optimize.backtesting import Backtesting

                        backtesting = Backtesting(config, exchange=exchange)
                        backtesting.start()
                        if strict_namespace:
                            from freqtrade.optimize.optimize_reports import store_backtest_results

                            config["export"] = "trades"
                            store_backtest_results(
                                config,
                                backtesting.results,
                                execution_context["execution_id"],
                                strategy_files={item.get_strategy_name(): item.__file__ for item in backtesting.strategylist},
                            )
                    finally:
                        exchange.close()
    except NetworkBlocked as exc:
        exit_code = 1
        status = "failed"
        failure_type = "infra_permanent"
        reason_code = "offline_contract_violation"
        message = str(exc)
        (result_dir / "stderr.log").write_text(traceback.format_exc(), encoding="utf-8")
    except OfflineContractViolation as exc:
        exit_code = 1
        status = "failed"
        failure_type = exc.failure_type
        reason_code = exc.reason_code
        message = str(exc)
        (result_dir / "stderr.log").write_text(traceback.format_exc(), encoding="utf-8")
    except NamespaceContractError as exc:
        exit_code = 1
        status = "failed"
        failure_type = exc.failure_class
        reason_code = exc.reason_code
        message = str(exc)
        (result_dir / "stderr.log").write_text(traceback.format_exc(), encoding="utf-8")
    except Exception as exc:
        exit_code = 1
        status = "failed"
        failure_type = "backtest_error"
        reason_code = "offline_backtest_error"
        message = str(exc)
        (result_dir / "stderr.log").write_text(traceback.format_exc(), encoding="utf-8")
    else:
        try:
            if strict_namespace:
                archive_path = result_dir / execution_context["expected_raw_archive_filename"]
                result_path = result_dir / execution_context["expected_raw_result_filename"]
                extract_exact_result(
                    archive_path,
                    result_path,
                    execution_context["expected_raw_result_filename"],
                    result_dir,
                    started_ns,
                )
            else:
                result_path = find_result_json(result_dir)
            metrics = parse_metrics(result_path, spec)
            dump_json(result_dir / "metrics.json", metrics)
            status, failure_type, reason_code, gate_reasons, stage_acceptance = evaluate_acceptance(
                metrics, spec.get("acceptance_gate") or {}
            )
            message = "; ".join(gate_reasons)
        except NamespaceContractError as exc:
            exit_code = 1
            status = "failed"
            failure_type = exc.failure_class
            reason_code = exc.reason_code
            message = str(exc)
            metrics = None
        except Exception as exc:
            exit_code = 1
            status = "failed"
            failure_type = "output_parse_error"
            reason_code = "output_parse_error"
            message = str(exc)
            metrics = None

    manifest.update(
        {
            "completed_at": utc_now(),
            "exit_code": exit_code,
            "network_attempts": network.attempts,
            "network_attempt_detected": bool(network.attempts),
            "termination_reason": reason_code or status,
        }
    )
    report = {
        "status": status,
        "failure_type": failure_type,
        "reason_code": reason_code,
        "message": message,
        "stage_acceptance": locals().get("stage_acceptance"),
        "execution_run_id": execution_run_id,
        "input_fingerprint": manifest["input_fingerprint"],
        "exchange_snapshot_aggregate_sha256": manifest["exchange_snapshot_aggregate_sha256"],
        "network_policy_id": manifest["network_policy_id"],
        "network_attempts": network.attempts,
        "attempt_id": (execution_context or {}).get("attempt_id"),
        "execution_id": (execution_context or {}).get("execution_id", execution_run_id),
        "output_root": repo_rel(repo_root, result_dir),
        "resolved_output_root": result_dir.as_posix(),
    }
    if status == "accepted" and metrics is not None:
        report["metrics_path"] = "metrics.json"
        report["core_metrics_signature"] = core_metrics_signature(metrics)
        report["raw_result_path"] = result_path.name
        report["raw_result_sha256"] = sha256_file(result_path)
    if status == "rejected" and metrics is not None:
        report["metrics_path"] = "metrics.json"
        report["core_metrics_signature"] = core_metrics_signature(metrics)
        report["raw_result_path"] = result_path.name
        report["raw_result_sha256"] = sha256_file(result_path)
    dump_json(report_path, report)
    dump_manifest(result_dir / "manifest.yaml", manifest)
    dump_json(result_dir / "artifact-hashes.json", artifact_hashes(result_dir))
    return {
        "status": status,
        "failure_type": failure_type,
        "reason_code": reason_code,
        "report_path": repo_rel(repo_root, report_path),
        "message": message,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a sealed offline Freqtrade backtest.")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--experiment-id", type=int, required=True)
    parser.add_argument("--execution-run-id", required=True)
    parser.add_argument("--exchange-snapshot", required=True)
    args = parser.parse_args()
    campaign = load_campaign(args.campaign)
    result = run_offline_backtest(Path.cwd(), campaign, args.experiment_id, args.execution_run_id, args.exchange_snapshot)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {"accepted", "rejected"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
