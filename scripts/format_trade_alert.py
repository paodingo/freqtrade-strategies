#!/usr/bin/env python3
"""Format trade-monitor events as concise Simplified Chinese notifications."""
from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation


SIGNAL_TEXT = {
    "trending_long": "趋势做多",
    "trending_short": "趋势做空",
    "v102_trending_short_core": "趋势空单核心信号",
    "v1130_crash_rebound_long": "V11.30 暴跌反弹做多",
}

EXIT_TEXT = {
    "stop_loss": "止损",
    "trailing_stop_loss": "移动止损",
    "roi": "达到收益目标",
    "exit_signal": "策略退出信号",
    "force_exit": "人工强制退出",
    "v1130_rebound_time_exit": "V11.30 反弹持仓超时退出",
}


def as_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def number(value, suffix: str = "", signed: bool = False) -> str:
    value_decimal = as_decimal(value)
    if value_decimal is None:
        return "-"
    prefix = "+" if signed and value_decimal > 0 else ""
    return f"{prefix}{value_decimal:,.2f}{suffix}"


def percent(value) -> str:
    value_decimal = as_decimal(value)
    if value_decimal is None:
        return "-"
    # Freqtrade stores close_profit as a ratio, while API profit_pct is percent.
    if abs(value_decimal) <= Decimal("2"):
        value_decimal *= 100
    return number(value_decimal, "%", signed=True)


def direction(is_short) -> str:
    return "做空" if bool(is_short) else "做多"


def reason(value, mapping: dict[str, str]) -> str:
    raw = value or "-"
    translated = mapping.get(raw)
    return f"{translated}（{raw}）" if translated else str(raw)


def counts(event: dict) -> str:
    return f"持仓 {event.get('open', 0)} / 累计 {event.get('total', 0)} / 已平 {event.get('closed', 0)}"


def format_new_open(event: dict) -> str:
    trade = event.get("trade") or {}
    lines = [
        f"[{event.get('label', '-')}] 新开仓",
        f"交易：{direction(trade.get('is_short'))} {trade.get('pair', '-')}",
        f"入场理由：{reason(trade.get('enter_tag'), SIGNAL_TEXT)}",
        f"开仓价：{number(trade.get('open_rate'))}",
        f"投入：{number(trade.get('stake_amount'), ' USDT')}",
        f"杠杆：{number(trade.get('leverage'), 'x')}",
        f"时间：{trade.get('open_date') or '-'}",
        f"统计：{counts(event)}",
    ]
    return "\n".join(lines)


def format_closed(event: dict) -> str:
    trade = event.get("trade") or {}
    lines = [
        f"[{event.get('label', '-')}] 已平仓",
        f"交易：{direction(trade.get('is_short'))} {trade.get('pair', '-')}",
        f"入场理由：{reason(trade.get('enter_tag'), SIGNAL_TEXT)}",
        f"退出理由：{reason(trade.get('exit_reason'), EXIT_TEXT)}",
        f"价格：{number(trade.get('open_rate'))} → {number(trade.get('close_rate'))}",
        f"实际盈亏：{number(trade.get('profit_abs'), ' USDT', signed=True)}（{percent(trade.get('profit_ratio'))}）",
        f"持仓时长：{trade.get('trade_duration') or '-'} 分钟",
        f"时间：{trade.get('close_date') or '-'}",
        f"统计：{counts(event)}",
    ]
    return "\n".join(lines)


def format_source_error(event: dict) -> str:
    return (
        f"[{event.get('label', '-')}] 交易数据连续读取失败\n"
        f"来源：{event.get('source', '-')}\n"
        f"连续失败：{event.get('failures', '-')} 次\n"
        f"错误：{event.get('error', '-')}"
    )


FORMATTERS = {
    "new_open": format_new_open,
    "closed": format_closed,
    "source_error": format_source_error,
}


def format_event(event: dict) -> str:
    formatter = FORMATTERS.get(event.get("type"))
    return formatter(event) if formatter else str(event.get("message", ""))


def main() -> int:
    payload = sys.stdin.read().strip()
    if not payload:
        return 0
    message = format_event(json.loads(payload))
    if message:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
