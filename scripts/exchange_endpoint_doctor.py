#!/usr/bin/env python3
"""Diagnose Binance public metadata endpoints for sealed snapshot provisioning."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse


BINANCE_OFFICIAL_BASE_URLS = (
    "https://data-api.binance.vision",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
    "https://api.binance.com",
)
ALLOWED_HOSTS = {urlparse(item).hostname.casefold() for item in BINANCE_OFFICIAL_BASE_URLS}
EXCHANGE_INFO_PATH = "/api/v3/exchangeInfo"
PROXY_ENV = {
    "httpsProxy": "RESEARCH_BINANCE_HTTPS_PROXY",
    "httpProxy": "RESEARCH_BINANCE_HTTP_PROXY",
    "socksProxy": "RESEARCH_BINANCE_SOCKS_PROXY",
}
PROXY_OVERRIDE_FILE = Path("research/runtime/provisioning/proxy-override.json")


class EndpointPolicyError(ValueError):
    pass


class NoProxySelected(RuntimeError):
    pass


def normalize_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme.lower() != "https":
        raise EndpointPolicyError("base URL scheme must be HTTPS")
    if parsed.username or parsed.password:
        raise EndpointPolicyError("base URL must not contain username or password")
    if parsed.query or parsed.fragment:
        raise EndpointPolicyError("base URL must not contain query or fragment")
    if parsed.path not in ("", "/"):
        raise EndpointPolicyError("base URL must not contain a path")
    host = (parsed.hostname or "").casefold()
    if not host:
        raise EndpointPolicyError("base URL host is required")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost"):
        raise EndpointPolicyError("localhost is not allowed")
    try:
        ipaddress.ip_address(host)
        raise EndpointPolicyError("IP literal hosts are not allowed")
    except ValueError:
        pass
    if host not in ALLOWED_HOSTS:
        raise EndpointPolicyError(f"host is not in Binance official allowlist: {host}")
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    return urlunparse(("https", netloc, "", "", "", ""))


def endpoint_url(base_url: str) -> str:
    return normalize_base_url(base_url) + EXCHANGE_INFO_PATH


def classify_http_status(status: int) -> str:
    if status == 403:
        return "endpoint_http_403"
    if status == 418:
        return "endpoint_http_418"
    if status == 429:
        return "endpoint_http_429"
    if status < 200 or status >= 300:
        return "endpoint_unexpected_status"
    return "ok"


def redact_proxy(proxy_url: str | None) -> dict | None:
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    host = parsed.hostname or ""
    return {
        "scheme": parsed.scheme,
        "host": host,
        "port": parsed.port,
        "has_auth": bool(parsed.username or parsed.password),
    }


def load_proxy_override(repo_root: Path) -> dict:
    path = repo_root / PROXY_OVERRIDE_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_proxy(cli_proxy: str | None = None, repo_root: str | Path = ".", allow_sources: bool = True) -> tuple[str | None, str | None]:
    candidates: list[tuple[str, str]] = []
    if cli_proxy:
        parsed = urlparse(cli_proxy)
        if parsed.scheme in {"https"}:
            candidates.append(("httpsProxy", cli_proxy))
        elif parsed.scheme in {"http"}:
            candidates.append(("httpProxy", cli_proxy))
        elif parsed.scheme.startswith("socks"):
            candidates.append(("socksProxy", cli_proxy))
        else:
            raise EndpointPolicyError("proxy scheme must be http, https, socks4, or socks5")
    if not allow_sources:
        if candidates:
            types = {item[0] for item in candidates}
            if len(types) > 1:
                raise EndpointPolicyError("proxy types are mutually exclusive")
            return candidates[0]
        return None, None
    for proxy_type, env_name in PROXY_ENV.items():
        if os.environ.get(env_name):
            candidates.append((proxy_type, os.environ[env_name]))
    override = load_proxy_override(Path(repo_root))
    for proxy_type in ("httpsProxy", "httpProxy", "socksProxy"):
        if override.get(proxy_type):
            candidates.append((proxy_type, str(override[proxy_type])))
    if not candidates:
        return None, None
    types = {item[0] for item in candidates}
    if len(types) > 1:
        raise EndpointPolicyError("proxy types are mutually exclusive")
    return candidates[0]


def dns_check(host: str) -> tuple[bool, list[str], str | None]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        ips = sorted({item[4][0] for item in infos})
        for ip in ips:
            parsed = ipaddress.ip_address(ip)
            if parsed.is_private or parsed.is_loopback or parsed.is_link_local:
                return False, ips, "private or local DNS result is not allowed"
        return True, ips, None
    except socket.gaierror as exc:
        return False, [], str(exc)


def tcp_tls_check(host: str, connect_timeout: float) -> tuple[dict, dict]:
    tcp = {"ok": False, "reason_code": None, "elapsed_ms": None}
    tls = {"ok": False, "reason_code": None, "elapsed_ms": None}
    started = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(connect_timeout)
    try:
        sock.connect((host, 443))
        tcp["ok"] = True
    except socket.timeout:
        tcp["reason_code"] = "endpoint_connect_timeout"
        return tcp, tls
    except OSError as exc:
        tcp["reason_code"] = "endpoint_dns_failure" if isinstance(exc, socket.gaierror) else "endpoint_connect_timeout"
        tcp["error"] = str(exc)
        return tcp, tls
    finally:
        tcp["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    started = time.perf_counter()
    try:
        context = ssl.create_default_context()
        with context.wrap_socket(sock, server_hostname=host) as tls_sock:
            tls_sock.getpeercert()
        tls["ok"] = True
    except ssl.SSLError as exc:
        tls["reason_code"] = "endpoint_tls_failure"
        tls["error"] = str(exc)
    except OSError as exc:
        tls["reason_code"] = "endpoint_tls_failure"
        tls["error"] = str(exc)
    finally:
        tls["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return tcp, tls


class GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        redirected = normalize_base_url(urlunparse((parsed.scheme, netloc, "", "", "", "")))
        if redirected not in BINANCE_OFFICIAL_BASE_URLS:
            raise EndpointPolicyError(f"redirect to non-allowlisted host: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_check(base_url: str, request_timeout: float, proxy_type: str | None = None, proxy_url: str | None = None) -> dict:
    url = endpoint_url(base_url)
    handlers: list[Any] = [GuardedRedirectHandler()]
    if proxy_url:
        if proxy_type == "socksProxy":
            return {"ok": False, "reason_code": "proxy_connect_failure", "error": "socks proxy is not supported by urllib endpoint doctor"}
        handlers.append(urllib.request.ProxyHandler({"https": proxy_url, "http": proxy_url}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, headers={"User-Agent": "research-endpoint-doctor/1.0"})
    started = time.perf_counter()
    result: dict[str, Any] = {
        "ok": False,
        "status": None,
        "reason_code": None,
        "elapsed_ms": None,
        "json": False,
        "symbols": False,
        "btc_usdt": False,
        "url": url,
    }
    try:
        with opener.open(request, timeout=request_timeout) as response:
            body = response.read()
            result["status"] = int(response.status)
            status_reason = classify_http_status(int(response.status))
            if status_reason != "ok":
                result["reason_code"] = status_reason
                return result
            payload = json.loads(body.decode("utf-8"))
            result["json"] = True
            symbols = payload.get("symbols")
            result["symbols"] = isinstance(symbols, list)
            result["btc_usdt"] = any(item.get("symbol") == "BTCUSDT" for item in symbols or [] if isinstance(item, dict))
            if not result["symbols"] or not result["btc_usdt"]:
                result["reason_code"] = "metadata_schema_invalid"
            else:
                result["ok"] = True
                result["reason_code"] = "ok"
    except urllib.error.HTTPError as exc:
        result["status"] = int(exc.code)
        result["reason_code"] = classify_http_status(int(exc.code))
    except TimeoutError:
        result["reason_code"] = "endpoint_read_timeout"
    except ssl.SSLError as exc:
        result["reason_code"] = "proxy_tls_failure" if proxy_url else "endpoint_tls_failure"
        result["error"] = str(exc)
    except EndpointPolicyError as exc:
        result["reason_code"] = "endpoint_unexpected_status"
        result["error"] = str(exc)
    except urllib.error.URLError as exc:
        text = str(exc.reason)
        if "407" in text or "authentication" in text.casefold():
            result["reason_code"] = "proxy_auth_failure"
        elif proxy_url:
            result["reason_code"] = "proxy_connect_failure"
        elif "timed out" in text.casefold():
            result["reason_code"] = "endpoint_read_timeout"
        else:
            result["reason_code"] = "endpoint_connect_timeout"
        result["error"] = text
    except json.JSONDecodeError as exc:
        result["reason_code"] = "metadata_schema_invalid"
        result["error"] = str(exc)
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result


def diagnose_endpoint(base_url: str, proxy_type: str | None, proxy_url: str | None, connect_timeout: float, request_timeout: float) -> dict:
    started = time.perf_counter()
    normalized = normalize_base_url(base_url)
    host = urlparse(normalized).hostname or ""
    dns_ok, ips, dns_error = dns_check(host)
    tcp = {"ok": None, "reason_code": None, "elapsed_ms": None}
    tls = {"ok": None, "reason_code": None, "elapsed_ms": None}
    if dns_ok and not proxy_url:
        tcp, tls = tcp_tls_check(host, connect_timeout)
    http = http_check(normalized, request_timeout, proxy_type=proxy_type, proxy_url=proxy_url) if dns_ok else {"ok": False, "reason_code": "endpoint_dns_failure", "status": None}
    ok = bool(dns_ok and http.get("ok") and (proxy_url or (tcp.get("ok") and tls.get("ok"))))
    reason_code = "ok" if ok else http.get("reason_code") or tls.get("reason_code") or tcp.get("reason_code") or "endpoint_dns_failure"
    return {
        "base_url": normalized,
        "host": host,
        "dns": {"ok": dns_ok, "ips": ips, "error": dns_error},
        "tcp": tcp,
        "tls": tls,
        "http": http,
        "proxy": {"used": bool(proxy_url), "type": proxy_type, "redacted": redact_proxy(proxy_url)},
        "ok": ok,
        "reason_code": reason_code,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def run_doctor(
    exchange: str = "binance",
    base_urls: list[str] | None = None,
    proxy: str | None = None,
    connect_timeout: float = 5.0,
    request_timeout: float = 10.0,
    repo_root: str | Path = ".",
    allow_proxy_sources: bool = True,
) -> dict:
    if exchange != "binance":
        raise EndpointPolicyError("only binance is supported")
    proxy_type, proxy_url = resolve_proxy(proxy, repo_root=repo_root, allow_sources=allow_proxy_sources)
    urls = base_urls or list(BINANCE_OFFICIAL_BASE_URLS)
    results = []
    for item in urls:
        try:
            attempts = []
            for attempt_no in range(1, 4):
                attempt = diagnose_endpoint(item, proxy_type, proxy_url, connect_timeout, request_timeout)
                attempt["attempt_no"] = attempt_no
                attempts.append(attempt)
                reason = attempt.get("reason_code")
                if attempt.get("ok") or reason not in {"endpoint_dns_failure", "endpoint_connect_timeout", "endpoint_read_timeout"}:
                    break
            final = dict(attempts[-1])
            final["attempts"] = attempts
            results.append(final)
        except EndpointPolicyError as exc:
            results.append({"base_url": item, "ok": False, "reason_code": "endpoint_unexpected_status", "error": str(exc), "proxy": {"used": bool(proxy_url), "type": proxy_type, "redacted": redact_proxy(proxy_url)}})
    selected = next((item["base_url"] for item in results if item.get("ok")), None)
    return {
        "exchange": exchange,
        "ok": selected is not None,
        "selected_base_url": selected,
        "proxy": {"used": bool(proxy_url), "type": proxy_type, "redacted": redact_proxy(proxy_url)},
        "endpoints": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Binance public exchangeInfo endpoints.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--base-url", action="append")
    parser.add_argument("--proxy")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--connect-timeout", type=float, default=5.0)
    parser.add_argument("--request-timeout", type=float, default=10.0)
    args = parser.parse_args()
    try:
        report = run_doctor(
            exchange=args.exchange,
            base_urls=args.base_url,
            proxy=args.proxy,
            connect_timeout=args.connect_timeout,
            request_timeout=args.request_timeout,
        )
    except EndpointPolicyError as exc:
        report = {"exchange": args.exchange, "ok": False, "selected_base_url": None, "error": str(exc), "endpoints": []}
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(f"endpoint doctor: {'pass' if report['ok'] else 'fail'}")
        for item in report.get("endpoints", []):
            print(f"- {item.get('base_url')}: {item.get('reason_code')}")
    return 1 if args.strict and not report.get("ok") else 0


if __name__ == "__main__":
    raise SystemExit(main())
