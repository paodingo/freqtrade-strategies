# Task 11: Trading Surface Inventory

结论：本任务只读盘点了原始工作区 `D:\code\freqtrade-strategies` 的交易系统变更面。原始工作区仍保持 quarantine-only：未复制、未删除、未移动、未 stash、未 commit，未读取 secret，未启动 bot，未登录服务器，未运行回测，未修改策略或 bot 配置。

## 1. 执行基线

- clean 工作区：`D:\code\freqtrade-strategies-clean`
- clean 分支：`codex/btc-mvp-system-harnessed`
- Task 10 commit：`b892ca8 Review harness migration milestone`
- 原始工作区：`D:\code\freqtrade-strategies`
- 原始工作区分支：`codex/btc-mvp-system`
- 原始工作区 commit：`5a5d426`

前置 gate：

```text
git status --short
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

只读观察命令：

```powershell
git -C D:\code\freqtrade-strategies -c core.quotepath=false status --short --untracked-files=all -- strategies configs user_data dashboard scripts deploy
git -C D:\code\freqtrade-strategies -c core.quotepath=false diff --name-only -- strategies configs user_data dashboard scripts deploy
```

## 2. 总体变更面统计

按 Git metadata 观察到的路径数量：

| 顶层路径 | 数量 |
|---|---:|
| `strategies/**` | 80 |
| `user_data/**` | 109 |
| `scripts/**` | 49 |
| `dashboard/**` | 7 |
| `configs/**` | 1 |

tracked modified 路径集中在：

- `strategies/**`
- `dashboard/**`
- `scripts/**`

untracked 路径集中在：

- strategy candidates
- bot config candidates
- backtest/data artifacts
- report/build/run helper scripts

## 3. 策略候选清单

### Modified 策略

```text
M strategies/RegimeAwareV661AlphaRisk.py
M strategies/RegimeAwareV66AlphaRisk.py
M strategies/RegimeAwareV67AlphaRisk.py
M strategies/regime_aware_base.py
M strategies/trade_supervisor_filter.py
```

### Untracked 策略

```text
?? strategies/RegimeAwarePhase2CoreCombo.py
?? strategies/RegimeAwareV101ScoredDynamicRiskAlpha.py
?? strategies/RegimeAwareV102ReliableShortCoreAlpha.py
?? strategies/RegimeAwareV103ProfitRunnerShortCoreAlpha.py
?? strategies/RegimeAwareV104ExtendedRunnerShortCoreAlpha.py
?? strategies/RegimeAwareV105BalancedShortCoreAlpha.py
?? strategies/RegimeAwareV106QualityGatedShortCoreAlpha.py
?? strategies/RegimeAwareV107MultiPairShortCoreAlpha.py
?? strategies/RegimeAwareV1081PairTieredShortCoreAlpha.py
?? strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py
?? strategies/RegimeAwareV1083PairTieredShortCoreAlpha.py
?? strategies/RegimeAwareV108PairTieredShortCoreAlpha.py
?? strategies/RegimeAwareV109DensityTieredShortCoreAlpha.py
?? strategies/RegimeAwareV110HighAttackShortCore.py
?? strategies/RegimeAwareV1110DisableWeakPairs.py
?? strategies/RegimeAwareV1111DynamicWeakPairCooldown.py
?? strategies/RegimeAwareV1112MarketSqueezeCooldown.py
?? strategies/RegimeAwareV1113MicroReboundTrapGuard.py
?? strategies/RegimeAwareV1114ExhaustedSelloffTrapGuard.py
?? strategies/RegimeAwareV1115ExhaustedSelloffRiskSizer.py
?? strategies/RegimeAwareV1116SelectiveAltRecoverySizer.py
?? strategies/RegimeAwareV1117ResidualSmallShortPruner.py
?? strategies/RegimeAwareV1118VolatilityShockSmallShortPruner.py
?? strategies/RegimeAwareV1119TailRiskCooldown.py
?? strategies/RegimeAwareV111HighAttackFilteredShortCore.py
?? strategies/RegimeAwareV1120AdaCapitulationCooldown.py
?? strategies/RegimeAwareV1121CoreCapitulationHalfSizer.py
?? strategies/RegimeAwareV1122AdaCapitulationHalfSizer.py
?? strategies/RegimeAwareV1123ReboundChaseGuard.py
?? strategies/RegimeAwareV1124ReboundChaseSizer.py
?? strategies/RegimeAwareV1125ChopDragSizer.py
?? strategies/RegimeAwareV1126CoreRecoilMicroSizer.py
?? strategies/RegimeAwareV1127DualTrapMicroSizer.py
?? strategies/RegimeAwareV1128SelectiveDragPruner.py
?? strategies/RegimeAwareV1129ResidualDragMicroSizer.py
?? strategies/RegimeAwareV112HighAttackBreakoutCombo.py
?? strategies/RegimeAwareV113HighAttackRouterCombo.py
?? strategies/RegimeAwareV114HighAttackQualityFilteredShortCore.py
?? strategies/RegimeAwareV115CostAwareShortCore.py
?? strategies/RegimeAwareV116StableShortCore.py
?? strategies/RegimeAwareV117WindowRouterShortCore.py
?? strategies/RegimeAwareV118ShortSqueezeGuard.py
?? strategies/RegimeAwareV119ShortSqueezeHedge.py
?? strategies/RegimeAwareV68AlphaRisk.py
?? strategies/RegimeAwareV69AlphaRisk.py
?? strategies/RegimeAwareV70AlphaRisk.py
?? strategies/RegimeAwareV71AlphaRisk.py
?? strategies/RegimeAwareV72AlphaRisk.py
?? strategies/RegimeAwareV73AlphaRisk.py
?? strategies/RegimeAwareV74AlphaRisk.py
?? strategies/RegimeAwareV75AlphaRisk.py
?? strategies/RegimeAwareV76AlphaRisk.py
?? strategies/RegimeAwareV77AlphaRisk.py
?? strategies/RegimeAwareV78AlphaRisk.py
?? strategies/RegimeAwareV79AlphaRisk.py
?? strategies/RegimeAwareV80AlphaRisk.py
?? strategies/RegimeAwareV81AlphaRisk.py
?? strategies/RegimeAwareV82AlphaRisk.py
?? strategies/RegimeAwareV83AlphaRisk.py
?? strategies/RegimeAwareV84AlphaRisk.py
?? strategies/RegimeAwareV85AlphaRisk.py
?? strategies/RegimeAwareV86AlphaRisk.py
?? strategies/RegimeAwareV87AlphaRisk.py
?? strategies/RegimeAwareV88PortfolioAlphaRisk.py
?? strategies/RegimeAwareV89TightRiskAlpha.py
?? strategies/RegimeAwareV90NoRangeShortAlpha.py
?? strategies/RegimeAwareV91ShortSqueezeGuardAlpha.py
?? strategies/RegimeAwareV92ShortSqueezeSizerAlpha.py
?? strategies/RegimeAwareV93TrendShortOnlyAlpha.py
?? strategies/RegimeAwareV94ProfitRunnerAlpha.py
?? strategies/RegimeAwareV95FundingAwareSizerAlpha.py
?? strategies/RegimeAwareV96StaleSelloffSizerAlpha.py
?? strategies/RegimeAwareV97AccountRiskCapAlpha.py
?? strategies/RegimeAwareV98TieredAttackAlpha.py
?? strategies/RegimeAwareV99AttackOnlyAlpha.py
```

## 4. V10.8.2 相关路径

```text
?? strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py
?? user_data/config_multi_futures_v1082.json
```

判断：默认冻结。后续只读审查也必须单独授权，不得迁移、修改或运行。

## 5. V11.29 相关路径

```text
?? scripts/run_v1129_residual_drag_micro_sizer_backtests.sh
?? strategies/RegimeAwareV1129ResidualDragMicroSizer.py
?? user_data/config_multi_futures_v1129.json
```

判断：默认冻结。可作为后续 `V11.29 Execution Data Inventory` 的只读准备对象，但不得运行回测、修改策略、修改配置或触碰 live/server 面。

## 6. Bot 配置清单

```text
?? configs/btc_mvp/config.yaml
?? user_data/config_btc_futures_phase2.json
?? user_data/config_btc_futures_v101.json
?? user_data/config_btc_futures_v102.json
?? user_data/config_btc_futures_v103.json
?? user_data/config_btc_futures_v104.json
?? user_data/config_btc_futures_v105.json
?? user_data/config_btc_futures_v106.json
?? user_data/config_btc_futures_v67.json
?? user_data/config_btc_futures_v68.json
?? user_data/config_btc_futures_v69.json
?? user_data/config_btc_futures_v70.json
?? user_data/config_btc_futures_v71.json
?? user_data/config_btc_futures_v72.json
?? user_data/config_btc_futures_v73.json
?? user_data/config_btc_futures_v74.json
?? user_data/config_btc_futures_v75.json
?? user_data/config_btc_futures_v80.json
?? user_data/config_btc_futures_v83.json
?? user_data/config_btc_futures_v84.json
?? user_data/config_btc_futures_v85.json
?? user_data/config_btc_futures_v86.json
?? user_data/config_btc_futures_v87.json
?? user_data/config_btc_futures_v96.json
?? user_data/config_btc_futures_v97.json
?? user_data/config_btc_futures_v98.json
?? user_data/config_btc_futures_v99.json
?? user_data/config_multi_futures_v107.json
?? user_data/config_multi_futures_v108.json
?? user_data/config_multi_futures_v1081.json
?? user_data/config_multi_futures_v1082.json
?? user_data/config_multi_futures_v1083.json
?? user_data/config_multi_futures_v109.json
?? user_data/config_multi_futures_v110.json
?? user_data/config_multi_futures_v111.json
?? user_data/config_multi_futures_v1110.json
?? user_data/config_multi_futures_v1111.json
?? user_data/config_multi_futures_v1112.json
?? user_data/config_multi_futures_v1113.json
?? user_data/config_multi_futures_v1114.json
?? user_data/config_multi_futures_v1115.json
?? user_data/config_multi_futures_v1116.json
?? user_data/config_multi_futures_v1117.json
?? user_data/config_multi_futures_v1118.json
?? user_data/config_multi_futures_v1119.json
?? user_data/config_multi_futures_v112.json
?? user_data/config_multi_futures_v1120.json
?? user_data/config_multi_futures_v1121.json
?? user_data/config_multi_futures_v1122.json
?? user_data/config_multi_futures_v1123.json
?? user_data/config_multi_futures_v1124.json
?? user_data/config_multi_futures_v1125.json
?? user_data/config_multi_futures_v1126.json
?? user_data/config_multi_futures_v1127.json
?? user_data/config_multi_futures_v1128.json
?? user_data/config_multi_futures_v1129.json
?? user_data/config_multi_futures_v113.json
?? user_data/config_multi_futures_v114.json
?? user_data/config_multi_futures_v115.json
?? user_data/config_multi_futures_v116.json
?? user_data/config_multi_futures_v117.json
?? user_data/config_multi_futures_v118.json
?? user_data/config_multi_futures_v119.json
?? user_data/config_multi_futures_v88.json
```

## 7. Dry-run/live 相关配置路径

仅按路径命名分类，未读取内容：

- `configs/btc_mvp/config.yaml`
- `user_data/config_btc_futures_*.json`
- `user_data/config_multi_futures_*.json`
- `user_data/config_multi_futures_v1129.json`
- `scripts/ensure_dry_run_bots_started.sh`
- `scripts/start_bot.sh`
- `scripts/check_trades.sh`
- `scripts/refresh_data.sh`
- `scripts/check_system_health.sh`
- `scripts/record_live_readiness.js`
- `scripts/validate_live_readiness.js`
- `scripts/deploy_phase1_server.sh`

判断：这些路径必须人工确认后才能进入更深只读审查；默认不得修改、不得执行。

## 8. Dashboard / server 操作面路径

```text
M dashboard/lib/config.js
M dashboard/lib/monitor_store.js
M dashboard/lib/trade_supervisor.js
M dashboard/public/app.js
M dashboard/public/index.html
M dashboard/public/styles.css
M dashboard/server.js
?? scripts/check_system_health.sh
?? scripts/deploy_phase1_server.sh
?? scripts/record_live_readiness.js
?? scripts/record_system_health.js
?? scripts/validate_live_readiness.js
```

判断：默认冻结。不得自动修改、不得启动 server、不得登录服务器。

## 9. 可以进入后续只读审查的文件

可以进入后续只读审查，但必须另开任务、显式路径范围、仍不得修改：

- untracked 策略候选清单中的非 V10.8.2/V11.29 策略文件
- `configs/btc_mvp/config.yaml`
- `user_data/config_btc_futures_*.json`
- `user_data/config_multi_futures_*.json`
- backtest/report builder 脚本，仅限元数据和用途分类
- dashboard/server 路径，仅限路径级与 diff name 级分类

## 10. 必须人工确认的文件

必须人工确认后才能读取内容或进一步处理：

- 所有 `user_data/config*.json`
- `configs/btc_mvp/config.yaml`
- all modified tracked strategy files
- all modified dashboard files
- `scripts/start_bot.sh`
- `scripts/ensure_dry_run_bots_started.sh`
- `scripts/check_trades.sh`
- `scripts/refresh_data.sh`
- `scripts/check_system_health.sh`
- `scripts/deploy_phase1_server.sh`
- `scripts/record_live_readiness.js`
- `scripts/validate_live_readiness.js`

## 11. 默认冻结文件

默认冻结：

- `strategies/RegimeAwareV1082PairTieredShortCoreAlpha.py`
- `user_data/config_multi_futures_v1082.json`
- `scripts/run_v1129_residual_drag_micro_sizer_backtests.sh`
- `strategies/RegimeAwareV1129ResidualDragMicroSizer.py`
- `user_data/config_multi_futures_v1129.json`
- all dashboard/server paths
- all bot lifecycle scripts
- all live/server readiness/deploy scripts
- all secret-adjacent paths

## 12. 禁止 Codex 自动处理的路径

禁止自动处理：

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key、交易所凭证、服务器密钥、dashboard 密码
- V10.8.2
- V11.29
- live/server 操作面
- 原始工作区 `D:\code\freqtrade-strategies` 中的任何文件

## 13. 后续 Task 12 推荐

推荐 Task 12：`V11.29 Execution Data Inventory`。

建议目标：

- 只读盘点 V11.29 真实执行验证所需的数据面。
- 仅使用 Git metadata 和已迁移审计文档作为起点。
- 不运行 `scripts/run_v1129_residual_drag_micro_sizer_backtests.sh`。
- 不读取 secret。
- 不修改 `strategies/RegimeAwareV1129ResidualDragMicroSizer.py`。
- 不修改 `user_data/config_multi_futures_v1129.json`。
- 不登录服务器、不启动 bot、不运行回测。

## 14. Task 11 停止点

Task 11 只做交易系统变更面只读盘点，未进入 Task 12。
