# Task 96: Dashboard API Contract Inventory

## Summary

Inventoried the dashboard API contract and compared the clean worktree against
the server deployment path.

Conclusion:

```text
dashboard_server_routes_present_and_deployed
```

The three previously reported endpoints are present in both the clean worktree
and deployed server `dashboard/server.js`.

## Endpoints Checked

| endpoint | clean code route | server route |
|---|---|---|
| `/api/market` | present | present |
| `/api/v11-high-attack-report` | present | present |
| `/api/v11-closed-loop-report` | present | present |

## Server File Fingerprints

Clean worktree:

| file | SHA256 |
|---|---|
| `dashboard/server.js` | `76fba75066085c48069c91927cfe66db6fd12bbca61e4195a40aae18c57ad757` |
| `dashboard/lib/config.js` | `c33624653f04b6fe6322931e912979d813518e029124f81ee24636fa0b525a64` |

Server:

| file | SHA256 |
|---|---|
| `/home/ubuntu/freqtrade-strategies/dashboard/server.js` | `76fba75066085c48069c91927cfe66db6fd12bbca61e4195a40aae18c57ad757` |
| `/home/ubuntu/freqtrade-strategies/dashboard/lib/config.js` | `c33624653f04b6fe6322931e912979d813518e029124f81ee24636fa0b525a64` |

Service state:

```text
freqtrade-monitor.service: active
```

## Existing Relevant Prior Fix

Task 54 already added:

- `/api/v11-high-attack-report`;
- `/api/v11-closed-loop-report`;
- `/api/market` fallback behavior;
- chart source selection that avoids using the SQLite-only shadow as a candle
  API source.

## Interpretation

Because the server code matches the clean worktree and routes exist, current
browser symptoms are unlikely to be caused by missing routes in
`dashboard/server.js`.

Remaining possibilities:

- authenticated runtime request returns a route-internal error;
- browser has stale frontend assets;
- frontend render assumptions break after a successful API response;
- dashboard static assets differ from expected browser cache;
- `/api/market` depends on upstream data/API freshness and may still return
  degraded data.

## What Was Not Done

This task did not:

- read dashboard password;
- read `.env`;
- read `user_data/monitor.env`;
- restart `freqtrade-monitor.service`;
- modify dashboard files;
- modify strategy or bot config;
- run backtests.

## Recommended Task 97

Proceed with:

```text
Task 97: Dashboard runtime display verification plan
```

Task 97 should not change code unless it has authenticated, current browser/API
evidence of a concrete render or response-shape bug.
