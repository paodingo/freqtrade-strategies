# Researcher Task Packet / 研究员任务包

## Immutable bindings / 不可变绑定

- Trigger fingerprint: `1d637b279e368feb13b8546a5005c86e75e4c3a78f1707ba5772f23884981d81`
- Research state fingerprint: `61733452eb4e4b4be0ea1c6672cdb812e9f18c2115e3e3bd44830654cf248d49`
- Constitution fingerprint: `b4f1570af852773609bb5a5e35e109c10dc263b24995ddcc8e52fa2961527bcd`
- Source policy version: `research-source-policy-v1`

## Allowed read-only sources / 允许只读来源

Read only the exact allowlisted paths below. Do not follow other repository references.

- `docs/decisions/ADR-candidate-python-import-isolation.md`
- `reports/audits/stage3a5_futures_online_offline_adapter_certification.md`
- `reports/decisions/stage3c2_evaluation_policy_decision_packet.md`
- `research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json`
- `research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json`
- `research/analysis/exit-logic-audit/exit-attribution.json`
- `research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json`
- `research/analysis/regime-aware-condition-graph.json`
- `research/analysis/regime-branch-audit/regime-branch-structure.json`
- `research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-lineage.json`
- `research/analysis/stage3d3a-final-report.json`
- `research/analysis/strategy-family-reassessment/family-evidence-matrix.json`
- `research/analysis/strategy-family-reassessment/human-review-packet.json`
- `research/closures/ranging-short-branch-retention-review-v1.json`
- `research/closures/regime-aware-ranging-thresholds-v1.yaml`
- `research/closures/stage3d4b-final-closure.json`
- `research/closures/stage3d4b-mechanism-approval-event.json`
- `research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml`
- `research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/manifest.yaml`
- `research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml`
- `research/director/current-research-state.json`
- `research/director/next-after-ranging-short-temporal/proposals/ranging-short-branch-retention-review-v1.json`
- `research/director/next-after-router-equivalence/proposals/branch-contribution-ablation-v1.json`
- `research/discovery/policy/source-policy.yaml`
- `research/discovery/schemas/research-idea.schema.json`
- `research/evaluation/evaluation-policy.yaml`
- `research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml`
- `research/governance/approvals/eth-cross-pair-generalization-v1-approval.json`
- `research/governance/approvals/ranging-short-branch-retention-review-v1-approval.json`
- `research/governance/backtest-output-namespace-contract.yaml`
- `research/governance/research-constitution.yaml`
- `research/proposals/stage3d3b-research-direction-proposal.yaml`
- `research/proposals/stage3d4b-mechanism-proposal.yaml`
- `research/recertification/stage3d3b/stage3d2b-invalidation-event.json`
- `research/runtime/freqtrade-2025-8-signal-execution-contract.yaml`
- `research/runtime/freqtrade-runtime.yaml`
- `research/runtime/offline-adapter-contract.yaml`
- `research/runtime/requirements-freqtrade.lock.txt`
- `research/temporal/stage3e1-temporal-comparison.json`

## Fixed scope / 固定范围

Keep Binance USD-M Futures, isolated margin, approved BTC/ETH Development data, `1h` primary, `4h` informative, the approved runtime, and all existing risk parameters unchanged. You may propose data readiness work, but Do not download market data.

## Forbidden boundaries / 禁止边界

Do not access Validation, Holdout, secrets, private APIs, live accounts, strategy mutation surfaces, Candidate surfaces, or execution surfaces. Do not create or start a Candidate, Campaign, experiment, backtest, or any execution.

## Output / 输出

Write only `research-idea-v1` JSON objects to this absolute system TEMP inbox: `C:\Users\paodi\AppData\Local\Temp\freqtrade-research-discovery\a5fb27a31b427c66\discovery-run-1d637b279e368feb\researcher`. The inbox is untrusted staging and is outside the governed repository. Do not modify the trigger or task packet.

## Role contract / 角色合同

# Researcher Role Contract

Generate 6-10 distinct `research-idea-v1` JSON objects. Use at most two ideas per `strategy_family`. You may propose entirely different strategy families, but every idea must keep Binance USD-M Futures, isolated margin, approved BTC/ETH Development data, `1h` primary, `4h` informative, the approved runtime, and existing risk parameters fixed.

Read only sources listed in the task packet. Do not read Validation results, Holdout, secrets, private APIs, live accounts, strategy mutation paths, Candidate paths, or execution runners. External sources may inform an idea only when their required provenance metadata are included. Do not download a market dataset.

Each hypothesis must be falsifiable. Include supporting evidence, contradictory evidence, the strongest known limitation, the smallest useful test, comparison baseline, estimated experiment count, wall-clock minutes, compute class, stop conditions, and a semantic fingerprint request. Do not promise return, win rate, or profitability. Write JSON to the provided inbox only; do not modify governed run artifacts.
