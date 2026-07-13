# Temporal Ablation Attempt 3 Root-Cause Amendment

- Attempt status remains: `temporal_ablation_execution_invalid`
- Attempt reason remains: `runtime_candidate_identity_mismatch`
- Completed Backtests remain: `4`
- Research verdict remains: `not_evaluated`
- Maximum retries remain: `0`
- Root-cause class: `implementation_error`
- Root-cause reason: `frozen_candidate_identity_not_propagated_to_parent_comparator`
- Identity propagation contract fingerprint: `fb620845db264886845ace8d00a139fa6d407c8fa29046e43d95f59e2b1d8c97`

The frozen Candidate identity was complete in the Campaign Spec and the worker loaded the approved Candidate. The worker runtime projection recorded the correct class, path, and source SHA-256. The parent comparator did not receive that frozen identity and instead retained generic router-extraction defaults. The resulting mismatch was an implementation error, not Candidate drift or a research result.

The Harness now binds independent Baseline and Candidate identity contracts through `Campaign Spec -> Attempt Manifest -> Worker -> Runtime Identity -> Parent Comparator`. Candidate class, path, source SHA-256, manifest SHA-256, experiment ID, and approved ablation unit are explicit. The parent comparator does not infer them from a directory, role, default Candidate, historical Registry, or historical attempt.

A missing expected identity stops before a Backtest process can start with `candidate_identity_contract_missing`. An actual loaded identity mismatch remains `runtime_candidate_identity_mismatch`.

Attempt 3 artifacts remain immutable at 81 files, 1,576,530 bytes, with tree SHA-256 `c279c499b904f53d19372367e867363ecdb6034bf3bb8dcf473d022aa50a7f05`. No Backtest, Validation, Holdout, or Hyperopt was run during this fix. A fourth execution attempt still requires separate human approval.
