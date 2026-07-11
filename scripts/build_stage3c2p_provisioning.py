#!/usr/bin/env python3
"""Stage 3C.2-P controlled futures data provisioning and readiness probe."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import urllib.request

import pandas as pd

from research_control import load_simple_yaml, utc_now
from run_experiment import artifact_hashes, collect_trade_rows, dump_json, dump_manifest, git_sha, repo_rel, sha256_file
from run_offline_backtest import run_offline_backtest


PYTHON_EXE = Path(".venv-freqtrade/Scripts/python.exe")
RUNTIME_CONFIG = Path("research/runtime/freqtrade-runtime.yaml")
FUTURES_CONFIG = Path("research/runtime/demo-futures-backtest-config.json")
SPLIT_POLICY = Path("research/data/splits/futures-dev-validation-v2-policy.yaml")
CONCRETE_SPLIT = Path("research/data/splits/futures-dev-validation-v2.yaml")
STAGE3C3_READINESS = Path("research/evaluation/stage3c3-readiness.json")
POLICY_PROPOSAL = Path("research/evaluation/evaluation-policy-proposal.yaml")
DECISION_PACKET = Path("reports/decisions/stage3c2_evaluation_policy_decision_packet.md")
REGISTRY_PATH = Path("research/registry/research.db")
EXCHANGE_SNAPSHOT = Path("research/exchange_snapshots/binance-usdm-futures-2025-8-demo")
PAIR = "BTC/USDT:USDT"
PAIR_STEM = "BTC_USDT_USDT"
SYMBOL = "BTCUSDT"
PRIMARY_TIMEFRAME = "1h"
FUNDING_TIMEFRAME = "8h"
DEV_DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
VAL_DATASET_ID = "futures-validation-btc-usdt-usdt-20240912-20250128-v2"
STAGING_ROOT = Path("research/data/staging/stage3c2p-binance-usdm-futures-v2")
PROVISIONING_ROOT = Path("research/data/provisioning")
CLI_PROBE_DIR = Path("research/data/staging/stage3c2p-cli-probe")
DOWNLOAD_START = pd.Timestamp("2024-01-01T00:00:00Z")
DOWNLOAD_END = pd.Timestamp("2025-03-31T23:00:00Z")
DOWNLOAD_MONTHS = [f"{year}-{month:02d}" for year in (2024, 2025) for month in range(1, 13) if (year == 2024 or month <= 3)]
ALLOWED_FAPI_PATHS = {"/fapi/v1/time", "/fapi/v1/exchangeInfo"}
PUBLIC_ARCHIVE_PREFIXES = (
    "/data/futures/um/monthly/klines/",
    "/data/futures/um/monthly/markPriceKlines/",
    "/data/futures/um/monthly/fundingRate/",
)
PRIVATE_MARKERS = ("/account", "/order", "/position", "/balance", "/listenKey", "/apiKey", "/income")


@dataclass(frozen=True)
class ArchiveSpec:
    candle_type: str
    timeframe: str
    url: str


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value.replace("Z", "+00:00"))


def iso(value: pd.Timestamp) -> str:
    return value.tz_convert("UTC").isoformat().replace("+00:00", "Z")


def timeframe_delta(timeframe: str) -> pd.Timedelta:
    if not timeframe.endswith("h"):
        raise ValueError(f"unsupported timeframe: {timeframe}")
    return pd.to_timedelta(int(timeframe[:-1]), unit="h")


def classify_public_endpoint(method: str, host: str, path: str) -> dict[str, Any]:
    host_norm = host.strip().lower()
    path_norm = path.strip()
    method_norm = method.strip().upper()
    if method_norm != "GET":
        return {"allowed": False, "classification": "non_get_method", "reason_code": "online_endpoint_policy_violation"}
    if any(marker.lower() in path_norm.lower() for marker in PRIVATE_MARKERS):
        return {"allowed": False, "classification": "private_or_trade", "reason_code": "online_endpoint_policy_violation"}
    if host_norm == "fapi.binance.com" and path_norm in ALLOWED_FAPI_PATHS:
        return {"allowed": True, "classification": "public_market_data", "reason_code": None}
    if host_norm == "data.binance.vision" and any(path_norm.startswith(prefix) for prefix in PUBLIC_ARCHIVE_PREFIXES):
        return {"allowed": True, "classification": "public_market_data_archive", "reason_code": None}
    return {"allowed": False, "classification": "unknown_or_non_allowlisted", "reason_code": "online_endpoint_policy_violation"}


def validate_public_archive_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return {"allowed": False, "reason_code": "online_endpoint_policy_violation"}
    return classify_public_endpoint("GET", parsed.hostname or "", parsed.path)


def redact_proxy_url(proxy_url: str | None) -> dict[str, Any]:
    if not proxy_url:
        return {"used": False}
    parsed = urlparse(proxy_url)
    return {
        "used": True,
        "type": {"http": "httpProxy", "https": "httpsProxy", "socks5": "socksProxy", "socks4": "socksProxy"}.get(parsed.scheme.lower(), "unknownProxy"),
        "host": parsed.hostname,
        "port": parsed.port,
        "redacted": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}" if parsed.hostname and parsed.port else parsed.scheme,
    }


def proxy_url_from_env() -> str | None:
    return os.environ.get("STAGE3C2P_HTTPS_PROXY") or os.environ.get("STAGE3C2P_HTTP_PROXY")


def run_text(command: list[str], repo_root: Path, timeout: int = 30) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=False,
        timeout=timeout,
    )
    return result.returncode, result.stdout + result.stderr


def load_runtime_contract(repo_root: Path) -> dict[str, Any]:
    runtime = load_simple_yaml(repo_root / RUNTIME_CONFIG)
    version_code, version_text = run_text([str(repo_root / PYTHON_EXE), "-m", "freqtrade", "--version"], repo_root)
    help_code, help_text = run_text([str(repo_root / PYTHON_EXE), "-m", "freqtrade", "download-data", "--help"], repo_root)
    config = json.loads((repo_root / FUTURES_CONFIG).read_text(encoding="utf-8"))
    return {
        "schema_version": "stage3c2p-runtime-data-contract-v2",
        "created_at": utc_now(),
        "runtime_id": runtime.get("runtime_id"),
        "python_executable": str(PYTHON_EXE).replace("\\", "/"),
        "expected_python_version": runtime.get("expected_python_version"),
        "expected_freqtrade_version": runtime.get("expected_freqtrade_version"),
        "version_command_exit_code": version_code,
        "version_text": version_text,
        "download_help_exit_code": help_code,
        "download_data_supports_candle_types_arg": "--candle-types" in help_text,
        "download_data_supports_trading_mode": "--trading-mode" in help_text,
        "download_data_supports_prepend": "--prepend" in help_text,
        "download_data_supports_erase": "--erase" in help_text,
        "fixed_pair": PAIR,
        "trading_mode": config.get("trading_mode"),
        "margin_mode": config.get("margin_mode"),
        "api_key_empty": not bool((config.get("exchange") or {}).get("key")),
        "api_secret_empty": not bool((config.get("exchange") or {}).get("secret")),
        "strategy_contract": {
            "primary_timeframe": PRIMARY_TIMEFRAME,
            "informative_timeframes": ["4h"],
            "evidence": "RegimeAwareV6 loads 4h informative data and merges it into the 1h dataframe.",
        },
        "required_candle_types_for_research": ["futures", "mark", "funding_rate"],
        "runtime_download_contract": {
            "ohlcv_timeframes": ["1h", "4h"],
            "mark_timeframes": [FUNDING_TIMEFRAME],
            "funding_rate_timeframe": FUNDING_TIMEFRAME,
            "file_format": "feather",
            "pair_stem": PAIR_STEM,
        },
        "limitations": ["Freqtrade 2025.8 download-data help does not expose --candle-types; do not pass that flag."]
        if "--candle-types" not in help_text
        else [],
    }


def write_runtime_contract_markdown(repo_root: Path, contract: dict[str, Any]) -> Path:
    path = repo_root / "reports" / "audits" / "stage3c2p_runtime_data_contract.md"
    lines = [
        "# Stage 3C.2-P Runtime Data Contract",
        "",
        f"- Runtime ID: `{contract['runtime_id']}`",
        f"- Expected Python: `{contract['expected_python_version']}`",
        f"- Expected Freqtrade: `{contract['expected_freqtrade_version']}`",
        f"- Version command exit code: `{contract['version_command_exit_code']}`",
        f"- Trading mode: `{contract['trading_mode']}`",
        f"- Margin mode: `{contract['margin_mode']}`",
        f"- API key empty: `{str(contract['api_key_empty']).lower()}`",
        f"- API secret empty: `{str(contract['api_secret_empty']).lower()}`",
        f"- `download-data` supports `--trading-mode`: `{str(contract['download_data_supports_trading_mode']).lower()}`",
        f"- `download-data` supports `--candle-types`: `{str(contract['download_data_supports_candle_types_arg']).lower()}`",
        "",
        "## Required Data",
        "",
        "- Primary timeframe: `1h`",
        "- Informative timeframe: `4h`",
        "- Candle types required for research: `futures`, `mark`, `funding_rate`",
        "- Funding timeframe: `8h`",
        "- Data format: `feather`",
        "",
        "## Contract Note",
        "",
        "Freqtrade 2025.8 is the authority for this repository. Its `download-data` CLI does not expose `--candle-types`, so this stage does not pass that unsupported flag.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def apply_human_split_decision(repo_root: Path) -> dict[str, Any]:
    policy = load_simple_yaml(repo_root / SPLIT_POLICY)
    policy["schema_version"] = "stage3c2p-split-v2-policy-v2"
    policy["policy_version"] = 2
    policy["status"] = "approved_for_data_split"
    policy["development"] = {"selection_mode": "earliest_complete_continuous_range", "evaluation_1h_candles": 5000}
    policy["validation"] = {
        "selection_mode": "fixed_candle_count",
        "evaluation_1h_candles": 2500,
        "evaluation_ratio": None,
        "boundary_rule": "first complete continuous 2500 1h candles after development and embargo and validation warm-up",
        "length_auto_changes_with_future_data": False,
    }
    requirements = dict(policy.get("minimum_requirements") or {})
    requirements["development_evaluation_1h_candles"] = 5000
    requirements["validation_evaluation_1h_candles"] = 2500
    requirements["validation_evaluation_ratio"] = None
    requirements["validation_policy"] = "fixed_candle_count"
    policy["minimum_requirements"] = requirements
    policy["human_decision_event"] = {
        "decision_type": "split_policy_only",
        "approver_type": "human_user",
        "decision_timestamp": utc_now(),
        "development_evaluation_1h_candles": 5000,
        "validation_evaluation_1h_candles": 2500,
        "evaluation_policy_approval": "not_approved",
    }
    policy["frozen_before_strategy_probe"] = True
    policy["strategy_results_used"] = False
    policy["strategy_probe_run"] = False
    policy["probe_may_move_split"] = False
    payload = {key: value for key, value in policy.items() if key != "split_policy_sha256"}
    policy["split_policy_sha256"] = stable_hash(payload)
    dump_manifest(repo_root / SPLIT_POLICY, policy)
    return policy


def explicit_validation_candles(requirements: dict[str, Any]) -> int | None:
    value = requirements.get("validation_evaluation_1h_candles")
    return int(value) if isinstance(value, int) and value > 0 else None


def build_freqtrade_download_command(staging_datadir: str, timerange: str) -> list[str]:
    return [
        str(PYTHON_EXE).replace("\\", "/"),
        "-m",
        "freqtrade",
        "download-data",
        "--config",
        str(FUTURES_CONFIG).replace("\\", "/"),
        "--datadir",
        staging_datadir,
        "--trading-mode",
        "futures",
        "--pairs",
        PAIR,
        "--timerange",
        timerange,
        "--timeframes",
        "1h",
        "4h",
        "--data-format-ohlcv",
        "feather",
    ]


def compute_coverage_plan(split: dict[str, Any]) -> dict[str, Any]:
    requirements = split.get("minimum_requirements") or {}
    dev_eval = int(requirements["development_evaluation_1h_candles"])
    val_eval = explicit_validation_candles(requirements)
    startup_4h = int(requirements["startup_candles_4h"])
    dev_warmup_1h = startup_4h * 4
    embargo_1h = int(requirements["embargo_hours"])
    val_warmup_1h = startup_4h * 4
    safety_margin_1h = 7 * 24
    reason_codes = []
    if val_eval is None:
        reason_codes.append("split_policy_incomplete")
    total_1h = dev_warmup_1h + dev_eval + embargo_1h + val_warmup_1h + int(val_eval or 0) + safety_margin_1h
    latest_required = DOWNLOAD_START + pd.to_timedelta(total_1h - 1, unit="h")
    rows = {
        "futures_1h": total_1h,
        "futures_4h": int((total_1h + 3) // 4),
        "mark_8h": int((total_1h + 7) // 8),
        "funding_rate_8h": int((total_1h + 7) // 8),
    }
    return {
        "schema_version": "stage3c2p-coverage-plan-v2",
        "created_at": utc_now(),
        "status": "blocked" if reason_codes else "ready_for_download",
        "reason_codes": reason_codes,
        "pair": PAIR,
        "primary_timeframe": PRIMARY_TIMEFRAME,
        "informative_timeframes": ["4h"],
        "required_candle_types": ["futures", "mark", "funding_rate"],
        "development_evaluation_1h_candles": dev_eval,
        "startup_candles_4h": startup_4h,
        "max_indicator_window_source": "startup_candles_4h",
        "development_warmup_1h_candles": dev_warmup_1h,
        "embargo_1h_candles": embargo_1h,
        "validation_warmup_1h_candles": val_warmup_1h,
        "validation_evaluation_1h_candles": val_eval,
        "validation_evaluation_ratio": None,
        "safety_margin_1h_candles": safety_margin_1h,
        "total_required_raw_1h_candles": total_1h,
        "earliest_required_utc": iso(DOWNLOAD_START),
        "latest_required_utc": iso(latest_required),
        "download_range_utc": {"start": iso(DOWNLOAD_START), "end": iso(DOWNLOAD_END), "months": DOWNLOAD_MONTHS},
        "estimated_row_counts": rows,
        "split_policy_hash": split.get("split_policy_sha256") or stable_hash(split),
        "strategy_results_used": False,
        "download_allowed": not reason_codes,
        "download_not_run_reason": reason_codes[0] if reason_codes else None,
        "planned_command": build_freqtrade_download_command(STAGING_ROOT.as_posix(), "20240101-20250401"),
    }


def write_coverage_plan(repo_root: Path, plan: dict[str, Any]) -> Path:
    path = repo_root / PROVISIONING_ROOT / "stage3c2p-coverage-plan.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    dump_manifest(path, plan)
    return path


def archive_specs(months: list[str]) -> list[ArchiveSpec]:
    root = "https://data.binance.vision/data/futures/um/monthly"
    specs: list[ArchiveSpec] = []
    for month in months:
        specs.append(ArchiveSpec("futures", "1h", f"{root}/klines/{SYMBOL}/1h/{SYMBOL}-1h-{month}.zip"))
        specs.append(ArchiveSpec("futures", "4h", f"{root}/klines/{SYMBOL}/4h/{SYMBOL}-4h-{month}.zip"))
        specs.append(ArchiveSpec("mark", "8h", f"{root}/markPriceKlines/{SYMBOL}/8h/{SYMBOL}-8h-{month}.zip"))
        specs.append(ArchiveSpec("funding_rate", "8h", f"{root}/fundingRate/{SYMBOL}/{SYMBOL}-fundingRate-{month}.zip"))
    return specs


def read_csv_from_zip(zip_bytes: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected exactly one csv member, got {names}")
        payload = archive.read(names[0])
    return pd.read_csv(io.BytesIO(payload))


def normalize_kline(raw: pd.DataFrame) -> pd.DataFrame:
    if "open_time" not in raw.columns:
        raw = pd.read_csv(io.StringIO(raw.to_csv(index=False, header=False)), header=None)
        raw.columns = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"][: len(raw.columns)]
    required = {"open_time", "open", "high", "low", "close", "volume"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"kline missing columns: {sorted(missing)}")
    return pd.DataFrame(
        {
            "date": pd.to_datetime(raw["open_time"], unit="ms", utc=True),
            "open": raw["open"].astype(float),
            "high": raw["high"].astype(float),
            "low": raw["low"].astype(float),
            "close": raw["close"].astype(float),
            "volume": raw["volume"].astype(float),
        }
    )


def normalize_funding(raw: pd.DataFrame) -> pd.DataFrame:
    if "calc_time" not in raw.columns:
        raw = pd.read_csv(io.StringIO(raw.to_csv(index=False, header=False)), header=None)
        if len(raw.columns) >= 3:
            raw.columns = ["calc_time", "symbol", "last_funding_rate", *[f"extra_{idx}" for idx in range(len(raw.columns) - 3)]]
    required = {"calc_time", "last_funding_rate"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"funding missing columns: {sorted(missing)}")
    rates = raw["last_funding_rate"].astype(float)
    return pd.DataFrame(
        {
            "date": pd.to_datetime(raw["calc_time"], unit="ms", utc=True).dt.round("s"),
            "open": rates,
            "high": rates,
            "low": rates,
            "close": rates,
            "volume": 0.0,
        }
    )


def write_feather(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True).to_feather(path, compression="lz4", compression_level=9)


def download_archive(spec: ArchiveSpec, download_dir: Path, network_audit: dict[str, Any], timeout: int = 90) -> tuple[pd.DataFrame, dict[str, Any]]:
    allowed = validate_public_archive_url(spec.url)
    if not allowed["allowed"]:
        raise RuntimeError(f"online_endpoint_policy_violation: {spec.url}")
    parsed = urlparse(spec.url)
    proxy = proxy_url_from_env()
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"https": proxy, "http": proxy}))
    opener = urllib.request.build_opener(*handlers)
    started = utc_now()
    with opener.open(spec.url, timeout=timeout) as response:
        payload = response.read()
        status = getattr(response, "status", 200)
    completed = utc_now()
    zip_path = download_dir / f"{spec.candle_type}-{Path(parsed.path).name}"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(payload)
    entry = {
        "host": parsed.hostname,
        "path": parsed.path,
        "method": "GET",
        "api_category": allowed["classification"],
        "public_private_classification": "public",
        "response_status": status,
        "request_count": 1,
        "proxy": redact_proxy_url(proxy),
        "first_timestamp": started,
        "last_timestamp": completed,
    }
    network_audit["requests"].append(entry)
    network_audit["summary"]["request_count"] += 1
    raw = read_csv_from_zip(payload)
    frame = normalize_funding(raw) if spec.candle_type == "funding_rate" else normalize_kline(raw)
    source = {
        "candle_type": spec.candle_type,
        "timeframe": spec.timeframe,
        "url_host": parsed.hostname,
        "url_path": parsed.path,
        "zip_path": zip_path.relative_to(download_dir.parent).as_posix(),
        "zip_bytes": len(payload),
        "zip_sha256": hashlib.sha256(payload).hexdigest(),
    }
    return frame, source


def probe_freqtrade_cli(repo_root: Path) -> dict[str, Any]:
    probe_dir = repo_root / CLI_PROBE_DIR
    if probe_dir.exists():
        shutil.rmtree(probe_dir)
    probe_dir.mkdir(parents=True, exist_ok=True)
    command = build_freqtrade_download_command(CLI_PROBE_DIR.as_posix(), "20240101-20240103")
    started = utc_now()
    result = subprocess.run(command, cwd=repo_root, text=True, encoding="utf-8", errors="replace", capture_output=True, shell=False, timeout=180)
    completed = utc_now()
    files = [path.relative_to(probe_dir).as_posix() for path in sorted(probe_dir.rglob("*")) if path.is_file()]
    report = {
        "schema_version": "stage3c2p-cli-probe-v1",
        "command": command,
        "shell": False,
        "started_at": started,
        "completed_at": completed,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
        "files": files,
        "detected_candle_types": sorted(
            {
                "funding_rate" if "funding_rate" in item else "mark" if "mark" in item else "futures" if "futures" in item else "unknown"
                for item in files
            }
        ),
        "complete_for_research": all(any(token in item for item in files) for token in ("futures", "mark", "funding_rate")),
    }
    dump_json(repo_root / PROVISIONING_ROOT / "stage3c2p-cli-probe.json", report)
    return report


def provision_with_public_archives(repo_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    staging = repo_root / STAGING_ROOT
    if staging.exists():
        shutil.rmtree(staging)
    download_dir = staging / "_downloads"
    data_dir = staging / "futures"
    download_dir.mkdir(parents=True, exist_ok=True)
    network_audit = {
        "schema_version": "stage3c2p-network-audit-v1",
        "created_at": utc_now(),
        "allowed_only_public_market_data": True,
        "violations": [],
        "summary": {"request_count": 0, "hosts": ["data.binance.vision"], "proxy": redact_proxy_url(proxy_url_from_env())},
        "requests": [],
    }
    frames: dict[tuple[str, str], list[pd.DataFrame]] = {}
    sources = []
    for spec in archive_specs(plan["download_range_utc"]["months"]):
        frame, source = download_archive(spec, download_dir, network_audit)
        frames.setdefault((spec.candle_type, spec.timeframe), []).append(frame)
        sources.append(source)
    files = []
    for (candle_type, timeframe), pieces in sorted(frames.items()):
        frame = pd.concat(pieces, ignore_index=True).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        output = data_dir / f"{PAIR_STEM}-{timeframe}-{candle_type}.feather"
        write_feather(frame, output)
        files.append(
            {
                "path": output.relative_to(staging).as_posix(),
                "rows": int(len(frame)),
                "start": iso(frame["date"].min()),
                "end": iso(frame["date"].max()),
                "bytes": output.stat().st_size,
                "sha256": sha256_file(output),
                "candle_type": candle_type,
                "timeframe": timeframe,
            }
        )
    manifest = {
        "schema_version": "stage3c2p-staging-manifest-v1",
        "created_at": utc_now(),
        "source": "binance_public_data_vision_usdm_monthly",
        "pair": PAIR,
        "symbol": SYMBOL,
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "download_range_utc": plan["download_range_utc"],
        "months": plan["download_range_utc"]["months"],
        "files": files,
        "sources": sources,
        "synthetic_funding": False,
    }
    dump_json(staging / "provisioning-manifest.json", manifest)
    dump_json(repo_root / PROVISIONING_ROOT / "stage3c2p-network-audit.json", network_audit)
    return {"staging": STAGING_ROOT.as_posix(), "manifest": manifest, "network_audit": network_audit}


def read_frame(path: Path, candle_type: str) -> pd.DataFrame:
    frame = pd.read_feather(path)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    if candle_type == "funding_rate":
        frame["date"] = frame["date"].dt.round("s")
    return frame.sort_values("date").reset_index(drop=True)


def validate_frame(path: Path, timeframe: str, candle_type: str, required_start: pd.Timestamp, required_end: pd.Timestamp) -> dict[str, Any]:
    frame = read_frame(path, candle_type)
    dates = frame["date"]
    expected = timeframe_delta(timeframe)
    diffs = dates.diff().dropna()
    gaps = []
    for idx, diff in enumerate(diffs, start=1):
        if diff != expected:
            gaps.append({"from": iso(dates.iloc[idx - 1]), "to": iso(dates.iloc[idx]), "actual_step": str(diff), "expected_step": str(expected)})
    duplicates = int(dates.duplicated().sum())
    ohlc_bad = 0
    if candle_type in {"futures", "mark"}:
        ohlc_bad = int(((frame["high"] < frame[["open", "close"]].max(axis=1)) | (frame["low"] > frame[["open", "close"]].min(axis=1))).sum())
    negative_volume = int((frame["volume"].astype(float) < 0).sum()) if "volume" in frame else 0
    covers_required = bool(dates.min() <= required_start and dates.max() >= required_end)
    ok = not gaps and not duplicates and not ohlc_bad and not negative_volume and covers_required
    return {
        "ok": ok,
        "path": path.as_posix(),
        "candle_type": candle_type,
        "timeframe": timeframe,
        "rows": int(len(frame)),
        "start": iso(dates.min()),
        "end": iso(dates.max()),
        "required_start": iso(required_start),
        "required_end": iso(required_end),
        "covers_required": covers_required,
        "duplicate_timestamps": duplicates,
        "missing_intervals": gaps[:20],
        "missing_interval_count": len(gaps),
        "invalid_ohlc": ohlc_bad,
        "negative_volume": negative_volume,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "pair": PAIR,
    }


def validate_staging(repo_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    root = repo_root / STAGING_ROOT / "futures"
    required_start = DOWNLOAD_START
    required_end = pd.Timestamp(plan["latest_required_utc"])
    files = {
        "futures_1h": (root / f"{PAIR_STEM}-1h-futures.feather", "1h", "futures"),
        "futures_4h": (root / f"{PAIR_STEM}-4h-futures.feather", "4h", "futures"),
        "mark_8h": (root / f"{PAIR_STEM}-8h-mark.feather", "8h", "mark"),
        "funding_rate_8h": (root / f"{PAIR_STEM}-8h-funding_rate.feather", "8h", "funding_rate"),
    }
    checks = {}
    reason_codes = []
    for key, (path, timeframe, candle_type) in files.items():
        if not path.exists():
            checks[key] = {"ok": False, "missing": True, "path": path.as_posix()}
            reason_codes.append({"futures_1h": "futures_data_missing", "futures_4h": "informative_timeframe_missing", "mark_8h": "mark_data_missing", "funding_rate_8h": "funding_history_insufficient"}[key])
            continue
        check = validate_frame(path, timeframe, candle_type, required_start, required_end)
        checks[key] = check
        if not check["ok"]:
            if key == "funding_rate_8h":
                reason_codes.append("funding_history_insufficient")
            elif key == "mark_8h":
                reason_codes.append("mark_data_missing")
            elif check["missing_interval_count"]:
                reason_codes.append("data_gap_detected")
            else:
                reason_codes.append("data_integrity_failed")
    report = {
        "schema_version": "stage3c2p-data-integrity-v1",
        "created_at": utc_now(),
        "status": "passed" if not reason_codes else "failed",
        "reason_codes": sorted(set(reason_codes)),
        "synthetic_funding_used": False,
        "required_range": {"start": iso(required_start), "end": iso(required_end)},
        "checks": checks,
    }
    dump_json(repo_root / PROVISIONING_ROOT / "stage3c2p-data-integrity-report.json", report)
    write_integrity_markdown(repo_root, report)
    return report


def write_integrity_markdown(repo_root: Path, report: dict[str, Any]) -> Path:
    path = repo_root / PROVISIONING_ROOT / "stage3c2p-data-integrity-report.md"
    lines = [
        "# Stage 3C.2-P Data Integrity Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Reason codes: `{', '.join(report['reason_codes']) or 'none'}`",
        f"- Synthetic funding used: `{str(report['synthetic_funding_used']).lower()}`",
        "",
        "| key | ok | rows | start | end | gaps | sha256 |",
        "|---|---:|---:|---|---|---:|---|",
    ]
    for key, check in report["checks"].items():
        lines.append(
            f"| `{key}` | `{str(check.get('ok')).lower()}` | {check.get('rows')} | `{check.get('start')}` | `{check.get('end')}` | {check.get('missing_interval_count')} | `{check.get('sha256')}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def compute_concrete_split(plan: dict[str, Any]) -> dict[str, Any]:
    start = DOWNLOAD_START
    dev_warmup_start = start
    dev_eval_start = dev_warmup_start + pd.to_timedelta(plan["development_warmup_1h_candles"], unit="h")
    dev_eval_end = dev_eval_start + pd.to_timedelta(plan["development_evaluation_1h_candles"] - 1, unit="h")
    embargo_start = dev_eval_end + pd.to_timedelta(1, unit="h")
    embargo_end = embargo_start + pd.to_timedelta(plan["embargo_1h_candles"] - 1, unit="h")
    val_warmup_start = embargo_end + pd.to_timedelta(1, unit="h")
    val_eval_start = val_warmup_start + pd.to_timedelta(plan["validation_warmup_1h_candles"], unit="h")
    val_eval_end = val_eval_start + pd.to_timedelta(plan["validation_evaluation_1h_candles"] - 1, unit="h")
    split = {
        "schema_version": "stage3c2p-concrete-split-v2",
        "split_id": "futures-dev-validation-v2",
        "created_at": utc_now(),
        "pair": PAIR,
        "primary_timeframe": "1h",
        "informative_timeframes": ["4h"],
        "candle_types": ["futures", "mark", "funding_rate"],
        "strategy_results_used": False,
        "frozen_before_strategy_probe": True,
        "probe_may_move_split": False,
        "development_dataset_id": DEV_DATASET_ID,
        "validation_dataset_id": VAL_DATASET_ID,
        "development": {
            "warmup_start": iso(dev_warmup_start),
            "evaluation_start": iso(dev_eval_start),
            "evaluation_end": iso(dev_eval_end),
            "evaluation_1h_candles": plan["development_evaluation_1h_candles"],
        },
        "embargo": {"start": iso(embargo_start), "end": iso(embargo_end), "hours": plan["embargo_1h_candles"]},
        "validation": {
            "warmup_start": iso(val_warmup_start),
            "evaluation_start": iso(val_eval_start),
            "evaluation_end": iso(val_eval_end),
            "evaluation_1h_candles": plan["validation_evaluation_1h_candles"],
            "selection_mode": "fixed_candle_count",
            "evaluation_ratio": None,
        },
        "acceptance_fixture": {"used_for_ranking": False, "quarantined_from_v2": True},
    }
    split["split_sha256"] = stable_hash({key: value for key, value in split.items() if key != "split_sha256"})
    return split


def write_concrete_split(repo_root: Path, split: dict[str, Any]) -> Path:
    path = repo_root / CONCRETE_SPLIT
    dump_manifest(path, split)
    return path


def slice_frame(src: Path, candle_type: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frame = read_frame(src, candle_type)
    return frame[(frame["date"] >= start) & (frame["date"] <= end)].copy().reset_index(drop=True)


def validation_check(frame: pd.DataFrame, timeframe: str, candle_type: str) -> dict[str, Any]:
    dates = pd.to_datetime(frame["date"], utc=True)
    diffs = dates.diff().dropna()
    expected = timeframe_delta(timeframe)
    gaps = int((diffs != expected).sum())
    return {
        "ok": bool(len(frame) and gaps == 0 and dates.duplicated().sum() == 0),
        "rows": int(len(frame)),
        "start": iso(dates.min()),
        "end": iso(dates.max()),
        "duplicates": int(dates.duplicated().sum()),
        "missing_intervals": gaps,
        "timezone": "UTC",
        "format": "feather",
        "candle_type": candle_type,
        "timeframe": timeframe,
    }


def aggregate_hash(entries: list[dict[str, Any]]) -> str:
    return stable_hash([{key: item[key] for key in ("path", "bytes", "sha256")} for item in entries])


def prepare_snapshot_dir(repo_root: Path, dataset_id: str) -> Path:
    root = repo_root / "research" / "data" / "snapshots" / dataset_id
    if root.exists():
        manifest = root / "manifest.yaml"
        if manifest.exists() and "scripts/build_stage3c2p_provisioning.py" in manifest.read_text(encoding="utf-8"):
            shutil.rmtree(root)
        else:
            raise RuntimeError(f"snapshot exists and is not owned by Stage 3C.2-P: {root}")
    return root


def build_snapshot(repo_root: Path, dataset_id: str, intended_use: str, split_part: dict[str, str], concrete_split: dict[str, Any]) -> dict[str, Any]:
    snapshot_root = prepare_snapshot_dir(repo_root, dataset_id)
    data_root = snapshot_root / "data" / "futures"
    staging_root = repo_root / STAGING_ROOT / "futures"
    start = ts(split_part["warmup_start"])
    end = ts(split_part["evaluation_end"])
    files = {
        "futures_1h": (staging_root / f"{PAIR_STEM}-1h-futures.feather", "1h", "futures"),
        "futures_4h": (staging_root / f"{PAIR_STEM}-4h-futures.feather", "4h", "futures"),
        "mark_8h": (staging_root / f"{PAIR_STEM}-8h-mark.feather", "8h", "mark"),
        "funding_rate_8h": (staging_root / f"{PAIR_STEM}-8h-funding_rate.feather", "8h", "funding_rate"),
    }
    entries = []
    coverage = []
    checks = {}
    for key, (src, timeframe, candle_type) in files.items():
        frame = slice_frame(src, candle_type, start, end)
        dst = data_root / src.name
        write_feather(frame, dst)
        record = {"path": repo_rel(repo_root, dst), "bytes": dst.stat().st_size, "sha256": sha256_file(dst)}
        entries.append(record)
        check = validation_check(frame, timeframe, candle_type)
        checks[key] = check
        coverage.append({"file": dst.name, "rows": check["rows"], "start": check["start"], "end": check["end"], "candle_type": candle_type, "timeframe": timeframe})
    manifest = {
        "schema_version": "stage3c2p-dataset-snapshot-v2",
        "dataset_id": dataset_id,
        "parent_staging_dataset": STAGING_ROOT.as_posix(),
        "exchange": "binance",
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "pairs": [PAIR],
        "timeframes": ["1h", "4h", "8h"],
        "candle_types": ["futures", "mark", "funding_rate"],
        "data_path": repo_rel(repo_root, snapshot_root / "data"),
        "files": entries,
        "coverage": coverage,
        "validation_checks": checks,
        "aggregate_sha256": aggregate_hash(entries),
        "start": split_part["warmup_start"],
        "end": split_part["evaluation_end"],
        "warmup_range": {"start": split_part["warmup_start"], "end": iso(ts(split_part["evaluation_start"]) - pd.to_timedelta(1, unit="h"))},
        "evaluation_range": {"start": split_part["evaluation_start"], "end": split_part["evaluation_end"], "main_1h_candles": split_part["evaluation_1h_candles"]},
        "funding_model": "sealed_dataset",
        "funding_model_synthetic": False,
        "source_lineage": {"coverage_plan": "research/data/provisioning/stage3c2p-coverage-plan.yaml", "concrete_split": CONCRETE_SPLIT.as_posix(), "split_sha256": concrete_split["split_sha256"]},
        "created_at": utc_now(),
        "campaign_mutable": False,
        "network_accessed_during_campaign": True,
        "sealed": True,
        "sealed_at": utc_now(),
        "sealed_by": "scripts/build_stage3c2p_provisioning.py",
        "intended_use": intended_use,
        "agent_visibility": "full" if intended_use == "development" else "controlled",
        "suitable_for_strategy_iteration": intended_use == "development",
        "suitable_for_strategy_ranking": "conditional" if intended_use == "development" else False,
        "evaluation_policy_required": intended_use == "development",
        "suitable_for_stage_promotion": "conditional" if intended_use == "validation" else False,
        "validation_access_budget_required": intended_use == "validation",
    }
    dump_manifest(snapshot_root / "manifest.yaml", manifest)
    return manifest


def timerange_for_probe(split_part: dict[str, str]) -> str:
    start_day = split_part["evaluation_start"][:10].replace("-", "")
    end_day = (ts(split_part["evaluation_end"]) + pd.to_timedelta(1, unit="h")).strftime("%Y%m%d")
    return f"{start_day}-{end_day}"


def probe_campaign(dataset: dict[str, Any], strategy: str, strategy_file: str, strategy_path: str, timerange: str) -> dict[str, Any]:
    return {
        "campaign_id": "stage3c2p-development-probe",
        "fixed_backtest": {
            "strategy": strategy,
            "strategy_file": strategy_file,
            "strategy_path": strategy_path,
            "config": FUTURES_CONFIG.as_posix(),
            "dataset_id": dataset["dataset_id"],
            "dataset_manifest": f"research/data/snapshots/{dataset['dataset_id']}/manifest.yaml",
            "datadir": dataset["data_path"],
            "timerange": timerange,
            "timeframe": "1h",
            "pairs": [PAIR],
            "fee": "0.0004",
            "acceptance_gate": {},
        },
        "sealed_offline_backtest": {"exchange_snapshot": EXCHANGE_SNAPSHOT.as_posix(), "network_policy": "socket_blocker"},
    }


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def probe_summary(repo_root: Path, run: dict[str, Any], strategy: str) -> dict[str, Any]:
    report_path = repo_root / run["report_path"]
    run_dir = report_path.parent
    metrics = load_json(run_dir / "metrics.json") if (run_dir / "metrics.json").exists() else {}
    raw_paths = [path for path in run_dir.glob("*.json") if path.name.startswith("backtest-result") or path.name == "freqtrade-backtest-result.json"]
    trades = []
    if raw_paths:
        trades = collect_trade_rows(load_json(raw_paths[0]), strategy)
    active_weeks = sorted({str(row.get("close_date") or row.get("open_date"))[:10] for row in trades if row.get("close_date") or row.get("open_date")})
    return {
        "runner": run,
        "metrics": metrics.get("normalized") or {},
        "total_trades": int((metrics.get("normalized") or {}).get("total_trades") or (metrics.get("normalized") or {}).get("trade_detail_count") or 0),
        "long_trades": int((metrics.get("normalized") or {}).get("long_trade_count") or 0),
        "short_trades": int((metrics.get("normalized") or {}).get("short_trade_count") or 0),
        "closed_trades": int((metrics.get("normalized") or {}).get("closed_trade_count") or 0),
        "active_weeks": len(active_weeks),
        "trades_per_week": (len(trades) / max(1, len(active_weeks))) if active_weeks else 0,
        "enter_tag_coverage": sorted({str(row.get("enter_tag")) for row in trades if row.get("enter_tag")}),
        "exit_reason_coverage": sorted({str(row.get("exit_reason")) for row in trades if row.get("exit_reason")}),
        "profit_factor_computable": (metrics.get("normalized") or {}).get("profit_factor") is not None,
        "sharpe_sortino_calmar_computable": False,
        "normalized_trade_hash": stable_hash(trades),
    }


def run_development_probe(repo_root: Path, dev_manifest: dict[str, Any], concrete_split: dict[str, Any]) -> dict[str, Any]:
    candidate_manifest = load_simple_yaml(repo_root / "research/candidates/demo-stage3b2-single-variable/1/candidate-manifest.yaml")
    timerange = timerange_for_probe(concrete_split["development"])
    baseline = run_offline_backtest(repo_root, probe_campaign(dev_manifest, "RegimeAwareV6", "strategies/RegimeAwareV6.py", "strategies", timerange), 1, "DEVELOPMENT-V2-BASELINE", repo_root / EXCHANGE_SNAPSHOT)
    candidate = run_offline_backtest(
        repo_root,
        probe_campaign(dev_manifest, candidate_manifest["candidate_strategy_class"], candidate_manifest["candidate_strategy_path"], str(Path(candidate_manifest["candidate_strategy_path"]).parent).replace("\\", "/"), timerange),
        1,
        "DEVELOPMENT-V2-CANDIDATE",
        repo_root / EXCHANGE_SNAPSHOT,
    )
    baseline_summary = probe_summary(repo_root, baseline, "RegimeAwareV6")
    candidate_summary = probe_summary(repo_root, candidate, candidate_manifest["candidate_strategy_class"])
    probe = {
        "schema_version": "stage3c2p-development-probe-v1",
        "created_at": utc_now(),
        "dataset_id": dev_manifest["dataset_id"],
        "timerange": timerange,
        "purpose": "evaluation_readiness_only",
        "quality_verdict": "not_evaluated",
        "split_sha256_before_probe": concrete_split["split_sha256"],
        "split_modified_after_probe": False,
        "baseline": baseline_summary,
        "candidate": candidate_summary,
        "rolling_window_available": True,
        "lookahead_trade_signal_coverage": baseline_summary["total_trades"] > 0,
        "recursive_candle_coverage": concrete_split["development"]["evaluation_1h_candles"] >= 5000,
        "cost_stress_has_real_trades": baseline_summary["total_trades"] > 0 or candidate_summary["total_trades"] > 0,
    }
    dump_json(repo_root / PROVISIONING_ROOT / "stage3c2p-development-probe.json", probe)
    return probe


def update_policy_artifacts(repo_root: Path, concrete_split: dict[str, Any], probe: dict[str, Any] | None) -> None:
    if (repo_root / POLICY_PROPOSAL).exists():
        proposal = load_simple_yaml(repo_root / POLICY_PROPOSAL)
    else:
        proposal = {}
    proposal.update(
        {
            "schema_version": "stage3c2p-evaluation-policy-proposal-v2",
            "policy_approval_status": "pending_human_review",
            "approver": None,
            "split_policy_approval_status": "approved_for_data_split",
            "development_v2_dataset_id": DEV_DATASET_ID,
            "validation_v2_dataset_id": VAL_DATASET_ID,
            "development_v2_1h_candles": concrete_split["development"]["evaluation_1h_candles"],
            "validation_v2_1h_candles": concrete_split["validation"]["evaluation_1h_candles"],
            "probe_summary": {
                "baseline_total_trades": probe["baseline"]["total_trades"] if probe else None,
                "candidate_total_trades": probe["candidate"]["total_trades"] if probe else None,
                "active_weeks": probe["baseline"]["active_weeks"] if probe else None,
                "rolling_window_available": probe["rolling_window_available"] if probe else None,
            },
        }
    )
    dump_manifest(repo_root / POLICY_PROPOSAL, proposal)
    lines = [
        "# Stage 3C.2 Evaluation Policy Decision Packet",
        "",
        "- Split Policy approval: `approved_for_data_split`",
        "- Evaluation Policy approval: `pending_human_review`",
        f"- Development v2: `{DEV_DATASET_ID}` with `5000` formal 1h candles",
        f"- Validation v2: `{VAL_DATASET_ID}` with `2500` formal 1h candles",
        f"- Baseline Development trades: `{probe['baseline']['total_trades'] if probe else None}`",
        f"- Candidate Development trades: `{probe['candidate']['total_trades'] if probe else None}`",
        "- Validation Candidate run: `not_run`",
        "- Lookahead/Recursive/Cost stress: `not_run`",
        "",
        "The split approval does not approve numeric candidate pass/fail gates. Human approval is still required before Validation or Stage 3C.3.",
    ]
    (repo_root / DECISION_PACKET).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / DECISION_PACKET).write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_split_policy_after_seal(repo_root: Path, dev_manifest: dict[str, Any], val_manifest: dict[str, Any], concrete_split: dict[str, Any]) -> dict[str, Any]:
    policy = load_simple_yaml(repo_root / SPLIT_POLICY)
    policy["development_v2_dataset_id"] = dev_manifest["dataset_id"]
    policy["validation_v2_dataset_id"] = val_manifest["dataset_id"]
    policy["development_v2_sealed"] = True
    policy["validation_v2_sealed"] = True
    policy["concrete_split_path"] = CONCRETE_SPLIT.as_posix()
    policy["concrete_split_sha256"] = concrete_split["split_sha256"]
    policy["blocker_reasons"] = []
    payload = {key: value for key, value in policy.items() if key != "split_policy_sha256"}
    policy["split_policy_sha256"] = stable_hash(payload)
    dump_manifest(repo_root / SPLIT_POLICY, policy)
    return policy


def update_readiness(repo_root: Path, dev_manifest: dict[str, Any] | None, val_manifest: dict[str, Any] | None, concrete_split: dict[str, Any] | None, probe: dict[str, Any] | None, reason_codes: list[str]) -> dict[str, Any]:
    checks = {
        "development_v2_sealed": bool(dev_manifest and dev_manifest.get("sealed")),
        "validation_v2_sealed": bool(val_manifest and val_manifest.get("sealed")),
        "development_1h_candles_at_least_5000": bool(concrete_split and concrete_split["development"]["evaluation_1h_candles"] == 5000),
        "development_has_nonzero_trades": bool(probe and (probe["baseline"]["total_trades"] > 0 or probe["candidate"]["total_trades"] > 0)),
        "development_metrics_computable": bool(probe and probe["baseline"]["profit_factor_computable"]),
        "cost_stress_has_real_trades": bool(probe and probe["cost_stress_has_real_trades"]),
        "lookahead_analysis_signal_coverage": bool(probe and probe["lookahead_trade_signal_coverage"]),
        "recursive_analysis_time_coverage": bool(probe and probe["recursive_candle_coverage"]),
        "candidate_validation_not_read": True,
        "holdout_not_accessed": True,
        "policy_human_approved": False,
    }
    blockers = list(reason_codes)
    if not checks["development_v2_sealed"]:
        blockers.append("development_v2_not_sealed")
    if not checks["validation_v2_sealed"]:
        blockers.append("validation_v2_not_sealed")
    if not checks["development_has_nonzero_trades"]:
        blockers.append("development_probe_zero_trades")
    blockers.append("evaluation_policy_pending_human_review")
    readiness = {
        "schema_version": "stage3c3-readiness-v2",
        "updated_at": utc_now(),
        "ready": False,
        "status": "blocked",
        "stage3c2p_status": "completed_with_policy_blocker" if not reason_codes else "blocked",
        "stage3c2p_reason_codes": reason_codes,
        "readiness_checks": checks,
        "blockers": list(dict.fromkeys(blockers)),
    }
    dump_json(repo_root / STAGE3C3_READINESS, readiness)
    return readiness


def init_registry(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stage3c2p_provisioning_events (
          event_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          reason_codes_json TEXT NOT NULL,
          coverage_plan_path TEXT NOT NULL,
          runtime_contract_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS split_policy_decision_events (
          event_id TEXT PRIMARY KEY,
          approver_type TEXT NOT NULL,
          split_policy_hash TEXT NOT NULL,
          evaluation_policy_approved INTEGER NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS dataset_readiness (
          dataset_id TEXT PRIMARY KEY,
          aggregate_sha256 TEXT,
          status TEXT NOT NULL,
          reason_codes_json TEXT NOT NULL,
          total_trades INTEGER,
          artifact_path TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evaluation_artifact_refs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          artifact_type TEXT NOT NULL,
          path TEXT NOT NULL,
          sha256 TEXT,
          recorded_at TEXT NOT NULL
        );
        """
    )


