# TASK-0104: Candidate Search Harness Design

## Status

Completed.

## Goal

Design an offline candidate-search harness and define metrics, data gates, and
anti-overfit controls before writing any implementation code.

## Allowed Outputs

- `reports/audits/task104_candidate_search_harness_design.md`
- `tasks/active/TASK-0104-candidate-search-harness-design.md`

## Result

The next strategy search should be metric-first and data-gated. Initial
implementation should prefer a `15m + 4h` mode because Task 103 found recent
`1h` futures OHLCV data stale.

Core metrics:

- trade count;
- net PnL after fees;
- max drawdown;
- profit factor;
- pair dispersion;
- exit reason distribution;
- MFE/MAE;
- sample-window coverage;
- overfit checks.

## Boundaries

This task did not:

- write harness code;
- run backtests;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- read secrets;
- restart bots;
- force-close trades;
- produce a replacement conclusion.

Recommended next task:

```text
Task 105: Candidate Search Harness Exact Path Allowlist Review
```

