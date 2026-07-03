# TASK-0020F: Deploy and Live Docs Historical Freeze Plan

## Goal

Create a plan for freezing stale deploy/live documentation as historical without directly editing `DEPLOY.md` or `LIVE_TRADING.md`.

## Preconditions

- Task 20E committed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `reports/audits/task20f_deploy_live_docs_historical_freeze_plan.md`
- `tasks/active/TASK-0020F-deploy-live-docs-historical-freeze-plan.md`

## Forbidden files and surfaces

- `DEPLOY.md`
- `LIVE_TRADING.md`
- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords
- V10.8.2 strategy/config
- V11.29 strategy/config
- live/server operation surface

## Execution boundaries

- Read `DEPLOY.md` and `LIVE_TRADING.md` only.
- Do not modify `DEPLOY.md` or `LIVE_TRADING.md`.
- Do not start, stop, or restart bots.
- Do not log in to the server.
- Do not run backtests.
- Do not modify strategies.
- Do not modify bot configs.
- Do not claim V11.29 passed real execution validation.
- Do not claim V11.29 can replace V10.8.2.

## Completed work

- Reviewed `DEPLOY.md` and identified stale V6.5 / V6.6 deploy and bot lifecycle commands.
- Reviewed `LIVE_TRADING.md` and identified stale V6.3 / V6.5 live readiness and live startup examples.
- Recommended freezing both as historical before any rewrite.
- Recommended a follow-up `Task 20G` for minimal historical marking.
- Kept the technical V11.29 data/performance audit track separate.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification and commit. Do not enter Task 20G or technical Task 20 without explicit user instruction.