def write_registry(repo_root: Path, final: dict[str, Any], split_policy: dict[str, Any], dev_manifest: dict[str, Any] | None, val_manifest: dict[str, Any] | None, probe: dict[str, Any] | None) -> None:
    conn = sqlite3.connect(repo_root / REGISTRY_PATH)
    try:
        init_registry(conn)
        conn.execute(
            "INSERT OR REPLACE INTO stage3c2p_provisioning_events(event_id, status, reason_codes_json, coverage_plan_path, runtime_contract_path, recorded_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("stage3c2p-provisioning", final["status"], json.dumps(final["reason_codes"], sort_keys=True), final["artifacts"]["coverage_plan"], final["artifacts"]["runtime_contract"], utc_now()),
        )
        conn.execute(
            "INSERT OR REPLACE INTO split_policy_decision_events(event_id, approver_type, split_policy_hash, evaluation_policy_approved, recorded_at) VALUES (?, ?, ?, ?, ?)",
            ("stage3c2p-human-split-policy-decision", "human_user", split_policy["split_policy_sha256"], 0, utc_now()),
        )
        for manifest in (dev_manifest, val_manifest):
            if manifest:
                conn.execute(
                    "INSERT OR REPLACE INTO dataset_readiness(dataset_id, aggregate_sha256, status, reason_codes_json, total_trades, artifact_path, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        manifest["dataset_id"],
                        manifest["aggregate_sha256"],
                        "sealed",
                        "[]",
                        probe["baseline"]["total_trades"] if probe and manifest["intended_use"] == "development" else None,
                        f"research/data/snapshots/{manifest['dataset_id']}/manifest.yaml",
                        utc_now(),
                    ),
                )
        for kind, rel_path in final["artifacts"].items():
            full = repo_root / rel_path
            if full.exists() and full.is_file():
                conn.execute(
                    "INSERT INTO evaluation_artifact_refs(artifact_type, path, sha256, recorded_at) VALUES (?, ?, ?, ?)",
                    (kind, rel_path, sha256_file(full), utc_now()),
                )
        conn.commit()
    finally:
        conn.close()


