# TASK-0102: Strategy Candidate Evidence Inventory

## Status

Completed.

## Goal

Read-only inventory existing strategy families, historical reports, V11.29 /
V11.30 evidence, high-volatility replay outputs, and available backtest
summaries to prioritize candidate strategy families.

## Allowed Outputs

- `reports/audits/task102_strategy_candidate_evidence_inventory.md`
- `tasks/active/TASK-0102-strategy-candidate-evidence-inventory.md`

## Boundaries

This task did not:

- run backtests;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- read secrets;
- start, stop, or restart bots;
- force-close V11.30 positions;
- produce a replacement conclusion.

## Result

Candidate-search preparation should start from:

1. high-volatility crash/rebound continuation;
2. crash-rebound exit-quality review after more closed trades;
3. ranging-short / volatility fade research family;
4. breakout/continuation and alpha/taker-pressure variants.

Next task:

```text
Task 103: High-Volatility Window Dataset Readiness Plan
```

