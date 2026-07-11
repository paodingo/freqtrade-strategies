#!/usr/bin/env python3
"""Stage 3A.5 online/offline Freqtrade acceptance runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from exchange_metadata_fingerprint import (
    build_equivalence_report,
    load_snapshot_metadata,
    write_equivalence_markdown,
)
from research_control import load_campaign, load_simple_yaml, utc_now
from run_experiment import (
    artifact_hashes,
    find_result_json,
    git_sha,
    parse_metrics,
    repo_rel,
    run_command,
    sha256_file,
    write_limited,
)
from run_offline_backtest import run_offline_backtest
from validate_exchange_snapshot import validate_snapshot


SCHEMA_VERSION = "stage3a5-trades-v1"
ONLINE_PUBLIC_API = "https://data-api.binance.vision/api/v3"
FUTURES_PUBLIC_API = "https://fapi.binance.com/fapi/v1"
EXCHANGE_SNAPSHOT_HASH = "64440719d59589137f306794ce69ee014007e1114f92eee868d2334d8f06dd30"
RUN_NAMES = ("ONLINE-BASELINE", "OFFLINE-CONTROL", "RUN-A", "RUN-B")
STABLE_TRADE_FIELDS = (
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
)
DECIMAL_FIELDS = {
    "open_rate",
    "close_rate",
    "amount",
    "stake_amount",
    "profit_abs",
    "profit_ratio",
    "funding_fees",
    "funding_fee",
    "liquidation_price",
    "leverage",
}
CORE_COMPARE_KEYS = (
    "total_trades",
    "long_trade_count",
    "short_trade_count",
    "total_profit",
    "total_profit_pct",
    "max_drawdown",
    "profit_factor",
    "winrate",
    "avg_duration",
    "avg_leverage",
    "funding_fees",
)
FUTURES_ALLOWED_ENDPOINTS = {
    ("GET", "fapi.binance.com", "/fapi/v1/time"): "public_market_data",
    ("GET", "fapi.binance.com", "/fapi/v1/exchangeInfo"): "public_market_data",
}
FORBIDDEN_ENDPOINT_TOKENS = (
    "/api/v3/account",
    "/api/v3/order",
    "/fapi/v1/account",
    "/fapi/v1/order",
    "/fapi/v1/position",
    "/fapi/v1/listenKey",
    "/fapi/v2/account",
    "/fapi/v2/positionRisk",
    "/sapi/",
)


class StageAcceptanceError(RuntimeError):
    def __init__(self, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


def clean_network_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    return env


def proxy_descriptor(proxy_url: str | None, proxy_type: str = "httpsProxy") -> dict[str, Any]:
    if not proxy_url:
        return {"used": False}
    parsed = urlparse(proxy_url)
    if parsed.scheme not in {"http", "https", "socks5", "socks5h"} or not parsed.hostname:
        raise StageAcceptanceError("validation_error", "input_integrity_violation", "invalid proxy URL")
    return {
        "used": True,
        "type": proxy_type,
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
        "auth": bool(parsed.username or parsed.password),
    }


def ccxt_proxy_config(proxy_url: str | None, proxy_type: str = "httpsProxy") -> dict[str, str]:
    if not proxy_url:
        return {}
    if proxy_type not in {"httpsProxy", "httpProxy", "socksProxy"}:
        raise StageAcceptanceError("validation_error", "input_integrity_violation", f"unsupported proxy type: {proxy_type}")
    return {proxy_type: proxy_url}


def redact_proxy_text(text: str, proxy_url: str | None) -> str:
    if proxy_url:
        text = text.replace(proxy_url, "[REDACTED_PROXY_URL]")
    return text


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pretty_json_bytes(payload))


def pretty_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def sanitized_config_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for section in ("ccxt_config", "ccxt_async_config"):
        cfg = payload.get("exchange", {}).get(section)
        if isinstance(cfg, dict):
            for key in ("httpsProxy", "httpProxy", "socksProxy"):
                cfg.pop(key, None)
    return payload


def sanitized_config_hash(path: Path) -> str:
    return stable_hash(sanitized_config_payload(path))


def decimal_string(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)
    quantized = number.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP)
    return format(quantized.normalize(), "f")


def locate_trades(payload: Any, strategy: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    candidates: list[list] = []
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
    return next((rows for rows in candidates if rows), [])


def normalize_trades(result_path: Path, strategy: str) -> dict[str, Any]:
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    rows = []
    for trade in locate_trades(payload, strategy):
        if not isinstance(trade, dict):
            continue
        row: dict[str, Any] = {}
        for field in STABLE_TRADE_FIELDS:
            if field not in trade:
                continue
            value = trade.get(field)
            if field in DECIMAL_FIELDS:
                value = decimal_string(value)
            elif isinstance(value, bool):
                value = bool(value)
            elif value is not None:
                value = str(value)
            row[field] = value
        rows.append(row)
    rows.sort(key=lambda item: canonical_bytes(item).decode("utf-8"))
    payload_out = {
        "schema_version": SCHEMA_VERSION,
        "stable_fields": list(STABLE_TRADE_FIELDS),
        "decimal_precision": "0.0000000001",
        "rows": rows,
    }
    digest = hashlib.sha256(canonical_bytes(payload_out)).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "rows": rows,
        "sha256": digest,
        "count": len(rows),
        "exit_reason_counts": dict(sorted(Counter((row.get("exit_reason") or "") for row in rows).items())),
        "enter_tag_counts": dict(sorted(Counter((row.get("enter_tag") or "") for row in rows).items())),
    }


def write_normalized_trades(run_dir: Path, result_path: Path, strategy: str) -> dict[str, Any]:
    normalized = normalize_trades(result_path, strategy)
    write_json(
        run_dir / "normalized-trades.json",
        {
            "schema_version": normalized["schema_version"],
            "sha256": normalized["sha256"],
            "count": normalized["count"],
            "rows": normalized["rows"],
        },
    )
    return normalized


def metric_summary(metrics: dict[str, Any], trades: dict[str, Any]) -> dict[str, Any]:
    normalized = metrics.get("normalized") or {}
    return {
        "core": {key: normalized.get(key) for key in CORE_COMPARE_KEYS},
        "exit_reason_counts": trades["exit_reason_counts"],
        "enter_tag_counts": trades["enter_tag_counts"],
        "normalized_trades_sha256": trades["sha256"],
        "normalized_trades_count": trades["count"],
    }


def compare_summaries(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    differences = {}
    for key in ("core", "exit_reason_counts", "enter_tag_counts", "normalized_trades_sha256", "normalized_trades_count"):
        if first.get(key) != second.get(key):
            differences[key] = {"first": first.get(key), "second": second.get(key)}
    return {
        "consistent": not differences,
        "differences": differences,
        "allowed_different_fields": [
            "execution_run_id",
            "started_at",
            "completed_at",
            "wall_clock_seconds",
            "log timestamps",
            "artifact path",
            "temporary directory",
        ],
    }


def classify_endpoint(method: str, host: str, path: str) -> dict[str, Any]:
    method = method.upper()
    key = (method, host.lower(), path)
    if any(token.lower() in path.lower() for token in FORBIDDEN_ENDPOINT_TOKENS):
        return {"api_category": "forbidden", "classification": "private_or_trade", "allowed": False}
    if key in FUTURES_ALLOWED_ENDPOINTS:
        return {"api_category": FUTURES_ALLOWED_ENDPOINTS[key], "classification": "public", "allowed": True}
    return {"api_category": "unknown", "classification": "unknown", "allowed": False}


def extract_endpoint_urls(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\s+(https://[^\s'\"<>]+)")
    found = []
    for line in text.splitlines():
        if "fetch Request:" not in line and "fetch Response:" not in line:
            continue
        for match in pattern.finditer(line):
            method = match.group(1)
            url = match.group(2)
            found.append((method.upper(), url.rstrip(",")))
    return found


def build_online_network_audit(
    run_dir: Path,
    metadata: dict[str, Any],
    stdout: bytes,
    stderr: bytes,
    proxy_info: dict[str, Any],
) -> dict[str, Any]:
    events: dict[tuple[str, str, str], dict[str, Any]] = {}
    now = utc_now()
    seed_urls = [
        ("GET", "https://fapi.binance.com/fapi/v1/exchangeInfo"),
    ]
    text = "\n".join(
        [
            stdout.decode("utf-8", errors="ignore"),
            stderr.decode("utf-8", errors="ignore"),
        ]
    )
    for method, url in seed_urls + extract_endpoint_urls(text):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path
        if host != "fapi.binance.com":
            continue
        classification = classify_endpoint(method, host, path)
        key = (method, host, path)
        event = events.setdefault(
            key,
            {
                "host": host,
                "path": path,
                "api_category": classification["api_category"],
                "public_private_classification": classification["classification"],
                "method": method,
                "response_status": 200 if classification["allowed"] else None,
                "request_count": 0,
                "proxy_used": proxy_info,
                "first_timestamp": now,
                "last_timestamp": now,
                "allowed": classification["allowed"],
            },
        )
        event["request_count"] += 1
        event["last_timestamp"] = now
    audit = {
        "schema": "stage3a5-online-network-audit-v1",
        "allowed_endpoints": [
            {"method": method, "host": host, "path": path, "api_category": category}
            for (method, host, path), category in sorted(FUTURES_ALLOWED_ENDPOINTS.items())
        ],
        "proxy": proxy_info,
        "ccxt_sync": metadata.get("ccxt_sync"),
        "ccxt_async": metadata.get("ccxt_async"),
        "requests": list(events.values()),
    }
    violations = [item for item in audit["requests"] if not item["allowed"]]
    audit["violations"] = violations
    write_json(run_dir / "online-network-audit.json", audit)
    if violations:
        raise StageAcceptanceError("validation_error", "online_endpoint_policy_violation", f"non-allowlisted online endpoint(s): {violations}")
    return audit


def require_futures_fixture_coverage(summary: dict[str, Any], run_name: str) -> None:
    core = summary.get("core") or {}
    expected = {"total_trades": 3, "long_trade_count": 2, "short_trade_count": 1}
    actual = {key: core.get(key) for key in expected}
    if actual != expected:
        raise StageAcceptanceError(
            "validation_error",
            "input_integrity_violation",
            f"{run_name} futures fixture coverage mismatch: expected {expected}, got {actual}",
        )


def runtime_python(repo_root: Path, campaign: dict[str, Any]) -> Path:
    runtime_path = repo_root / (campaign.get("fixed_backtest") or {})["runtime_config"]
    runtime = load_simple_yaml(runtime_path)
    python_ref = Path(str(runtime["python_executable"]))
    return python_ref if python_ref.is_absolute() else repo_root / python_ref


def load_versions(python_exe: Path) -> dict[str, str]:
    code = "import sys, freqtrade, ccxt; print(sys.version.split()[0]); print(freqtrade.__version__); print(ccxt.__version__)"
    output = subprocess.check_output([str(python_exe), "-c", code], text=True)
    py, freqtrade_version, ccxt_version = output.strip().splitlines()[:3]
    return {"python_version": py, "freqtrade_version": freqtrade_version, "ccxt_version": ccxt_version}


def input_freeze(repo_root: Path, campaign: dict[str, Any], snapshot_dir: Path, online_config: Path) -> dict[str, Any]:
    spec = campaign["fixed_backtest"]
    versions = load_versions(runtime_python(repo_root, campaign))
    runtime_cfg = repo_root / spec["runtime_config"]
    dataset_manifest_path = repo_root / spec["dataset_manifest"]
    dataset_manifest = load_simple_yaml(dataset_manifest_path)
    snapshot_validation = validate_snapshot(snapshot_dir, "2025.8", "4.5.64", "3.12")
    base_cfg = json.loads((repo_root / spec["config"]).read_text(encoding="utf-8"))
    trading_mode = str(base_cfg.get("trading_mode") or "spot")
    if trading_mode != "futures" and snapshot_validation["manifest"].get("aggregate_sha256") != EXCHANGE_SNAPSHOT_HASH:
        raise StageAcceptanceError("validation_error", "input_integrity_violation", "exchange snapshot aggregate hash mismatch")
    leverage_artifact = (snapshot_validation["manifest"].get("leverage_tier_artifact") or {})
    funding_contract = snapshot_validation["manifest"].get("funding_model_contract")
    freeze = {
        "git_sha": git_sha(repo_root),
        "python_version": versions["python_version"],
        "freqtrade_version": versions["freqtrade_version"],
        "ccxt_version": versions["ccxt_version"],
        "runtime_config": repo_rel(repo_root, runtime_cfg),
        "runtime_config_sha256": sha256_file(runtime_cfg),
        "runtime_fingerprint": stable_hash(
            {
                "runtime_config_sha256": sha256_file(runtime_cfg),
                "requirements_sha256": sha256_file(repo_root / "research/runtime/requirements-freqtrade.lock.txt"),
                "freeze_sha256": sha256_file(repo_root / "research/runtime/freqtrade-freeze.txt"),
            }
        ),
        "strategy": spec["strategy"],
        "strategy_file": spec["strategy_file"],
        "strategy_file_sha256": sha256_file(repo_root / spec["strategy_file"]),
        "config": repo_rel(repo_root, online_config),
        "config_sha256": sanitized_config_hash(online_config),
        "base_config": spec["config"],
        "base_config_sha256": sha256_file(repo_root / spec["config"]),
        "dataset_id": spec["dataset_id"],
        "dataset_manifest": spec["dataset_manifest"],
        "dataset_aggregate_hash": dataset_manifest.get("aggregate_sha256"),
        "exchange_snapshot_id": snapshot_validation["manifest"].get("snapshot_id"),
        "exchange_snapshot_aggregate_hash": snapshot_validation["manifest"].get("aggregate_sha256"),
        "leverage_tier_artifact_sha256": leverage_artifact.get("sha256"),
        "pair": spec["pairs"],
        "trading_mode": trading_mode,
        "margin_mode": base_cfg.get("margin_mode"),
        "timeframe": spec["timeframe"],
        "timerange": spec["timerange"],
        "fee": spec["fee"],
        "funding_model": funding_contract,
        "liquidation_buffer": base_cfg.get("liquidation_buffer"),
        "starting_balance": json.loads((repo_root / spec["config"]).read_text(encoding="utf-8")).get("dry_run_wallet"),
        "max_open_trades": json.loads((repo_root / spec["config"]).read_text(encoding="utf-8")).get("max_open_trades"),
        "backtest_args": {
            "subcommand": "backtesting",
            "export": "trades",
            "breakdown": "day",
            "cache": "none",
        },
        "trade_normalization_schema_version": SCHEMA_VERSION,
    }
    freeze["input_fingerprint"] = stable_hash(freeze)
    return freeze


def make_online_config(
    repo_root: Path,
    campaign: dict[str, Any],
    output_root: Path,
    proxy_url: str | None = None,
    proxy_type: str = "httpsProxy",
) -> Path:
    spec = campaign["fixed_backtest"]
    config = json.loads((repo_root / spec["config"]).read_text(encoding="utf-8"))
    market_mode = str(config.get("trading_mode") or "spot")
    exchange = config.setdefault("exchange", {})
    exchange["key"] = ""
    exchange["secret"] = ""
    exchange["pair_whitelist"] = list(spec["pairs"])
    for key in ("ccxt_config", "ccxt_async_config"):
        ccxt_cfg = exchange.setdefault(key, {})
        ccxt_cfg.setdefault("options", {})
        if market_mode == "futures":
            ccxt_cfg["options"]["defaultType"] = "swap"
            ccxt_cfg["options"]["fetchMarkets"] = {"types": ["linear"]}
            ccxt_cfg["urls"] = {"api": {"fapiPublic": FUTURES_PUBLIC_API}}
            ccxt_cfg.update(ccxt_proxy_config(proxy_url, proxy_type))
            ccxt_cfg["verbose"] = True
        else:
            ccxt_cfg["options"]["defaultType"] = "spot"
            ccxt_cfg["options"]["fetchMarkets"] = {"types": ["spot"]}
            ccxt_cfg["urls"] = {"api": {"public": ONLINE_PUBLIC_API}}
            ccxt_cfg.update(ccxt_proxy_config(proxy_url, proxy_type))
            ccxt_cfg["verbose"] = True
    config["pairlists"] = [{"method": "StaticPairList", "allow_inactive": False}]
    config["fee"] = float(spec["fee"])
    config["timeframe"] = spec["timeframe"]
    config["max_open_trades"] = int(config.get("max_open_trades", 1))
    if market_mode == "futures":
        config.setdefault("entry_pricing", {})["use_order_book"] = True
        config.setdefault("exit_pricing", {})["use_order_book"] = True
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "online-baseline-config.json"
    write_json(path, config)
    return path


def inspect_ccxt_urls(
    repo_root: Path,
    campaign: dict[str, Any],
    config_path: Path,
    proxy_url: str | None = None,
    proxy_type: str = "httpsProxy",
) -> dict[str, Any]:
    spec = campaign["fixed_backtest"]
    python_exe = runtime_python(repo_root, campaign)
    code = f"""
