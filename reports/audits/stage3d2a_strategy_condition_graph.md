# Stage 3D.2-A Strategy Condition Graph

- Base strategy: `RegimeAwareV6`
- Base strategy SHA-256: `1A422F41AB801746C2EE39F5D20722B26B674098BCA6AC1684E78BD8E7285509`
- AST extracted expressions: `34`

## Signal Groups

- `trending_long_entry`: `regime_trending AND trend_4h_up AND close_gt_ema200 AND trending_long_trigger_any AND volume_gt_0`
- `trending_short_entry`: `regime_trending AND trend_4h_down AND close_lt_ema200 AND trending_short_trigger_any AND volume_gt_0`
- `ranging_long_entry`: `regime_ranging AND rlong_bb_percent_lt_0_20 AND rlong_rsi_lt_40 AND rlong_volume_gt_mean_0_8 AND rlong_close_gt_ema200_0_92 AND rlong_bb_width_4h_lt_mean_1_3 AND rlong_adx_4h_lt_22 AND close_gt_ema200 AND volume_gt_0`
- `ranging_short_entry`: `regime_ranging AND rshort_bb_percent_gt_0_80 AND rshort_rsi_gt_60 AND rshort_volume_gt_mean_0_8 AND rshort_bb_width_4h_lt_mean_1_3 AND rshort_adx_4h_lt_22 AND close_lt_ema200 AND volume_gt_0`
- `ranging_breakdown_exit_long`: `regime_ranging AND exit_long_close_lt_ema200_0_90 AND volume_gt_0`
