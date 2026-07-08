# V11.30 Final Decision Telemetry

## Summary

- strategy: `RegimeAwareV1130CrashReboundShadow`
- latest_updated_pair: `BCH/USDT:USDT`
- timeframe: `15m`
- generated_at: `2026-07-08T13:33:45.166009+00:00`
- safety_verdict: `telemetry_only_no_behavior_change`
- pairs_observed: `6`
- rows_observed: `300`
- candidate_rows: `1`
- enabled_rows: `0`
- blocked_rows: `1`

## Latest Rows

| candle_time | candidate | gate | enter_long | enter_tag |
|---|---:|---|---:|---|
| 2026-07-08T12:00:00+00:00 | False | not_candidate | 0 |  |
| 2026-07-08T12:15:00+00:00 | False | not_candidate | 0 |  |
| 2026-07-08T12:30:00+00:00 | False | not_candidate | 0 |  |
| 2026-07-08T12:45:00+00:00 | False | not_candidate | 0 |  |
| 2026-07-08T13:00:00+00:00 | True | blocked_taker_sell_pressure | 0 |  |
| 2026-07-08T13:15:00+00:00 | False | not_candidate | 0 |  |

## Data Gaps

- none observed

## Safety Boundary

This telemetry mirrors final strategy decision fields only. It does not approve V11.30 replacement readiness.