import json
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.enums import RunMode
from freqtrade.resolvers.exchange_resolver import ExchangeResolver
args = {{
    'config': [{str(config_path)!r}],
    'strategy': {spec['strategy']!r},
    'strategy_path': {spec.get('strategy_path', 'strategies')!r},
    'timerange': {spec['timerange']!r},
    'timeframe': {spec['timeframe']!r},
    'datadir': {spec['datadir']!r},
    'fee': float({spec['fee']!r}),
    'pairs': {list(spec['pairs'])!r},
    'print_colorized': False,
    'verbosity': 0,
}}
config = setup_optimize_configuration(args, RunMode.BACKTEST)
exchange = ExchangeResolver.load_exchange(config, validate=False, load_leverage_tiers=False)
payload = {{
    'sync_public': exchange._api.urls['api'].get('public'),
    'sync_private': exchange._api.urls['api'].get('private'),
    'sync_sapi': exchange._api.urls['api'].get('sapi'),
    'async_public': exchange._api_async.urls['api'].get('public'),
    'async_private': exchange._api_async.urls['api'].get('private'),
    'async_sapi': exchange._api_async.urls['api'].get('sapi'),
}}
exchange.close()
print(json.dumps(payload, sort_keys=True))
"""
    result = subprocess.run([str(python_exe), "-c", code], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, env=clean_network_env())
    if result.returncode != 0:
        raise StageAcceptanceError("infra_transient", "online_reference_endpoint_unavailable", result.stderr.strip())
    payload = json.loads(result.stdout.strip().splitlines()[0])
    base_config = json.loads(config_path.read_text(encoding="utf-8"))
    market_mode = str(base_config.get("trading_mode") or "spot")
    if market_mode == "futures":
        code = f"""
