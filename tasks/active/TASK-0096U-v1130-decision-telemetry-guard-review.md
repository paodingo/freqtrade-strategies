# TASK-0096U: V11.30 Decision Telemetry Guard Review

## Status

Completed.

## Objective

Approve and patch only the exact generated output paths required for V11.30
behavior-neutral final decision telemetry.

## Result

Completed.

Allowed exact paths:

```text
reports/v1130_observation/v1130_final_decision_telemetry.json
reports/v1130_observation/v1130_final_decision_telemetry.md
```

Changed:

```text
scripts/guard_harness_diff.js
scripts/guard_trading_surface.js
docs/harness/change_surface_matrix.md
reports/audits/task96u_v1130_decision_telemetry_guard_review.md
```

## Boundaries

- No telemetry implementation.
- No strategy behavior change.
- No bot config change.
- No dashboard/deploy change.
- No server login required for this task.
- No bot start/stop/restart.
- No secret reads.
- No SQLite writes.

## Next

Run:

```text
Task 96V: Implement V11.30 behavior-neutral final decision telemetry
```

Task 96V must prove no change to `enter_long`, `enter_tag`, or
`v1130_crash_rebound_gate` for the same input dataframe.
