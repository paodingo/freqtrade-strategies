# Researcher Task Packet / 研究员任务包

## Immutable bindings / 不可变绑定

- Trigger fingerprint: `b3939e7db2a82c1253b5091efe09bb0f4020991fb4206912fb60b36cb79d91dd`
- Research state fingerprint: `d69d75d3c4c05dc67753c1ecd196ed1b43a37c5a8038a9326279d14c4b175b59`
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
- `research/governance/backtest-output-namespace-contract.yaml`
- `research/governance/research-constitution.yaml`
- `research/knowledge/open-source-v1/current-context.json`
- `research/proposals/stage3d3b-research-direction-proposal.yaml`
- `research/proposals/stage3d4b-mechanism-proposal.yaml`
- `research/recertification/stage3d3b/stage3d2b-invalidation-event.json`
- `research/runtime/freqtrade-2025-8-signal-execution-contract.yaml`
- `research/runtime/freqtrade-runtime.yaml`
- `research/runtime/offline-adapter-contract.yaml`
- `research/runtime/requirements-freqtrade.lock.txt`
- `research/temporal/stage3e1-temporal-comparison.json`

## Automatic Knowledge Broker / 自动知识召回

This bounded, deterministic Top-K selection is advisory. Apply negative lessons before proposing semantic duplicates. Class C patterns are inspiration only and cannot satisfy the A/B evidence gate.

```json
{
  "governance": {
    "backtest_authorized": false,
    "candidate_creation_authorized": false,
    "class_c_only_result": "reject",
    "proposal_requirement": "at_least_one_A_or_B",
    "strategy_mutation_authorized": false
  },
  "knowledge_snapshot_fingerprint": "86b5d8da34601a7ff59e94029ccf43914d83b14f06764962425875cdbd85ecbc",
  "limits": {
    "max_lessons": 4,
    "max_patterns": 4,
    "ranking": "deterministic_weighted_lexical_v2"
  },
  "query_terms": [
    "bnb xrp descriptive cross pair generalization discovery v1",
    "manual request",
    "cross pair generalization",
    "does temporal consistency persist across additional binance usd m pairs",
    "reproducible eth trade behavior observed",
    "exit logic structure",
    "which exit mechanisms explain regime specific losses without changing risk semantics",
    "no exit change warranted insufficient causal evidence",
    "regime branch structure",
    "are regime branch activation and directionality imbalances structural rather than threshold local",
    "structural directionality rotation observed no mutation warranted",
    "strategy family reassessment",
    "should the current regime aware family be retained restructured or retired from active research",
    "restructure family worth studying",
    "branch contribution ablation",
    "which single regime direction signal group contributes incremental btc eth development evidence",
    "closed mixed temporal dependency",
    "cross pair data readiness audit",
    "exit logic structure audit",
    "regime branch structure audit",
    "stage3d2b runtime cache invalidation",
    "candidate dependency module cache shadowed",
    "recertified",
    "regime aware ranging thresholds v1",
    "closed evidence exhausted",
    "a keep current",
    "ranging long setup rsi max",
    "ranging shared adx 4h max long",
    "ranging short setup bb percent min",
    "ranging short setup rsi min",
    "ranging short branch retention review v1",
    "ranging short entry"
  ],
  "schema_version": "knowledge-broker-selection-v1",
  "selected_lessons": [
    {
      "evidence_paths": [
        "reports/audits/eth-cross-pair-generalization/eth-cross-pair-generalization-final-report.json",
        "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json"
      ],
      "lesson_id": "cross-pair-reproducibility-not-generalization-v1",
      "matched_mechanism_keys": [
        "cross-pair",
        "development-only"
      ],
      "outcome": "descriptive_not_generalized",
      "reuse_policy": "warn_and_require_material_difference",
      "score": 10420,
      "summary_zh": "ETH 在独立进程中稳定复现交易行为，但描述性收益与 Profit Factor 明显弱于 BTC；可复现性只能证明实现稳定，不能证明盈利性或跨币种泛化。",
      "title_zh": "跨币种行为可复现不等于经济泛化成立"
    },
    {
      "evidence_paths": [
        "reports/audits/stage4c1/cycle-1-regime-branch-final-report.json",
        "research/analysis/regime-branch-audit/regime-branch-structure.json"
      ],
      "lesson_id": "regime-directionality-rotation-no-threshold-search-v1",
      "matched_mechanism_keys": [
        "directionality-rotation",
        "regime-branch",
        "threshold-closure"
      ],
      "outcome": "structural_no_mutation",
      "reuse_policy": "warn_and_require_material_difference",
      "score": 940,
      "summary_zh": "单个切片可能高度偏多或偏空，但跨切片方向显著轮动且没有稳定单侧缺陷；结构性分布现象不能作为相邻阈值搜索、删除单侧分支或立即修改策略的依据。",
      "title_zh": "状态方向轮动不构成阈值搜索或立即修改依据"
    },
    {
      "evidence_paths": [
        "research/analysis/branch-contribution-ablation-v1/ablation-execution-attempt-2-contribution-result.json",
        "research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json",
        "research/closures/ranging-short-branch-retention-review-v1.json"
      ],
      "lesson_id": "ranging-short-temporal-retention-v1",
      "matched_mechanism_keys": [
        "branch-contribution",
        "ranging-short",
        "retention-governance",
        "temporal-slices"
      ],
      "outcome": "retained",
      "reuse_policy": "block_semantic_duplicate",
      "score": 750,
      "summary_zh": "全开发区间消融显示该分支在 BTC 与 ETH 上为负贡献，但四个冻结切片分别呈现无贡献、一段正贡献和两段负贡献；证据支持保留现有分支并关闭整体删除研究，未来重开必须提供新的时间稳定证据。",
      "title_zh": "震荡做空分支具有时间依赖，应保留而非整体删除"
    },
    {
      "evidence_paths": [
        "reports/audits/exit-logic-audit/exit-logic-structure-final-report.json",
        "research/analysis/exit-logic-audit/exit-attribution.json"
      ],
      "lesson_id": "exit-frequency-insufficient-causal-evidence-v1",
      "matched_mechanism_keys": [
        "causal-attribution",
        "exit-logic",
        "no-mutation"
      ],
      "outcome": "insufficient_causal_evidence",
      "reuse_policy": "block_semantic_duplicate",
      "score": 660,
      "summary_zh": "退出原因计数和分片损益能够描述现象，但未隔离退出机制的增量因果贡献；不得仅凭 ROI、止损等频率占比重写退出或风险语义。",
      "title_zh": "退出频率归因不足以支持退出逻辑重写"
    }
  ],
  "selected_patterns": [
    {
      "local_data_readiness": "ready",
      "matched_mechanism_keys": [
        "cross-pair"
      ],
      "mechanism_summary_zh": "在统一时钟上组合多个标的和周期，避免分别回测后再主观拼接。",
      "pattern_id": "multi-symbol-timeframe-composition",
      "proposal_eligibility": "inspiration_only_requires_A_or_B",
      "score": 10400,
      "strategy_family": "cross_pair_research",
      "title_zh": "多标的多周期组合"
    },
    {
      "local_data_readiness": "data_readiness_required",
      "matched_mechanism_keys": [
        "cross-sectional"
      ],
      "mechanism_summary_zh": "比较同一时点多个资产的标准化特征，而不是只看单资产绝对阈值。",
      "pattern_id": "cross-sectional-factor-ranking",
      "proposal_eligibility": "inspiration_only_requires_A_or_B",
      "score": 1040,
      "strategy_family": "relative_strength",
      "title_zh": "横截面因子排序"
    },
    {
      "local_data_readiness": "data_readiness_required",
      "matched_mechanism_keys": [
        "cross-venue"
      ],
      "mechanism_summary_zh": "比较资金费率、基差和执行成本，在对冲后捕捉相对价值。",
      "pattern_id": "funding-basis-arbitrage",
      "proposal_eligibility": "inspiration_only_requires_A_or_B",
      "score": 1040,
      "strategy_family": "relative_value",
      "title_zh": "资金费率与基差套利"
    },
    {
      "local_data_readiness": "ready",
      "matched_mechanism_keys": [
        "regime-filter",
        "signal-gating"
      ],
      "mechanism_summary_zh": "低周期负责入场，高周期只提供已经确认的市场状态过滤。",
      "pattern_id": "multi-timeframe-regime-gating",
      "proposal_eligibility": "inspiration_only_requires_A_or_B",
      "score": 150,
      "strategy_family": "regime_filtering",
      "title_zh": "多周期状态过滤"
    }
  ],
  "selection_fingerprint": "58fbbce41429d81c98f519038d8e72d2dfad66d0a3790c1611a80ac5b7c15827",
  "selection_id": "knowledge-selection-3cfac267cbcf0825",
  "trigger_fingerprint": "b3939e7db2a82c1253b5091efe09bb0f4020991fb4206912fb60b36cb79d91dd"
}
```

