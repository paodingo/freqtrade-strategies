# Task 39R: V11.29 Ranging-Short Return Study Guard Exception

## Summary

Added exact guard exceptions for the Task 39 offline ranging-short return study
artifacts.

Allowed exact paths:

```text
scripts/build_v1129_ranging_short_offline_return_study.js
reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.json
reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.md
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
secret files, SQLite snapshots, or server state.

## Verification

Required checks:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Recommended Task 39

Proceed to Task 39: V11.29 Ranging-Short Offline Candidate Return Study.

