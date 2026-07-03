# TASK-0021A: V11.29 Non-Secret Config and Informative Mapping Audit

## Goal

Read-only inspect V11.29 non-secret config fields and strategy informative mapping to distinguish stale data, candle type mismatch, and fallback/performance issues.

## Preconditions

- Task 21 committed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task21a_v1129_non_secret_config_informative_mapping_audit.md`
- `tasks/active/TASK-0021A-v1129-non-secret-config-informative-mapping-audit.md`

## Forbidden files and surfaces

- `strategies/**` modifications
- `user_data/**` modifications
- `configs/**` modifications
- `dashboard/**` modifications
- `deploy/**` modifications
- bot lifecycle scripts
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords
- live/server write operation surface

## Execution boundaries

- Read-only SSH allowed.
- Read-only non-secret config grep allowed.
- Read-only strategy mapping inspection allowed.
- Do not print secrets.
- Do not download data.
- Do not modify config or strategy files.
- Do not start, stop, or restart containers.
- Do not run backtests.

## Completed work

- Confirmed V11.29 config uses futures isolated dry-run and StaticPairList.
- Confirmed 12-pair whitelist matches the pairs reporting 4h warnings.
- Confirmed strategy informative mapping uses `(pair, "4h")` without explicit futures candle type.
- Confirmed `_load_4h()` first queries DataProvider and then falls back to local futures feather files.
- Found no targeted fallback failure log in the checked window.
- Classified candle type mismatch as likely for the noisy DataProvider warning.
- Recommended Task 22 performance bottleneck audit as the next step.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification and commit. Do not enter Task 22 without explicit user instruction.