## Fixed scope / 固定范围

Keep Binance USD-M Futures, isolated margin, approved BTC/ETH Development data, `1h` primary, `4h` informative, the approved runtime, and all existing risk parameters unchanged. You may propose data readiness work, but Do not download market data.

## Forbidden boundaries / 禁止边界

Do not access Validation, Holdout, secrets, private APIs, live accounts, strategy mutation surfaces, Candidate surfaces, or execution surfaces. Do not create or start a Candidate, Campaign, experiment, backtest, or any execution.

## Output / 输出

Write only `research-idea-v1` JSON objects to this absolute system TEMP inbox: `C:\Users\paodi\AppData\Local\Temp\freqtrade-research-discovery\a5fb27a31b427c66\discovery-run-b3939e7db2a82c12\researcher`. The inbox is untrusted staging and is outside the governed repository. Do not modify the trigger or task packet.

## Role contract / 角色合同

# Researcher Role Contract

Generate 6-10 distinct `research-idea-v1` JSON objects. Use at most two ideas per `strategy_family`. You may propose entirely different strategy families, but every idea must keep Binance USD-M Futures, isolated margin, approved BTC/ETH Development data, `1h` primary, `4h` informative, the approved runtime, and existing risk parameters fixed.

Read only sources listed in the task packet. Do not read Validation results, Holdout, secrets, private APIs, live accounts, strategy mutation paths, Candidate paths, or execution runners. External sources may inform an idea only when their required provenance metadata are included. Do not download a market dataset.

Each hypothesis must be falsifiable. Include supporting evidence, contradictory evidence, the strongest known limitation, the smallest useful test, comparison baseline, estimated experiment count, wall-clock minutes, compute class, stop conditions, and a semantic fingerprint request. Do not promise return, win rate, or profitability. Write JSON to the provided inbox only; do not modify governed run artifacts.

When an Automatic Knowledge Broker selection is present, every idea must include `knowledge_use` bound to the exact `selection_id` and `selection_fingerprint`. List only selected pattern IDs, consider every selected lesson, and explain material differences from every selected lesson whose reuse policy blocks or warns about semantic duplication. Broker output never replaces A/B evidence.
