# Task 186: V11.31 Longer Replay Backtest Gate Review

## Summary

Reviewed the V11.31 actual data acquisition execution report and determined
that an OHLCV-only 7d/14d longer replay/backtest preparation task may proceed,
but only under an explicit limitation: alpha/taker/protection timelines remain
unknown and must not be treated as verified.

Decision:

```text
authorize_ohlcv_only_longer_replay_backtest_path_review
```

## Sources Reviewed

```text
reports/audits/task183_v1131_actual_data_acquisition_execution_report_implementation.md
reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.md
```

## Observed Data Readiness

| field | state |
|---|---|
| selected source | `container:freqtrade-v1130-crash-rebound-shadow` |
| approved pairs | `ETH`, `SOL`, `DOGE`, `LINK`, `XRP`, `BCH` |
| 15m files | `6/6` |
| 15m minimum rows | `88429` |
| 15m latest timestamp | `2026-07-10 03:00:00+00:00` |
| 4h files | `6/6` |
| 4h minimum rows | `5526` |
| 4h latest timestamp | `2026-07-09 20:00:00+00:00` |
| 7d window support | `true` |
| 14d window support | `true` |
| alpha/taker/protection timelines | `unknown` |

## Gate Decision

The data gate is sufficient to proceed with a future exact-path
OHLCV-only longer replay/backtest authorization task.

The gate is not sufficient to:

- claim V11.31 profitability;
- deploy or promote V11.31;
- evaluate V11.31 replacement fitness;
- claim alpha/taker/protection behavior was verified;
- run any backtest without a separate exact-path task authorization.

## Required Future Backtest Boundary

A future task may only propose exact paths for an OHLCV-only 7d/14d replay or
backtest report. It must:

- use only the approved pair set;
- use the observed 15m and 4h data sources;
- label alpha/taker/protection as `unknown` or `not evaluated`;
- include fees/slippage assumptions explicitly if a backtest is later run;
- keep strategy/config/server changes out of scope;
- avoid bot lifecycle commands and live/server state changes.

## Blocking Gaps

- Alpha/taker/protection timelines remain unknown.
- No replay/backtest has been run yet.
- No profitability, deployment, or replacement conclusion is allowed.

## Recommended Next Task

Proceed with:

```text
Task 189: V11.31 Longer Replay Backtest Exact Path Review
```

