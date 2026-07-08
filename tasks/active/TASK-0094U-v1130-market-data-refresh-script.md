# TASK-0094U: V11.30 OHLCV-Only Market Data Refresh Script

## Status

Completed.

## Objective

Create a dedicated V11.30 OHLCV-only market data refresh script in the clean
worktree and add the exact guard exception needed for it.

## Result

Completed.

Created:

```text
scripts/refresh_v1130_market_data.sh
```

The script uses the approved V11.30 config, six-pair universe, `15m` and `4h`
timeframes, futures trading mode, and feather OHLCV storage.

## Boundaries

- No server install.
- No cron change.
- No systemd change.
- No data refresh execution.
- No bot start/stop/restart.
- No trading command.
- No backtest.
- No strategy change.
- No bot config change.
- No dashboard or deploy change.
- No secrets read.

## Next

Run:

```text
Task 94V: Install and verify V11.30 market data refresh timer
```
