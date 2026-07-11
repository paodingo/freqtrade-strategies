# Stage 3D.3-A Freqtrade 2025.8 Execution Semantics

The audit uses the frozen local runtime source, not current online documentation.

## Verified Paths

- `IStrategy.get_entry_signal` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\strategy\interface.py:1345`: live entry collision.
- `IStrategy.get_exit_signal` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\strategy\interface.py:1312`: directional exit signal.
- `Backtesting._get_ohlcv_as_lists` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\optimize\backtesting.py:458`: one-candle signal shift.
- `Backtesting.check_for_trade_entry` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\optimize\backtesting.py:1254`: backtest long/short and entry/exit collision.
- `Backtesting.backtest_loop` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\optimize\backtesting.py:1449`: position stacking, pair lock, slot, order sequence.
- `Backtesting._enter_trade` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\optimize\backtesting.py:1066`: stake, precision, confirmation, trade creation.
- `Backtesting._get_exit_for_signal` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\optimize\backtesting.py:800`: exit pricing and confirmation.
- `Backtesting.time_pair_generator` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\optimize\backtesting.py:1563`: last candle and event ordering.
- `StrategyResolver._load_strategy` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\resolvers\strategy_resolver.py:255`: strategy path resolution.
- `IResolver._load_object` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\resolvers\iresolver.py:161`: module loading.
- `Wallets.get_trade_stake_amount` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\wallets.py:354`: wallet stake.
- `Wallets.validate_stake_amount` at `D:\code\freqtrade-strategies-clean\.venv-freqtrade\Lib\site-packages\freqtrade\wallets.py:377`: stake limits.

## Candidate Isolation Finding

- Finding: `candidate_dependency_module_cache_shadowed`
- Shadowed experiments: `[2, 3, 4, 5, 6, 7, 8, 9, 10]`
- `run_offline_backtest()` executes sequentially in-process; candidate modules have unique names but share `regime_aware_base`.
- Python retained experiment 1's shared dependency in `sys.modules`, so experiments 2-10 did not load their own mutated dependency.
- No site-package file was modified.
