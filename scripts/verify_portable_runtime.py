#!/usr/bin/env python3
"""Verify hydrated Runtime assets, versions, imports, and offline Backtesting initialization."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import hashlib
from pathlib import Path
from typing import Any

from portable_runtime_assets import (
    CCXT_VERSION,
    FREQTRADE_VERSION,
    MANIFEST_PATH,
    PYTHON_VERSION,
    TARGET_ROOT,
    PortableRuntimeError,
    load_manifest,
    run_command,
    runtime_identity,
    verify_runtime_files,
)


def initialization_child(repo: Path) -> dict[str, Any]:
    opened: set[str] = set()

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
            try:
                opened.add(Path(args[0]).resolve().as_posix())
            except (OSError, ValueError):
                pass

    sys.addaudithook(audit)
    sys.path.insert(0, str(repo / "scripts"))
    from run_offline_backtest import NetworkBlocker, setup_backtest_config
    from sealed_exchange_factory import create_sealed_exchange
    from freqtrade.optimize.backtesting import Backtesting

    with tempfile.TemporaryDirectory(prefix="portable-runtime-init-") as temp:
        temp_root = Path(temp)
        data = temp_root / "data"
        output = temp_root / "output"
        data.mkdir()
        output.mkdir()
        spec = {
            "strategy": "RegimeAwareV6",
            "strategy_path": "strategies",
            "config": "research/runtime/demo-futures-backtest-config.json",
            "timerange": "1706947200-1711447200",
            "timeframe": "1h",
            "datadir": data.as_posix(),
            "fee": "0.0004",
            "pairs": ["BTC/USDT:USDT"],
        }
        network = NetworkBlocker()
        with network:
            config = setup_backtest_config(spec, output)
            config["user_data_dir"] = temp_root / "user_data"
            exchange = create_sealed_exchange(config, repo / "research/exchange_snapshots/binance-usdm-futures-2025-8-demo")
            try:
                backtesting = Backtesting(config, exchange=exchange)
                strategies = [item.get_strategy_name() for item in backtesting.strategylist]
            finally:
                exchange.close()
    target_root = (repo / TARGET_ROOT).resolve()
    runtime_reads = sorted(
        path
        for path in opened
        if path.startswith(target_root.as_posix() + "/") and Path(path).is_file()
    )
    return {
        "status": "passed",
        "backtesting_import": Backtesting.__module__,
        "backtesting_initialized": True,
        "backtest_start_called": False,
        "strategy_loaded": strategies,
        "network_attempts": network.attempts,
        "runtime_files_read": runtime_reads,
        "runtime_file_read_count": len(runtime_reads),
    }


def verify(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    manifest = load_manifest(repo)
    files = verify_runtime_files(repo, manifest)
    python = repo / TARGET_ROOT / "Scripts/python.exe"
    identity = runtime_identity(python)
    if Path(identity["executable"]).resolve() != python.resolve():
        raise PortableRuntimeError(f"hydrated_python_identity_mismatch:{identity['executable']}")
    if identity["python"] != PYTHON_VERSION or identity["freqtrade"] != FREQTRADE_VERSION or identity["ccxt"] != CCXT_VERSION:
        raise PortableRuntimeError(f"hydrated_runtime_version_mismatch:{identity}")
    version = run_command([str(python), "-B", "-m", "freqtrade", "--version"], cwd=repo)
    if version.returncode != 0 or FREQTRADE_VERSION not in (version.stdout + version.stderr):
        raise PortableRuntimeError(f"freqtrade_cli_version_failed:{version.stdout}:{version.stderr}")
    import_check = run_command([str(python), "-B", "-I", "-c", "from freqtrade.optimize.backtesting import Backtesting; import ccxt; print(Backtesting.__module__, ccxt.__version__)"], cwd=repo)
    if import_check.returncode != 0 or CCXT_VERSION not in import_check.stdout:
        raise PortableRuntimeError(f"backtesting_import_failed:{import_check.stderr}")
    child = run_command([str(python), "-B", str(Path(__file__).resolve()), "--initialization-child", "--repo", str(repo)], cwd=repo, timeout=300)
    if child.returncode != 0:
        raise PortableRuntimeError(f"offline_backtesting_initialization_failed:{child.stdout[-2000:]}:{child.stderr[-2000:]}")
    initialization = json.loads(child.stdout.strip().splitlines()[-1])
    expected_targets = {entry["repo_relative_target"] for entry in manifest["files"]}
    unexpected_reads = []
    for raw in initialization["runtime_files_read"]:
        relative = Path(raw).resolve().relative_to(repo).as_posix()
        if relative not in expected_targets:
            unexpected_reads.append(relative)
    if unexpected_reads:
        raise PortableRuntimeError(f"runtime_read_outside_manifest:{unexpected_reads[:5]}")
    forbidden_network = [item for item in initialization["network_attempts"] if item.get("blocked") or not item.get("loopback")]
    if forbidden_network:
        raise PortableRuntimeError(f"offline_initialization_network_violation:{forbidden_network}")
    reads = initialization.pop("runtime_files_read")
    initialization["runtime_file_reads_sha256"] = hashlib.sha256(
        json.dumps(reads, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    sys.path.insert(0, str(repo / "scripts"))
    from research_director_common import fingerprint, load_document

    stopped = json.loads(
        (repo / "research/analysis/ranging-short-temporal-review-v1/campaign-stopped.json").read_text(
            encoding="utf-8"
        )
    )
    campaign = load_document(
        repo
        / "research/director/compiled/ranging-short-branch-decision-review-v1-temporal-v2/campaign.yaml"
    )
    computed_campaign_fingerprint = fingerprint(
        {
            key: value
            for key, value in campaign.items()
            if key not in {"compiled_at", "campaign_fingerprint"}
        }
    )
    return {
        **files,
        "python": identity,
        "freqtrade_module_version": FREQTRADE_VERSION,
        "ccxt_module_version": CCXT_VERSION,
        "freqtrade_cli_version_passed": True,
        "backtesting_import_passed": True,
        "offline_backtesting_initialization": initialization,
        "governance_boundary": {
            "original_stop_status": stopped["status"],
            "original_stop_reason": stopped["reason_code"],
            "campaign_fingerprint": campaign["campaign_fingerprint"],
            "campaign_fingerprint_verified": computed_campaign_fingerprint
            == campaign["campaign_fingerprint"]
            == stopped["campaign_fingerprint"],
        },
        "candidate_loaded": False,
        "backtest_executed": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialization-child", action="store_true")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = (args.repo or Path(__file__).resolve().parents[1]).resolve()
    try:
        result = initialization_child(repo) if args.initialization_child else verify(repo)
    except Exception as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, indent=2))
        return 2
    if args.output and not args.initialization_child:
        output = args.output if args.output.is_absolute() else repo / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
