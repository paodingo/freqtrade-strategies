# Stage 3B.2 Single Variable Selection

This audit is read-only with respect to official strategy sources.

## Selected Variable

- Variable: `ranging_short_setup.bb_percent_min`
- Current value: `0.8`
- New value: `0.85`
- Source: `strategies/regime_aware_base.py:231`
- Decision surface: `short entry`
- Rule: increase the existing ranging-short bb_percent threshold by 0.05 within [0.0, 1.0]
- Hypothesis: Increasing this short-entry threshold may reduce some ranging short entry signals.

## Excluded Forbidden Variables

- `can_short`: explicitly forbidden
- `timeframe`: explicitly forbidden
- `startup_candle_count`: explicitly forbidden
- `stoploss`: explicitly forbidden
- `minimal_roi`: explicitly forbidden

## Candidate Thresholds

- `literal_threshold_line_188` at `strategies/regime_aware_base.py:188` = `40`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_199` at `strategies/regime_aware_base.py:199` = `40`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_199` at `strategies/regime_aware_base.py:199` = `45`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_211` at `strategies/regime_aware_base.py:211` = `60`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_219` at `strategies/regime_aware_base.py:219` = `60`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_219` at `strategies/regime_aware_base.py:219` = `55`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_228` at `strategies/regime_aware_base.py:228` = `22`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_235` at `strategies/regime_aware_base.py:235` = `22`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_173` at `strategies/regime_aware_base.py:173` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_176` at `strategies/regime_aware_base.py:176` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_182` at `strategies/regime_aware_base.py:182` = `25`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_186` at `strategies/regime_aware_base.py:186` = `0.02`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_205` at `strategies/regime_aware_base.py:205` = `25`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_209` at `strategies/regime_aware_base.py:209` = `0.02`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_343` at `strategies/regime_aware_base.py:343` = `65`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_352` at `strategies/regime_aware_base.py:352` = `35`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_357` at `strategies/regime_aware_base.py:357` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_262` at `strategies/regime_aware_base.py:262` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_277` at `strategies/regime_aware_base.py:277` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_289` at `strategies/regime_aware_base.py:289` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_299` at `strategies/regime_aware_base.py:299` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_309` at `strategies/regime_aware_base.py:309` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_338` at `strategies/regime_aware_base.py:338` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_341` at `strategies/regime_aware_base.py:341` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_347` at `strategies/regime_aware_base.py:347` = `0`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_350` at `strategies/regime_aware_base.py:350` = `0`: not selected; surface `entry/filter`; risk `medium`
- `ranging_short_setup.bb_percent_min` at `strategies/regime_aware_base.py:231` = `0.8`: selected; surface `short entry`; risk `low`
- `literal_threshold_line_232` at `strategies/regime_aware_base.py:232` = `60`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_223` at `strategies/regime_aware_base.py:223` = `0.2`: not selected; surface `entry/filter`; risk `medium`
- `literal_threshold_line_224` at `strategies/regime_aware_base.py:224` = `40`: not selected; surface `entry/filter`; risk `medium`
