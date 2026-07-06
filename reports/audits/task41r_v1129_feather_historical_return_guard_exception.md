# Task 41R: V11.29 Feather Historical Return Study Guard Exception

## Summary

Added exact guard exceptions for the Task 41 feather-based historical return
study artifacts.

Allowed exact paths:

```text
scripts/build_v1129_feather_ranging_short_historical_return_study.js
reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json
reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.md
```

This does not allow:

- `reports/v1129_execution_validation/**`
- `reports/*v1129*`
- `scripts/build_v1129_*`
- SQLite snapshots
- real execution report wildcard paths
- strategy/config/dashboard/deploy/live/server changes

## Modified Guards

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`

## Boundary Confirmation

This task did not modify strategy code, bot configuration, dashboard, deploy,
secret files, SQLite snapshots, data files, or server state.

## Verification

Required checks:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Recommended Task 41

Proceed to Task 41: V11.29 Feather-Based Ranging-Short Historical Return Study.

