# TASK-0094V: V11.30 Market Data Refresh Timer Installation

## Status

Completed.

## Objective

Install and verify a dedicated V11.30 market data refresh timer on the server.

## Result

Completed.

Installed:

```text
/home/ubuntu/freqtrade-strategies/scripts/refresh_v1130_market_data.sh
/etc/systemd/system/freqtrade-v1130-market-data-refresh.service
/etc/systemd/system/freqtrade-v1130-market-data-refresh.timer
```

Timer:

```text
active (waiting)
OnCalendar=*:02/15
Persistent=true
```

Verification:

- manual service run: success;
- automatic timer run: success;
- V11.30 six-pair `15m` data advanced to `2026-07-08T11:00:00Z`;
- V11.30/V11.29 containers remained running.

## Boundaries

- Did not edit legacy cron.
- Did not run `scripts/refresh_data.sh`.
- Did not start, stop, or restart bots.
- Did not run `freqtrade trade`.
- Did not run backtests.
- Did not modify strategies.
- Did not modify bot configs.
- Did not modify dashboard or deploy files.
- Did not read `.env` or `user_data/monitor.env`.

## Note

A cron-state check exposed notification routing variables in command output.
Their values are not reproduced in the audit report. Future server checks
should use filtered crontab inspection when notification routing variables may
be present.

## Next

Run:

```text
Task 95R: Rerun V11.30 telemetry and decision trace after fresh data automation
```
