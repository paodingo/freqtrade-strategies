# Task 35R: Allow V11.29 Pre-Filter Reconstruction Exact Paths

## Summary

Task 34 recommended Task 35: V11.29 Pre-Filter Signal Reconstruction. A no-side-effect guard self-test confirmed the Task 35 script and output paths were blocked by both harness and trading-surface guards.

This task adds exact guard exceptions only for the Task 35 read-only reconstruction artifacts:

```text
scripts/build_v1129_pre_filter_signal_reconstruction.js
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md
```

No broad allowlist was added.

## Preconditions

- Task 34 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks passed before edits.

## Guard Changes

Modified:

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
```

Added exact path allowlist entries only for:

```text
scripts/build_v1129_pre_filter_signal_reconstruction.js
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md
```

The guards still do not allow:

```text
reports/v1129_execution_validation/**
reports/*v1129*
scripts/build_v1129_*
reports/v1129_execution_validation/real_execution_report.json
reports/v1129_execution_validation/snapshots/should_not_commit.sqlite
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
```

## Self-Test Results

Exact Task 35 paths:

```text
scripts/build_v1129_pre_filter_signal_reconstruction.js: allowed
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json: allowed
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md: allowed
```

Blocked paths:

```text
reports/v1129_execution_validation/real_execution_report.json: blocked
reports/v1129_execution_validation/snapshots/should_not_commit.sqlite: blocked
strategies/RegimeAwareV1129GuardSelfTest.py: blocked
user_data/config_multi_futures_v1129_guard_selftest.json: blocked
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
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- copy SQLite;
- modify original dirty workspace.

## Verification

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Recommended Next Task

```text
Task 35: V11.29 Pre-Filter Signal Reconstruction
```
