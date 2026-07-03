# Agent Operating Playbook

Last updated: 2026-07-01

This playbook expands `AGENTS.md` into repeatable procedures. Use it when an AI
agent needs to modify strategy code, deploy to the server, update the dashboard,
or triage live alerts.

## System Map

| Component | Authority | Notes |
| --- | --- | --- |
| Server repo | `/home/ubuntu/freqtrade-strategies` on `43.134.72.69` | source of truth for live dry-run state |
| Local repo | `D:/code/freqtrade-strategies` | development copy |
| Dashboard | `freqtrade-monitor.service` on port `8090` | should show V11 current vs V10.8.2 benchmark |
| Current bot | `freqtrade-v1116` on port `8109` | V11.16 high-attack density candidate |
| Benchmark bot | `freqtrade-v1082` on port `8091` | V10.8.2 historical profitable baseline |
| Legacy Phase2 | `freqtrade-phase2` | archived/stopped, not primary web display |

Core wiring files:

- `dashboard/lib/config.js`
- `dashboard/public/index.html`
- `dashboard/public/app.js`
- `dashboard/server.js`
- `scripts/check_system_health.sh`
- `scripts/refresh_data.sh`
- `scripts/ensure_dry_run_bots_started.sh`
- `scripts/check_trades.sh`
- `tests/test_dashboard_phase2_summary.js`
- `tests/test_start_bot_static.js`

## Strategy Iteration Protocol

Use this sequence for any V11/V12 strategy candidate:

1. Define the bottleneck being addressed: trade count, PF, drawdown, cost,
   negative pair contribution, or concentration risk.
2. Create a new candidate version instead of weakening the online benchmark.
3. Give the candidate an isolated strategy class, config, database, port, and
   report directory.
4. Add tests for wiring and any deterministic strategy helpers.
5. Backtest 30d and 70d against V10.8.2.
6. Include rolling 14d windows and cost stress where the relevant scripts
   support it.
7. Report net profit, trade count, win rate, PF, max drawdown, max consecutive
   losses, max single-trade contribution, pair contribution, strategy-arm
   contribution, fees, slippage, and funding.
8. If the candidate fails, keep the report and state the bottleneck. Do not
   hide failed evidence.

Research candidates must not replace the dry-run bot until the user explicitly
approves promotion.

## Dashboard Update Protocol

When the main bot or benchmark changes:

1. Update `dashboard/lib/config.js`.
2. Update any scripts that infer default bot lanes:
   `scripts/refresh_data.sh`, `scripts/ensure_dry_run_bots_started.sh`,
   `scripts/check_trades.sh`, and `scripts/check_system_health.sh`.
3. Update dashboard public text and remove stale primary-lane wording.
4. Update tests so they lock the intended lanes and reject stale labels.
5. Run local checks:

```powershell
node --check dashboard/public/app.js
node --check dashboard/lib/config.js
node --check dashboard/server.js
node --test tests/test_dashboard_phase2_summary.js tests/test_start_bot_static.js
```

6. Deploy changed files to the server if the web UI is meant to change there.
7. Restart `freqtrade-monitor.service`.
8. Verify server tests, health check, and authenticated `/api/summary`.

The dashboard should answer these questions first:

- Which bot is current?
- Which bot is the benchmark?
- Are both running?
- What happened recently?
- Which pairs and strategy arms are helping or hurting?
- Is replacement of the benchmark allowed by the current evidence?

## Server Deployment Checklist

Use exact changed files. Avoid broad syncs unless the user asked for it.

```powershell
scp -i D:/key/openclaw/clf.pem <file> ubuntu@43.134.72.69:/tmp/
```

Then on the server:

```bash
cd /home/ubuntu/freqtrade-strategies
# copy files from /tmp into their repo paths
node --check dashboard/public/app.js
node --check dashboard/lib/config.js
node --check dashboard/server.js
node --test tests/test_dashboard_phase2_summary.js tests/test_start_bot_static.js
sudo systemctl restart freqtrade-monitor.service
./scripts/check_system_health.sh
```

If authenticated dashboard checks are needed, derive credentials from the
server process environment for that local curl only. Do not print secrets in
chat, docs, reports, or commits.

## Alert Triage Checklist

When Telegram or logs mention API exceptions, stopped state, or `jq: parse
error`, check in this order:

1. Is the alert script itself producing invalid JSON or malformed text?
2. Is `freqtrade-monitor.service` running and returning non-500 responses?
3. Is the target bot container running?
4. Does `/api/v1/show_config` report `state=running`?
5. Does `/api/v1/status` show open trades, closed trades, or API errors?
6. Are pairlocks preventing entries?
7. Is the strategy intentionally flat because filters blocked entries?

Do not collapse these into "the bot is dead" without evidence.

## Data Rules

- Binance futures market data is the external market source.
- Freqtrade bot state and dry-run trades come from the server bot APIs.
- OI is optional. Missing OI is neutral.
- Historical OI gaps must be reported, not invented.
- Backtest windows must state their exact date range and available coverage.
- Do not use future data, forward fills, or post-hoc pair selection inside a
  historical decision path.

## Skills And AI Stability

The general skill set is sufficient, but only if agents follow a stable routing
policy:

| Situation | Skill or fallback |
| --- | --- |
| Behavior or strategy-code change | test-driven-development |
| Bug, alert, API error, unexpected failure | systematic-debugging |
| Large architecture or phase redesign | writing-plans |
| Dashboard UI verification | frontend-testing-debugging |
| Before saying work is complete | verification-before-completion |
| Skill unavailable | follow the equivalent checklist in this playbook |

The missing piece is not more creativity. It is a project-specific operating
contract. `AGENTS.md` is that contract; this playbook is the procedure library.

## Final Response Template

Keep final answers short, but include evidence:

```text
已完成：...
验证：...
服务器状态：...
剩余风险：...
```

If no server work was done, say that server state was not touched.
