# Temporal Branch Contribution Review - Attempt 2 Stopped

- Status: `temporal_ablation_execution_invalid`
- Reason: `windows_path_length_limit`
- Failed execution: `ranging-short-ablation-s01 / Baseline / RUN-A`
- Attempted / completed Backtests: `1 / 0`
- Remaining Backtests not started: `15`
- Retries: `0`
- Research verdict: `not_evaluated`
- Temporal classification: `null`
- Validation / Holdout accesses: `0 / 0`
- Candidate or formal strategy modified: `false`

The sealed runner computed 21 unsealed trades, then stopped before writing the raw result because `backtest-result-cd110c0ff7cb.meta.json` had a 264-character absolute path while Windows long paths were disabled. No raw result or normalized trades were produced, so no slice or cross-time contribution conclusion is valid.

The original `temporal-branch-contribution-review-v1` failure tree remains unchanged at SHA-256 `f610bcebe0e67bb1096f9b8ab96d66c8a69f6dcbca58eb077654175ee7e32e93`. Attempt 2 was not retried and no later queue item was started.

The failed worker generated 1,568 Manifest-excluded `__pycache__/*.pyc` files inside the ignored Portable Runtime. All extras matched that exact generated-bytecode allowlist, were removed without touching declared Runtime assets, and the complete 9,550-file Runtime Manifest closure passed afterward.
