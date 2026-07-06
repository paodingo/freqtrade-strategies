# Task 34: V11.29 Pre-Filter Signal Reconstruction Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement the follow-up task step-by-step. Steps use checkbox syntax for tracking.

**Goal:** Define a safe read-only reconstruction plan that identifies which signal layer suppresses V11.29 entries before any alpha, short-core, pair universe, or strategy changes.

**Architecture:** Build a report-only reconstruction tool in a later task. It should read already-analyzed runtime dataframe columns from the Freqtrade API and, only if necessary, read non-secret strategy source logic to recompute boolean masks offline. It must not change live strategy behavior, bot config, server runtime, SQLite content, or secrets.

**Tech Stack:** PowerShell for local verification, SSH for read-only server access, Freqtrade REST API `/api/v1/pair_candles`, Node.js or Python for local report generation, Markdown/JSON evidence files.

---

## Summary

Task 33 showed that V11.29 has live runtime dataframe rows but no surviving final entries:

```text
V11.29 rows=6132
enter_long_rows=0
enter_short_rows=0
trending_short_tag_rows=0
v102_trending_short_core=0
alpha_filter_block_long=6108
alpha_filter_block_short=2040
v1129_gate_nonpass_rows=0
v1118_block_rows=0
```

The next task should not immediately tune alpha or strategy logic. It should first reconstruct the signal funnel:

```text
base raw signals
-> alpha directional filter
-> V10.2 short-core pruning
-> V10.8 pair tier / stake eligibility
-> V11.18+ quality/gate/retag layers
-> final enter_long / enter_short
```

This task only defines that plan. It does not implement the reconstruction and does not change live trading behavior.

## Key Question

The reconstruction must answer:

```text
At which layer do V11.29 candidate entries disappear?
```

More specifically:

1. Are there raw `trending_short` conditions before alpha filtering?
2. Are there raw `v66_ranging_short_edge` conditions before V10.2 short-core pruning?
3. Does alpha filtering block otherwise valid short candidates?
4. Does V10.2 short-core remove all non-core candidates by design?
5. Do later V11 gates block any already-valid short-core candidate?
6. Would stake sizing reject valid entries because stake is below `min_stake`?

## File Responsibilities For Task 35

Recommended Task 35 files:

```text
scripts/build_v1129_pre_filter_signal_reconstruction.js
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md
reports/audits/task35_v1129_pre_filter_signal_reconstruction.md
tasks/active/TASK-0035-v1129-pre-filter-signal-reconstruction.md
```

Guard note:

- These paths are likely blocked by existing V11.29/report guards.
- If needed, create a narrow guard-prep task before Task 35.
- Only exact paths should be allowed.
- Do not add broad allowlists such as:
  - `reports/v1129_execution_validation/**`
  - `reports/*v1129*`
  - `scripts/build_v1129_*`

## Required Inputs

Task 35 should read only:

1. Runtime dataframe from:

```text
http://localhost:8122/api/v1/pair_candles?pair=<pair>&timeframe=15m&limit=<n>
```

2. Sanitized alpha-risk summary from `monitor_history.sqlite`:

```text
count
min(sampled_at)
max(sampled_at)
recent risk levels
recent flag counts
```

3. Non-secret strategy source files, read-only, if mask reconstruction requires exact thresholds:

```text
/freqtrade/project/strategies/regime_aware_base.py
/freqtrade/project/strategies/RegimeAwareV66.py
/freqtrade/project/strategies/RegimeAwareV66AlphaRisk.py
/freqtrade/project/strategies/alpha_risk_filter.py
/freqtrade/project/strategies/RegimeAwareV102ReliableShortCoreAlpha.py
/freqtrade/project/strategies/RegimeAwareV108PairTieredShortCoreAlpha.py
/freqtrade/project/strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py
/freqtrade/project/strategies/RegimeAwareV1118VolatilityShockSmallShortPruner.py
/freqtrade/project/strategies/RegimeAwareV1122AdaCapitulationHalfSizer.py
/freqtrade/project/strategies/RegimeAwareV1124ReboundChaseSizer.py
/freqtrade/project/strategies/RegimeAwareV1127DualTrapMicroSizer.py
/freqtrade/project/strategies/RegimeAwareV1129ResidualDragMicroSizer.py
```

Do not read:

