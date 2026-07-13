# Implementation Brief: Regime-conditioned branch factorization study

Campaign: `stage4a-regime-conditioned-branch-factorization-v1`
Fingerprint: `5f759a309a23e684bbd3277a3aff1de3b075c01ddd22e2d3f67e57e00c7c8fe3`
Compile mode: `dry_run`
Execution authorized: `false`

## Minimum research unit

`router-extraction-semantic-equivalence-v1` changes only `location_and_interface_of_regime_dispatch_only`. The future execution scope is exactly one Candidate and 8 Backtest invocations (2 strategies x 2 pairs x 2 fresh-process repetitions).

## Frozen order

1. Current authorized work is read-only mapping, compilation and human review only.
2. A new human execution approval is required before creating the one equivalence Candidate.
3. Prove exact BTC and ETH semantic equivalence in fresh processes.
4. Stop on any mismatch. Branch contribution ablation is not compiled here and requires a separate Proposal and approval.

## Planned queue (not authorized)

1. `create exactly one router-extraction Candidate after new human execution approval`
2. `run the BTC baseline/Candidate equivalence pack in distinct fresh processes`
3. `run the ETH baseline/Candidate equivalence pack in distinct fresh processes`

## Equivalence boundary

Code movement is a refactor only when the normalized 29-condition inventory, five signal groups, signal-frame hashes, tags, timestamps, trade signatures and all risk/execution settings are identical. Any mismatch is a real semantic change and stops the Campaign.

## Baseline and single-variable control

`RegimeAwareV6` remains the immutable execution baseline. No condition, threshold, entry, exit, ROI, stoploss, leverage, protection or execution configuration may change. Each future ablation must be a separate Campaign and Candidate.

## Human approval still required

- Candidate class/path and exact diff allowlist.
- Eight Backtest invocations on the two frozen development pairs.
- Runtime and wall-clock budget for execution.
- Any later single-branch contribution ablation.

## Definition of done for this compilation

- Campaign Spec, structure map and decision packet agree on counts and boundaries.
- Targeted tests, readiness, baseline and Registry integrity pass.
- No Candidate, Backtest, Validation or Holdout access occurs.
- Commit logically and leave the version-controlled worktree clean.
