#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const EXIT_PASS = 0;
const EXIT_BLOCKED = 1;
const EXIT_TOOL_ERROR = 2;

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
  "dashboard/server.js",
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
  { prefix: "research/governance/approvals/" },
  { prefix: "research/director/" },
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
  { regex: /^scripts\/research_[^/]+\.py$/ },
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
  { path: "scripts/backtest_execution_namespace.py" },
  { path: "scripts/run_router_extraction_semantic_equivalence_campaign.py" },
  { path: "scripts/run_strategy_family_reassessment_campaign.py" },
  { path: "tests/test_signal_mask_comparison_contract.py" },
  { path: "tests/test_backtest_execution_namespace.py" },
  { path: "tests/test_router_extraction_recertification_attempt3.py" },
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

function isLowRiskSurface(repoPath) {
  if (EXACT_HIGH_RISK_SHADOW_EXCEPTIONS.has(repoPath)) {
    return true;
  }

  return LOW_RISK_SURFACES.some((surface) => {
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
  const blocked = changedPaths
    .filter((repoPath) => highRiskReason(repoPath) || !isLowRiskSurface(repoPath))
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
