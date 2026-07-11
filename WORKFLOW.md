# Research Campaign Workflow

The control plane uses SQLite as the only scheduling state source:

```text
research/registry/research.db
```

JSONL audit output may exist for review, but it is not the state database.

## Outer Loop

1. Load and validate `research/campaigns/active/*.yaml`.
2. Initialize or migrate `research/registry/research.db`.
3. Reclaim expired leases.
4. Check Campaign budget and stop conditions.
5. For `fixed_backtest`, run the environment doctor before claiming work.
6. Atomically claim the next queued experiment.
7. Execute the selected runner: `dry_run` or the fixed `backtesting` runner.
8. Record attempt, artifact, budget, and audit rows.
9. Retry or terminate according to deterministic rules.
10. Continue while `autonomy.automatically_claim_next` is true.
11. Write a final report when the Campaign completes, stops, fails, or escalates.

## Inner Loop

This phase is dry-run only. A claimed experiment moves through:

```text
queued -> claimed -> preparing -> running -> validating -> recorded -> accepted
queued -> claimed -> preparing -> running -> failed
queued -> claimed -> escalated
```

Rejected dry-run outcomes are available for future evaluators but the demo
runner currently accepts successful simulations, fails simulated failures, and
escalates path violations.

## Experiment State Machine

Allowed states:

```text
queued -> claimed -> preparing -> running -> validating -> recorded -> accepted | rejected | escalated | failed
failed -> queued
```

The only retry transition is `failed -> queued`, and only when:

- the failure type is retryable;
- the experiment has retries remaining;
- the Campaign total attempt budget is not exhausted.

Illegal transitions fail and are written to `audit_events`.

## Campaign State Machine

Allowed states:

```text
draft -> active -> pausing -> paused -> completed | stopped | failed | escalated
paused -> active
```

`completed` means the target was reached or the queue was normally exhausted.
`stopped` means an expected limit fired before all queued work completed, for
example `max_total_attempts` with remaining queued experiments. A blocked path
reaches `escalated`.

## Lease And Recovery

Each claim writes `lease_owner` and `lease_expires_at`. If a process crashes
after claiming, a later `--resume` run reclaims expired leases and requeues the
experiment when retry policy allows it. This prevents two owners from owning the
same queued experiment and gives crash recovery an explicit audit trail.

## Deduplication

`hypotheses` and `experiments` enforce `UNIQUE(campaign_id, fingerprint)`.
Duplicate fingerprints are rejected during seeding or ingestion and recorded in
`audit_events`.

## Budget

Budget is charged through `budget_events` with idempotency keys. A repeated
orchestrator run does not recharge a completed attempt. Campaign-level stop
checks use SQLite counts, not model memory.

## Path Guard

`scripts/research_guard.py` normalizes paths against the repository root,
rejects `../` escapes and symlink escapes, applies permanent blocks, then
checks Campaign allow rules. `blocked_paths` always wins over `allowed_paths`.

## Fixed Backtest Runner

`scripts/run_experiment.py` implements the first real execution hook. It accepts
only a Campaign-defined `fixed_backtest` spec, builds an argument array, and
runs it with `shell=False`.

The command shape is:

- executable: the Campaign-authorized Python executable from
  `research/runtime/freqtrade-runtime.yaml`;
- invocation: `python -m freqtrade`;
- subcommand: `backtesting`;
- forbidden command words: `trade`, `hyperopt`, `lookahead-analysis`,
  `recursive-analysis`, `download-data`, and `webserver`.

The runner must not search `PATH`, auto-select another Python, create a fake
Freqtrade module, install dependencies, or download data.

Each experiment writes an isolated result directory:

```text
research/results/<campaign_id>/<experiment_id>/
```

Required artifacts include `command.json`, `manifest.yaml`, `stdout.log`,
`stderr.log`, the raw Freqtrade result JSON or extracted JSON, `metrics.json`,
`runner-report.json`, and `artifact-hashes.json`. SQLite stores only summaries
and artifact paths.

The runner classifies nonzero Freqtrade exits as `backtest_error`, incompatible
or missing output as `output_parse_error`, timeouts as `infra_transient`, and
metric-gate failures as `candidate_rejected`. It never decides Champion
promotion.

## Environment Doctor

`scripts/research_environment_doctor.py` is read-only. It checks the runtime
contract, Python executable, Freqtrade module and version, dependency lock hash,
strategy/config existence, offline dataset manifest and file hashes, pair,
timeframe, timerange coverage, output writability, guard effectiveness, disabled
network policy, and `fixed_backtest` runner type.

Environment failures are stable reason codes:

- `runtime_python_missing`
- `freqtrade_module_missing`
- `freqtrade_version_mismatch`
- `dataset_missing`
- `dataset_manifest_missing`
- `dataset_hash_mismatch`
- `environment_not_ready`

They map to `infra_permanent`, do not increment candidate failure counters, and
do not retry until the operator fixes the runtime or dataset.

## Offline Data Snapshot

Fixed backtests use `research/data/snapshots/<dataset_id>/manifest.yaml`, not
mutable `user_data/data`. The manifest records dataset ID, exchange, trading
mode, timerange, timeframes, pairs, data path, file paths, byte sizes, SHA-256,
source, creation time, mutability, and whether network was accessed during the
Campaign.

## Next Real-Strategy Hook

The next phase may create a single candidate strategy copy inside a
Campaign-allowed research path, then point `fixed_backtest.strategy_file` at that
copy. The same state machine, guard, lease, budget, and artifact rules remain in
force.