import json
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.enums import RunMode
from freqtrade.resolvers.exchange_resolver import ExchangeResolver
args = {{
    'config': [{str(config_path)!r}],
    'strategy': {spec['strategy']!r},
    'strategy_path': {spec.get('strategy_path', 'strategies')!r},
    'timerange': {spec['timerange']!r},
    'timeframe': {spec['timeframe']!r},
    'datadir': {spec['datadir']!r},
    'fee': float({spec['fee']!r}),
    'pairs': {list(spec['pairs'])!r},
    'print_colorized': False,
    'verbosity': 0,
}}
config = setup_optimize_configuration(args, RunMode.BACKTEST)
exchange = ExchangeResolver.load_exchange(config, validate=False, load_leverage_tiers=False)
api = exchange._api.urls['api']
async_api = exchange._api_async.urls['api']
payload = {{
    'sync_fapi_public': api.get('fapiPublic'),
    'sync_fapi_private': api.get('fapiPrivate'),
    'sync_private': api.get('private'),
    'async_fapi_public': async_api.get('fapiPublic'),
    'async_fapi_private': async_api.get('fapiPrivate'),
    'async_private': async_api.get('private'),
    'sync_https_proxy_set': bool(getattr(exchange._api, 'httpsProxy', None)),
    'async_https_proxy_set': bool(getattr(exchange._api_async, 'httpsProxy', None)),
}}
exchange.close()
print(json.dumps(payload, sort_keys=True))
"""
        result = subprocess.run([str(python_exe), "-c", code], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, env=clean_network_env())
        if result.returncode != 0:
            raise StageAcceptanceError("infra_transient", "futures_online_endpoint_unavailable", result.stderr.strip())
        payload = json.loads(result.stdout.strip().splitlines()[0])
        if payload["sync_fapi_public"] != FUTURES_PUBLIC_API or payload["async_fapi_public"] != FUTURES_PUBLIC_API:
            raise StageAcceptanceError("validation_error", "input_integrity_violation", "futures public URL override did not apply")
        if payload["sync_fapi_private"] != "https://fapi.binance.com/fapi/v1" or payload["sync_private"] != "https://api.binance.com/api/v3":
            raise StageAcceptanceError("validation_error", "input_integrity_violation", "private futures or spot URL was modified")
        if proxy_url and not (payload["sync_https_proxy_set"] and payload["async_https_proxy_set"]):
            raise StageAcceptanceError("validation_error", "input_integrity_violation", "proxy was not injected into both sync and async CCXT instances")
    else:
        if payload["sync_public"] != ONLINE_PUBLIC_API or payload["async_public"] != ONLINE_PUBLIC_API:
            raise StageAcceptanceError("validation_error", "input_integrity_violation", "public URL override did not apply")
        if payload["sync_private"] != "https://api.binance.com/api/v3" or payload["sync_sapi"] != "https://api.binance.com/sapi/v1":
            raise StageAcceptanceError("validation_error", "input_integrity_violation", "private or sapi URL was modified")
    payload["proxy"] = proxy_descriptor(proxy_url, proxy_type)
    return payload


def load_online_markets(
    repo_root: Path,
    campaign: dict[str, Any],
    run_dir: Path,
    proxy_url: str | None = None,
    proxy_type: str = "httpsProxy",
) -> dict[str, Any]:
    python_exe = runtime_python(repo_root, campaign)
    base_config = json.loads((repo_root / campaign["fixed_backtest"]["config"]).read_text(encoding="utf-8"))
    market_mode = str(base_config.get("trading_mode") or "spot")
    if market_mode == "futures":
        proxy_kwargs = ccxt_proxy_config(proxy_url, proxy_type)
        code = f"""
