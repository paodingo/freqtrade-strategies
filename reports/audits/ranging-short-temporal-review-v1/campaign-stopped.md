# Temporal Branch Contribution Review — Stopped

- Status: `temporal_ablation_execution_invalid`
- Reason: `runtime_execution_asset_missing`
- Failed execution: `ranging-short-ablation-s01 / Baseline / RUN-A`
- Attempted / completed Backtests: `1 / 0`
- Remaining Backtests not started: `15`
- Retries: `0`
- Research verdict: `not_evaluated`
- Temporal classification: `null`
- Validation / Holdout accesses: `0 / 0`
- Candidate or formal strategy modified: `false`

The sealed runner stopped before Backtesting initialization because the execution worktree did not contain `.venv-freqtrade/Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json`. The failure namespace remains in the ignored result root; no raw Backtest result or normalized trade output was produced.
