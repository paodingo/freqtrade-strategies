# TASK-0028: V11.29 Zero-Trade Signal Audit

## Goal

Read-only audit why V11.29 remains `trades=0/orders=0` after entering `RUNNING`, without modifying strategy behavior or bot configuration.

## Preconditions

- Task 27 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.
- Server access allowed for read-only investigation.

## Allowed Changes

- `reports/audits/task28_v1129_zero_trade_signal_audit.md`
- `tasks/active/TASK-0028-v1129-zero-trade-signal-audit.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**` bot configs
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key, exchange credentials, server keys, dashboard password
- V10.8.2 strategy/config
- V11.29 strategy/config
- live trading operations

## Completed Work

- Checked current V11.29 and V10.8.2 runtime truth.
- Checked V11.29 API endpoints: `ping`, `show_config`, `count`, `profit`, `status`, `locks`, `whitelist`.
- Checked V11.29 and V10.8.2 SQLite counts read-only.
- Checked V11.29 logs since current `RUNNING` transition.
- Checked local futures data file coverage and latest candle timestamps.
- Read V11.29 strategy inheritance and gate/retag layers from existing strategy files.
- Documented what is ruled out and what remains unknown.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 29 automatically.
