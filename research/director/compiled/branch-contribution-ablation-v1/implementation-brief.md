# Implementation Brief: Regime router branch contribution ablation

Campaign: `stage4a-branch-contribution-ablation-v1`
Fingerprint: `a3db3e0e2d52f6caf700732150a396acee1fa7accc9f054eaef2cbab43e6490f`
Compile mode: `dry_run`
Execution authorized: `false`

## Verified baseline

`RegimeAwareV6` remains the formal execution baseline. `RegimeAwareRouterEquivalentV1` is only the verified structural reference. BTC and ETH each have 27 exact-equivalence trades in the frozen router recertification.

## Real ablation units

- `trending_long_entry`: trending / long / enter_long (eligible: `true`)
- `trending_short_entry`: trending / short / enter_short (eligible: `true`)
- `ranging_long_entry`: ranging / long / enter_long (eligible: `true`)
- `ranging_short_entry`: ranging / short / enter_short (eligible: `true`)
- `ranging_breakdown_exit_long`: ranging / long / exit_long (eligible: `true`)
- `shared_regime_router`: shared / both / dispatch (eligible: `false`)

Only one eligible signal group may be selected in a future human execution approval. The shared router is mapped but is not eligible in this Campaign.

## Reversible single-variable mechanism

Preserve the original branch code, conditions, tags and source locations. A future isolated Candidate may gate exactly one final signal group and must record the selected unit, mechanism, preserved source hash and exact diff allowlist. Large deletion is forbidden.

## Frozen future execution design

- Candidate count: `1`
- Backtest calls: `8` (`2 roles x 2 pairs x 2 fresh-process repetitions`)
- Pairs: BTC and ETH Development only
- Initial temporal slice Backtests: `0`; rolling-window attribution uses the same approved runs
- Validation/Holdout: `0 / 0`
- Balanced Research Gate: descriptive context only, never a promotion gate

Planned queue (not executable under current authority):

1. `record the human-selected single eligible ablation unit and freeze its reversible Candidate diff allowlist`
2. `run the four BTC fresh-process Baseline/Candidate executions and validate namespace plus identity`
3. `run the four ETH fresh-process Baseline/Candidate executions and produce contribution attribution`

## Contribution metrics

- `removed_branch_original_signal_count`
- `actual_trade_count_delta`
- `long_short_trade_delta`
- `return_delta`
- `profit_factor_delta`
- `max_drawdown_delta`
- `fee_and_funding_delta`
- `rolling_window_delta`
- `temporal_slice_delta_if_separately_approved`
- `pair_level_delta`
- `remaining_branch_behavior`
- `normalized_trade_hash`

## Deterministic classifications

- `branch_positive_contributor`
- `branch_negative_contributor`
- `branch_mixed_regime_dependent`
- `branch_redundant`
- `branch_contribution_inconclusive`
- `ablation_execution_invalid`

## Human approval still required

- Name exactly one eligible `unit_id`.
- Approve one Candidate class/path, reversible gating mechanism and exact diff allowlist.
- Approve the eight development-only Backtest calls and 120-minute budget.
- Confirm no temporal-slice expansion, Validation, Holdout, threshold, exit, router, risk or execution change.

No Candidate, Backtest or ablation is created by this compilation.
