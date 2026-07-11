# ADR: Candidate Python Import Isolation

Status: Accepted for Stage 3D.3-B recertification.

## Decision

Use Scheme A: each original candidate is materialized as an immutable execution package with experiment-unique module names for the strategy base, regime detector, and risk manager. Every backtest runs in a fresh Python interpreter and exits after one invocation.

## Rejected Alternative

Scheme B was not selected because shared module names plus path ordering remain vulnerable to `sys.modules` and loader-order coupling. `importlib.reload()`, partial module eviction, and reusable workers are prohibited.

## Naming

Modules use `regime_aware_base_c3d2b_eNNNN`, `regime_detector_c3d2b_eNNNN`, and `risk_manager_c3d2b_eNNNN`. Candidate class names and approved strategy semantics remain unchanged.

## Compatibility

Freqtrade 2025.8 receives the package directory as `strategy_path`; the wrapper imports only its unique base module. Runtime identity must prove source path, source hash, module origin, and AST mutation before backtesting.

## Risks And Upgrade Requirements

Packaging import rewrites are identity-only and must remain separate from semantic diffs. Freqtrade/Python upgrades require loader compatibility tests, PID isolation tests, reverse-order tests, and runtime identity recertification.
