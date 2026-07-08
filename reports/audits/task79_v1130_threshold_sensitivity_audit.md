# Task 79: V11.30 Threshold Sensitivity Audit

## Summary

Audited V11.30 gate sensitivity using the post-refresh 240-candle replay window.
This task does not change strategy thresholds. It only reports how many
candidates would appear under alternative threshold scenarios.

Conclusion:

- baseline produced `11` raw candidates, with `9` enabled and `2` blocked by
  taker sell pressure;
- lowering only the return threshold from `0.004` to `0.003` did not increase
  candidates;
- lowering only volume ratio from `0.8` to `0.6` did not increase candidates;
- relaxing range from `0.012` to `0.008` increased enabled examples from `9` to
  `23`;
- combined looser thresholds increased enabled examples to `34`;
- the dominant bottleneck in this window is the `range` threshold, not return
  or volume alone.

## Sensitivity Scenarios

| scenario | candidates | enabled | blocked taker sell pressure | blocked alpha short |
|---|---:|---:|---:|---:|
| `baseline` | 11 | 9 | 2 | 0 |
| `return_0_003` | 11 | 9 | 2 | 0 |
| `range_0_008` | 29 | 23 | 6 | 0 |
| `volume_ratio_0_6` | 11 | 9 | 2 | 0 |
| `rsi_30_68` | 14 | 10 | 4 | 0 |
| `combined_looser` | 46 | 34 | 12 | 0 |

## Interpretation

Observed:

- the latest checked candle still failed `return` and `range` across all pairs;
- several latest candles also failed `rsi` or `volume`;
- the historical window is most sensitive to the required 15m range threshold.

Not concluded:

- lowering thresholds would improve profit;
- V11.30 is bad or good;
- V11.30 can replace any benchmark;
- a live trade should have happened at the latest candle.

## Candidate Next Changes To Study

Potential future research tasks:

1. Run an offline return study for `range >= 0.008` while keeping current alpha
   blocks.
2. Test a two-tier gate:
   - strict live gate for immediate trading;
   - looser watch gate for alert/telemetry only.
3. Add a market-regime qualifier before lowering range, to avoid simply
   increasing noise.

Do not change live strategy thresholds without a separate implementation and
backtest/replay task.

## Non-Actions

This task did not:

- modify strategy thresholds;
- modify bot configs;
- start, stop, or restart bots;
- read secrets;
- run backtests;
- write SQLite.

## Recommended Next Task

Recommended next sequence:

```text
Task 80: Correct V11.30 data refresh command if local feather freshness remains required
Task 81: V11.30 range-threshold offline return study
Task 82: V11.30 live observation continuation with telemetry
```
