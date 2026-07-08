# Task 71: Dashboard Current Strategy Display Alignment

## Summary

The dashboard default bot list was aligned with the currently running strategy
surface:

- keep `v1129` as the API-backed current bot;
- replace the stopped old `v1129_shadow` SQLite bot with active
  `v1130_shadow`;
- add V11.30 display labels for the crash-rebound entry and exit tags.

This task does not add a V11.30 API server and does not expose or read any new
credentials.

## Files Changed

- `dashboard/lib/config.js`
- `dashboard/server.js`

## Dashboard Bot Alignment

Before:

- `v1129`
- `v1129_shadow`

After:

- `v1129`
- `v1130_shadow`

New SQLite bot entry:

```text
key: v1130_shadow
label: V11.30 crash-rebound shadow
strategy: RegimeAwareV1130CrashReboundShadow
db: user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
source: sqlite
runmode: dry_run
```

## Tag Display Alignment

Added display labels for:

- `v1130_crash_rebound_long`
- `v1130_rebound_take_profit`
- `v1130_rebound_rsi_exit`
- `v1130_rebound_time_exit`

## Server Deployment

Server deployment was limited to:

- copy `dashboard/lib/config.js`;
- copy `dashboard/server.js`;
- restart only `freqtrade-monitor.service`.

This is a dashboard service restart only. It is not a bot restart.

Server validation result:

- `node --check dashboard/lib/config.js`: passed
- `node --check dashboard/server.js`: passed
- `systemctl is-active freqtrade-monitor.service`: `active`

## Boundaries

This task did not:

- modify strategies;
- modify bot configs;
- read secrets;
- start, stop, or restart trading bots;
- run backtests;
- modify the original dirty workspace.

## Validation

Validation commands:

```powershell
node --check dashboard/lib/config.js
node --check dashboard/server.js
node --test tests/test_dashboard_interpretation.js tests/test_monitor_store.js
.\scripts\run_agent_readiness_checks.ps1
```

Server validation after dashboard sync:

```bash
node --check dashboard/lib/config.js
node --check dashboard/server.js
systemctl is-active freqtrade-monitor.service
curl http://localhost:8090/api/summary
```

## Recommended Next Task

Recommended next batch:

```text
Task 72: V11.30 Observation Window Extension
Task 73: V11.30 Data Maintenance Plan For Stale Local Feather Files
Task 74: V11.30 Signal Telemetry Persistence Design
```

Rationale:

- V11.30 needs a longer live observation window;
- stale local data files should be handled explicitly;
- gate telemetry should be persisted instead of only living in dataframe
  columns.
