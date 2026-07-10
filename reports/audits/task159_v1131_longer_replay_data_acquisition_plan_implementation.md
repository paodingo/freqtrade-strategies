# Task 159: V11.31 Longer Replay Data Acquisition Plan Implementation

## Summary

Implemented a plan-only V11.31 longer replay data acquisition artifact builder.
The task converts existing committed evidence into a bounded future acquisition
plan and does not perform acquisition.

Decision:

```text
plan_only_no_data_acquisition
```

## Sources Reviewed

```text
reports/v1131_observation/v1131_longer_replay_data_source_inventory.json
reports/audits/task148_v1131_longer_replay_data_acquisition_authorization.md
reports/audits/task156_v1131_data_acquisition_plan_guard_exception.md
```

## Files Generated

```text
scripts/build_v1131_longer_replay_data_acquisition_plan.js
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.md
```

## Current Evidence Used

| field | state |
|---|---|
| approved pair set | `ETH`, `SOL`, `DOGE`, `LINK`, `XRP`, `BCH` |
| observed 15m source rows per pair | `88271` |
| committed replay rows per pair | `240` |
| committed replay days per pair | `2.5` |
| 7d replay support from committed artifacts | `false` |
| 14d replay support from committed artifacts | `false` |
| 4h row-level source path | `unknown` |
| alpha/taker/protection evidence | `missing` / `unknown` |

## Boundaries Preserved

- No server access was performed.
- No data was downloaded, refreshed, copied, or generated.
- No backtest was run.
- No strategy or bot config files were modified.
- No secret files were read.
- No bot lifecycle command was run.
- No profitability, deployment, or replacement claim was made.

## Verification

Verification completed:

```powershell
node --check scripts/build_v1131_longer_replay_data_acquisition_plan.js
node scripts/build_v1131_longer_replay_data_acquisition_plan.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Result:

```text
node --check: pass
generator: pass
readiness: pass (9 changed path(s) checked)
```

## Recommended Next Task

Proceed with:

```text
Task 162: V11.31 Longer Replay Data Acquisition Execution Authorization
```
