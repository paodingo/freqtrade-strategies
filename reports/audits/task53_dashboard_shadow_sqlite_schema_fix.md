# Task 53: Dashboard Shadow SQLite Schema Fix

## Summary

Investigated why the web dashboard still could not correctly display the
V11.29 ranging-short shadow bot after Task 52.

Root cause: the new SQLite-only dashboard loader assumed the shadow SQLite
`trades` table had an `open_timestamp` column. Some Freqtrade SQLite schemas do
not have that column. The loader therefore returned:

```text
no such column: open_timestamp
```

for the shadow card, making the web display look broken even though the shadow
bot itself was running.

## Fix

Updated:

```text
dashboard/server.js
```

The SQLite loader now builds `ORDER BY` from columns that actually exist:

```text
open_timestamp -> open_date -> id -> rowid
close_timestamp -> close_date -> open_timestamp -> open_date -> id -> rowid
```

This keeps the shadow display schema-tolerant without changing strategy,
config, or bot runtime behavior.

## Verification

Local reproduction before fix:

```text
v1129_shadow ok=false
error=no such column: open_timestamp
```

Local reproduction after fix:

```text
v1129_shadow ok=true
source=sqlite
tradeCount=0
ordersCount=0
currentOpenTrades=0
```

Server deployment:

```text
copied dashboard/server.js to /home/ubuntu/freqtrade-strategies/dashboard/server.js
node --check /home/ubuntu/freqtrade-strategies/dashboard/server.js
sudo systemctl restart freqtrade-monitor.service
systemctl is-active freqtrade-monitor.service => active
```

Recent server logs after restart showed no:

```text
ERROR
Exception
TypeError
SyntaxError
no such column
```

## Boundaries

This task did not:

- read dashboard password or secrets;
- read `.env`;
- read `user_data/monitor.env`;
- modify strategies;
- modify bot configs;
- start, stop, or restart trading bots;
- run backtests;
- commit the server worktree.

## Next Check

Open the dashboard with a hard refresh. The active bot cards should now be:

```text
V11.29 current
V11.29 ranging-short shadow
```

The shadow card should show SQLite-derived counts instead of an API error.
