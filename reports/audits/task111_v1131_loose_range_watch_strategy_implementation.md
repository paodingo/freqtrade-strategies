# Task 111: V11.31 Loose-Range Watch Strategy Implementation

## Summary

Implemented the local V11.31 loose-range watch shadow strategy, dry-run config,
and unit tests.

Conclusion:

```text
v1131_loose_range_watch_shadow_implemented_locally_not_deployed
```

This task is local-only. It does not deploy, start, stop, or restart any bot. It
does not modify current V11.30 behavior and does not claim V11.31 is profitable
or can replace V10.8.2.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `8ac9433` |
| starting status | clean |
| readiness before implementation | passed |
| guard approval | Task 110 |

## Files Created

```text
strategies/RegimeAwareV1131LooseRangeWatchShadow.py
user_data/config_multi_futures_v1131_loose_range_watch_shadow.json
tests/test_regime_aware_v1131_loose_range_watch_shadow.py
```

## Strategy Behavior

The V11.31 strategy:

- inherits from `RegimeAwareV66AlphaRisk`;
- clears inherited entries;
- emits only `v1131_loose_range_watch_long`;
- uses `15m` entries with `4h` context inherited from the parent;
- does not use stale `1h` OHLCV;
- requires allowed pairs only;
- fails closed on missing raw or alpha columns;
- blocks `takerSellPressure`;
- blocks alpha short crowding;
- uses fixed shadow stake cap `250`;
- keeps dry-run/shadow intent.

Key loose-range parameters:

| parameter | value |
|---|---:|
| `shadow_min_15m_return` | `0.004` |
| `shadow_min_15m_range` | `0.008` |
| `shadow_min_rsi` | `35` |
| `shadow_max_rsi` | `62` |
| `shadow_min_volume_ratio` | `0.8` |

## Config

The config is a dry-run futures shadow config only:

```text
user_data/config_multi_futures_v1131_loose_range_watch_shadow.json
```

It uses:

```text
dry_run = true
strategy = RegimeAwareV1131LooseRangeWatchShadow
db_url = sqlite:////freqtrade/project/user_data/tradesv3_v1131_loose_range_watch_shadow.dryrun.sqlite
```

## Validation

Required validation:

```text
python -m unittest tests/test_regime_aware_v1131_loose_range_watch_shadow.py
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Safety Boundary

This task did not:

- deploy V11.31;
- start, stop, or restart bots;
- modify current V11.30;
- modify V10.8.2;
- modify dashboard or deploy files;
- run backtests;
- refresh or download data;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- force-close trades;
- produce a replacement conclusion.

## Recommended Next Task

Proceed with:

```text
Task 112: V11.31 Offline Replay / Backtest Plan
```

Do not deploy V11.31 until offline validation and a separate server preflight
task approve it.

