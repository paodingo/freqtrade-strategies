# TASK-0020S: Legacy Dry-Run Container Stop Decision Plan

## Goal

Read-only decide whether legacy dry-run containers `freqtrade-v1116` and `freqtrade-v1127` can be stopped to reduce server resource pressure.

## Preconditions

- Task 20 committed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task20s_legacy_dry_run_container_stop_decision_plan.md`
- `tasks/active/TASK-0020S-legacy-dry-run-container-stop-decision-plan.md`

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
- live/server write operation surface

## Execution boundaries

- Read-only SSH allowed.
- Read-only `docker ps`, `docker stats --no-stream`, `docker logs --tail`, `docker exec` SQLite queries allowed.
- Do not run `docker inspect`.
- Do not read `.env` or `user_data/monitor.env`.
- Do not start, stop, restart, or remove containers.
- Do not run `freqtrade trade`.
- Do not run backtests.
- Do not modify server files.
- Do not modify strategies, configs, dashboard, or deploy.

## Completed work

- Confirmed `freqtrade-v1127` has no trades, orders, open trades, or open orders.
- Confirmed `freqtrade-v1116` has no open trades or open orders, but has one closed trade and two orders.
- Found dashboard default references to `v1116` / `8109`.
- Recommended stopping `freqtrade-v1127` first in a separate authorized stop task.
- Recommended not stopping `freqtrade-v1116` until dashboard dependency is resolved.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification and commit. Do not stop any container in this task.
