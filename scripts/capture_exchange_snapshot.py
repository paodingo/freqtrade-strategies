#!/usr/bin/env python3
"""Capture and seal a real CCXT Binance markets metadata snapshot."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from exchange_endpoint_doctor import (
    BINANCE_OFFICIAL_BASE_URLS,
    EXCHANGE_INFO_PATH,
    EndpointPolicyError,
    endpoint_url,
    normalize_base_url,
    redact_proxy,
    resolve_proxy,
    run_doctor,
)
from run_experiment import sha256_file
from validate_exchange_snapshot import aggregate_hash


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict) -> None:
    lines = []
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            lines.append(f"{key}: {json.dumps(value, sort_keys=True, ensure_ascii=False)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def normalize_market(market: dict) -> dict:
    keys = [
        "id",
        "symbol",
        "base",
        "quote",
        "settle",
        "type",
        "spot",
        "margin",
        "swap",
        "future",
        "option",
        "active",
        "precision",
        "limits",
        "maker",
        "taker",
        "contract",
        "linear",
        "inverse",
        "contractSize",
    ]
    return {key: market.get(key) for key in keys if key in market}


def override_spot_public_api_urls(api_urls: dict, base_url: str) -> tuple[dict, dict]:
    if not isinstance(api_urls, dict):
        raise RuntimeError("ccxt binance urls['api'] is not a mapping")
    if "public" not in api_urls:
        raise RuntimeError("ccxt binance spot public endpoint key was not found")
    before = json.loads(json.dumps(api_urls, sort_keys=True))
    after = json.loads(json.dumps(api_urls, sort_keys=True))
    after["public"] = normalize_base_url(base_url) + "/api/v3"
    for key, value in before.items():
        if key != "public" and after.get(key) != value:
            raise RuntimeError(f"non-public Binance API URL changed unexpectedly: {key}")
    return before, after


def redact_text(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "<redacted-proxy-url>")


def classify_capture_failure(stderr: str) -> str:
    lowered = stderr.casefold()
    if " 403" in lowered or "forbidden" in lowered:
        return "endpoint_http_403"
    if " 418" in lowered:
        return "endpoint_http_418"
    if " 429" in lowered or "too many requests" in lowered:
        return "endpoint_http_429"
    if "timed out" in lowered or "timeout" in lowered:
        return "endpoint_connect_timeout"
    if "ssl" in lowered or "tls" in lowered:
        return "endpoint_tls_failure"
    if "json" in lowered or "symbols" in lowered:
        return "metadata_schema_invalid"
    return "metadata_capture_incomplete"


def choose_endpoint(
    base_url: str | None,
    proxy: str | None,
    connect_timeout: float,
    request_timeout: float,
    repo_root: Path,
) -> tuple[str | None, dict]:
    if base_url:
        selected = normalize_base_url(base_url)
        report = run_doctor(base_urls=[selected], connect_timeout=connect_timeout, request_timeout=request_timeout, repo_root=repo_root, allow_proxy_sources=False)
        return (selected if report["ok"] else None), report
    direct = run_doctor(connect_timeout=connect_timeout, request_timeout=request_timeout, repo_root=repo_root, allow_proxy_sources=False)
    if direct["ok"]:
        return direct["selected_base_url"], direct
    _available_proxy_type, available_proxy_url = resolve_proxy(proxy, repo_root=repo_root, allow_sources=True)
    if available_proxy_url:
        proxied = run_doctor(proxy=proxy, connect_timeout=connect_timeout, request_timeout=request_timeout, repo_root=repo_root, allow_proxy_sources=True)
        return proxied["selected_base_url"], proxied
    return None, direct


def capture_with_runtime(runtime_python: Path, base_url: str, proxy_type: str | None, proxy_url: str | None, timeout: int) -> tuple[int, str, str]:
    code = r"""
import ccxt
import freqtrade
import json
import os
import platform
import sys

base_url = os.environ["RESEARCH_BINANCE_BASE_URL"].rstrip("/")
spot_public_url = base_url + "/api/v3"
proxy_type = os.environ.get("RESEARCH_BINANCE_PROXY_TYPE")
proxy_url = os.environ.get("RESEARCH_BINANCE_PROXY_URL")
exchange_config = {
    "enableRateLimit": True,
    "options": {
        "defaultType": "spot",
        "fetchMarkets": {"types": ["spot"]},
    },
}
if proxy_url:
    if proxy_type == "httpsProxy":
        exchange_config["httpsProxy"] = proxy_url
    elif proxy_type == "httpProxy":
        exchange_config["httpProxy"] = proxy_url
    elif proxy_type == "socksProxy":
        exchange_config["socksProxy"] = proxy_url
