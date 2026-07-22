# TASK-0193 Paper Lane Runtime Remediation

Status: In progress

## Goal

Make the V11.30 dry-run lane immutable, observable, and eligible for a 24-hour reliability acceptance window.

## Changes

- Load the V11.30 config from the immutable release rather than the mutable server worktree.
- Retire the V11.29 container after a read-only SQLite backup.
- Reduce Binance market metadata reload frequency and use explicit bounded CCXT timeouts.
- Extend the reliability controller to inspect the actual V11.30 container and bounded runtime logs.
- Repair the date-dependent reliability tests that failed on 2026-07-22.

## Closure gate

- deployed release and runtime config hashes match;
- V11.30 is running with zero restarts;
- V11.29 is absent from the active container set;
- the reliability timer is active;
- at least 24 hours of samples meet the acceptance contract in `docs/paper_lane_recovery.md`.

Live trading and real-money operations remain out of scope.
