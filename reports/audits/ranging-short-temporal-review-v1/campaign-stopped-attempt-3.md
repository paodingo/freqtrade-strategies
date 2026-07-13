# Temporal Branch Contribution Review - Attempt 3 Stopped

- Status: `temporal_ablation_execution_invalid`
- Reason: `runtime_candidate_identity_mismatch`
- Failure phase: `slice_reproducibility_gate`
- Attempted / completed Backtests: `4 / 4`
- Remaining Backtests not started: `12`
- Completed Slice results: `0`
- Retries: `0`
- Research verdict: `not_evaluated`
- Temporal classification: `null`
- Validation / Holdout accesses: `0 / 0`
- Candidate or formal strategy modified: `false`

The four `s01` executions completed in distinct processes and sealed valid, one-to-one execution bindings. Each execution contained 21 normalized trades with SHA-256 `953dcb2de53cf81dea6185d51b20c1fb50a2240eb1a73c5a81bd5a78d63955d5`.

The loaded Candidate identity was the frozen approved source at `research/candidates/branch-contribution-ablation-v1/1/RegimeAware_Ablation_RangingShort_C1.py` with SHA-256 `e20dd42d2ba8a11ac2b832ad610c8f25cce28e6c92b74959ba0cce286c753eb0`. The parent comparator was not configured for this temporal Candidate and retained the generic router-extraction identity. It therefore raised `runtime_candidate_identity_mismatch` before producing a Slice contribution result.

In accordance with `max_retries: 0`, Attempt 3 was not retried, the remaining 12 Backtests were not started, and no contribution or cross-time research conclusion was generated. Attempt 1, Attempt 2, and other historical execution results were not read.
