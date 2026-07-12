# Router Extraction Attempt 1 False-positive Amendment

Attempt `router-extraction-semantic-equivalence-v1-attempt-1` is invalidated as an `implementation_error` with reason `signal_mask_semantic_projection_contaminated_by_runtime_identity`.

The attempt completed four BTC Backtests and stopped before ETH. Baseline and Candidate were each reproducible. Their final signal-row hash, signal counts, normalized trade hash, total/long/short trades, core metrics, enter tags and exit reasons were identical.

The comparator incorrectly included `role`, strategy class, module name/path and source SHA-256 in the signal semantic object. Those fields correctly differed across Baseline and Candidate, but they are runtime identity evidence rather than signal semantics.

Therefore this attempt cannot be used as evidence that router extraction changes strategy semantics. Its raw artifacts remain preserved under `research/results/stage4a-regime-conditioned-branch-factorization-v1/` and must not be reused by recertification.

Recertification is required after a versioned comparison contract separates `signal_semantic_projection_v1` from `runtime_identity_projection_v1`.
