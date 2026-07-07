# Task 56: High-Volatility Strategy Candidate Search Plan

## Summary

本任务根据 Task 55 的根因审计，制定下一代高波动策略候选搜索计划。目标不是直接修改 live 策略，而是把最近强波动窗口转化为可回放、可评分、可筛选的候选策略研究任务。

结论：V11.29 当前不应继续作为唯一主线优化对象。只读 live dataframe 统计显示，约 7 天、12 个 pair、7560 根 15m 行中：

| Metric | Count |
|---|---:|
| `final_entry` | `0` |
| `alpha_long_block` | `7224` |
| `alpha_short_block` | `2532` |
| `high_volatility` | `43` |
| `crash_rebound_candidate` | `10` |
| `selloff_continuation_candidate` | `110` |
| `blowoff_short_candidate` | `1064` |
| `shadow_core` | `160` |
| `base_ranging_short` | `1` |
| `high_adx` | `6404` |

这说明市场确实给出了大量高波动候选事件，但 V11.29 的 final entry 完全没有接住。下一步应该启动下一代策略候选搜索，而不是仅放宽某一个阈值后继续盲目观察。

## Scope And Boundaries

本任务只读检查 live API dataframe 与 clean worktree 文档。

已执行：

- 只读调用 `freqtrade-v1129` API 的 `/api/v1/whitelist`。
- 只读调用 `/api/v1/pair_candles`，按 12 个 pair 拉取最近最多 672 根 15m K 线。
- 在临时脚本中计算候选事件统计；临时脚本已删除。
- 新增本审计报告与任务记录。

未执行：

- 未修改策略。
- 未修改 bot 配置。
- 未启动、停止、重启 bot。
- 未运行回测。
- 未读取 secret、`.env`、`user_data/monitor.env`、API key、交易所凭证、dashboard 密码。
- 未登录交易所或执行交易。
- 未进入 live replacement 判断。

## Evidence: Why V11.29 Should Not Be The Only Path

Task 55 已确认：

- V11.29 bot 正在 `running / dry_run / futures / 15m`。
- `locks=0`，模拟余额可用。
- V11.29 main SQLite：`trades=0`、`orders=0`。
- V11.29 shadow SQLite：`trades=0`、`orders=0`。
- 最近窗口中 12 个 pair 的 `enter_long_rows=0`、`enter_short_rows=0`。
- long 方向被 `topTraderAccountLongCrowding` 触发的 `alpha_filter_block_long` 全面阻断。
- short 方向被高 ADX、EMA、ranging 条件等组合限制。

Task 56 的新增统计进一步说明：

- `high_adx=6404`，而当前 base ranging short 依赖低 ADX 条件；
- `blowoff_short_candidate=1064`，但 final entry 仍为 0；
- `selloff_continuation_candidate=110`，但 V11.29 没有高 ADX selloff continuation arm；
- `shadow_core=160`，但 shadow 只做窄观察，且当前未产生 orders；
- `base_ranging_short=1`，说明现有 base short 条件几乎不会触发。

这不是单一 bug，更像策略架构与当前行情形态不匹配。

## Candidate Event Definitions Used In This Audit

本任务中的候选事件只是粗筛，不是交易信号，不用于 live 下单。

| Candidate | Rough Definition |
|---|---|
| `high_volatility` | 15m open-close 绝对变动约 `>= 1.2%` 或 high-low range 约 `>= 2%` |
| `crash_rebound_candidate` | 高波动反弹，15m 收涨、RSI 中低位、成交量不低 |
| `selloff_continuation_candidate` | 15m 明显下跌、4h ADX 高、成交量不低 |
| `blowoff_short_candidate` | `bb_percent` 高、RSI 高、24h range 上沿、成交量不低 |
| `shadow_core` | 接近当前 shadow ranging short 的宽松核心条件 |
| `base_ranging_short` | 当前 base strategy 的原始 ranging short 条件 |

这些定义只用于决定下一步研究方向。它们必须通过历史 replay、费用/滑点模型、样本外窗口和 dry-run shadow 才能进入策略实现。

## Candidate Search Direction

### 1. High-ADX Selloff Continuation Short

优先级：最高。

理由：

- 7 天粗筛中 `selloff_continuation_candidate=110`。
- 当前 V11.29 的 base ranging short 依赖低 ADX，因此天然错过高 ADX selloff。
- 暴跌行情中，这类 arm 比等待 ranging reversal 更直接。

下一步要验证：

