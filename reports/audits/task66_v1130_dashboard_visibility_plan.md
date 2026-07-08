# Task 66: V11.30 Dashboard Visibility Plan

## Summary

Reviewed the local dashboard code path and produced a plan to make V11.30
visible without adding an API server or exposing new credentials.

Conclusion:

- V11.30 should be displayed as an active dry-run shadow using SQLite/log
  observation.
- V11.30 should not be treated as an API bot unless a later secret-safe API
  task explicitly authorizes it.
- The current dashboard config still lists the old `v1129_shadow` SQLite bot and
  does not list V11.30.

This task is plan-only. It did not modify dashboard code or restart the
dashboard service.

## Inputs Reviewed

- `dashboard/lib/config.js`
- `dashboard/server.js`
- `dashboard/public/app.js`
- Task 63 runtime evidence
- Task 64 first observation evidence
- Task 65 telemetry gap audit

## Current Dashboard Bot Model

Current `BOTS` in `dashboard/lib/config.js`:

1. `v1129`
   - label: `V11.29 current`
   - source: API
   - URL: `http://localhost:8122`

2. `v1129_shadow`
   - label: `V11.29 ranging-short shadow`
   - source: SQLite
   - DB:
     `user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite`

Problem:

- Task 63 stopped `freqtrade-v1129-ranging-short-shadow`;
- Task 63 started `freqtrade-v1130-crash-rebound-shadow`;
- dashboard config has not been updated to show the new active shadow;
- V11.30 has no REST API port by design.

## Existing Useful Dashboard Capabilities

`dashboard/server.js` already has:

- `loadSqliteBot(bot)` for read-only SQLite bot status;
- `loadSqliteBotTrades(bot, limit)` for SQLite closed trades;
- `/api/summary`;
- `/api/trades`;
- `/api/market`;
- `/api/v11-high-attack-report`;
- `/api/v11-closed-loop-report`.

The SQLite loader can expose:

- trade count;
- open trade count;
- closed trade count;
- orders count;
- DB mtime as a rough bot start/update time;
- strategy label;
- runmode;
- dry-run status.

## Current Visibility Gaps

| Gap | Cause | Recommended Handling |
|---|---|---|
| V11.30 not shown as active shadow | `BOTS` does not include V11.30 | add exact SQLite bot entry |
| old V11.29 shadow may still show | `BOTS` still includes `v1129_shadow` | replace with V11.30 or mark old as archived |
| V11.30 analyzed candles unavailable | no `api_server` on V11.30 | use V11.29/Binance candles for chart until a read-only replay report exists |
| V11.30 gate states unavailable | dataframe-only column not persisted | add a future generated telemetry report, not API credentials |
| `/api/market` can still depend on V11.29 API | chart source selects API bot for 15m/1h | keep as market source but label clearly |
| `/api/v11-*` report wording is stale | report paths still use V11.29 candidate files | create a V11.30 report route or alias later |

## Proposed Dashboard Change Scope

Future implementation task should modify only:

- `dashboard/lib/config.js`
- `dashboard/server.js` if route/label semantics need adjustment
- `dashboard/public/app.js` if UI labels need adjustment
- focused dashboard tests
- audit/task records

Do not modify:

- strategy files;
- bot config files;
- deploy scripts;
- secret/env files;
- live/server process state unless separately authorized.

## Proposed V11.30 SQLite Bot Entry

Draft:

```js
{
  key: "v1130_shadow",
  label: "V11.30 crash-rebound shadow",
  source: "sqlite",
  botName: "V11.30 crash-rebound shadow",
  strategy: "RegimeAwareV1130CrashReboundShadow",
  runmode: "dry_run",
  dryRun: true,
  state: "running",
  maxOpenTrades: 2,
  stakeAmount: 250,
  stakeCurrency: "USDT",
  dbFile: process.env.BOT_V1130_SHADOW_DB_FILE
    || path.join(PROJECT_DIR, "user_data", "tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite"),
}
```

Recommended bot order:

1. `v1129` as current/main API bot;
2. `v1130_shadow` as active shadow SQLite bot.

The old `v1129_shadow` should not remain in the default comparison because that
container is stopped.

## Market Chart Plan

Short-term:

- keep `/api/market` candles sourced from `v1129` API or Binance fallback;
- do not pretend those candles are V11.30 analyzed dataframe;
- display V11.30 orders/trades from SQLite when present.

Medium-term:

- add a generated V11.30 gate replay report from Task 68;
- use that report for V11.30 markers/gate labels instead of needing a V11.30
  REST API.

## Report Route Plan

Current report routes exist in local code:

- `/api/v11-high-attack-report`
- `/api/v11-closed-loop-report`

But they still point to V11/V11.29 report paths. Future dashboard work should:

- keep these routes backward-compatible;
- add V11.30-specific route or payload section;
- avoid returning 404 when reports are absent; use `available: false` JSON;
- avoid claiming V11.30 replacement readiness.

If the deployed dashboard currently returns 404 for these local-code routes,
the deployed service is likely not running this committed code or is serving a
different artifact. Verify service code path before patching application logic.

## Validation Plan For Future Implementation

Run locally:

```powershell
node --check dashboard/lib/config.js
node --check dashboard/server.js
node --test tests/test_dashboard_interpretation.js tests/test_monitor_store.js
.\scripts\run_agent_readiness_checks.ps1
```

Run server-side only after explicit authorization:

```bash
cd /home/ubuntu/freqtrade-strategies
node --check dashboard/lib/config.js
node --check dashboard/server.js
sudo systemctl restart freqtrade-monitor.service
curl -sS http://localhost:8090/api/summary
curl -sS 'http://localhost:8090/api/trades?limit=20'
```

Do not read dashboard password or secret env files during this task.

## Recommended Next Task

Recommended dashboard task:

```text
Task 71: Dashboard Current Strategy Display Alignment
```

But before changing dashboard code, the runtime-observation sequence should
continue:

```text
Task 67: V11.30 Live Candle Data Freshness Audit
Task 68: V11.30 Live Gate Replay On Latest Candles
```

Reason:

- dashboard visibility can show V11.30 status now;
- gate replay is needed before deciding whether the strategy is too strict.

## Non-Actions

This task did not:

- modify dashboard code;
- restart dashboard service;
- read secrets;
- modify strategy/config;
- run backtests;
- start/stop/restart bots.
