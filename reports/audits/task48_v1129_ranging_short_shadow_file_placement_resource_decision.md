# Task 48: V11.29 Ranging-Short Shadow File Placement and Resource Decision

## Summary

Performed a bounded read-only server check to decide where the V11.29
ranging-short shadow files should be placed and whether the server has enough
resource headroom to start the shadow bot.

Decision:

- file placement is now identified;
- do not start a third Freqtrade bot yet because memory headroom is too low;
- a later task may copy only the two exact Task 45 files to the identified
  host bind mount, but should still not start the shadow bot without a separate
  resource/start authorization.

This task did not copy files, did not modify server files, did not start,
stop, or restart containers, did not read env files, and did not read secrets.

## Local Preconditions

```text
cwd: D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
git status before task: clean
readiness before task: pass
```

## Server Evidence

```text
host: 43.134.72.69
user: ubuntu
hostname: VM-0-8-ubuntu
server time: 2026-07-07T03:02:40+08:00
```

Running containers:

| Container | Image | Status | Port |
| --- | --- | --- | --- |
| `freqtrade-v1129` | `freqtradeorg/freqtrade:stable` | `Up 3 days` | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1082` | `freqtradeorg/freqtrade:stable` | `Up 6 days` | `127.0.0.1:8091->8091/tcp` |

## Read-Only Commands Used

```text
hostname
date -Is
docker ps --format ...
docker inspect --format '{{json .Mounts}}' freqtrade-v1129
docker inspect --format '{{json .Mounts}}' freqtrade-v1082
ss -ltnp | grep ':8123 ' || true
test/ls exact target paths
find exact V1129-related filenames
df -h /
free -h
docker stats --no-stream --format ...
docker exec ... test/ls exact target paths
```

No full `docker inspect` output was used. No environment files were read.

## File Placement Decision

Both current Freqtrade containers use this bind mount:

```text
Type: bind
Source: /home/ubuntu/freqtrade-strategies
Destination: /freqtrade/project
RW: true
```

Therefore the host-side target paths for the shadow files are:

```text
/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129RangingShortShadow.py
/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

The container-side paths are:

```text
/freqtrade/project/strategies/RegimeAwareV1129RangingShortShadow.py
/freqtrade/project/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

The proposed shadow DB path is:

```text
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
/freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
```

Current status:

| Path | Status |
| --- | --- |
| host strategy target | missing |
| host config target | missing |
| host shadow DB target | missing |
| container strategy target | missing |
| container config target | missing |
| container shadow DB target | missing |

## Existing V11.29 Server Files

Observed existing V11.29-related server files by path/name only:

```text
/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129ResidualDragMicroSizer.py
/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129.json
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129.dryrun.sqlite
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129.dryrun.sqlite-shm
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129.dryrun.sqlite-wal
/home/ubuntu/freqtrade-strategies/reports/live_window_execution_check/v1129_since_20260702-2026-07-03_09-12-49.meta.json
/home/ubuntu/freqtrade-strategies/reports/live_window_execution_check/v1129_since_20260702-2026-07-03_09-12-49.zip
/home/ubuntu/freqtrade-strategies/scripts/run_v1129_residual_drag_micro_sizer_backtests.sh
```

No file contents were read.

## Port Decision

```text
proposed shadow API port: 8123
observed listener on 8123: none
decision: port appears available, re-check immediately before any start
```

## Resource Decision

Disk:

```text
filesystem: /dev/vda2
size: 50G
used: 25G
available: 23G
use: 54%
```

Memory:

```text
total: 1.9Gi
used: 1.7Gi
free: 95Mi
available: 189Mi
swap total: 5.9Gi
swap used: 3.0Gi
swap free: 3.0Gi
```

Container snapshot:

| Container | CPU | Memory | Memory % |
| --- | --- | --- | --- |
| `freqtrade-v1129` | `7.15%` | `371.2MiB / 1.922GiB` | `18.87%` |
| `freqtrade-v1082` | `69.68%` | `460.3MiB / 1.922GiB` | `23.39%` |

Decision:

```text
do not start the shadow bot yet
```

Reason: available memory is below 200MiB and swap is already heavily used.
Starting a third Freqtrade process could degrade the current V10.8.2 benchmark
and V11.29 observation bots.

## Safe Copy Draft For Later Task

Only if a later task explicitly authorizes exact file placement:

```powershell
scp -i D:\key\openclaw\clf.pem strategies\RegimeAwareV1129RangingShortShadow.py ubuntu@43.134.72.69:/tmp/RegimeAwareV1129RangingShortShadow.py
scp -i D:\key\openclaw\clf.pem user_data\config_multi_futures_v1129_ranging_short_shadow.json ubuntu@43.134.72.69:/tmp/config_multi_futures_v1129_ranging_short_shadow.json
```

Then, in the same authorized task, move only those exact files:

```bash
install -m 0644 /tmp/RegimeAwareV1129RangingShortShadow.py /home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129RangingShortShadow.py
install -m 0644 /tmp/config_multi_futures_v1129_ranging_short_shadow.json /home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129_ranging_short_shadow.json
rm -f /tmp/RegimeAwareV1129RangingShortShadow.py /tmp/config_multi_futures_v1129_ranging_short_shadow.json
```

The later task must not copy `.env`, `user_data/monitor.env`, credentials,
dashboard secrets, SQLite snapshots, or unrelated files.

## Start Decision

Do not start the shadow bot in Task 48.

Before any future start task:

1. Re-check memory and swap.
2. Re-check port `8123`.
3. Confirm the two exact shadow files are present.
4. Confirm the shadow DB file does not already exist, or explicitly decide how
   to preserve/rotate it.
5. Confirm whether current V10.8.2 and V11.29 stability is acceptable.
6. Do not stop existing bots unless the task explicitly authorizes that exact
   operation.

## Explicit Non-Actions

This task did not:

- copy files to the server;
- modify server files;
- create the shadow SQLite DB;
- start, stop, or restart containers;
- run `freqtrade trade`;
- run backtests;
- read `.env`;
- read `user_data/monitor.env`;
- print or copy credentials;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- modify the original dirty workspace.

## Recommended Task 49

Recommended next task:

```text
Task 49: V11.29 Ranging-Short Shadow Exact File Placement
```

Task 49 may copy only:

```text
strategies/RegimeAwareV1129RangingShortShadow.py
user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

to:

```text
/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129RangingShortShadow.py
/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

Task 49 should not start the bot. A separate resource/start task should decide
whether a third bot is safe, or whether another nonessential process must be
stopped first with explicit authorization.
