#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const EXIT_PASS = 0;
const EXIT_BLOCKED = 1;
const EXIT_TOOL_ERROR = 2;
const L1_CONTRACT_PATH = "research/governance/low-risk-development-descriptive-execution-contract-v1.json";
const L1_CONTRACT_APPROVAL_PATH = "research/governance/approvals/low-risk-development-descriptive-execution-v1-approval.json";
const L1_FEEDBACK_CONTRACT_PATH = "research/governance/low-risk-descriptive-knowledge-feedback-contract-v1.json";
const DESCRIPTIVE_WORKER_CONTRACT_PATH = "research/governance/descriptive-worker-handler-contract-v1.json";
const LEGACY_DEVELOPMENT_MANIFEST_COMPATIBILITY_PATH = "research/governance/legacy-development-manifest-compatibility-v1.json";
const KNOWLEDGE_REVIEW_BATCH_POLICY_PATH = "research/director/knowledge-review-batch-policy-v1.json";
const KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT = "reports/audits/open-source-learning-v1/review-batches/aggregated";

const HIGH_RISK_SURFACES = [
  { prefix: "strategies/", reason: "strategy code is outside the harness surface" },
  { prefix: "user_data/", reason: "bot config/runtime data is outside the harness surface" },
  { prefix: "configs/", reason: "bot config surface is outside the harness surface" },
  { prefix: "dashboard/", reason: "dashboard runtime surface is outside the harness surface" },
  { path: "scripts/start_bot.sh", reason: "bot start script is outside the harness surface" },
  { path: "scripts/ensure_dry_run_bots_started.sh", reason: "bot lifecycle script is outside the harness surface" },
  { path: "scripts/refresh_data.sh", reason: "market data refresh script is outside the harness surface" },
  { path: "scripts/check_system_health.sh", reason: "server/system health script is outside the harness surface" },
  { path: "scripts/check_trades.sh", reason: "trade monitor script is outside the harness surface" },
  { prefix: "deploy/", reason: "deployment surface is outside the harness surface" },
  { prefix: "reports/reliable_strategy_search_v1129/", reason: "V11.29 report surface is outside the harness surface" },
  { path: ".env", reason: "local secret environment file is outside the harness surface" },
  { path: "user_data/monitor.env", reason: "monitor secret environment file is outside the harness surface" },
];

const EXACT_TRADE_MONITOR_EXCEPTIONS = new Set([
  "scripts/check_trades.sh",
  "scripts/notify_trades.sh",
]);

const EXACT_HIGH_RISK_SHADOW_EXCEPTIONS = new Set([
  "strategies/RegimeAwareV1129RangingShortShadow.py",
  "user_data/config_multi_futures_v1129_ranging_short_shadow.json",
  "strategies/RegimeAwareV1130CrashReboundShadow.py",
  "user_data/config_multi_futures_v1130_crash_rebound_shadow.json",
  "strategies/RegimeAwareV1131LooseRangeWatchShadow.py",
  "user_data/config_multi_futures_v1131_loose_range_watch_shadow.json",
  "dashboard/lib/config.js",
  "dashboard/lib/env_aware_fetch.js",
  "dashboard/server.js",
]);

const EXACT_PAPER_LANE_RECOVERY_EXCEPTIONS = new Set([
  "deploy/reconcile_dry_run_bots.py",
  "deploy/runtime-bots.json",
  "docs/paper_lane_recovery.md",
  "tests/test_dry_run_bot_runtime.py",
]);

const EXACT_FRONTEND_V1_EXCEPTIONS = new Set([
  "dashboard/config/strategy-registry.json",
  "dashboard/contracts/strategy-registry.schema.json",
  "dashboard/lib/config.js",
  "dashboard/lib/data_reliability.js",
  "dashboard/lib/performance.js",
  "dashboard/lib/strategy_registry.js",
  "dashboard/server.js",
  "dashboard/start.js",
  "dashboard/public/v2/index.html",
  "dashboard/public/v2/assets/app.css",
  "dashboard/public/v2/assets/app.js",
  "dashboard/public/v2/assets/fonts/jetbrains-mono-cyrillic-wght-normal.woff2",
  "dashboard/public/v2/assets/fonts/jetbrains-mono-greek-wght-normal.woff2",
  "dashboard/public/v2/assets/fonts/jetbrains-mono-latin-ext-wght-normal.woff2",
  "dashboard/public/v2/assets/fonts/jetbrains-mono-latin-wght-normal.woff2",
  "dashboard/public/v2/assets/fonts/jetbrains-mono-vietnamese-wght-normal.woff2",
  "dashboard/public/v2/assets/fonts/sora-latin-ext-wght-normal.woff2",
  "dashboard/public/v2/assets/fonts/sora-latin-wght-normal.woff2",
  "dashboard/web/eslint.config.js",
  "dashboard/web/index.html",
  "dashboard/web/package-lock.json",
  "dashboard/web/package.json",
  "dashboard/web/src/App.tsx",
  "dashboard/web/src/api/market.test.ts",
  "dashboard/web/src/api/market.ts",
  "dashboard/web/src/api/strategyRegistry.test.ts",
  "dashboard/web/src/api/strategyRegistry.ts",
  "dashboard/web/src/components/DashboardHeader.tsx",
  "dashboard/web/src/components/EvidencePanel.tsx",
  "dashboard/web/src/components/FreshnessPanel.tsx",
  "dashboard/web/src/components/MarketPanel.tsx",
  "dashboard/web/src/components/PerformancePanel.tsx",
  "dashboard/web/src/components/StatePanel.tsx",
  "dashboard/web/src/components/StrategyCard.tsx",
  "dashboard/web/src/components/StrategyComparisonPanel.tsx",
  "dashboard/web/src/components/TweaksPanel.tsx",
  "dashboard/web/src/hooks/useDashboardPreferences.ts",
  "dashboard/web/src/lib/format.test.ts",
  "dashboard/web/src/lib/format.ts",
  "dashboard/web/src/lib/compare.test.ts",
  "dashboard/web/src/lib/compare.ts",
  "dashboard/web/src/main.tsx",
  "dashboard/web/src/styles.css",
  "dashboard/web/src/data-panels.css",
  "dashboard/web/src/variants/CockpitView.tsx",
  "dashboard/web/src/variants/NarrativeView.tsx",
  "dashboard/web/src/variants/TerminalView.tsx",
  "dashboard/web/src/views.css",
  "dashboard/web/src/vite-env.d.ts",
  "dashboard/web/tsconfig.app.json",
  "dashboard/web/tsconfig.json",
  "dashboard/web/tsconfig.node.json",
  "dashboard/web/vite.config.ts",
  "docs/frontend_module_charter.md",
  "docs/frontend_module_charter.zh-CN.html",
  "scripts/guard_harness_diff.js",
  "scripts/guard_trading_surface.js",
  "scripts/data_reliability_controller.py",
  "deploy/freqtrade-data-reliability.service",
  "deploy/freqtrade-data-reliability.timer",
  "deploy/install_dry_run_release.sh",
  "tests/test_data_reliability.js",
  "tests/test_data_reliability_controller.py",
  "tests/test_automation_workflows_static.py",
  "tests/test_operational_release_static.py",
  "tests/test_release_bundle.py",
  "tests/test_strategy_registry.js",
  "tests/test_dashboard_performance.js",
  "tests/test_dashboard_public_metadata.js",
  "tests/test_env_aware_fetch.js",
]);

