# Stage 3A Futures Acceptance Coverage Audit

Date: 2026-07-10

## Scope

This audit establishes a futures execution-semantics fixture for `RegimeAwareV6`.
It does not modify the strategy, does not rank candidates, and does not use
profit, drawdown, Profit Factor, or Sharpe as fixture selection criteria.

## Strategy Contract

- Strategy: `strategies/RegimeAwareV6.py`
- Strategy SHA256: `1A422F41AB801746C2EE39F5D20722B26B674098BCA6AC1684E78BD8E7285509`
- Base Git SHA: `a3e5f0826e9a74396a9648a661aaa88f1c46900a`
- `timeframe`: `1h`
- `startup_candle_count`: `200`
- `can_short`: inherited `True` from `RegimeAwareBaseMixin`
- Informative timeframes: `4h` futures from `informative_pairs()`
- Entry generation: `populate_entry_trend()` initializes both `enter_long` and
  `enter_short`; `_populate_trending_entries()` can set `trending_long` and
  `trending_short`; `_populate_ranging_entries()` can set `ranging_long` and
  `ranging_short` because `RegimeAwareV6.enable_ranging_entries = True`.

## Current Baseline Gap

The previous Stage 3A futures baseline used
`demo-btc-usdt-usdt-futures-1h-202401` over `20240101-20240131`.
That snapshot contained 1h futures, 1h mark, and 8h funding data, but did not
contain the strategy-required 4h futures informative file and did not include
the 8h mark candles Freqtrade expects for futures funding/mark handling.

Result classification was corrected:

- Zero or insufficient fixture coverage is `validation_error`.
- Reason code is `acceptance_fixture_no_trades` for zero trades or
  `baseline_coverage_insufficient` for missing long/short coverage.
- This condition is not `candidate_rejected`, does not count as a candidate
  failure, and does not affect Champion/Challenger records.

## Historical Evidence

Existing historical reports show that the strategy family can produce real
futures long and short trades:

- `docs/backtests/2026-06-11-v66-alpha-risk-backtest.md`
  - Pair: `BTC/USDT:USDT`
  - Timeframe: `15m`
  - Full coverage window: `2026-06-04` to `2026-06-10`
  - Baseline long/short: `5 / 45`
- `docs/backtests/2026-06-11-v66-alpha-family-30d.summary.json`
  - Window: `2026-05-12` to `2026-06-10`
  - Alpha-family examples include long and short counts, but these are not the
    exact `RegimeAwareV6` 1h fixture and were used only as coverage evidence.

Because exact `RegimeAwareV6` 1h evidence was not already frozen, the fallback
scan used authorized sealed data in chronological order.

## Provisioned Fixture Data

New sealed snapshot:

- Dataset ID: `demo-btc-usdt-usdt-futures-acceptance-20260329-20260412`
- Manifest: `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-20260329-20260412/manifest.yaml`
- Aggregate SHA256: `b556d7db23144614225b732a22c5e91bcc0efb2dd170e112d555ae7f70279736`
- Pair: `BTC/USDT:USDT`
- Trading mode: `futures`
- Margin mode: `isolated`
- Timeframes sealed: `1h`, `4h`, `8h`
- Candle types: `futures`, `mark`, `funding_rate`
- File coverage: `2026-03-01` to `2026-06-30`
- Fixture timerange: `20260329-20260412`
- `execution_baseline_only`: `true`
- `suitable_for_strategy_ranking`: `false`
- `funding_model_synthetic`: `false`

The snapshot was created in provisioning mode from Binance public monthly USD-M
archives and is not mutable during campaign execution.

## Window Selection

Acceptance coverage criteria:

```yaml
coverage:
  min_total_trades: 2
  min_long_trades: 1
  min_short_trades: 1
  require_closed_trades: true
  require_enter_tag: true
  require_exit_reason: true
```

Chronological scan results:

| Order | Timerange | Total | Long | Short | Coverage verdict | Reason |
|---:|---|---:|---:|---:|---|---|
| 0 | `20260315-20260329` | 0 | 0 | 0 | incomplete | `acceptance_fixture_no_trades` |
| 1 | `20260322-20260405` | 1 | 0 | 1 | incomplete | `baseline_coverage_insufficient` |
| 2 | `20260329-20260412` | 3 | 2 | 1 | passed | first window satisfying coverage |

The selected window is the first chronological window satisfying execution
coverage. Profit, drawdown, Profit Factor, and win rate were not used to rank or
select the window.

## Fixture Acceptance Result

Offline control probe:

- Report: `research/results/demo-futures-stage3a5-acceptance/2/OFFLINE-CONTROL-PROBE/runner-report.json`
- Metrics: `research/results/demo-futures-stage3a5-acceptance/2/OFFLINE-CONTROL-PROBE/metrics.json`
- Total trades: `3`
- Long trades: `2`
- Short trades: `1`
- Closed trades: `3`
- Missing `enter_tag`: `0`
- Missing `exit_reason`: `0`
- Funding fees parsed: `0.20088932145673266`
- Average leverage parsed: `1.0`
- Verdict: passed coverage gate

## Reproducibility

Offline no-network independent runs:

- RUN-A: `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-offline-repro-001/RUN-A`
- RUN-B: `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-offline-repro-001/RUN-B`
- Comparison: `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-offline-repro-001/run-a-run-b-comparison.json`
- Input fingerprint: `efc441d255c7a3f57182851809cdded62fc8d231357f67c0d63fa223a9cdc40a`
- Core metrics consistent: `true`
- Normalized futures trade hash consistent: `true`
- Differences: none

## Online Baseline Status

Stage 3A.5-F3 subsequently completed the futures online/offline adapter
certification with an explicit research-only `httpsProxy` because direct local
TCP/TLS connectivity to `fapi.binance.com` timed out.

Certification report:

- `reports/audits/stage3a5_futures_online_offline_adapter_certification.md`

Final status:

- FUTURES-ONLINE-BASELINE: passed
- FUTURES-OFFLINE-CONTROL: passed
- Online/offline semantic comparison: consistent
- Stage 3A: complete for this fixed futures acceptance fixture

## Conclusion

The project now has a real, sealed futures acceptance fixture with long and
short trade coverage for unmodified `RegimeAwareV6`. Offline sealed execution,
RUN-A/RUN-B reproducibility, and the Stage 3A.5-F3 online/offline adapter
certification all pass.
