# Research Campaign Autonomy

This repository now separates small agent tasks from bounded Research Campaigns.
A Campaign is a machine-readable contract executed by deterministic Python code,
not by model judgment.

## Pre-authorized In Campaign Scope

Within an active `mode: dry_run` Campaign, the orchestrator may:

- read the Campaign YAML;
- create and update `research/registry/research.db`;
- claim queued dry-run experiments;
- record attempts, leases, budget events, artifacts, and audit events;
- retry failures only when the configured retry and budget rules allow it;
- continue to the next queued dry-run experiment without asking the user after
  every small experiment.

Within an active `mode: fixed_backtest` Campaign, the orchestrator may run one
preconfigured Freqtrade `backtesting` command through `scripts/run_experiment.py`
only after `scripts/research_environment_doctor.py` passes. The command must use
the fixed runtime contract:

```text
<campaign-authorized-python> -m freqtrade backtesting ...
```

The runner may not search `PATH`, choose another Python, change strategies, add
command arguments, download data, run Hyperopt, run Lookahead Analysis, run
Recursive Analysis, start a server, or promote a Champion.

The model may suggest hypotheses or summarize results, but it must not decide
budget validity, state validity, stop conditions, retry eligibility, or path
authorization. Those decisions belong to the Python control plane.

## Human Escalation Required

The Campaign must stop and escalate before:

- reading `.env`, `user_data/monitor.env`, private keys, exchange credentials,
  dashboard passwords, API tokens, or any secret-like material;
- touching `deploy/**`, `configs/production/**`, `user_data/config_live.json`,
  `scripts/start_bot.sh`, or `scripts/refresh_data.sh`;
- starting, stopping, restarting, or trading with any bot;
- accessing live trading APIs or server deployment surfaces;
- changing production trading configuration;
- accessing sealed holdout data;
- lowering evaluation gates, widening scope, bypassing tests, or extending
  budget without an updated Campaign contract.

## Role Boundaries

| Role | Responsibility |
|---|---|
| Model | explain, inspect, propose code changes, summarize audit evidence |
| Orchestrator | enforce Campaign state, leases, retries, budgets, stop conditions |
| Evaluator | classify dry-run outcomes and later real experiment metrics |
| Gatekeeper | enforce path permissions and escalation rules |

## Why Small Experiments Do Not Pause

Inside a Campaign, the user has already approved a bounded queue, budget, and
stop policy. Completing one dry-run experiment is not a new decision point. The
orchestrator continues until the queue is empty, budget is exhausted, a stop
condition fires, or a risk boundary is crossed.

## Stop Conditions

The Campaign stops on:

- queue exhaustion while automatic hypothesis generation is disabled;
- `budget.max_experiments`;
- `budget.max_total_attempts`;
- `budget.max_consecutive_failures`;
- `budget.max_wall_clock_minutes`;
- blocked path access or illegal state transition.

Terminal Campaign states mean:

- `completed`: the queue was normally exhausted or the configured experiment
  target was reached with no remaining queued work;
- `stopped`: an expected stop condition such as attempt budget, wall-clock, or
  operator stop fired before all queued work completed;
- `failed`: the control plane or execution infrastructure failed
  unrecoverably;
- `escalated`: a permission, scope, secret, live-trading, or other high-risk
  boundary requires human handling.

## Failure Taxonomy

| failure_type | consumes attempt | retryable | counts candidate failures |
|---|---:|---:|---:|
| `infra_transient` | yes | yes | no |
| `infra_permanent` | yes | no | no |
| `implementation_error` | yes | no | no |
| `validation_error` | yes | no | no |
| `backtest_error` | yes | no | no |
| `output_parse_error` | yes | no | no |
| `candidate_rejected` | yes | no | yes |
| `guard_violation` | yes | no | no |
| `budget_stop` | no | no | no |
| `operator_stop` | no | no | no |

`lease_expired` is normalized to `infra_transient`. Infrastructure failures do
not increment consecutive candidate failures. Candidate metric gate failures are
`candidate_rejected`. Guard violations immediately escalate and are never
retried.

Environment reason codes such as `runtime_python_missing`,
`freqtrade_module_missing`, `freqtrade_version_mismatch`, `dataset_missing`,
`dataset_manifest_missing`, `dataset_hash_mismatch`, and
`environment_not_ready` are all classified as `infra_permanent`. They stop the
Campaign as environment failures and do not count as candidate failures.

## Runtime And Data

The fixed runtime is described by
`research/runtime/freqtrade-runtime.yaml`. The offline dataset is described by
`research/data/snapshots/<dataset_id>/manifest.yaml`. Campaigns may read these
contracts and verify hashes, but they may not install dependencies, download
market data, refresh data, or mutate the snapshot during execution.

## Non-negotiable Limits

The model must not expand Campaign permissions, budget, retry policy, data
scope, sealed holdout access, or evaluation standards. A new Campaign YAML or
human-reviewed task is required for any expansion.
