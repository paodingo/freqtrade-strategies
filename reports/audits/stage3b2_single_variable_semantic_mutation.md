# Stage 3B.2 Single Variable Semantic Mutation

Date: 2026-07-10

## Verdict

Stage 3B.2 is complete for one pre-authorized single-variable semantic mutation.

Engineering verdict:

- `mutation_verified_behavior_unchanged`

This means the candidate source was changed exactly once at the authorized AST
node, both independent candidate runs reproduced exactly, and the fixed
acceptance fixture did not produce a behavioral difference versus the Stage 3A
baseline.

This is not a strategy quality result.

## Selected Variable

Variable selection audit:

- `reports/audits/stage3b2_single_variable_selection.md`

Selected variable:

- Name: `ranging_short_setup.bb_percent_min`
- Source: `strategies/regime_aware_base.py:231`
- Candidate copy: `research/candidates/demo-stage3b2-single-variable/1/regime_aware_base.py`
- Old value: `0.80`
- New value: `0.85`
- AST parent: `Compare`
- Left side: `dataframe["bb_percent"]`
- Operator: `Gt`
- Decision surface: short entry
- Hypothesis: Increasing this short-entry threshold may reduce some ranging short entry signals.

Excluded forbidden variables include `can_short`, `timeframe`,
`startup_candle_count`, `stoploss`, and `minimal_roi`.

## Experiment Spec

Artifact:

- `research/experiments/demo-stage3b2-single-variable/1/experiment-spec.yaml`

Frozen fields:

- experiment type: `single_variable_semantic_mutation`
- quality evaluation enabled: `false`
- champion promotion enabled: `false`
- sealed holdout enabled: `false`
- semantic mutation budget: `1`
- baseline trade hash: `74c40da36d57d452066e39e0425a83ae1ddc73be8069c91d184dd6afa5c4e6ee`
- runtime fingerprint: `6bf6037afd7df77bdea8879cef02744e25dd498c21d30f24b97be28cdfd3fd0d`
- dataset hash: `b556d7db23144614225b732a22c5e91bcc0efb2dd170e112d555ae7f70279736`
- exchange snapshot hash: `599d67345bed5b2b3b42669baf460fa336ffde80502cfd1880ea57cd0dc5074d`
- leverage-tier hash: `3cbdcc23ac57dd40e8664036293947fbe283865ef4a0f87e9265bb441858d981`

## Candidate

Candidate artifacts:

- Source: `research/candidates/demo-stage3b2-single-variable/1/RegimeAware_C3B2_E0001.py`
- Mutated dependency: `research/candidates/demo-stage3b2-single-variable/1/regime_aware_base.py`
- Manifest: `research/candidates/demo-stage3b2-single-variable/1/candidate-manifest.yaml`

Candidate identity:

- Class: `RegimeAware_C3B2_E0001`
- Candidate strategy SHA256: `1077567183500eefa76c9cf1749d2b2e64e4d25398d73d602794487955127593`

Authorized AST diff:

```diff
-            (dataframe["bb_percent"] > 0.80)
+            (dataframe["bb_percent"] > 0.85)
```

Diff gate:

- identity diff allowed: true
- semantic mutation count: `1`
- semantic diff location: `regime_aware_base.py:231`
- old value matched spec: true
- new value matched spec: true
- forbidden source hits: none
- unauthorized semantic diff: none

## Static Validation

Static validation passed:

- Python compile
- Freqtrade `list-strategies`
- candidate class uniqueness
- Strategy-Market Contract
- base strategy integrity
- candidate manifest integrity
- experiment spec integrity
- AST single-mutation verification
- fixture integrity
- dataset integrity
- exchange snapshot integrity
- leverage-tier integrity
- runtime fingerprint
- forbidden import/path scan
- network disabled policy

Official `RegimeAwareV6.py` SHA256 remained:

`1A422F41AB801746C2EE39F5D20722B26B674098BCA6AC1684E78BD8E7285509`

## Candidate Runs

RUN-A:

- `research/results/demo-stage3b2-single-variable/1/CANDIDATE-RUN-A/runner-report.json`

RUN-B:

- `research/results/demo-stage3b2-single-variable/1/CANDIDATE-RUN-B/runner-report.json`

Both runs:

- used sealed offline runner
- used `--cache none`
- used the same candidate input fingerprint:
  `2b9cee90df25d3f369e0084ba9e278e9a1954a9cdd9420d30dc3a3b078d5f01e`
- produced independent result directories
- produced real Freqtrade backtest results
- had no non-loopback network access

RUN-A/RUN-B comparison:

- `research/results/demo-stage3b2-single-variable/1/candidate-reproducibility-comparison.json`
- `consistent`: `true`
- `differences`: `{}`
- normalized futures trade hash consistent: true

Candidate normalized futures trade hash:

`74c40da36d57d452066e39e0425a83ae1ddc73be8069c91d184dd6afa5c4e6ee`

## Baseline/Candidate Behavior

Comparison artifact:

- `research/results/demo-stage3b2-single-variable/1/baseline-candidate-behavioral-comparison.json`

Result:

- behavior verdict: `behavior_unchanged`
- core metrics consistent: true
- differences: `{}`
- added trades: none
- deleted trades: none
- modified trades: none

This is acceptable for Stage 3B.2 because the objective is to verify the
controlled mutation pipeline. The fixture did not exercise a candle where
raising `ranging_short_setup.bb_percent_min` from `0.80` to `0.85` changed the
final trades.

## Registry

SQLite:

- `research/registry/research.db`
- table: `stage3b2_single_variable_experiments`

Recorded:

- selected variable: `ranging_short_setup.bb_percent_min`
- old/new value: `0.8` -> `0.85`
- semantic mutation count: `1`
- reproducibility verdict: `passed`
- engineering verdict: `mutation_verified_behavior_unchanged`
- quality evaluation status: `not_evaluated`
- promotion status: `not_allowed`
- failure class/reason: `null`

## Final Report

Artifact:

- `research/results/demo-stage3b2-single-variable/1/stage3b2-final-report.json`

Status:

- `stage3b2_complete`: `true`
- `status`: `mutation_verified_behavior_unchanged`

## Safety Notes

This stage did not:

- modify `strategies/RegimeAwareV6.py`
- modify official strategy files in `strategies/`
- modify fixture, dataset, exchange snapshot, or leverage tiers
- run Hyperopt
- run Lookahead Analysis
- run Recursive Analysis
- generate follow-up hypotheses
- perform strategy quality ranking
- promote a Champion
- access sealed holdout
- access private API, server, bot, deploy, or secrets

## Next Minimal Stage

The next stage should establish a Research Development/Validation data plane:

- add a non-sealed development slice for exploratory candidate behavior checks;
- keep the current sealed acceptance fixture as an execution-contract gate;
- add a separate validation slice before any candidate ranking is allowed;
- keep sealed holdout inaccessible until an explicit later stage.
