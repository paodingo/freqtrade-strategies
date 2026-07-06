# Task 39: V11.29 Ranging-Short Offline Candidate Return Study

## Summary

Implemented and ran a read-only offline candidate return study generator:

```text
scripts/build_v1129_ranging_short_offline_return_study.js
```

Generated:

```text
reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.json
reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.md
```

The generator reads V11.29 runtime `pair_candles` data through the server-side
localhost API and reconstructs only the `v66_ranging_short_edge` candidate
family. It computes candidate-only forward returns, favorable excursion, and
adverse excursion over 1/2/4/8 candles.

This is not a Freqtrade backtest, not a live execution report, and not a V11.29
replacement verdict.

## Data Source

Read-only source:

```text
freqtrade-v1129 localhost:8122 /api/v1/pair_candles
timeframe = 15m
limit = 3000
```

The runtime API currently exposed about 5.4896 days of candles per pair, not
the 30d minimum window required by Task 38.

## Candidate Counts

| Metric | Count |
| --- | ---: |
| total `v66_ranging_short_edge` candidates | 111 |
| alpha-allowed candidates | 85 |
| alpha-blocked candidates | 26 |
| max available runtime candle window | 5.4896 days |

Classification:

```text
insufficient
```

Reason:

```text
available runtime candle window is shorter than the 30d minimum gate
```

## Aggregate Forward Return Summary

Fee assumption:

```text
10 bps round trip
```

For a short candidate, positive return means future close is lower than the
candidate close.

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 111 | 0.7886 | -9.2114 | 0.3333 | 20.4512 | 22.6791 |
| 2 | 111 | -0.9409 | -10.9409 | 0.3604 | 27.8431 | 31.8075 |
| 4 | 111 | -6.4547 | -16.4547 | 0.3514 | 35.3366 | 45.8417 |
| 8 | 111 | -15.5990 | -25.5990 | 0.3694 | 47.1665 | 73.7445 |

Alpha-allowed 4-candle summary:

| Metric | Value |
| --- | ---: |
| count | 85 |
| gross mean bps | -5.5344 |
| fee-adjusted mean bps | -15.5344 |
| fee-adjusted positive rate | 0.3882 |
| MFE mean bps | 35.6854 |
| MAE mean bps | 46.0665 |

## Pair-Level Notes

The current short runtime window remains uneven:

| Pair | Candidates | 4-candle fee-adjusted mean bps |
| --- | ---: | ---: |
| BTC/USDT:USDT | 4 | 14.2424 |
| BNB/USDT:USDT | 15 | -15.8643 |
| DOGE/USDT:USDT | 27 | -10.4383 |
| AVAX/USDT:USDT | 37 | -10.2284 |
| LTC/USDT:USDT | 20 | -41.9578 |
| TRX/USDT:USDT | 8 | -18.2542 |

BTC is positive in this short sample, but the sample is only four candidates.
That is not sufficient for a live change. The broader aggregate and
alpha-allowed set are negative after conservative fees in the current window.

## What This Can Conclude

Observed:

- V11.29 runtime candle data is available through the API.
- `v66_ranging_short_edge` candidates still exist.
- The candidate-only forward return study can be generated without touching
  strategy, config, SQLite, or bot runtime state.

Derived:

- Current short-window fee-adjusted aggregate returns are negative over the
  tested horizons.
- Alpha-allowed candidates do not currently pass the 4-candle fee-adjusted mean
  gate.

Insufficient:

- The available runtime window is shorter than 30d.
- The BTC subset is far too small to treat as evidence.
- No real orders, fills, fees, funding, slippage, or latency are measured here.

Unknown:

- Whether the candidate family behaves differently over 30d+ historical data.
- Whether pair-specific filters could change the result.
- Whether a full offline replay or backtest would match this simple forward
  return study.

## Safety Decision

Do not enable live V11.29 ranging-short entries from this evidence.

The current outcome supports extending historical data coverage first, not
changing strategy or bot configuration.

## Validation

Commands run:

```powershell
node --check scripts/build_v1129_ranging_short_offline_return_study.js
node scripts/build_v1129_ranging_short_offline_return_study.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- write SQLite;
- modify server files;
- modify the original dirty workspace.

## Recommended Task 40

Recommended next task:

```text
Task 40: V11.29 Ranging-Short Historical Data Coverage Extension
```

Scope:

- Locate or acquire at least 30d of clean 15m/4h candle context.
- Re-run the same candidate-only return study on the longer window.
- Keep the work offline until sample sufficiency and fee-adjusted gates are
  satisfied.
- Do not change live V11.29 strategy/config until later explicit approval.