```text
.env
user_data/monitor.env
API keys
exchange credentials
server keys
dashboard passwords
docker inspect full output
```

## Reconstruction Layers

Task 35 should produce counts per pair and aggregate counts for these layers.

### Layer 1: Data Freshness

Inputs:

```text
date
date_4h
last_analyzed
data_start
data_stop
```

Outputs:

```json
{
  "pair": "BTC/USDT:USDT",
  "rows": 511,
  "data_stop": "2026-07-06 06:45:00+00:00",
  "last_4h_context": "2026-07-06T00:00:00Z",
  "freshness_status": "observed"
}
```

### Layer 2: Base Raw Trend/Range Conditions

Reconstruct from dataframe columns:

```text
trending_long_raw
trending_short_raw
ranging_long_raw
ranging_short_raw
```

Use the formulas from `regime_aware_base.py` and `RegimeAwareV66.py`:

```text
trending_short_raw =
  regime_4h == TRENDING
  and trend_4h_down
  and close < ema200
  and (pullback_ema_short or bb_breakout_short or rsi_exhaustion)
  and volume > 0

v66_ranging_short_raw =
  regime_4h == RANGING
  and near_upper_edge
  and enough_range
  and range_not_expanding
  and bb_percent > 0.82
  and rsi > 57
  and volume_ok
  and close < ema200 * 1.10
  and volume > 0
```

Outputs:

```json
{
  "raw": {
    "trending_long": 0,
    "trending_short": 0,
    "ranging_long": 0,
    "ranging_short": 0
  }
}
```

Use real counts; do not write assumed zeros.

### Layer 3: Alpha Filter Effects

Compute how many candidate rows would be removed by:

```text
alpha_filter_block_long
alpha_filter_block_short
```

Outputs:

```json
{
  "alpha_filter": {
    "raw_long_candidates": 0,
    "raw_short_candidates": 0,
    "blocked_long_candidates": 0,
    "blocked_short_candidates": 0,
    "surviving_long_after_alpha": 0,
    "surviving_short_after_alpha": 0
  }
}
```

If raw candidates cannot be reconstructed from available columns, mark the field as:

```json
{"state": "unknown", "reason": "missing required column ..."}
```

Do not treat missing fields as zero.

### Layer 4: V10.2 Short-Core Pruning

Use V10.2 rules:

```text
block all long entries
block all ranging tags
block all short entries not tagged trending_short
surviving short core becomes v102_trending_short_core
```

Outputs:

```json
{
  "short_core": {
    "long_blocked_by_design": 0,
    "ranging_blocked_by_design": 0,
    "non_core_short_blocked": 0,
    "v102_trending_short_core": 0
  }
}
```

### Layer 5: Pair Tier / Stake Eligibility

Use V10.8 pair-tier rules:

```text
core pairs: BTC, SOL, XRP, DOGE
watch pairs: ETH, BNB under V10.8.2
blocked pairs: none under V10.8.2
unknown/current V11.29 inherited tier must be read from source before use
```

Outputs:

```json
{
  "pair_tier": {
    "core_candidate_rows": 0,
    "watch_candidate_rows": 0,
    "blocked_pair_rows": 0,
    "stake_eligible_rows": 0,
    "stake_unknown_rows": 0
  }
}
```

Stake sizing must not read balances or secrets. If `min_stake` / `available_balance` is not available safely, mark as `unknown`.

### Layer 6: V11 Gate / Retag Effects

Count rows affected by:

```text
v1118_volatility_shock_gate
v1122_ada_capitulation_gate
v1124_rebound_sizer_gate
v1127_dual_trap_gate
v1129_residual_drag_gate
```

Outputs:

```json
{
  "v11_gates": {
    "v1118_blocked": 0,
    "v1122_retagged_or_sized": 0,
    "v1124_retagged_or_sized": 0,
    "v1127_retagged_or_sized": 0,
    "v1129_retagged_or_sized": 0,
    "final_enter_short": 0
  }
}
```

## Output Schema For Task 35

Recommended top-level JSON:

