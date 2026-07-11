# Stage 3E.1 Temporal Data Coverage Audit

Strategy results were not used for this audit.

## development_v2

- Dataset: `futures-dev-btc-usdt-usdt-20240101-20240830-v2`
- Aggregate SHA-256: `3e86474ba634c3779389d818997d1626357090da7fef6b9f007ad0f9bbcfdd5c`

- `futures_1h`: `5800` rows, `2024-01-01T00:00:00+00:00` to `2024-08-29T15:00:00+00:00`, duplicates `0`, gaps `0`, SHA-256 `b5d2dd9cb7a34115ccdb2fd8b2044c1dc160f4d1e03af345387beb08452d0491`
- `futures_4h`: `1450` rows, `2024-01-01T00:00:00+00:00` to `2024-08-29T12:00:00+00:00`, duplicates `0`, gaps `0`, SHA-256 `3f2df1df5332d4e9a06330205da0717a6eaa3fee4b1da4367432db1242fbab60`
- `mark_8h`: `725` rows, `2024-01-01T00:00:00+00:00` to `2024-08-29T08:00:00+00:00`, duplicates `0`, gaps `0`, SHA-256 `658aa6b5d082a092e7a858744251a8f65f5c330c2ffddd45d570c3c9572f5922`
- `funding_rate_8h`: `725` rows, `2024-01-01T00:00:00+00:00` to `2024-08-29T08:00:00+00:00`, duplicates `0`, gaps `0`, SHA-256 `c830fdaa85e4ad375210b36bf0cf1e5f96aee426259e3762c5d785947b8fe585`

## validation_v2_baseline_only

- Dataset: `futures-validation-btc-usdt-usdt-20240912-20250128-v2`
- Aggregate SHA-256: `22927967300eaa286712d8c03c0bb40d84bc2b948291dfedff9fd9e13c92c2b7`

- `futures_1h`: `3300` rows, `2024-09-12T16:00:00+00:00` to `2025-01-28T03:00:00+00:00`, duplicates `0`, gaps `0`, SHA-256 `19b28d535dde40aa8e67e780c40013335ca0e917b8a3e9c6e03ec777fdfc668a`
- `futures_4h`: `825` rows, `2024-09-12T16:00:00+00:00` to `2025-01-28T00:00:00+00:00`, duplicates `0`, gaps `0`, SHA-256 `97743310a7d62c5212e052ea3f98ed796abd763ab46168e9540cc2d3c44751c5`
- `mark_8h`: `413` rows, `2024-09-12T16:00:00+00:00` to `2025-01-28T00:00:00+00:00`, duplicates `0`, gaps `0`, SHA-256 `4dee19ed361e2412b7d7d477f6516e4c13b63f87f8cb0cb1d306f32001424aa2`
- `funding_rate_8h`: `413` rows, `2024-09-12T16:00:00+00:00` to `2025-01-28T00:00:00+00:00`, duplicates `0`, gaps `0`, SHA-256 `5749d1218d28307d42449fb871cf1f934172cde703d3a3122e9f1595d2ef3ff2`

## Governance

- Acceptance Fixture is excluded from performance profiling.
- Development v2 supplies three slices.
- Validation v2 supplies one formal-strategy profiling slice and is not candidate tuning feedback.
- Holdout is not accessed.
- Additional provisioning required: `false`.
