#!/usr/bin/env python3
"""Assess runtime data reliability and perform bounded, auditable repairs.

The controller deliberately does not mutate strategy code, rebuild databases, delete
data, or manage trading bot lifecycles. Its repair surface is limited to the
Dashboard data service and the existing market-data refresh unit.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import datetime as dt
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "data-reliability-report-v1"
STATUS_ORDER = {
    "reliable": 0,
    "degraded": 1,
    "incomplete": 2,
    "stale": 3,
    "blocked": 4,
}
DEFAULT_BASE_URL = "http://127.0.0.1:8090"
DEFAULT_REPORT_DIR = Path("/home/ubuntu/freqtrade-runtime/data-reliability")
DEFAULT_PAIR = "BTC/USDT:USDT"
DEFAULT_TIMEFRAME = "15m"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def isoformat(value: dt.datetime | None = None) -> str:
    value = value or utc_now()
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def age_seconds(value: Any, now: dt.datetime) -> int | None:
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    return max(0, round((now - parsed).total_seconds()))


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check(
    check_id: str,
    status: str,
    severity: str,
    message: str,
    *,
    blocks_decisions: bool = False,
    observed_value: Any = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "severity": severity,
        "message": message,
        "blocks_decisions": blocks_decisions,
        "observed_value": observed_value,
    }


def assess_snapshot(
    snapshot: dict[str, Any],
    *,
    now: dt.datetime | None = None,
    ticker_stale_seconds: int = 120,
    candle_stale_seconds: int = 2700,
    minimum_candles: int = 24,
) -> dict[str, Any]:
    """Return a pure reliability assessment for a four-endpoint snapshot."""
    now = now or utc_now()
    checks: list[dict[str, Any]] = []

    summary = snapshot.get("summary")
    if not isinstance(summary, dict):
        checks.append(check(
            "dashboard.summary", "blocked", "critical", "Dashboard summary endpoint is unavailable.",
            blocks_decisions=True,
        ))
    else:
        summary_age = age_seconds(summary.get("generatedAt"), now)
        if summary_age is None or summary_age > ticker_stale_seconds:
            checks.append(check(
                "dashboard.observation", "stale", "critical", "Runtime observation timestamp is stale or invalid.",
                blocks_decisions=True, observed_value={"age_seconds": summary_age},
            ))
        else:
            checks.append(check(
                "dashboard.observation", "reliable", "info", "Runtime observation is current.",
                observed_value={"age_seconds": summary_age},
            ))

        bots = summary.get("bots")
        if not isinstance(bots, list) or not bots:
            checks.append(check(
                "runtime.instances", "blocked", "critical", "No runtime strategy instances were observed.",
                blocks_decisions=True,
            ))
        else:
            for index, bot in enumerate(bots):
                bot = bot if isinstance(bot, dict) else {}
                bot_key = str(bot.get("key") or f"instance-{index + 1}")
                if bot.get("ok") is not True:
                    checks.append(check(
                        f"runtime.{bot_key}", "blocked", "critical", "Runtime strategy instance is unreachable.",
                        blocks_decisions=True,
                        observed_value={
                            "runtime_status": bot.get("runtimeStatus"),
                            "error_code": bot.get("errorCode"),
                        },
                    ))
                    continue
                if bot.get("dryRun") is not True:
                    checks.append(check(
                        f"runtime.{bot_key}", "blocked", "critical", "Runtime instance is not verified as dry-run.",
                        blocks_decisions=True, observed_value={"dry_run": bot.get("dryRun")},
                    ))
                    continue
                checks.append(check(
                    f"runtime.{bot_key}", "reliable", "info", "Dry-run runtime instance is reachable.",
                    observed_value={"latency_ms": bot.get("latencyMs")},
                ))
                if not is_number(bot.get("profitAllCoin")):
                    checks.append(check(
                        f"performance.{bot_key}", "incomplete", "warning",
                        "Simulated P&L is unavailable and was not substituted with zero.",
                        blocks_decisions=False, observed_value=None,
                    ))
                else:
                    checks.append(check(
                        f"performance.{bot_key}", "reliable", "info", "Simulated P&L is available.",
                        observed_value={
                            "profit_abs": bot.get("profitAllCoin"),
                            "currency": bot.get("stakeCurrency"),
                        },
                    ))

    registry = snapshot.get("registry")
    deployment = registry.get("deployment") if isinstance(registry, dict) else None
    if not isinstance(deployment, dict) or deployment.get("available") is not True:
        checks.append(check(
            "deployment.identity", "blocked", "critical", "Deployment identity is unavailable or invalid.",
            blocks_decisions=True,
            observed_value=(deployment or {}).get("status_reason") if isinstance(deployment, dict) else None,
        ))
    elif deployment.get("dry_run_only") is not True:
        checks.append(check(
            "deployment.identity", "blocked", "critical", "Deployment is not verified as dry-run-only.",
            blocks_decisions=True,
        ))
    else:
        checks.append(check(
            "deployment.identity", "reliable", "info", "Immutable dry-run deployment identity is verified.",
            observed_value={"git_sha": deployment.get("git_short_sha")},
        ))

    market = snapshot.get("market")
    if not isinstance(market, dict):
        checks.append(check(
            "market.candles", "blocked", "critical", "Market endpoint is unavailable.",
            blocks_decisions=True,
        ))
    else:
        candles = market.get("candles")
        candle_count = len(candles) if isinstance(candles, list) else 0
        source_type = market.get("sourceType")
        freshness = market.get("dataFreshness") if isinstance(market.get("dataFreshness"), dict) else {}
        candle_age = freshness.get("ageSeconds")
        if not is_number(candle_age):
            candle_age = age_seconds(market.get("lastAnalyzed"), now)
        if source_type == "unavailable" or candle_count == 0:
            checks.append(check(
                "market.candles", "blocked", "critical", "No usable market candles are available.",
                blocks_decisions=True,
                observed_value={"count": candle_count, "source_type": source_type},
            ))
        elif freshness.get("stale") is True or candle_age is None or candle_age > candle_stale_seconds:
            checks.append(check(
                "market.candles", "stale", "critical", "Market candles are stale.",
                blocks_decisions=True,
                observed_value={"count": candle_count, "age_seconds": candle_age, "source_type": source_type},
            ))
        elif candle_count < minimum_candles:
            checks.append(check(
                "market.candles", "incomplete", "critical", "Market candle window is incomplete.",
                blocks_decisions=True,
                observed_value={"count": candle_count, "minimum": minimum_candles},
            ))
        else:
            checks.append(check(
                "market.candles", "reliable", "info", "Market candle window is current and complete.",
                observed_value={"count": candle_count, "age_seconds": candle_age, "source_type": source_type},
            ))

        ticker = market.get("ticker")
        ticker_age = age_seconds(ticker.get("updatedAt"), now) if isinstance(ticker, dict) else None
        if not isinstance(ticker, dict) or not is_number(ticker.get("price")):
            checks.append(check(
                "market.ticker", "incomplete", "critical", "Current ticker price is unavailable.",
                blocks_decisions=True,
            ))
        elif ticker_age is None or ticker_age > ticker_stale_seconds:
            checks.append(check(
                "market.ticker", "stale", "critical", "Current ticker price is stale.",
                blocks_decisions=True, observed_value={"age_seconds": ticker_age},
            ))
        else:
            checks.append(check(
                "market.ticker", "reliable", "info", "Current ticker price is available.",
                observed_value={"price": ticker.get("price"), "age_seconds": ticker_age},
            ))

    alpha = snapshot.get("alpha")
    if not isinstance(alpha, dict):
        checks.append(check(
            "market.alpha", "incomplete", "warning", "Derivatives alpha metrics are unavailable.",
            blocks_decisions=True,
        ))
    elif alpha.get("status") == "ok":
        checks.append(check(
            "market.alpha", "reliable", "info", "Derivatives alpha metrics are complete.",
            observed_value={"source": alpha.get("source")},
        ))
    elif alpha.get("status") == "partial":
        checks.append(check(
            "market.alpha", "degraded", "warning", "Derivatives alpha metrics are partially available.",
            observed_value={"error_count": len(alpha.get("errors") or [])},
        ))
    else:
        checks.append(check(
            "market.alpha", "incomplete", "warning", "Derivatives alpha metrics are unavailable.",
            blocks_decisions=True,
            observed_value={"status": alpha.get("status")},
        ))

    overall_status = max((item["status"] for item in checks), key=lambda value: STATUS_ORDER[value])
    decision_allowed = not any(item["blocks_decisions"] for item in checks)
    issues = [item for item in checks if item["status"] != "reliable"]
    return {
        "overall_status": overall_status,
        "decision_allowed": decision_allowed,
        "checks": checks,
        "issues": issues,
        "summary": {
            "check_count": len(checks),
            "reliable_count": sum(item["status"] == "reliable" for item in checks),
            "issue_count": len(issues),
            "blocking_count": sum(item["blocks_decisions"] for item in checks),
        },
    }


class DashboardClient:
    def __init__(self, base_url: str, username: str, password: str, timeout_seconds: float = 12.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        self.headers = {"Accept": "application/json", "Authorization": f"Basic {token}"}

    def get(self, endpoint: str) -> dict[str, Any]:
        request = urllib.request.Request(f"{self.base_url}{endpoint}", headers=self.headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise RuntimeError(f"dashboard_http_{response.status}")
                value = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError(f"dashboard_request_failed:{type(error).__name__}") from error
        if not isinstance(value, dict):
            raise RuntimeError("dashboard_response_invalid")
        return value

    def snapshot(self, pair: str, timeframe: str, limit: int = 40) -> tuple[dict[str, Any], dict[str, str]]:
        encoded_pair = urllib.parse.quote(pair, safe="")
        endpoints = {
            "summary": "/api/summary",
            "registry": "/api/strategy-registry",
            "market": f"/api/market?pair={encoded_pair}&timeframe={urllib.parse.quote(timeframe)}&limit={limit}",
            "alpha": f"/api/alpha-risk?pair={encoded_pair}",
        }
        snapshot: dict[str, Any] = {}
        errors: dict[str, str] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(endpoints)) as executor:
            futures = {executor.submit(self.get, endpoint): name for name, endpoint in endpoints.items()}
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    snapshot[name] = future.result()
                except RuntimeError as error:
                    errors[name] = str(error)
        return snapshot, errors


def run_systemctl(*args: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["systemctl", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, type(error).__name__
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    return result.returncode == 0, (detail[-1][:240] if detail else f"exit_{result.returncode}")


def repair_record(action: str, reason: str, operation: Callable[[], tuple[bool, str]]) -> dict[str, Any]:
    started_at = isoformat()
    ok, detail = operation()
    return {
        "action": action,
        "reason": reason,
        "status": "succeeded" if ok else "failed",
        "started_at": started_at,
        "completed_at": isoformat(),
        "detail": detail,
    }


def write_report(report: dict[str, Any], report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=report_dir, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, report_dir / "latest.json")
    with (report_dir / "history.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n")


def build_report(
    client: DashboardClient,
    *,
    repair: bool,
    report_dir: Path,
    pair: str,
    timeframe: str,
    dashboard_unit: str,
    refresh_unit: str,
) -> dict[str, Any]:
    repairs: list[dict[str, Any]] = []
    snapshot, probe_errors = client.snapshot(pair, timeframe)

    if repair and ("summary" in probe_errors or "registry" in probe_errors):
        repairs.append(repair_record(
            "restart_dashboard_data_service",
            "Dashboard control endpoints were unavailable.",
            lambda: run_systemctl("restart", dashboard_unit),
        ))
        if repairs[-1]["status"] == "succeeded":
            snapshot, probe_errors = client.snapshot(pair, timeframe)

    assessment = assess_snapshot(snapshot)
    market_needs_refresh = any(
        item["id"] in {"market.candles", "market.ticker"}
        and item["status"] in {"blocked", "stale", "incomplete"}
        for item in assessment["checks"]
    )
    if repair and market_needs_refresh:
        repairs.append(repair_record(
            "refresh_market_data",
            "Market candle or ticker data failed its reliability contract.",
            lambda: run_systemctl("start", refresh_unit),
        ))
        if repairs[-1]["status"] == "succeeded":
            refreshed, refreshed_errors = client.snapshot(pair, timeframe)
            snapshot = refreshed
            probe_errors = refreshed_errors
            assessment = assess_snapshot(snapshot)

    checked_at = isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "checked_at": checked_at,
        **assessment,
        "repairs": repairs,
        "probe_errors": probe_errors,
        "sources": {
            "dashboard_base_url": client.base_url,
            "pair": pair,
            "timeframe": timeframe,
            "report_file": str(report_dir / "latest.json"),
        },
        "repair_policy": {
            "allowed": ["restart_dashboard_data_service", "refresh_market_data"],
            "forbidden": ["manage_trading_bots", "rebuild_database", "delete_data", "modify_strategy"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("DATA_RELIABILITY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--report-dir", type=Path, default=Path(os.environ.get("DATA_RELIABILITY_REPORT_DIR", DEFAULT_REPORT_DIR)))
    parser.add_argument("--pair", default=os.environ.get("DATA_RELIABILITY_PAIR", DEFAULT_PAIR))
    parser.add_argument("--timeframe", default=os.environ.get("DATA_RELIABILITY_TIMEFRAME", DEFAULT_TIMEFRAME))
    parser.add_argument("--dashboard-unit", default="freqtrade-monitor.service")
    parser.add_argument("--refresh-unit", default="freqtrade-v1130-market-data-refresh.service")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when the decision circuit breaker is open.")
    args = parser.parse_args()

    username = os.environ.get("DASHBOARD_USER", "paodingo")
    password = os.environ.get("DASHBOARD_PASSWORD", "")
    if not password:
        raise SystemExit("DASHBOARD_PASSWORD is required")

    client = DashboardClient(args.base_url, username, password)
    report = build_report(
        client,
        repair=args.repair,
        report_dir=args.report_dir,
        pair=args.pair,
        timeframe=args.timeframe,
        dashboard_unit=args.dashboard_unit,
        refresh_unit=args.refresh_unit,
    )
    write_report(report, args.report_dir)
    print(json.dumps({
        "checked_at": report["checked_at"],
        "overall_status": report["overall_status"],
        "decision_allowed": report["decision_allowed"],
        "issue_count": report["summary"]["issue_count"],
        "repair_count": len(report["repairs"]),
    }, ensure_ascii=False))
    return 1 if args.strict and not report["decision_allowed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
