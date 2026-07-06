# TASK-0037: V11.29 Ranging-Short Candidate Matrix

## Goal

Build a read-only candidate matrix for V11.29 `v66_ranging_short_edge`
candidates and identify why they do not become final `enter_short` signals.

## Preconditions

- Task 36 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task37_v1129_ranging_short_candidate_matrix.md`
- `tasks/active/TASK-0037-v1129-ranging-short-candidate-matrix.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key, exchange credentials, server keys, dashboard password
- V10.8.2 strategy/config modifications
- V11.29 strategy/config modifications
- SQLite snapshot files
- live trading operations
- original dirty workspace

## Completed Work

- Queried V11.29 runtime `pair_candles` API read-only.
- Reconstructed `v66_ranging_short_edge` candidate counts.
- Grouped candidates by pair, 1d/7d/14d window, alpha block state, and final
  blocking reason.
- Confirmed no candidate became final `enter_short`.
- Identified `v102_short_core_prunes_ranging_non_core_short` as the dominant
  reason candidate rows do not become final short entries.
- Recommended Task 38 as an offline-only ranging-short calibration design.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 38
automatically.

