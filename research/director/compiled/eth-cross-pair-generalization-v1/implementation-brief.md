# Implementation Brief: ETH development-only cross-pair generalization

Campaign: `stage4a-eth-cross-pair-generalization-v1`
Fingerprint: `12338df116617891e268d88bebff193adecb80847a8070615eb37a0f6b6bdc3b`
Compile mode: `dry_run`
Execution authorized: `false`

## Objective

Does the frozen RegimeAwareV6 baseline retain reproducible signal and trade behavior on ETH/USDT:USDT 1h over the same development boundary as BTC?

## Machine authority

Use `campaign.yaml`, its frozen input hashes, the approved Evaluation Policy, and the pending-review Constitution as the facts. This brief is explanatory only.

## Queue

1. `seal ETH public OHLCV, mark and funding data to the BTC development boundary`
2. `run the unchanged RegimeAwareV6 baseline twice in distinct fresh processes`
3. `compare deterministic ETH results with existing BTC development evidence without applying promotion gates`

## Required boundaries

- Do not run this Campaign until human approval is recorded.
- Do not create a Candidate or modify strategy/risk semantics.
- Do not access Validation, Holdout, live/server/deploy, private API, or secrets.
- Stop on any scope expansion, missing hash, closure conflict, or budget breach.

## Definition of done

- Emit every required artifact and Registry event.
- Pass targeted tests, readiness, baseline verification and integrity checks.
- Commit logically and leave the version-controlled worktree clean.
