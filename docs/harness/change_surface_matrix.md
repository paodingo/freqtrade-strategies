# Harness Change Surface Matrix

This matrix is the default static boundary for agent work in the harness
worktree. It is intentionally narrow so routine agent tasks cannot accidentally
touch trading behavior, production-like bot wiring, secrets, or server
operations.

| Surface | Default | Reason | Guard |
| --- | --- | --- | --- |
| `scripts/guard_harness_diff.js` | Allowed | Task 1 guard implementation | `guard_harness_diff.js` |
| `scripts/guard_no_secret_material.js` | Allowed | Task 1 guard implementation | `guard_harness_diff.js` |
| `scripts/guard_trading_surface.js` | Allowed | Task 1 guard implementation | `guard_harness_diff.js` |
| `scripts/run_agent_readiness_checks.sh` | Allowed | Static guard runner | `guard_harness_diff.js` |
| `.github/workflows/agent-readiness.yml` | Allowed | Static-only CI wiring | `guard_harness_diff.js` |
| `tasks/**` | Allowed only for the listed Task 1 files | Agent task briefs and templates | `guard_harness_diff.js` |
| `docs/harness/change_surface_matrix.md` | Allowed | Human-readable boundary map | `guard_harness_diff.js` |
| `strategies/**` | Blocked | Strategy behavior must not change by default | `guard_trading_surface.js` |
| `user_data/**` | Blocked | Bot configs and runtime state must not change by default | `guard_trading_surface.js` |
| `dashboard/lib/config.js` | Blocked | Runtime config can change live monitor behavior | `guard_trading_surface.js` |
| `dashboard/server.js` | Blocked | Server endpoints can change operational truth | `guard_trading_surface.js` |
| `dashboard/public/**` | Blocked | UI can misrepresent live state | `guard_trading_surface.js` |
| bot lifecycle scripts | Blocked | Agent tasks must not start, stop, or restart bots | `guard_trading_surface.js` |
| `deploy/**` | Blocked | Deployment must be an explicit server task | `guard_trading_surface.js` |
| `reports/reliable_strategy_search_v1129/**` | Blocked | V11.29 evidence must not be rewritten by default | `guard_trading_surface.js` |
| V10.8.2/V11.29 versioned paths | Blocked | Protected reference surfaces | `guard_trading_surface.js` |
| `.env`, `user_data/monitor.env`, key files | Blocked | Secret material must not be read or committed | `guard_no_secret_material.js` |

CI is static-only. It runs syntax checks and the guard scripts without Docker,
server access, bot lifecycle commands, or secret-dependent inputs.
