# Task 94T: V11.30 Market Data Refresh Automation Plan

## Summary

Created a safe automation plan for V11.30 market data refresh.

Conclusion:

```text
plan_only_ready_for_implementation_task
```

Task 94S proved that the approved one-time command can advance V11.30 market
data. This task defines how to automate that refresh without reusing the legacy
multi-bot maintenance script and without introducing bot lifecycle side
effects.

This task did not install cron, did not create a timer, did not modify server
files, and did not run a data refresh.

## Evidence Reviewed

- `reports/audits/task94_market_data_freshness_continuous_audit.md`
- `reports/audits/task94r_v1130_market_data_refresh_pipeline_diagnosis.md`
- `reports/audits/task94s_v1130_one_time_safe_market_data_refresh.md`
- local `scripts/refresh_data.sh`
- local harness guard surfaces

## Current State

Task 94 found V11.30 market data content was stale:

```text
15m latest candle: 2026-07-08T06:15:00Z
4h latest candle: 2026-07-08T00:00:00Z
```

Task 94S executed the approved one-time refresh command and advanced the data:

```text
15m latest candle: 2026-07-08T09:45:00Z
4h latest candle: 2026-07-08T04:00:00Z
```

Remaining gap:

```text
no_dedicated_v1130_continuous_refresh_automation
```

## Why the Existing Refresh Script Must Not Be Reused

The current `scripts/refresh_data.sh` is not a V11.30-specific data refresh
tool.

Local script properties observed:

- config points to historical BTC/V6.x style configuration;
- pair scope is `BTC/USDT:USDT`;
- timeframes include `15m 1h 4h`;
- bot list contains historical V6.5/V6.6 containers;
- it contains bot lifecycle logic and can start containers.

Task 94R also found the deployed server script is broader than a data refresh:

- default config is old/non-V11.30;
- default bot set includes older bots;
- it can run bot lifecycle checks;
- it can run broader reports and health gates.

Therefore, it is not safe to modify or reuse this script as the V11.30
automation mechanism.

## Proposed Automation Design

Create a new V11.30-only refresh surface in a future implementation task:

```text
scripts/refresh_v1130_market_data.sh
```

The script should do one thing only:

```text
download V11.30 OHLCV data for the approved V11.30 pair/timeframe universe
```

It must not:

- start, stop, or restart containers;
- run `freqtrade trade`;
- run backtests;
- run dashboard checks;
- run broad system health gates;
- read `.env`;
- read `user_data/monitor.env`;
- print secrets;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files.

## Exact Command Template

The future script should wrap this command shape only:

```bash
docker exec freqtrade-v1130-crash-rebound-shadow freqtrade download-data \
  --config /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json \
  --datadir /freqtrade/project/user_data/data \
  --trading-mode futures \
  --timeframes 15m 4h \
  --pairs ETH/USDT:USDT SOL/USDT:USDT DOGE/USDT:USDT LINK/USDT:USDT XRP/USDT:USDT BCH/USDT:USDT \
  --data-format-ohlcv feather
```

Hard restrictions:

- do not add `--prepend`;
- do not add `--erase`;
- do not broaden pairs without a separate strategy/pair-universe task;
- do not switch config paths without a separate bot-config review task;
- do not call the legacy `scripts/refresh_data.sh`.

## Recommended Script Behavior

Future script behavior:

1. set `set -euo pipefail`;
2. define constants for container, config, datadir, timeframes, and pairs;
3. confirm the target container is running with `docker ps`;
4. record UTC start time;
5. run the exact `freqtrade download-data` command;
6. record UTC end time;
7. optionally run a read-only latest-candle check using Python inside the same
   container;
8. write logs to a dedicated file such as:

```text
/var/log/freqtrade-v1130-market-data-refresh.log
```

The script should exit non-zero if:

- the V11.30 container is not running;
- `download-data` fails;
- latest 15m candle remains older than the expected closed-candle tolerance.

## Freshness Acceptance Rule

For automated monitoring, use candle content, not file mtime.

Recommended acceptance:

- `15m`: latest candle should be within one or two closed-candle intervals of
  current UTC time;
- `4h`: latest candle should be the most recent fully closed 4h candle;
- mtime alone is informational and must not be used as the freshness verdict.

Status labels:

