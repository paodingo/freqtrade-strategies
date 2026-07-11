#!/usr/bin/env python3
"""Deterministic Binance USD-M futures endpoint diagnostics for Stage 3A.5."""

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from research_control import load_campaign
from run_stage3a5_acceptance import (
    FUTURES_PUBLIC_API,
    clean_network_env,
    make_online_config,
    proxy_descriptor,
    redact_proxy_text,
    runtime_python,
)


BASE_HOST = "fapi.binance.com"
BASE_URL = "https://fapi.binance.com"
PUBLIC_PATHS = ("/fapi/v1/time", "/fapi/v1/exchangeInfo")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def elapsed(start: float) -> float:
    return round(time.monotonic() - start, 3)


def result(layer: str, success: bool, start: float, **extra: Any) -> dict[str, Any]:
    payload = {
        "layer": layer,
        "success": success,
        "elapsed_seconds": elapsed(start),
    }
    payload.update(extra)
    return payload


def sanitize_exception(exc: BaseException, proxy_url: str | None = None) -> dict[str, str]:
    return {
        "exception_type": type(exc).__name__,
        "sanitized_exception": redact_proxy_text(str(exc), proxy_url)[:1000],
    }


def resolve_dns(timeout: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = time.monotonic()
    try:
        socket.setdefaulttimeout(timeout)
        infos = socket.getaddrinfo(BASE_HOST, 443, type=socket.SOCK_STREAM)
        addresses = []
        for family, _type, _proto, _canon, sockaddr in infos:
            addresses.append(
                {
                    "address": sockaddr[0],
                    "family": "IPv6" if family == socket.AF_INET6 else "IPv4",
                }
            )
        return addresses, result("dns_resolution", True, start, reason_code=None, resolved_addresses=addresses)
    except Exception as exc:
        return [], result("dns_resolution", False, start, reason_code="futures_endpoint_dns_failure", **sanitize_exception(exc))


def tcp_connect(addresses: list[dict[str, Any]], family_name: str, timeout: float) -> dict[str, Any]:
    start = time.monotonic()
    selected = [item for item in addresses if item["family"] == family_name]
    attempts = []
    reason = f"futures_endpoint_{family_name.lower()}_connect_timeout"
    for item in selected:
        try:
            family = socket.AF_INET6 if family_name == "IPv6" else socket.AF_INET
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((item["address"], 443))
            attempts.append({"address": item["address"], "success": True})
            return result(f"{family_name.lower()}_tcp_443", True, start, reason_code=None, attempts=attempts)
        except Exception as exc:
            attempts.append({"address": item["address"], "success": False, **sanitize_exception(exc)})
    return result(f"{family_name.lower()}_tcp_443", False, start, reason_code=reason, attempts=attempts)


def tls_handshake(timeout: float) -> dict[str, Any]:
    start = time.monotonic()
    try:
        context = ssl.create_default_context()
        with socket.create_connection((BASE_HOST, 443), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=BASE_HOST) as tls:
                cipher = tls.cipher()
        return result("tls_handshake", True, start, reason_code=None, cipher=cipher)
    except Exception as exc:
        return result("tls_handshake", False, start, reason_code="futures_endpoint_tls_failure", **sanitize_exception(exc))


def http_get(path: str, timeout: float, proxy_url: str | None) -> dict[str, Any]:
    start = time.monotonic()
    url = BASE_URL + path
    try:
        if proxy_url:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"https": proxy_url, "http": proxy_url}))
        else:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=timeout) as response:
            sample = response.read(200)
            status = response.status
        ok = status == 200
        return result(
            f"http_get_{path}",
            ok,
            start,
            reason_code=None if ok else f"futures_endpoint_http_{status}" if status in {403, 418, 429} else "futures_endpoint_unexpected_status",
            actual_endpoint=url,
            http_status=status,
            response_sample_bytes=len(sample),
        )
    except urllib.error.HTTPError as exc:
        reason = f"futures_endpoint_http_{exc.code}" if exc.code in {403, 418, 429} else "futures_endpoint_unexpected_status"
        return result(f"http_get_{path}", False, start, reason_code=reason, actual_endpoint=url, http_status=exc.code, **sanitize_exception(exc, proxy_url))
    except TimeoutError as exc:
        return result(f"http_get_{path}", False, start, reason_code="futures_endpoint_read_timeout", actual_endpoint=url, **sanitize_exception(exc, proxy_url))
    except Exception as exc:
        reason = "futures_proxy_connect_failed" if proxy_url else "futures_endpoint_read_timeout"
        return result(f"http_get_{path}", False, start, reason_code=reason, actual_endpoint=url, **sanitize_exception(exc, proxy_url))


