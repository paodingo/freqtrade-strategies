# TASK-0091R: V11.30 Decision Trace Guard Exception

## Status

Completed.

## Objective

Allow only the exact Task 91 decision trace paths through the harness and
trading-surface guards.

## Exact Paths

- `scripts/build_v1130_decision_trace_report.js`
- `reports/v1130_observation/v1130_decision_trace_report.json`
- `reports/v1130_observation/v1130_decision_trace_report.md`

## Boundaries

- No broad `reports/v1130_observation/**` allowance.
- No broad `scripts/build_v1130_*` allowance.
- No strategy changes.
- No bot config changes.
- No dashboard changes.
- No deploy changes.
- No SQLite snapshot allowance.
- No server operations.
- No secrets.

## Next

Run Task 91.
