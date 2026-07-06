# Task 55: V11.29 Live Signal Miss Root-Cause Audit

## Summary

本任务对 2026-07-07 凌晨服务器上 V11.29 在大幅波动行情中仍然没有产生 trades/orders 的情况做只读根因审计。

结论：当前现象不是 dashboard 展示错误，也不是 bot 完全停机。`freqtrade-v1129` 正在 `running / dry_run / futures / 15m` 状态下运行，余额、pairlist、locks 均未显示硬阻断；但 SQLite 与 API 均证明 `trades=0`、`orders=0`。最近 96 根 15m K 线中，12 个 pair 的 `enter_long_rows=0`、`enter_short_rows=0`。主要原因是：

- V11.29 long 方向被 `alpha_filter_block_long` 全面阻断，最新主要 flag 为 `topTraderAccountLongCrowding`。
- V11.29 主策略 short 条件过严，尤其 `adx_4h < 22`、`close < ema200`、`bb_percent > 0.80`、`rsi > 60`、ranging regime 等条件未同时满足。
- V11.29 shadow short lane 启动时间较晚，且只覆盖 5 个 pair；启动前已出现部分 `shadow_core` 候选窗口，启动后尚未满足完整入场条件。
- 主 V11.29 近期日志曾出现 Binance `exchangeInfo` `RequestTimeout`，但后续 heartbeat 仍为 `RUNNING`；该异常不能解释全部 0 orders，但说明运行链路存在外部 API 抖动风险。

这说明当前 V11.29 对暴跌暴涨行情的响应能力不足，不能作为“已验证可替代 V10.8.2”的策略继续推进。需要快速进入下一代策略候选搜索与事件回放验证。

## Scope And Boundaries

本任务只读检查服务器与 clean worktree 中的现有证据。

已执行：

- 只读检查本地分支、commit、`git status --short --untracked-files=all`。
- 运行 `.\scripts\run_agent_readiness_checks.ps1`。
- 只读 SSH 检查服务器容器状态、SQLite schema/count、Freqtrade API 状态、recent dataframe signals、相关策略过滤代码。

未执行：

- 未修改策略。
- 未修改 bot 配置。
- 未读取 `.env`、`user_data/monitor.env`、API key、交易所凭证、dashboard 密码或服务器密钥内容。
- 未启动、停止、重启任何 bot。
- 未运行回测。
- 未登录交易所或执行交易。

## Server Runtime Evidence

服务器容器状态只读观察：

| Component | Evidence |
|---|---|
| `freqtrade-v1129` | `Up 3 days`，API 暴露 `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1129-ranging-short-shadow` | `Up 29 minutes` |
| `freqtrade-v1082` | `Exited (137)` |
| Server memory | `1.9Gi` total，约 `1.6Gi` used，`180Mi` free，swap 使用约 `2.5Gi / 5.9Gi` |
| `freqtrade-v1129` stats | CPU 约 `10.58%`，memory 约 `271.7MiB` |
| shadow stats | CPU 约 `0.00%`，memory 约 `179.2MiB` |

Freqtrade API self-report for `freqtrade-v1129`：

| Field | Observed |
|---|---|
| `state` | `running` |
| `runmode` | `dry_run` |
| `strategy` | `RegimeAwareV1129ResidualDragMicroSizer` |
| `timeframe` | `15m` |
| `max_open_trades` | `4` |
| `/count.current` | `0` |
| `/status` | `[]` |
| `/locks.lock_count` | `0` |
| `/profit.trade_count` | `0` |
| balance | simulated `USDT` available |

因此，本轮不能把 0 trades/orders 归因于 stopped、locks、余额不足或 dashboard 读取失败。

## SQLite Evidence

只读 SQLite 查询结果：

| DB | Path | `trades` | `orders` | Notes |
|---|---|---:|---:|---|
| V11.29 main | `/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129.dryrun.sqlite` | `0` | `0` | 表存在，行数为 0 |
| V11.29 shadow | `/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite` | `0` | `0` | 表存在，行数为 0 |
| V10.8.2 baseline | `/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1082.dryrun.sqlite` | `6` | `12` | 历史 baseline 有闭合交易和订单 |

V11.29 DB 有 `trades`、`orders`、`pairlocks`、`wallet_history` 等表，缺失的不是 schema，而是实际订单/交易样本。

## Live Signal Evidence

对 `freqtrade-v1129` 的 `/api/v1/pair_candles` 做只读检查，最近 96 根 `15m` K 线、12 个 pair：

| Observed Field | Result |
|---|---|
| `rows` | 每 pair 约 `96` |
| latest candle | `2026-07-06T19:30:00Z` |
| `enter_long_rows` | 全部 pair 为 `0` |
| `enter_short_rows` | 全部 pair 为 `0` |
| `alpha_filter_block_long_rows` | 全部 pair 为 `96` |
| `alpha_filter_block_short_rows` | 多数 pair 为 `31` |
| latest `alpha_risk_flags` | `topTraderAccountLongCrowding` |
| `v1129_residual_drag_gate` | 多数显示 `pass`，但 entry 仍为 0 |

典型最新样本：

