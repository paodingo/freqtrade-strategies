# Research R187: Causal Structure Readiness Exact Guard Surface

## Summary

The user authorized execution of the development-only causal structure event
coverage audit. The first readiness run correctly blocked the new paths because
they were not yet present in the harness allowlist.

This task adds exact allowances for only these four implementation artifacts:

```text
scripts/analyze_chan_structure_readiness.py
tests/test_chan_structure_readiness.py
research/analysis/chan-structure-readiness-v1/event-coverage-report.json
research/analysis/chan-structure-readiness-v1/event-coverage-report.md
```

No prefix, regex, `scripts/**`, `tests/**`, or
`research/analysis/chan-structure-readiness-v1/**` wildcard was added.

## Authorized Behavior

- read hash-verified BTC and ETH development-only OHLCV files;
- reconstruct the common 1h development window;
- count confirmed fractals, structure breaks, and confirmed higher-low/lower-high retests;
- run prefix-recomputation causality checks;
- write one JSON report and one Markdown report;
- run isolated unit and readiness tests.

## Explicit Non-Allowances

- no strategy or bot-config changes;
- no Candidate creation;
- no Backtest, Hyperopt, Validation, or Holdout access;
- no threshold, exit, risk, stake, leverage, or ROI changes;
- no market-data download or refresh;
- no secret, API, server, deployment, or bot lifecycle access;
- no live or dry-run trade operation.

## Guard Scope

`scripts/guard_harness_diff.js` contains the four exact paths. The trading
surface guard is unchanged because these paths do not match any protected
trading or versioned runtime surface.

`docs/harness/change_surface_matrix.md` records the same narrow boundary, and
the audit test asserts that no directory-prefix allowance exists.

## Verification

Required checks:

```text
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
python -m unittest tests.test_chan_structure_readiness -v
.\scripts\run_agent_readiness_checks.ps1
```
