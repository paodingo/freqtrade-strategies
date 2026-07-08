# Task 97: Dashboard Runtime Display Verification Plan

## Summary

Evaluated whether a dashboard code change is justified after Task 96.

Decision:

```text
do_not_modify_dashboard_code_without_authenticated_runtime_evidence
```

## Reason

Task 96 confirmed:

- clean `dashboard/server.js` contains the reported routes;
- server `dashboard/server.js` matches clean worktree by SHA256;
- server `dashboard/lib/config.js` matches clean worktree by SHA256;
- `freqtrade-monitor.service` is active.

Therefore a blind code edit is not justified.

## Required Next Evidence

Before modifying dashboard code, collect one of:

1. authenticated `/api/market?timeframe=15m&limit=240` response body and status;
2. authenticated `/api/v11-high-attack-report` response body and status;
3. authenticated `/api/v11-closed-loop-report` response body and status;
4. browser console error and network payload;
5. screenshot showing the exact stale/misleading panel.

This evidence must not expose dashboard password or API credentials.

## Likely Runtime Checks

Use a browser session or temporary user-assisted authenticated probe to verify:

- whether endpoint status is `200`, `401`, `404`, or `500`;
- whether stale frontend assets are loaded;
- whether response JSON shape differs from frontend assumptions;
- whether market data staleness is displayed clearly;
- whether V11.30 is shown as SQLite-only observation rather than API-backed bot.

## No Code Change This Task

No dashboard code was modified because the route surface is already deployed and
the remaining issue requires authenticated runtime evidence.

## Recommended Follow-Up

Proceed with:

```text
Task 97A: Authenticated dashboard runtime probe
```

This should be explicitly authorized to use a safe authenticated browser/session
without printing credentials.
