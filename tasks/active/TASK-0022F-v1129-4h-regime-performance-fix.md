# TASK-0022F: V11.29 4h Regime Performance Fix

## Goal

Implement the minimal bounded 4h lookback fix recommended by Task 22R.

## Preconditions

- Task 22R committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks passed before edits.
- User explicitly authorized entering the strategy-code implementation step.

## Allowed files

- `strategies/regime_aware_base.py`
- `reports/audits/task22f_v1129_4h_regime_performance_fix.md`
- `tasks/active/TASK-0022F-v1129-4h-regime-performance-fix.md`

## Forbidden files and surfaces

- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords
- server write operations
- bot start / stop / restart
- backtests
- V11.29 replacement conclusion

## Completed work

- Added `_bounded_informative_4h()` to `RegimeAwareBaseMixin`.
- Limited 4h informative input to `max(startup_candle_count + 300, 600)` rows before indicator and regime calculation.
- Left entry/exit/stake/config/server behavior unchanged.
- Did not modify guard rules.

## Verification commands

```powershell
python -m py_compile strategies/regime_aware_base.py
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Stop condition

Stop after verification, commit, and push. Do not deploy to server and do not enter Task 22V without separate authorization.

