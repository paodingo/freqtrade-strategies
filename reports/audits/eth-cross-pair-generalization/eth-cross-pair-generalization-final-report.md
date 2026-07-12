# ETH Cross-pair Generalization Final Report

- Pair/timeframe: `ETH/USDT:USDT` / `1h`
- Dataset: `futures-dev-eth-usdt-usdt-20240101-20240830-v1`
- Dataset aggregate SHA-256: `00ddc63806215087904425ae59543e62cac5d5aa2c8c29406b7f90eeb0c28187`
- RUN-A/RUN-B distinct PIDs: `58028` / `24900`
- Reproducible: `true`
- ETH total trades: `27`
- ETH total profit: `-204.31205016 USDT` (`-2.0431205%` of the configured starting balance)
- ETH profit factor / win rate: `0.7157067` / `0.4814815`
- Result: `reproducible_eth_trade_behavior_observed`

The unchanged strategy produced reproducible trades on ETH, so execution behavior is portable to this approved pair and boundary. This does not prove profitable or policy-qualified cross-pair generalization: the ETH result is negative and the formal Evaluation Policy remains BTC-only. No Candidate was created, no strategy was modified, no Hyperopt ran, and Validation/Holdout were not accessed.

## BTC Descriptive Reference

- BTC total trades / ETH total trades: `27 / 27`
- BTC long-short / ETH long-short: `7-20 / 6-21`
- BTC profit factor / ETH profit factor: `0.9525611 / 0.7157067`
- BTC total profit / ETH total profit: `-32.72550825 / -204.31205016 USDT`

These are descriptive development metrics only; no formal relative gate was applied.

## Execution Accounting

- One cadence-validator precision defect stopped before snapshot output.
- One missing offline leverage fixture stopped before metrics or research evidence.
- After the local read-only fixture was restored, the two authorized fresh-process research runs both completed and matched.

## Verification

- Targeted tests: `104 / 104`
- Research tests: `48 / 48`
- Readiness guards: passed
- Full baseline verifier: `errors: []` with only the locked `8` Python and `4` Node historical failures
- Python compile / Node syntax: passed
- Registry integrity: `ok`
- Next Director recommendation: `no_research_recommended`
- Campaign commit: `d6ddf65a183de0b4f1f6f27391ee52aae667c6d4`
- Final Research State fingerprint: `66c946f0072a137b1621a87b9fe3f91fc405c80e8564c0f23a4762254d8be053`
- Final Director run: `director-run-38c2b968238b458a`
- Git closure: this commit; clean status required immediately after commit
