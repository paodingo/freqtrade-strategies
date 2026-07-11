# Stage 3C.2-R Evaluation Data Coverage Audit

## 结论

- Verdict: `data_provisioning_blocked`
- Strategy results used: `false`
- Acceptance fixture can be Development: `false`
- Best complete source: `demo-btc-usdt-usdt-futures-acceptance-202603-202606`
- Max continuous research range: `2026-03-01T00:00:00Z` to `2026-06-28T16:00:00Z`
- Main 1h candles available: `2873`
- Required main 1h candles: `5000`
- Missing main 1h candles: `2127`

因此本地数据不足以创建真实 sealed Development/Validation v2。Stage 3C.2-R 只能冻结 split v2 政策和 provisioning blocker，不能运行策略 readiness probe。

## Dataset Inventory

| dataset | complete | sealed | acceptance | files | continuous range | 1h candles |
|---|---:|---:|---:|---:|---|---:|
| `demo-btc-usdt-usdt-futures-1h-202401` | `false` | `true` | `false` | 3 | `None` to `None` | 0 |
| `demo-btc-usdt-usdt-futures-acceptance-202603-202606` | `true` | `true` | `true` | 4 | `2026-03-01T00:00:00Z` to `2026-06-28T16:00:00Z` | 2873 |
| `demo-btc-usdt-usdt-futures-acceptance-20260329-20260412` | `true` | `true` | `true` | 4 | `2026-03-01T00:00:00Z` to `2026-06-28T16:00:00Z` | 2873 |
| `futures-dev-btc-usdt-usdt-20260301-20260328-v1` | `true` | `true` | `false` | 4 | `2026-03-01T00:00:00Z` to `2026-03-28T16:00:00Z` | 665 |
| `futures-validation-btc-usdt-usdt-20260503-20260628-v1` | `true` | `true` | `false` | 4 | `2026-05-03T00:00:00.005000Z` to `2026-06-28T16:00:00Z` | 1360 |

## File Details

### `demo-btc-usdt-usdt-futures-1h-202401`

| key | type | timeframe | audit | rows | start | end | continuous_end | dup | gaps | bytes | sha256 | source |
|---|---|---|---|---:|---|---|---|---:|---:|---:|---|---|
| `funding_rate_8h` | `funding_rate` | `8h` | `file_read` | 93 | `2024-01-01T00:00:00Z` | `2024-01-31T16:00:00Z` | `2024-01-31T16:00:00Z` | 0 | 0 | 4426 | `a65627ec7c712555681a28078977a0a7c845d4a2074027b2a610835eb6be5468` | `research/data/snapshots/demo-btc-usdt-usdt-futures-1h-202401/data/futures/BTC_USDT_USDT-8h-funding_rate.feather` |
| `futures_1h` | `futures` | `1h` | `file_read` | 744 | `2024-01-01T00:00:00Z` | `2024-01-31T23:00:00Z` | `2024-01-31T23:00:00Z` | 0 | 0 | 26370 | `2671ca1956e44cd064a4039d390d5bb7f7f653696e69ac830c8cad9c1e21be61` | `research/data/snapshots/demo-btc-usdt-usdt-futures-1h-202401/data/futures/BTC_USDT_USDT-1h-futures.feather` |
| `mark_1h` | `mark` | `1h` | `file_read` | 744 | `2024-01-01T00:00:00Z` | `2024-01-31T23:00:00Z` | `2024-01-31T23:00:00Z` | 0 | 0 | 29434 | `2393927b3a394cf43b10917b1f32535f41cea00fd4d7f5c657368215a5cf8397` | `research/data/snapshots/demo-btc-usdt-usdt-futures-1h-202401/data/futures/BTC_USDT_USDT-1h-mark.feather` |

### `demo-btc-usdt-usdt-futures-acceptance-202603-202606`

