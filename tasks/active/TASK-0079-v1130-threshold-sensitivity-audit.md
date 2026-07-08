# TASK-0079: V11.30 Threshold Sensitivity Audit

## Status

Completed.

## Objective

Use post-refresh gate telemetry to identify which V11.30 thresholds most limit
candidate generation.

## Result

- Baseline: `11` candidates, `9` enabled.
- Lower return threshold alone: no increase.
- Lower volume threshold alone: no increase.
- Lower range threshold to `0.008`: `29` candidates, `23` enabled.
- Combined looser thresholds: `46` candidates, `34` enabled.
- Main observed bottleneck: `range`.

## Boundary

No strategy threshold, bot config, runtime bot, secret, SQLite, or dashboard
surface was modified.

## Output

- `reports/audits/task79_v1130_threshold_sensitivity_audit.md`

## Next

Recommended: Task 80, Task 81, Task 82.