import ccxt, json
exchange = ccxt.binance({{'enableRateLimit': True, 'timeout': 30000, 'options': {{'defaultType': 'swap', 'fetchMarkets': {{'types': ['linear']}}}}, **{proxy_kwargs!r}}})
before = json.loads(json.dumps(exchange.urls.get('api', {{}}), sort_keys=True))
exchange.urls['api']['fapiPublic'] = {FUTURES_PUBLIC_API!r}
markets = exchange.load_markets()
payload = {{
    'api_urls_before': before,
    'api_urls_after': exchange.urls.get('api', {{}}),
    'markets': markets,
    'currencies': exchange.currencies,
    'options': exchange.options,
    'precisionMode': getattr(exchange, 'precisionMode', None),
    'paddingMode': getattr(exchange, 'paddingMode', None),
    'source_public_endpoint': {FUTURES_PUBLIC_API!r} + '/exchangeInfo',
    'https_proxy_set': bool(getattr(exchange, 'httpsProxy', None)),
}}
print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
"""
        result = subprocess.run([str(python_exe), "-c", code], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, env=clean_network_env())
        if result.returncode != 0:
            raise StageAcceptanceError("infra_transient", "futures_online_endpoint_unavailable", redact_proxy_text(result.stderr.strip() or result.stdout.strip(), proxy_url))
        payload = json.loads(result.stdout)
        async_code = f"""
