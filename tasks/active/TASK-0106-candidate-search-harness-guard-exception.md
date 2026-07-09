# TASK-0106: Candidate Search Harness Guard Exception

## Status

Completed.

## Goal

Add exact guard exceptions for the first candidate-search harness implementation
surface approved by Task 105.

## Allowed Files

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task106_candidate_search_harness_guard_exception.md`
- `tasks/active/TASK-0106-candidate-search-harness-guard-exception.md`

## Exact Allowance

Allowed exactly:

```text
scripts/build_strategy_candidate_search_harness.js
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv
```

## Boundaries

This task did not:

- allow `reports/candidate_search/**`;
- allow `scripts/build_strategy_*`;
- write harness code;
- generate candidate-search outputs;
- run backtests;
- refresh data;
- modify strategies;
- modify bot configs;
- modify dashboard/deploy files;
- read secrets;
- restart bots;
- force-close trades.

Recommended next task:

```text
Task 107: Candidate Search Harness First Pass
```

