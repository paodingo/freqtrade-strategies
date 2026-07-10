# Task 154: Ranging Short Alpha/Taker Source Acquisition Authorization

## Summary

Authorized a future ranging-short alpha/taker/protection source acquisition
task as a bounded read-only evidence step. This task does not access the server,
copy files, read secrets, modify strategy/config files, run backtests, or start
or stop bots.

Decision:

```text
authorize_future_read_only_alpha_taker_source_acquisition_plan
```

## Sources Reviewed

```text
reports/audits/task152_ranging_short_alpha_taker_data_source_inventory_implementation.md
reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.json
reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.md
```

## Current Evidence State

| field | state |
|---|---|
| OHLCV candidate count | `1214` |
| alpha-risk source | `missing` |
| taker-buy pressure source | `missing` |
| taker-sell pressure source | `missing` |
| protection/pairlock source | `unknown` |
| pairlist history source | `unknown` |
| recent 2026-07 runtime window | `not proven` |
| strategy implementation | `not authorized` |
| backtest | `not authorized` |

## Authorized Future Read-Only Questions

A future source acquisition task may answer only these questions:

- whether a non-secret alpha-risk source exists;
- whether non-secret taker-buy/taker-sell pressure sources exist;
- whether protection/pairlock and pairlist history can be inventoried without
  reading secrets;
- whether a recent 2026-07 window is available;
- whether missing fields must remain `missing` or `unknown`.

## Explicitly Not Authorized

The future task is not authorized to:

- modify `strategies/**`;
- modify `user_data/**` or bot configs;
- modify `configs/**`, `dashboard/**`, or `deploy/**`;
- read `.env`, `user_data/monitor.env`, API keys, passwords, tokens, or server
  private keys;
- start, stop, restart, or deploy a bot;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- claim ranging-short is profitable or deployable.

## Recommended Next Task

Proceed with:

```text
Task 157: Ranging Short Alpha/Taker Source Acquisition Exact Path Review
```

