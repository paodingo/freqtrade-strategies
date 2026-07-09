# Task 147: V11.31 Longer Replay Data Source Inventory Implementation

## Summary

Implemented a read-only V11.31 longer replay data-source inventory report
builder.

Generated outputs:

```text
reports/v1131_observation/v1131_longer_replay_data_source_inventory.json
reports/v1131_observation/v1131_longer_replay_data_source_inventory.md
```

Decision:

```text
longer_replay_data_source_inventory_incomplete
```

## Scope

The generator reads committed local evidence only:

```text
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json
reports/v1130_observation/v1130_watch_only_telemetry_report.json
reports/audits/task136_v1131_longer_replay_window_data_source_authorization.md
```

It does not access the server, download or refresh data, run a backtest, modify
strategy files, modify bot config, read secrets, or perform live/server
operations.

## Result

- `15m` source paths are observed in committed watch-only telemetry.
- Source feather reports show large total row counts, but the committed replay
  still uses only `240` rows per pair, about `2.5` days.
- `7d` and `14d` committed replay coverage remain unavailable.
- Row-level `4h` informative data inventory remains `unknown`.
- Alpha/taker/protection state for the wider window remains `unknown`.
- Backtest reconsideration remains `false`.

## Verification

Verification completed:

```powershell
node --check scripts/build_v1131_longer_replay_data_source_inventory.js
node scripts/build_v1131_longer_replay_data_source_inventory.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Result:

```text
node --check: pass
generator: pass
readiness: pass (9 changed path(s) checked)
git status --short --untracked-files=all: only Task 145/146/147 authorized files
```

## Recommended Next Task

Proceed with:

```text
Task 148: V11.31 Longer Replay Data Acquisition Authorization
```
