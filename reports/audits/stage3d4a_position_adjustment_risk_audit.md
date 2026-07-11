# Stage 3D.4-A Position Adjustment Risk Audit

- Current leverage: `1.0` observed; current `max_open_trades`: `1`; stake: `1500`.
- Stacking same-pair signals increases correlated nominal exposure; repeated setup signals are not diversification.
- Added exposure amplifies liquidation sensitivity, funding costs, drawdown, and stake-sizing error even at 1x leverage.
- Position adjustment requires an enabled callback path, order lifecycle accounting, partial-fill handling, wallet/precision checks, and independent funding/liquidation validation.
- The current Harness lacks certified adjustment-order reproducibility, aggregate exposure gates, and per-adjustment risk attribution.
- Conclusion: position stacking and adjustment remain high-risk and unauthorized.
