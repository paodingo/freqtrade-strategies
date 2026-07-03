# TASK-0020S-STOP: Stop Legacy V1127 and V1116 Containers

## Goal

Stop legacy dry-run containers `freqtrade-v1127` and `freqtrade-v1116` after explicit user authorization, while preserving `freqtrade-v1129` and `freqtrade-v1082`.

## Authorization

User explicitly requested:

```text
v1127和v1116，都停
```

## Allowed server operation

- `docker stop freqtrade-v1127 freqtrade-v1116`

## Forbidden operations

- Do not stop `freqtrade-v1129`.
- Do not stop `freqtrade-v1082`.
- Do not remove containers.
- Do not delete SQLite files.
- Do not read `.env`.
- Do not read `user_data/monitor.env`.
- Do not print or read secrets.
- Do not modify strategy files.
- Do not modify bot configs.
- Do not modify dashboard or deploy files.
- Do not run backtests.

## Completed work

- Captured pre-stop container and resource state.
- Stopped `freqtrade-v1127`.
- Stopped `freqtrade-v1116`.
- Confirmed `freqtrade-v1129` remains running.
- Confirmed `freqtrade-v1082` remains running.
- Confirmed dashboard HTTP endpoint remains reachable with `401`.
- Generated audit report.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification and commit. Do not enter Task 21 without explicit user instruction.
