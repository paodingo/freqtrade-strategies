# Stage 3D.4-A First-Trigger Semantics

## Verified Behavior

- Freqtrade 2025.8 shifts each closed-candle signal by one candle before execution.
- While flat, the earliest executable current signal is used; there is no false-to-true edge requirement.
- While a same-pair position is open and stacking is disabled, later same-direction signals are ignored and are not queued.
- After exit, an old in-position signal is not reused. A signal must still be true on a later raw candle to execute naturally on the next candle.
- Long/short or same-direction entry/exit collision is rejected before position checks.
- Strategy trending assignments run before ranging assignments; a same-side overlap keeps the entry boolean and the later ranging assignment overwrites `enter_tag`.

## Evidence

- `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\optimize\backtesting.py:1449`
- `strategies/regime_aware_base.py:240` and subsequent entry assignment order.
- `research/results/stage3d3b-candidate-process-isolation-recertification/stage3d3b-final-report.json` and per-run runtime signal diffs.
- Observed flat-state first-trigger conflicts among the 12 duplicate signals: `0`.
