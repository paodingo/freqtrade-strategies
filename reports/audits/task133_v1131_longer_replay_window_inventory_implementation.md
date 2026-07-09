# Task 133: V11.31 Longer Replay Window Inventory Implementation

## Summary

Implemented a read-only V11.31 longer replay window inventory generator.

Generated outputs:

```text
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_longer_replay_window_inventory.md
```

Decision:

```text
longer_window_data_not_yet_available_in_committed_evidence
```

## Scope

The generator reads committed local evidence only:

```text
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json
reports/v1130_observation/v1130_watch_only_telemetry_report.json
reports/audits/task124_v1131_longer_replay_window_acquisition_plan.md
```

It does not access the server, refresh market data, run a backtest, start or stop
any bot, read secrets, modify strategy files, or modify bot config.

## Inventory Result

| item | result |
|---|---|
| 15m committed rows | `1440` |
| 15m rows per pair | `240` |
| 15m approximate days per pair | `2.5` |
| latest committed 15m candle | `2026-07-08T11:30:00.000Z` |
| 7d committed 15m support | `false` |
| 14d committed 15m support | `false` |
| 4h row-level inventory | `unknown` |
| alpha-screened replay enabled | `23` |
| OHLCV watch-only enabled | `29` |
| sample gate | `30` |
| can reconsider backtest | `false` |
| can deploy shadow | `false` |

## Blocking Gaps

- `authorized_longer_15m_window_inventory`
- `authorized_4h_informative_window_inventory`
- `alpha_taker_protection_reconstruction_or_explicit_unknown_marking`
- `sample_count_after_final_filters_at_or_above_gate`
- `per_pair_and_per_day_concentration_review`

## Explicit Non-Conclusion

This task does not conclude that V11.31 is good, bad, profitable, deployable, or
ready to replace V10.8.2, V11.29, or V11.30.

## Verification

Verification completed:

```powershell
node --check scripts/build_v1131_longer_replay_window_inventory.js
node scripts/build_v1131_longer_replay_window_inventory.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Result:

```text
node --check: pass
generator: pass
readiness: pass (9 changed path(s) checked)
git diff --name-only: no tracked diff before staging because all files were new
git status --short --untracked-files=all: only Task 133/134/135 authorized files
```

## Recommended Next Task

Proceed with:

```text
Task 136: V11.31 Longer Replay Window Data Source Authorization
```
