# Research R188: Causal Structure Reversal Single-Candidate Exact Guard Surface

## Summary

After the Task 187 development-only readiness gate passed, the user explicitly
said `继续`. Under the approved Research Constitution this is recorded as the
human authorization for one medium-risk `new_strategy_branch` Campaign.

The Campaign is limited to one isolated long-side Candidate and eight sealed,
development-only Backtest calls. The formal strategy and trading runtime are
outside the change surface.

## Exact implementation paths

```text
research/candidates/chan-structure-reversal-v1/RegimeAwareChanStructureLongV1.py
research/candidates/chan-structure-reversal-v1/candidate-manifest.json
scripts/run_chan_structure_reversal_campaign.py
tests/test_chan_structure_reversal_candidate.py
research/analysis/chan-structure-reversal-v1/development-comparison.json
reports/audits/chan-structure-reversal-v1/final-report.json
reports/audits/chan-structure-reversal-v1/final-report.md
```

The compiled Campaign and human approval are stored under the already governed
`research/director/**` and `research/governance/approvals/**` surfaces.

No Candidate, analysis, report, script, or test directory prefix was added to
the harness allowlist.

## Frozen execution matrix

```text
BTC/ETH x Baseline/Candidate x RUN-A/RUN-B = 8 calls
timeframe = 1h
timerange = 20240609-20240811
fee = 0.0004
Validation accesses = 0
Holdout accesses = 0
Candidates = 1
Retries = 0
```

## Candidate boundary

- one new causal confirmed-higher-low long signal group;
- pivot radius, break horizon and retest horizon reused from Task 187;
- 4h regime used only as a recognized-state gate and attribution tag;
- existing routed entries remain unchanged;
- exit logic, ROI, stoploss, leverage, stake, protections and execution
  configuration remain unchanged.

## Explicit non-allowances

- no `strategies/**`, `user_data/**`, `configs/**`, `dashboard/**` or
  `deploy/**` mutation;
- no threshold search, exit rewrite, risk change or Hyperopt;
- no Validation, Holdout, forward dry-run or live trading;
- no automatic promotion or automatic follow-up Candidate;
- no secret, private API, bot lifecycle, market refresh or server operation.

## Required verification

```text
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
python -m unittest tests.test_chan_structure_readiness tests.test_chan_structure_reversal_candidate -v
.\scripts\run_agent_readiness_checks.ps1
```
