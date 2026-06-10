#!/usr/bin/env python3
"""Generate the Chinese V6.6 alpha-family backtest report."""

from __future__ import annotations

import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_FILE = ROOT / "docs" / "backtests" / "2026-06-11-v66-alpha-family-30d.summary.json"
OUT_FILE = ROOT / "docs" / "backtests" / "2026-06-11-v66-alpha-family-30d.zh.html"


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def num(value, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.{digits}f}"


def signed(value, digits: int = 2) -> str:
    if value is None:
        return "-"
    number = float(value)
    prefix = "+" if number > 0 else ""
    return f"{prefix}{number:,.{digits}f}"


def money(value) -> str:
    return f"{signed(value)} USDT"


def pct(value, digits: int = 2) -> str:
    return f"{signed(value, digits)}%"


def winrate(value) -> str:
    return f"{num(value, 1)}%"


def css_class(value) -> str:
    number = float(value or 0)
    if number > 0:
        return "pos"
    if number < 0:
        return "neg"
    return "neu"


def short_date(value: str) -> str:
    if "/" in value:
        day, month, *_ = value.split("/")
        return f"{month}-{day}"
    return value


def bar(value, max_value, kind: str = "profit") -> str:
    max_value = max(float(max_value or 1), 1)
    width = max(2, round(abs(float(value or 0)) / max_value * 100))
    return f'<span class="bar {kind} {css_class(value)}"><i style="width:{width}%"></i></span>'


def render_metric_cards(strategies, best, max_abs_profit) -> str:
    cards = []
    for index, strategy in enumerate(strategies, start=1):
        winner = " winner" if strategy["id"] == best["id"] else ""
        cards.append(f"""
        <article class="metric-card{winner}">
          <div class="rank">#{index}</div>
          <h3>{esc(strategy['name'])}</h3>
          <p class="strategy-code">{esc(strategy['strategy'])}</p>
          <strong class="metric-value {css_class(strategy['profit_abs'])}">{money(strategy['profit_abs'])}</strong>
          <div class="mini-grid">
            <span>胜率 <b>{winrate(strategy['winrate'])}</b></span>
            <span>交易 <b>{strategy['total_trades']}</b></span>
            <span>PF <b>{num(strategy['profit_factor'])}</b></span>
            <span>回撤 <b>{num(strategy['max_drawdown_abs'])}</b></span>
          </div>
          {bar(strategy['profit_abs'], max_abs_profit)}
        </article>
        """)
    return "\n".join(cards)


