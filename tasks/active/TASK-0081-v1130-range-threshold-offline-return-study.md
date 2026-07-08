# TASK-0081: V11.30 Range Threshold Offline Return Study

## Status

Completed.

## Objective

Evaluate the `range >= 0.008` watch scenario without changing live strategy
thresholds.

## Result

- Candidates: `29`.
- Enabled: `23`.
- Blocked by taker sell pressure: `6`.
- 4-candle mean forward return: `20.15` bps.
- 8-candle mean forward return: `34.13` bps.
- 1-candle mean forward return: `-1.88` bps.

## Boundary

No strategy/config/live bot change was made. No backtest was run.

## Output

- `reports/audits/task81_v1130_range_threshold_offline_return_study.md`

## Next

Proceed to Task 82 and consider a later loose-range watch gate design.
