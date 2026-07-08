# TASK-0071: Dashboard Current Strategy Display Alignment

## Status

Completed.

## Objective

Align the web dashboard with the currently running strategy surface so it shows
the active V11.30 crash-rebound shadow instead of the stopped old V11.29
ranging-short shadow.

## Allowed Files

- `dashboard/lib/config.js`
- `dashboard/server.js`
- `reports/audits/task71_dashboard_current_strategy_display_alignment.md`
- `tasks/active/TASK-0071-dashboard-current-strategy-display-alignment.md`

## Result

- Dashboard config now includes `v1130_shadow` as a SQLite-backed dry-run
  observation bot.
- V11.30 entry and exit tags have readable dashboard labels.
- Server dashboard files were synced and `freqtrade-monitor.service` is
  `active` after restart.
- No V11.30 API server was added.
- No secret was read.
- No trading bot was started, stopped, or restarted.

## Output

- `reports/audits/task71_dashboard_current_strategy_display_alignment.md`

## Next

Proceed to extended observation and telemetry persistence planning.
