# Harness Change Surface Matrix

This matrix is the default static boundary for agent work in the harness
worktree. It is intentionally narrow so routine agent tasks cannot accidentally
touch trading behavior, production-like bot wiring, secrets, or server
operations.

| Surface | Default | Reason | Guard |
| --- | --- | --- | --- |
| `scripts/guard_*.js` | Allowed | Static guard implementation | `guard_harness_diff.js` |
| `scripts/run_agent_readiness_checks.sh` | Allowed | Linux/Git Bash static guard runner | `guard_harness_diff.js` |
| `scripts/run_agent_readiness_checks.ps1` | Allowed | Windows PowerShell static guard runner | `guard_harness_diff.js` |
| `.github/workflows/*.yml` and `.github/workflows/*.yaml` | Allowed | Static-only CI wiring | `guard_harness_diff.js` |
| `.gitignore` | Allowed | Generated/cache/data exclusion rules | `guard_harness_diff.js` |
| `AGENTS.md` and `README.md` | Allowed | Agent/user-facing repo guidance | `guard_harness_diff.js` |
| `tasks/**/*.md` | Allowed | Agent task briefs and records | `guard_harness_diff.js` |
| `docs/harness/**` | Allowed | Human-readable harness boundary docs | `guard_harness_diff.js` |
| `docs/harness/v1129_execution_report_schema.md` | Allowed by exact path only | Task 13 harness schema doc; this is not a V11.29 strategy, config, report evidence, or runtime surface | `guard_trading_surface.js` |
| `scripts/build_v1129_execution_empty_report.js` | Allowed by exact path only | Task 14 empty/insufficient sample report generator; does not read real trade DB, secrets, or live/server state | `guard_harness_diff.js` |
| Task 14 empty report samples | Allowed by exact path only | Only `reports/v1129_execution_validation/sample_empty_report.json` and `reports/v1129_execution_validation/sample_empty_report.md`; no `reports/v1129_execution_validation/**` or real execution report evidence | `guard_harness_diff.js`, `guard_trading_surface.js` |
| `scripts/build_v1129_snapshot_insufficient_report.js` | Allowed by exact path only | Task 18 snapshot-based insufficient report generator; allowed as harness reporting code only, not a bot, strategy, config, SQLite, dashboard, server, or live surface | `guard_harness_diff.js` |
| Task 18 snapshot insufficient report outputs | Allowed by exact path only | Only `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json` and `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md`; no `reports/v1129_execution_validation/**`, no SQLite snapshots, and no real execution report wildcard | `guard_harness_diff.js`, `guard_trading_surface.js` |
| Task 7S approved `docs/*` files | Allowed by exact path only | Narrow A-class docs migration allowlist; does not allow `docs/**`, `docs/*.md`, or `docs/*.html` | `guard_harness_diff.js` |
| `reports/audits/**/*.md` | Allowed | Audit plans and evidence records | `guard_harness_diff.js` |
| `strategies/**` | Blocked | Strategy behavior must not change by default | `guard_trading_surface.js` |
| `user_data/**` | Blocked | Bot configs and runtime state must not change by default | `guard_trading_surface.js` |
| `configs/**` | Blocked | Bot and experiment config must not change by default | `guard_trading_surface.js` |
| `dashboard/**` | Blocked | Dashboard runtime/UI changes can misrepresent live state | `guard_trading_surface.js` |
| bot lifecycle scripts | Blocked | Agent tasks must not start, stop, or restart bots | `guard_trading_surface.js` |
| `deploy/**` | Blocked | Deployment must be an explicit server task | `guard_trading_surface.js` |
| `reports/reliable_strategy_search_v1129/**` | Blocked | V11.29 evidence must not be rewritten by default | `guard_trading_surface.js` |
| V10.8.2/V11.29 versioned paths | Blocked | Protected reference surfaces | `guard_trading_surface.js` |
| `.env`, `user_data/monitor.env`, key files | Blocked | Secret material must not be read or committed | `guard_no_secret_material.js` |

The harness diff guard is task-aware by path class, not by a one-task file
allowlist. Low-risk documentation/harness surfaces can pass while real trading,
bot, server, dashboard, deployment, and secret paths remain blocked. Trading
surface checks use changed file paths instead of scanning documentation text, so
audit documents can mention terms such as `user_data`, `stoploss`, `leverage`,
or `pairlist` without being treated as trading parameter changes.

Task 7S adds a narrow A-class docs migration allowlist for exactly these files:
`docs/agent_operating_playbook.md`, `docs/agent_operating_playbook.html`,
`docs/opensource_reference_audit.md`, and `docs/验收报告格式.md`. This is not a
general `docs/**`, `docs/*.md`, or `docs/*.html` allowance.

CI is static-only. It runs syntax checks and the guard scripts without Docker,
server access, bot lifecycle commands, or secret-dependent inputs. Windows local
checks should prefer `scripts/run_agent_readiness_checks.ps1` to avoid WSL or
Git Bash dependency; Linux, Git Bash, and Linux CI can keep using
`scripts/run_agent_readiness_checks.sh`.
