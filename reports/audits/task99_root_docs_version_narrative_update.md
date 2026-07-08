# Task 99: Root Docs Version Narrative Update

## Summary

Updated root documentation to reflect the current V11.30 observation state.

## Files Updated

- `README.md`
- `STRATEGY_GUIDE.md`
- `DEPLOY.md`
- `LIVE_TRADING.md`

## Narrative Changes

Current positioning:

- V11.30 is the current observation candidate.
- V11.30 has `0` trades and `0` orders.
- V11.30 market data content is stale and must be fixed before judging strategy
  quality.
- V11.29 is a previous investigation target.
- V10.8.2 remains benchmark evidence only.
- V6.x docs are historical and must not be used as current operation manuals.

## Safety Changes

`DEPLOY.md` and `LIVE_TRADING.md` now explicitly say their body content is
historical and not current V11.30 authority.

## What Was Not Done

This task did not:

- modify strategy code;
- modify bot config;
- modify dashboard code;
- modify deploy scripts;
- read secrets;
- start, stop, or restart bots;
- run backtests.

## Validation

Performed a text scan for stale root-doc current-state wording and corrected the
remaining root-doc `V11.29` current reference.

## Next

Proceed with:

```text
Task 100: V11.30 Go / No-Go Evidence Review
```
