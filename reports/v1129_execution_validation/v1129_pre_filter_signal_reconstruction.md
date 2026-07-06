# V11.29 Pre-Filter Signal Reconstruction

## Summary

This report reconstructs V11.29 signal counts from the read-only runtime
`pair_candles` API and a sanitized alpha-risk SQLite summary. It does not read
secret files, place orders, run backtests, modify strategy code, modify bot
configuration, or restart any bot.

- Rows reconstructed: 6156
- Raw trending short candidates: 0
- Raw ranging short candidates: 111
- Short candidates blocked by alpha: 26
- V10.2 short-core candidates: 0
- Final enter_short rows: 0
- Primary layer: `v102_short_core_pruning`
- Confidence: `high`

## Root Cause Assessment

Short candidates survive alpha, but none satisfy V10.2 trending-short core semantics.

## Aggregate Funnel

| Layer | Count |
| --- | ---: |
| raw trending long | 1152 |
| raw trending short | 0 |
| raw ranging long | 17 |
| raw ranging short | 111 |
| alpha blocked long candidates | 1169 |
| alpha blocked short candidates | 26 |
| surviving long after alpha | 0 |
| surviving short after alpha | 85 |
| V10.2 long blocked by design | 0 |
| V10.2 ranging blocked by design | 85 |
| V10.2 non-core short blocked | 85 |
| V10.2 short-core candidates | 0 |
| V11.18 blocked | 0 |
| V11.29 retagged/sized | 0 |
| final enter_long | 0 |
| final enter_short | 0 |

## Pair Breakdown

| Pair | Rows | Raw trending short | Raw ranging short | Alpha blocked short | V10.2 short core | Final short |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 513 | 0 | 4 | 0 | 0 | 0 |
| ETH/USDT:USDT | 513 | 0 | 0 | 0 | 0 | 0 |
| SOL/USDT:USDT | 513 | 0 | 0 | 0 | 0 | 0 |
| BNB/USDT:USDT | 513 | 0 | 15 | 5 | 0 | 0 |
| XRP/USDT:USDT | 513 | 0 | 0 | 0 | 0 | 0 |
| DOGE/USDT:USDT | 513 | 0 | 27 | 7 | 0 | 0 |
| ADA/USDT:USDT | 513 | 0 | 0 | 0 | 0 | 0 |
| LINK/USDT:USDT | 513 | 0 | 0 | 0 | 0 | 0 |
| AVAX/USDT:USDT | 513 | 0 | 37 | 7 | 0 | 0 |
| LTC/USDT:USDT | 513 | 0 | 20 | 4 | 0 | 0 |
| TRX/USDT:USDT | 513 | 0 | 8 | 3 | 0 | 0 |
| BCH/USDT:USDT | 513 | 0 | 0 | 0 | 0 | 0 |

## Observed Tags

| Tag | Rows |
| --- | ---: |
| `trending_long` | 1100 |
| `v66_ranging_short_edge` | 111 |
| `v66_ranging_long_edge` | 17 |

## Alpha Summary

- Source status: `missing`
- Sample count: unknown
- Min sampled_at: `unknown`
- Max sampled_at: `unknown`
- Recent levels: `{}`
- Recent top flags: `{}`

## Interpretation

The reconstruction identifies the suppressing layer before final entries are
created. A non-empty `enter_tag` remains metadata; it is not an order trigger.
Final entries require `enter_long == 1` or `enter_short == 1`.

## Recommended Next Task

Task 36: V11.29 Short-Core Condition Calibration Plan
