# Stage 3D.4-A Single-Threshold Research Closure

All four current single-threshold directions are closed as `single_threshold_search_exhausted`.

## ranging_long_setup.rsi_max

- Tested values: `[41.10393009, 42.42420359, 45.0]`
- Trade-changing experiments: `[]`
- Development: `{'41.10393009': 'not_run_behavior_unchanged', '42.42420359': 'not_run_behavior_unchanged', '45.0': 'not_run_behavior_unchanged'}`
- Blocker/diagnosis: `existing_same_direction_position` / `additional signals are reachable but occur inside existing same-direction positions`
- Neighbor-value information gain: `low`
- Uncovered effective interval evidence: `false`

## ranging_short_setup.bb_percent_min

- Tested values: `[0.79578426, 0.75]`
- Trade-changing experiments: `[]`
- Development: `{'0.79578426': 'not_run_behavior_unchanged', '0.75': 'not_run_behavior_unchanged'}`
- Blocker/diagnosis: `existing_same_direction_position` / `additional signals are reachable but occur inside existing same-direction positions`
- Neighbor-value information gain: `low`
- Uncovered effective interval evidence: `false`

## ranging_short_setup.rsi_min

- Tested values: `[57.29961157, 56.88531804, 55.0]`
- Trade-changing experiments: `[6, 7, 8]`
- Development: `{'57.29961157': 'development_ineligible_no_material_improvement', '56.88531804': 'development_ineligible_risk_degradation', '55.0': 'development_ineligible_no_material_improvement'}`
- Blocker/diagnosis: `development_gate_rejection` / `signal_quality_and_entry_timing_not_numeric_reachability: all values create trades; two add no material improvement and the middle relaxation degrades risk`
- Neighbor-value information gain: `low`
- Uncovered effective interval evidence: `false`

## ranging_shared.adx_4h_max_long

- Tested values: `[22.16370727, 22.90931181]`
- Trade-changing experiments: `[]`
- Development: `{'22.16370727': 'not_run_behavior_unchanged', '22.90931181': 'not_run_behavior_unchanged'}`
- Blocker/diagnosis: `existing_same_direction_position` / `additional signals are reachable but occur inside existing same-direction positions`
- Neighbor-value information gain: `low`
- Uncovered effective interval evidence: `false`
