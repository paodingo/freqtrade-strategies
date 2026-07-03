# TASK-0020: V11.29 Data Coverage and Runtime Performance Audit

## Goal

Read-only audit V11.29 server-side data coverage, runtime performance warnings, and container resource pressure. Decide whether legacy containers can be considered for a separate stop-decision task.

## Preconditions

- Task 20G committed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task20_v1129_data_coverage_runtime_performance_audit.md`
- `tasks/active/TASK-0020-v1129-data-coverage-runtime-performance-audit.md`

## Forbidden files and surfaces

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- bot lifecycle scripts
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords
- V10.8.2 strategy/config
- V11.29 strategy/config
- live/server write operation surface

## Execution boundaries

- Read-only SSH allowed.
- Read-only `docker ps`, `docker stats --no-stream`, `docker logs --tail`, `df`, and `docker exec ls/find` allowed.
- Do not run `docker inspect`.
- Do not read `.env` or `user_data/monitor.env`.
- Do not start, stop, restart, or remove containers.
- Do not run `freqtrade trade`.
- Do not run backtests.
- Do not modify server files.
- Do not modify strategies or bot configs.
- Do not claim V11.29 passed real execution validation.
- Do not claim V11.29 can replace V10.8.2.

## Completed work

- Confirmed four Freqtrade containers are running: V11.29, V11.27, V11.16, and V10.8.2.
- Captured resource snapshot showing V11.16 and V11.29 as the main CPU/memory candidates.
- Confirmed server data directory exists and contains futures 15m / 1h / 4h files.
- Concluded that "4h files are completely absent" is not proven.
- Recommended separate stop-decision review for V11.16 and V11.27.
- Recommended keeping V11.29 and V10.8.2 running for now unless a separate stop task authorizes otherwise.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification and commit. Do not stop any server process in this task.