| key | type | timeframe | audit | rows | start | end | continuous_end | dup | gaps | bytes | sha256 | source |
|---|---|---|---|---:|---|---|---|---:|---:|---:|---|---|
| `funding_rate_8h` | `funding_rate` | `8h` | `file_read` | 366 | `2026-03-01T00:00:00Z` | `2026-06-30T16:00:00Z` | `2026-06-30T16:00:00Z` | 0 | 0 | 9234 | `295fe4bfb015629962461cd156fe073dcba98f842c7b5b4260ca78fa124edefd` | `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-202603-202606/data/futures/BTC_USDT_USDT-8h-funding_rate.feather` |
| `futures_1h` | `futures` | `1h` | `file_read` | 2928 | `2026-03-01T00:00:00Z` | `2026-06-30T23:00:00Z` | `2026-06-30T23:00:00Z` | 0 | 0 | 89658 | `72d5205238a0263497d612ada03ead63686ef2a6846c1bc72d40e6262b478329` | `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-202603-202606/data/futures/BTC_USDT_USDT-1h-futures.feather` |
| `futures_4h` | `futures` | `4h` | `file_read` | 732 | `2026-03-01T00:00:00Z` | `2026-06-30T20:00:00Z` | `2026-06-30T20:00:00Z` | 0 | 0 | 26914 | `0bb50d9d222d152899f69034def85202e37a90953644dd754fd13bb70249975c` | `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-202603-202606/data/futures/BTC_USDT_USDT-4h-futures.feather` |
| `mark_8h` | `mark` | `8h` | `file_read` | 363 | `2026-03-01T00:00:00Z` | `2026-06-30T16:00:00Z` | `2026-06-28T16:00:00Z` | 0 | 1 | 15738 | `e5b5f9e2b43fc0d65c8b6c25199a552297b50015cc0cb9218a841402e71c16db` | `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-202603-202606/data/futures/BTC_USDT_USDT-8h-mark.feather` |

### `demo-btc-usdt-usdt-futures-acceptance-20260329-20260412`

| key | type | timeframe | audit | rows | start | end | continuous_end | dup | gaps | bytes | sha256 | source |
|---|---|---|---|---:|---|---|---|---:|---:|---:|---|---|
| `funding_rate_8h` | `funding_rate` | `8h` | `file_read` | 366 | `2026-03-01T00:00:00Z` | `2026-06-30T16:00:00Z` | `2026-06-30T16:00:00Z` | 0 | 0 | 9234 | `295fe4bfb015629962461cd156fe073dcba98f842c7b5b4260ca78fa124edefd` | `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-20260329-20260412/data/futures/BTC_USDT_USDT-8h-funding_rate.feather` |
| `futures_1h` | `futures` | `1h` | `file_read` | 2928 | `2026-03-01T00:00:00Z` | `2026-06-30T23:00:00Z` | `2026-06-30T23:00:00Z` | 0 | 0 | 89658 | `72d5205238a0263497d612ada03ead63686ef2a6846c1bc72d40e6262b478329` | `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-20260329-20260412/data/futures/BTC_USDT_USDT-1h-futures.feather` |
| `futures_4h` | `futures` | `4h` | `file_read` | 732 | `2026-03-01T00:00:00Z` | `2026-06-30T20:00:00Z` | `2026-06-30T20:00:00Z` | 0 | 0 | 26914 | `0bb50d9d222d152899f69034def85202e37a90953644dd754fd13bb70249975c` | `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-20260329-20260412/data/futures/BTC_USDT_USDT-4h-futures.feather` |
| `mark_8h` | `mark` | `8h` | `file_read` | 363 | `2026-03-01T00:00:00Z` | `2026-06-30T16:00:00Z` | `2026-06-28T16:00:00Z` | 0 | 1 | 15738 | `e5b5f9e2b43fc0d65c8b6c25199a552297b50015cc0cb9218a841402e71c16db` | `research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-20260329-20260412/data/futures/BTC_USDT_USDT-8h-mark.feather` |

### `futures-dev-btc-usdt-usdt-20260301-20260328-v1`

