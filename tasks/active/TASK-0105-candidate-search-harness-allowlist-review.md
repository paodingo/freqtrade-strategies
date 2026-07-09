# TASK-0105: Candidate Search Harness Exact Path Allowlist Review

## Status

Completed.

## Goal

Review the exact path surface required for a future offline candidate-search
harness without modifying guards or writing the harness.

## Allowed Outputs

- `reports/audits/task105_candidate_search_harness_allowlist_review.md`
- `tasks/active/TASK-0105-candidate-search-harness-allowlist-review.md`

## Result

Approved for a future guard-exception task:

```text
scripts/build_strategy_candidate_search_harness.js
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md
reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv
```

Not approved:

- `reports/candidate_search/**`;
- `scripts/build_strategy_*`;
- `scripts/build_v1130_*`;
- `strategies/**`;
- `user_data/**`;
- `configs/**`;
- `dashboard/**`;
- `deploy/**`;
- secrets;
- bot lifecycle or live/server operations.

## Boundaries

This task did not:

- modify guards;
- write harness code;
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
Task 106: Candidate Search Harness Guard Exception
```

