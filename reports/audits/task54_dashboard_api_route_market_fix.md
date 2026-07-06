# Task 54: Dashboard API Route and Market Fallback Fix

## Summary

Investigated the dashboard failures reported after the V11.29 shadow display
change:

```text
/api/market?timeframe=15m&limit=240 -> 500 Internal Server Error
/api/v11-high-attack-report -> 404 Not Found
/api/v11-closed-loop-report -> 404 Not Found
```

Root causes:

1. The deployed frontend still requests the V11 report endpoints, but the clean
   dashboard server did not include those routes.
2. The market route could still return 500 when the selected Freqtrade API
   source failed and Binance Futures fallback also timed out.
3. The chart source selector still had old V6-era assumptions and did not
   explicitly choose an API-backed current V11.29 bot.

## Fix

Updated:

```text
dashboard/server.js
```

Changes:

- added `/api/v11-high-attack-report`;
- added `/api/v11-closed-loop-report`;
- restored safe missing-report fallback payloads for those endpoints;
- changed chart source selection to prefer API-backed `v1129`;
- prevented SQLite-only shadow from being used as a Freqtrade candle API
  source;
- made `/api/market` return structured empty/fallback data instead of 500 when
  both Freqtrade candle API and Binance fallback fail.

## Local Reproduction

Using a temporary local dashboard password and an intentionally unreachable
`BOT_V1129_URL`, all three reported endpoints returned 200 after the fix:

```text
/api/market?timeframe=15m&limit=24 => 200
/api/v11-high-attack-report => 200
/api/v11-closed-loop-report => 200
```

## Server Deployment

Copied exactly:

```text
dashboard/server.js
```

to:

```text
/home/ubuntu/freqtrade-strategies/dashboard/server.js
```

Then restarted only:

```text
freqtrade-monitor.service
```

Server status:

```text
freqtrade-monitor.service: active
```

Unauthenticated probes correctly returned 401 before route execution:

```text
/api/market?timeframe=15m&limit=24 -> 401 Unauthorized
/api/v11-high-attack-report -> 401 Unauthorized
/api/v11-closed-loop-report -> 401 Unauthorized
```

Recent service logs after restart showed no:

```text
ERROR
Exception
TypeError
SyntaxError
no such column
Internal Server Error
Unhandled
Cannot
aborted
failed
```

## Boundaries

This task did not:

- read dashboard password;
- read `.env`;
- read `user_data/monitor.env`;
- print or copy credentials;
- modify strategies;
- modify bot configs;
- start, stop, or restart trading bots;
- run backtests;
- commit the server worktree.

## Validation

```text
node --check dashboard/server.js
local temporary-auth endpoint reproduction
node --check /home/ubuntu/freqtrade-strategies/dashboard/server.js
systemctl restart freqtrade-monitor.service
systemctl is-active freqtrade-monitor.service
.\scripts\run_agent_readiness_checks.ps1
```

## Next Check

Open the dashboard with a hard refresh and confirm these no longer appear in
the browser network panel:

```text
/api/market?timeframe=15m&limit=240 500
/api/v11-high-attack-report 404
/api/v11-closed-loop-report 404
```

If a display issue remains after these endpoint fixes, the next investigation
should focus on frontend render assumptions in the older deployed
`dashboard/public/app.js`.
