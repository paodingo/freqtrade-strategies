# Task 38: V11.29 Ranging-Short Offline Calibration Design

## Summary

This task defines an offline-only calibration design for the V11.29
`v66_ranging_short_edge` candidate family. It does not run backtests, modify
strategy code, modify bot configuration, change server state, or enable live
entries.

The current evidence chain is:

- Task 35 reconstructed the V11.29 pre-filter funnel and identified
  `v102_short_core_pruning` as the current primary suppressing layer.
- Task 36 defined the calibration question and safety gates.
- Task 37 confirmed that `v66_ranging_short_edge` candidates exist, but are not
  final `enter_short` orders.

Task 37 observed:

| Metric | Count |
| --- | ---: |
| total `v66_ranging_short_edge` candidates | 111 |
| blocked by `v102_short_core_prunes_ranging_non_core_short` | 85 |
| blocked by `alpha_filter_block_short` | 26 |
| final `enter_short` rows from these candidates | 0 |

This is enough to justify offline research. It is not enough to justify live
strategy or configuration changes.

## Calibration Objective

The objective is to answer a narrow question:

```text
Should `v66_ranging_short_edge` remain fully blocked by the inherited V10.2
short-core path, or should it become a separate, risk-capped research lane?
```

The design must preserve three boundaries:

1. Keep V11.29 live behavior unchanged during calibration.
2. Keep V10.8.2 as benchmark evidence only, not as an automatic replacement
   target.
3. Require offline evidence before any dry-run or live experiment is proposed.

## Candidate Definition

Candidate family:

```text
v66_ranging_short_edge
```

Observed runtime characteristics:

- `regime_4h = ranging`
- near upper range position on 24h and 48h windows
- elevated `bb_percent`
- elevated `rsi`
- moderate or non-expanding 4h trend strength
- `enter_tag = v66_ranging_short_edge`
- final `enter_short = 0`

The candidate is not equivalent to:

- `v102_trending_short_core`
- a final order signal
- a verified profitable short
- a V11.29 replacement proof

## Required Data Windows

Minimum offline study windows:

| Window | Purpose | Required Before Live Change |
| --- | --- | --- |
| 7d | Confirm recent candidate density and pair concentration. | Yes |
| 14d | Reduce one-off market regime bias. | Yes |
| 30d | Measure broader market behavior and rough drawdown risk. | Yes |
| 60d+ | Optional robustness check if data is available. | Recommended |

If fewer than 30 days of reliable candles are available, the calibration should
remain in `insufficient` status.

## Required Metrics

The offline calibration should compute candidate-only metrics without changing
the production strategy:

| Metric | Reason |
| --- | --- |
| candidate count by pair | Identify whether the signal is broad or pair-specific. |
| candidate count by day | Detect clustering and one-day artifacts. |
| candidate count by regime context | Confirm candidates are truly ranging-short. |
| next 1/2/4/8 candle adverse excursion | Estimate immediate short risk. |
| next 1/2/4/8 candle favorable excursion | Estimate realistic edge. |
| hypothetical entry/exit return | Measure candidate quality under fixed rules. |
| max drawdown per candidate path | Avoid selecting high-pain reversals. |
| alpha-blocked vs alpha-allowed split | Check whether alpha filtering is protecting the system. |
| pair-level hit rate | Identify pairs that should remain excluded. |
| fee-adjusted expectation | Prevent tiny gross edge from becoming net loss. |
| correlation with V10.8.2 active windows | Keep benchmark context visible. |

Metrics must distinguish:

- observed: directly available from candles/runtime fields;
- derived: computed from candles;
- missing: unavailable in local data;
- unknown: cannot be verified from current sources.

## Offline Calibration Design

Recommended Task 39 implementation shape:

1. Build a read-only candidate dataset:
   - Use historical `15m` candles and available informative `4h` columns.
   - Reconstruct only `v66_ranging_short_edge` conditions.
   - Do not alter live strategy files.

2. Generate candidate-only forward returns:
   - Use fixed horizons such as 1, 2, 4, and 8 candles.
   - Include favorable and adverse excursion.
   - Include fee assumptions explicitly.
   - Do not pretend this is a full execution-quality report.

3. Split by pair:
   - `AVAX/USDT:USDT`
   - `DOGE/USDT:USDT`
   - `LTC/USDT:USDT`
   - `BNB/USDT:USDT`
   - `TRX/USDT:USDT`
   - `BTC/USDT:USDT`

4. Split by alpha state:
   - candidates alpha would block;
   - candidates alpha would allow.

5. Produce pass/fail classification:
   - `reject`: negative fee-adjusted expectation or high adverse excursion;
   - `needs_more_data`: sample too small or clustered;
   - `research_candidate`: enough evidence for a later dry-run shadow design;
   - `unknown`: input data missing or formula cannot be reconstructed safely.

## Pass/Fail Gates

Before any later task proposes live strategy/config changes, the candidate
family must satisfy all of these gates:

| Gate | Required Result |
| --- | --- |
| sample size | at least 100 candidates over 30d, or explicitly marked `insufficient` |
| pair concentration | no single pair should dominate without pair-specific justification |
| fee-adjusted expectation | positive after conservative fees, otherwise `reject` |
| adverse excursion | bounded enough for a small-stake research lane |
| alpha split | alpha-allowed candidates must outperform alpha-blocked candidates, or alpha must remain active |
| stale-data check | candles must be current for the evaluated window |
| no replacement claim | no V11.29 replacement verdict allowed |

If any gate fails, the next step should remain offline analysis or rejection,
not live enablement.

## Explicit Non-Goals

This task does not authorize:

- editing `strategies/**`;
- editing bot configs under `user_data/**` or `configs/**`;
- starting, stopping, or restarting containers;
- running live or dry-run experiments;
- running a backtest in this task;
- copying or editing SQLite snapshots;
- changing dashboard or deploy code;
- weakening guard rules;
- declaring V11.29 better or worse than V10.8.2.

## Risk Notes

The key risk is overfitting to recent ranging-short clusters. Task 37 showed
real candidate density, but the distribution is uneven:

- AVAX: 37 candidates
- DOGE: 27 candidates
- LTC: 20 candidates
- BNB: 15 candidates
- TRX: 8 candidates
- BTC: 4 candidates

The top three pairs account for most candidates. A later calibration must
therefore report pair-level results, not only aggregate results.

Another risk is confusing `enter_tag` with order intent. The tag identifies a
candidate family, but final execution still requires `enter_short == 1`.

## Recommended Task 39

Recommended next task:

```text
Task 39: V11.29 Ranging-Short Offline Candidate Return Study
```

Suggested scope:

- Add a read-only analysis script if guard rules allow it, or first add exact
  guard exceptions if needed.
- Reconstruct `v66_ranging_short_edge` from local or server-available candle
  data.
- Compute candidate-only forward returns and adverse/favorable excursion.
- Generate JSON/Markdown outputs under an exact allowlist.
- Do not run live bot operations.
- Do not modify strategies or bot configs.
- Do not claim V11.29 can replace V10.8.2.

## Boundaries

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- log into the server;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- modify original dirty workspace files.

## Verification

Required completion checks:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

