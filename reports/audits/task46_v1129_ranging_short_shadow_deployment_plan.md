# Task 46: V11.29 Ranging-Short Shadow Deployment Plan

## Summary

This task defines a plan for deploying the V11.29 ranging-short shadow bot as a
separate dry-run observation lane.

It is plan-only. It does not log in to the server, does not copy files to the
server, does not create a container, does not start/stop/restart any bot, does
not run `freqtrade trade`, does not run backtests, and does not modify strategy
or bot config files.

## Current Clean Worktree State

```text
branch: codex/btc-mvp-system-harnessed
readiness: pass
working tree: clean before Task 46 edits
```

## Deployment Objective

Start a separate dry-run-only shadow lane to observe whether the Task 45
pair-filtered ranging-short strategy produces real candidates, orders, and
trades without touching the current V10.8.2 benchmark bot or the current
V11.29 bot.

The lane must not be used for replacement decisions until it has enough real
dry-run evidence.

## Exact Local Source Files

```text
strategies/RegimeAwareV1129RangingShortShadow.py
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

These files were created in Task 45 and are the only strategy/config inputs for
the shadow lane.

## Proposed Runtime Identity

```text
container_name: freqtrade-v1129-ranging-short-shadow
bot_label: V11.29 ranging-short shadow
trade_supervisor_bot_key: v1129_shadow
api_port: 8123
api_bind: 127.0.0.1
mode: dry-run only
```

The proposed API port must be checked before start. It must not replace or
reuse existing bot ports.

## Proposed Server Paths

Project root inside container:

```text
/freqtrade/project
```

Strategy path inside container:

```text
/freqtrade/project/strategies/RegimeAwareV1129RangingShortShadow.py
```

Config path inside container:

```text
/freqtrade/project/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

SQLite dry-run database path:

```text
/freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
```

The shadow lane must not use:

```text
/freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite
/freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite
```

## Required Pre-Start Checks

Before any authorized server start task, verify:

```text
hostname
date
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
test -f /freqtrade/project/strategies/RegimeAwareV1129RangingShortShadow.py
test -f /freqtrade/project/user_data/config_multi_futures_v1129_ranging_short_shadow.json
test ! -f /freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
```

The DB existence check is informational. If the DB already exists, do not
delete it automatically. Stop and require an explicit decision to preserve,
snapshot, or rotate it.

Config validation should confirm:

```text
dry_run = true
strategy = RegimeAwareV1129RangingShortShadow
api_server.listen_port = 8123
db_url = sqlite:////freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
pair_whitelist = ETH/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, BCH/USDT:USDT, XRP/USDT:USDT
```

## Proposed Safe Copy Plan

Only if a later task explicitly authorizes server file copy:

```powershell
scp -i D:\key\openclaw strategies\RegimeAwareV1129RangingShortShadow.py ubuntu@43.134.72.69:/tmp/RegimeAwareV1129RangingShortShadow.py
scp -i D:\key\openclaw user_data\config_multi_futures_v1129_ranging_short_shadow.json ubuntu@43.134.72.69:/tmp/config_multi_futures_v1129_ranging_short_shadow.json
```

Then move into final paths with explicit server-side commands authorized in
that later task.

Do not copy `.env`, `user_data/monitor.env`, dashboard secrets, API keys,
exchange credentials, or SSH keys.

## Proposed Container Start Draft

This is a draft only and must not be executed in Task 46:

```bash
docker run -d \
  --name freqtrade-v1129-ranging-short-shadow \
  --restart unless-stopped \
  -v /freqtrade/project:/freqtrade/project \
  -w /freqtrade/project \
  -p 127.0.0.1:8123:8123 \
  freqtradeorg/freqtrade:stable \
  trade \
  --config /freqtrade/project/user_data/config_multi_futures_v1129_ranging_short_shadow.json \
  --strategy RegimeAwareV1129RangingShortShadow \
  --strategy-path /freqtrade/project/strategies
```

A later execution task must verify the actual image, volume layout, and
existing deployment pattern before using or adapting this draft.

## Monitoring Plan

After an explicitly authorized start task, observe:

```text
container running state
API health on localhost:8123
bot state
SQLite file size and mtime
trades count
orders count
candidate / gate telemetry if available
blocked_missing_alpha_filter count if exported
blocked_alpha_short count if exported
enabled_shadow_ranging_short count if exported
```

Observation windows:

```text
1d: process/API stability and first evidence check
3d: candidate/order/trade health
7d: minimum dry-run evidence window
14d: preferred evidence window if resources allow
```

## Rollback Plan

If a later authorized deployment causes resource pressure or API instability:

1. Stop only the shadow container.
2. Do not stop V10.8.2 or current V11.29 unless separately authorized.
3. Preserve the shadow SQLite DB for audit.
4. Preserve container logs for audit.
5. Record the reason and exact timestamp.

Forbidden automatic rollback actions:

```text
docker stop freqtrade-v1082
docker stop freqtrade-v1129
docker restart any existing benchmark/current bot
rm SQLite files
edit strategy/config files on server
```

## Explicit Non-Actions In This Task

This task did not:

- log in to the server;
- run SSH;
- copy files;
- start, stop, or restart containers;
- run `freqtrade trade`;
- run a backtest;
- refresh market data;
- write SQLite;
- read `.env`;
- read `user_data/monitor.env`;
- read or print credentials;
- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`, `dashboard/**`, or `deploy/**`;
- modify the original dirty workspace.

## Recommended Task 47

Recommended next task:

```text
Task 47: V11.29 Ranging-Short Shadow Server Preflight
```

Task 47 should be read-only server preflight unless explicitly expanded. It
should verify server layout, existing container names, image names, available
ports, file placement requirements, and whether the server has enough resource
headroom to start the shadow bot.
