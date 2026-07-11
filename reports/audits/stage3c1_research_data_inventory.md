# Stage 3C.1 Research Data Inventory

- Source dataset: `demo-btc-usdt-usdt-futures-acceptance-20260329-20260412`
- Strategy results used for split selection: `false`
- Acceptance fixture is not used for ranking and is placed in the embargo interval.

## Files

| key | candle type | timeframe | rows | start | end | bytes | sha256 | issues |
|---|---|---|---:|---|---|---:|---|---|
| `futures_1h` | `futures` | `1h` | 2928 | `2026-03-01 00:00:00+00:00` | `2026-06-30 23:00:00+00:00` | 89658 | `72d5205238a0263497d612ada03ead63686ef2a6846c1bc72d40e6262b478329` | `none` |
| `futures_4h` | `futures` | `4h` | 732 | `2026-03-01 00:00:00+00:00` | `2026-06-30 20:00:00+00:00` | 26914 | `0bb50d9d222d152899f69034def85202e37a90953644dd754fd13bb70249975c` | `none` |
| `mark_8h` | `mark` | `8h` | 363 | `2026-03-01 00:00:00+00:00` | `2026-06-30 16:00:00+00:00` | 15738 | `e5b5f9e2b43fc0d65c8b6c25199a552297b50015cc0cb9218a841402e71c16db` | `missing_or_irregular_candles` |
| `funding_rate_8h` | `funding_rate` | `8h` | 366 | `2026-03-01 00:00:00.005000+00:00` | `2026-06-30 16:00:00.005000+00:00` | 9234 | `295fe4bfb015629962461cd156fe073dcba98f842c7b5b4260ca78fa124edefd` | `none` |

## Use Assessment

- Development: allowed from the early source interval after deterministic time split.
- Validation: allowed from the later source interval after embargo and warm-up separation.
- Acceptance fixture: execution contract only, not ranking.
- Unsuitable: spot data and incomplete futures demo data.
