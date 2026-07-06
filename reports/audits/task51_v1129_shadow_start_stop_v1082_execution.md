# Task 51: Stop V10.8.2 and Start V11.29 Ranging-Short Shadow

## Summary

Executed the requested runtime change:

- stopped `freqtrade-v1082`;
- started `freqtrade-v1129-ranging-short-shadow`;
- kept the existing `freqtrade-v1129` container running;
- patched the shadow config to remove the invalid `api_server` block and set
  `initial_state: running`.

The shadow bot is now running in dry-run mode with SQLite/log observation. It
does not expose an API/web surface because no API credentials were added.

## Local Preconditions

```text
cwd: D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
git status before task: clean
readiness before task: pass
```

## Server Runtime Change

Server:

```text
host: 43.134.72.69
user: ubuntu
server time observed: 2026-07-07T03:13:50+08:00
```

Before:

```text
freqtrade-v1129: Up 3 days, 127.0.0.1:8122->8122/tcp
freqtrade-v1082: Up 6 days, 127.0.0.1:8091->8091/tcp
```

After:

```text
freqtrade-v1129-ranging-short-shadow: Up, dry-run, RUNNING
freqtrade-v1129: Up 3 days, unchanged
freqtrade-v1082: Exited (137)
```

## Config Patch

Patched:

```text
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

Changes:

```text
removed api_server block
added initial_state: running
```

Reason:

Freqtrade requires `username`, `password`, and `jwt_secret_key` whenever the
`api_server` object is present, even when `enabled` is false. To avoid adding
plaintext API credentials, the API block was removed and the bot was started
without an API/web surface.

Resulting selected config fields:

```text
strategy: RegimeAwareV1129RangingShortShadow
dry_run: true
initial_state: running
db_url: sqlite:////freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
api_server: absent
pair_whitelist: ETH/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, BCH/USDT:USDT, XRP/USDT:USDT
```

## Shadow Start Evidence

Container:

```text
freqtrade-v1129-ranging-short-shadow
```

Start command shape:

```text
docker run -d --name freqtrade-v1129-ranging-short-shadow \
  --restart unless-stopped \
  -v /home/ubuntu/freqtrade-strategies:/freqtrade/project \
  -w /freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --config /freqtrade/project/user_data/config_multi_futures_v1129_ranging_short_shadow.json \
  --strategy RegimeAwareV1129RangingShortShadow \
  --strategy-path /freqtrade/project/strategies
```

Log evidence:

```text
Using DB: sqlite:////freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
Whitelist with 5 pairs: ETH, AVAX, LINK, BCH, XRP
Changing state to: RUNNING
Bot heartbeat ... state='RUNNING'
Dry run is enabled. All trades are simulated.
```

## V10.8.2 Stop Evidence

```text
docker stop freqtrade-v1082
freqtrade-v1082: Exited (137)
```

No V10.8.2 files were modified.

## Resource Snapshot

After shadow start:

```text
Mem total: 1.9Gi
Mem available: 315Mi to 429Mi observed
Swap used: 2.2Gi observed after restart
```

Container memory snapshot:

```text
freqtrade-v1129-ranging-short-shadow: about 380MiB after steady heartbeat
freqtrade-v1129: about 104MiB after steady heartbeat
```

Resource pressure remains real. This setup should be watched closely.

## Shadow DB Evidence

Shadow SQLite files were created:

```text
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite-wal
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite-shm
```

This task did not write SQLite directly. SQLite was created by the dry-run bot.

## Known Limitation

The shadow bot currently has no API/web surface because the API block was
removed to avoid plaintext credential changes. Monitoring must use:

- container state;
- docker logs;
- SQLite snapshots/queries;
- file mtime/size;
- later secret-safe API config if explicitly authorized.

## Explicit Non-Actions

This task did not:

- stop `freqtrade-v1129`;
- modify V10.8.2 strategy/config files;
- modify current V11.29 strategy/config files;
- read `.env`;
- read `user_data/monitor.env`;
- print or copy API keys, exchange credentials, dashboard passwords, or tokens;
- run backtests;
- run live trading;
- commit the server worktree.

## Validation

Local validation:

```text
config JSON parse: pass
api_server absent: pass
initial_state = running: pass
.\scripts\run_agent_readiness_checks.ps1: pass
```

Server validation:

```text
freqtrade-v1129-ranging-short-shadow: Up
shadow logs: state RUNNING
freqtrade-v1082: Exited
shadow DB files: present
```

## Recommended Task 52

Recommended next task:

```text
Task 52: V11.29 Ranging-Short Shadow First Observation Check
```

Task 52 should inspect, read-only:

- shadow container state;
- recent logs for errors;
- SQLite trades/orders counts;
- whether the new shadow DB mtime is advancing;
- resource pressure after several minutes of runtime;
- whether API/web monitoring should be added via a secret-safe config task.
