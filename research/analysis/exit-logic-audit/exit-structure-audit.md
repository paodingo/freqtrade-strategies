# Exit Logic Structure Audit

- Temporal slices: `4`
- Total observed exits: `82`
- Aggregate exit counts: `{"force_exit": 2, "ranging_target_middle": 9, "roi": 40, "stop_loss": 28, "trending_time_stop": 3}`
- Prior direct exit deltas: `0`
- First-trigger conflicts: `0`
- Real missed reentry opportunities: `0`
- Result: `no_exit_change_warranted_insufficient_causal_evidence`

The negative slice has a high stop-loss share, but positive slices also contain material stop-loss exits. Exit-reason distribution alone is therefore not causal evidence for changing ROI, stoploss, time-stop, protections, or strategy logic. This Campaign makes no strategy or risk change.
