#!/usr/bin/env python3
"""Capture a sealed Binance USD-M futures CCXT metadata snapshot."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capture_exchange_snapshot import artifact_entries, normalize_market, write_json, write_yaml
from exchange_metadata_fingerprint import build_futures_scope_fingerprint
from run_experiment import sha256_file
from validate_exchange_snapshot import aggregate_hash


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def capture(runtime_python: str, timeout: int) -> dict[str, Any]:
    code = r"""
import ccxt, freqtrade, json, sys
exchange = ccxt.binance({
    "enableRateLimit": True,
    "options": {"defaultType": "swap", "fetchMarkets": {"types": ["linear"]}},
})
before = json.loads(json.dumps(exchange.urls.get("api", {}), sort_keys=True))
markets = exchange.load_markets()
payload = {
    "python_version": sys.version.split()[0],
    "freqtrade_version": freqtrade.__version__,
    "ccxt_version": ccxt.__version__,
    "markets": markets,
    "currencies": exchange.currencies,
    "options": exchange.options,
    "api_urls_before": before,
    "api_urls_after": exchange.urls.get("api", {}),
    "precisionMode": getattr(exchange, "precisionMode", None),
    "paddingMode": getattr(exchange, "paddingMode", None),
}
print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
"""
    result = subprocess.run([runtime_python, "-c", code], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode != 0:
        return capture_raw_fapi_with_ccxt_parser(runtime_python, timeout, result.stderr.strip())
    return json.loads(result.stdout)


def classify_ccxt_load_markets_error(error_text: str) -> dict[str, str | bool]:
    lowered = error_text.casefold()
    if "requesttimeout" in lowered or "connecttimeout" in lowered or "timed out" in lowered:
        reason = "futures_metadata_ccxt_timeout"
    else:
        reason = "futures_metadata_ccxt_load_markets_failed"
    return {
        "used_fallback": True,
        "reason_code": reason,
        "sanitized_detail": "ccxt binance futures load_markets did not complete; raw public fapi exchangeInfo fallback was used",
    }


def capture_raw_fapi_with_ccxt_parser(runtime_python: str, timeout: int, ccxt_error: str) -> dict[str, Any]:
    endpoint = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    with urllib.request.urlopen(endpoint, timeout=20) as response:
        raw = json.loads(response.read().decode("utf-8"))
    temp = json.dumps(raw, sort_keys=True, ensure_ascii=False)
    code = r"""
import ccxt, freqtrade, json, sys
raw = json.loads(sys.stdin.read())
exchange = ccxt.binance({"options": {"defaultType": "swap"}})
markets = {}
for item in raw.get("symbols", []):
    try:
        market = exchange.parse_market(item)
        markets[market["symbol"]] = market
    except Exception:
        pass
currencies = {}
for asset in raw.get("assets", []):
    code = asset.get("asset")
    if code:
        currencies[code] = {
            "id": code,
            "code": code,
            "numericId": None,
            "precision": None,
            "active": None,
            "deposit": None,
            "withdraw": None,
            "limits": {},
        }
