# Task 35: V11.29 Pre-Filter Signal Reconstruction

## Summary

Implemented and ran the read-only V11.29 pre-filter signal reconstruction generator:

```text
scripts/build_v1129_pre_filter_signal_reconstruction.js
```

Generated:

```text
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md
```

The generator uses SSH to run a read-only Python collector on the server. The collector reads:

- V11.29 runtime dataframe from `localhost:8122/api/v1/pair_candles`;
- sanitized alpha-risk summary from `/freqtrade/project/user_data/monitor_history.sqlite` opened with `mode=ro`.

It does not read `.env`, does not read `user_data/monitor.env`, does not print secrets, does not modify SQLite, does not alter strategies/configs, and does not start/stop/restart bots.

## Reconstruction Result

The generated report identifies:

```text
primary_layer = v102_short_core_pruning
confidence = high
```

Key aggregate counts:

| Metric | Count |
| --- | ---: |
| rows reconstructed | 6156 |
| raw trending long candidates | 1152 |
| raw trending short candidates | 0 |
| raw ranging long candidates | 17 |
| raw ranging short candidates | 111 |
| alpha blocked long candidates | 1169 |
| alpha blocked short candidates | 26 |
| surviving short after alpha | 85 |
| V10.2 ranging blocked by design | 85 |
| V10.2 short-core candidates | 0 |
| final enter_short | 0 |

Interpretation:

- The observed V11.29 window does not contain raw `trending_short` candidates.
- The only reconstructed raw short candidates are `ranging_short`.
- 85 raw short candidates survive alpha filtering, but they are ranging/non-core shorts.
- V10.2 short-core architecture intentionally blocks ranging/non-core shorts, so those 85 surviving short candidates do not become `v102_trending_short_core`.
- Alpha long filtering blocks the long side broadly, but alpha short filtering is not the primary blocker for this reconstructed window because reconstructed raw `trending_short` candidates are absent.
- Later V11 gates are not the primary blocker because no short-core candidates reached them.

## Generated Files

```text
scripts/build_v1129_pre_filter_signal_reconstruction.js
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md
reports/audits/task35_v1129_pre_filter_signal_reconstruction.md
tasks/active/TASK-0035-v1129-pre-filter-signal-reconstruction.md
```

## Validation

Required validation:

```powershell
node --check scripts/build_v1129_pre_filter_signal_reconstruction.js
node scripts/build_v1129_pre_filter_signal_reconstruction.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read or print `user_data/monitor.env`;
- print API key, exchange credentials, server keys, dashboard password, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- copy SQLite;
- modify original dirty workspace.

## Recommended Task 36

Recommended next task:

```text
Task 36: V11.29 Short-Core Condition Calibration Plan
```

Scope:

- Plan how to evaluate whether short-core conditions are currently too restrictive.
- Compare candidate relaxing options without changing live strategy first.
- Consider whether ranging-short candidates should remain intentionally blocked or become a separate small-stake research lane.
- Do not change V11.29 live strategy/config until a plan and guard boundary are approved.
