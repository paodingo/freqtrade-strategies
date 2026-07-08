# Task 94R: V11.30 Market Data Refresh Pipeline Diagnosis

## Summary

Diagnosed the V11.30 market data refresh pipeline using read-only checks.

Conclusion:

```text
no_current_safe_automated_v1130_refresh_pipeline
```

The existing cron refresh script is a legacy multi-bot operational script and
should not be used as the V11.30 data freshness solution.

## Evidence Reviewed

- `reports/audits/task73_v1130_data_maintenance_plan_for_stale_local_feather_files.md`
- `reports/audits/task75_v1130_safe_market_data_refresh_dry_run_and_exact_command_approval.md`
- `reports/audits/task77_v1130_market_data_refresh_execution.md`
- `reports/audits/task80_v1130_data_refresh_command_correction.md`
- `reports/audits/task94_market_data_freshness_continuous_audit.md`
- local `scripts/refresh_data.sh`
- server `/home/ubuntu/freqtrade-strategies/scripts/refresh_data.sh`
- server crontab and timer/service inventory
- read-only feather latest-candle inspection

## Current Server Refresh Automation

Crontab contains:

```text
0 */6 * * * /home/ubuntu/freqtrade-strategies/scripts/refresh_data.sh >> /var/log/freqtrade-cron.log 2>&1
* * * * * /home/ubuntu/freqtrade-strategies/scripts/notify_trades.sh >> /home/ubuntu/freqtrade-trade-monitor.log 2>&1
```

No V11.30-specific systemd timer was found.

## Existing Server `scripts/refresh_data.sh`

The deployed refresh script is not V11.30-specific.

Observed properties:

- default config:

```text
/freqtrade/project/user_data/config_multi_futures_v1116.json
```

- default pairs:

```text
BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT BNB/USDT:USDT XRP/USDT:USDT DOGE/USDT:USDT
```

- default bots:

```text
freqtrade-v1116:8109
freqtrade-v1082:8091
freqtrade-v1127:8120
freqtrade-v1129:8122
```

- it runs `ensure_dry_run_bots_started.sh`;
- it runs a V11 closed-loop report builder;
- it runs full system health, trading acceptance, live readiness, and
  opportunity audit gates.

Therefore it is an operational multi-bot maintenance script, not a safe
V11.30-only OHLCV refresh pipeline.

## Current Data Freshness

Read-only check time:

```text
2026-07-08T09:58:48Z
```

15m content:

| pair | latest 15m candle |
|---|---|
| `BTC` | `2026-07-03T08:45:00+00:00` |
| `BNB` | `2026-07-03T08:45:00+00:00` |
| `ETH` | `2026-07-08T06:15:00+00:00` |
| `SOL` | `2026-07-08T06:15:00+00:00` |
| `XRP` | `2026-07-08T06:15:00+00:00` |
| `DOGE` | `2026-07-08T06:15:00+00:00` |
| `LINK` | `2026-07-08T06:15:00+00:00` |
| `BCH` | `2026-07-08T06:15:00+00:00` |

For V11.30's six-pair universe, 15m content remains stale relative to the
server observation time.

Important distinction:

- file mtimes for the six V11.30 pairs were updated around `2026-07-08 14:41`
  server time;
- latest candle content remained `2026-07-08T06:15:00Z`;
- mtime alone must not be used as proof of freshness.

## Root Cause Assessment

Most likely:

1. V11.30 had a one-time corrected refresh in Task 80.
2. No safe V11.30-specific continuous refresh automation was installed.
3. The active cron refresh path still points to a legacy script that is not
   aligned with V11.30 pairs/config and can start old bots / run broad gates.

## Previously Proven Correct Command Shape

Task 80 proved the append-oriented command without `--prepend` can advance the
V11.30 local feather files:

```bash
docker exec freqtrade-v1130-crash-rebound-shadow freqtrade download-data \
  --config /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json \
  --datadir /freqtrade/project/user_data/data \
  --trading-mode futures \
  --timeframes 15m 4h \
  --pairs ETH/USDT:USDT SOL/USDT:USDT DOGE/USDT:USDT LINK/USDT:USDT XRP/USDT:USDT BCH/USDT:USDT \
  --data-format-ohlcv feather
```

This task did not execute the command.

## Safe Refresh Execution Plan

Recommended next task:

```text
Task 94S: Execute one-time V11.30 safe market data refresh
```

Scope:

1. Record pre-refresh latest candle timestamps for V11.30 pairs on `15m` and
   `4h`.
2. Run only the Task 80 corrected command.
3. Do not use `scripts/refresh_data.sh`.
4. Do not use `--prepend`.
5. Do not use `--erase`.
6. Do not start, stop, or restart bots.
7. Do not read `.env` or `user_data/monitor.env`.
8. Record post-refresh latest candle timestamps.
9. Confirm V11.30 and V11.29 containers remain running.
10. Generate an audit report.

## Safe Automation Plan

After one-time refresh succeeds, create a separate plan for automation:

```text
Task 94T: V11.30 market data refresh automation plan
```

Do not reuse the current cron script directly. A future automation should be a
dedicated V11.30 OHLCV-only script or systemd timer with explicit pair/config
scope and no bot lifecycle side effects.

## Forbidden Actions

This task did not and does not authorize:

- running `scripts/refresh_data.sh`;
- bot start/stop/restart;
- `docker restart`, `docker stop`, `docker start`;
- `freqtrade trade`;
- `--erase`;
- strategy edits;
- bot config edits;
- dashboard edits;
- deploy edits;
- secret reads;
- backtests.

## Next Recommendation

Proceed with:

```text
Task 94S: Execute one-time V11.30 safe market data refresh
```

Then rerun:

```text
Task 88/91 style V11.30 telemetry and decision trace after fresh data
```
