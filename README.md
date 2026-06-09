# Freqtrade Strategies

基于 [freqtrade](https://github.com/freqtrade/freqtrade) 的策略实验仓库。当前重点是 BTC/USDT:USDT 合约 dry-run，对比 V6 基线和 V6.1 趋势核心版本。

## 当前策略

- `RegimeAwareV6`：当前基线策略，支持多空，保留趋势与震荡入场逻辑。
- `RegimeAwareV61`：V6.1 对比策略，保留趋势入场，关闭震荡入场，并加入轻量保护。

V6 之前的历史策略已经从主代码路径删除。V8/V9 暂保留为后续实验参考，不参与当前云端双 bot 对比。

## 常用命令

```bash
# V6 回测
freqtrade backtesting \
  --strategy RegimeAwareV6 \
  --strategy-path strategies \
  --config user_data/config_btc_futures_v6.json \
  --datadir user_data/data \
  --timerange 20240101-20260608

# V6.1 回测
freqtrade backtesting \
  --strategy RegimeAwareV61 \
  --strategy-path strategies \
  --config user_data/config_btc_futures_v61.json \
  --datadir user_data/data \
  --timerange 20240101-20260608 \
  --enable-protections
```

## 云端对比

- V6 API: `http://43.134.72.69:8080`
- V6.1 API: `http://43.134.72.69:8081`
- 两个 bot 使用独立配置和独立 dry-run SQLite 数据库。

部署与运维细节见 [DEPLOY.md](DEPLOY.md)。

## 项目结构

```text
strategies/
  RegimeAwareV6.py       # V6 基线
  RegimeAwareV61.py      # V6.1 对比策略
  RegimeAwareV8.py       # 保留实验版本
  RegimeAwareV9.py       # 保留实验版本
  regime_detector.py     # 状态识别模块
  risk_manager.py        # 风控模块
tests/                   # 单元测试
user_data/               # freqtrade 配置
scripts/                 # 云端启动、刷新、监控脚本
docs/superpowers/        # 历史设计文档和计划
```

## 风险提示

当前仍是 dry-run 对比阶段。回测和 dry-run 都不等于真实成交表现，尤其要持续观察滑点、手续费、资金费率、趋势/震荡误判和连续亏损。
