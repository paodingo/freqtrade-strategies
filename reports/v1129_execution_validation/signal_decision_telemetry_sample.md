# V11.29 Signal Decision Telemetry Sample

## Summary

This is a read-only telemetry sample generated from clean-worktree audit
evidence. It does not attach to the live bot, does not read SQLite, does not read
secrets, does not place orders, and does not change strategy or bot
configuration.

- Sample status: `insufficient`
- Can place orders: `false`
- Reads live server: `false`
- Reads secret material: `false`
- Can explain zero trades: `false`

## Data Freshness

Task 28 observed stale local downloaded/fallback futures data:

- Local fallback stale checks: 24
- Live DataProvider freshness checks: 12 marked `unknown`
- Whitelist pairs covered: 12

This means the local downloaded/fallback data set was not real-time updated in
the Task 28 evidence. It does not prove that the running bot lacked live
exchange candles.

## Runtime Context

Runtime context is copied from Task 28 audit evidence and is not refreshed by
this generator:

- API state: `running`
- Run mode: `dry_run`
- Observed trades: `0`
- Observed orders: `0`

## Pair Decision Coverage

Pair decision rows generated: 12

All pair-level signal decisions remain `unknown` because no generated signal
dataframe, strategy callback telemetry, or safe runtime DataProvider probe was
read in this task.

Unknown no-entry reason rows: 12

## Blocking Gaps

- `runtime_dataprovider_freshness_probe`: Need safe read-only proof of live candle timestamps per pair/timeframe.
- `signal_dataframe_probe`: Need final enter_long/enter_short/enter_tag evidence per pair/candle.
- `gate_level_reason_probe`: Need evidence of which inherited V11 gate allowed, retagged, or blocked entries.
- `stake_decision_probe`: Need safe category-only custom stake evidence without balances or secrets.

## What This Sample Cannot Conclude

This sample cannot conclude whether V11.29 received fresh live exchange data,
whether any pair produced entry signals, whether inherited V11 gates blocked or
retagged signals, whether stake sizing blocked orders, or whether V11.29 can be
compared with V10.8.2.

## Recommended Next Task

Task 31: V11.29 Safe Runtime Data Freshness Probe