const LOW_RISK_SURFACES = [
  { path: ".gitignore" },
  { path: ".gitattributes" },
  { path: "AGENTS.md" },
  { path: "README.md" },
  { path: "STRATEGY_GUIDE.md" },
  { path: "DEPLOY.md" },
  { path: "LIVE_TRADING.md" },
  { path: "AUTONOMY.md" },
  { path: "WORKFLOW.md" },
  { exact: "harness/protocol/v0.1/harness-protocol.schema.json" },
  { exact: "harness/protocol/v0.1/protocol-manifest.json" },
  { exact: "harness/protocol/v0.1/fixtures/normal.json" },
  { exact: "harness/protocol/v0.1/fixtures/governed-block.json" },
  { exact: "harness/protocol/v0.1/fixtures/tool-error.json" },
  { exact: "harness/protocol/v0.1/fixtures/authority-mismatch.json" },
  { exact: "harness/protocol/v0.1/fixtures/known-baseline-debt.json" },
  { exact: "tests/test_harness_protocol_guard_contract.py" },
  { exact: "tests/test_harness_protocol_contracts.py" },
  { exact: "tests/test_harness_protocol_conformance.py" },
  { regex: /^\.github\/workflows\/[^/]+\.ya?ml$/ },
  { path: "research/campaigns/active/demo-control-plane.yaml" },
  { path: "research/campaigns/active/demo-happy-path.yaml" },
  { path: "research/campaigns/active/demo-guard-escalation.yaml" },
  { path: "research/campaigns/active/demo-fixed-backtest.yaml" },
  { path: "research/campaigns/active/demo-sealed-offline-backtest.yaml" },
  { path: "research/campaigns/active/demo-futures-stage3a5.yaml" },
  { path: "research/campaigns/active/demo-futures-stage3a5-acceptance.yaml" },
  { path: "research/campaigns/active/demo-stage3b1-candidate-identity.yaml" },
  { path: "research/campaigns/active/demo-stage3b2-single-variable.yaml" },
  { path: "research/campaigns/active/stage3c1-research-data-plane.yaml" },
  { path: "research/campaigns/active/stage3d1-bounded-autonomous-search.yaml" },
  { path: "research/runtime/freqtrade-runtime.yaml" },
  { path: "research/runtime/offline-adapter-contract.yaml" },
  { path: "research/runtime/demo-backtest-config.json" },
  { path: "research/runtime/demo-futures-backtest-config.json" },
  { path: "research/runtime/requirements-freqtrade.lock.txt" },
  { path: "research/runtime/freqtrade-freeze.txt" },
  { path: "research/runtime/research-control-requirements.lock.txt" },
  { path: "research/runtime/systemd/research-registry-backup.service" },
  { path: "research/runtime/systemd/research-registry-backup.timer" },
  { path: "research/runtime/freqtrade-version-selection.md" },
  { path: "research/runtime/README.md" },
  { regex: /^research\/runtime\/provisioning\/[^/]+\.log$/ },
  { regex: /^research\/runtime\/provisioning\/[^/]*endpoint-doctor[^/]*\.json$/ },
  { path: "research/data/dataset-manifest.schema.json" },
  { path: "research/data/data-usage-policy.yaml" },
  { path: "research/data/validation-access-policy.yaml" },
  { path: "research/data/pollution-state-model.yaml" },
  { path: "research/data/evaluation-result.schema.json" },
  { path: "research/search-spaces/regime-aware-safe-mutations-v1.yaml" },
  { path: "research/search-spaces/regime-aware-safe-mutations-v2-proposal.yaml" },
  { path: "research/search-spaces/regime-aware-safe-mutations-v2-batch1.yaml" },
  { path: "research/queues/stage3d2b-batch1-experiments.yaml" },
  { path: "research/campaigns/active/stage3d2b-reachability-informed-batch1.yaml" },
  { regex: /^research\/(candidates|experiments|results)\/stage3d2b-reachability-informed-batch1\// },
  { path: "research/queues/stage3d1-experiments.yaml" },
  { path: "research/analysis/regime-aware-condition-graph.json" },
  { regex: /^research\/analysis\/stage3d2a-[^/]+\.json$/ },
  { path: "research/analysis/signal-to-trade-lifecycle-v1.yaml" },
  { regex: /^research\/analysis\/stage3d3a-[^/]+\.(json|md)$/ },
  { path: "research/runtime/freqtrade-2025-8-signal-execution-contract.yaml" },
  { path: "research/proposals/stage3d3b-research-direction-proposal.yaml" },
  { path: "reports/audits/stage3d3a_signal_to_trade_attribution.md" },
  { path: "reports/audits/stage3d3a_freqtrade_execution_semantics.md" },
  { path: "research/queues/stage3d3b-recertification.yaml" },
  { path: "research/campaigns/active/stage3d3b-candidate-process-isolation-recertification.yaml" },
  { regex: /^research\/recertification\/stage3d3b\// },
  { regex: /^research\/results\/stage3d3b-candidate-process-isolation-recertification\// },
  { path: "reports/amendments/stage3d2b-runtime-cache-invalidation.md" },
  { path: "docs/decisions/ADR-candidate-python-import-isolation.md" },
  { regex: /^research\/analysis\/stage3d4a-[^/]+\.json$/ },
  { path: "reports/audits/stage3d4a_single_threshold_research_closure.md" },
  { path: "reports/audits/stage3d4a_first_trigger_semantics.md" },
  { path: "reports/audits/stage3d4a_position_adjustment_risk_audit.md" },
  { path: "reports/audits/stage3d4a_final_report.md" },
  { path: "reports/decisions/stage3d4b_mechanism_decision_packet.md" },
  { path: "research/proposals/stage3d4b-mechanism-proposal.yaml" },
  { path: "scripts/close_stage3d4b_research_branch.py" },
  { path: "tests/test_stage3d4b_research_branch_closure.py" },
  { regex: /^research\/closures\/stage3d4b-[^/]+\.(json|yaml)$/ },
  { path: "research/closures/regime-aware-ranging-thresholds-v1.yaml" },
  { path: "research/governance/research-constitution.yaml" },
  { path: "research/discovery/schemas/research-trigger.schema.json" },
  { path: "research/discovery/schemas/research-idea.schema.json" },
  { path: "research/discovery/schemas/research-critique.schema.json" },
  { path: "research/discovery/schemas/research-shortlist.schema.json" },
  { path: "research/discovery/schemas/research-direction-approval.schema.json" },
  { path: "research/discovery/schemas/research-direction-handoff.schema.json" },
  { path: "research/discovery/policy/source-policy.yaml" },
  { path: "research/discovery/policy/ranking-policy.yaml" },
  { path: "research/discovery/prompts/researcher.md" },
  { path: "research/discovery/prompts/critic.md" },
  { prefix: "research/discovery/runs/" },
  { prefix: "reports/audits/research-discovery/" },
  { prefix: "tests/fixtures/research-discovery/" },
  { path: "docs/superpowers/specs/2026-07-14-researcher-critic-discovery-design.md" },
  { path: "docs/superpowers/specs/2026-07-14-researcher-critic-discovery-design.zh-CN.html" },
  { path: "docs/superpowers/plans/2026-07-14-researcher-critic-discovery.md" },
  { path: "docs/superpowers/plans/2026-07-14-researcher-critic-discovery.zh-CN.html" },
  { path: "research/governance/windows-execution-path-budget.yaml" },
  { path: "research/governance/temporal-ablation-candidate-identity-propagation-v1.json" },
  { prefix: "research/governance/approvals/" },
  { prefix: "research/director/" },
  { prefix: "research/candidates/branch-contribution-ablation-v1/" },
  { prefix: "research/analysis/branch-contribution-ablation-v1/" },
  { prefix: "reports/audits/branch-contribution-ablation-v1/" },
  { path: "scripts/run_branch_contribution_ablation_campaign.py" },
  { path: "tests/test_branch_contribution_ablation_campaign.py" },
  { path: "tests/test_ranging_short_branch_decision_review_compilation.py" },
  { path: "scripts/compile_ranging_short_temporal_campaign.py" },
  { path: "tests/test_ranging_short_temporal_campaign_compilation.py" },
  { path: "scripts/run_ranging_short_temporal_campaign.py" },
  { path: "scripts/record_ranging_short_temporal_stop.py" },
  { path: "tests/test_ranging_short_temporal_campaign_execution.py" },
  { path: "tests/test_temporal_candidate_identity_propagation.py" },
  { path: "tests/test_temporal_attempt4_execution_binding.py" },
  { path: "scripts/windows_execution_paths.py" },
  { path: "tests/test_windows_execution_path_budget.py" },
  { path: "scripts/portable_runtime_assets.py" },
  { path: "scripts/build_portable_runtime_asset_manifest.py" },
  { path: "scripts/hydrate_portable_runtime.py" },
  { path: "scripts/verify_portable_runtime.py" },
  { path: "tests/test_portable_runtime_hydration.py" },
  { path: "research/runtime/portable-runtime-assets-freqtrade-2025.8.json" },
  { path: "reports/audits/portable-runtime-hydration-v1.json" },
  { path: "reports/audits/portable-runtime-hydration-v1.md" },
  { path: "research/analysis/ranging-short-temporal-review-v1/campaign-stopped.json" },
  { path: "research/analysis/ranging-short-temporal-review-v1/campaign-stopped-attempt-2.json" },
  { path: "research/analysis/ranging-short-temporal-review-v1/campaign-stopped-attempt-3.json" },
  { path: "research/analysis/ranging-short-temporal-review-v1/campaign-stopped-attempt-3-root-cause-amendment.json" },
  { path: "research/analysis/ranging-short-temporal-review-v1/ranging-short-ablation-s01-contribution-comparison.json" },
  { path: "research/analysis/ranging-short-temporal-review-v1/ranging-short-ablation-s02-contribution-comparison.json" },
  { path: "research/analysis/ranging-short-temporal-review-v1/ranging-short-ablation-s03-contribution-comparison.json" },
  { path: "research/analysis/ranging-short-temporal-review-v1/ranging-short-ablation-s04-contribution-comparison.json" },
  { path: "research/analysis/ranging-short-temporal-review-v1/temporal-contribution-result.json" },
  { path: "reports/audits/ranging-short-temporal-review-v1/campaign-stopped.json" },
  { path: "reports/audits/ranging-short-temporal-review-v1/campaign-stopped.md" },
  { path: "reports/audits/ranging-short-temporal-review-v1/campaign-stopped-attempt-2.json" },
  { path: "reports/audits/ranging-short-temporal-review-v1/campaign-stopped-attempt-2.md" },
  { path: "reports/audits/ranging-short-temporal-review-v1/campaign-stopped-attempt-3.json" },
  { path: "reports/audits/ranging-short-temporal-review-v1/campaign-stopped-attempt-3.md" },
  { path: "reports/audits/ranging-short-temporal-review-v1/campaign-stopped-attempt-3-root-cause-amendment.json" },
  { path: "reports/audits/ranging-short-temporal-review-v1/campaign-stopped-attempt-3-root-cause-amendment.md" },
  { path: "reports/audits/ranging-short-temporal-review-v1/final-report.json" },
  { path: "reports/audits/ranging-short-temporal-review-v1/final-report.md" },
  { path: "research/closures/ranging-short-branch-retention-review-v1.json" },
  { path: "reports/closures/ranging-short-branch-retention-review-v1-final-report.json" },
  { path: "reports/closures/ranging-short-branch-retention-review-v1-final-report.md" },
  { path: "scripts/close_ranging_short_branch_retention.py" },
  { path: "tests/test_ranging_short_branch_retention_closure.py" },
  { path: "research/temporal/ranging-short-ablation-temporal-slices-v1.yaml" },
  { prefix: "reports/audits/cross-pair-data-readiness/" },
  { prefix: "reports/audits/exit-logic-audit/" },
  { prefix: "reports/audits/stage4c1/" },
  { prefix: "reports/audits/eth-cross-pair-generalization/" },
  { prefix: "research/analysis/exit-logic-audit/" },
  { prefix: "research/analysis/regime-branch-audit/" },
  { prefix: "research/analysis/eth-cross-pair-generalization/" },
  { path: "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml" },
  { path: "reports/audits/stage4a_research_director_final_report.json" },
  { path: "reports/closures/stage3d4b_regime_aware_threshold_branch_closure.md" },
  { path: "scripts/build_temporal_generalization_profile.py" },
  { path: "scripts/run_temporal_slice_worker.py" },
  { path: "tests/test_stage3e1_temporal_generalization_profile.py" },
  { path: "research/campaigns/active/stage3e1-temporal-generalization-profile.yaml" },
  { regex: /^research\/temporal\/stage3e1-[^/]+\.(json|yaml)$/ },
  { regex: /^research\/temporal\/(profiles|execution-manifests)\/stage3e1-[^/]+\.(json|md)$/ },
  { regex: /^research\/temporal\/execution-manifests\/stage3e1-s\d+\/RUN-[AB](\.launch)?\.json$/ },
  { regex: /^research\/temporal\/snapshots\/temporal-stage3e1-s\d+-btc-usdt-usdt-1h\// },
  { regex: /^research\/results\/stage3e1-temporal-generalization-profile\// },
  { path: "reports/audits/stage3e1_temporal_data_coverage_audit.md" },
  { path: "research/data/splits/futures-dev-validation-v1.yaml" },
  { path: "research/data/splits/futures-dev-validation-v2-policy.yaml" },
  { path: "research/data/splits/futures-dev-validation-v2.yaml" },
  { regex: /^research\/data\/provisioning\/stage3c2p-[^/]+\.(json|yaml|md|log)$/ },
  { regex: /^research\/data\/profiles\/futures-dev-validation-v1-market-profile\.(json|md)$/ },
  { regex: /^research\/data\/snapshots\/futures-(dev|validation)-btc-usdt-usdt-[^/]+\/manifest\.yaml$/ },
  { regex: /^research\/data\/snapshots\/futures-(dev|validation)-btc-usdt-usdt-[^/]+\/data\/futures\/[^/]+\.feather$/ },
  { path: "research/data/data-lineage.sqlite" },
  { path: "research/evaluation/evaluation-policy.yaml" },
  { path: "research/evaluation/evaluation-policy-proposal.yaml" },
  { path: "research/evaluation/stage3c3-readiness.json" },
  { path: "research/evaluation/stage3c3-result.json" },
  { path: "research/data/snapshots/demo-btc-usdt-1h-202401/manifest.yaml" },
  { path: "research/data/snapshots/demo-btc-usdt-1h-202401/README.md" },
  { path: "research/data/snapshots/demo-btc-usdt-usdt-futures-1h-202401/manifest.yaml" },
  { path: "research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-202603-202606/manifest.yaml" },
  { path: "research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-20260329-20260412/manifest.yaml" },
  { regex: /^research\/data\/snapshots\/demo-btc-usdt-usdt-futures-1h-202401\/data\/futures\/[^/]+\.(feather|json)$/ },
  { regex: /^research\/data\/snapshots\/demo-btc-usdt-usdt-futures-acceptance-[^/]+\/data\/futures\/[^/]+\.(feather|json)$/ },
  { regex: /^research\/registry\/(research\.db|audit_events\.jsonl|campaign_report-[^/]+\.md)$/ },
  { regex: /^research\/results\/demo-futures-stage3a5\/[^/]+\/[^/]+\/[^/]+\.(json|yaml|log|zip)$/ },
  { regex: /^research\/results\/demo-stage3b1-candidate-identity\/[^/]+\/[^/]+\.(json|yaml|log|zip)$/ },
  { regex: /^research\/results\/demo-stage3b1-candidate-identity\/[^/]+\/[^/]+\/[^/]+\.(json|yaml|log|zip)$/ },
  { regex: /^research\/candidates\/demo-stage3b1-candidate-identity\/[^/]+\/[^/]+\.(py|yaml|json)$/ },
  { regex: /^research\/experiments\/demo-stage3b2-single-variable\/[^/]+\/[^/]+\.(yaml|json)$/ },
  { regex: /^research\/results\/demo-stage3b2-single-variable\/[^/]+\/[^/]+\.(json|yaml|log|zip)$/ },
  { regex: /^research\/results\/demo-stage3b2-single-variable\/[^/]+\/[^/]+\/[^/]+\.(json|yaml|log|zip)$/ },
  { regex: /^research\/candidates\/demo-stage3b2-single-variable\/[^/]+\/[^/]+\.(py|yaml|json)$/ },
  { regex: /^research\/experiments\/stage3d1-bounded-autonomous-search\/[^/]+\/[^/]+\.(yaml|json)$/ },
  { regex: /^research\/candidates\/stage3d1-bounded-autonomous-search\/[^/]+\/[^/]+\.(py|yaml|json)$/ },
  { regex: /^research\/results\/stage3c1-research-data-plane\/.+\.(json|yaml|log|zip)$/ },
  { regex: /^research\/results\/stage3c2-candidate-evaluation\/.+\.(json|yaml|log|zip|md)$/ },
  { regex: /^research\/results\/stage3c2r-readiness\/.+\.(json|yaml|log|zip|md)$/ },
  { regex: /^research\/results\/stage3c3-balanced-research-gate\/.+\.(json|yaml|log|zip|md)$/ },
  { regex: /^research\/results\/stage3d1-bounded-autonomous-search\/.+\.(json|yaml|log|zip|md)$/ },
  { regex: /^research\/exchange_snapshots\/[^/]+\/(manifest\.yaml|markets\.raw\.json|markets\.normalized\.json|currencies\.json|options\.json|artifact-hashes\.json|capture\.log|endpoint-doctor\.json|ccxt-url-structure\.json)$/ },
  { regex: /^research\/exchange_snapshots\/[^/]+\/(leverage-tiers-contract\.json|futures-scope-fingerprint\.json)$/ },
  { regex: /^research\/exchange_snapshots\/[^/]+\/fapi\.exchangeInfo\.raw\.json$/ },
  { prefix: "docs/harness/" },
  { path: "docs/decisions/ADR-offline-freqtrade-backtesting.md" },
  { path: "docs/quality/test-baseline.yaml" },
  { path: "reports/audits/portable-baseline-dependency-audit.json" },
  { path: "reports/audits/portable-baseline-dependency-audit.md" },
  { path: "research/testing/portable-baseline-fixture-contract.yaml" },
  { path: "research/testing/portable-baseline-profile.yaml" },
  { path: "scripts/build_portable_baseline_fixture_pack.py" },
  { path: "scripts/hydrate_portable_baseline_fixture_pack.py" },
  { path: "scripts/portable_baseline_fixtures.py" },
  { path: "scripts/verify_portable_baseline_fixture_pack.py" },
  { path: "scripts/run_portable_test_suite.py" },
  { path: "scripts/block_portable_network.js" },
  { path: "tests/portable_baseline_support.py" },
  { path: "tests/test_portable_baseline_fixtures.py" },
  { prefix: "tests/fixtures/portable-baseline/" },
  { path: "reports/audits/stage3a_strategy_market_contract_audit.md" },
  { path: "reports/audits/stage3b2_single_variable_selection.md" },
  { path: "reports/audits/stage3b2_single_variable_semantic_mutation.md" },
  { path: "reports/audits/stage3c1_research_data_inventory.md" },
  { path: "reports/audits/stage3c1_research_data_plane.md" },
  { path: "reports/decisions/stage3c2_evaluation_policy_decision_packet.md" },
  { path: "docs/agent_operating_playbook.md" },
  { path: "docs/agent_operating_playbook.html" },
  { path: "docs/opensource_reference_audit.md" },
  { path: "docs/\u9a8c\u6536\u62a5\u544a\u683c\u5f0f.md" },
  { regex: /^reports\/audits\/.+\.md$/ },
  { regex: /^tasks\/.+\.md$/ },
  { path: "scripts/build_v1129_execution_empty_report.js" },
  { path: "reports/v1129_execution_validation/sample_empty_report.json" },
  { path: "reports/v1129_execution_validation/sample_empty_report.md" },
  { path: "scripts/build_v1129_snapshot_insufficient_report.js" },
  { path: "reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json" },
  { path: "reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md" },
  { path: "scripts/build_v1129_signal_decision_telemetry.js" },
  { path: "reports/v1129_execution_validation/signal_decision_telemetry_sample.json" },
  { path: "reports/v1129_execution_validation/signal_decision_telemetry_sample.md" },
  { path: "scripts/build_v1129_pre_filter_signal_reconstruction.js" },
  { path: "reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json" },
  { path: "reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md" },
  { path: "scripts/build_v1129_ranging_short_offline_return_study.js" },
  { path: "reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.json" },
  { path: "reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.md" },
  { path: "scripts/build_v1129_feather_ranging_short_historical_return_study.js" },
  { path: "reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json" },
  { path: "reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.md" },
  { path: "scripts/build_v1129_high_volatility_replay_harness.js" },
  { path: "reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.json" },
  { path: "reports/v1129_execution_validation/v1129_high_volatility_replay_scorecard.md" },
  { path: "tests/test_v1129_high_volatility_replay_harness.js" },
  { path: "tests/test_regime_aware_v1130_crash_rebound_shadow.py" },
  { path: "tests/test_regime_aware_v1131_loose_range_watch_shadow.py" },
  { path: "scripts/build_v1130_gate_telemetry_report.js" },
  { path: "reports/v1130_observation/v1130_gate_telemetry_report.json" },
  { path: "reports/v1130_observation/v1130_gate_telemetry_report.md" },
  { path: "scripts/build_v1130_loose_range_replay_report.js" },
  { path: "reports/v1130_observation/v1130_loose_range_replay_report.json" },
  { path: "reports/v1130_observation/v1130_loose_range_replay_report.md" },
  { path: "scripts/build_v1130_watch_only_telemetry_report.js" },
  { path: "reports/v1130_observation/v1130_watch_only_telemetry_report.json" },
  { path: "reports/v1130_observation/v1130_watch_only_telemetry_report.md" },
  { path: "scripts/build_v1130_decision_trace_report.js" },
  { path: "reports/v1130_observation/v1130_decision_trace_report.json" },
  { path: "reports/v1130_observation/v1130_decision_trace_report.md" },
  { path: "reports/v1130_observation/v1130_final_decision_telemetry.json" },
  { path: "reports/v1130_observation/v1130_final_decision_telemetry.md" },
  { path: "scripts/refresh_v1130_market_data.sh" },
  { path: "scripts/build_strategy_candidate_search_harness.js" },
  { path: "reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json" },
  { path: "reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.md" },
  { path: "reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_matrix.csv" },
  { path: "scripts/build_v1131_loose_range_replay_report.js" },
  { path: "reports/v1131_observation/v1131_loose_range_replay_report.json" },
  { path: "reports/v1131_observation/v1131_loose_range_replay_report.md" },
  { path: "scripts/build_v1131_loose_range_replay_coverage_extension.js" },
  { path: "reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json" },
  { path: "reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md" },
  { path: "scripts/build_v1131_longer_replay_window_inventory.js" },
  { path: "reports/v1131_observation/v1131_longer_replay_window_inventory.json" },
  { path: "reports/v1131_observation/v1131_longer_replay_window_inventory.md" },
  { path: "scripts/build_v1131_longer_replay_data_source_inventory.js" },
  { path: "reports/v1131_observation/v1131_longer_replay_data_source_inventory.json" },
  { path: "reports/v1131_observation/v1131_longer_replay_data_source_inventory.md" },
  { path: "scripts/build_v1131_longer_replay_data_acquisition_plan.js" },
  { path: "reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json" },
  { path: "reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.md" },
  { path: "scripts/build_v1131_longer_replay_data_acquisition_execution_report.js" },
  { path: "reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.json" },
  { path: "reports/v1131_observation/v1131_longer_replay_data_acquisition_execution_report.md" },
  { path: "scripts/build_v1131_longer_replay_data_acquisition_actual_execution_report.js" },
  { path: "reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.json" },
  { path: "reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.md" },
  { path: "scripts/build_ranging_short_alpha_state_reconstruction.js" },
  { path: "reports/ranging_short_research/ranging_short_alpha_state_reconstruction.json" },
  { path: "reports/ranging_short_research/ranging_short_alpha_state_reconstruction.md" },
  { path: "scripts/build_ranging_short_alpha_taker_data_source_inventory.js" },
  { path: "reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.json" },
  { path: "reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.md" },
  { path: "scripts/build_ranging_short_alpha_taker_source_acquisition_plan.js" },
  { path: "reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.json" },
  { path: "reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.md" },
  { path: "scripts/build_ranging_short_alpha_taker_source_acquisition_execution_report.js" },
  { path: "reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_execution_report.json" },
  { path: "reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_execution_report.md" },
  { path: "scripts/build_ranging_short_alpha_taker_source_acquisition_actual_execution_report.js" },
  { path: "reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_actual_execution_report.json" },
  { path: "reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_actual_execution_report.md" },
  { path: "scripts/build_v1130_runtime_performance_audit.js" },
  { path: "reports/v1130_observation/v1130_runtime_performance_audit.json" },
  { path: "reports/v1130_observation/v1130_runtime_performance_audit.md" },
  { path: "scripts/build_v1130_live_telemetry_window_report.js" },
  { path: "reports/v1130_observation/v1130_live_telemetry_window_report.json" },
  { path: "reports/v1130_observation/v1130_live_telemetry_window_report.md" },
  { path: "scripts/build_v1130_live_telemetry_server_collection_plan.js" },
  { path: "reports/v1130_observation/v1130_live_telemetry_server_collection_plan.json" },
  { path: "reports/v1130_observation/v1130_live_telemetry_server_collection_plan.md" },
  { path: "scripts/build_v1130_live_telemetry_server_collection_execution_report.js" },
  { path: "reports/v1130_observation/v1130_live_telemetry_server_collection_execution_report.json" },
  { path: "reports/v1130_observation/v1130_live_telemetry_server_collection_execution_report.md" },
  { path: "scripts/build_v1130_live_telemetry_server_collection_actual_execution_report.js" },
  { path: "reports/v1130_observation/v1130_live_telemetry_server_collection_actual_execution_report.json" },
  { path: "reports/v1130_observation/v1130_live_telemetry_server_collection_actual_execution_report.md" },
  { path: "scripts/check_trades.sh" },
  { path: "scripts/notify_trades.sh" },
  { regex: /^scripts\/guard_[^/]+\.js$/ },
  { path: "scripts/seed_demo_campaign.py" },
  { path: "scripts/research_control.py" },
  { path: "scripts/research_data_guard.py" },
  { path: "scripts/research_director.py" },
  { path: "scripts/research_director_common.py" },
  { path: "scripts/research_discovery_common.py" },
  { path: "scripts/research_discovery_trigger.py" },
  { path: "scripts/research_discovery_review.py" },
  { path: "scripts/research_discovery_route.py" },
  { path: "scripts/research_environment_doctor.py" },
  { path: "scripts/research_guard.py" },
  { path: "scripts/research_orchestrator.py" },
  { path: "scripts/research_status.py" },
  { path: "scripts/build_current_research_state.py" },
  { path: "scripts/compile_research_campaign.py" },
  { path: "scripts/export_director_registry.py" },
  { path: "scripts/route_research_approval.py" },
  { path: "scripts/stage4b1_governance.py" },
  { path: "scripts/run_cross_pair_readiness_campaign.py" },
  { path: "scripts/run_exit_logic_structure_campaign.py" },
  { path: "scripts/run_regime_branch_structure_campaign.py" },
  { path: "scripts/stage4c1_portfolio.py" },
  { path: "scripts/run_eth_cross_pair_generalization_campaign.py" },
  { path: "scripts/run_experiment.py" },
  { path: "scripts/seal_dataset_snapshot.py" },
  { path: "scripts/compare_reproducibility.py" },
  { path: "scripts/capture_exchange_snapshot.py" },
  { path: "scripts/capture_futures_exchange_snapshot.py" },
  { path: "scripts/provision_futures_dataset_snapshot.py" },
  { path: "scripts/exchange_endpoint_doctor.py" },
  { path: "scripts/futures_endpoint_doctor.py" },
  { path: "scripts/exchange_metadata_fingerprint.py" },
  { path: "scripts/validate_strategy_market_contract.py" },
  { path: "scripts/validate_exchange_snapshot.py" },
  { path: "scripts/sealed_exchange_factory.py" },
  { path: "scripts/run_offline_backtest.py" },
  { path: "scripts/run_stage3a5_acceptance.py" },
  { path: "scripts/create_candidate_strategy.py" },
  { path: "scripts/run_stage3b1_candidate_identity.py" },
  { path: "scripts/run_stage3b2_single_variable.py" },
  { path: "scripts/build_stage3c1_data_plane.py" },
  { path: "scripts/build_stage3c2p_provisioning.py" },
  { path: "scripts/build_stage3c2r_readiness.py" },
  { path: "scripts/build_stage3c3_evaluation.py" },
  { path: "scripts/run_stage3d1_bounded_search.py" },
  { path: "scripts/analyze_strategy_signal_reachability.py" },
  { path: "scripts/profile_futures_market_regimes.py" },
  { path: "scripts/evaluate_research_candidate.py" },
  { path: "scripts/verify_test_baseline.py" },
  { path: "tests/test_research_control_plane.py" },
  { path: "tests/test_research_runner.py" },
  { path: "tests/test_research_environment_doctor.py" },
  { path: "tests/test_research_discovery_contracts.py" },
  { path: "tests/test_research_discovery_registry.py" },
  { path: "tests/test_research_discovery_workflow.py" },
  { path: "tests/test_stage4a_research_director.py" },
  { path: "tests/test_stage4b1_cross_pair_readiness.py" },
  { path: "tests/test_exit_logic_structure_campaign.py" },
  { path: "tests/test_stage4c1_portfolio.py" },
  { path: "tests/test_eth_cross_pair_generalization_campaign.py" },
  { path: "tests/test_strategy_family_reassessment_preparation.py" },
  { path: "tests/test_protected_manifest_hash_contract.py" },
  { path: "scripts/protected_manifest_hash.py" },
  { path: "scripts/audit_manifest_checkout_hashes.py" },
  { path: "research/governance/manifest-hash-contract.yaml" },
  { path: "research/governance/protected-manifest-hash-registry.yaml" },
  { path: L1_CONTRACT_PATH },
  { path: L1_FEEDBACK_CONTRACT_PATH },
  { path: DESCRIPTIVE_WORKER_CONTRACT_PATH },
  { path: LEGACY_DEVELOPMENT_MANIFEST_COMPATIBILITY_PATH },
  { path: "research/governance/descriptive-worker-failure-recovery-contract-v1.json" },
  { path: "reports/audits/manifest-checkout-hash-drift.json" },
  { path: "reports/audits/manifest-checkout-hash-drift.md" },
  { prefix: "reports/audits/strategy-family-reassessment/" },
  { prefix: "reports/audits/regime-conditioned-branch-factorization/" },
  { prefix: "research/analysis/strategy-family-reassessment/" },
  { prefix: "research/analysis/regime-conditioned-branch-factorization/" },
  { prefix: "research/director/next-after-router-equivalence/" },
  { path: "research/governance/signal-mask-comparison-contract.yaml" },
  { path: "research/governance/backtest-output-namespace-contract.yaml" },
  { path: "research/governance/artifact-contamination-registry.yaml" },
  { path: "scripts/build_regime_conditioned_branch_factorization_preparation.py" },
  { path: "scripts/analyze_chan_structure_readiness.py" },
  { path: "tests/test_chan_structure_readiness.py" },
  { path: "research/analysis/chan-structure-readiness-v1/event-coverage-report.json" },
  { path: "research/analysis/chan-structure-readiness-v1/event-coverage-report.md" },
  { path: "research/candidates/chan-structure-reversal-v1/RegimeAwareChanStructureLongV1.py" },
  { path: "research/candidates/chan-structure-reversal-v1/candidate-manifest.json" },
  { path: "scripts/run_chan_structure_reversal_campaign.py" },
  { path: "tests/test_chan_structure_reversal_candidate.py" },
  { path: "research/analysis/chan-structure-reversal-v1/development-comparison.json" },
  { path: "reports/audits/chan-structure-reversal-v1/final-report.json" },
  { path: "reports/audits/chan-structure-reversal-v1/final-report.md" },
  { path: "scripts/analyze_bnb_xrp_funding_mark_stress.py" },
  { path: "tests/test_bnb_xrp_funding_mark_stress.py" },
  { path: "research/analysis/discovery-bnb-xrp-funding-mark-stress-v1-v1/analysis.json" },
  { path: "reports/audits/discovery-bnb-xrp-funding-mark-stress-v1-v1/report.md" },
  { path: "research/knowledge/schemas/open-source-source-snapshot.schema.json" },
  { path: "research/knowledge/schemas/strategy-pattern-card.schema.json" },
  { path: "research/knowledge/schemas/research-lesson-card.schema.json" },
  { path: "research/knowledge/schemas/knowledge-broker-selection.schema.json" },
  { path: "research/knowledge/schemas/research-lesson-feedback-draft.schema.json" },
  { path: "research/knowledge/schemas/knowledge-source-refresh-report.schema.json" },
  { path: "research/knowledge/schemas/knowledge-retrieval-evaluation.schema.json" },
  { path: "research/knowledge/schemas/research-learning-loop-health.schema.json" },
  { path: "research/knowledge/schemas/knowledge-review-packet.schema.json" },
  { path: "research/knowledge/schemas/knowledge-review-event.schema.json" },
  { path: "research/knowledge/schemas/knowledge-review-recommendations.schema.json" },
  { path: "research/knowledge/schemas/knowledge-review-batch-approval.schema.json" },
  { path: "research/knowledge/schemas/knowledge-review-batch-handoff.schema.json" },
  { path: "research/knowledge/schemas/knowledge-review-human-intent.schema.json" },
  { path: "research/knowledge/schemas/knowledge-review-post-approval-plan.schema.json" },
  { path: "research/knowledge/schemas/research-lesson-curation-draft-packet.schema.json" },
  { path: "research/knowledge/schemas/research-lesson-promotion-human-intent.schema.json" },
  { path: "research/knowledge/schemas/research-lesson-curation-candidate.schema.json" },
  { path: "research/knowledge/schemas/research-lesson-promotion-packet.schema.json" },
  { path: "research/knowledge/schemas/research-lesson-promotion-approval.schema.json" },
  { path: "research/knowledge/schemas/knowledge-result-feedback-backfill-packet.schema.json" },
  { path: "research/knowledge/schemas/knowledge-result-feedback-backfill-intent.schema.json" },
  { path: "research/knowledge/schemas/knowledge-result-feedback-backfill-approval.schema.json" },
  { path: "research/knowledge/evaluation/retrieval-cases-v1.json" },
  { path: "research/knowledge/prompts/knowledge-review-advisor-v1.md" },
  { path: "research/knowledge/prompts/lesson-curation-draft-advisor-v1.md" },
  { path: "scripts/open_source_knowledge.py" },
  { path: "scripts/research_knowledge_maintenance.py" },
  { path: "scripts/research_knowledge_review.py" },
  { path: "scripts/research_knowledge_advisory.py" },
  { path: "scripts/research_knowledge_batcher.py" },
  { path: "scripts/research_knowledge_batch_apply.py" },
  { path: "scripts/research_knowledge_post_review.py" },
  { path: "scripts/research_knowledge_curation_draft.py" },
  { path: "scripts/research_knowledge_candidate_compiler.py" },
  { path: "scripts/research_knowledge_promotion_apply.py" },
  { path: "scripts/research_knowledge_feedback_backfill.py" },
  { path: "tests/test_open_source_knowledge.py" },
  { path: "tests/test_research_knowledge_maintenance.py" },
  { path: "tests/test_research_knowledge_review.py" },
  { path: "tests/test_research_knowledge_advisory.py" },
  { path: "tests/test_research_knowledge_batcher.py" },
  { path: "tests/test_research_knowledge_batch_apply.py" },
  { path: "tests/test_research_knowledge_feedback_backfill.py" },
  { path: "tests/test_research_learning_loop.py" },
  { path: "tests/test_low_risk_descriptive_auto_execution.py" },
  { path: "tests/test_research_supervisor_ledger.py" },
  { path: "tests/test_research_review_sla.py" },
  { path: "tests/test_research_lesson_curation.py" },
  { path: "tests/test_research_lesson_promotion.py" },
  { path: "scripts/research_worker_queue.py" },
  { path: "scripts/research_descriptive_worker.py" },
  { path: "scripts/research_worker_supervisor.py" },
  { path: "scripts/research_supervisor_ledger.py" },
  { path: "scripts/research_review_sla.py" },
  { path: "scripts/research_worker_recovery.py" },
  { path: "scripts/research_lesson_feedback.py" },
  { path: "scripts/research_lesson_curation.py" },
  { path: "scripts/research_lesson_promotion.py" },
  { path: "scripts/research_registry_backup.py" },
  { path: "tests/test_research_registry_backup.py" },
  { path: "scripts/research_control_migration_manifest.py" },
  { path: "tests/test_research_control_migration_manifest.py" },
  { path: "research/governance/research-registry-backup-policy-v1.json" },
  { path: "docs/research_registry_backup_ubuntu.md" },
  { path: "scripts/render_additional_pair_discovery_round.py" },
  { path: "scripts/render_bnb_xrp_descriptive_discovery_round.py" },
  { path: "research/analysis/discovery-additional-pair-manifest-inventory-v1-v2/analysis.json" },
  { path: "research/analysis/discovery-bnb-xrp-distribution-shift-profile-v1-v1/analysis.json" },
  { path: "research/analysis/research-lifecycle-state-consistency-audit-v1/analysis.json" },
  { path: "scripts/provision_additional_pair_development_data.py" },
  { path: "tests/test_additional_pair_development_provisioning.py" },
  { path: "research/data/snapshots/futures-dev-bnb-usdt-usdt-20240101-20240830-v1/manifest.yaml" },
  { path: "research/data/snapshots/futures-dev-xrp-usdt-usdt-20240101-20240830-v1/manifest.yaml" },
  { path: "research/knowledge/open-source-v1/manifest.json" },
  { path: "research/knowledge/open-source-v1/current-context.json" },
  { path: "research/knowledge/open-source-v1/sources/freqtrade-strategies.json" },
  { path: "research/knowledge/open-source-v1/sources/jesse.json" },
  { path: "research/knowledge/open-source-v1/sources/qlib.json" },
  { path: "research/knowledge/open-source-v1/sources/lean.json" },
  { path: "research/knowledge/open-source-v1/sources/nautilus-trader.json" },
  { path: "research/knowledge/open-source-v1/sources/hummingbot.json" },
  { path: "research/knowledge/open-source-v1/patterns/causal-indicator-validation.json" },
  { path: "research/knowledge/open-source-v1/patterns/multi-timeframe-regime-gating.json" },
  { path: "research/knowledge/open-source-v1/patterns/explicit-order-intent.json" },
  { path: "research/knowledge/open-source-v1/patterns/multi-symbol-timeframe-composition.json" },
  { path: "research/knowledge/open-source-v1/patterns/cross-sectional-factor-ranking.json" },
  { path: "research/knowledge/open-source-v1/patterns/walk-forward-concept-drift.json" },
  { path: "research/knowledge/open-source-v1/patterns/portfolio-risk-model-separation.json" },
  { path: "research/knowledge/open-source-v1/patterns/scheduled-universe-rebalance.json" },
  { path: "research/knowledge/open-source-v1/patterns/deterministic-research-live-parity.json" },
  { path: "research/knowledge/open-source-v1/patterns/realistic-fill-order-state.json" },
  { path: "research/knowledge/open-source-v1/patterns/inventory-aware-market-making.json" },
  { path: "research/knowledge/open-source-v1/patterns/funding-basis-arbitrage.json" },
  { path: "research/knowledge/open-source-v1/lessons/chan-confirmed-higher-low-direct-entry-v1.json" },
  { path: "research/knowledge/open-source-v1/lessons/cross-pair-reproducibility-not-generalization-v1.json" },
  { path: "research/knowledge/open-source-v1/lessons/exit-frequency-insufficient-causal-evidence-v1.json" },
  { path: "research/knowledge/open-source-v1/lessons/ranging-short-temporal-retention-v1.json" },
  { path: "research/knowledge/open-source-v1/lessons/regime-directionality-rotation-no-threshold-search-v1.json" },
  { path: "research/knowledge/open-source-v1/lessons/semantic-equivalence-current-artifact-binding-v1.json" },
  { path: "research/knowledge/open-source-v1/lessons/strategy-family-baseline-single-structure-hypothesis-v1.json" },
  { path: "research/knowledge/open-source-v1/lessons/candidate-module-cache-shadowing-v1.json" },
  { path: "research/knowledge/open-source-v1/lessons/single-threshold-ranging-search-exhausted-v1.json" },
  { path: "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-cross-pair-reproducibility-not-generalization-v1.json" },
  { path: "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-exit-frequency-insufficient-causal-evidence-v1.json" },
  { path: "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-ranging-short-temporal-retention-v1.json" },
  { path: "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-regime-directionality-rotation-no-threshold-search-v1.json" },
  { path: "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-semantic-equivalence-current-artifact-binding-v1.json" },
  { path: "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/candidates/lesson-candidate-strategy-family-baseline-single-structure-hypothesis-v1.json" },
  { path: "research/knowledge/curation/open-source-learning-v1-review-batch-20260719/promotion-review-packet.json" },
  { path: "research/governance/approvals/open-source-learning-v1-lesson-promotion-20260720.json" },
  { path: "reports/audits/open-source-learning-v1/final-report.json" },
  { path: "reports/audits/open-source-learning-v1/final-report.md" },
  { path: "reports/audits/open-source-learning-v1/lesson-curation-report.md" },
  { path: "reports/audits/open-source-learning-v1/lesson-promotion-report.md" },
  { path: "reports/audits/open-source-learning-v1/source-refresh-report.json" },
  { path: "reports/audits/open-source-learning-v1/retrieval-evaluation.json" },
  { path: "reports/audits/open-source-learning-v1/learning-loop-health.json" },
  { path: "reports/audits/open-source-learning-v1/result-feedback-backfill/knowledge-result-feedback-backfill-0f7eaa76bf8d7093/packet.json" },
  { path: "reports/audits/open-source-learning-v1/result-feedback-backfill/knowledge-result-feedback-backfill-0f7eaa76bf8d7093/human-intent.json" },
  { path: "reports/audits/open-source-learning-v1/result-feedback-backfill/knowledge-result-feedback-backfill-0f7eaa76bf8d7093/approval.json" },
  { path: "reports/audits/open-source-learning-v1/result-feedback-backfill/knowledge-result-feedback-backfill-0f7eaa76bf8d7093/registration-events.json" },
  { path: "reports/audits/open-source-learning-v1/pending-review-packet.json" },
  { path: "reports/audits/open-source-learning-v1/review-recommendations.json" },
  { path: "reports/audits/open-source-learning-v1/review-recommendations.md" },
  { path: "research/governance/approvals/open-source-learning-v1-review-batch-20260719.json" },
  { path: "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719/packet.json" },
  { path: "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719/recommendations.json" },
  { path: "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719/batch-approval.json" },
  { path: "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719/review-events.json" },
  { path: "reports/audits/open-source-learning-v1/promotion-batches/open-source-learning-v1-lesson-promotion-20260720/packet.json" },
  { path: "reports/audits/open-source-learning-v1/promotion-batches/open-source-learning-v1-lesson-promotion-20260720/approval.json" },
  { path: "reports/audits/open-source-learning-v1/promotion-batches/open-source-learning-v1-lesson-promotion-20260720/review-events.json" },
  { path: "reports/audits/task189_open_source_knowledge_guard_exception.md" },
  { path: "scripts/backtest_execution_namespace.py" },
  { path: "scripts/run_router_extraction_semantic_equivalence_campaign.py" },
  { path: "scripts/run_strategy_family_reassessment_campaign.py" },
  { path: "tests/test_signal_mask_comparison_contract.py" },
  { path: "tests/test_backtest_execution_namespace.py" },
  { path: "tests/test_router_extraction_recertification_attempt3.py" },
  { path: "tests/test_branch_contribution_ablation_preparation.py" },
  { path: "tests/test_branch_contribution_ablation_compilation.py" },
  { path: "tests/test_regime_conditioned_branch_factorization_preparation.py" },
  { path: "tests/test_strategy_family_reassessment_campaign.py" },
  { path: "tests/test_dataset_snapshot_sealing.py" },
  { path: "tests/test_exchange_snapshot.py" },
  { path: "tests/test_exchange_endpoint_doctor.py" },
  { path: "tests/test_sealed_exchange_factory.py" },
  { path: "tests/test_offline_backtest_runner.py" },
  { path: "tests/test_stage3a5_acceptance.py" },
  { path: "tests/test_stage3b1_candidate_lifecycle.py" },
  { path: "tests/test_stage3b2_single_variable.py" },
  { path: "tests/test_stage3c1_data_plane.py" },
  { path: "tests/test_stage3c2_candidate_evaluator.py" },
  { path: "tests/test_stage3c2p_provisioning.py" },
  { path: "tests/test_stage3c2r_readiness.py" },
  { path: "tests/test_stage3c3_balanced_gate.py" },
  { path: "tests/test_stage3d1_bounded_search.py" },
  { path: "tests/test_stage3d2a_signal_reachability.py" },
  { path: "scripts/run_stage3d2b_reachability_search.py" },
  { path: "tests/test_stage3d2b_reachability_search.py" },
  { path: "scripts/analyze_signal_to_trade_attribution.py" },
  { path: "tests/test_stage3d3a_signal_to_trade_attribution.py" },
  { path: "scripts/audit_candidate_runtime_identity.py" },
  { path: "scripts/run_isolated_candidate_backtest.py" },
  { path: "scripts/run_stage3d3b_recertification.py" },
  { path: "tests/test_stage3d3b_process_isolation_recertification.py" },
  { path: "scripts/analyze_duplicate_signal_mechanisms.py" },
  { path: "tests/test_stage3d4a_duplicate_signal_mechanisms.py" },
  { path: "tests/test_exchange_metadata_fingerprint.py" },
  { path: "tests/test_strategy_market_contract.py" },
  { path: "scripts/run_agent_readiness_checks.sh" },
  { path: "scripts/run_agent_readiness_checks.ps1" },
];

function failTool(message, detail) {
  console.error(`guard_harness_diff: tool/config error: ${message}`);
  if (detail) {
    console.error(detail);
  }
  process.exit(EXIT_TOOL_ERROR);
}

function git(args, cwd) {
  try {
    return execFileSync("git", ["-c", "core.quotepath=false", ...args], {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (error) {
    const stderr = error.stderr ? String(error.stderr).trim() : "";
    const stdout = error.stdout ? String(error.stdout).trim() : "";
    failTool(`git ${args.join(" ")} failed`, stderr || stdout || error.message);
  }
}

function repoRoot() {
  return git(["rev-parse", "--show-toplevel"], process.cwd()).trim();
}

function normalizePath(value, root) {
  let normalized = String(value || "").trim().replace(/\\/g, "/");
  if (!normalized) {
    return "";
  }
  const normalizedRoot = root.replace(/\\/g, "/").replace(/\/+$/, "");
  if (normalized.toLowerCase().startsWith(`${normalizedRoot.toLowerCase()}/`)) {
    normalized = normalized.slice(normalizedRoot.length + 1);
  }
  return normalized.replace(/^\.\/+/, "").replace(/\/+$/, "");
}

function splitPathList(output, root) {
  return output
    .split(/\r?\n/)
    .map((line) => normalizePath(line, root))
    .filter(Boolean);
}

function collectChangedPaths(root) {
  const argPaths = process.argv.slice(2).filter((arg) => arg !== "--");
  if (argPaths.length > 0) {
    return [...new Set(argPaths.map((arg) => normalizePath(arg, root)).filter(Boolean))].sort();
  }

  if (process.env.GUARD_DIFF_FILES) {
    return [
      ...new Set(
        process.env.GUARD_DIFF_FILES
          .split(/[\r\n,]+/)
          .map((entry) => normalizePath(entry, root))
          .filter(Boolean),
      ),
    ].sort();
  }

  if (process.env.GUARD_DIFF_BASE) {
    const output = git(
      ["diff", "--name-only", "--diff-filter=ACDMRTUXB", `${process.env.GUARD_DIFF_BASE}...HEAD`],
      root,
    );
    return [...new Set(splitPathList(output, root))].sort();
  }

  const outputs = [
    git(["diff", "--name-only", "--diff-filter=ACDMRTUXB"], root),
    git(["diff", "--cached", "--name-only", "--diff-filter=ACDMRTUXB"], root),
    git(["ls-files", "--others", "--exclude-standard"], root),
  ];
  return [...new Set(outputs.flatMap((output) => splitPathList(output, root)))].sort();
}

function highRiskReason(repoPath) {
  if (EXACT_TRADE_MONITOR_EXCEPTIONS.has(repoPath)) {
    return null;
  }

  if (EXACT_HIGH_RISK_SHADOW_EXCEPTIONS.has(repoPath)) {
    return null;
  }

  if (EXACT_FRONTEND_V1_EXCEPTIONS.has(repoPath)) {
    return null;
  }

  if (EXACT_PAPER_LANE_RECOVERY_EXCEPTIONS.has(repoPath)) {
    return null;
  }

  for (const surface of HIGH_RISK_SURFACES) {
    if (surface.path && repoPath === surface.path) {
      return surface.reason;
    }
    if (surface.prefix && repoPath.startsWith(surface.prefix)) {
      return surface.reason;
    }
  }
  return null;
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function recursivelySorted(value) {
  if (Array.isArray(value)) {
    return value.map((item) => recursivelySorted(item));
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, recursivelySorted(value[key])]),
    );
  }
  return value;
}

function prettyJson(value) {
  return `${JSON.stringify(recursivelySorted(value), null, 2)}\n`;
}

function sha256Bytes(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function exactAutoAuthorizedArtifacts(root) {
  const authorized = new Set();
  const contractPath = path.join(root, L1_CONTRACT_PATH);
  const contractApprovalPath = path.join(root, L1_CONTRACT_APPROVAL_PATH);
  const constitutionPath = path.join(root, "research/governance/research-constitution.yaml");
  const proposalsRoot = path.join(root, "research/director/discovery-handoff/proposals");
  if (!fs.existsSync(contractPath) || !fs.existsSync(contractApprovalPath) || !fs.existsSync(constitutionPath) || !fs.existsSync(proposalsRoot)) {
    return authorized;
  }
  let contract;
  let contractApproval;
  try {
    contract = JSON.parse(fs.readFileSync(contractPath, "utf8"));
    contractApproval = JSON.parse(fs.readFileSync(contractApprovalPath, "utf8"));
  } catch (_error) {
    return authorized;
  }
  const contractSha256 = sha256Bytes(fs.readFileSync(contractPath));
  const constitutionSha256 = sha256Bytes(fs.readFileSync(constitutionPath));
  if (
    contract.schema_version !== "low-risk-development-descriptive-execution-contract-v1"
    || contract.status !== "active"
    || contract.approval_authority !== L1_CONTRACT_APPROVAL_PATH
    || contractApproval.approval_status !== "approved"
    || contractApproval.approver_type !== "human_user"
    || contractApproval.approval_id !== contract.contract_id
    || contractApproval.approved_contract_path !== L1_CONTRACT_PATH
    || contractApproval.approved_contract_sha256 !== contractSha256
    || contractApproval.campaign_execution_authorized !== false
    || contractApproval.trading_execution_authorized !== false
    || contractApproval.strategy_mutation_authorized !== false
    || contractApproval.candidate_creation_authorized !== false
    || contractApproval.validation_accesses_authorized !== 0
    || contractApproval.holdout_accesses_authorized !== 0
    || contractApproval.silent_contract_amendment_allowed !== false
    || contract.authority?.approved_constitution_sha256 !== constitutionSha256
    || contract.artifact_contract?.exact_paths_only !== true
    || contract.execution_semantics?.campaign_execution_authorized !== false
    || contract.execution_semantics?.trading_execution_authorized !== false
    || contract.execution_semantics?.strategy_mutation_authorized !== false
  ) {
    return authorized;
  }
  for (const entry of fs.readdirSync(proposalsRoot, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".json")) {
      continue;
    }
    let run;
    try {
      run = JSON.parse(fs.readFileSync(path.join(proposalsRoot, entry.name), "utf8"));
    } catch (_error) {
      continue;
    }
    for (const proposal of Array.isArray(run.proposals) ? run.proposals : []) {
      const proposalId = proposal?.proposal_id;
      if (typeof proposalId !== "string" || !/^[a-z0-9][a-z0-9-]+$/.test(proposalId)) {
        continue;
      }
      const exactArtifacts = [
        `research/analysis/${proposalId}/analysis.json`,
        `reports/audits/${proposalId}/report.md`,
      ];
      const authorization = proposal.descriptive_execution_authorization;
      if (!authorization || typeof authorization !== "object") {
        continue;
      }
      const fingerprintPayload = { ...authorization };
      delete fingerprintPayload.authorization_fingerprint;
      const authorizationFingerprint = sha256Bytes(Buffer.from(canonicalJson(fingerprintPayload), "utf8"));
      if (
        proposal.risk_class !== "low"
        || proposal.execution_authorized !== false
        || proposal.descriptive_execution_authorized !== true
        || proposal.approval_requirement !== "auto_approved_under_constitution"
        || JSON.stringify(proposal.allowed_changes) !== JSON.stringify(exactArtifacts)
        || JSON.stringify(proposal.required_artifacts) !== JSON.stringify(exactArtifacts)
        || authorization.authorization_mode !== "standing_l1_development_descriptive_contract"
        || authorization.contract_sha256 !== contractSha256
        || authorization.descriptive_execution_authorized !== true
        || authorization.campaign_execution_authorized !== false
        || authorization.trading_execution_authorized !== false
        || authorization.strategy_mutation_authorized !== false
        || JSON.stringify(authorization.exact_artifact_paths) !== JSON.stringify(exactArtifacts)
        || authorization.authorization_fingerprint !== authorizationFingerprint
      ) {
        continue;
      }
      for (const artifact of exactArtifacts) {
        authorized.add(artifact);
      }
    }
  }
  return authorized;
}

function exactKnowledgeReviewBatchArtifacts(root) {
  const authorized = new Set();
  const policyFile = path.join(root, KNOWLEDGE_REVIEW_BATCH_POLICY_PATH);
  const outputRoot = path.join(root, KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT);
  if (!fs.existsSync(policyFile) || !fs.existsSync(outputRoot)) {
    return authorized;
  }
  let policy;
  try {
    policy = JSON.parse(fs.readFileSync(policyFile, "utf8"));
  } catch (_error) {
    return authorized;
  }
  const policyPayload = { ...policy };
  delete policyPayload.policy_fingerprint;
  if (
    policy.schema_version !== "knowledge-review-batch-policy-v1"
    || policy.status !== "active"
    || policy.output_root !== KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT
    || policy.advisory_drafting_authorized !== true
    || policy.automatic_decision_authorized !== false
    || policy.automatic_application_authorized !== false
    || policy.automatic_lesson_promotion_authorized !== false
    || policy.execution_authorized !== false
    || policy.policy_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(policyPayload), "utf8"))
  ) {
    return authorized;
  }
  for (const entry of fs.readdirSync(outputRoot, { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^knowledge-review-batch-[a-f0-9]{16}$/.test(entry.name)) {
      continue;
    }
    const packetRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/packet.json`;
    const handoffRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/handoff.json`;
    const advisoryRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/recommendations.json`;
    const intentRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/human-intent.json`;
    const approvalRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/batch-approval.json`;
    const eventsRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/review-events.json`;
    const postPlanRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/post-approval-plan.json`;
    const curationDraftRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/curation-draft-packet.json`;
    const candidateRootRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/lesson-candidates`;
    const promotionPacketRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/promotion-review-packet.json`;
    const promotionBaseContextRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/promotion-base-context.json`;
    const promotionBaseManifestRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/promotion-base-manifest.json`;
    const promotionHumanIntentRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/promotion-human-intent.json`;
    const promotionApprovalRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/promotion-approval.json`;
    const promotionEventsRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/promotion-events.json`;
    const publishedManifestRepoPath = `${KNOWLEDGE_REVIEW_BATCH_OUTPUT_ROOT}/${entry.name}/published-knowledge-manifest.json`;
    const packetFile = path.join(root, packetRepoPath);
    const handoffFile = path.join(root, handoffRepoPath);
    if (!fs.existsSync(packetFile) || !fs.existsSync(handoffFile)) {
      continue;
    }
    let packet;
    let handoff;
    try {
      packet = JSON.parse(fs.readFileSync(packetFile, "utf8"));
      handoff = JSON.parse(fs.readFileSync(handoffFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const packetPayload = { ...packet };
    delete packetPayload.packet_fingerprint;
    const handoffPayload = { ...handoff };
    delete handoffPayload.handoff_fingerprint;
    const identity = {
      packet_fingerprint: packet.packet_fingerprint,
      policy_fingerprint: policy.policy_fingerprint,
      trigger_reason: handoff.trigger_reason,
    };
    const expectedBatchId = `knowledge-review-batch-${sha256Bytes(Buffer.from(canonicalJson(identity), "utf8")).slice(0, 16)}`;
    if (
      handoff.schema_version !== "knowledge-review-batch-handoff-v1"
      || handoff.batch_id !== entry.name
      || handoff.batch_id !== expectedBatchId
      || handoff.policy_path !== KNOWLEDGE_REVIEW_BATCH_POLICY_PATH
      || handoff.policy_fingerprint !== policy.policy_fingerprint
      || handoff.packet_path !== packetRepoPath
      || handoff.packet_fingerprint !== packet.packet_fingerprint
      || handoff.planned_advisory_path !== advisoryRepoPath
      || handoff.planned_human_intent_path !== intentRepoPath
      || handoff.planned_approval_path !== approvalRepoPath
      || handoff.planned_review_events_path !== eventsRepoPath
      || handoff.planned_post_approval_plan_path !== postPlanRepoPath
      || handoff.planned_curation_draft_path !== curationDraftRepoPath
      || handoff.planned_curation_candidate_root !== candidateRootRepoPath
      || handoff.planned_promotion_review_packet_path !== promotionPacketRepoPath
      || handoff.planned_promotion_base_context_path !== promotionBaseContextRepoPath
      || handoff.planned_promotion_base_manifest_path !== promotionBaseManifestRepoPath
      || handoff.planned_promotion_human_intent_path !== promotionHumanIntentRepoPath
      || handoff.planned_promotion_approval_path !== promotionApprovalRepoPath
      || handoff.planned_promotion_events_path !== promotionEventsRepoPath
      || handoff.planned_published_manifest_path !== publishedManifestRepoPath
      || handoff.human_decision_required !== true
      || handoff.advisory_drafting_authorized !== true
      || handoff.automatic_decision_authorized !== false
      || handoff.automatic_application_authorized !== false
      || handoff.automatic_lesson_promotion_authorized !== false
      || handoff.execution_authorized !== false
      || handoff.handoff_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(handoffPayload), "utf8"))
      || packet.schema_version !== "knowledge-review-packet-v1"
      || packet.execution_authorized !== false
      || packet.decision_contract?.reviewer_type !== "human_user"
      || packet.decision_contract?.automatic_promotion_authorized !== false
      || !Array.isArray(packet.items)
      || packet.items.length < 1
      || packet.items.some((item) => item.automatic_application_authorized !== false)
      || packet.packet_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(packetPayload), "utf8"))
    ) {
      continue;
    }
    authorized.add(packetRepoPath);
    authorized.add(handoffRepoPath);
    const advisoryFile = path.join(root, advisoryRepoPath);
    if (!fs.existsSync(advisoryFile)) {
      continue;
    }
    let advisory;
    try {
      advisory = JSON.parse(fs.readFileSync(advisoryFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const advisoryPayload = { ...advisory };
    delete advisoryPayload.advisory_fingerprint;
    const packetItems = new Map(packet.items.map((item) => [item.review_key, item]));
    const recommendations = Array.isArray(advisory.recommendations) ? advisory.recommendations : [];
    const uniqueKeys = new Set(recommendations.map((item) => item.review_key));
    const approved = recommendations.filter((item) => item.recommended_decision === "approved").length;
    const rejected = recommendations.filter((item) => item.recommended_decision === "rejected").length;
    const referencesAreBound = recommendations.every((recommendation) => {
      const packetItem = packetItems.get(recommendation.review_key);
      return packetItem
        && packetItem.review_type === recommendation.review_type
        && packetItem.target_id === recommendation.target_id
        && ["approved", "rejected"].includes(recommendation.recommended_decision)
        && Array.isArray(recommendation.references)
        && recommendation.references.length > 0
        && recommendation.references.every((reference) => {
          if (typeof reference !== "string" || /^https?:\/\//.test(reference) || !packetItem.evidence.includes(reference)) {
            return false;
          }
          const evidencePath = path.resolve(root, reference);
          const relative = path.relative(root, evidencePath);
          return !relative.startsWith("..") && !path.isAbsolute(relative) && fs.existsSync(evidencePath) && fs.statSync(evidencePath).isFile();
        });
    });
    if (
      advisory.schema_version !== "knowledge-review-recommendations-v1"
      || advisory.advisory_id !== `knowledge-review-advisory-${packet.packet_fingerprint.slice(0, 16)}`
      || advisory.generated_at !== packet.generated_at
      || advisory.packet_fingerprint !== packet.packet_fingerprint
      || advisory.human_decision_required !== true
      || advisory.automatic_application_authorized !== false
      || advisory.execution_authorized !== false
      || recommendations.length !== packet.items.length
      || uniqueKeys.size !== recommendations.length
      || [...uniqueKeys].some((key) => !packetItems.has(key))
      || !referencesAreBound
      || advisory.summary?.approved !== approved
      || advisory.summary?.rejected !== rejected
      || advisory.summary?.total !== recommendations.length
      || advisory.advisory_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(advisoryPayload), "utf8"))
    ) {
      continue;
    }
    authorized.add(advisoryRepoPath);
    const intentFile = path.join(root, intentRepoPath);
    if (!fs.existsSync(intentFile)) {
      continue;
    }
    let intent;
    try {
      intent = JSON.parse(fs.readFileSync(intentFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const intentPayload = { ...intent };
    delete intentPayload.intent_fingerprint;
    const intentIdentity = { ...intentPayload };
    delete intentIdentity.schema_version;
    delete intentIdentity.intent_id;
    const expectedIntentId = `knowledge-review-human-intent-${sha256Bytes(Buffer.from(canonicalJson(intentIdentity), "utf8")).slice(0, 16)}`;
    if (
      intent.schema_version !== "knowledge-review-human-intent-v1"
      || intent.intent_id !== expectedIntentId
      || intent.batch_id !== entry.name
      || intent.reviewer_type !== "human_user"
      || typeof intent.reviewer_id !== "string" || intent.reviewer_id.length < 1
      || intent.decision !== "approve_recommendations"
      || typeof intent.statement !== "string" || intent.statement.length < 1
      || typeof intent.decided_at !== "string" || intent.decided_at.length < 1
      || intent.authorization_source !== "explicit_user_instruction"
      || intent.packet_fingerprint !== packet.packet_fingerprint
      || intent.advisory_fingerprint !== advisory.advisory_fingerprint
      || intent.approved_count !== approved
      || intent.rejected_count !== rejected
      || intent.review_event_application_authorized !== true
      || intent.automatic_source_update_authorized !== false
      || intent.automatic_lesson_promotion_authorized !== false
      || intent.execution_authorized !== false
      || intent.intent_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(intentPayload), "utf8"))
    ) {
      continue;
    }
    authorized.add(intentRepoPath);
    const approvalFile = path.join(root, approvalRepoPath);
    if (!fs.existsSync(approvalFile)) {
      continue;
    }
    let approval;
    try {
      approval = JSON.parse(fs.readFileSync(approvalFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const approvalPayload = { ...approval };
    delete approvalPayload.approval_fingerprint;
    if (
      approval.schema_version !== "knowledge-review-batch-approval-v1"
      || approval.approval_id !== `knowledge-review-approval-${intent.intent_fingerprint.slice(0, 16)}`
      || approval.reviewer_type !== intent.reviewer_type
      || approval.reviewer_id !== intent.reviewer_id
      || approval.decision !== intent.decision
      || approval.statement !== intent.statement
      || approval.decided_at !== intent.decided_at
      || approval.packet_fingerprint !== packet.packet_fingerprint
      || approval.advisory_fingerprint !== advisory.advisory_fingerprint
      || approval.approved_count !== approved
      || approval.rejected_count !== rejected
      || approval.automatic_source_update_authorized !== false
      || approval.automatic_lesson_promotion_authorized !== false
      || approval.execution_authorized !== false
      || approval.approval_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(approvalPayload), "utf8"))
    ) {
      continue;
    }
    authorized.add(approvalRepoPath);
    const eventsFile = path.join(root, eventsRepoPath);
    if (!fs.existsSync(eventsFile)) {
      continue;
    }
    let eventsPayload;
    try {
      eventsPayload = JSON.parse(fs.readFileSync(eventsFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const events = Array.isArray(eventsPayload.events) ? eventsPayload.events : [];
    const eventsMatch = events.length === recommendations.length && events.every((event, index) => {
      const recommendation = recommendations[index];
      const eventIntent = {
        review_type: recommendation.review_type,
        target_id: recommendation.target_id,
        decision: recommendation.recommended_decision,
        reviewer_type: approval.reviewer_type,
        reviewer_id: approval.reviewer_id,
        reason: `accepted_advisory:${advisory.advisory_id}:${recommendation.disposition}`,
        decided_at: approval.decided_at,
        source_packet_fingerprint: packet.packet_fingerprint,
      };
      const expectedEventId = `knowledge-review-${sha256Bytes(Buffer.from(canonicalJson(eventIntent), "utf8")).slice(0, 16)}`;
      const eventPayload = { ...event };
      delete eventPayload.event_fingerprint;
      return event.schema_version === "knowledge-review-event-v1"
        && event.review_event_id === expectedEventId
        && Object.entries(eventIntent).every(([key, value]) => event[key] === value)
        && event.automatic_source_update_authorized === false
        && event.automatic_lesson_promotion_authorized === false
        && event.execution_authorized === false
        && event.event_fingerprint === sha256Bytes(Buffer.from(canonicalJson(eventPayload), "utf8"));
    });
    if (eventsPayload.execution_authorized !== false || !eventsMatch) {
      continue;
    }
    authorized.add(eventsRepoPath);
    const postPlanFile = path.join(root, postPlanRepoPath);
    if (!fs.existsSync(postPlanFile)) {
      continue;
    }
    let postPlan;
    try {
      postPlan = JSON.parse(fs.readFileSync(postPlanFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const expectedActions = recommendations.map((recommendation, index) => {
      const event = events[index];
      const packetItem = packetItems.get(recommendation.review_key);
      let resultingStatus;
      let actionType;
      let workflowOwner;
      let humanRequired;
      if (event.decision === "rejected") {
        resultingStatus = event.review_type === "license_review" ? "deprecated" : "rejected";
        actionType = "closed_no_follow_up";
        workflowOwner = "none";
        humanRequired = false;
      } else if (event.review_type === "lesson_feedback") {
        resultingStatus = "approved_for_manual_curation";
        actionType = "prepare_non_authoritative_lesson_curation_draft";
        workflowOwner = "knowledge_curator";
        humanRequired = false;
      } else if (event.review_type === "source_update") {
        resultingStatus = "approved_for_manual_rebuild";
        actionType = "manual_source_snapshot_rebuild";
        workflowOwner = "human_source_maintainer";
        humanRequired = true;
      } else {
        resultingStatus = "active_pinned";
        actionType = "manual_source_metadata_rebuild";
        workflowOwner = "human_source_maintainer";
        humanRequired = true;
      }
      return {
        review_key: recommendation.review_key,
        review_event_id: event.review_event_id,
        review_type: event.review_type,
        target_id: event.target_id,
        decision: event.decision,
        resulting_status: resultingStatus,
        action_type: actionType,
        workflow_owner: workflowOwner,
        evidence: packetItem.evidence,
        manual_action_required: humanRequired,
        automatic_execution_authorized: false,
      };
    });
    const planIdentity = {
      batch_id: entry.name,
      approval_fingerprint: approval.approval_fingerprint,
      review_event_fingerprints: events.map((event) => event.event_fingerprint),
    };
    const planId = `knowledge-post-approval-plan-${sha256Bytes(Buffer.from(canonicalJson(planIdentity), "utf8")).slice(0, 16)}`;
    const expectedPlanPayload = {
      schema_version: "knowledge-review-post-approval-plan-v1",
      plan_id: planId,
      generated_at: approval.decided_at,
      batch_id: entry.name,
      packet_fingerprint: packet.packet_fingerprint,
      advisory_fingerprint: advisory.advisory_fingerprint,
      approval_fingerprint: approval.approval_fingerprint,
      actions: expectedActions,
      summary: {
        lesson_curation_drafts: expectedActions.filter((item) => item.action_type === "prepare_non_authoritative_lesson_curation_draft").length,
        source_snapshot_rebuilds: expectedActions.filter((item) => item.action_type === "manual_source_snapshot_rebuild").length,
        source_metadata_rebuilds: expectedActions.filter((item) => item.action_type === "manual_source_metadata_rebuild").length,
        closed: expectedActions.filter((item) => item.action_type === "closed_no_follow_up").length,
        total: expectedActions.length,
      },
      automatic_candidate_creation_authorized: false,
      curation_drafting_authorized: true,
      automatic_source_rebuild_authorized: false,
      automatic_lesson_promotion_authorized: false,
      execution_authorized: false,
    };
    const postPlanPayload = { ...postPlan };
    delete postPlanPayload.plan_fingerprint;
    if (
      canonicalJson(postPlanPayload) !== canonicalJson(expectedPlanPayload)
      || postPlan.plan_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(postPlanPayload), "utf8"))
    ) {
      continue;
    }
    authorized.add(postPlanRepoPath);
    const curationDraftFile = path.join(root, curationDraftRepoPath);
    if (!fs.existsSync(curationDraftFile)) {
      continue;
    }
    let curationDraft;
    let currentContext;
    try {
      curationDraft = JSON.parse(fs.readFileSync(curationDraftFile, "utf8"));
      const baseContextFile = path.join(root, promotionBaseContextRepoPath);
      currentContext = JSON.parse(fs.readFileSync(
        fs.existsSync(baseContextFile)
          ? baseContextFile
          : path.join(root, "research/knowledge/open-source-v1/current-context.json"),
        "utf8",
      ));
    } catch (_error) {
      continue;
    }
    const eligibleActions = new Map(
      expectedActions
        .filter((item) => item.action_type === "prepare_non_authoritative_lesson_curation_draft")
        .map((item) => [item.target_id, item]),
    );
    const eligibleFeedback = [...eligibleActions.keys()].sort();
    const formalLessonIds = new Set((currentContext.lessons || []).map((item) => item.lesson_id));
    const drafts = Array.isArray(curationDraft.drafts) ? curationDraft.drafts : [];
    const coveredFeedback = [];
    const proposedLessonIds = new Set();
    const allowedOutcomes = new Set([
      "rejected_degradation", "negative_contributor", "invalidated_engineering",
      "closed_evidence_exhausted", "retained", "descriptive_not_generalized",
      "insufficient_causal_evidence", "verified_engineering", "structural_no_mutation",
      "research_direction_retained",
    ]);
    const draftsValid = drafts.length > 0 && drafts.every((draft) => {
      const draftPayload = { ...draft };
      delete draftPayload.draft_fingerprint;
      const sourceIds = Array.isArray(draft.source_feedback_ids) ? draft.source_feedback_ids : [];
      const eventIds = Array.isArray(draft.source_review_event_ids) ? draft.source_review_event_ids : [];
      const evidencePaths = Array.isArray(draft.evidence_paths) ? draft.evidence_paths : [];
      const supersedes = Array.isArray(draft.supersedes_lesson_ids) ? draft.supersedes_lesson_ids : [];
      if (
        !/^lesson-curation-draft-[a-z0-9-]+$/.test(draft.draft_id || "")
        || sourceIds.length < 1
        || canonicalJson(sourceIds) !== canonicalJson([...sourceIds].sort())
        || new Set(sourceIds).size !== sourceIds.length
        || sourceIds.some((item) => !eligibleActions.has(item))
      ) {
        return false;
      }
      const expectedEventIds = sourceIds.map((item) => eligibleActions.get(item).review_event_id).sort();
      const allowedEvidence = new Set(sourceIds.flatMap((item) => eligibleActions.get(item).evidence));
      const evidenceValid = evidencePaths.length > 0
        && canonicalJson(evidencePaths) === canonicalJson([...evidencePaths].sort())
        && new Set(evidencePaths).size === evidencePaths.length
        && evidencePaths.every((reference) => {
          if (/^https?:\/\//.test(reference) || !allowedEvidence.has(reference)) {
            return false;
          }
          const evidencePath = path.resolve(root, reference);
          const relative = path.relative(root, evidencePath);
          return !relative.startsWith("..") && !path.isAbsolute(relative) && fs.existsSync(evidencePath) && fs.statSync(evidencePath).isFile();
        });
      const card = draft.proposed_card || {};
      const cardPayload = { ...card };
      delete cardPayload.lesson_fingerprint;
      const mechanismKeys = Array.isArray(card.mechanism_keys) ? card.mechanism_keys : [];
      const cardValid = card.schema_version === "research-lesson-card-v1"
        && /^[a-z0-9][a-z0-9-]+$/.test(card.lesson_id || "")
        && typeof card.title_zh === "string" && card.title_zh.length > 0
        && allowedOutcomes.has(card.outcome)
        && mechanismKeys.length > 0 && new Set(mechanismKeys).size === mechanismKeys.length
        && mechanismKeys.every((item) => /^[a-z0-9][a-z0-9-]+$/.test(item))
        && card.scope && typeof card.scope === "object" && !Array.isArray(card.scope) && Object.keys(card.scope).length > 0
        && typeof card.summary_zh === "string" && card.summary_zh.length > 0
        && canonicalJson(card.evidence_paths) === canonicalJson(evidencePaths)
        && card.source_class === "A"
        && ["block_semantic_duplicate", "warn_and_require_material_difference", "require_recertification"].includes(card.reuse_policy)
        && card.validation_accesses === 0
        && card.holdout_accesses === 0
        && card.lesson_fingerprint === sha256Bytes(Buffer.from(canonicalJson(cardPayload), "utf8"));
      const replacementValid = draft.merge_disposition === "replace_existing_lesson"
        ? supersedes.length > 0 && supersedes.every((item) => formalLessonIds.has(item))
        : supersedes.length === 0 && !formalLessonIds.has(card.lesson_id);
      if (
        canonicalJson(eventIds) !== canonicalJson(expectedEventIds)
        || !evidenceValid
        || !cardValid
        || proposedLessonIds.has(card.lesson_id)
        || !["standalone", "merged_feedback", "replace_existing_lesson"].includes(draft.merge_disposition)
        || !replacementValid
        || typeof draft.material_difference_zh !== "string" || draft.material_difference_zh.length < 1
        || draft.automatic_candidate_registration_authorized !== false
        || draft.automatic_promotion_authorized !== false
        || draft.draft_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(draftPayload), "utf8"))
      ) {
        return false;
      }
      proposedLessonIds.add(card.lesson_id);
      coveredFeedback.push(...sourceIds);
      return true;
    });
    const expectedCoverage = {
      eligible_feedback_ids: eligibleFeedback,
      covered_feedback_ids: eligibleFeedback,
      uncovered_feedback_ids: [],
      duplicate_feedback_merged: eligibleFeedback.length - drafts.length,
    };
    const curationDraftPayload = { ...curationDraft };
    delete curationDraftPayload.draft_packet_fingerprint;
    if (
      !draftsValid
      || canonicalJson([...coveredFeedback].sort()) !== canonicalJson(eligibleFeedback)
      || new Set(coveredFeedback).size !== coveredFeedback.length
      || curationDraft.schema_version !== "research-lesson-curation-draft-packet-v1"
      || curationDraft.draft_packet_id !== `knowledge-curation-draft-${postPlan.plan_fingerprint.slice(0, 16)}`
      || curationDraft.generated_at !== postPlan.generated_at
      || curationDraft.batch_id !== entry.name
      || curationDraft.post_approval_plan_fingerprint !== postPlan.plan_fingerprint
      || curationDraft.knowledge_snapshot_fingerprint !== currentContext.knowledge_snapshot_fingerprint
      || canonicalJson(curationDraft.coverage) !== canonicalJson(expectedCoverage)
      || curationDraft.human_promotion_review_required !== true
      || curationDraft.automatic_candidate_registration_authorized !== false
      || curationDraft.automatic_promotion_authorized !== false
      || curationDraft.execution_authorized !== false
      || curationDraft.draft_packet_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(curationDraftPayload), "utf8"))
    ) {
      continue;
    }
    authorized.add(curationDraftRepoPath);
    const promotionBaseContextFile = path.join(root, promotionBaseContextRepoPath);
    const promotionBaseManifestFile = path.join(root, promotionBaseManifestRepoPath);
    if (!fs.existsSync(promotionBaseContextFile) || !fs.existsSync(promotionBaseManifestFile)) {
      continue;
    }
    let promotionBaseManifest;
    try {
      promotionBaseManifest = JSON.parse(fs.readFileSync(promotionBaseManifestFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const baseContextPayload = { ...currentContext };
    delete baseContextPayload.context_fingerprint;
    const baseManifestPayload = { ...promotionBaseManifest };
    delete baseManifestPayload.manifest_fingerprint;
    const baseSnapshotFingerprint = sha256Bytes(Buffer.from(canonicalJson({ assets: promotionBaseManifest.assets }), "utf8"));
    if (
      currentContext.context_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(baseContextPayload), "utf8"))
      || currentContext.knowledge_snapshot_fingerprint !== baseSnapshotFingerprint
      || curationDraft.knowledge_snapshot_fingerprint !== baseSnapshotFingerprint
      || promotionBaseManifest.knowledge_snapshot_fingerprint !== baseSnapshotFingerprint
      || promotionBaseManifest.context_path !== "research/knowledge/open-source-v1/current-context.json"
      || promotionBaseManifest.context_sha256 !== sha256Bytes(Buffer.from(prettyJson(currentContext), "utf8"))
      || promotionBaseManifest.counts?.sources !== currentContext.sources.length
      || promotionBaseManifest.counts?.patterns !== currentContext.patterns.length
      || promotionBaseManifest.counts?.lessons !== currentContext.lessons.length
      || promotionBaseManifest.manifest_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(baseManifestPayload), "utf8"))
    ) {
      continue;
    }
    authorized.add(promotionBaseContextRepoPath);
    authorized.add(promotionBaseManifestRepoPath);
    const compiledCandidates = [...drafts]
      .sort((left, right) => left.proposed_card.lesson_id.localeCompare(right.proposed_card.lesson_id))
      .map((draft) => {
        const candidate = {
          schema_version: "research-lesson-curation-candidate-v1",
          candidate_id: `lesson-candidate-${draft.proposed_card.lesson_id}`,
          status: "pending_human_promotion_review",
          source_feedback_ids: draft.source_feedback_ids,
          merge_disposition: draft.merge_disposition,
          supersedes_lesson_ids: draft.supersedes_lesson_ids,
          material_difference_zh: draft.material_difference_zh,
          proposed_card: draft.proposed_card,
          automatic_promotion_authorized: false,
        };
        candidate.candidate_fingerprint = sha256Bytes(Buffer.from(canonicalJson(candidate), "utf8"));
        return candidate;
      });
    const candidateRefs = compiledCandidates.map((candidate) => ({
      candidate_id: candidate.candidate_id,
      proposed_lesson_id: candidate.proposed_card.lesson_id,
      path: `${candidateRootRepoPath}/${candidate.candidate_id}.json`,
      candidate_fingerprint: candidate.candidate_fingerprint,
      source_feedback_ids: candidate.source_feedback_ids,
      supersedes_lesson_ids: candidate.supersedes_lesson_ids,
    }));
    const promotionPacketPayload = {
      schema_version: "research-lesson-promotion-packet-v1",
      packet_id: `knowledge-lesson-promotion-review-${curationDraft.draft_packet_fingerprint.slice(0, 16)}`,
      generated_at: curationDraft.generated_at,
      source_review_batch: entry.name,
      knowledge_snapshot_fingerprint: currentContext.knowledge_snapshot_fingerprint,
      approved_feedback_count: eligibleFeedback.length,
      candidate_count: compiledCandidates.length,
      formal_lesson_count_before: currentContext.lessons.length,
      candidates: candidateRefs,
      coverage: {
        approved_feedback_ids: eligibleFeedback,
        covered_feedback_ids: curationDraft.coverage.covered_feedback_ids,
        uncovered_feedback_ids: [],
        duplicate_feedback_merged: curationDraft.coverage.duplicate_feedback_merged,
      },
      human_approval_required: true,
      automatic_promotion_authorized: false,
      execution_authorized: false,
    };
    const expectedPromotionPacket = {
      ...promotionPacketPayload,
      packet_fingerprint: sha256Bytes(Buffer.from(canonicalJson(promotionPacketPayload), "utf8")),
    };
    const promotionPacketFile = path.join(root, promotionPacketRepoPath);
    const candidateFilesExist = candidateRefs.every((reference) => fs.existsSync(path.join(root, reference.path)));
    if (!promotionPacketFile || !fs.existsSync(promotionPacketFile) || !candidateFilesExist) {
      continue;
    }
    let actualPromotionPacket;
    try {
      actualPromotionPacket = JSON.parse(fs.readFileSync(promotionPacketFile, "utf8"));
    } catch (_error) {
      continue;
    }
    if (canonicalJson(actualPromotionPacket) !== canonicalJson(expectedPromotionPacket)) {
      continue;
    }
    let candidatesValid = true;
    for (const candidate of compiledCandidates) {
      const candidateRepoPath = `${candidateRootRepoPath}/${candidate.candidate_id}.json`;
      let actualCandidate;
      try {
        actualCandidate = JSON.parse(fs.readFileSync(path.join(root, candidateRepoPath), "utf8"));
      } catch (_error) {
        candidatesValid = false;
        break;
      }
      if (canonicalJson(actualCandidate) !== canonicalJson(candidate)) {
        candidatesValid = false;
        break;
      }
      authorized.add(candidateRepoPath);
    }
    if (!candidatesValid) {
      for (const reference of candidateRefs) {
        authorized.delete(reference.path);
      }
      continue;
    }
    authorized.add(promotionPacketRepoPath);
    const promotionHumanIntentFile = path.join(root, promotionHumanIntentRepoPath);
    if (!fs.existsSync(promotionHumanIntentFile)) {
      continue;
    }
    let promotionIntent;
    try {
      promotionIntent = JSON.parse(fs.readFileSync(promotionHumanIntentFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const promotionDecisions = Array.isArray(promotionIntent.decisions) ? promotionIntent.decisions : [];
    const promotionDecisionMap = new Map(promotionDecisions.map((item) => [item.candidate_id, item]));
    const promotionIntentPayload = { ...promotionIntent };
    delete promotionIntentPayload.intent_fingerprint;
    const promotionIntentIdentity = { ...promotionIntentPayload };
    delete promotionIntentIdentity.schema_version;
    delete promotionIntentIdentity.intent_id;
    const promotionApproved = promotionDecisions.filter((item) => item.decision === "approved").length;
    const promotionRejected = promotionDecisions.filter((item) => item.decision === "rejected").length;
    const promotionDecisionsValid = promotionDecisions.length === compiledCandidates.length
      && promotionDecisionMap.size === compiledCandidates.length
      && compiledCandidates.every((candidate) => {
        const decision = promotionDecisionMap.get(candidate.candidate_id);
        return decision
          && decision.candidate_fingerprint === candidate.candidate_fingerprint
          && ["approved", "rejected"].includes(decision.decision);
      });
    if (
      promotionIntent.schema_version !== "research-lesson-promotion-human-intent-v1"
      || promotionIntent.intent_id !== `lesson-promotion-human-intent-${sha256Bytes(Buffer.from(canonicalJson(promotionIntentIdentity), "utf8")).slice(0, 16)}`
      || promotionIntent.batch_id !== entry.name
      || promotionIntent.reviewer_type !== "human_user"
      || typeof promotionIntent.reviewer_id !== "string" || promotionIntent.reviewer_id.length < 1
      || typeof promotionIntent.statement !== "string" || promotionIntent.statement.length < 1
      || typeof promotionIntent.decided_at !== "string" || promotionIntent.decided_at.length < 1
      || promotionIntent.authorization_source !== "explicit_user_instruction"
      || promotionIntent.packet_fingerprint !== expectedPromotionPacket.packet_fingerprint
      || !promotionDecisionsValid
      || promotionIntent.approved_count !== promotionApproved
      || promotionIntent.rejected_count !== promotionRejected
      || promotionIntent.knowledge_candidate_registration_authorized !== true
      || promotionIntent.formal_knowledge_publication_authorized !== true
      || promotionIntent.lesson_promotion_application_authorized !== true
      || promotionIntent.strategy_mutation_authorized !== false
      || promotionIntent.trading_execution_authorized !== false
      || promotionIntent.intent_fingerprint !== sha256Bytes(Buffer.from(canonicalJson(promotionIntentPayload), "utf8"))
    ) {
      continue;
    }
    authorized.add(promotionHumanIntentRepoPath);
    const promotionApprovalFile = path.join(root, promotionApprovalRepoPath);
    if (!fs.existsSync(promotionApprovalFile)) {
      continue;
    }
    let promotionApproval;
    try {
      promotionApproval = JSON.parse(fs.readFileSync(promotionApprovalFile, "utf8"));
    } catch (_error) {
      continue;
    }
    const promotionApprovalPayload = {
      schema_version: "research-lesson-promotion-approval-v1",
      approval_id: `lesson-promotion-approval-${promotionIntent.intent_fingerprint.slice(0, 16)}`,
      reviewer_type: promotionIntent.reviewer_type,
      reviewer_id: promotionIntent.reviewer_id,
      statement: promotionIntent.statement,
      decided_at: promotionIntent.decided_at,
      packet_fingerprint: expectedPromotionPacket.packet_fingerprint,
      decisions: promotionIntent.decisions,
      approved_count: promotionApproved,
      rejected_count: promotionRejected,
      automatic_lesson_promotion_authorized: false,
      trading_execution_authorized: false,
    };
    const expectedPromotionApproval = {
      ...promotionApprovalPayload,
      approval_fingerprint: sha256Bytes(Buffer.from(canonicalJson(promotionApprovalPayload), "utf8")),
    };
    if (canonicalJson(promotionApproval) !== canonicalJson(expectedPromotionApproval)) {
      continue;
    }
    authorized.add(promotionApprovalRepoPath);
    const expectedPromotionEvents = promotionIntent.decisions.map((decision) => {
      const eventIdentity = {
        review_type: "lesson_promotion",
        target_id: decision.candidate_id,
        decision: decision.decision,
        reviewer_id: promotionIntent.reviewer_id,
        source_packet_fingerprint: expectedPromotionPacket.packet_fingerprint,
      };
      const eventPayload = {
        schema_version: "knowledge-review-event-v1",
        review_event_id: `knowledge-review-${sha256Bytes(Buffer.from(canonicalJson(eventIdentity), "utf8")).slice(0, 16)}`,
        ...eventIdentity,
        reviewer_type: "human_user",
        reason: `accepted_human_promotion_batch:${expectedPromotionApproval.approval_id}`,
        decided_at: promotionIntent.decided_at,
        automatic_source_update_authorized: false,
        automatic_lesson_promotion_authorized: false,
        execution_authorized: false,
      };
      return {
        ...eventPayload,
        event_fingerprint: sha256Bytes(Buffer.from(canonicalJson(eventPayload), "utf8")),
      };
    });
    const promotionEventsFile = path.join(root, promotionEventsRepoPath);
    if (!fs.existsSync(promotionEventsFile)) {
      continue;
    }
    let actualPromotionEvents;
    try {
      actualPromotionEvents = JSON.parse(fs.readFileSync(promotionEventsFile, "utf8"));
    } catch (_error) {
      continue;
    }
    if (canonicalJson(actualPromotionEvents) !== canonicalJson({ events: expectedPromotionEvents, execution_authorized: false })) {
      continue;
    }
    authorized.add(promotionEventsRepoPath);
    const targetLessonsById = new Map(currentContext.lessons.map((item) => [item.lesson_id, item]));
    const supersededLessonIds = new Set();
    for (const candidate of compiledCandidates) {
      if (promotionDecisionMap.get(candidate.candidate_id).decision !== "approved") {
        continue;
      }
      for (const lessonId of candidate.supersedes_lesson_ids) {
        supersededLessonIds.add(lessonId);
        targetLessonsById.delete(lessonId);
      }
      if (targetLessonsById.has(candidate.proposed_card.lesson_id)) {
        targetLessonsById.clear();
        break;
      }
      targetLessonsById.set(candidate.proposed_card.lesson_id, candidate.proposed_card);
    }
    if (targetLessonsById.size === 0) {
      continue;
    }
    const targetLessons = [...targetLessonsById.values()].sort((left, right) => left.lesson_id.localeCompare(right.lesson_id));
    const targetAssets = [];
    const baseAssetsByPath = new Map(promotionBaseManifest.assets.map((item) => [item.path, item]));
    const basePayloadsByPath = new Map();
    for (const [items, idField, folder] of [
      [currentContext.sources, "project_id", "sources"],
      [currentContext.patterns, "pattern_id", "patterns"],
      [currentContext.lessons, "lesson_id", "lessons"],
    ]) {
      for (const item of items) {
        basePayloadsByPath.set(`research/knowledge/open-source-v1/${folder}/${item[idField]}.json`, item);
      }
    }
    for (const [kind, items, idField, folder] of [
      ["source", currentContext.sources, "project_id", "sources"],
      ["pattern", currentContext.patterns, "pattern_id", "patterns"],
      ["lesson", targetLessons, "lesson_id", "lessons"],
    ]) {
      for (const item of items) {
        const assetPath = `research/knowledge/open-source-v1/${folder}/${item[idField]}.json`;
        const baseAsset = baseAssetsByPath.get(assetPath);
        const basePayload = basePayloadsByPath.get(assetPath);
        targetAssets.push({
          kind,
          path: assetPath,
          sha256: baseAsset && canonicalJson(basePayload) === canonicalJson(item)
            ? baseAsset.sha256
            : sha256Bytes(Buffer.from(prettyJson(item), "utf8")),
        });
      }
    }
    targetAssets.sort((left, right) => left.path.localeCompare(right.path));
    const targetSnapshotFingerprint = sha256Bytes(Buffer.from(canonicalJson({ assets: targetAssets }), "utf8"));
    const targetContextPayload = { ...currentContext };
    delete targetContextPayload.knowledge_snapshot_fingerprint;
    delete targetContextPayload.lessons;
    delete targetContextPayload.context_fingerprint;
    targetContextPayload.knowledge_snapshot_fingerprint = targetSnapshotFingerprint;
    targetContextPayload.lessons = targetLessons;
    const expectedTargetContext = {
      ...targetContextPayload,
      context_fingerprint: sha256Bytes(Buffer.from(canonicalJson(targetContextPayload), "utf8")),
    };
    const targetManifestPayload = { ...promotionBaseManifest };
    for (const key of ["generated_at", "knowledge_snapshot_fingerprint", "counts", "assets", "context_sha256", "manifest_fingerprint"]) {
      delete targetManifestPayload[key];
    }
    targetManifestPayload.generated_at = promotionIntent.decided_at;
    targetManifestPayload.knowledge_snapshot_fingerprint = targetSnapshotFingerprint;
    targetManifestPayload.counts = {
      sources: currentContext.sources.length,
      patterns: currentContext.patterns.length,
      lessons: targetLessons.length,
    };
    targetManifestPayload.assets = targetAssets;
    targetManifestPayload.context_sha256 = sha256Bytes(Buffer.from(prettyJson(expectedTargetContext), "utf8"));
    const expectedTargetManifest = {
      ...targetManifestPayload,
      manifest_fingerprint: sha256Bytes(Buffer.from(canonicalJson(targetManifestPayload), "utf8")),
    };
    const publishedManifestFile = path.join(root, publishedManifestRepoPath);
    if (!fs.existsSync(publishedManifestFile)) {
      continue;
    }
    let actualPublishedManifest;
    try {
      actualPublishedManifest = JSON.parse(fs.readFileSync(publishedManifestFile, "utf8"));
    } catch (_error) {
      continue;
    }
    if (canonicalJson(actualPublishedManifest) !== canonicalJson(expectedTargetManifest)) {
      continue;
    }
    authorized.add(publishedManifestRepoPath);
    for (const candidate of compiledCandidates) {
      if (promotionDecisionMap.get(candidate.candidate_id).decision !== "approved") {
        continue;
      }
      const formalLessonPath = `research/knowledge/open-source-v1/lessons/${candidate.proposed_card.lesson_id}.json`;
      const formalLessonFile = path.join(root, formalLessonPath);
      if (fs.existsSync(formalLessonFile)) {
        try {
          if (canonicalJson(JSON.parse(fs.readFileSync(formalLessonFile, "utf8"))) === canonicalJson(candidate.proposed_card)) {
            authorized.add(formalLessonPath);
          }
        } catch (_error) {
          // Keep the path unauthorized.
        }
      }
      for (const lessonId of candidate.supersedes_lesson_ids) {
        authorized.add(`research/knowledge/open-source-v1/lessons/${lessonId}.json`);
      }
    }
    const formalContextPath = "research/knowledge/open-source-v1/current-context.json";
    const formalManifestPath = "research/knowledge/open-source-v1/manifest.json";
    try {
      if (canonicalJson(JSON.parse(fs.readFileSync(path.join(root, formalContextPath), "utf8"))) === canonicalJson(expectedTargetContext)) {
        authorized.add(formalContextPath);
      }
      if (canonicalJson(JSON.parse(fs.readFileSync(path.join(root, formalManifestPath), "utf8"))) === canonicalJson(expectedTargetManifest)) {
        authorized.add(formalManifestPath);
      }
    } catch (_error) {
      // Keep formal snapshot paths unauthorized.
    }
  }
  return authorized;
}

function isLowRiskSurface(repoPath, autoAuthorizedArtifacts = new Set()) {
  if (EXACT_FRONTEND_V1_EXCEPTIONS.has(repoPath)) {
    return true;
  }

  if (EXACT_HIGH_RISK_SHADOW_EXCEPTIONS.has(repoPath)) {
    return true;
  }

  if (EXACT_PAPER_LANE_RECOVERY_EXCEPTIONS.has(repoPath)) {
    return true;
  }

  if (autoAuthorizedArtifacts.has(repoPath)) {
    return true;
  }

  return LOW_RISK_SURFACES.some((surface) => {
    if (surface.exact && repoPath === surface.exact) {
      return true;
    }
    if (surface.path && repoPath === surface.path) {
      return true;
    }
    if (surface.prefix && repoPath.startsWith(surface.prefix)) {
      return true;
    }
    return Boolean(surface.regex && surface.regex.test(repoPath));
  });
}

function surfaceReason(repoPath) {
  return highRiskReason(repoPath) || "path is not an authorized low-risk harness/documentation surface";
}

function main() {
  const root = repoRoot();
  if (!fs.existsSync(path.join(root, ".git")) && !fs.existsSync(path.join(root, ".git", "HEAD"))) {
    failTool("current directory is not a git worktree");
  }

  const changedPaths = collectChangedPaths(root);
  const autoAuthorizedArtifacts = exactAutoAuthorizedArtifacts(root);
  for (const artifact of exactKnowledgeReviewBatchArtifacts(root)) {
    autoAuthorizedArtifacts.add(artifact);
  }
  const blocked = changedPaths
    .filter((repoPath) => highRiskReason(repoPath) || !isLowRiskSurface(repoPath, autoAuthorizedArtifacts))
    .map((repoPath) => ({ path: repoPath, reason: surfaceReason(repoPath) }));

  if (blocked.length > 0) {
    console.error("guard_harness_diff: blocked high-risk diff");
    for (const item of blocked) {
      console.error(`- ${item.path}: ${item.reason}`);
    }
    process.exit(EXIT_BLOCKED);
  }

  console.log(`guard_harness_diff: pass (${changedPaths.length} changed path(s) checked)`);
  process.exit(EXIT_PASS);
}

main();
