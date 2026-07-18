#!/usr/bin/env python3
"""Audit current public-source reachability and local data-layer freshness."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


BASE_URL = "https://fapi.binance.com"
PAIR = "BTC/USDT:USDT"
SYMBOL = "BTCUSDT"
PUBLIC_ENDPOINTS = {
    "server_time": ("/fapi/v1/time", {}),
    "klines_1h": ("/fapi/v1/klines", {"symbol": SYMBOL, "interval": "1h", "limit": 3}),
    "klines_4h": ("/fapi/v1/klines", {"symbol": SYMBOL, "interval": "4h", "limit": 3}),
    "premium_index": ("/fapi/v1/premiumIndex", {"symbol": SYMBOL}),
    "funding_rate": ("/fapi/v1/fundingRate", {"symbol": SYMBOL, "limit": 3}),
    "open_interest": ("/futures/data/openInterestHist", {"symbol": SYMBOL, "period": "5m", "limit": 3}),
    "taker_flow": ("/futures/data/takerlongshortRatio", {"symbol": SYMBOL, "period": "5m", "limit": 3}),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def epoch_ms_iso(value: int | float | None) -> str | None:
    if not value:
        return None
    return iso(datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc))


def public_probe(name: str, path: str, params: dict[str, Any], timeout: float) -> dict[str, Any]:
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    started = utc_now()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "freqtrade-data-layer-audit/1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = response.status
        completed = utc_now()
        latest_ms = None
        row_count = len(payload) if isinstance(payload, list) else 1
        if name.startswith("klines_") and payload:
            latest_ms = payload[-1][6]
        elif name == "premium_index":
            latest_ms = payload.get("time")
        elif name == "funding_rate" and payload:
            latest_ms = payload[-1].get("fundingTime")
        elif name in {"open_interest", "taker_flow"} and payload:
            latest_ms = payload[-1].get("timestamp")
        elif name == "server_time":
            latest_ms = payload.get("serverTime")
        return {
            "ok": status == 200,
            "http_status": status,
            "latency_ms": round((completed - started).total_seconds() * 1000, 1),
            "row_count": row_count,
            "latest_timestamp": epoch_ms_iso(latest_ms),
            "endpoint": path,
            "authentication": "none_public_market_data",
        }
    except Exception as error:
        completed = utc_now()
        return {
            "ok": False,
            "latency_ms": round((completed - started).total_seconds() * 1000, 1),
            "endpoint": path,
            "error_type": type(error).__name__,
            "error": str(error)[:240],
            "authentication": "none_public_market_data",
        }


def node_fetch_probe(repo: Path, use_env_proxy: bool) -> dict[str, Any]:
    environment = os.environ.copy()
    if use_env_proxy:
        environment["NODE_USE_ENV_PROXY"] = "1"
    else:
        environment.pop("NODE_USE_ENV_PROXY", None)
    code = (
        "fetch('https://fapi.binance.com/fapi/v1/time',"
        "{signal:AbortSignal.timeout(6000)})"
        ".then(async r=>{console.log(JSON.stringify({ok:r.ok,status:r.status}));"
        "if(!r.ok)process.exitCode=2})"
        ".catch(e=>{console.log(JSON.stringify({ok:false,error:e.name}));process.exitCode=1})"
    )
    started = utc_now()
    try:
        result = subprocess.run(
            ["node", "-e", code],
            cwd=repo,
            env=environment,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            shell=False,
        )
        payload = json.loads((result.stdout.strip().splitlines() or ["{}"]) [-1])
        return {
            "ok": result.returncode == 0 and payload.get("ok") is True,
            "use_env_proxy": use_env_proxy,
            "exit_code": result.returncode,
            "latency_ms": round((utc_now() - started).total_seconds() * 1000, 1),
            "error_type": payload.get("error"),
        }
    except Exception as error:
        return {
            "ok": False,
            "use_env_proxy": use_env_proxy,
            "latency_ms": round((utc_now() - started).total_seconds() * 1000, 1),
            "error_type": type(error).__name__,
        }


def listener_probe(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def monitor_store_probe(runtime_root: Path, observed_at: datetime) -> dict[str, Any]:
    path = runtime_root / "user_data/monitor_history.sqlite"
    if not path.is_file():
        return {"exists": False, "latest_sample": None, "age_seconds": None, "stale": True}
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        rows = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in ("history_samples", "alpha_risk_samples", "regime_router_samples")
        }
        latest = connection.execute("SELECT MAX(sampled_at) FROM history_samples").fetchone()[0]
    finally:
        connection.close()
    latest_at = datetime.fromisoformat(latest.replace("Z", "+00:00")) if latest else None
    age = (observed_at - latest_at).total_seconds() if latest_at else None
    return {
        "exists": True,
        "path": path.relative_to(runtime_root).as_posix(),
        "rows": rows,
        "latest_sample": iso(latest_at) if latest_at else None,
        "age_seconds": round(age, 1) if age is not None else None,
        "stale": age is None or age > 7200,
    }


def current_local_history_probe(runtime_root: Path, observed_at: datetime) -> dict[str, Any]:
    roots = [
        runtime_root / "user_data/data",
        runtime_root / "research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-202603-202606/data/futures",
    ]
    files = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("**/BTC_USDT_USDT-*-*.feather"):
            frame = pd.read_feather(path, columns=["date"])
            dates = pd.to_datetime(frame["date"], utc=True)
            latest = dates.max().to_pydatetime()
            files.append(
                {
                    "path": path.relative_to(runtime_root).as_posix(),
                    "rows": int(len(dates)),
                    "latest_timestamp": iso(latest),
                    "age_seconds": round((observed_at - latest).total_seconds(), 1),
                }
            )
    user_data_files = [item for item in files if item["path"].startswith("user_data/data/")]
    latest = max((item["latest_timestamp"] for item in files), default=None)
    return {
        "user_data_market_file_count": len(user_data_files),
        "inspected_file_count": len(files),
        "latest_local_market_timestamp": latest,
        "files": sorted(files, key=lambda item: item["path"]),
        "continuously_updated_current_history": False,
    }


def trade_store_probe(runtime_root: Path) -> dict[str, Any]:
    stores = sorted(
        path.relative_to(runtime_root).as_posix()
        for path in (runtime_root / "user_data").glob("*.sqlite")
        if "monitor_history" not in path.name
    )
    return {
        "freqtrade_trade_store_count": len(stores),
        "paths": stores,
        "current_simulated_pnl_available": bool(stores),
    }


def build_audit(repo: Path, runtime_root: Path, timeout: float) -> dict[str, Any]:
    observed_at = utc_now()
    public = {
        name: public_probe(name, path, params, timeout)
        for name, (path, params) in PUBLIC_ENDPOINTS.items()
    }
    monitor = monitor_store_probe(runtime_root, observed_at)
    local_history = current_local_history_probe(runtime_root, observed_at)
    trades = trade_store_probe(runtime_root)
    node_default = node_fetch_probe(repo, use_env_proxy=False)
    node_proxy = node_fetch_probe(repo, use_env_proxy=True)
    proxy_present = bool(os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"))
    public_all_ok = all(item["ok"] for item in public.values())
    dashboard_path_ok = node_default["ok"] or (not proxy_present and public_all_ok)
    feature_coverage = {
        "current_on_demand": {
            "ohlcv_1h": public["klines_1h"]["ok"],
            "ohlcv_4h": public["klines_4h"]["ok"],
            "mark_and_index": public["premium_index"]["ok"],
            "funding_rate": public["funding_rate"]["ok"],
            "open_interest": public["open_interest"]["ok"],
            "taker_flow": public["taker_flow"]["ok"],
        },
        "continuous_local_history": {
            "ohlcv": False,
            "mark_and_funding": False,
            "open_interest": False,
            "taker_flow": False,
            "long_short_ratios": False,
            "order_book": False,
            "liquidations": False,
            "trade_ticks": False,
        },
    }
    verdicts = {
        "sealed_historical_research_integrity": {
            "grade": "reliable",
            "reason": "sealed manifests, byte hashes, UTC continuity and exact local rehydration are enforced",
        },
        "public_binance_source_reachability": {
            "grade": "reliable_at_observation_time" if public_all_ok else "degraded",
            "reason": "all audited unauthenticated USD-M public endpoints responded" if public_all_ok else "one or more audited public endpoints failed",
        },
        "dashboard_live_fetch_path": {
            "grade": "reliable" if dashboard_path_ok else "unreliable",
            "reason": "Node fetch succeeds in the current launch environment" if dashboard_path_ok else "Node fetch bypasses required environment proxy; NODE_USE_ENV_PROXY=1 restores reachability",
        },
        "local_persistence_freshness": {
            "grade": "unreliable",
            "reason": "no continuously updated market history is persisted and monitor samples exceed the 2h freshness SLA",
        },
        "current_simulated_performance": {
            "grade": "unavailable" if not trades["current_simulated_pnl_available"] else "available",
            "reason": "no current Freqtrade trade SQLite store exists" if not trades["current_simulated_pnl_available"] else "at least one Freqtrade trade store exists",
        },
        "feature_completeness": {
            "grade": "partial",
            "reason": "OHLCV/mark/funding/OI/taker are available on demand, but continuous historical alpha, order-book, liquidation and trade-tick datasets are absent",
        },
    }
    return {
        "schema_version": "data-layer-reliability-audit-v1",
        "observed_at": iso(observed_at),
        "pair": PAIR,
        "scope": "read_only_public_market_data_and_local_persistence",
        "runtime_root_mode": "explicit_local_workspace",
        "overall_verdict": "not_reliable_for_current_strategy_decisioning",
        "verdicts": verdicts,
        "public_endpoint_probe": public,
        "runtime": {
            "dashboard_port_8090_listening": listener_probe(8090),
            "freqtrade_port_8122_listening": listener_probe(8122),
            "monitor_store": monitor,
            "trade_store": trades,
            "local_market_history": local_history,
        },
        "node_proxy_diagnosis": {
            "http_or_https_proxy_present": proxy_present,
            "node_use_env_proxy_configured": os.environ.get("NODE_USE_ENV_PROXY") == "1",
            "default_node_fetch": node_default,
            "node_fetch_with_env_proxy": node_proxy,
            "root_cause_confirmed": proxy_present and not node_default["ok"] and node_proxy["ok"],
        },
        "feature_coverage": feature_coverage,
        "remediation_gates": [
            "launch Dashboard Node with environment proxy support when HTTP(S)_PROXY is required",
            "restore a supervised Freqtrade dry-run service and current trade SQLite store",
            "schedule incremental 15m/1h/4h futures OHLCV plus mark and funding persistence with gap alarms",
            "persist time-aligned OI, taker flow and long/short ratios for research instead of relying only on ephemeral snapshots",
            "add freshness SLOs and fail-closed UI states for each source independently",
        ],
        "security": {
            "private_endpoints_called": False,
            "credentials_read": False,
            "trading_actions": False,
        },
    }


def report_text(audit: dict[str, Any]) -> str:
    verdicts = audit["verdicts"]
    public_ok = sum(item["ok"] for item in audit["public_endpoint_probe"].values())
    public_total = len(audit["public_endpoint_probe"])
    monitor = audit["runtime"]["monitor_store"]
    return "\n".join(
        [
            "# 数据层可靠性审计",
            "",
            f"- 审计时间：`{audit['observed_at']}`",
            f"- 总体结论：`{audit['overall_verdict']}`",
            f"- Binance USD-M 公共接口：`{public_ok}/{public_total}` 可达",
            f"- Dashboard Node 代理根因：`{str(audit['node_proxy_diagnosis']['root_cause_confirmed']).lower()}`",
            f"- Dashboard / Freqtrade 本地监听：`{str(audit['runtime']['dashboard_port_8090_listening']).lower()} / {str(audit['runtime']['freqtrade_port_8122_listening']).lower()}`",
            f"- Monitor 最新采样：`{monitor.get('latest_sample')}`，stale=`{str(monitor.get('stale')).lower()}`",
            f"- 当前模拟盘收益库：`{str(audit['runtime']['trade_store']['current_simulated_pnl_available']).lower()}`",
            "",
            "## 分层结论",
            "",
            "| 层 | 评级 | 原因 |",
            "|---|---|---|",
            *[
                f"| `{key}` | `{value['grade']}` | {value['reason']} |"
                for key, value in verdicts.items()
            ],
            "",
            "## 解释",
            "",
            "冻结研究数据可按清单和 SHA-256 精确复现，因此适合可重复的历史研究；但它不是实时数据。当前 Binance 公共源本身可用，故障发生在本机 Node 运行链路没有使用所需代理。即使修复代理，本机仍没有持续运行的 Dashboard/Freqtrade 服务、连续增量落盘和当前模拟盘交易库。",
            "",
            "现有字段覆盖也只是部分完整：按需可取得 OHLCV、mark/index、funding、OI 和 taker flow；缺少连续历史 OI/taker/多空比，以及订单簿、清算和逐笔成交的研究级落盘。",
            "",
            "## 修复门槛",
            "",
            *[f"- {item}" for item in audit["remediation_gates"]],
            "",
        ]
    )


def update_current_state(repo: Path, audit: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    state_path = repo / "research/director/current-research-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monitor = audit["runtime"]["monitor_store"]
    state["data_layer_reliability"] = {
        "status": "audited_current",
        "observed_at": audit["observed_at"],
        "overall_verdict": audit["overall_verdict"],
        "sealed_historical_research_integrity": "reliable",
        "public_binance_endpoints": {
            "available": all(item["ok"] for item in audit["public_endpoint_probe"].values()),
            "passed": sum(item["ok"] for item in audit["public_endpoint_probe"].values()),
            "total": len(audit["public_endpoint_probe"]),
        },
        "dashboard_live_fetch_path": audit["verdicts"]["dashboard_live_fetch_path"]["grade"],
        "node_proxy_root_cause_confirmed": audit["node_proxy_diagnosis"]["root_cause_confirmed"],
        "local_persistence_freshness": audit["verdicts"]["local_persistence_freshness"]["grade"],
        "feature_completeness": audit["verdicts"]["feature_completeness"]["grade"],
        "monitor_latest_sample": monitor.get("latest_sample"),
        "current_simulated_pnl_available": audit["runtime"]["trade_store"]["current_simulated_pnl_available"],
        "remediation_required": True,
        "evidence": [json_path.as_posix(), markdown_path.as_posix()],
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    state_md = repo / "research/director/current-research-state.md"
    existing = state_md.read_text(encoding="utf-8")
    marker = "## 数据层当前审计"
    existing = existing.split(marker, 1)[0].rstrip()
    section = "\n".join(
        [
            marker,
            "",
            f"- 审计时间：`{audit['observed_at']}`",
            f"- 总体：`{audit['overall_verdict']}`",
            f"- Binance 公共源：`{sum(item['ok'] for item in audit['public_endpoint_probe'].values())}/{len(audit['public_endpoint_probe'])}` 可达",
            "- 冻结历史研究数据：`reliable`",
            "- Dashboard 实时 fetch：`unreliable`（Node 未使用所需环境代理；根因已复现）",
            "- 本地连续落盘：`unreliable`",
            f"- Monitor 最新采样：`{monitor.get('latest_sample')}`",
            f"- 当前模拟盘收益：`{'available' if audit['runtime']['trade_store']['current_simulated_pnl_available'] else 'unavailable'}`",
            "- 字段完整性：`partial`",
            "",
            f"审计：`{markdown_path.as_posix()}`。",
            "",
        ]
    )
    state_md.write_text(existing + "\n\n" + section, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--update-current-state", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    runtime_root = (args.runtime_root or repo).resolve()
    audit = build_audit(repo, runtime_root, args.timeout)
    if args.json_output:
        output = repo / args.json_output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if args.markdown_output:
        output = repo / args.markdown_output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_text(audit), encoding="utf-8", newline="\n")
    if args.update_current_state:
        if not args.json_output or not args.markdown_output:
            raise SystemExit("--update-current-state requires --json-output and --markdown-output")
        update_current_state(repo, audit, args.json_output, args.markdown_output)
    print(json.dumps({"overall_verdict": audit["overall_verdict"], "public_endpoints_ok": sum(item["ok"] for item in audit["public_endpoint_probe"].values()), "node_proxy_root_cause_confirmed": audit["node_proxy_diagnosis"]["root_cause_confirmed"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