import asyncio, json
import ccxt.async_support as ccxt
async def main():
    exchange = ccxt.binance({{'enableRateLimit': True, 'timeout': 30000, 'options': {{'defaultType': 'swap', 'fetchMarkets': {{'types': ['linear']}}}}, **{proxy_kwargs!r}}})
    exchange.urls['api']['fapiPublic'] = {FUTURES_PUBLIC_API!r}
    try:
        markets = await exchange.load_markets()
        print(json.dumps({{'market_count': len(markets), 'btc_usdt_usdt_present': 'BTC/USDT:USDT' in markets, 'https_proxy_set': bool(getattr(exchange, 'httpsProxy', None))}}, sort_keys=True))
    finally:
        await exchange.close()
asyncio.run(main())
"""
        async_result = subprocess.run([str(python_exe), "-c", async_code], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, env=clean_network_env())
        if async_result.returncode != 0:
            raise StageAcceptanceError("infra_transient", "futures_ccxt_async_load_markets_failed", redact_proxy_text(async_result.stderr.strip() or async_result.stdout.strip(), proxy_url))
        async_payload = json.loads(async_result.stdout.strip().splitlines()[-1])
        snapshot = repo_root / (campaign.get("sealed_offline_backtest") or {})["exchange_snapshot"]
        metadata = {
            "source_public_endpoint": payload["source_public_endpoint"],
            "api_urls_before": payload["api_urls_before"],
            "api_urls_after": payload["api_urls_after"],
            "market_count": len(payload.get("markets") or {}),
            "btc_usdt_usdt_present": "BTC/USDT:USDT" in (payload.get("markets") or {}),
            "ccxt_sync": {
                "load_markets_success": True,
                "market_count": len(payload.get("markets") or {}),
                "https_proxy_set": payload.get("https_proxy_set"),
            },
            "ccxt_async": {
                "load_markets_success": True,
                "market_count": async_payload.get("market_count"),
                "https_proxy_set": async_payload.get("https_proxy_set"),
            },
            "proxy": proxy_descriptor(proxy_url, proxy_type),
            "snapshot_manifest": repo_rel(repo_root, snapshot / "manifest.yaml"),
        }
        write_json(run_dir / "metadata-fingerprint.json", metadata)
        if not metadata["btc_usdt_usdt_present"]:
            raise StageAcceptanceError("validation_error", "futures_metadata_scope_drift", "BTC/USDT:USDT missing from online futures metadata")
        return metadata
    code = f"""
