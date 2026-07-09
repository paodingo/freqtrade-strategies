# Task 124: Longer Read-Only V11.31 Replay Window Acquisition Plan

## Summary

Task 123 concluded that V11.31 is not ready for backtest because its best
alpha-screened replay layer has only `23` enabled samples, below the `30`
initial gate.

This task defines the safe next evidence step:

```text
acquire_longer_read_only_15m_4h_replay_window_before_backtest
```

The plan does not download data, run backtests, modify strategy/config, or touch
server runtime.

## Current Evidence Gap

| item | current value |
|---|---:|
| alpha-screened V11.31 proxy enabled samples | `23` |
| initial sample gate | `30` |
| OHLCV-only watch samples | `29` |
| OHLCV-only limitation | alpha/taker/protection unknown |
| same-window live execution quality | missing for V11.31 |

## Recommended Acquisition Scope

Acquire a longer read-only replay window for the exact V11.31 pair/timeframe
universe:

| field | value |
|---|---|
| pairs | `ETH`, `SOL`, `DOGE`, `LINK`, `XRP`, `BCH` futures pairs |
| primary timeframe | `15m` |
| informative timeframe | `4h` |
| excluded timeframe | `1h`, unless a later task reintroduces `1h` filters |
| minimum target window | recent `7d` |
| preferred target window | recent `14d` |
| data mode | read-only OHLCV plus committed alpha/taker evidence if available |

## Required Outputs For Future Task

A future implementation should produce:

```text
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_longer_replay_window_inventory.md
```

If a replay generator is needed, it should be introduced in a separate exact
guard task before implementation.

## Safety Boundary

The future acquisition task must not:

- run a Freqtrade backtest;
- modify strategy code;
- modify bot config;
- start, stop, or restart bots;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- write server files;
- copy SQLite trade databases into Git;
- treat OHLCV-only candidates as final strategy entries.

## Acceptance Criteria For Reconsidering Backtest

Backtest can be reconsidered only if the longer window proves:

- exact V11.31 threshold samples reach at least `30`;
- alpha/taker/protection state is observed or explicitly marked unknown;
- fee-adjusted `4_candle` and `8_candle` proxy returns remain positive;
- pair concentration remains acceptable;
- missing lifecycle/fill/slippage/funding/latency evidence is still explicit.

## Recommended Next Task

Proceed with:

```text
Task 127: V11.31 Longer Replay Window Inventory Exact Path Review
```

Do not run a backtest until a later task explicitly clears both sample and
lifecycle evidence gates.

