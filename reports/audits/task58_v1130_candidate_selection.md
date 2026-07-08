# Task 58: V11.30 Candidate Selection

## Summary

本任务基于 Task 57 high-volatility replay scorecard，选择是否进入 V11.30 候选策略设计。当前阶段仍然只读分析，不修改策略、不修改 bot 配置、不启动新 bot、不进入 live。

结论：选择 **V11.30 Crash Rebound Long Shadow** 作为下一步候选，但只允许进入 Task 59 的 shadow implementation plan，不允许直接修改 live 主策略或启用真实交易。

理由：

- Task 57 中 `crash_rebound` 是唯一 4-candle 与 8-candle fee-adjusted mean 为正的候选族。
- `blowoff_short` 与 `selloff_continuation` 在粗筛下均为负，不应作为 V11.30 主线。
- 进一步只读 gate 探索显示，排除 `alpha_short_block` / `takerSellPressure` 后，`crash_rebound` 从 15 个样本收紧到 12 个样本，4-candle fee-adjusted mean 约 `+24.5853 bps`，positive rate `0.75`。
- 样本仍然很少，所以只能做小仓位 dry-run shadow，不能做 replacement 或 live 结论。

## Scope And Boundaries

已执行：

- 只读查看 `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json`。
- 只读调用服务器 `freqtrade-v1129` local API `/api/v1/pair_candles`。
- 使用临时脚本探索 `crash_rebound` gate variants；临时脚本已删除。
- 新增本审计报告和任务记录。

未执行：

- 未修改 `strategies/**`。
- 未修改 `user_data/**`。
- 未修改 `configs/**`。
- 未修改 `dashboard/**`。
- 未修改 `deploy/**`。
- 未读取 `.env` 或 `user_data/monitor.env`。
- 未读取或打印 API key、交易所凭证、服务器密钥、dashboard 密码。
- 未启动、停止、重启 bot。
- 未运行回测。
- 未执行真实交易。

## Task 57 Scorecard Recap

Task 57 replay scorecard:

| Candidate | Count | 4-candle fee-adjusted mean bps | 4-candle positive rate | 4-candle MAE mean bps |
|---|---:|---:|---:|---:|
| `crash_rebound` | `15` | `21.5559` | `0.6667` | `69.002` |
| `blowoff_short` | `1075` | `-18.653` | `0.4009` | `65.7918` |
| `selloff_continuation` | `122` | `-19.9735` | `0.3361` | `66.9187` |

Interpretation:

- `crash_rebound` is the only candidate family with positive 4-candle mean after fee assumption.
- Short-side candidates are currently too noisy and negative under rough gates.
- V11.29 still has `final_entry_rows=0`, so the new candidate should be separated as a shadow lane rather than mixed into V11.29 main.

## Crash Rebound Gate Exploration

Base rough definition used in Task 57:

- 15m open-close return `> 0.4%`;
- 15m high-low range `>= 1.2%`;
- RSI between `35` and `62`;
- volume greater than `0.8 * volume_mean`;
- direction: long;
- fee assumption: `10 bps`.

Additional Task 58 read-only variants:

| Variant | Count | 4-candle fee-adjusted mean bps | Positive rate | Notes |
|---|---:|---:|---:|---|
| `base_crash_rebound` | `15` | `21.5559` | `0.6667` | Best broad family from Task 57 |
| `not_alpha_short_blocked` | `12` | `24.5853` | `0.75` | Better and cleaner; removes taker-sell pressure cases |
| `not_taker_sell_pressure` | `12` | `24.5853` | `0.75` | Same count in current sample |
| `volume_ratio_ge_1` | `14` | `18.1952` | `0.6429` | Useful but not enough alone |
| `range_hl_ge_1_5pct` | `3` | `74.7696` | `0.6667` | Too few samples; BCH-only in current window |
| `bch_sol_doge_eth_only` | `12` | `29.0671` | `0.6667` | Pair subset looks stronger but may be overfit |
| `bch_only` | `7` | `31.7419` | `0.5714` | Too concentrated |
| `rsi_40_58` | `9` | `2.5893` | `0.5556` | Worse than base |
| `rsi_40_58_and_volume_ge_1` | `8` | `-5.6628` | `0.5` | Reject as primary gate |

