# Task 60R: V11.30 Crash Rebound Guard Exception

## Summary

This task adds exact guard exceptions for the V11.30 crash-rebound shadow local
implementation files authorized by Task 59. It does not create the strategy,
config, or test files; it only prepares the static guard boundary.

## Exact Paths Allowed

```text
strategies/RegimeAwareV1130CrashReboundShadow.py
user_data/config_multi_futures_v1130_crash_rebound_shadow.json
tests/test_regime_aware_v1130_crash_rebound_shadow.py
```

## Files Modified

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
reports/audits/task60r_v1130_crash_rebound_guard_exception.md
tasks/active/TASK-0060R-v1130-crash-rebound-guard-exception.md
```

## Boundary Confirmation

This task did not allow:

- `strategies/**`
- `user_data/**`
- `tests/**`
- `*v1130*`
- `dashboard/**`
- `deploy/**`
- `configs/**`
- `.env`
- `user_data/monitor.env`
- secret material
- server operations
- bot start/stop/restart

## Validation

Required validation:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Recommended Next Task

Task 60: V11.30 Crash Rebound Shadow Local Implementation.

