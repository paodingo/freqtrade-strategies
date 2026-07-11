# Stage 3D.4-B Research Branch Closure

## Decision

The human-approved decision is `A_keep_current`. Existing first-trigger and entry execution semantics remain unchanged. The branch status is `closed_evidence_exhausted`; engineering validity remains `verified`, and no code change is required.

## Research Scope And Tested Values

- `ranging_long_setup.rsi_max`: `[41.10393009, 42.42420359, 45.0]`
- `ranging_short_setup.bb_percent_min`: `[0.79578426, 0.75]`
- `ranging_short_setup.rsi_min`: `[57.29961157, 56.88531804, 55.0]`
- `ranging_shared.adx_4h_max_long`: `[22.16370727, 22.90931181]`

The Stage 3D.2-B module-cache defect invalidated original experiments 2-10. Stage 3D.3-B preserved that history, introduced fresh-process runtime identity checks, and recertified experiments 1-10. All ten changed reachable signals. Experiments 6, 7, and 8 changed trades; none passed the Development Gate (no material improvement, risk degradation, no material improvement).

## Signal-To-Trade And Lifecycle Conclusion

Twelve same-direction signals occurred while positions were already open. Ten expired before flat. Two setups later appeared independently and were opened by current semantics. There were zero uncaptured post-exit re-entry opportunities. Signal persistence, carry-over, position stacking, and position adjustment therefore have no demonstrated low-risk value in this scope.

## Governance

All four variables are `closed_for_current_scope` and `single_threshold_search_allowed: false`. Adjacent values, wider ranges, more backtests, lack of an eligible candidate, poor results, or an LLM hunch do not reopen the branch.

## Reopen Conditions

- `human_approved_new_dataset_or_market_scope`
- `new_pair_or_timeframe`
- `human_approved_strategy_structural_change`
- `new_evidence_of_uncaptured_independent_post_exit_reentry`
- `changed_first_trigger_execution_semantics`
- `human_approved_multivariable_mechanism_research`
- `newly_discovered_research_validity_defect`

## Approval And Integrity

Approval event: `stage3d4b-a-keep-current-human-approval`. Proposal preapproval and postapproval hashes are explicit. Historical Stage 3D.1, 3D.2-B, 3D.3-B, and 3D.4-A evidence remains referenced and unmodified by this closure operation.

## Artifact Index

- `preapproval_snapshot`: `research/closures/stage3d4b-preapproval-proposal-snapshot.yaml`
- `approval_event`: `research/closures/stage3d4b-mechanism-approval-event.json`
- `approved_decision`: `research/closures/stage3d4b-approved-mechanism-decision.yaml`
- `proposal`: `research/proposals/stage3d4b-mechanism-proposal.yaml`
- `closure`: `research/closures/regime-aware-ranging-thresholds-v1.yaml`
- `final_json`: `research/closures/stage3d4b-final-closure.json`
- `final_markdown`: `reports/closures/stage3d4b_regime_aware_threshold_branch_closure.md`
- `stage3d4a_evidence`: `research/analysis/stage3d4a-final-report.json`
- `stage3d3b_recertification`: `research/results/stage3d3b-candidate-process-isolation-recertification/stage3d3b-final-report.json`
- `invalidation_event`: `research/recertification/stage3d3b/stage3d2b-invalidation-event.json`
- `historical_amendment`: `reports/amendments/stage3d2b-runtime-cache-invalidation.md`
