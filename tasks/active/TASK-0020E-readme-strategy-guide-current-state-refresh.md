# TASK-0020E: README and Strategy Guide Current-State Refresh

## Goal

Refresh low-risk entry documentation so it no longer presents V6.5 / V6.6 as the current active strategy line, while preserving V11.29 as an insufficient real-execution validation target.

## Preconditions

- Task 20D committed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed files

- `README.md`
- `STRATEGY_GUIDE.md`
- `scripts/guard_harness_diff.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task20e_readme_strategy_guide_current_state_refresh.md`
- `tasks/active/TASK-0020E-readme-strategy-guide-current-state-refresh.md`

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

- Do not start, stop, or restart bots.
- Do not log in to the server.
- Do not run backtests.
- Do not modify strategies.
- Do not modify bot configs.
- Do not claim V11.29 passed real execution validation.
- Do not claim V11.29 can replace V10.8.2.

## Completed work

- Updated `README.md` current-state narrative.
- Updated `STRATEGY_GUIDE.md` current-state narrative.
- Added exact harness guard allowance for root `STRATEGY_GUIDE.md`.
- Preserved V6.5 / V6.6 as historical strategy context.
- Explicitly marked V11.29 as `insufficient`.
- Left `DEPLOY.md` and `LIVE_TRADING.md` untouched for a separate high-risk docs task.

## Verification commands

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification. Do not enter Task 20F or the technical Task 20 without explicit user instruction.