```json
{
  "metadata": {
    "strategy": "RegimeAwareV1129ResidualDragMicroSizer",
    "generated_at": "ISO timestamp",
    "mode": "read_only_pre_filter_signal_reconstruction",
    "source": "runtime_pair_candles_api",
    "can_place_orders": false,
    "reads_secret_material": false
  },
  "data_sources": [],
  "aggregate": {
    "rows": 0,
    "raw_candidates": {},
    "alpha_filter": {},
    "short_core": {},
    "pair_tier": {},
    "v11_gates": {},
    "final_entries": {}
  },
  "pairs": [],
  "root_cause_assessment": {
    "primary_layer": "unknown",
    "secondary_layers": [],
    "confidence": "low | medium | high",
    "reason": ""
  },
  "recommended_next_task": ""
}
```

## Implementation Tasks For Task 35

### Task 35.1: Guard Prep If Needed

**Files:**

- Modify only if blocked:
  - `scripts/guard_harness_diff.js`
  - `scripts/guard_trading_surface.js`
  - `docs/harness/change_surface_matrix.md`
- Create:
  - `reports/audits/task35r_v1129_pre_filter_reconstruction_guard_exception.md`
  - `tasks/active/TASK-0035R-v1129-pre-filter-reconstruction-guard-exception.md`

- [ ] Add exact path exceptions only for:

```text
scripts/build_v1129_pre_filter_signal_reconstruction.js
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json
reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md
```

- [ ] Verify these paths are still blocked:

```text
reports/v1129_execution_validation/real_execution_report.json
reports/v1129_execution_validation/snapshots/should_not_commit.sqlite
strategies/RegimeAwareV1129GuardSelfTest.py
user_data/config_multi_futures_v1129_guard_selftest.json
```

- [ ] Run:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

### Task 35.2: Build Read-Only Reconstruction Generator

**Files:**

- Create:
  - `scripts/build_v1129_pre_filter_signal_reconstruction.js`

- [ ] Implement a generator that accepts no secrets and places no orders.

Required behavior:

```text
read pair_candles API summaries through SSH or pre-supplied JSON
parse dataframe columns
compute raw/base masks if all required columns exist
compute alpha block effects
compute V10.2 short-core pruning effects
compute V11 gate counts
write JSON and Markdown reports
```

- [ ] It must fail closed if a required source is missing:

```text
missing API data -> mark source unavailable, do not invent counts
missing columns -> mark affected layer unknown
connection failure -> write blocked report, do not retry with wider permissions
```

### Task 35.3: Generate Reconstruction Report

**Files:**

- Create:
  - `reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json`
  - `reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md`
  - `reports/audits/task35_v1129_pre_filter_signal_reconstruction.md`
  - `tasks/active/TASK-0035-v1129-pre-filter-signal-reconstruction.md`

- [ ] Run:

```powershell
node --check scripts/build_v1129_pre_filter_signal_reconstruction.js
node scripts/build_v1129_pre_filter_signal_reconstruction.js
```

- [ ] Confirm the report states one of:

```text
primary_layer = raw_trending_short_absent
primary_layer = alpha_filter_short_block
primary_layer = v102_short_core_pruning
primary_layer = v11_gate_block
primary_layer = unknown
```

- [ ] Confirm the report does not state:

```text
V11.29 passed
V11.29 failed
V11.29 can replace V10.8.2
V11.29 cannot replace V10.8.2
```

### Task 35.4: Final Verification

- [ ] Run:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

- [ ] Final Git-visible files must be limited to the exact Task 35 authorization set.

## Stop Conditions

Stop immediately if:

- secret material is required;
- strategy/config changes are required;
- API access requires reading `.env` or `user_data/monitor.env`;
- live bot start/stop/restart would be needed;
- reconstruction cannot distinguish missing fields from zero counts;
- guard would require broad allowlists.

## What Task 34 Does Not Conclude

This plan does not conclude:

- V11.29 failed;
- V11.29 passed;
- V11.29 can or cannot replace V10.8.2;
- alpha filter must be changed;
- short-core conditions must be changed;
- pair universe must be changed.

It only defines how to prove the suppressing layer before any fix.

## Recommended Task 35

Recommended next task:

```text
Task 35: V11.29 Pre-Filter Signal Reconstruction
```

If guard blocks Task 35 exact paths, first run:

```text
Task 35R: Allow V11.29 Pre-Filter Reconstruction Exact Paths
```

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read or print `user_data/monitor.env`;
- print API key, exchange credentials, server keys, dashboard password, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- copy SQLite;
- modify original dirty workspace.
