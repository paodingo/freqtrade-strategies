# Implementation Brief: Regime branch structure audit

Campaign: `stage4a-regime-branch-structure-audit-v1`
Fingerprint: `2af657d1abe2f369ed6df92a0c442fe90c49058ef32593d51106b3f1e97456b1`
Compile mode: `dry_run`
Execution authorized: `false`

## Objective

Are directionality and regime activation imbalances structural rather than addressable by another threshold search?

## Machine authority

Use `campaign.yaml`, its frozen input hashes, the approved Evaluation Policy, and the pending-review Constitution as the facts. This brief is explanatory only.

## Queue

1. `compare branch activation by regime`
2. `separate structural gaps from threshold-local effects`
3. `emit no-mutation recommendation`

## Required boundaries

- Do not run this Campaign until human approval is recorded.
- Do not create a Candidate or modify strategy/risk semantics.
- Do not access Validation, Holdout, live/server/deploy, private API, or secrets.
- Stop on any scope expansion, missing hash, closure conflict, or budget breach.

## Definition of done

- Emit every required artifact and Registry event.
- Pass targeted tests, readiness, baseline verification and integrity checks.
- Commit logically and leave the version-controlled worktree clean.
