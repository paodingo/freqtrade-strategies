# TASK-0193 Runtime Remediation Baseline

Captured at `2026-07-22T08:33:05Z` from read-only server evidence.

## Runtime identity

- Current immutable release: `1db987fe2babb879a1abbf7c7861fe2d1eff4284`.
- V11.29 and V11.30 were both running from that release with zero container restarts.
- The server worktree is not runtime authority and contains extensive historical uncommitted material.
- The V11.30 config hash matched the deployed release manifest.
- Pre-change online SQLite backups and runtime identity evidence were written to `/home/ubuntu/freqtrade-runtime/rollback/paper-lane-20260722T084442Z`; both database backups passed `PRAGMA integrity_check` and have recorded SHA256 hashes.

## Trailing 24-hour evidence

- Reliability samples: `260`.
- Decision-allowed samples: `258`.
- Blocked samples: `2`.
- Maximum observed candle age: `919` seconds.
- Immutable deployment identities observed: only `1db987fe2bab`.
- V11.30 market reload failures: `13` distinct `Could not load markets` events.
- V11.30 strategy analysis overruns: `1`.
- V11.29 market reload failures: `14` distinct events.

## Decision

The existing data-reliability report was too optimistic because it did not inspect container state or bounded runtime logs. TASK-0193 must remain open until the corrected controller records a clean 24-hour window after deployment.
