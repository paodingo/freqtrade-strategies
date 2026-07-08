# Task 94U: V11.30 OHLCV-Only Market Data Refresh Script

## Summary

Implemented the local V11.30 OHLCV-only market data refresh script and added an
exact harness guard exception for that path.

Result:

```text
v1130_refresh_script_ready_for_server_install_plan
```

This task did not install the script on the server, did not modify cron or
systemd, and did not execute the script.

## Files Changed

- `scripts/guard_harness_diff.js`
- `docs/harness/change_surface_matrix.md`
- `scripts/refresh_v1130_market_data.sh`
- `reports/audits/task94u_v1130_market_data_refresh_script.md`
- `tasks/active/TASK-0094U-v1130-market-data-refresh-script.md`

## Guard Exception

Added exactly one new low-risk path exception:

```text
scripts/refresh_v1130_market_data.sh
```

No broad rule was added.

Not allowed:

- `scripts/refresh_*.sh`
- `scripts/*v1130*.sh`
- `scripts/**`
- generic server/deploy/dashboard paths

## Script Scope

The script targets only:

```text
container: freqtrade-v1130-crash-rebound-shadow
config: /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json
datadir: /freqtrade/project/user_data/data
timeframes: 15m, 4h
pairs: ETH, SOL, DOGE, LINK, XRP, BCH futures
```

It runs:

```text
freqtrade download-data
```

with `--data-format-ohlcv feather`.

It then runs a read-only Python latest-candle inspection inside the same
container.

## Safety Properties

The script does not contain:

- `--prepend`
- `--erase`
- bot start logic
- bot stop logic
- bot restart logic
- `freqtrade trade`
- backtest commands
- dashboard commands
- deploy commands
- strategy edits
- bot config edits
- secret-file reads

The script only checks whether the V11.30 container is already running. If the
container is not running, it exits non-zero.

## Validation

Commands run:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
bash -n scripts/refresh_v1130_market_data.sh
Select-String -Path scripts/refresh_v1130_market_data.sh -Pattern "docker start|docker stop|docker restart|freqtrade trade|--prepend|--erase"
node scripts/guard_harness_diff.js scripts/refresh_v1130_market_data.sh
node scripts/guard_harness_diff.js scripts/refresh_v1130_other.sh
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Observed validation result:

```text
guard_harness_diff syntax: pass
guard_trading_surface syntax: pass
Git Bash syntax check for scripts/refresh_v1130_market_data.sh: pass
forbidden command scan: no matches
exact allowed path self-test: pass with exit code 0
similar non-allowed refresh path self-test: blocked with exit code 1
readiness: pass
Git-visible files: only Task 94U authorized paths
```

## What Was Not Done

This task did not:

- log in to the server;
- copy the script to the server;
- install cron;
- install systemd units;
- run the script;
- run a data refresh;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- modify strategies;
- modify bot configs;
- modify dashboard;
- modify deploy files;
- read secrets;
- modify the original dirty worktree.

## Recommended Next Task

Proceed with:

```text
Task 94V: Install and verify V11.30 market data refresh timer
```

Task 94V should copy/install this exact script on the server, wire a dedicated
timer or narrow cron entry, run one controlled cycle, and confirm candle-content
freshness after the timer fires.
