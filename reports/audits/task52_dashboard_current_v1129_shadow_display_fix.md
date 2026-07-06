# Task 52: Dashboard Current V11.29 Shadow Display Fix

## Summary

Updated the dashboard display model so the web side reflects the current runtime
topology:

- `freqtrade-v1129` remains the API-backed current V11.29 bot on
  `localhost:8122`;
- `freqtrade-v1129-ranging-short-shadow` is displayed as a SQLite/log
  observation bot;
- stopped `freqtrade-v1082` is no longer part of the default active dashboard
  comparison.

The fix avoids adding plaintext API credentials for the shadow bot. The shadow
bot remains API-disabled and is represented through its dry-run SQLite DB.

## Why This Was Needed

After Task 51, the runtime topology changed:

```text
freqtrade-v1129: running, API on 127.0.0.1:8122
freqtrade-v1129-ranging-short-shadow: running, no API, SQLite/log observation
freqtrade-v1082: stopped
```

The dashboard code still assumed the old API-only bot model. That made the web
view incomplete or misleading for the shadow strategy because the shadow bot has
no API endpoint.

## Local Changes

```text
dashboard/lib/config.js
dashboard/server.js
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
reports/audits/task52_dashboard_current_v1129_shadow_display_fix.md
tasks/active/TASK-0052-dashboard-current-v1129-shadow-display-fix.md
```

## Dashboard Behavior

Default dashboard bot sources are now:

```text
v1129: API, http://localhost:8122
v1129_shadow: SQLite, user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
```

The SQLite-only shadow summary includes:

- strategy name;
- dry-run mode;
- running state label;
- max open trades;
- stake amount;
- open trade count;
- closed trade count;
- orders count;
- open trade rows if present.

Comparison is intentionally marked not ready when one side is SQLite-only,
because SQLite observation alone is not the same as full Freqtrade API
profit/balance telemetry.

## Guard Change

Added exact dashboard exceptions only for:

```text
dashboard/lib/config.js
dashboard/server.js
```

No broad `dashboard/**` allowance was added.

## Server Deployment

Copied exactly these files to the server:

```text
/home/ubuntu/freqtrade-strategies/dashboard/lib/config.js
/home/ubuntu/freqtrade-strategies/dashboard/server.js
```

Restarted only:

```text
freqtrade-monitor.service
```

No trading bot was started, stopped, or restarted in this task.

## Server Verification

Service state:

```text
freqtrade-monitor.service: active
process: /usr/bin/node /home/ubuntu/freqtrade-strategies/dashboard/server.js
listener: 0.0.0.0:8090
```

Runtime bot sources from deployed code:

```json
[
  {
    "key": "v1129",
    "label": "V11.29 current",
    "source": "api",
    "url": "http://localhost:8122",
    "dbFile": null
  },
  {
    "key": "v1129_shadow",
    "label": "V11.29 ranging-short shadow",
    "source": "sqlite",
    "url": null,
    "dbFile": "/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite"
  }
]
```

Recent dashboard service logs showed no `ERROR`, `Exception`, `TypeError`, or
`SyntaxError` after restart.

## Validation

Local validation:

```text
node --check dashboard/lib/config.js
node --check dashboard/server.js
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Server validation:

```text
node --check /home/ubuntu/freqtrade-strategies/dashboard/lib/config.js
node --check /home/ubuntu/freqtrade-strategies/dashboard/server.js
systemctl restart freqtrade-monitor.service
systemctl is-active freqtrade-monitor.service
```

## Explicit Non-Actions

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print or copy dashboard credentials;
- add API credentials to the shadow bot;
- start, stop, or restart trading bots;
- modify strategies;
- modify existing current V11.29 config;
- modify V10.8.2 files;
- run backtests;
- commit the server worktree.

## Known Limitation

The shadow bot still has no API/web endpoint. The web dashboard can show
SQLite-derived execution sample state, but it cannot show API-only Freqtrade
fields such as wallet balance, API latency, or `/status` open-trade payloads
for the shadow bot unless a later secret-safe API config task enables local
API authentication.

## Recommended Task 53

Recommended next task:

```text
Task 53: V11.29 Shadow First Web Observation Check
```

Task 53 should verify, with authorized dashboard access or server-side
read-only probes, that the web page shows:

- `V11.29 current`;
- `V11.29 ranging-short shadow`;
- no active `V10.8.2` API error card;
- shadow SQLite orders/trades counts;
- no dashboard service errors after several refresh cycles.
