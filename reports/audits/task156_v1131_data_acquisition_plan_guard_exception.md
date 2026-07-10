# Task 156: V11.31 Longer Replay Data Acquisition Plan Guard Exception

## Summary

Added narrow guard exceptions for a future read-only V11.31 longer replay data
acquisition plan artifact.

Decision:

```text
exact_paths_allowed_no_broad_v1131_surface
```

## Source Reviewed

```text
reports/audits/task151_v1131_longer_replay_data_acquisition_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js` and
`scripts/guard_trading_surface.js`:

```text
scripts/build_v1131_longer_replay_data_acquisition_plan.js
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.md
```

## Explicitly Not Added

The guards were not widened to:

```text
scripts/build_v1131_*
reports/v1131_observation/**
reports/**/*v1131*
```

## Protected Surfaces Remain Blocked

The task did not lower protections for:

```text
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
.env
user_data/monitor.env
bot lifecycle commands
backtests
live/server operations
```

## Verification

Verification completed:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Result:

```text
node --check scripts/guard_harness_diff.js: pass
node --check scripts/guard_trading_surface.js: pass
readiness: pass (9 changed path(s) checked)
v1131 acquisition plan exact harness self-test: pass
v1131 acquisition plan exact trading self-test: pass
v1131 broad report harness self-test: blocked
v1131 broad report trading self-test: blocked
v1131 broad builder harness self-test: blocked
v1131 broad builder trading self-test: blocked
strategy blocked harness self-test: blocked
config blocked trading self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 159: V11.31 Longer Replay Data Acquisition Plan Implementation
```
