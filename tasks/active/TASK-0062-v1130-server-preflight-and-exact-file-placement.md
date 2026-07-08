# TASK-0062: V11.30 Server Preflight And Exact File Placement

## Status

Completed.

## Objective

Perform a read-only server preflight and place exactly the V11.30 crash-rebound
shadow strategy/config files on the server. Do not start or stop bots.

## Allowed Local Files

- `reports/audits/task62_v1130_server_preflight_and_exact_file_placement.md`
- `tasks/active/TASK-0062-v1130-server-preflight-and-exact-file-placement.md`

## Exact Server Files Placed

- `/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1130CrashReboundShadow.py`
- `/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1130_crash_rebound_shadow.json`

## Completed Work

- Verified local branch and clean status.
- Ran local readiness checks.
- Connected to server with `ubuntu@43.134.72.69`.
- Ran read-only server preflight commands.
- Confirmed target repo and target directories exist.
- Confirmed V11.30 target files were missing before placement.
- Copied exactly two V11.30 files.
- Verified server SHA256 hashes match local SHA256 hashes.
- Verified config JSON parses on server.
- Confirmed container list did not change after placement.
- Confirmed server repo shows only the two exact placed files as untracked.

## Resource Finding

Server available memory was about `232Mi`, with about `3.0Gi` swap already used.
This is too tight to start an additional bot in this task.

## Non-Actions

- Did not read secrets.
- Did not run `docker inspect`.
- Did not start, stop, or restart containers.
- Did not run `freqtrade trade`.
- Did not run backtests.
- Did not write SQLite.
- Did not modify dashboard or deploy files.
- Did not commit the server repo.

## Next

Proceed to a separate Task 63 runtime resource decision and shadow start
authorization before starting V11.30.
