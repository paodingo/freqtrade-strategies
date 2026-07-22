# Chan Structure Reversal Candidate Development Report

## Result

Classification: `development_rejected_material_degradation`

| Pair | Baseline trades | Candidate trades | Structure trades | Baseline return | Candidate return | Return delta | Baseline PF | Candidate PF | Baseline DD | Candidate DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BTC/USDT:USDT | 30 | 35 | 7 | 1.968% | 0.137% | -1.831pp | 1.287 | 1.017 | 1.727% | 2.522% |
| ETH/USDT:USDT | 27 | 38 | 15 | -0.121% | -4.154% | -4.033pp | 0.981 | 0.572 | 1.654% | 5.422% |

## Candidate boundary

- One isolated Candidate: `RegimeAwareChanStructureLongV1`.
- One new signal group, long side only.
- Signal: confirmed bottom -> close above preceding swing high -> confirmed higher low.
- Signal is emitted on the retest confirmation candle; it is never backdated.
- Existing entries, exits, ROI, stoploss, leverage, stake, protections and execution configuration are unchanged.

## Execution boundary

- Matrix: BTC/ETH x Baseline/Candidate x RUN-A/RUN-B = `8` calls.
- Timerange/timeframe: `20240609-20240811` / `1h`.
- Fee: `0.0004`; sealed offline exchange adapter; allowed loopback IPC / forbidden network attempts: `8 / 0`.
- Fresh-process reproducibility: `true`.
- Validation/Holdout accesses: `0 / 0`.

## Decision

This development result cannot promote or replace the formal strategy. Validation, forward dry-run, live trading, and any follow-up Candidate require separate decisions.
