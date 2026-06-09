#!/usr/bin/env python3
"""Format trade-monitor events for human-readable Telegram messages."""
from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation


SIGNAL_TEXT = {
    "trending_long": "趋势做多",
    "trending_short": "趋势做空",
    "ranging_long": "震荡做多",
    "ranging_short": "震荡做空",
}


def as_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def money(value, suffix: str = "") -> str:
    number = as_decimal(value)
    if number is None:
        return "-"
    text = f"{number:,.2f}"
    if number > 0:
        text = f"+{text}"
    return f"{text}{suffix}"


def plain_number(value) -> str:
    number = as_decimal(value)
    if number is None:
        return "-"
    return f"{number:,.2f}"


def direction_text(is_short) -> str:
    return "做空" if bool(is_short) else "做多"


def signal_text(signal: str | None) -> str:
    return SIGNAL_TEXT.get(signal or "", signal or "-")


def format_new_open(event: dict) -> str:
    trade = event.get("trade") or {}
    label = event.get("label", "-")
    pair = trade.get("pair", "-")
    lines = [
        f"[{label}] 新开仓",
        f"方向：{direction_text(trade.get('is_short'))} {pair}",
        f"信号：{signal_text(trade.get('enter_tag'))}",
        f"开仓价：{plain_number(trade.get('open_rate'))}",
        f"现价：{plain_number(trade.get('current_rate'))}",
        f"投入：{plain_number(trade.get('stake_amount'))} USDT",
        f"浮盈：{money(trade.get('profit_abs'), ' USDT')}",
        format_counts(event),
        f"累计收益：{money(event.get('profit_all_coin'), ' USDT')}",
    ]
    latest = event.get("latest_trade_date")
    if latest:
        lines.append(f"最近交易：{latest}")
    return "\n".join(lines)


def format_counts(event: dict) -> str:
    return (
        "统计："
        f"持仓 {event.get('open', 0)} / "
        f"累计 {event.get('total', 0)} / "
        f"已平 {event.get('closed', 0)}"
    )


def format_closed(event: dict) -> str:
    label = event.get("label", "-")
    count = event.get("closed_delta", 0)
    lines = [
        f"[{label}] 有平仓",
        f"本次平仓：{count} 笔",
        format_counts(event),
        f"累计收益：{money(event.get('profit_all_coin'), ' USDT')}",
    ]
    latest = event.get("latest_trade_date")
    if latest:
        lines.append(f"最近交易：{latest}")
    return "\n".join(lines)


def format_count_change(event: dict) -> str:
    label = event.get("label", "-")
    lines = [
        f"[{label}] 交易数量变化",
        format_counts(event),
        f"累计收益：{money(event.get('profit_all_coin'), ' USDT')}",
    ]
    latest = event.get("latest_trade_date")
    if latest:
        lines.append(f"最近交易：{latest}")
    return "\n".join(lines)


def format_api_recovered(event: dict) -> str:
    return (
        f"[{event.get('label', '-')}] API 已恢复\n"
        f"状态：{event.get('state', '-')} / {event.get('runmode', '-')}\n"
        f"策略：{event.get('strategy', '-')}"
    )


def format_api_error(event: dict) -> str:
    return (
        f"[{event.get('label', '-')}] API 异常\n"
        f"端口：localhost:{event.get('port', '-')}\n"
        "说明：无法完整读取 bot 状态，请检查容器/API。"
    )


def format_bot_state(event: dict) -> str:
    return (
        f"[{event.get('label', '-')}] Bot 状态变化\n"
        f"状态：{event.get('state', '-')}\n"
        "说明：当前可能无法正常交易，请检查。"
    )


FORMATTERS = {
    "new_open": format_new_open,
    "closed": format_closed,
    "count_change": format_count_change,
    "api_recovered": format_api_recovered,
    "api_error": format_api_error,
    "bot_state": format_bot_state,
}


def format_event(event: dict) -> str:
    event_type = event.get("type")
    formatter = FORMATTERS.get(event_type)
    if formatter is None:
        return event.get("message", "")
    return formatter(event)


def main() -> int:
    payload = sys.stdin.read().strip()
    if not payload:
        return 0
    event = json.loads(payload)
    message = format_event(event)
    if message:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
