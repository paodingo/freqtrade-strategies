#!/usr/bin/env python3
"""Emit human-readable alerts for trade changes in the runtime registry."""
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from format_trade_alert import format_event


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PROJECT_DIR / "dashboard" / "config" / "strategy-registry.json"
DEFAULT_STATE = PROJECT_DIR / "user_data" / "trade_monitor_state_v2.json"
STATE_SCHEMA = "trade-monitor-state-v2"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path(os.getenv("STRATEGY_REGISTRY_FILE", DEFAULT_REGISTRY)))
    parser.add_argument("--state", type=Path, default=Path(os.getenv("TRADE_MONITOR_STATE_FILE", DEFAULT_STATE)))
    parser.add_argument("--emit-baseline", action="store_true", help="Emit existing trades when creating state")
    return parser.parse_args(argv)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f"{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def first(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return default


def normalize_trade(record: dict[str, Any]) -> dict[str, Any]:
    trade_id = first(record, "trade_id", "id")
    is_open = bool(first(record, "is_open", default=False))
    open_date = first(record, "open_date", "open_date_utc")
    close_date = first(record, "close_date", "close_date_utc")
    return {
        "trade_id": str(trade_id),
        "pair": first(record, "pair", default="-"),
        "is_open": is_open,
        "is_short": bool(first(record, "is_short", default=False)),
        "enter_tag": first(record, "enter_tag", "buy_tag"),
        "exit_reason": first(record, "exit_reason", "sell_reason"),
        "open_rate": first(record, "open_rate"),
        "close_rate": first(record, "close_rate"),
        "current_rate": first(record, "current_rate", "close_rate"),
        "stake_amount": first(record, "stake_amount"),
        "profit_abs": first(record, "realized_profit", "close_profit_abs", "profit_abs"),
        "profit_ratio": first(record, "close_profit", "profit_ratio", "profit_pct"),
        "open_date": open_date,
        "close_date": close_date,
        "trade_duration": first(record, "trade_duration"),
        "leverage": first(record, "leverage"),
        "funding_fees": first(record, "funding_fees"),
        "fee_open_cost": first(record, "fee_open_cost"),
        "fee_close_cost": first(record, "fee_close_cost"),
    }


def fetch_json(url: str, auth: str, timeout: float) -> Any:
    headers = {"Accept": "application/json"}
    if auth:
        token = base64.b64encode(auth.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def read_freqtrade(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    url_config = runtime.get("url") or {}
    base_url = os.getenv(url_config.get("env", ""), url_config.get("default", "")).rstrip("/")
    if not base_url:
        raise RuntimeError("Freqtrade URL is missing")
    auth = os.getenv("FREQTRADE_API_AUTH", "freqtrader:freqtrade")
    timeout = float(os.getenv("TRADE_MONITOR_API_TIMEOUT_SECONDS", "8"))
    payload = fetch_json(f"{base_url}/api/v1/trades?limit=500", auth, timeout)
    records = payload.get("trades", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise RuntimeError("Freqtrade trades response is not a list")
    return [normalize_trade(item) for item in records if isinstance(item, dict)]


def read_sqlite(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    sqlite_config = runtime.get("sqlite") or {}
    raw_path = os.getenv(sqlite_config.get("env", ""), sqlite_config.get("default_relative_path", ""))
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = PROJECT_DIR / db_path
    if not db_path.is_file():
        raise RuntimeError(f"SQLite database not found: {db_path}")
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 500").fetchall()
    finally:
        connection.close()
    return [normalize_trade(dict(row)) for row in rows]


def read_strategy_trades(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    runtime = strategy.get("runtime") or {}
    source = runtime.get("source")
    if source == "freqtrade":
        return read_freqtrade(runtime)
    if source == "sqlite":
        return read_sqlite(runtime)
    raise RuntimeError(f"Unsupported runtime source: {source}")


def display_label(strategy: dict[str, Any]) -> str:
    runtime = strategy.get("runtime") or {}
    env_name = runtime.get("label_env")
    return os.getenv(env_name, strategy.get("display_name", strategy.get("strategy_id", "-"))) if env_name else strategy.get("display_name", "-")


def is_dry_run_strategy(strategy: dict[str, Any]) -> bool:
    runtime = strategy.get("runtime") or {}
    return strategy.get("stage") == "dry_run" and runtime.get("dry_run", True) is not False


def trade_events(label: str, trades: list[dict[str, Any]], previous: dict[str, Any], initialized: bool) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous_trades = previous.get("trades", {}) if isinstance(previous, dict) else {}
    total = len(trades)
    closed = sum(not trade["is_open"] for trade in trades)
    opened = total - closed
    for trade in sorted(trades, key=lambda item: (item.get("open_date") or "", item["trade_id"])):
        old = previous_trades.get(trade["trade_id"])
        if old is None:
            if initialized:
                events.append({
                    "type": "new_open" if trade["is_open"] else "closed",
                    "label": label,
                    "open": opened,
                    "total": total,
                    "closed": closed,
                    "trade": trade,
                })
        elif bool(old.get("is_open")) and not trade["is_open"]:
            events.append({"type": "closed", "label": label, "open": opened, "total": total, "closed": closed, "trade": trade})
    return events


def monitor(registry: dict[str, Any], previous_state: dict[str, Any], emit_baseline: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    was_initialized = previous_state.get("schema") == STATE_SCHEMA
    previous_bots = previous_state.get("bots", {}) if was_initialized else {}
    next_bots: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    for strategy in registry.get("strategies", []):
        if not is_dry_run_strategy(strategy):
            continue
        runtime = strategy.get("runtime") or {}
        bot_key = runtime.get("bot_key") or strategy.get("strategy_id")
        label = display_label(strategy)
        old_bot = previous_bots.get(bot_key, {})
        bot_initialized = was_initialized and isinstance(old_bot.get("trades"), dict)
        try:
            trades = read_strategy_trades(strategy)
            events.extend(trade_events(label, trades, old_bot, bot_initialized or emit_baseline))
            next_bots[bot_key] = {
                "ok": True,
                "label": label,
                "source": runtime.get("source"),
                "trades": {trade["trade_id"]: trade for trade in trades},
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }
        except (OSError, RuntimeError, sqlite3.Error, urllib.error.URLError, json.JSONDecodeError) as exc:
            failures = int(old_bot.get("consecutive_failures", 0)) + 1
            next_bots[bot_key] = {
                **old_bot,
                "ok": False,
                "label": label,
                "source": runtime.get("source"),
                "error": str(exc),
                "consecutive_failures": failures,
                "observed_at": datetime.now(timezone.utc).isoformat(),
            }
            threshold = int(os.getenv("TRADE_MONITOR_FAILURE_ALERT_THRESHOLD", "3"))
            if was_initialized and failures == threshold:
                events.append({"type": "source_error", "label": label, "source": runtime.get("source"), "error": str(exc), "failures": failures})
    return {"schema": STATE_SCHEMA, "bots": next_bots, "updated_at": datetime.now(timezone.utc).isoformat()}, events


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry = load_json(args.registry, {})
    if registry.get("schema_version") != "strategy-registry-v1":
        print(f"TRADE_MONITOR_ERROR: invalid registry: {args.registry}", file=sys.stderr)
        return 2
    previous = load_json(args.state, {})
    next_state, events = monitor(registry, previous, args.emit_baseline)
    atomic_write_json(args.state, next_state)
    messages = [format_event(event) for event in events]
    messages = [message for message in messages if message]
    if messages:
        print("TRADE_ALERT:" + "\n\n".join(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
