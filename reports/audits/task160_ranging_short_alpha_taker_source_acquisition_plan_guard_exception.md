# Task 160: Ranging Short Alpha/Taker Source Acquisition Plan Guard Exception

## Summary

Added narrow harness guard exceptions for the exact ranging-short alpha/taker
source acquisition plan paths approved by Task 157.

Decision:

```text
exact_paths_allowed_no_broad_ranging_short_surface
```

## Source Reviewed

```text
reports/audits/task157_ranging_short_alpha_taker_source_acquisition_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js`:

```text
scripts/build_ranging_short_alpha_taker_source_acquisition_plan.js
reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.json
reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.md
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
bot lifecycle commands
backtests
live/server operations
```

## Verification

Verification completed:

```powershell
node --check scripts/guard_harness_diff.js
.\scripts\run_agent_readiness_checks.ps1
```

Result:

```text
node --check scripts/guard_harness_diff.js: pass
readiness: pass (9 changed path(s) checked)
ranging exact builder harness self-test: pass
ranging exact report harness self-test: pass
ranging broad builder harness self-test: blocked
ranging broad report harness self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 163: Ranging Short Alpha/Taker Source Acquisition Plan Implementation
```
