# Branch Contribution Ablation Campaign Stopped

- Status: `ablation_execution_invalid`
- Reason: `runtime_execution_asset_missing`
- Research verdict: `not_evaluated`
- Candidate created: `true` (`1 / 1`)
- Runner invocations: `1`
- Backtest engine started / completed calls: `false / 0`
- Failed run: `BTC Baseline RUN-A`
- Validation/Holdout: `0 / 0`

The sealed offline runner stopped before `Backtesting` initialization because the fixed Runtime leverage-tier artifact was absent from the independent worktree. The exact Manifest-bound file was subsequently hydrated read-only, but the frozen Campaign allows zero retries per experiment. No retry, contribution classification, or next Proposal was produced.
