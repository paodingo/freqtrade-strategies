# Task 166: Ranging Short Alpha/Taker Source Acquisition Execution Authorization

## Summary

Reviewed the Task 163 plan-only artifact and authorized a future bounded
read-only source acquisition execution task for ranging-short alpha/taker
evidence. This task does not connect to the server, acquire data, run backtests,
modify strategy/config files, or start/stop bots.

Decision:

```text
authorize_future_bounded_read_only_source_acquisition_execution
```

## Sources Reviewed

```text
reports/audits/task163_ranging_short_alpha_taker_source_acquisition_plan_implementation.md
reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.json
reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.md
```

## Current Evidence State

| field | state |
|---|---|
| candidate family | `ranging_short_volatility_fade` |
| alpha-risk timeline | `missing` |
| taker-buy pressure timeline | `missing` |
| taker-sell pressure timeline | `missing` |
| protection/pairlock timeline | `unknown` |
| pairlist timeline | `unknown` |
| strategy implementation | `not authorized` |
| backtest | `not authorized` |

## Authorized Future Execution Scope

A future task may perform only bounded, read-only source acquisition planning
and evidence collection:

- locate non-secret alpha-risk timeline sources if they exist;
- locate non-secret taker-buy/taker-sell pressure timeline sources if they exist;
- locate non-secret protection/pairlock and pairlist timeline sources if they
  exist;
- record existence, size, mtime, and schema/field availability metadata;
- keep fields as `missing` or `unknown` unless non-secret evidence proves them.

## Explicitly Not Authorized

The future task is not authorized to:

- read `.env`, `user_data/monitor.env`, API keys, passwords, tokens, or server
  private keys;
- modify `strategies/**`, `user_data/**`, `configs/**`, `dashboard/**`, or
  `deploy/**`;
- start, stop, restart, or deploy any bot;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- implement a strategy;
- claim profitability, deployability, or replacement fitness.

## Stop Conditions For Future Execution

The future task must stop if exact output paths are not pre-authorized, if
readiness fails, if evidence requires reading secrets, or if any command would
write live bot data, strategy/config/dashboard/deploy files, or SQLite data.

## Recommended Next Task

Proceed with:

```text
Task 169: Ranging Short Alpha/Taker Source Acquisition Execution Path Review
```

