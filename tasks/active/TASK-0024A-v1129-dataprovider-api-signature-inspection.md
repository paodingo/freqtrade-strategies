# TASK-0024A: V11.29 DataProvider API Signature Inspection

## Goal

Read-only inspect Freqtrade 2026.5.1 DataProvider and informative pair APIs to decide the safe V11.29 4h candle type mapping fix.

## Preconditions

- Task 24 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task24a_v1129_dataprovider_api_signature_inspection.md`
- `tasks/active/TASK-0024A-v1129-dataprovider-api-signature-inspection.md`

## Forbidden operations

- Modify strategies.
- Modify bot configs.
- Modify dashboard or deploy files.
- Read `.env`.
- Read `user_data/monitor.env`.
- Print secrets.
- Start, stop, or restart bots.
- Run backtests.
- Claim V11.29 replacement readiness.

## Completed work

- Inspected `DataProvider.get_pair_dataframe()` signature.
- Inspected `DataProvider.ohlcv()` behavior.
- Inspected `CandleType` values.
- Inspected `PairWithTimeframe` type.
- Confirmed current strategy lacks `informative_pairs()` override.
- Recommended Task 24F strategy-code patch.

## Stop condition

Stop after report, verification, commit, and push. Do not enter Task 24F automatically.

