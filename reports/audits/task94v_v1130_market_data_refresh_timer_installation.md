# Task 94V: V11.30 Market Data Refresh Timer Installation

## Summary

Installed and verified a dedicated V11.30 market data refresh timer on the
server.

Result:

```text
v1130_market_data_refresh_timer_installed_and_verified
```

The timer uses the Task 94U OHLCV-only script and does not run the legacy
`scripts/refresh_data.sh`.

## Local Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting commit: `a4d62c4`
- Starting `git status --short --untracked-files=all`: empty
- Local readiness before server work: passed

## Server

Server identity:

```text
host: 43.134.72.69
user: ubuntu
hostname: VM-0-8-ubuntu
initial check time UTC: 2026-07-08T10:17:02Z
systemd: 255
```

Relevant container state before install:

```text
freqtrade-v1130-crash-rebound-shadow: Up 7 hours
freqtrade-v1129: Up 4 days
```

Relevant container state after verification:

```text
freqtrade-v1130-crash-rebound-shadow: Up 8 hours
freqtrade-v1129: Up 4 days
```

No bot start, stop, or restart command was executed.

## Installed Script

Copied the committed local script to:

```text
/home/ubuntu/freqtrade-strategies/scripts/refresh_v1130_market_data.sh
```

Installed permissions:

```text
-rwxr-xr-x ubuntu ubuntu
```

Validation:

```text
bash -n /home/ubuntu/freqtrade-strategies/scripts/refresh_v1130_market_data.sh: pass
```

The server copy was normalized to LF line endings.

## Installed Systemd Units

Installed:

```text
/etc/systemd/system/freqtrade-v1130-market-data-refresh.service
/etc/systemd/system/freqtrade-v1130-market-data-refresh.timer
```

Service:

```ini
[Unit]
Description=Freqtrade V11.30 OHLCV-only market data refresh
Wants=docker.service
After=docker.service

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/freqtrade-strategies
ExecStart=/home/ubuntu/freqtrade-strategies/scripts/refresh_v1130_market_data.sh
```

Timer:

```ini
[Unit]
Description=Run V11.30 market data refresh shortly after 15m candle close

[Timer]
OnCalendar=*:02/15
Persistent=true
Unit=freqtrade-v1130-market-data-refresh.service

[Install]
WantedBy=timers.target
```

Timer status after install:

```text
Loaded: loaded
Active: active (waiting)
Initial trigger shown: 2026-07-08 18:32:00 CST
```

## Manual Service Verification

Before manual service run:

```text
checked_at_utc: 2026-07-08T10:18:10Z
15m latest candle: 2026-07-08T09:45:00Z
4h latest candle: 2026-07-08T04:00:00Z
```

Manual command:

```text
sudo systemctl start freqtrade-v1130-market-data-refresh.service
```

Result:

```text
Result=success
ExecMainStatus=0
ActiveState=inactive
SubState=dead
```

After manual service run:

```text
checked_at_utc: 2026-07-08T10:18:59Z
15m latest candle: 2026-07-08T10:00:00Z
4h latest candle: 2026-07-08T04:00:00Z
```

All six V11.30 pairs reported the same latest candle values:

- `ETH`
- `SOL`
- `DOGE`
- `LINK`
- `XRP`
- `BCH`

## Automatic Timer Verification

The automatic timer later triggered successfully.

Observed status:

```text
check time UTC: 2026-07-08T11:22:18Z
LastTriggerUSec: 2026-07-08 19:17:01 CST
NextElapseUSecRealtime: 2026-07-08 19:32:00 CST
timer ActiveState: active
timer SubState: waiting
service Result: success
service ExecMainStatus: 0
```

After the automatic timer run:

```text
checked_at_utc: 2026-07-08T11:22:19Z
15m latest candle: 2026-07-08T11:00:00Z
4h latest candle: 2026-07-08T04:00:00Z
```

All six V11.30 pairs reported:

```text
15m rows: 88269
15m latest_date: 2026-07-08T11:00:00+00:00
4h rows: 5516
4h latest_date: 2026-07-08T04:00:00+00:00
```

This confirms the timer can refresh candle content without manual execution.

## Legacy Cron Status

The legacy cron entries were not edited in this task.

While checking cron state, the command output included notification routing
environment variables. Their values are intentionally not reproduced in this
report. Future tasks should avoid printing full crontab when notification or
credential-like routing variables may be present; use filtered checks instead.

The V11.30 timer does not depend on the legacy cron path.

## Safety Confirmation

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print API keys, exchange credentials, server keys, dashboard passwords, or
  tokens in the report;
- start, stop, or restart any bot;
- run `freqtrade trade`;
- run a backtest;
- modify strategies;
- modify bot configs;
- modify dashboard files;
- modify deploy files;
- modify the original Windows dirty worktree.

The server-side refresh script scan found no matches for:

```text
docker start
docker stop
docker restart
freqtrade trade
--prepend
--erase
.env
monitor.env
```

## Remaining Risk

The timer is now installed and verified, but V11.30 still needs a fresh
observation pass after stable data refresh. This task does not prove that
V11.30 should trade, does not prove strategy quality, and does not make a
replacement decision.

## Recommended Next Task

Proceed with:

```text
Task 95R: Rerun V11.30 telemetry and decision trace after fresh data automation
```

That task should regenerate the V11.30 observation/decision reports using fresh
market data and determine whether zero-trade behavior is still caused by
strategy gates rather than stale data.
