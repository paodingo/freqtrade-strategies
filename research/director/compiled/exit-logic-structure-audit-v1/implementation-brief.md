# Implementation Brief: Exit logic structure and attribution audit

Campaign: `stage4a-exit-logic-structure-audit-v1`
Fingerprint: `a4c3b5d8d072963441d2dce1e989d71822062d65a58f610cac40145a79a9f3ae`
Compile mode: `dry_run`
Execution authorized: `false`

## Objective

Which existing exit mechanisms explain regime-specific loss concentration without changing strategy or risk semantics?

## Machine authority

Use `campaign.yaml`, its frozen input hashes, the approved Evaluation Policy, and the pending-review Constitution as the facts. This brief is explanatory only.

## Queue

1. `map existing exit reasons to temporal regimes`
2. `audit first-trigger and time-stop semantics`
3. `produce structural findings only`

## Required boundaries

- Do not run this Campaign until human approval is recorded.
- Do not create a Candidate or modify strategy/risk semantics.
- Do not access Validation, Holdout, live/server/deploy, private API, or secrets.
- Stop on any scope expansion, missing hash, closure conflict, or budget breach.

## Definition of done

- Emit every required artifact and Registry event.
- Pass targeted tests, readiness, baseline verification and integrity checks.
- Commit logically and leave the version-controlled worktree clean.