| Pair | Latest close | `alpha_filter_block_long` | `alpha_filter_block_short` | `enter_long` | `enter_short` | Notes |
|---|---:|---|---|---:|---:|---|
| BTC/USDT:USDT | `63819.7` | `true` | `false` | `0` | `0` | `topTraderAccountLongCrowding` |
| ETH/USDT:USDT | `1795.26` | `true` | `false` | `0` | `0` | `topTraderAccountLongCrowding` |
| SOL/USDT:USDT | `82.05` | `true` | `false` | `0` | `0` | `topTraderAccountLongCrowding` |
| XRP/USDT:USDT | `1.1491` | `true` | `false` | `0` | `0` | `enter_tag=trending_long` before filter, but final entry is 0 |

XRP 的样本尤其关键：`enter_tag=trending_long` 仍存在，但 `enter_long=0`，说明 pre-filter 或中间逻辑曾识别 long 形态，最终被 alpha filter 清零。

## Gate-Level Root Cause

代码证据：

- `strategies/alpha_risk_filter.py` 中 `topTraderAccountLongCrowding` 属于 `LONG_HOSTILE_FLAGS`。
- `apply_alpha_filter(..., mode="directional")` 会将包含 long-hostile flags 的样本标记为 `alpha_filter_block_long=true`。
- 随后会执行：`enter_long == 1` 且 `alpha_filter_block_long` 时，将 `enter_long` 置为 `0`。

基础 short 条件来自 `strategies/regime_aware_base.py`：

- `regime_4h == RANGING`
- `ranging_short_setup`
- `close < ema200`
- `volume > 0`

其中 `ranging_short_setup` 还要求：

- `bb_percent > 0.80`
- `rsi > 60`
- `volume > volume_mean * 0.8`
- `bb_width_4h < bb_width_mean_4h * 1.3`
- `adx_4h < 22`

实时 gate 分解显示：

| Condition | Result Pattern |
|---|---|
| `alpha_long_allows` | 12 个 pair 最近 96 根均为 `0` |
| `adx_lt_22` | 12 个 pair 最近 96 根均为 `0` |
| `bbp_gt_080` / `rsi_gt_60` | 有部分窗口满足 |
| `shadow_core` | BTC/SOL/DOGE/LINK/AVAX 曾出现少量候选 |
| `base_ranging_short` | 全部为 `0` |

因此，当前无交易的直接根因不是“行情没波动”，而是：

1. long 路径被 alpha crowding 风险全面防守；
2. short 路径对高波动行情的 ADX/EMA/range 条件过窄；
3. V11.29 不具备有效的 crash/rebound 或 momentum continuation 执行 arm；
4. shadow lane 是后补观察通道，不是完整替代策略，启动时间与覆盖面都不足。

## Runtime Quality Risk

日志中还发现：

```text
ccxt.base.errors.RequestTimeout: binance GET https://fapi.binance.com/fapi/v1/exchangeInfo
freqtrade.exceptions.TemporaryError: Error in reload_markets due to RequestTimeout
```

后续 heartbeat 仍为 `RUNNING`，pairlist 正常刷新，所以它不是 0 orders 的唯一根因。但它说明：

- Binance API 链路存在间歇超时；
- Telegram/API 异常提醒与 dashboard API 抖动可能仍会反复出现；
- 策略验证不能只看 container `Up`，必须看 API、SQLite、signal dataframe、orders 四层证据。

## Assessment

V11.29 当前不能被视为合格的 live execution candidate。

原因不是它“亏钱”，而是更早一层的问题：在强波动窗口中没有产生任何 orders，导致无法验证执行质量、滑点、手续费、胜率、profit factor 或替代价值。

这也意味着继续只围绕 V11.29 小修小补，可能会浪费时间。需要并行或优先启动下一代策略候选搜索，尤其针对：

- 暴跌后的 rebound long；
- 快速拉升后的 short fade；
- 高 ADX 高波动 momentum continuation；
- 15m/1h 多时间框架 breakout；
- 不依赖单一 alpha crowding flag 全局清零的风险模型。

## What This Does Not Conclude

本任务不输出以下结论：

- 不声称 V11.29 策略失败。
- 不声称 V11.29 可以或不可以替换 V10.8.2。
- 不声称 V10.8.2 应恢复运行。
- 不承诺任何策略能在暴跌暴涨行情中稳定赚钱。

但本任务可以明确判断：

- V11.29 当前 live entry 体系对本轮高波动行情响应不足。
- 当前样本不足以证明 V11.29 有真实执行能力。
- 继续推进前必须做事件级 signal miss 审计与下一代候选搜索。

## Recommended Task 56

推荐下一步直接执行：

**Task 56: High-Volatility Strategy Candidate Search Plan**

目标：

1. 使用最近 24h / 72h / 7d 的高波动窗口作为事件集；
2. 只读生成 V11.29 miss matrix：每个 pair、每根 15m K 线、pre-filter signal、alpha block、ADX/EMA/range gate、final entry；
3. 快速筛选下一代候选策略方向；
4. 明确区分：
   - 可以直接用历史数据回放的候选；
   - 需要新增特征的候选；
   - 需要新 shadow lane 的候选；
   - 不应继续投入的 V11.29 变体；
5. 推荐 Task 57：实现最小只读 replay harness 或新 shadow candidate。

优先级：高。

理由：当前 V11.29 在强波动期间 0 orders，已经触发策略替代搜索条件。

