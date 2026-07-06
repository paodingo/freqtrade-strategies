# TASK-0053: Dashboard Shadow SQLite Schema Fix

## Status

Completed.

## Objective

Fix the dashboard SQLite-only shadow loader so it can display Freqtrade SQLite
schemas without `open_timestamp`.

## Files Modified

```text
dashboard/server.js
reports/audits/task53_dashboard_shadow_sqlite_schema_fix.md
tasks/active/TASK-0053-dashboard-shadow-sqlite-schema-fix.md
```

## Result

The shadow loader now uses available timestamp/date/id columns instead of
assuming `open_timestamp` exists.

## Validation

```text
node --check dashboard/server.js
local /api/summary reproduction with temporary auth
server node --check
systemctl restart freqtrade-monitor.service
systemctl is-active freqtrade-monitor.service
```
