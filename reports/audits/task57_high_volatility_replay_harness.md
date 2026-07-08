# Task 57: High-Volatility Replay Harness

## Summary

本任务实现并运行了 V11.29 高波动候选事件只读 replay harness。它从服务器 `freqtrade-v1129` 的 analyzed dataframe 读取最近 15m 数据，按 Task 56 定义的候选族计算 direction-aware forward return scorecard。

关键结论：

- 本任务没有修改策略、bot 配置、dashboard、deploy、SQLite、服务器文件或运行中 bot 状态。
- 本任务没有读取 secret、`.env`、`user_data/monitor.env`、API key、交易所凭证、dashboard 密码。
- 当前 replay 样本中 `final_entry_rows=0`，继续证明 V11.29 当前 entry/gate 体系没有把高波动候选转为订单。
- 三个方向候选里，`crash_rebound` 在当前粗筛条件下表现最好，但样本数只有 `15`，不能直接进入 live。
- `blowoff_short` 与 `selloff_continuation` 在当前粗筛条件下 4-candle fee-adjusted mean 为负，不应直接做 V11.30 主线，除非 Task 58 进一步收紧条件。

## Files Changed

| Path | Purpose |
|---|---|
| `scripts/guard_harness_diff.js` | 为 Task 57 精确允许 replay harness 脚本、输出和测试文件 |
| `scripts/guard_trading_surface.js` | 为 Task 57 精确允许 versioned harness/report/test 路径 |
| `docs/harness/change_surface_matrix.md` | 记录 Task 57 精确白名单，不放宽目录通配 |
| `tests/test_v1129_high_volatility_replay_harness.js` | TDD 单元测试，验证候选分类和 direction-aware forward return |
| `scripts/build_v1129_high_volatility_replay_harness.js` | 只读 replay harness |
| `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json` | replay JSON scorecard |
| `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.md` | replay Markdown scorecard |
| `reports/audits/task57_high_volatility_replay_harness.md` | 本审计报告 |
| `tasks/active/TASK-0057-high-volatility-replay-harness.md` | 本任务记录 |

## Guard Boundary

Task 57 只新增以下精确白名单：

- `scripts/build_v1129_high_volatility_replay_harness.js`
- `tests/test_v1129_high_volatility_replay_harness.js`
- `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json`
- `reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.md`

明确没有允许：

- `reports/v1129_execution_validation/**`
- `scripts/build_v1129_*`
- `tests/**`
- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`

## TDD Evidence

RED:

```text
node --test tests/test_v1129_high_volatility_replay_harness.js
Error: Cannot find module '../scripts/build_v1129_high_volatility_replay_harness'
```

GREEN:

```text
node --test tests/test_v1129_high_volatility_replay_harness.js
pass 2
fail 0
```

Tests cover:

- `classifyCandidateTypes` detects `selloff_continuation`、`blowoff_short`、`crash_rebound`。
- `buildReplayScorecard` computes direction-aware forward returns for short and long candidates.

## Replay Method

Input:

- Server: `43.134.72.69`
- API source: `freqtrade-v1129` local API `127.0.0.1:8122`
- Endpoint: `/api/v1/pair_candles`
- Timeframe: `15m`
- Limit: `672`
- Pairs: 12 whitelisted V11.29 pairs

Candidate families:

| Candidate | Direction | Rough meaning |
|---|---|---|
| `high_volatility` | observation | Large 15m open-close or high-low range |
| `selloff_continuation` | short | High-ADX selloff continuation idea |
| `blowoff_short` | short | Upper-range / high-RSI fade idea |
| `crash_rebound` | long | High-volatility rebound idea |

Scoring:

- Horizons: 1 / 2 / 4 / 8 candles.
- Fee assumption: `10 bps`.
- Short return: `(entry_close - future_close) / entry_close`.
- Long return: `(future_close - entry_close) / entry_close`.
- MFE/MAE derived from future highs/lows.

## Scorecard Result

Observed scorecard metadata:

| Metric | Value |
|---|---:|
| total rows | `8064` |
| final entry rows | `0` |
| alpha long block rows | `7728` |
| alpha short block rows | `2712` |
| high volatility | `43` |
| selloff continuation | `122` |
| blowoff short | `1075` |
| crash rebound | `15` |

Candidate ranking at 4-candle horizon:

| Rank | Candidate | Count | 4-candle fee-adjusted mean bps | Positive rate | MAE mean bps |
|---:|---|---:|---:|---:|---:|
| 1 | `crash_rebound` | `15` | `21.5559` | `0.6667` | `69.002` |
| 2 | `blowoff_short` | `1075` | `-18.653` | `0.4009` | `65.7918` |
| 3 | `selloff_continuation` | `122` | `-19.9735` | `0.3361` | `66.9187` |

Interpretation:

- `crash_rebound` is the only rough candidate with positive mean after the 10 bps fee assumption at the 4-candle and 8-candle horizons.
- `crash_rebound` sample count is small, so it needs stricter Task 58 validation before strategy work.
- `blowoff_short` has many events but negative mean under this rough definition; it may need much tighter filters or rejection.
- `selloff_continuation` under the rough definition is not attractive enough for direct V11.30 work.

## What This Can Conclude

Observed:

- V11.29 analyzed dataframe can be queried and replayed.
- High-volatility candidate families exist in recent market data.
- V11.29 final entries remain zero during these candidate windows.

Derived:

- `crash_rebound` is the first candidate family to inspect for V11.30.
- The current short-side rough candidates do not justify direct strategy changes.

Insufficient:

- This is not a Freqtrade backtest.
- This does not verify fills, order price, funding, slippage, latency, or live execution quality.
- This does not justify live trading.
- This does not prove a replacement strategy exists.

## Recommended Task 58

**Task 58: V11.30 Candidate Selection**

Recommended scope:

1. Read Task 57 scorecard.
2. Focus first on `crash_rebound`.
3. Tighten candidate gates by pair, volatility size, RSI band, alpha flags, BTC/ETH regime, and forward-return horizon.
4. Decide whether V11.30 should be:
   - a crash rebound long shadow;
   - a stricter blowoff short shadow;
   - a mixed high-volatility strategy;
   - or no strategy if replay evidence is too weak.
5. Do not modify live strategy/config until Task 58 explicitly selects a candidate and Task 59 authorizes implementation.