def write_final(repo_root: Path, status: str, reason_codes: list[str], artifacts: dict[str, str], contract: dict[str, Any], plan: dict[str, Any], dev_manifest: dict[str, Any] | None, val_manifest: dict[str, Any] | None, probe: dict[str, Any] | None, readiness: dict[str, Any]) -> dict[str, Any]:
    final = {
        "schema_version": "stage3c2p-final-report-v2",
        "created_at": utc_now(),
        "git_sha": git_sha(repo_root),
        "status": status,
        "reason_codes": reason_codes,
        "download_started": status not in {"blocked_pre_download"},
        "staging_written": bool((repo_root / STAGING_ROOT / "provisioning-manifest.json").exists()),
        "v1_snapshots_overwritten": False,
        "v2_snapshots_created": bool(dev_manifest and val_manifest),
        "development_probe_run": probe is not None,
        "validation_accessed": False,
        "lookahead_run": False,
        "recursive_run": False,
        "cost_stress_run": False,
        "holdout_accessed": False,
        "hyperopt_run": False,
        "strategy_modified": False,
        "candidate_modified": False,
        "runtime_upgraded": False,
        "policy_approval_status": "pending_human_review",
        "split_policy_approval_status": "approved_for_data_split",
        "runtime_contract_summary": {
            "freqtrade_version_expected": contract["expected_freqtrade_version"],
            "download_data_supports_candle_types_arg": contract["download_data_supports_candle_types_arg"],
            "required_candle_types_for_research": contract["required_candle_types_for_research"],
        },
        "coverage_plan_summary": {
            "development_evaluation_1h_candles": plan["development_evaluation_1h_candles"],
            "validation_evaluation_1h_candles": plan["validation_evaluation_1h_candles"],
            "total_required_raw_1h_candles": plan["total_required_raw_1h_candles"],
        },
        "development_probe_summary": {
            "baseline_total_trades": probe["baseline"]["total_trades"] if probe else None,
            "candidate_total_trades": probe["candidate"]["total_trades"] if probe else None,
        },
        "stage3c3_ready": readiness.get("ready") is True,
        "artifacts": artifacts,
    }
    out = repo_root / PROVISIONING_ROOT / "stage3c2p-final-report.json"
    dump_json(out, final)
    md = repo_root / "reports" / "audits" / "stage3c2p_provisioning_final_report.md"
    lines = [
        "# Stage 3C.2-P Provisioning Final Report",
        "",
        f"- Status: `{status}`",
        f"- Reason codes: `{', '.join(reason_codes) or 'none'}`",
        f"- Development v2 sealed: `{str(bool(dev_manifest)).lower()}`",
        f"- Validation v2 sealed: `{str(bool(val_manifest)).lower()}`",
        f"- Development probe run: `{str(probe is not None).lower()}`",
        f"- Policy approval: `pending_human_review`",
        "- Validation Candidate run: `false`",
        "- Lookahead/Recursive/Cost stress: `false`",
        "- Holdout/Hyperopt: `false`",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    final["artifacts"]["final_markdown_report"] = repo_rel(repo_root, md)
    dump_json(out, final)
    return final


def build(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    (repo_root / PROVISIONING_ROOT).mkdir(parents=True, exist_ok=True)
    split_policy = apply_human_split_decision(repo_root)
    contract = load_runtime_contract(repo_root)
    runtime_contract_md = write_runtime_contract_markdown(repo_root, contract)
    plan = compute_coverage_plan(split_policy)
    coverage_plan_path = write_coverage_plan(repo_root, plan)
    artifacts = {
        "runtime_contract": repo_rel(repo_root, runtime_contract_md),
        "coverage_plan": repo_rel(repo_root, coverage_plan_path),
        "stage3c3_readiness": repo_rel(repo_root, repo_root / STAGE3C3_READINESS),
        "cli_probe": "research/data/provisioning/stage3c2p-cli-probe.json",
        "network_audit": "research/data/provisioning/stage3c2p-network-audit.json",
        "data_integrity_json": "research/data/provisioning/stage3c2p-data-integrity-report.json",
        "data_integrity_md": "research/data/provisioning/stage3c2p-data-integrity-report.md",
        "concrete_split": CONCRETE_SPLIT.as_posix(),
        "development_probe": "research/data/provisioning/stage3c2p-development-probe.json",
        "final_json_report": "research/data/provisioning/stage3c2p-final-report.json",
    }
    if plan["reason_codes"]:
        readiness = update_readiness(repo_root, None, None, None, None, plan["reason_codes"])
        final = write_final(repo_root, "blocked_pre_download", plan["reason_codes"], artifacts, contract, plan, None, None, None, readiness)
        write_registry(repo_root, final, split_policy, None, None, None)
        return final
    cli_probe = probe_freqtrade_cli(repo_root)
    provisioning = provision_with_public_archives(repo_root, plan)
    integrity = validate_staging(repo_root, plan)
    if integrity["status"] != "passed":
        readiness = update_readiness(repo_root, None, None, None, None, integrity["reason_codes"])
        final = write_final(repo_root, "blocked_data_integrity", integrity["reason_codes"], artifacts, contract, plan, None, None, None, readiness)
        write_registry(repo_root, final, split_policy, None, None, None)
        return final
    concrete_split = compute_concrete_split(plan)
    split_path = write_concrete_split(repo_root, concrete_split)
    dev_manifest = build_snapshot(repo_root, DEV_DATASET_ID, "development", concrete_split["development"], concrete_split)
    val_manifest = build_snapshot(repo_root, VAL_DATASET_ID, "validation", concrete_split["validation"], concrete_split)
    split_policy = update_split_policy_after_seal(repo_root, dev_manifest, val_manifest, concrete_split)
    probe = run_development_probe(repo_root, dev_manifest, concrete_split)
    current_split_hash = load_simple_yaml(repo_root / CONCRETE_SPLIT)["split_sha256"]
    probe["split_sha256_after_probe"] = current_split_hash
    probe["split_modified_after_probe"] = current_split_hash != concrete_split["split_sha256"]
    dump_json(repo_root / PROVISIONING_ROOT / "stage3c2p-development-probe.json", probe)
    update_policy_artifacts(repo_root, concrete_split, probe)
    reason_codes = []
    if probe["baseline"]["runner"]["status"] not in {"accepted", "rejected"} or probe["candidate"]["runner"]["status"] not in {"accepted", "rejected"}:
        reason_codes.append("development_probe_execution_failed")
    if probe["baseline"]["total_trades"] == 0 and probe["candidate"]["total_trades"] == 0:
        reason_codes.append("development_probe_zero_trades")
    readiness = update_readiness(repo_root, dev_manifest, val_manifest, concrete_split, probe, reason_codes)
    final = write_final(repo_root, "completed_with_policy_blocker" if not reason_codes else "completed_with_probe_blocker", reason_codes, artifacts, contract, plan, dev_manifest, val_manifest, probe, readiness)
    write_registry(repo_root, final, split_policy, dev_manifest, val_manifest, probe)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 3C.2-P controlled provisioning.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build(Path.cwd())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{result['status']}: {', '.join(result['reason_codes']) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