def render_summary_table(strategies) -> str:
    rows = []
    for index, strategy in enumerate(sorted(strategies, key=lambda item: item["profit_abs"], reverse=True), start=1):
        rows.append(f"""
        <tr>
          <td>{index}</td>
          <td><strong>{esc(strategy['name'])}</strong><br><span class="muted">{esc(strategy['strategy'])}</span></td>
          <td class="num {css_class(strategy['profit_abs'])}">{money(strategy['profit_abs'])}</td>
          <td class="num {css_class(strategy['profit_pct'])}">{pct(strategy['profit_pct'])}</td>
          <td class="num">{num(strategy['final_balance'])}</td>
          <td class="num">{strategy['total_trades']}</td>
          <td class="num">{winrate(strategy['winrate'])}</td>
          <td class="num">{num(strategy['profit_factor'])}</td>
          <td class="num neg">{num(strategy['max_drawdown_abs'])} / {num(strategy['max_drawdown_pct'])}%</td>
          <td class="num">{strategy['long_trades']} / {strategy['short_trades']}</td>
          <td class="num pos">{money(strategy['avg_win_abs'])}</td>
          <td class="num neg">{money(strategy['avg_loss_abs'])}</td>
          <td class="num">{num(strategy['payoff_loss_to_win'])}</td>
        </tr>
        """)
    return f"""
    <table>
      <thead><tr>
        <th>排名</th><th>策略</th><th>收益</th><th>收益率</th><th>最终余额</th><th>交易</th><th>胜率</th><th>PF</th><th>最大回撤</th><th>多/空</th><th>平均盈利</th><th>平均亏损</th><th>亏/盈倍数</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def render_winner_count(summary, strategies_by_id, period: str, title: str) -> str:
    counts = summary["periods"][period]["winner_counts"]
    total = max(sum(counts.values()), 1)
    rows = []
    for strategy_id, strategy in strategies_by_id.items():
        count = counts.get(strategy_id, 0)
        rows.append(f"""
        <div class="count-row">
          <span>{esc(strategy['name'])}</span><b>{count}</b>{bar(count, total, 'count')}
        </div>
        """)
    return f'<article class="panel small"><h3>{esc(title)}</h3><div class="count-list">{"".join(rows)}</div></article>'


def render_period_table(summary, strategies_by_id, period: str, title: str) -> str:
    ids = list(strategies_by_id.keys())
    rows = []
    for item in summary["periods"][period]["rows"]:
        values = item["values"]
        cells = []
        for strategy_id in ids:
            value = values.get(strategy_id, {"profit_abs": 0, "trades": 0})
            cells.append(
                f'<td class="num {css_class(value["profit_abs"])}">{signed(value["profit_abs"])}'
                f'<br><span class="muted">{value["trades"]} 笔</span></td>'
            )
        rows.append(f"""
        <tr>
          <td>{esc(short_date(item['date']))}</td>
          {''.join(cells)}
          <td><strong>{esc(item['best_name'])}</strong><br><span class="{css_class(item['best_profit_abs'])}">{money(item['best_profit_abs'])}</span></td>
        </tr>
        """)
    headers = "".join(f"<th>{esc(strategy['name'])}</th>" for strategy in strategies_by_id.values())
    return f"""
    <section class="section">
      <div class="section-head"><h2>{esc(title)}</h2><p>按该周期内绝对收益比较，收益最高者标记为胜出。</p></div>
      <div class="table-wrap">
        <table class="period-table"><thead><tr><th>周期</th>{headers}<th>胜出</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
      </div>
    </section>
    """


def render_breakdown(strategies, field: str, title: str) -> str:
    cards = []
    for strategy in strategies:
        rows = []
        items = [
            item for item in strategy.get(field, [])
            if item.get("key") != "TOTAL"
        ]
        items.sort(key=lambda item: abs(float(item.get("profit_abs") or 0)), reverse=True)
        for item in items:
            raw_winrate = item.get("winrate")
            item_winrate = "-" if raw_winrate is None else winrate(float(raw_winrate) * 100)
            rows.append(f"""
            <tr>
              <td>{esc(item.get('key'))}</td>
              <td class="num">{item.get('trades')}</td>
              <td class="num {css_class(item.get('profit_abs'))}">{money(item.get('profit_abs'))}</td>
              <td class="num">{item_winrate}</td>
              <td class="num">{num(item.get('profit_factor'))}</td>
            </tr>
            """)
        cards.append(f"""
        <article class="panel breakdown">
          <h3>{esc(strategy['name'])}</h3>
          <table><thead><tr><th>项目</th><th>笔数</th><th>收益</th><th>胜率</th><th>PF</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
        </article>
        """)
    return f"""
    <section class="section">
      <div class="section-head"><h2>{esc(title)}</h2><p>只展示非 TOTAL 项；收益为该标签或退出原因在 30 天内的合计。</p></div>
      <div class="breakdown-grid">{''.join(cards)}</div>
    </section>
    """


def main() -> None:
    summary = json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))
    strategies = summary["strategies"]
    strategies_by_id = {strategy["id"]: strategy for strategy in strategies}
    best = max(strategies, key=lambda item: item["profit_abs"])
    max_abs_profit = max(abs(strategy["profit_abs"]) for strategy in strategies)

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>V6.6 Alpha 家族 30 天回测报告</title>
<style>
:root {{ color-scheme: light; --ink:#17202a; --muted:#627084; --line:#d8dee8; --panel:#ffffff; --bg:#f4f6f9; --soft:#eef2f7; --pos:#147d4f; --neg:#bd3b35; --neu:#566170; --accent:#22577a; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Microsoft YaHei", "Segoe UI", sans-serif; line-height:1.55; }}
main {{ max-width:1440px; margin:0 auto; padding:28px 28px 56px; }}
header {{ display:grid; grid-template-columns:1.4fr .8fr; gap:24px; align-items:end; border-bottom:1px solid var(--line); padding-bottom:22px; }}
h1 {{ font-size:34px; line-height:1.15; margin:0 0 12px; letter-spacing:0; }}
p {{ margin:0; color:var(--muted); }}
.badges {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }}
.badge {{ border:1px solid var(--line); background:var(--panel); padding:6px 10px; border-radius:6px; color:var(--muted); font-size:13px; }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; margin:24px 0; }}
.metric-card, .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }}
.metric-card {{ position:relative; min-height:202px; }}
.metric-card.winner {{ border-color:#86b69b; box-shadow:0 0 0 2px rgba(20,125,79,.08); }}
.rank {{ position:absolute; right:14px; top:12px; color:var(--muted); font-weight:700; }}
h2 {{ font-size:22px; margin:0; }}
h3 {{ font-size:16px; margin:0 0 4px; }}
.strategy-code, .muted {{ color:var(--muted); font-size:12px; }}
.metric-value {{ display:block; font-size:28px; margin:16px 0 14px; }}
.mini-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px 10px; font-size:13px; color:var(--muted); }}
.mini-grid b {{ color:var(--ink); }}
.pos {{ color:var(--pos); }} .neg {{ color:var(--neg); }} .neu {{ color:var(--neu); }}
.bar {{ display:block; height:7px; background:var(--soft); border-radius:999px; overflow:hidden; margin-top:10px; }}
.bar i {{ display:block; height:100%; background:var(--neu); }}
.bar.pos i {{ background:var(--pos); }} .bar.neg i {{ background:var(--neg); }} .bar.count i {{ background:var(--accent); }}
.section {{ margin-top:28px; }}
.section-head {{ display:flex; justify-content:space-between; gap:20px; align-items:end; margin-bottom:12px; }}
.section-head p {{ max-width:720px; text-align:right; }}
.table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:8px; background:var(--panel); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ padding:10px 11px; border-bottom:1px solid var(--line); vertical-align:top; text-align:left; }}
th {{ background:#e9eef5; color:#344255; font-weight:700; white-space:nowrap; }}
tr:last-child td {{ border-bottom:0; }}
.num {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }}
.insight-grid {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; margin-top:18px; }}
.insight-grid .panel {{ min-height:164px; }}
.big {{ font-size:24px; font-weight:800; margin:10px 0 6px; display:block; }}
.count-grid {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; margin-top:16px; }}
.count-row {{ display:grid; grid-template-columns:1fr 34px; gap:8px; align-items:center; margin:10px 0; font-size:13px; }}
.count-row .bar {{ grid-column:1 / -1; margin-top:0; }}
.breakdown-grid {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:14px; }}
.period-table th, .period-table td {{ min-width:132px; }}
.callout {{ border-left:4px solid var(--accent); background:#edf4f8; padding:14px 16px; border-radius:6px; margin-top:18px; }}
footer {{ color:var(--muted); font-size:12px; margin-top:28px; border-top:1px solid var(--line); padding-top:16px; }}
@media (max-width:980px) {{ header, .kpi-grid, .insight-grid, .count-grid, .breakdown-grid {{ grid-template-columns:1fr; }} .badges {{ justify-content:flex-start; }} .section-head {{ display:block; }} .section-head p {{ text-align:left; margin-top:6px; }} main {{ padding:18px; }} }}
</style>
</head>
<body>
<main>
<header>
  <div>
    <h1>V6.6 Alpha 家族 30 天回测报告</h1>
    <p>对比现有 V6.6 Alpha level、V6.6.1 Alpha、V6.6.2 Alpha、V6.7 Alpha。所有候选都使用 Alpha level 风险过滤，回测窗口与 Alpha 覆盖窗口对齐。</p>
  </div>
  <div class="badges">
    <span class="badge">回测：{esc(summary['timerange'])}</span>
    <span class="badge">Alpha：{esc(summary['alpha_range'])}</span>
    <span class="badge">BTC/USDT:USDT · 15m · dry-run 10000 USDT</span>
  </div>
</header>

<section class="kpi-grid">{render_metric_cards(strategies, best, max_abs_profit)}</section>

<section class="section">
  <div class="section-head"><h2>核心结论</h2><p>30 天窗口里，旧的 V6.6 Alpha level 仍然是唯一盈利策略。</p></div>
  <div class="insight-grid">
    <article class="panel"><h3>总冠军</h3><span class="big pos">{esc(best['name'])}</span><p>收益 {money(best['profit_abs'])}，胜率 {winrate(best['winrate'])}，最大回撤 {num(best['max_drawdown_abs'])} USDT。</p></article>
    <article class="panel"><h3>新版本结论</h3><span class="big neg">没有打过基准</span><p>V6.6.1 的趋势做空收紧过度，胜率从 78.8% 降到 49.2%；V6.6.2 只是把 V6.6.1 的亏损放大。</p></article>
    <article class="panel"><h3>相对稳健候选</h3><span class="big neg">V6.7 亏损较小</span><p>V6.7 把交易压到 36 笔，回撤低于 V6.6.1/2，但仍亏 {money(strategies_by_id['v67_alpha']['profit_abs'])}，不能替换现有 V6.6 Alpha。</p></article>
  </div>
  <div class="callout"><strong>操作建议：</strong>继续保留 V6.6 Alpha level 作为挑战者；V6.6.1/V6.6.2/V6.7 这轮参数不要上线。下一轮优化应保留 V6.6 Alpha 的趋势做空主体，只针对亏损的箱体多单和少数 stop_loss 做微调。</div>
</section>

<section class="section"><div class="section-head"><h2>总体排名</h2><p>收益、回撤、胜率和盈亏结构放在同一张表里看。</p></div><div class="table-wrap">{render_summary_table(strategies)}</div></section>

<section class="section"><div class="section-head"><h2>哪个时间段谁更优</h2><p>月度全部由 V6.6 Alpha level 胜出；周度 5 个窗口里 V6.6 Alpha level 赢 3 个。</p></div><div class="count-grid">{render_winner_count(summary, strategies_by_id, 'day', '按日')}{render_winner_count(summary, strategies_by_id, 'week', '按周')}{render_winner_count(summary, strategies_by_id, 'month', '按月')}</div></section>

{render_period_table(summary, strategies_by_id, 'month', '月度胜负')}
{render_period_table(summary, strategies_by_id, 'week', '周度胜负')}
{render_period_table(summary, strategies_by_id, 'day', '日度胜负明细')}
{render_breakdown(strategies, 'enter_tags', '入场标签拆解')}
{render_breakdown(strategies, 'exit_reasons', '退出原因拆解')}

<footer>
  生成时间：{esc(summary['generated_at'])}。服务器原始结果目录：{esc(summary['source_dir'])}。本报告使用 Freqtrade 回测导出的 zip JSON 生成；未使用未来数据。注意：30 天样本仍然偏短，不代表实盘保证收益。
</footer>
</main>
</body>
</html>"""
    OUT_FILE.write_text(html_doc, encoding="utf-8")
    print(OUT_FILE)


if __name__ == "__main__":
    main()