| key | type | timeframe | audit | rows | start | end | continuous_end | dup | gaps | bytes | sha256 | source |
|---|---|---|---|---:|---|---|---|---:|---:|---:|---|---|
| `funding_rate_8h` | `funding_rate` | `8h` | `file_read` | 84 | `2026-03-01T00:00:00Z` | `2026-03-28T16:00:00Z` | `2026-03-28T16:00:00Z` | 0 | 0 | 4914 | `bba32209bc604e71475a9920cff943c8043492214a158f893d0908fc31a6fda3` | `research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/data/futures/BTC_USDT_USDT-8h-funding_rate.feather` |
| `futures_1h` | `futures` | `1h` | `file_read` | 672 | `2026-03-01T00:00:00Z` | `2026-03-28T23:00:00Z` | `2026-03-28T23:00:00Z` | 0 | 0 | 24354 | `8ecb7a280c80ebab8fd3ead6e553ad1c91ea4746c26de4f57ae9cdf337ea5a65` | `research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/data/futures/BTC_USDT_USDT-1h-futures.feather` |
| `futures_4h` | `futures` | `4h` | `file_read` | 168 | `2026-03-01T00:00:00Z` | `2026-03-28T20:00:00Z` | `2026-03-28T20:00:00Z` | 0 | 0 | 9274 | `2b4a6ea576f9932bb7498773ef2d002cd42833469095c4511bd126c46f971ba2` | `research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/data/futures/BTC_USDT_USDT-4h-futures.feather` |
| `mark_8h` | `mark` | `8h` | `file_read` | 84 | `2026-03-01T00:00:00Z` | `2026-03-28T16:00:00Z` | `2026-03-28T16:00:00Z` | 0 | 0 | 6498 | `774873f7374a1c879b9db3b29ac40c5df8bc46afcd577d31cf9656ba2d6e1065` | `research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/data/futures/BTC_USDT_USDT-8h-mark.feather` |

- Sealed Validation data audit mode: `manifest_only`; data files are not opened for candidate evaluation.

### `futures-validation-btc-usdt-usdt-20260503-20260628-v1`

| key | type | timeframe | audit | rows | start | end | continuous_end | dup | gaps | bytes | sha256 | source |
|---|---|---|---|---:|---|---|---|---:|---:|---:|---|---|
| `funding_rate_8h` | `funding_rate` | `8h` | `manifest_only` | 171 | `2026-05-03T00:00:00.005000Z` | `2026-06-28T16:00:00Z` | `2026-06-28T16:00:00Z` | 0 | 0 | 6226 | `f1fab5e712b8facbb81970534ee7b2321231ec511d2d55603e1a026cb543b55b` | `research/data/snapshots/futures-validation-btc-usdt-usdt-20260503-20260628-v1/data/futures/BTC_USDT_USDT-8h-funding_rate.feather` |
| `futures_1h` | `futures` | `1h` | `manifest_only` | 1361 | `2026-05-03T00:00:00Z` | `2026-06-28T16:00:00Z` | `2026-06-28T16:00:00Z` | 0 | 0 | 45026 | `48f5adb98e746ce1eeeb5197345c0900989268ed723bfc0d9bcb9d62572fce8c` | `research/data/snapshots/futures-validation-btc-usdt-usdt-20260503-20260628-v1/data/futures/BTC_USDT_USDT-1h-futures.feather` |
| `futures_4h` | `futures` | `4h` | `manifest_only` | 341 | `2026-05-03T00:00:00Z` | `2026-06-28T16:00:00Z` | `2026-06-28T16:00:00Z` | 0 | 0 | 14890 | `b171368dac842ea37c4751294db955dac1fd0ae37c391cc5c400c8c2ebb685a3` | `research/data/snapshots/futures-validation-btc-usdt-usdt-20260503-20260628-v1/data/futures/BTC_USDT_USDT-4h-futures.feather` |
| `mark_8h` | `mark` | `8h` | `manifest_only` | 171 | `2026-05-03T00:00:00Z` | `2026-06-28T16:00:00Z` | `2026-06-28T16:00:00Z` | 0 | 0 | 9418 | `a49e056b03fb6179b219913ca96f5c2d4b4f27a717460c490581bab36bd8fea3` | `research/data/snapshots/futures-validation-btc-usdt-usdt-20260503-20260628-v1/data/futures/BTC_USDT_USDT-8h-mark.feather` |

## Provisioning Plan

- 需要 Campaign 明确授权 `provisioning_mode` 后，才允许通过 Binance public market-data endpoint 补充 USD-M futures 数据。
- 目标是形成不少于 `5000` 根连续 Development 评价 1h K 线，另加完整 startup/warm-up。
- 同期必须具备 `4h futures` informative、`8h mark` 和 `8h funding_rate` 完整数据。
- 不得访问 account/private/trade API，不得读取 secret，不得使用 sealed holdout。
