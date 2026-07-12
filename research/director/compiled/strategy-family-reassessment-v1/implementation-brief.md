# Implementation Brief: Strategy family reassessment evidence audit

Campaign: `stage4a-strategy-family-reassessment-v1`
Fingerprint: `1b3900b566df7a07313a9e9832e30c1e9a16efeade246c486b3a052b38a2b8a1`
Compile mode: `dry_run`
Execution authorized: `false`

## Objective

Does the combined BTC temporal evidence and reproducible ETH development result justify reassessing the current regime-aware strategy family before any new Candidate design?

## Machine authority

Use `campaign.yaml`, its frozen input hashes, the approved Evaluation Policy, and the approved Research Constitution as the facts. This brief is explanatory only.

## Queue

1. `build an evidence matrix for the current regime-aware family assumptions`
2. `compare retain, retire, and future-family research directions without implementing any family`
3. `produce a human-review decision packet with explicit no-execution boundaries`

## Required boundaries

- Do not run this Campaign until human approval is recorded.
- Do not create a Candidate or modify strategy/risk semantics.
- Do not access Validation, Holdout, live/server/deploy, private API, or secrets.
- Stop on any scope expansion, missing hash, closure conflict, or budget breach.

## Definition of done

- Emit every required artifact and Registry event.
- Pass targeted tests, readiness, baseline verification and integrity checks.
- Commit logically and leave the version-controlled worktree clean.
