# Task 142: Ranging Short Alpha/Taker Data Source Authorization

## Summary

Authorized the next ranging-short work as a read-only alpha/taker/protection
data-source inventory boundary. This task does not locate live secrets, access
server files, modify strategy code, modify bot config, run backtests, or start
or stop bots.

Decision:

```text
authorize_read_only_alpha_taker_data_source_inventory
```

## Sources Reviewed

```text
reports/audits/task140_ranging_short_alpha_state_reconstruction_implementation.md
reports/ranging_short_research/ranging_short_alpha_state_reconstruction.json
reports/ranging_short_research/ranging_short_alpha_state_reconstruction.md
```

## Current Evidence State

| field | state |
|---|---|
| OHLCV-derived candidate count | `1214` |
| 8-candle fee-adjusted mean | `7.3426 bps` |
| alpha-risk flags | `missing` |
| taker-buy pressure | `missing` |
| taker-sell pressure | `missing` |
| protection / pairlist / wallet state | `unknown` |
| strategy implementation | `not authorized` |
| backtest | `not authorized` |

## Authorized Future Read-Only Questions

The next data-source task may answer only these questions:

- whether committed or server-side non-secret telemetry contains historical
  alpha-risk allowed/blocked state;
- whether taker-buy and taker-sell pressure can be reconstructed for candidate
  timestamps;
- whether protection, pairlist, max-open-trades, and wallet/stake blockers are
  available as non-secret evidence;
- whether the available source window reaches recent 2026-07 market conditions;
- whether unreconstructable fields must remain `missing` or `unknown`.

## Explicitly Not Authorized

The next task is not authorized to:

- modify `strategies/**`;
- modify `user_data/**` or bot configs;
- modify `configs/**`, `dashboard/**`, or `deploy/**`;
- read `.env`, `user_data/monitor.env`, API keys, passwords, tokens, or server
  private keys;
- start, stop, restart, or deploy a bot;
- run a Freqtrade backtest;
- claim ranging-short is profitable or deployable.

## Proposed Future Exact Paths

If a local report builder is required, it should be reviewed by a separate exact
path task before any guard change:

```text
scripts/build_ranging_short_alpha_taker_data_source_inventory.js
reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.json
reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.md
```

Do not approve broad patterns such as:

```text
scripts/build_ranging_short_*
reports/ranging_short_research/**
reports/**/*ranging_short*
```

## Recommended Next Task

Proceed with:

```text
Task 145: Ranging Short Alpha/Taker Data Source Exact Path Review
```

