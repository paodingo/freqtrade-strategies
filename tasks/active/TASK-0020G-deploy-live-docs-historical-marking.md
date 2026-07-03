# TASK-0020G: Deploy and Live Docs Historical Marking

## Goal

Mark stale deploy/live documents as historical / not-current without rewriting them into V11.29 operational runbooks.

## Preconditions

- Task 20F committed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `DEPLOY.md`
- `LIVE_TRADING.md`
- `scripts/guard_harness_diff.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task20g_deploy_live_docs_historical_marking.md`
- `tasks/active/TASK-0020G-deploy-live-docs-historical-marking.md`

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
- live/server operation surface

## Execution boundaries

- Add warning banners only.
- Do not delete old commands.
- Do not add V11.29 deploy/live/start/stop/restart instructions.
- Do not log in to the server.
- Do not start, stop, or restart bots.
- Do not run backtests.
- Do not modify strategies.
- Do not modify bot configs.
- Do not claim V11.29 passed real execution validation.
- Do not claim V11.29 can replace V10.8.2.

## Completed work

- Added historical warning to `DEPLOY.md`.
- Added historical warning to `LIVE_TRADING.md`.
- Added exact root document guard allowance for `DEPLOY.md` and `LIVE_TRADING.md`.
- Updated the harness change surface matrix.

## Verification commands

```powershell
node --check scripts/guard_harness_diff.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification and commit. Do not enter technical Task 20 without explicit user instruction.
