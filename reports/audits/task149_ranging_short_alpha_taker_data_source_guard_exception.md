# Task 149: Ranging Short Alpha/Taker Data Source Guard Exception

## Summary

Added a narrow harness guard exception for the future read-only ranging-short
alpha/taker/protection data-source inventory report builder.

Decision:

```text
exact_paths_allowed_no_broad_ranging_short_surface
```

## Source Reviewed

```text
reports/audits/task145_ranging_short_alpha_taker_data_source_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js`:

```text
scripts/build_ranging_short_alpha_taker_data_source_inventory.js
reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.json
reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.md
```

## Explicitly Not Added

The guard was not widened to:

```text
scripts/build_ranging_short_*
reports/ranging_short_research/**
reports/**/*ranging_short*
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
ranging alpha-taker exact harness self-test: pass
ranging broad harness self-test: blocked
ranging broad builder harness self-test: blocked
strategy blocked harness self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 152: Ranging Short Alpha/Taker Data Source Inventory Implementation
```
