# Task 184: Ranging Short Actual Source Acquisition Execution Report Guard Exception

## Summary

Added narrow harness guard exceptions for the exact ranging-short actual source
acquisition execution report paths approved by Task 181.

Decision:

```text
exact_paths_allowed_no_broad_ranging_short_surface
```

## Source Reviewed

```text
reports/audits/task181_ranging_short_actual_source_acquisition_execution_report_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js`:

```text
scripts/build_ranging_short_alpha_taker_source_acquisition_actual_execution_report.js
reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_actual_execution_report.json
reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_actual_execution_report.md
```

## Explicitly Not Added

The guard was not widened to `scripts/build_ranging_short_*`,
`reports/ranging_short_research/**`, or `reports/**/*ranging_short*`.

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
ranging actual builder harness self-test: pass
ranging actual json harness self-test: pass
ranging broad builder harness self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 187: Ranging Short Actual Source Acquisition Execution Report Implementation
```
