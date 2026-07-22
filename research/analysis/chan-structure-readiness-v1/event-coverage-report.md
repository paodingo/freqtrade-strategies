# Causal Structure Event Coverage Audit

## Result

Verdict: `ready_for_candidate_design_review`

This is a development-only, descriptive coverage audit. It is not a backtest and does not establish a 15m V11.30 edge.

| Pair | Candles | Bottoms | Tops | Long breaks | Long retests | Short breaks | Short retests | Causality | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| BTC/USDT:USDT | 4552 | 629 | 655 | 382 | 141 | 345 | 131 | pass | pass |
| ETH/USDT:USDT | 4552 | 637 | 644 | 391 | 169 | 349 | 144 | pass | pass |

The frozen readiness gate requires at least `10` unique confirmed retest signals per side and pair, zero hourly gaps, and prefix-invariance causality checks.

## Frozen semantics

- Pivot radius: `2` bars. A pivot at `t` is emitted only at the close of `t+2`.
- Break window: `24` bars after initial pivot confirmation.
- Retest window: `12` bars after the break.
- Long: confirmed bottom -> close above the preceding swing high -> confirmed higher low.
- Short: confirmed top -> close below the preceding swing low -> confirmed lower high.
- Signal timestamps are confirmation-candle close timestamps. No signal is backdated to the pivot candle.

## Data boundary

- Common evaluation window: `2024-02-03T08:00:00+00:00` to `2024-08-11T00:00:00+00:00`.
- Timeframe: `1h`; no sealed development-only `15m` dataset is available in the repository.
- Validation and Holdout accesses: `0 / 0`.

- `BTC/USDT:USDT` mode: `canonical_development_snapshot`
  - `research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/data/futures/BTC_USDT_USDT-1h-futures.feather` (`sha256=b5d2dd9cb7a34115ccdb2fd8b2044c1dc160f4d1e03af345387beb08452d0491`, verified)
- `ETH/USDT:USDT` mode: `canonical_development_snapshot`
  - `research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/data/futures/ETH_USDT_USDT-1h-futures.feather` (`sha256=cc4d8387fe95727f1d46ae9c69380f250a3af39da5e232cb93baaaff6d3ed94f`, verified)

## Decision boundary

Next step: human review of one structure-branch candidate design; separate authorization required.

No strategy was modified, no Candidate was created, no Backtest was run, and no live/dry-run bot was touched.
