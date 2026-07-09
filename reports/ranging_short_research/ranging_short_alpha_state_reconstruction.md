# Ranging Short Alpha-State Reconstruction

## Summary

This report reconstructs only what can be proven from committed read-only
evidence. The available ranging-short study remains OHLCV-derived and does not
contain historical alpha/taker/protection state.

Decision:

```text
alpha_state_not_reconstructable_from_committed_evidence
```

## Sources

- `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json`
- `reports/audits/task128_ranging_short_candidate_evidence_deep_review.md`
- `reports/audits/task131_ranging_short_alpha_state_reconstruction_plan.md`

## Observed OHLCV Evidence

| item | value |
|---|---|
| candidate count | 1214 |
| pair count | 12 |
| method | `derived_from_ohlcv_feather` |
| latest pair data max | `2026-07-03T08:45:00+00:00` |

| horizon candles | count | fee-adjusted mean bps | fee-adjusted positive rate | MFE mean bps | MAE mean bps |
|---:|---:|---:|---:|---:|---:|
| 1 | 1214 | -8.3853 | 0.3979 | 27.4189 | 27.6761 |
| 2 | 1213 | -4.0056 | 0.4625 | 39.1428 | 37.1132 |
| 4 | 1212 | 0.1647 | 0.5149 | 55.8373 | 48.9276 |
| 8 | 1212 | 7.3426 | 0.5817 | 78.6989 | 65.3719 |

## Pair Matrix

| pair | candidates | 8-candle fee-adjusted mean bps | 8-candle positive rate | alpha state | protection blocked |
|---|---:|---:|---:|---|---|
| `BTC/USDT:USDT` | 97 | 1.5704 | 0.5258 | `missing` | `unknown` |
| `ETH/USDT:USDT` | 65 | 26.874 | 0.6923 | `missing` | `unknown` |
| `SOL/USDT:USDT` | 133 | -2.8237 | 0.5639 | `missing` | `unknown` |
| `BNB/USDT:USDT` | 110 | -5.4222 | 0.5364 | `missing` | `unknown` |
| `XRP/USDT:USDT` | 112 | 10.0614 | 0.5714 | `missing` | `unknown` |
| `DOGE/USDT:USDT` | 94 | 8.304 | 0.5957 | `missing` | `unknown` |
| `ADA/USDT:USDT` | 90 | -7.041 | 0.6889 | `missing` | `unknown` |
| `LINK/USDT:USDT` | 104 | 8.5945 | 0.5577 | `missing` | `unknown` |
| `AVAX/USDT:USDT` | 138 | 16.5553 | 0.5882 | `missing` | `unknown` |
| `LTC/USDT:USDT` | 158 | 12.6762 | 0.5696 | `missing` | `unknown` |
| `TRX/USDT:USDT` | 7 | -0.8951 | 0.2857 | `missing` | `unknown` |
| `BCH/USDT:USDT` | 106 | 14.6831 | 0.5943 | `missing` | `unknown` |

## Alpha-State Availability

| field | state | reason |
|---|---|---|
| `alpha_risk_flags` | `missing` | Committed evidence contains OHLCV-derived candidates but no historical alpha-risk allowed/blocked state. |
| `taker_buy_pressure` | `missing` | No committed taker-buy pressure series is available for the candidate timestamps. |
| `taker_sell_pressure` | `missing` | No committed taker-sell pressure series is available for the candidate timestamps. |
| `protection_blocked` | `unknown` | No live protection or pairlock state was joined to the historical candidates. |
| `pairlist_included` | `unknown` | Historical runtime pairlist inclusion is not proven for every candidate timestamp. |
| `max_open_trades_blocked` | `unknown` | Historical wallet/open-trade state is not present in the committed OHLCV study. |
| `wallet_or_stake_blocked` | `unknown` | Historical wallet and stake availability are not present in the committed OHLCV study. |

## Decision

| item | value |
|---|---|
| can authorize strategy implementation | `false` |
| can authorize backtest | `false` |
| can authorize shadow deployment | `false` |
| can claim profitability | `false` |
| reason | The candidate remains research-only because alpha/taker/protection state is missing or unknown. |

## Blocking Gaps

- `alpha_risk_flags_missing`
- `taker_buy_pressure_missing`
- `taker_sell_pressure_missing`
- `protection_blocked_unknown`
- `pairlist_included_unknown`
- `max_open_trades_blocked_unknown`
- `wallet_or_stake_blocked_unknown`
- `recent_runtime_window_missing`
- `no_freqtrade_backtest`
- `no_live_dry_run_execution_evidence`

## What This Cannot Conclude

- Does not prove ranging-short is profitable.
- Does not authorize strategy implementation.
- Does not authorize a Freqtrade backtest.
- Does not authorize deployment or live shadow launch.
- Does not conclude V11.30 or V11.31 should be abandoned.

## Recommended Next Task

```text
Task 142: Ranging Short Alpha/Taker Data Source Authorization
```
