# Implementation Brief: Ranging-short branch decision review

Campaign: `stage4a-ranging-short-branch-decision-review-v1`
Fingerprint: `1bf23890fd3386f7970e46cb74451c7b3696a7f92252faa233fca5f9af36192d`
Compile mode: `dry_run`
Execution authorized: `false`

## Metric semantics

All recorded deltas use `Candidate - Baseline`. Profit and fee/funding values are absolute USDT; `total_profit_pct` is stored as a ratio and is converted to percentage points by multiplying by 100. Profit Factor is dimensionless. `max_drawdown` in this artifact is absolute USDT, not a percentage or percentage-point value; lower is better.

ETH max drawdown is `291.71629049 - 340.65008476 = -48.93379427 USDT`, meaning the Candidate reduced absolute drawdown by 48.93379427 USDT.

## Policy and evidence boundary

- BTC Development is inside Balanced Research Gate v1 scope, but the ablation did not produce the complete policy gate evidence set.
- ETH Development is descriptive cross-pair evidence only.
- Validation, Holdout, temporal ablation slices and Forward Dry-run were not run.
- The current finding is branch contribution evidence, not `development_eligible`.

## Recommendation

`temporal_ablation_review_worth_authorizing`

- Option A Validation: `2` calls, `1` Validation access, `60` minutes.
- Option B Temporal: `16` calls (`4 slices x Baseline/Candidate x RUN-A/RUN-B`), `0` Validation/Holdout, `240` minutes.
- Option C Retain: `0` calls.

The existing Candidate is reused and frozen at `e20dd42d2ba8a11ac2b832ad610c8f25cce28e6c92b74959ba0cce286c753eb0`. No result in this compilation is sufficient to delete `ranging_short_entry` from the formal strategy.

## Human approval still required

- Select exactly one option.
- For temporal review, approve four exact slice boundaries, 16 Development-only calls and 240 minutes.
- For Validation review, approve one limited BTC Validation disclosure and two frozen Baseline/Candidate calls.
- Any strategy/Candidate modification, Holdout, Hyperopt or automatic follow-up remains forbidden.

No Campaign step is executed by this compilation.
