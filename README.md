# Freqtrade 策略仓库

这是一个 BTC/USDT:USDT 合约策略实验仓库。当前重点是 V6.2 与 V6.1 的
dry-run 对比，以及一个只读监控面板。

## 当前运行

| 对象 | 策略/服务 | 端口 | 模式 | 钱包 | 仓位 |
| --- | --- | --- | --- | --- | --- |
| V6.2 | `RegimeAwareV62` | 8080 | dry-run | 10,000 USDT | 首笔 1,500，最多加到 3,500 |
| V6.1 | `RegimeAwareV61` | 8081 | dry-run | 10,000 USDT | 固定 2,500 |
| 监控面板 | Node dashboard | 8090 | 只读 | 不适用 | 不适用 |

两个 bot 当前都只跑 `BTC/USDT:USDT`，并且 `max_open_trades=1`。V6.2 已经
替代旧 V6 作为基线，但容器名仍沿用 `freqtrade-v6`，避免运维脚本大面积改名。

## 策略说明

- `RegimeAwareV61`：趋势入场版本，关闭震荡入场，并启用 Freqtrade protections。
- `RegimeAwareV62`：在 V6.1 信号基础上支持保守加仓；不会给旧小仓加仓，也不会在距离止损/强平过近或刚成交不久时加仓。
- `RegimeAwareV6`、`RegimeAwareV8`、`RegimeAwareV9`：历史或实验参考版本，不参与当前云端主对比。

## 常用命令

```bash
# 完整本地冒烟测试，需要 Docker 和 Node。
bash scripts/run_tests.sh

# 启动当前 V6.2 dry-run bot。
bash scripts/start_bot.sh

# 刷新行情数据并检查两个 dry-run bot API。
bash scripts/refresh_data.sh

# 有持仓变化时输出 TRADE_ALERT 行，供 OpenClaw/Telegram 转发。
bash scripts/check_trades.sh
```

## 文档

- 部署和运维：[DEPLOY.md](DEPLOY.md)
- 实盘准备：[LIVE_TRADING.md](LIVE_TRADING.md)
- 策略说明：[STRATEGY_GUIDE.md](STRATEGY_GUIDE.md)

## 风险状态

当前仍处于 dry-run 和观察阶段。回测和模拟盘不能证明真实成交表现。任何实盘启动前，
都必须完成实盘清单、轮换 API/面板密码、关闭 Freqtrade API 公网暴露，并确认 Telegram
交易提醒可靠。
