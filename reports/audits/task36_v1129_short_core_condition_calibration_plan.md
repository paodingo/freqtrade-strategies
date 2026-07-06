# Task 36: V11.29 Short-Core Condition Calibration Plan

## Summary

This task converts the Task 35 pre-filter reconstruction evidence into a
calibration plan. It does not modify strategy code, bot configuration, server
state, SQLite snapshots, or live trading operations.

Current conclusion from Task 35:

- V11.29 runtime data is fresh enough for signal inspection.
- V11.29 snapshot-based execution validation remains `insufficient` because
  trades and orders are still zero.
- The reconstructed signal funnel found raw ranging-short candidates, but no
  raw trending-short candidates.
- Some ranging-short candidates survived alpha filtering, but V10.2 short-core
  semantics intentionally pruned ranging and non-core shorts before V11.29
  retagging/sizing could act.
- The current primary suppressing layer is therefore `v102_short_core_pruning`,
  not missing runtime candles, not V11.29 late-stage gating, and not a proven
  exchange/API execution failure.

This is not a replacement verdict. It does not prove V11.29 is good or bad.

## Evidence Baseline

Task 35 observed:

| Metric | Count |
| --- | ---: |
| rows reconstructed | 6156 |
| raw trending long candidates | 1152 |
| raw trending short candidates | 0 |
| raw ranging long candidates | 17 |
| raw ranging short candidates | 111 |
| alpha blocked short candidates | 26 |
| surviving short after alpha | 85 |
| V10.2 ranging blocked by design | 85 |
| V10.2 short-core candidates | 0 |
| V11.29 retagged/sized | 0 |
| final enter_short | 0 |

Observed tags were metadata only:

- `trending_long`
- `v66_ranging_short_edge`
- `v66_ranging_long_edge`

Final execution still requires `enter_long == 1` or `enter_short == 1`.

## Calibration Question

The key question is not whether V11.29 should immediately trade. The key
question is whether the inherited V10.2 short-core requirement is intentionally
strict enough, or whether V11.29 needs a separately validated research lane for
non-core short candidates.

Calibration must be evidence-first:

1. Identify which blocked candidate family is worth studying.
2. Measure its historical and dry-run behavior without changing live V11.29.
3. Define explicit pass/fail gates before any live configuration or strategy
   change is considered.

## Candidate Calibration Paths

| Candidate | Description | Initial Action | Risk |
| --- | --- | --- | --- |
| Keep V10.2 short-core strict | Treat zero short-core candidates as expected behavior and continue observation. | Continue telemetry and wait for raw trending-short candidates. | Low operational risk, but may leave V11.29 inactive for long periods. |
| Ranging-short research lane | Study `v66_ranging_short_edge` candidates separately from the production short-core path. | Build offline candidate matrix from existing runtime data and historical data. | Medium research risk; must not become live trading without new approval. |
| Relax short-core conditions | Test whether broader short definitions would have created valid entries. | Offline-only simulation or backtest in a later authorized task. | High model risk; must not be applied directly to live V11.29. |
| Alpha long-side calibration | Investigate why long candidates are broadly blocked by alpha. | Separate long-side audit task if needed. | Medium; not the primary zero-short cause in Task 35. |
| Pair-specific calibration | Review whether only certain pairs produce useful candidate density. | Summarize candidates by pair and market regime. | Low if read-only; can reduce later blast radius. |

## Proposed Validation Gates

No strategy or bot configuration change should proceed until these gates are
answered in order:

1. Candidate identity gate:
   - Which exact candidate family is being evaluated?
   - Is it `v66_ranging_short_edge`, relaxed trending short, alpha-unblocked
     long, or another explicitly named family?

2. Data sufficiency gate:
   - How many candidates exist over 1d, 7d, and 14d?
   - Are candidates concentrated in one pair, one market regime, or one short
     time window?

3. Historical behavior gate:
   - Does the candidate family have historical evidence beyond the current
     runtime window?
   - If backtesting is proposed, it must be a separate authorized task.

4. Execution quality gate:
   - If dry-run evidence is later collected, does it include trades, orders,
     fees, fills, and timestamps?
   - If orders are absent, no execution-quality claim is allowed.

5. Safety boundary gate:
   - Any live experiment must use explicit strategy/config allowlists, separate
     task authorization, and a rollback/stop condition.
   - No broad guard bypass, no secret access, and no dashboard/server mutation
     should be bundled into calibration.

## Recommended Task 37

Recommended next task:

```text
Task 37: V11.29 Ranging-Short Candidate Matrix
```

Suggested scope:

- Read-only build a matrix of `v66_ranging_short_edge` candidates from current
  V11.29 runtime data.
- Group by pair, timestamp, regime fields, alpha block state, and the exact
  reason each candidate failed to become `enter_short`.
- Do not modify strategy, bot config, dashboard, deploy, server state, or
  SQLite.
- Do not run backtests unless a later task explicitly authorizes it.

Task 37 should produce evidence that answers whether the ranging-short research
lane is worth a later offline calibration task.

## Boundaries

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- log into the server;
- modify the original dirty workspace.

## Verification

Required completion checks:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

