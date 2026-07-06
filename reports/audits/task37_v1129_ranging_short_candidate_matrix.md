# Task 37: V11.29 Ranging-Short Candidate Matrix

## Summary

This task built a read-only candidate matrix for V11.29
`v66_ranging_short_edge` candidates from the live V11.29 runtime
`pair_candles` API.

It did not modify strategy code, bot configuration, dashboard, deploy files,
SQLite files, server files, or bot runtime state. It did not read `.env`,
`user_data/monitor.env`, API keys, exchange credentials, server keys,
dashboard passwords, or tokens.

Observed at:

```text
2026-07-06T07:45:45.721015+00:00
```

Read-only source:

```text
freqtrade-v1129 localhost:8122 /api/v1/pair_candles
timeframe = 15m
limit = 672
```

## Aggregate Matrix

| Metric | Count |
| --- | ---: |
| total `v66_ranging_short_edge` candidates | 111 |
| blocked by `v102_short_core_prunes_ranging_non_core_short` | 85 |
| blocked by `alpha_filter_block_short` | 26 |
| final `enter_short` rows from these candidates | 0 |

Interpretation:

- `v66_ranging_short_edge` candidates exist.
- Most of them are not blocked by alpha.
- The dominant blocker is still the inherited V10.2 short-core rule that prunes
  ranging/non-core short candidates before they can become final
  `enter_short`.
- This does not prove the candidates would have been profitable.
- This does not prove V11.29 should trade them live.

## Pair Matrix

| Pair | Rows | Candidates | 1d | 7d | 14d | V10.2 short-core pruned | Alpha short blocked | Final short |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 514 | 4 | 4 | 4 | 4 | 4 | 0 | 0 |
| ETH/USDT:USDT | 514 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| SOL/USDT:USDT | 514 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| BNB/USDT:USDT | 514 | 15 | 0 | 15 | 15 | 10 | 5 | 0 |
| XRP/USDT:USDT | 513 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DOGE/USDT:USDT | 514 | 27 | 0 | 27 | 27 | 20 | 7 | 0 |
| ADA/USDT:USDT | 514 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| LINK/USDT:USDT | 514 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AVAX/USDT:USDT | 514 | 37 | 1 | 37 | 37 | 30 | 7 | 0 |
| LTC/USDT:USDT | 513 | 20 | 0 | 20 | 20 | 16 | 4 | 0 |
| TRX/USDT:USDT | 513 | 8 | 0 | 8 | 8 | 5 | 3 | 0 |
| BCH/USDT:USDT | 513 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Candidate Concentration

The ranging-short candidates are concentrated in six pairs:

| Pair | Candidates |
| --- | ---: |
| AVAX/USDT:USDT | 37 |
| DOGE/USDT:USDT | 27 |
| LTC/USDT:USDT | 20 |
| BNB/USDT:USDT | 15 |
| TRX/USDT:USDT | 8 |
| BTC/USDT:USDT | 4 |

The current runtime sample shows candidate density over the 7d/14d window, but
only BTC and AVAX had candidates inside the latest 1d window.

## Representative Candidate Rows

The collector sampled concrete rows without reading secrets or modifying server
state. Examples:

| Pair | Time UTC | Regime | Tag | Alpha short block | Blocked reason | RSI | BB% | 24h range pos | 48h range pos | ADX 4h | Final short |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 2026-07-05T22:30:00Z | ranging | `v66_ranging_short_edge` | false | `v102_short_core_prunes_ranging_non_core_short` | 75.3065 | 1.0000 | 0.7237 | 0.7415 | 33.9960 | 0 |
| BTC/USDT:USDT | 2026-07-05T22:45:00Z | ranging | `v66_ranging_short_edge` | false | `v102_short_core_prunes_ranging_non_core_short` | 78.2792 | 1.0000 | 0.8329 | 0.8436 | 33.9960 | 0 |
| BNB/USDT:USDT | 2026-07-03T09:15:00Z | ranging | `v66_ranging_short_edge` | true | `alpha_filter_block_short` | 58.4201 | 0.8526 | 0.7380 | 0.8638 | 27.7851 | 0 |
| DOGE/USDT:USDT | 2026-07-03T01:30:00Z | ranging | `v66_ranging_short_edge` | false | `v102_short_core_prunes_ranging_non_core_short` | 66.4160 | 1.0000 | 0.7778 | 0.8465 | 31.1161 | 0 |
| AVAX/USDT:USDT | 2026-07-03T01:00:00Z | ranging | `v66_ranging_short_edge` | false | `v102_short_core_prunes_ranging_non_core_short` | 66.1004 | 0.9529 | 0.7948 | 0.8859 | 14.6740 | 0 |
| LTC/USDT:USDT | 2026-07-03T01:00:00Z | ranging | `v66_ranging_short_edge` | false | `v102_short_core_prunes_ranging_non_core_short` | 66.7698 | 1.0000 | 0.9149 | 0.9574 | 13.0862 | 0 |
| TRX/USDT:USDT | 2026-07-03T21:15:00Z | ranging | `v66_ranging_short_edge` | false | `v102_short_core_prunes_ranging_non_core_short` | 84.4129 | 1.0000 | 0.9443 | 0.9552 | 19.9889 | 0 |

## What This Matrix Can Conclude

Observed:

- V11.29 runtime data is being analyzed and exposed through `pair_candles`.
- `v66_ranging_short_edge` candidates exist in the observed runtime window.
- The exact candidate family is ranging-short, not trending-short.
- Most ranging-short candidates are pruned by V10.2 short-core semantics rather
  than by alpha short filtering.
- No candidate became final `enter_short` in this sample.

Derived:

- The next useful research lane is not a generic "make V11.29 trade" change.
  It is a scoped evaluation of whether ranging-short candidates should remain
  blocked or become a separate, risk-capped research lane.

Insufficient:

- This matrix does not measure candidate profitability.
- This matrix does not measure order fill quality, fees, slippage, funding, or
  latency.
- This matrix does not support a same-window replacement comparison with
  V10.8.2.

Unknown:

- Whether these ranging-short candidates would have produced acceptable
  backtest or dry-run outcomes if enabled.
- Whether a small-stake separate research lane would improve or harm the
  system.

## Safety Decision

Do not modify the live V11.29 strategy or config based only on this matrix.

The candidate family is real enough to justify offline research, but not enough
to justify live entry enablement.

## Recommended Task 38

Recommended next task:

```text
Task 38: V11.29 Ranging-Short Offline Calibration Design
```

Suggested scope:

- Define an offline-only calibration design for `v66_ranging_short_edge`.
- Decide which historical data windows and metrics are required.
- Define a candidate-only backtest or replay plan, but do not run it unless the
  task explicitly authorizes backtesting.
- Define pass/fail criteria before any live strategy/config change.
- Keep V10.8.2 comparison as benchmark evidence, not as an automatic
  replacement verdict.

## Boundaries

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
- run backtests;
- write SQLite;
- modify server files;
- modify the original dirty workspace.

## Verification

Required completion checks:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

