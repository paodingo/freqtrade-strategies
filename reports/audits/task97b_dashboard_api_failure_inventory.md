# Task 97B: Dashboard API Failure Inventory

## Summary

Ran a narrow dashboard API failure inventory for the reported web issues:

```text
/api/market?timeframe=15m&limit=240 500 Internal Server Error
/api/v11-high-attack-report 404 Not Found
/api/v11-closed-loop-report 404 Not Found
```

Conclusion:

```text
authenticated_runtime_evidence_required_before_dashboard_code_change
```

The clean worktree defines all three routes. The server monitor process is
active and listening on port `8090`. Unauthenticated probes return `401`, which
means this task cannot reproduce the authenticated browser-side `500` or `404`
without a safe authenticated session.

No dashboard code was modified.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting `git status --short --untracked-files=all`: empty
- Readiness before checks: passed

## Local Route Inventory

Clean worktree route definitions:

| route | local status |
|---|---|
| `/api/market` | defined in `dashboard/server.js` |
| `/api/v11-high-attack-report` | defined in `dashboard/server.js` |
| `/api/v11-closed-loop-report` | defined in `dashboard/server.js` |

Frontend call observed:

```text
dashboard/public/app.js calls /api/market?timeframe=<state.chartTimeframe>&limit=240
```

## Server Runtime Probe

Read-only server probe:

| item | observed |
|---|---|
| host | `VM-0-8-ubuntu` |
| date UTC | `2026-07-08T12:55:41Z` |
| service | `freqtrade-monitor.service` |
| service state | `active` |
| active since | `Wed 2026-07-08 11:22:11 CST` |
| port `8090` listening | yes |
| recent monitor journal | no entries in last 2 hours |

Unauthenticated HTTP status:

| endpoint | status |
|---|---|
| `/api/summary` | `401` |
| `/api/market?timeframe=15m&limit=240` | `401` |
| `/api/v11-high-attack-report` | `401` |
| `/api/v11-closed-loop-report` | `401` |

Interpretation:

- The monitor service is up.
- The auth gate is active.
- The unauthenticated probe cannot reach route handlers.
- Authenticated browser-side `500` / `404` still needs authenticated evidence.

## Likely Failure Classes

Possible causes for authenticated `/api/market` `500`:

- `loadMarketCandles` reaches the V11.29 Freqtrade API and receives an error;
- Binance Futures fallback fails or is blocked;
- `MonitorStore.recordDataFreshness` fails while writing monitor history;
- `loadBots` fails while reading V11.30 SQLite or V11.29 API;
- response shaping encounters an unexpected null or malformed payload.

Possible causes for authenticated V11 report `404`:

- browser is hitting a different host, port, or stale deployment;
- static frontend bundle and server route are from different revisions;
- proxy or cache returns a web-server-level `404` before Node route handling;
- authenticated route returns a JSON fallback but frontend or proxy reports it
  as unavailable;
- browser request path differs from the clean-worktree route.

## What This Task Did Not Do

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print dashboard credentials;
- use API credentials;
- modify `dashboard/**`;
- modify `deploy/**`;
- modify bot config;
- modify strategy code;
- start, stop, or restart services;
- run backtests;
- write SQLite;
- change server files.

## Required Next Evidence

Before changing dashboard code, collect at least one of:

1. authenticated browser Network panel status and response body for
   `/api/market?timeframe=15m&limit=240`;
2. authenticated browser Network panel status and response body for
   `/api/v11-high-attack-report`;
3. authenticated browser Network panel status and response body for
   `/api/v11-closed-loop-report`;
4. screenshot showing which panel is stale or wrong;
5. a safe authenticated local curl run that redacts credentials and response
   secrets before saving output.

## Recommended Next Task

Proceed with:

```text
Task 97C: Authenticated dashboard runtime failure probe
```

Task 97C should use an already-authenticated browser/session or user-assisted
credential entry, capture status codes and response bodies, redact secrets, and
only then decide whether dashboard code should be changed.
