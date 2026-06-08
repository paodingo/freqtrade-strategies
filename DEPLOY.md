# 部署与运维文档

本文档涵盖从零搭建、部署、监控到维护的完整流程。

---

## 目录

1. [项目概览](#1-项目概览)
2. [本地开发环境](#2-本地开发环境)
3. [服务器部署](#3-服务器部署)
4. [监控与查看](#4-监控与查看)
5. [回测新策略](#5-回测新策略)
6. [策略更新部署](#6-策略更新部署)
7. [日常维护](#7-日常维护)
8. [故障排查](#8-故障排查)
9. [文件结构参考](#9-文件结构参考)

---

## 1. 项目概览

### 仓库

```
https://github.com/paodingo/freqtrade-strategies
```

### 当前运行

| 项目 | 值 |
|------|-----|
| 策略 | RegimeAwareV6 |
| 交易对 | BTC/USDT:USDT（永续合约） |
| 模式 | 模拟盘（dry_run），$10,000 虚拟资金 |
| 每笔投入 | $200 USDT，最多 2 笔同时持仓 |
| 服务器 | 腾讯云新加坡 43.134.72.69 |
| 运行方式 | Docker 容器，`--restart unless-stopped` |

### 版本历史

```
V1 → V2 → V3 → V4 → V5 → V6  ← 当前线上
                         V7  (实验)
                         V8  (实验)
                         V9  (实验)
```

---

## 2. 本地开发环境

### 前提

- Windows / macOS / Linux
- Docker Desktop 已安装

### 克隆项目

```bash
git clone https://github.com/paodingo/freqtrade-strategies.git
cd freqtrade-strategies
```

### 拉取 freqtrade 镜像

```bash
docker pull freqtradeorg/freqtrade:stable
```

### 下载历史数据

```bash
docker run --rm \
  -v "$(pwd):/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "BTC/USDT:USDT" \
  --timeframes 1h 4h \
  --timerange 20240101- \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  -d /freqtrade/project/user_data/data \
  --trading-mode futures
```

### 本地运行（可选）

如果不想在本地跑模拟盘，可以跳过这步只在服务器上跑。

```bash
# 启动
docker run -d \
  --name freqtrade-local \
  -p 8080:8080 \
  -v "$(pwd):/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data

# 通过 API 启动 bot（容器启动后默认是 STOPPED 状态）
curl -s -X POST http://localhost:8080/api/v1/start \
  -u freqtrader:freqtrade

# 停止 & 删除
docker stop freqtrade-local && docker rm freqtrade-local
```

---

## 3. 服务器部署

### SSH 连接

```bash
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69
```

> Windows 上用 PowerShell 执行，macOS/Linux 去掉 `-i` 前的盘符。

### 初次部署（服务器从零开始）

```bash
# 1. 确认 Docker 已安装
docker --version

# 2. 拉代码
git clone https://github.com/paodingo/freqtrade-strategies.git ~/freqtrade-strategies
cd ~/freqtrade-strategies

# 3. 拉镜像 & 下载数据
docker pull freqtradeorg/freqtrade:stable

docker run --rm \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "BTC/USDT:USDT" \
  --timeframes 1h 4h \
  --timerange 20240101- \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  -d /freqtrade/project/user_data/data \
  --trading-mode futures

# 4. 启动 bot
docker run -d \
  --name freqtrade-v6 \
  --restart unless-stopped \
  -p 8080:8080 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data

# 5. 等待容器启动（~8秒），然后通过 API 启动 bot
sleep 8
curl -s -X POST http://localhost:8080/api/v1/start \
  -u freqtrader:freqtrade
```

### 设置定时数据刷新（Cron）

```bash
crontab -e

# 添加这两行（每 6 小时刷新一次）：
0 */6 * * * docker run --rm -v /home/ubuntu/freqtrade-strategies:/freqtrade/project freqtradeorg/freqtrade:stable download-data --exchange binance --pairs "BTC/USDT:USDT" --timeframes 1h 4h --timerange 20240101- --config /freqtrade/project/user_data/config_btc_futures.json -d /freqtrade/project/user_data/data --trading-mode futures >> /var/log/freqtrade-cron.log 2>&1
```

---

## 4. 监控与查看

### 查看 bot 运行状态

```bash
# 容器是否在跑
docker ps --filter "name=freqtrade-v6"

# 最近日志（实时）
docker logs -f freqtrade-v6

# 查看最近 50 行
docker logs --tail 50 freqtrade-v6
```

### 查看交易活动

```bash
# 看有没有买卖信号
docker logs freqtrade-v6 | grep -i "enter\|exit\|signal\|trade"

# 看有没有出错
docker logs freqtrade-v6 | grep -i "ERROR\|WARNING"

# 看 4h 数据是否正常加载
docker logs freqtrade-v6 | grep "4h"
```

### 通过 API 查看状态

```bash
# bot 状态
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/status

# 当前持仓
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/trades

# 盈亏统计
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/profit

# 余额
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/balance

# 强制买入（用于测试，慎用）
# curl -s -X POST http://localhost:8080/api/v1/forcebuy \
#   -H "Content-Type: application/json" \
#   -d '{"pair": "BTC/USDT:USDT"}' \
#   -u freqtrader:freqtrade
```

### 服务器健康检查

```bash
# 磁盘空间
df -h /

# 内存
free -h

# 容器资源占用
docker stats --no-stream freqtrade-v6
```

---

## 5. 回测新策略

### 命令行回测

```bash
# 在项目目录下执行
docker run --rm \
  -v "$(pwd):/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  backtesting \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data \
  --timerange 20240101-20260608
```

> 替换 `RegimeAwareV6` 为你想要测试的策略名（如 `RegimeAwareV9`）。

### 回测输出解读

```
Result for strategy RegimeAwareV6
┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃    Pair    ┃ Trades ┃ Tot Profit % ┃   Drawdown   ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
┃ BTC/USDT   ┃    223 ┃      0.74%  ┃      0.44%   ┃
└────────────┴────────┴──────────────┴──────────────┘
```

关键指标：
- **Tot Profit %**：总收益率。正值 = 赚钱
- **Drawdown**：最大回撤。越小越好
- **Win%**：胜率。>50% 正常
- **Sharpe**：夏普比率。正值 = 风险调整后正收益

---

## 6. 策略更新部署

### 标准更新流程（推送新策略到服务器）

```bash
# 1. 在本地修改代码，提交 & 推送
cd /path/to/freqtrade-strategies
# ... 修改 strategies/RegimeAwareV6.py 或创建新策略 ...
git add -A
git commit -m "描述你的改动"
git push origin master

# 2. SSH 到服务器，拉代码 & 重启容器
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69

cd ~/freqtrade-strategies
git pull

# 停止旧容器
docker stop freqtrade-v6 && docker rm freqtrade-v6

# 启动新容器
docker run -d \
  --name freqtrade-v6 \
  --restart unless-stopped \
  -p 8080:8080 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data

# 等容器就绪，启动 bot
sleep 8
curl -s -X POST http://localhost:8080/api/v1/start \
  -u freqtrader:freqtrade

# 确认运行
docker logs freqtrade-v6 | grep "RUNNING"
```

### 切换策略版本

如果想让 V9 代替 V6 上线：

```bash
# 修改 --strategy 参数即可
docker run -d --name freqtrade-v9 \
  --restart unless-stopped \
  -p 8080:8080 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV9 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data
```

---

## 7. 日常维护

### 每天看一眼（可选）

```bash
# 一个命令搞定
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 \
  "docker ps --filter 'name=freqtrade-v6' && echo '---' && docker logs --tail 20 freqtrade-v6 | grep -v heartbeat"
```

### 每周检查

```bash
# 查看一周内的交易
docker logs freqtrade-v6 --since 168h | grep -i "enter\|exit"

# 更新 freqtrade 镜像
docker pull freqtradeorg/freqtrade:stable

# 然后重新部署（同 6. 更新流程）
```

### 数据清理

```bash
# 如果数据文件太旧或出错，删除后重新下载
rm -rf ~/freqtrade-strategies/user_data/data/futures

# 重新下载（命令见 3. 服务器部署）
```

### 日志清理

```bash
# Docker 日志会一直增长，定期清理
docker logs --tail 1000 freqtrade-v6 > /tmp/freqtrade-backup.log
truncate -s 0 $(docker inspect --format='{{.LogPath}}' freqtrade-v6)
```

---

## 8. 故障排查

### Bot 没信号

1. **4h 数据问题**：`docker logs freqtrade-v6 | grep "4h"`
   - 看到 `4h data unavailable` → 数据没下载或路径不对
   - 解决：重新下载数据（见 7. 数据清理）

2. **行情太静**：BTC 可能在一个窄区间震荡
   - 到 Binance 上肉眼看看 BTC 是不是横盘
   - 完全正常——策略在震荡时应该空仓

3. **参数太严**：
   - 在本地跑一次回测确认策略本身能产生交易
   - 如果回测有交易但实盘没有 → 可能是 API 连接问题

### 容器崩溃

```bash
# 检查退出码
docker ps -a --filter "name=freqtrade-v6"

# 查看最后日志
docker logs --tail 100 freqtrade-v6

# 常见原因：
# exit 137 = OOM（内存不够）→ 给小服务器减 max_open_trades
# exit 1   = 配置错误 → 检查 config 文件
# exit 0   = 正常退出 → 检查最后日志
```

### API 连不上

```bash
# 确认容器在跑
docker ps --filter "name=freqtrade-v6"

# 确认端口映射
docker port freqtrade-v6

# 如果容器在跑但 API 不通，等几秒再试（bot 启动有时间）
sleep 10
curl http://localhost:8080/api/v1/ping
```

### Binance 连接问题

新加坡服务器到 Binance 通常没问题。如果看到 `Connection timeout`：

```bash
# 测试连通性
curl -s https://api.binance.com/api/v3/ping

# freqtrade 会在 WebSocket 断开时自动回退到 REST API，
# 不影响交易执行，只是延迟稍大
```

---

## 9. 文件结构参考

```
freqtrade-strategies/
├── strategies/
│   ├── __init__.py
│   ├── regime_detector.py      # 市场状态检测（趋势/震荡投票）
│   ├── risk_manager.py         # 风控模块（熔断、仓位限制）
│   ├── RegimeAware.py          # V1
│   ├── RegimeAwareV2.py        # V2
│   ├── RegimeAwareV3.py        # V3
│   ├── RegimeAwareV4.py        # V4
│   ├── RegimeAwareV5.py        # V5
│   ├── RegimeAwareV6.py        # V6 ← 当前线上
│   ├── RegimeAwareV8.py        # V8（多币种实验）
│   └── RegimeAwareV9.py        # V9（ATR 缩放实验）
├── tests/                      # 单元测试
├── user_data/
│   ├── config_btc.json         # 现货配置
│   ├── config_btc_futures.json # 合约配置 ← 当前使用
│   └── data/                   # 历史 K 线数据（不提交 git）
├── scripts/
│   ├── start_bot.sh            # 一键启动脚本
│   └── refresh_data.sh         # 数据刷新脚本
├── docs/superpowers/           # 设计文档和实现计划
├── STRATEGY_GUIDE.md           # 策略说明书（白话版）
├── DEPLOY.md                   # 本文档
└── README.md                   # 项目简介
```
