# TASK-0060R: V11.30 Crash Rebound Guard Exception

## Objective

Add exact guard exceptions for the future V11.30 crash-rebound shadow local
implementation files, without implementing strategy/config/test files yet.

## Allowed Changes

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task60r_v1130_crash_rebound_guard_exception.md`
- `tasks/active/TASK-0060R-v1130-crash-rebound-guard-exception.md`

## Exact Future Allowlist

- `strategies/RegimeAwareV1130CrashReboundShadow.py`
- `user_data/config_multi_futures_v1130_crash_rebound_shadow.json`
- `tests/test_regime_aware_v1130_crash_rebound_shadow.py`

## Forbidden

- No strategy implementation in this task.
- No bot config implementation in this task.
- No server operations.
- No bot start/stop/restart.
- No secret reads.