payload = {
    "python_version": sys.version.split()[0],
    "freqtrade_version": freqtrade.__version__,
    "ccxt_version": ccxt.__version__,
    "markets": markets,
    "currencies": currencies,
    "options": exchange.options,
    "api_urls_before": exchange.urls.get("api", {}),
    "api_urls_after": exchange.urls.get("api", {}),
    "precisionMode": getattr(exchange, "precisionMode", None),
    "paddingMode": getattr(exchange, "paddingMode", None),
    "raw_fapi_exchange_info": raw,
}
print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
"""
    result = subprocess.run([runtime_python, "-c", code], input=temp, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or ccxt_error or f"ccxt parser returned {result.returncode}")
    payload = json.loads(result.stdout)
    payload["ccxt_load_markets_fallback"] = classify_ccxt_load_markets_error(ccxt_error)
    payload["fallback_source_public_endpoint"] = endpoint
    return payload


def capture_snapshot(repo_root: str | Path, runtime_python: str, snapshot_id: str, timeout: int = 180) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    snapshot_dir = repo / "research" / "exchange_snapshots" / snapshot_id
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True)
    payload = capture(runtime_python, timeout)
    markets = payload["markets"]
    currencies = payload.get("currencies") or {}
    options = payload.get("options") or {}
    normalized = {symbol: normalize_market(value) for symbol, value in sorted(markets.items())}
    write_json(snapshot_dir / "markets.raw.json", markets)
    write_json(snapshot_dir / "markets.normalized.json", normalized)
    write_json(snapshot_dir / "currencies.json", currencies)
    write_json(snapshot_dir / "options.json", options)
    if payload.get("raw_fapi_exchange_info"):
        write_json(snapshot_dir / "fapi.exchangeInfo.raw.json", payload["raw_fapi_exchange_info"])
    write_json(snapshot_dir / "ccxt-url-structure.json", {
        "api_urls_before": payload.get("api_urls_before"),
        "api_urls_after": payload.get("api_urls_after"),
        "source_public_endpoint": payload.get("api_urls_after", {}).get("fapiPublic") or payload.get("api_urls_after", {}).get("fapiPublicV2"),
    })
    leverage_path = repo / ".venv-freqtrade" / "Lib" / "site-packages" / "freqtrade" / "exchange" / "binance_leverage_tiers.json"
    leverage_artifact = {
        "path": leverage_path.relative_to(repo).as_posix() if leverage_path.exists() else None,
        "sha256": sha256_file(leverage_path) if leverage_path.exists() else None,
        "bytes": leverage_path.stat().st_size if leverage_path.exists() else None,
        "network_required": False,
        "load_path": "freqtrade.exchange.binance_leverage_tiers.json",
    }
    write_json(snapshot_dir / "leverage-tiers-contract.json", leverage_artifact)
    scope = build_futures_scope_fingerprint(
        {
            "markets": markets,
            "currencies": currencies,
            "options": options,
            "precisionMode": payload.get("precisionMode"),
            "paddingMode": payload.get("paddingMode"),
        },
        leverage_tier_artifact=leverage_artifact,
        fee_contract={"fee": "0.0004", "source": "fixed_backtest.fee"},
        funding_model_contract={
            "funding_rate_source": "sealed_dataset",
            "funding_model_synthetic": False,
            "execution_baseline_only": True,
        },
    )
    write_json(snapshot_dir / "futures-scope-fingerprint.json", {k: v for k, v in scope.items() if k != "canonical_payload"})
    entries = artifact_entries(snapshot_dir)
    write_json(snapshot_dir / "artifact-hashes.json", {item["path"]: {"bytes": item["bytes"], "sha256": item["sha256"]} for item in entries})
    entries = artifact_entries(snapshot_dir)
    btc = normalized.get("BTC/USDT:USDT") or {}
    manifest = {
        "snapshot_id": snapshot_id,
        "exchange": "binance",
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "pair": "BTC/USDT:USDT",
        "python_version": payload.get("python_version"),
        "freqtrade_version": payload.get("freqtrade_version"),
        "ccxt_version": payload.get("ccxt_version"),
        "markets_count": len(markets),
        "currencies_count": len(currencies),
        "btc_usdt_usdt_exists": bool(btc),
        "btc_usdt_usdt_swap": btc.get("swap"),
        "btc_usdt_usdt_linear": btc.get("linear"),
        "btc_usdt_usdt_contract": btc.get("contract"),
        "btc_usdt_usdt_contract_size": btc.get("contractSize"),
        "leverage_tier_artifact": leverage_artifact,
        "funding_model_contract": {
            "funding_rate_source": "sealed_dataset",
            "funding_model_synthetic": False,
            "execution_baseline_only": True,
            "suitable_for_strategy_ranking": False,
        },
        "ccxt_load_markets_fallback": payload.get("ccxt_load_markets_fallback"),
        "fallback_source_public_endpoint": payload.get("fallback_source_public_endpoint"),
        "files": entries,
        "aggregate_sha256": aggregate_hash(entries),
        "sealed": True,
        "sealed_at": utc_now(),
        "sealed_by": "scripts/capture_futures_exchange_snapshot.py",
    }
    write_yaml(snapshot_dir / "manifest.yaml", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture Binance USD-M futures metadata snapshot.")
    parser.add_argument("--snapshot-id", default="binance-usdm-futures-2025-8-demo")
    parser.add_argument("--runtime-python", default=".venv-freqtrade/Scripts/python.exe")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    manifest = capture_snapshot(Path.cwd(), args.runtime_python, args.snapshot_id, args.timeout)
    print(json.dumps({"ok": True, "manifest": manifest}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