exchange = ccxt.binance(exchange_config)
api_urls_before = json.loads(json.dumps(exchange.urls.get("api", {}), sort_keys=True))
api_urls = exchange.urls.get("api")
if not isinstance(api_urls, dict):
    raise RuntimeError("ccxt binance urls['api'] is not a mapping")
if "public" not in api_urls:
    raise RuntimeError("ccxt binance spot public endpoint key was not found")
private_before = {key: value for key, value in api_urls.items() if key != "public"}
api_urls["public"] = spot_public_url
private_after = {key: value for key, value in api_urls.items() if key != "public"}
if private_before != private_after:
    raise RuntimeError("non-public Binance API URLs changed unexpectedly")
markets = exchange.load_markets()
payload = {
    "python_version": platform.python_version(),
    "freqtrade_version": getattr(freqtrade, "__version__", "unknown"),
    "ccxt_version": ccxt.__version__,
    "markets": markets,
    "currencies": exchange.currencies,
    "options": exchange.options,
    "spot_public_key": "public",
    "source_public_endpoint": spot_public_url + "/exchangeInfo",
    "ccxt_api_urls_before": api_urls_before,
    "ccxt_api_urls_after": exchange.urls.get("api", {}),
}
print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
"""
    env = os.environ.copy()
    env["RESEARCH_BINANCE_BASE_URL"] = base_url
    if proxy_type and proxy_url:
        env["RESEARCH_BINANCE_PROXY_TYPE"] = proxy_type
        env["RESEARCH_BINANCE_PROXY_URL"] = proxy_url
        if proxy_type == "httpsProxy":
            env["HTTPS_PROXY"] = proxy_url
        elif proxy_type == "httpProxy":
            env["HTTP_PROXY"] = proxy_url
        elif proxy_type == "socksProxy":
            env["ALL_PROXY"] = proxy_url
    result = subprocess.run(
        [str(runtime_python), "-c", code],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        shell=False,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def artifact_entries(snapshot_dir: Path) -> list[dict]:
    entries = []
    for path in sorted(snapshot_dir.iterdir()):
        if path.is_file() and path.name != "manifest.yaml":
            entries.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return entries


def seal_files(snapshot_dir: Path) -> None:
    for path in snapshot_dir.iterdir():
        if path.is_file():
            os.chmod(path, stat.S_IREAD)


def remove_snapshot_dir(path: Path) -> None:
    if not path.exists():
        return
    for item in path.rglob("*"):
        if item.is_file():
            os.chmod(item, stat.S_IWRITE)
    shutil.rmtree(path)


def capture_snapshot(
    repo_root: str | Path,
    snapshot_id: str,
    runtime_python: str | Path,
    proxy: str | None = None,
    base_url: str | None = None,
    timeout: int = 60,
    connect_timeout: float = 5.0,
    request_timeout: float = 10.0,
) -> dict:
    repo_root = Path(repo_root).resolve()
    runtime_python = (repo_root / runtime_python).resolve() if not Path(runtime_python).is_absolute() else Path(runtime_python)
    if not runtime_python.exists():
        raise RuntimeError(f"runtime python missing: {runtime_python}")
    snapshot_dir = repo_root / "research" / "exchange_snapshots" / snapshot_id
    remove_snapshot_dir(snapshot_dir)
    snapshot_dir.mkdir(parents=True)
    log_path = snapshot_dir / "capture.log"
    proxy_type, proxy_url = resolve_proxy(proxy, repo_root=repo_root)
    selected_base_url, endpoint_report = choose_endpoint(base_url, proxy, connect_timeout, request_timeout, repo_root)
    write_json(snapshot_dir / "endpoint-doctor.json", endpoint_report)
    if not selected_base_url:
        log_path.write_text(
            "\n".join(
                [
                    f"started_at={utc_now()}",
                    f"runtime_python={runtime_python}",
                    "selected_base_url=",
                    f"proxy={json.dumps(redact_proxy(proxy_url), sort_keys=True)}",
                    "returncode=endpoint-doctor-failed",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        raise RuntimeError("no Binance official endpoint passed endpoint doctor")
    log_lines = [
        f"started_at={utc_now()}",
        f"runtime_python={runtime_python}",
        f"selected_base_url={selected_base_url}",
        f"source_public_endpoint={endpoint_url(selected_base_url)}",
        f"proxy={json.dumps(redact_proxy(proxy_url), sort_keys=True)}",
    ]
    returncode, stdout, stderr = capture_with_runtime(runtime_python, selected_base_url, proxy_type, proxy_url, timeout)
    stderr = redact_text(stderr, proxy_url)
    stdout = redact_text(stdout, proxy_url)
    log_lines.extend([f"returncode={returncode}", "--- stderr ---", stderr])
    if returncode != 0:
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        reason = classify_capture_failure(stderr)
        raise RuntimeError(f"{reason}; ccxt load_markets failed; log={log_path}")
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        log_lines.extend(["--- stdout ---", stdout])
        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
        raise RuntimeError(f"capture output was not JSON: {exc}") from exc

    markets = payload["markets"]
    currencies = payload.get("currencies") or {}
    options = payload.get("options") or {}
    normalized = {symbol: normalize_market(value) for symbol, value in sorted(markets.items())}
    write_json(snapshot_dir / "markets.raw.json", markets)
    write_json(snapshot_dir / "markets.normalized.json", normalized)
    write_json(snapshot_dir / "currencies.json", currencies)
    write_json(snapshot_dir / "options.json", options)
    write_json(
        snapshot_dir / "ccxt-url-structure.json",
        {
            "spot_public_key": payload.get("spot_public_key"),
            "source_public_endpoint": payload.get("source_public_endpoint"),
            "api_urls_before": payload.get("ccxt_api_urls_before"),
            "api_urls_after": payload.get("ccxt_api_urls_after"),
        },
    )
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    entries = artifact_entries(snapshot_dir)
    write_json(snapshot_dir / "artifact-hashes.json", {item["path"]: {"bytes": item["bytes"], "sha256": item["sha256"]} for item in entries})
    entries = artifact_entries(snapshot_dir)
    btc = normalized.get("BTC/USDT") or {}
    manifest = {
        "snapshot_id": snapshot_id,
        "exchange": "binance",
        "trading_mode": "spot",
        "python_version": payload.get("python_version"),
        "freqtrade_version": payload.get("freqtrade_version"),
        "ccxt_version": payload.get("ccxt_version"),
        "captured_at": utc_now(),
        "source_public_endpoint": payload.get("source_public_endpoint"),
        "base_url": selected_base_url,
        "proxy_used": bool(proxy_url),
        "proxy_type": proxy_type,
        "markets_count": len(markets),
        "currencies_count": len(currencies),
        "btc_usdt_exists": bool(btc),
        "btc_usdt_spot": btc.get("spot"),
        "btc_usdt_active": btc.get("active"),
        "btc_usdt_precision": btc.get("precision"),
        "btc_usdt_limits": btc.get("limits"),
        "btc_usdt_maker": btc.get("maker"),
        "btc_usdt_taker": btc.get("taker"),
        "files": entries,
        "aggregate_sha256": aggregate_hash(entries),
        "sealed": True,
        "sealed_at": utc_now(),
        "sealed_by": "scripts/capture_exchange_snapshot.py",
    }
    write_yaml(snapshot_dir / "manifest.yaml", manifest)
    seal_files(snapshot_dir)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a real Binance exchange metadata snapshot.")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--runtime-python", default=".venv-freqtrade/Scripts/python.exe")
    parser.add_argument("--base-url")
    parser.add_argument("--proxy")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--connect-timeout", type=float, default=5.0)
    parser.add_argument("--request-timeout", type=float, default=10.0)
    args = parser.parse_args()
    try:
        manifest = capture_snapshot(
            Path.cwd(),
            args.snapshot_id,
            args.runtime_python,
            proxy=args.proxy,
            base_url=args.base_url,
            timeout=args.timeout,
            connect_timeout=args.connect_timeout,
            request_timeout=args.request_timeout,
        )
    except Exception as exc:
        message = str(exc)
        reason_code = next((code for code in (
            "endpoint_dns_failure",
            "endpoint_connect_timeout",
            "endpoint_read_timeout",
            "endpoint_tls_failure",
            "endpoint_http_403",
            "endpoint_http_418",
            "endpoint_http_429",
            "proxy_connect_failure",
            "proxy_auth_failure",
            "proxy_tls_failure",
            "metadata_schema_invalid",
            "metadata_capture_incomplete",
        ) if code in message), "exchange_markets_metadata_timeout")
        print(json.dumps({"ok": False, "failure_type": "infra_transient", "reason_code": reason_code, "message": message}, indent=2))
        return 1
    print(json.dumps({"ok": True, "manifest": manifest}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