import ccxt, json
exchange = ccxt.binance({{'enableRateLimit': True, 'options': {{'defaultType': 'spot', 'fetchMarkets': {{'types': ['spot']}}}}}})
before = json.loads(json.dumps(exchange.urls.get('api', {{}}), sort_keys=True))
exchange.urls['api']['public'] = {ONLINE_PUBLIC_API!r}
markets = exchange.load_markets()
payload = {{
    'api_urls_before': before,
    'api_urls_after': exchange.urls.get('api', {{}}),
    'markets': markets,
    'currencies': exchange.currencies,
    'options': exchange.options,
    'precisionMode': getattr(exchange, 'precisionMode', None),
    'paddingMode': getattr(exchange, 'paddingMode', None),
    'source_public_endpoint': {ONLINE_PUBLIC_API!r} + '/exchangeInfo',
}}
print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
"""
    result = subprocess.run([str(python_exe), "-c", code], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode != 0:
        raise StageAcceptanceError("infra_transient", "online_reference_endpoint_unavailable", result.stderr.strip())
    payload = json.loads(result.stdout)
    snapshot = repo_root / "research/exchange_snapshots/binance-spot-2025-8-demo"
    online_metadata = {
        "markets": payload["markets"],
        "currencies": payload.get("currencies") or {},
        "options": payload.get("options") or {},
        "precisionMode": payload.get("precisionMode"),
        "paddingMode": payload.get("paddingMode"),
    }
    sealed_metadata = load_snapshot_metadata(
        snapshot,
        precision_mode=payload.get("precisionMode"),
        padding_mode=payload.get("paddingMode"),
    )
    report = build_equivalence_report(
        sealed_metadata,
        online_metadata,
        snapshot,
        pair=campaign["fixed_backtest"]["pairs"][0],
        fee_contract={"fee": campaign["fixed_backtest"]["fee"], "source": "fixed_backtest.fee"},
    )
    write_json(run_dir / "metadata-equivalence-report.json", report)
    write_equivalence_markdown(run_dir / "metadata-equivalence-report.md", report)
    fingerprint = {
        "source_public_endpoint": payload["source_public_endpoint"],
        "api_urls_before": payload["api_urls_before"],
        "api_urls_after": payload["api_urls_after"],
        "artifact_integrity": {
            "hash_domain": report["artifact_integrity"]["hash_domain"],
            "artifact_aggregate_complete": report["artifact_integrity"]["artifact_aggregate_complete"],
            "manifest_aggregate_sha256": report["artifact_integrity"]["manifest_aggregate_sha256"],
            "computed_aggregate_sha256": report["artifact_integrity"]["computed_aggregate_sha256"],
        },
        "artifact_vs_content_comparison": report["artifact_vs_content_comparison"],
        "full_metadata": report["full_metadata_comparison"],
        "research_scope": report["research_scope_comparison"],
        "classification": report["classification"],
    }
    write_json(run_dir / "metadata-fingerprint.json", fingerprint)
    if not report["artifact_integrity"]["artifact_aggregate_complete"]:
        raise StageAcceptanceError("validation_error", "input_integrity_violation", "sealed snapshot artifact integrity check failed")
    if not report["classification"]["continue_acceptance"]:
        raise StageAcceptanceError(
            report["classification"]["failure_type"] or "validation_error",
            report["classification"]["reason_code"],
            "exchange metadata research scope is not equivalent",
        )
    return fingerprint


def build_cli_command(repo_root: Path, campaign: dict[str, Any], config_path: Path, run_dir: Path) -> list[str]:
    spec = campaign["fixed_backtest"]
    command = [
        str(runtime_python(repo_root, campaign)),
        "-m",
        "freqtrade",
        "backtesting",
        "--strategy",
        spec["strategy"],
        "--strategy-path",
        spec.get("strategy_path", "strategies"),
        "--config",
        str(config_path),
        "--timerange",
        spec["timerange"],
        "--timeframe",
        spec["timeframe"],
        "--datadir",
        spec["datadir"],
        "--fee",
        str(spec["fee"]),
        "--export",
        "trades",
        "--export-filename",
        str(run_dir / "freqtrade-backtest-result.json"),
        "--export-directory",
        str(run_dir),
        "--breakdown",
        "day",
        "--cache",
        "none",
    ]
    for pair in spec["pairs"]:
        command.extend(["--pairs", pair])
    return command


def prepare_run_dir(path: Path) -> Path:
    if path.exists():
        raise StageAcceptanceError("validation_error", "input_integrity_violation", f"run directory already exists: {path}")
    path.mkdir(parents=True)
    return path


def run_online_baseline(
    repo_root: Path,
    campaign: dict[str, Any],
    run_dir: Path,
    online_config: Path,
    freeze: dict[str, Any],
    proxy_url: str | None = None,
    proxy_type: str = "httpsProxy",
) -> dict[str, Any]:
    prepare_run_dir(run_dir)
    proxy_info = proxy_descriptor(proxy_url, proxy_type)
    url_audit = inspect_ccxt_urls(repo_root, campaign, online_config, proxy_url=proxy_url, proxy_type=proxy_type)
    write_json(run_dir / "online-endpoint-audit.json", url_audit)
    metadata = load_online_markets(repo_root, campaign, run_dir, proxy_url=proxy_url, proxy_type=proxy_type)
    command = build_cli_command(repo_root, campaign, online_config, run_dir)
    write_json(run_dir / "command.json", {"command": command, "shell": False, "cache": "none"})
    started = utc_now()
    start = time.monotonic()
    code, stdout, stderr, timed_out = run_command(command, repo_root, int(campaign["fixed_backtest"].get("timeout_seconds", 600)), env=clean_network_env())
    write_limited(run_dir / "stdout.log", stdout)
    write_limited(run_dir / "stderr.log", redact_proxy_text(stderr.decode("utf-8", errors="ignore"), proxy_url).encode("utf-8"))
    if timed_out or code != 0:
        reason = "futures_online_baseline_failed" if campaign["fixed_backtest"]["pairs"][0].endswith(":USDT") else "online_baseline_failed"
        raise StageAcceptanceError("backtest_error", reason, f"online baseline exit={code} timed_out={timed_out}")
    network_audit = build_online_network_audit(run_dir, metadata, stdout, stderr, proxy_info)
    result_path = find_result_json(run_dir)
    metrics = parse_metrics(result_path, campaign["fixed_backtest"])
    trades = write_normalized_trades(run_dir, result_path, campaign["fixed_backtest"]["strategy"])
    summary = metric_summary(metrics, trades)
    if campaign["fixed_backtest"]["pairs"][0].endswith(":USDT"):
        require_futures_fixture_coverage(summary, "ONLINE-BASELINE")
    write_json(run_dir / "metrics.json", metrics)
    write_json(run_dir / "input-fingerprint.json", freeze)
    report = {
        "status": "accepted",
        "run_name": "ONLINE-BASELINE",
        "started_at": started,
        "completed_at": utc_now(),
        "wall_clock_seconds": round(time.monotonic() - start, 3),
        "exit_code": code,
        "cache": "none",
        "input_fingerprint": freeze["input_fingerprint"],
        "metadata_fingerprint": metadata,
        "online_network_audit_path": "online-network-audit.json",
        "online_network_audit": {
            "request_count": sum(item["request_count"] for item in network_audit["requests"]),
            "violations": network_audit["violations"],
            "proxy": proxy_info,
        },
        "summary": summary,
        "result_path": result_path.relative_to(run_dir).as_posix(),
    }
    write_json(run_dir / "runner-report.json", report)
    write_json(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    return report


def enrich_offline_run(repo_root: Path, campaign: dict[str, Any], run_dir: Path, freeze: dict[str, Any], run_name: str) -> dict[str, Any]:
    result_path = find_result_json(run_dir)
    metrics = parse_metrics(result_path, campaign["fixed_backtest"])
    trades = write_normalized_trades(run_dir, result_path, campaign["fixed_backtest"]["strategy"])
    summary = metric_summary(metrics, trades)
    if campaign["fixed_backtest"]["pairs"][0].endswith(":USDT"):
        require_futures_fixture_coverage(summary, run_name)
    write_json(run_dir / "metrics.json", metrics)
    write_json(run_dir / "input-fingerprint.json", freeze)
    report_path = run_dir / "runner-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update({"run_name": run_name, "cache": "none", "input_fingerprint": freeze["input_fingerprint"], "summary": summary})
    write_json(report_path, report)
    write_json(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    return report


def run_offline(repo_root: Path, campaign: dict[str, Any], experiment_id: str, run_name: str, snapshot_dir: Path, freeze: dict[str, Any]) -> dict[str, Any]:
    run_dir = repo_root / "research" / "results" / campaign["campaign_id"] / experiment_id / run_name
    prepare_run_dir(run_dir)
    result = run_offline_backtest(repo_root, campaign, experiment_id, run_name, snapshot_dir)
    if result["status"] != "accepted":
        reason = "futures_offline_control_failed" if run_name == "OFFLINE-CONTROL" else "reproducibility_execution_failed"
        raise StageAcceptanceError(result.get("failure_type") or "backtest_error", reason, result.get("message") or run_name)
    return enrich_offline_run(repo_root, campaign, run_dir, freeze, run_name)


def update_sqlite(repo_root: Path, campaign_id: str, experiment_id: str, report_path: Path, status: str) -> dict[str, Any]:
    db_path = repo_root / "research" / "registry" / "research.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS stage3a5_acceptance (campaign_id TEXT, experiment_id TEXT PRIMARY KEY, status TEXT NOT NULL, report_path TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO stage3a5_acceptance(campaign_id, experiment_id, status, report_path, updated_at) VALUES (?, ?, ?, ?, ?)",
            (campaign_id, experiment_id, status, repo_rel(repo_root, report_path), utc_now()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"db_path": repo_rel(repo_root, db_path), "table": "stage3a5_acceptance", "status": status}


def run_acceptance(
    repo_root: Path,
    campaign_path: Path,
    experiment_id: str | None = None,
    proxy_url: str | None = None,
    proxy_type: str = "httpsProxy",
) -> dict[str, Any]:
    campaign = load_campaign(campaign_path)
    spec = campaign["fixed_backtest"]
    base_config = json.loads((repo_root / spec["config"]).read_text(encoding="utf-8"))
    market_mode = str(base_config.get("trading_mode") or "spot")
    if market_mode not in {"spot", "futures"}:
        raise StageAcceptanceError("validation_error", "input_integrity_violation", f"unsupported market mode: {market_mode}")
    snapshot_dir = repo_root / (campaign.get("sealed_offline_backtest") or {})["exchange_snapshot"]
    experiment_id = experiment_id or ("stage3a5-" + utc_now().replace(":", "").replace("+00:00", "Z"))
    root = repo_root / "research" / "results" / campaign["campaign_id"] / experiment_id
    online_config = make_online_config(repo_root, campaign, root / "input-freeze", proxy_url=proxy_url, proxy_type=proxy_type)
    freeze = input_freeze(repo_root, campaign, snapshot_dir, online_config)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "input-freeze" / "input-freeze.json", freeze)

    online = run_online_baseline(repo_root, campaign, root / "ONLINE-BASELINE", online_config, freeze, proxy_url=proxy_url, proxy_type=proxy_type)
    offline_control = run_offline(repo_root, campaign, experiment_id, "OFFLINE-CONTROL", snapshot_dir, freeze)
    online_offline = compare_summaries(online["summary"], offline_control["summary"])
    write_json(root / "online-offline-comparison.json", online_offline)
    if not online_offline["consistent"]:
        raise StageAcceptanceError("validation_error", "offline_adapter_semantic_mismatch", "ONLINE-BASELINE and OFFLINE-CONTROL differ")

    run_a = run_offline(repo_root, campaign, experiment_id, "RUN-A", snapshot_dir, freeze)
    run_b = run_offline(repo_root, campaign, experiment_id, "RUN-B", snapshot_dir, freeze)
    repro = compare_summaries(run_a["summary"], run_b["summary"])
    repro["input_fingerprints"] = {"RUN-A": run_a["input_fingerprint"], "RUN-B": run_b["input_fingerprint"]}
    repro["input_fingerprint_consistent"] = run_a["input_fingerprint"] == run_b["input_fingerprint"]
    write_json(root / "run-a-run-b-comparison.json", repro)
    if not repro["consistent"] or not repro["input_fingerprint_consistent"]:
        raise StageAcceptanceError("validation_error", "reproducibility_mismatch", "RUN-A and RUN-B differ")

    final_report = {
        "campaign_execution": {"status": "completed"},
        "stage_acceptance": {"status": "passed"},
        "status": "completed",
        "stage3a_complete": True,
        "market_mode": market_mode,
        "campaign_id": campaign["campaign_id"],
        "experiment_id": experiment_id,
        "input_fingerprint": freeze["input_fingerprint"],
        "runs": {name: repo_rel(repo_root, root / name) for name in RUN_NAMES},
        "online_offline_comparison": online_offline,
        "reproducibility_comparison": repro,
        "cache_policy": "none",
        "proxy": proxy_descriptor(proxy_url, proxy_type),
        "sqlite": update_sqlite(repo_root, campaign["campaign_id"], experiment_id, root / "stage3a5-final-report.json", "completed"),
    }
    write_json(root / "stage3a5-final-report.json", final_report)
    return final_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Stage 3A.5 online/offline acceptance.")
    parser.add_argument("--campaign", default="research/campaigns/active/demo-sealed-offline-backtest.yaml")
    parser.add_argument("--experiment-id")
    parser.add_argument("--proxy")
    parser.add_argument("--proxy-type", choices=["httpsProxy", "httpProxy", "socksProxy"], default="httpsProxy")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = run_acceptance(Path.cwd(), Path(args.campaign), experiment_id=args.experiment_id, proxy_url=args.proxy, proxy_type=args.proxy_type)
    except StageAcceptanceError as exc:
        repo_root = Path.cwd()
        experiment_id = args.experiment_id or ("stage3a5-" + utc_now().replace(":", "").replace("+00:00", "Z"))
        campaign_id = "unknown"
        report_path = None
        try:
            campaign = load_campaign(Path(args.campaign))
            campaign_id = campaign["campaign_id"]
            root = repo_root / "research" / "results" / campaign_id / experiment_id
            root.mkdir(parents=True, exist_ok=True)
            report_path = root / "stage3a5-final-report.json"
        except Exception:
            campaign = None
        result = {
            "campaign_execution": {"status": "failed" if exc.failure_type != "infra_transient" else "stopped"},
            "stage_acceptance": {"status": "blocked", "reason_code": exc.reason_code},
            "status": "failed",
            "stage3a_complete": False,
            "campaign_id": campaign_id,
            "experiment_id": experiment_id,
            "failure_type": exc.failure_type,
            "reason_code": exc.reason_code,
            "message": redact_proxy_text(exc.message, args.proxy),
            "proxy": proxy_descriptor(args.proxy, args.proxy_type),
        }
        if report_path is not None:
            result["sqlite"] = update_sqlite(repo_root, campaign_id, experiment_id, report_path, result["stage_acceptance"]["status"])
            write_json(report_path, result)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