- 触发后 1 / 2 / 4 / 8 根 15m K 线 forward return；
- 是否需要只做 short，还是允许 crash rebound long；
- 是否需要限制在 BTC/ETH/SOL/ADA/BCH 等高波动 pair；
- fee、funding、slippage 后是否仍有边际。

### 2. Blowoff Short / Exhaustion Fade

优先级：高，但需要严格过滤。

理由：

- 粗筛 `blowoff_short_candidate=1064`，说明候选很多。
- 如果直接使用会过度交易，必须二次筛选。
- 当前 V11.29 记录中多处 `enter_tag` 仍出现 `v66_ranging_short_edge` 或 `trending_long`，但 final entry 被清零，说明中间层曾识别形态。

下一步要验证：

- 哪些 blowoff 候选后续真的回落；
- 是否需要加入成交量冲顶、upper wick、funding/crowding 反向解释；
- 是否必须排除强趋势继续上涨场景；
- 是否能作为 shadow lane，而不是直接主策略。

### 3. Crash Rebound Long

优先级：中。

理由：

- 粗筛 `crash_rebound_candidate=10`，样本少但可能价值高。
- 当前 long 方向被 `topTraderAccountLongCrowding` 几乎全局挡掉；如果 alpha risk filter 只做 hard block，会错过所有反弹。

下一步要验证：

- alpha crowding 是否应该从 hard block 改为 sizing / cooldown / confirmation；
- 反弹 long 是否需要更高胜率、更小仓位、更短持仓；
- 是否必须要求 BTC/ETH 同步回稳。

### 4. Alpha Filter Re-Architecture

优先级：高，作为策略基础设施任务。

理由：

- `alpha_long_block=7224 / 7560`，几乎等于全局关停 long。
- 当前 filter 对 long 是二元 hard block；这对风险防守有价值，但会导致大多数行情完全无交易。

下一步要验证：

- `topTraderAccountLongCrowding` 是否总是 long-hostile；
- 是否需要按 regime 区分：trend continuation、crash rebound、range fade；
- 是否从 hard block 改成 stake sizing、confirmation requirement、cooldown 或 max exposure cap；
- 是否需要单独记录 pre-filter signal，而不是只看 final entry。

## Recommended Immediate Path

推荐下一步不要直接改 live 策略，而是走三步：

1. **Task 57: High-Volatility Replay Harness**
   - 读取现有 analyzed dataframe / candles；
   - 对上述 candidate definitions 做 forward-return replay；
   - 输出 JSON/Markdown candidate scorecard；
   - 不修改策略，不启动 bot。

2. **Task 58: V11.30 Candidate Selection**
   - 根据 Task 57 的 replay 结果选 1 个主候选；
   - 明确 strategy arm、pairlist、risk sizing、entry/exit、禁止条件；
   - 决定是否新建 V11.30 strategy 或只做 shadow lane。

3. **Task 59: V11.30 Shadow Implementation Plan**
   - 只在候选有正向 replay 证据后，才授权策略/配置改动；
   - 使用小仓位 dry-run shadow；
   - 必须输出 signal telemetry 和 order/trade evidence。

## Do Not Do Yet

当前阶段不建议：

- 直接放宽 V11.29 的 `adx_4h < 22`。
- 直接移除 `alpha_filter_block_long`。
- 直接把 shadow lane 扩成主策略。
- 直接恢复 V10.8.2 作为替代结论。
- 直接运行 live 真实交易。
- 只看 dashboard 颜色或 PnL 卡片做策略判断。

原因：我们已经证明 V11.29 不出手，但还没有证明哪一种替代逻辑能赚钱。下一步必须通过 replay 验证候选。

## Task 57 Recommendation

推荐执行：

**Task 57: High-Volatility Replay Harness**

允许目标：

- 新增只读 replay 脚本；
- 读取 live API/analyzed dataframe 或服务器 candle 文件；
- 生成候选策略 forward-return scorecard；
- 输出每个 candidate 的样本数、平均 forward return、中位数、胜率、最大不利波动、pair 分布、时间窗口分布。

禁止目标：

- 不修改策略；
- 不修改 bot 配置；
- 不启动/停止 bot；
- 不运行 live trade；
- 不声称新策略已经可用。

Task 57 的成功标准：

- 能明确回答：`selloff_continuation`、`blowoff_short`、`crash_rebound` 中哪个最值得进入 V11.30。
- 如果三个都不行，立即转向外部策略搜索，不继续堆 V11.29 变体。