- `fresh`: latest candle is within tolerance;
- `stale`: latest candle is outside tolerance;
- `unknown`: file missing or cannot be read;
- `failed`: command failed.

## Scheduling Recommendation

Use a dedicated systemd timer or a narrow cron entry.

Preferred systemd names:

```text
freqtrade-v1130-market-data-refresh.service
freqtrade-v1130-market-data-refresh.timer
```

Suggested schedule:

```text
every 15 minutes, with a short delay after candle close
```

Example timing:

```text
OnCalendar=*:02/15
```

The timer must run only the dedicated V11.30 refresh script.

It must not run:

- `scripts/refresh_data.sh`;
- `scripts/ensure_dry_run_bots_started.sh`;
- `scripts/start_bot.sh`;
- any dashboard restart command;
- any trading command.

## Safe Cron Draft

If cron is used instead of systemd, use a dedicated entry:

```cron
2,17,32,47 * * * * /home/ubuntu/freqtrade-strategies/scripts/refresh_v1130_market_data.sh >> /var/log/freqtrade-v1130-market-data-refresh.log 2>&1
```

Do not replace or edit existing legacy cron entries in the implementation task
unless there is a separate decommission plan for the old maintenance flow.

## Validation Plan for Implementation Task

The future implementation task should verify:

1. `bash -n scripts/refresh_v1130_market_data.sh`
2. script contains no `docker start`, `docker stop`, or `docker restart`
3. script contains no `freqtrade trade`
4. script contains no `.env` or `monitor.env` reads
5. a one-shot run advances or confirms current candle content
6. V11.30 and V11.29 containers remain running
7. readiness checks pass locally
8. only authorized files are visible in Git

Suggested post-run read-only check:

```bash
docker exec freqtrade-v1130-crash-rebound-shadow python - <<'PY'
import os, pandas as pd, json, time
base = "/freqtrade/project/user_data/data/futures"
pairs = ["ETH", "SOL", "DOGE", "LINK", "XRP", "BCH"]
out = []
for pair in pairs:
    row = {"pair": pair}
    for tf in ["15m", "4h"]:
        path = f"{base}/{pair}_USDT_USDT-{tf}-futures.feather"
        row[tf] = {"exists": os.path.exists(path)}
        if os.path.exists(path):
            df = pd.read_feather(path, columns=["date"])
            row[tf]["latest"] = pd.Timestamp(df["date"].iloc[-1]).isoformat()
            row[tf]["rows"] = int(len(df))
    out.append(row)
print(json.dumps({"checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pairs": out}, indent=2))
PY
```

## Guardrail Requirements

The implementation task will need an explicit guard exception if it creates:

```text
scripts/refresh_v1130_market_data.sh
```

That exception must be exact-path only.

Do not allow:

- `scripts/refresh_*.sh`
- `scripts/*v1130*.sh`
- `scripts/**`
- broad dashboard/deploy/server paths

The guard exception should document that this script is OHLCV-only and has no
bot lifecycle permissions.

## Files Allowed in Future Task

Recommended implementation task allowed files:

```text
scripts/guard_harness_diff.js
docs/harness/change_surface_matrix.md
scripts/refresh_v1130_market_data.sh
reports/audits/task94u_v1130_market_data_refresh_script.md
tasks/active/TASK-0094U-v1130-market-data-refresh-script.md
```

If server installation is authorized separately, use another task:

```text
Task 94V: Install V11.30 market data refresh timer
```

That server task should still avoid bot lifecycle changes.

## Forbidden Future Shortcuts

Do not:

- patch the old `scripts/refresh_data.sh` to include V11.30;
- run old refresh automation and call it fixed;
- let the refresh script start or restart bots;
- combine data refresh with dashboard repair;
- combine data refresh with strategy threshold changes;
- combine data refresh with live replacement decisions;
- use mtime as proof of freshness;
- suppress data staleness alerts without fixing candle content.

## Recommended Next Task

Proceed with:

```text
Task 94U: Implement V11.30 OHLCV-only refresh script
```

Task 94U should only create the local script and exact guard exception.

After Task 94U passes, proceed with:

```text
Task 94V: Install and verify V11.30 market data refresh timer
```

After the timer is installed and observed through at least one cycle, rerun:

```text
Task 88/91 style V11.30 telemetry and decision trace after fresh data
```

Only after fresh data is stable should we continue strategy quality or next
candidate decisions.
