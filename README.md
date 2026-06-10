# Freqtrade 策略仓库

这是一个 BTC/USDT:USDT 合约策略实验仓库。当前重点是 V6.5 震荡短线策略与 V6.6 选择性箱体边缘策略的 dry-run 对比，以及一个只读监控面板。

## 当前运行

| 对象 | 策略/服务 | 端口 | 模式 | 钱包 | 仓位 |
| --- | --- | --- | --- | --- | --- |
| V6.5 | `RegimeAwareV65` | 8081 | dry-run | 10,000 USDT | 15m 主周期，首笔 3,000，震荡短线，更快进出 |
| V6.6 | `RegimeAwareV66` | 8082 | dry-run | 10,000 USDT | 首笔 2,500，只在箱体边缘交易，箱体中部禁开 |
| 监控面板 | Node dashboard | 8090 | 只读 | 不适用 | 不适用 |

两个 bot 当前都只跑 `BTC/USDT:USDT`，并且 `max_open_trades=1`。V6.2/V6.3/V6.4 代码和配置仍保留在仓库里，作为历史回退和审计参考；当前云端主对比不再运行 V6.3。

## 策略说明

- `RegimeAwareV61`：历史对照版本，趋势入场、关闭震荡入场，并启用 Freqtrade protections。
- `RegimeAwareV62`：历史基线，在 V6.1 信号基础上支持固定额度的保守加仓。
- `RegimeAwareV63`：历史稳定基线；按账户最大亏损百分比反推加仓额度，并检查止损/强平距离、波动、冷却时间和可用余额。
- `RegimeAwareV64`：历史进攻挑战者；15m 趋势版，作为 V6.5 回退参考。
- `RegimeAwareV65`：当前进攻基线；15m 震荡短线策略，重新开启并放宽震荡入场，使用更小 ROI、更紧止损和更短超时。
- `RegimeAwareV66`：当前选择性候选；继承 V6.5，但加入 24h/48h 箱体位置过滤，只在上下沿交易，中部不追信号，并在趋势单失效为震荡后更快退出。
- `RegimeAwareV6`、`RegimeAwareV8`、`RegimeAwareV9`：历史或实验参考版本，不参与当前云端主对比。

## 常用命令

```bash
# 完整本地冒烟测试，需要 Docker 和 Node。
bash scripts/run_tests.sh

# 启动当前 V6.5 dry-run bot。
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

当前仍处于 dry-run 和观察阶段。回测和模拟盘不能证明真实成交表现。任何实盘启动前，都必须完成实盘清单、轮换 API/面板密码、关闭 Freqtrade API 公网暴露，并确认 Telegram 交易提醒可靠。
