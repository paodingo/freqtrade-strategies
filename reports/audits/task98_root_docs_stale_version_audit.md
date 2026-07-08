# Task 98: Root Docs Stale Version Audit

## Summary

Audited root documentation for stale version narratives.

Conclusion:

```text
root_docs_needed_v1130_currentization
```

## Files Reviewed

- `README.md`
- `DEPLOY.md`
- `LIVE_TRADING.md`
- `STRATEGY_GUIDE.md`
- selected `docs/**/*.md` scan results

## Findings

| file | finding | action |
|---|---|---|
| `README.md` | V11.29 still described as current validation object | update to V11.30 current observation candidate |
| `STRATEGY_GUIDE.md` | V11.29 still described as current validation object | update current validation language to V11.30 |
| `DEPLOY.md` | warning existed, but body still said current V6.5/V6.6 deployment | clarify body is historical, not current authority |
| `LIVE_TRADING.md` | warning existed, but body still implied V6.x live readiness direction | clarify body is historical template only |
| `docs/agent_operating_playbook.md` | still references older V11.16/V10.8.2 dashboard roles | defer to a later playbook-specific update |
| `docs/backtests/**` | historical V6.x backtest docs | keep as historical evidence |

## Exclusions

This task did not modify:

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- secrets
- live/server state

## Recommended Task 99

Proceed with root docs version narrative update.
