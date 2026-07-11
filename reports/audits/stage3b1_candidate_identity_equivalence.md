# Stage 3B.1 Candidate Identity Equivalence

Date: 2026-07-10

## Verdict

Stage 3B.1 is complete for the fixed `RegimeAwareV6` futures acceptance
fixture.

The run proved the isolated candidate lifecycle:

`official baseline strategy -> isolated candidate copy -> Freqtrade load -> sealed offline backtest -> baseline/candidate comparison -> SQLite registry record`

without modifying the official strategy.

## Fixed Inputs

- Campaign: `research/campaigns/active/demo-stage3b1-candidate-identity.yaml`
- Experiment: `1`
- Base strategy: `strategies/RegimeAwareV6.py`
- Base strategy SHA256: `1A422F41AB801746C2EE39F5D20722B26B674098BCA6AC1684E78BD8E7285509`
- Candidate class: `RegimeAware_C3B1_E0001`
- Candidate path: `research/candidates/demo-stage3b1-candidate-identity/1/RegimeAware_C3B1_E0001.py`
- Manifest: `research/candidates/demo-stage3b1-candidate-identity/1/candidate-manifest.yaml`
- Dataset snapshot: `demo-btc-usdt-usdt-futures-acceptance-20260329-20260412`
- Dataset aggregate SHA256: `b556d7db23144614225b732a22c5e91bcc0efb2dd170e112d555ae7f70279736`
- Exchange snapshot: `binance-usdm-futures-2025-8-demo`
- Exchange aggregate SHA256: `599d67345bed5b2b3b42669baf460fa336ffde80502cfd1880ea57cd0dc5074d`
- Expected input fingerprint: `c770e0ab66bb76daa1249851d94006e66e2efdb08ceb334ae444c2dd6730bd79`
- Expected normalized futures trade hash: `74c40da36d57d452066e39e0425a83ae1ddc73be8069c91d184dd6afa5c4e6ee`

## Candidate Source Diff

The only allowed source changes were observed:

- class rename: `RegimeAwareV6` -> `RegimeAware_C3B1_E0001`
- non-runtime identity metadata: `candidate_identity_metadata`
- verbatim dependency copies: `regime_aware_base.py`, `regime_detector.py`, `risk_manager.py`

No semantic changes were made to:

- `can_short`
- timeframe
- startup candles
- entry or exit conditions
- leverage behavior
- stoploss or ROI
- protections
- order settings
- indicators
- fee, funding, margin, or liquidation settings

## Static Validation

Static checks passed:

- Python compile: passed
- Freqtrade `list-strategies`: loaded `RegimeAware_C3B1_E0001`
- candidate class uniqueness: passed
- legacy class conflict: none
- Strategy-Market Contract: passed
- base strategy hash: unchanged
- sealed dataset hash: verified
- sealed exchange hash: verified
- candidate source diff: identity-only
- forbidden source tokens: none

## Baseline Reference

Baseline artifact reused from Stage 3A:

- Run: `research/results/demo-futures-stage3a5-acceptance/stage3a5-futures-f3-cert-003/OFFLINE-CONTROL`
- Artifact integrity: passed, `13` files checked
- Input fingerprint: `c770e0ab66bb76daa1249851d94006e66e2efdb08ceb334ae444c2dd6730bd79`
- Normalized futures trade hash: `74c40da36d57d452066e39e0425a83ae1ddc73be8069c91d184dd6afa5c4e6ee`

## Candidate Run

Artifact:

- `research/results/demo-stage3b1-candidate-identity/1/CANDIDATE-RUN/runner-report.json`

Result:

- Status: accepted
- Total trades: `3`
- Long trades: `2`
- Short trades: `1`
- Total profit: `66.34329576`
- Total profit ratio: `0.006634329576000001`
- Max drawdown: `0.27958697`
- Profit Factor: `238.29037072078145`
- Win rate: `0.6666666666666666`
- Average duration: `1 day, 16:00:00`
- Average leverage: `1.0`
- Funding fees: `0.20088932145673266`
- Enter tags: `ranging_short: 1`, `trending_long: 2`
- Exit reasons: `force_exit: 1`, `ranging_target_middle: 1`, `roi: 1`
- Normalized futures trade hash: `74c40da36d57d452066e39e0425a83ae1ddc73be8069c91d184dd6afa5c4e6ee`

Network policy:

- Socket blocker enabled
- Non-loopback network attempts: none
- Loopback-only Freqtrade internal attempt observed: `127.0.0.1:8502`

## Equivalence Comparison

Artifact:

- `research/results/demo-stage3b1-candidate-identity/1/baseline-candidate-comparison.json`

Result:

- `consistent`: `true`
- `differences`: `{}`
- `total_trades`: `3`
- `long_trade_count`: `2`
- `short_trade_count`: `1`
- normalized futures trade hash matched exactly

## Registry

SQLite table:

- `research/registry/research.db`
- table: `stage3b1_candidate_lifecycle`

Recorded final state:

- `creation_status`: `created`
- `static_validation_status`: `passed`
- `execution_status`: `accepted`
- `equivalence_verdict`: `identity_verified`
- `failure_class`: `null`
- `failure_reason`: `null`

No `champion`, `promoted`, `qualified_challenger`, or `strategy_improved`
status was written.

## Final Report

Machine-readable report:

- `research/results/demo-stage3b1-candidate-identity/1/stage3b1-final-report.json`

Status:

- `status`: `identity_verified`
- `stage3b1_complete`: `true`

## Safety Notes

This stage did not:

- modify `strategies/RegimeAwareV6.py`;
- modify any official strategy in `strategies/`;
- modify live or production config;
- modify sealed dataset, exchange snapshot, or leverage-tier artifacts;
- run Hyperopt;
- run Lookahead Analysis;
- run Recursive Analysis;
- generate new hypotheses;
- promote a Champion;
- access sealed holdout;
- start Docker, server, bot, deploy, or live trading.

## Stage 3B.2 Minimal Next Step

Stage 3B.2 should allow a single isolated candidate copy to change exactly one
pre-authorized strategy variable under the same candidate namespace, while
retaining the same static diff classifier, sealed offline execution, no-network
runner, registry state machine, and baseline/candidate field-level comparison.