def run_python_layer(name: str, python_exe: Path, code: str, timeout: float, proxy_url: str | None) -> dict[str, Any]:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            [str(python_exe), "-c", code],
            cwd=Path.cwd(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=clean_network_env(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        reason = "futures_ccxt_async_load_markets_failed" if "async" in name else "futures_ccxt_sync_load_markets_failed"
        return result(name, False, start, reason_code=reason, exception_type="TimeoutExpired", sanitized_exception=redact_proxy_text(str(exc), proxy_url))
    if completed.returncode == 0:
        try:
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
        except Exception:
            payload = {"stdout_tail": completed.stdout.strip()[-500:]}
        return result(name, True, start, reason_code=None, **payload)
    reason = "futures_ccxt_async_load_markets_failed" if "async" in name else "futures_ccxt_sync_load_markets_failed"
    return result(
        name,
        False,
        start,
        reason_code=reason,
        stdout=redact_proxy_text(completed.stdout, proxy_url)[-1000:],
        stderr=redact_proxy_text(completed.stderr, proxy_url)[-2000:],
    )


def ccxt_sync_code(proxy_url: str | None) -> str:
    proxy = {"httpsProxy": proxy_url} if proxy_url else {}
    return f"""
import ccxt, json
exchange = ccxt.binance({{'enableRateLimit': True, 'timeout': 30000, 'options': {{'defaultType': 'swap', 'fetchMarkets': {{'types': ['linear']}}}}, **{proxy!r}}})
exchange.urls['api']['fapiPublic'] = {FUTURES_PUBLIC_API!r}
markets = exchange.load_markets()
print(json.dumps({{'market_count': len(markets), 'btc_usdt_usdt_present': 'BTC/USDT:USDT' in markets, 'https_proxy_set': bool(getattr(exchange, 'httpsProxy', None)), 'actual_endpoint': {FUTURES_PUBLIC_API!r} + '/exchangeInfo'}}, sort_keys=True))
"""


def ccxt_async_code(proxy_url: str | None) -> str:
    proxy = {"httpsProxy": proxy_url} if proxy_url else {}
    return f"""
import asyncio, json
import ccxt.async_support as ccxt
async def main():
    exchange = ccxt.binance({{'enableRateLimit': True, 'timeout': 30000, 'options': {{'defaultType': 'swap', 'fetchMarkets': {{'types': ['linear']}}}}, **{proxy!r}}})
    exchange.urls['api']['fapiPublic'] = {FUTURES_PUBLIC_API!r}
    try:
        markets = await exchange.load_markets()
        print(json.dumps({{'market_count': len(markets), 'btc_usdt_usdt_present': 'BTC/USDT:USDT' in markets, 'https_proxy_set': bool(getattr(exchange, 'httpsProxy', None)), 'actual_endpoint': {FUTURES_PUBLIC_API!r} + '/exchangeInfo'}}, sort_keys=True))
    finally:
        await exchange.close()
asyncio.run(main())
"""


def freqtrade_cli_layer(repo_root: Path, campaign: dict[str, Any], timeout: float, proxy_url: str | None) -> dict[str, Any]:
    start = time.monotonic()
    python_exe = runtime_python(repo_root, campaign)
    try:
        with tempfile.TemporaryDirectory(prefix="futures-doctor-") as tmp:
            config_path = make_online_config(repo_root, campaign, Path(tmp), proxy_url=proxy_url, proxy_type="httpsProxy")
            cmd = [
                str(python_exe),
                "-m",
                "freqtrade",
                "list-markets",
                "--config",
                str(config_path),
                "--exchange",
                "binance",
                "--trading-mode",
                "futures",
                "--print-json",
            ]
            completed = subprocess.run(cmd, cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=clean_network_env(), check=False)
        if completed.returncode == 0:
            return result("freqtrade_cli_initialization", True, start, reason_code=None, stdout_tail=completed.stdout[-500:])
        return result(
            "freqtrade_cli_initialization",
            False,
            start,
            reason_code="futures_freqtrade_cli_initialization_failed",
            stdout=redact_proxy_text(completed.stdout, proxy_url)[-1000:],
            stderr=redact_proxy_text(completed.stderr, proxy_url)[-2000:],
        )
    except Exception as exc:
        return result("freqtrade_cli_initialization", False, start, reason_code="futures_freqtrade_cli_initialization_failed", **sanitize_exception(exc, proxy_url))


def run_doctor(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path.cwd()
    proxy_url = args.proxy
    campaign = load_campaign(args.campaign)
    python_exe = runtime_python(repo_root, campaign)
    proxy = proxy_descriptor(proxy_url, "httpsProxy")
    checks = []
    addresses, dns = resolve_dns(args.connect_timeout)
    checks.append(dns)
    checks.append(tcp_connect(addresses, "IPv4", args.connect_timeout))
    checks.append(tcp_connect(addresses, "IPv6", args.connect_timeout))
    checks.append(tls_handshake(args.connect_timeout))
    for path in PUBLIC_PATHS:
        checks.append(http_get(path, args.request_timeout, proxy_url))
    checks.append(run_python_layer("ccxt_sync_load_markets", python_exe, ccxt_sync_code(proxy_url), args.request_timeout, proxy_url))
    checks.append(run_python_layer("ccxt_async_load_markets", python_exe, ccxt_async_code(proxy_url), args.request_timeout, proxy_url))
    checks.append(freqtrade_cli_layer(repo_root, campaign, args.request_timeout, proxy_url))
    if proxy_url:
        required_layers = {
            "http_get_/fapi/v1/time",
            "http_get_/fapi/v1/exchangeInfo",
            "ccxt_sync_load_markets",
            "ccxt_async_load_markets",
            "freqtrade_cli_initialization",
        }
        ok = all(item["success"] for item in checks if item["layer"] in required_layers)
    else:
        ok = all(item["success"] for item in checks if item["layer"] not in {"ipv6_tcp_443"})
    return {
        "schema": "stage3a5-futures-endpoint-doctor-v1",
        "generated_at": utc_now(),
        "base_url": BASE_URL,
        "proxy": proxy,
        "checks": checks,
        "ok": ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Binance USD-M futures public endpoint reachability.")
    parser.add_argument("--campaign", default="research/campaigns/active/demo-futures-stage3a5-acceptance.yaml")
    parser.add_argument("--proxy")
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--request-timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_doctor(args)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