Key selection insight:

- Do not use `alpha_filter_block_long` as a hard veto for this candidate, because most observed profitable rebound candidates still had long crowding flags.
- Do use `alpha_filter_block_short=false` / no `takerSellPressure` as a quality filter, because it improves the 4-candle mean and positive rate in the current sample.
- Do not make the candidate BCH-only despite strong examples; that would be too narrow and likely overfit.

## Selected Candidate

Selected for Task 59 planning:

**V11.30 Crash Rebound Long Shadow**

Direction:

- long only.

Initial shadow purpose:

- Observe whether post-crash rebound entries that V11.29 currently blocks can produce real dry-run orders and useful execution evidence.

Initial candidate gate draft:

| Gate | Draft |
|---|---|
| timeframe | `15m` |
| direction | long |
| 15m return | `close / open - 1 > 0.004` |
| 15m range | `(high - low) / close >= 0.012` |
| RSI | `35 <= rsi <= 62` |
| volume | `volume > volume_mean * 0.8` |
| alpha short pressure | require `alpha_filter_block_short == false` |
| taker sell pressure | exclude candidates whose `alpha_risk_flags` include `takerSellPressure` |
| alpha long crowding | not a hard veto; use as sizing/risk cap in later design |
| initial hold horizon | target observation around 4 to 8 candles |
| stake | small dry-run shadow stake only; exact amount deferred to Task 59 |

Initial pair policy:

- Do not select BCH-only.
- Start from V11.29 liquid pair universe or a limited high-liquidity subset.
- Task 59 should evaluate whether to use all V11.29 pairs or a conservative subset such as BCH/SOL/DOGE/ETH/LINK/XRP.

## Rejected Candidates

### Blowoff Short

Rejected as V11.30 primary candidate.

Reason:

- Very large sample count (`1075`) but negative 4-candle fee-adjusted mean (`-18.653 bps`).
- Positive rate is only `0.4009`.
- It may be useful after tighter filtering, but not as the next primary shadow.

### Selloff Continuation

Rejected as V11.30 primary candidate.

Reason:

- 4-candle fee-adjusted mean remains negative (`-19.9735 bps`).
- Positive rate is low (`0.3361`).
- In this market slice, naive high-ADX selloff continuation appears weaker than rebound long.

### Direct V11.29 Parameter Loosening

Rejected.

Reason:

- V11.29 has shown `final_entry_rows=0`, but blindly loosening alpha or ADX gates risks turning no-trade into noisy overtrading.
- A separated V11.30 shadow lane gives cleaner evidence.

## Risk Controls Required In Task 59

Task 59 must not implement an unconstrained long strategy. It should include at minimum:

- separate strategy class or shadow arm name;
- dry-run only;
- small stake sizing;
- explicit entry tag, e.g. `v1130_crash_rebound_long`;
- no live trading;
- no replacement conclusion;
- clear SQLite/API evidence path;
- signal telemetry showing pre-filter candidate, alpha flags, final entry, and reason;
- maximum open trades cap lower than the main V11.29 lane;
- time-based or weakness-based exit logic for observation;
- no hard dependency on secret files.

## Decision

Proceed to Task 59:

**Task 59: V11.30 Crash Rebound Shadow Implementation Plan**

Allowed outcome:

- produce implementation plan for a dry-run shadow candidate.

Not allowed yet:

- modify strategy code;
- modify bot config;
- start new bot;
- stop existing bot;
- deploy to server;
- claim V11.30 is profitable or production-ready.

## What This Cannot Conclude

This task cannot conclude:

- V11.30 will make money.
- `crash_rebound` is production-ready.
- V11.29 can be replaced.
- V10.8.2 should be restored.
- Any candidate is safe for live trading.

It can only conclude:

- `crash_rebound` is the best available next candidate from the current replay evidence.
- The next safe step is a narrow implementation plan, followed by small dry-run shadow validation.

