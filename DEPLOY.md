# 部署与运维文档

---

## 目录

1. [项目概览](#1-项目概览)
2. [远程部署（服务器）](#2-远程部署服务器)
3. [本地开发环境](#3-本地开发环境)
4. [从本地推代码到服务器](#4-从本地推代码到服务器)
5. [回测新策略](#5-回测新策略)
6. [监控与查看](#6-监控与查看)
7. [日常维护](#7-日常维护)
8. [故障排查](#8-故障排查)
9. [文件结构参考](#9-文件结构参考)
10. [实盘预备](#10-实盘预备)

---

## 1. 项目概览

### 仓库

```
https://github.com/paodingo/freqtrade-strategies
```

### 服务器

| 项目 | 值 |
|------|-----|
| 云平台 | 腾讯云 Lighthouse |
| 地域 | 新加坡 (ap-southeast-1) |
| IP | 43.134.72.69 |
| 系统 | Ubuntu 24.04 |
| 用户 | ubuntu |
| SSH 密钥路径 | `D:/key/openclaw/clf.pem` |

### 当前对比运行

| 项目 | 值 |
|------|-----|
| 基线策略 | **RegimeAwareV6** |
| 基线容器 | `freqtrade-v6`，API `8080` |
| 对比策略 | **RegimeAwareV61** |
| 对比容器 | `freqtrade-v61`，API `8081` |
| 交易对 | BTC/USDT:USDT（永续合约） |
| 模式 | 模拟盘（dry_run），$10,000 虚拟资金 |
| 每笔投入 | $2,500 USDT |
| 最多持仓 | 1 笔（当前只跑 BTC，单仓控制风险） |
| 止损 | -4% |
| 止盈 | 5%（ROI 机制） |
| 滑点 | 入/出各 0.03%，共 0.06% |
| 自动重启 | Docker `--restart unless-stopped` |
| 数据刷新 | Cron 每 6 小时自动下载 |
| 数据库 | V6 与 V6.1 分别使用独立 dry-run SQLite 文件 |

当前 V6/V6.1 的仓位设置是：每个 bot 各自拥有 $10,000 dry-run 钱包，`tradable_balance_ratio` 为 0.99，`max_open_trades` 为 1，`stake_amount` 为 `2500`。在 -4% 止损下，单笔止损约为 $100 USDT，约占模拟账户 1%。已有持仓不会因为重启自动扩大，新的入场会按新配置计算仓位。

### 回测性能（2024-01-09 → 2026-06-08）

| 指标 | 值 |
|------|-----|
| 总收益 | +0.74% ($74 USD) |
| 年化 | +0.31% CAGR |
| 最大回撤 | 0.44% |
| 夏普比率 | 0.31 |
| 交易次数 | 223 |
| 胜率 | 56.1% |
| 利润因子 | 1.15 |

### 策略简介

`RegimeAwareV6` 是一个做多+做空的合约策略。核心思路：

1. **判断市场状态**（4 小时 K 线）—— ADX + 布林带宽度 + ATR 三指标投票，2/3 通过即确认
2. **做多条件**—— 4h 多头排列 + 价格在 EMA200 上方 + 1h 回调至 EMA21 附近（2%以内）+ 收阳线
3. **做空条件**—— 4h 空头排列 + 价格在 EMA200 下方 + 1h 反弹至 EMA21 附近 + 收阴线
4. **震荡模式**—— 布林带区间内低买高卖，ADX < 22 确认无趋势
5. **出场**—— 5% 止盈（ROI），-4% 硬止损，跌超 EMA200 紧急出场

更多策略细节见 [STRATEGY_GUIDE.md](STRATEGY_GUIDE.md)。

---

## 2. 远程部署（服务器）

### 2.1 SSH 连接

**Windows（PowerShell）：**
```powershell
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69
```

**macOS / Linux：**
```bash
chmod 600 ~/key/openclaw/clf.pem
ssh -i ~/key/openclaw/clf.pem ubuntu@43.134.72.69
```

### 2.2 本地一键部署（推荐）

在本地项目目录下，一行命令部署到远程服务器：

> Windows 上用 PowerShell 执行。下面以 Windows 为例。

```powershell
# === 部署 V6 到服务器（完整流程：推代码 → 下载数据 → 启动容器）===

# Step 1: 本地提交 & 推送
cd D:\code\freqtrade-strategies
git add -A
git commit -m "your commit message"
git push origin master

# Step 2: 远程拉代码 & 下载数据 & 重启容器
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 @'
set -e
cd ~/freqtrade-strategies
git pull

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

docker stop freqtrade-v6 2>/dev/null || true
docker rm freqtrade-v6 2>/dev/null || true

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

sleep 8
curl -s -X POST http://localhost:8080/api/v1/start \
  -u freqtrader:freqtrade

echo "=== Deployed ==="
docker ps --filter "name=freqtrade-v6" --format "{{.Names}} {{.Status}}"
'@
```

### 2.3 同时运行 V6 和 V6.1 对比

可以同时跑。关键是分开容器名、API 端口、配置文件和 dry-run 数据库：

| 策略 | 容器 | API | 配置 | 数据库 |
|------|------|-----|------|--------|
| V6 | `freqtrade-v6` | `8080` | `user_data/config_btc_futures_v6.json` | `tradesv3_v6.dryrun.sqlite` |
| V6.1 | `freqtrade-v61` | `8081` | `user_data/config_btc_futures_v61.json` | `tradesv3_v61.dryrun.sqlite` |

PowerShell 一键部署：

```powershell
cd D:\code\freqtrade-strategies
git push origin master

ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 @'
set -e
cd ~/freqtrade-strategies
git pull
docker pull freqtradeorg/freqtrade:stable

docker run --rm \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "BTC/USDT:USDT" \
  --timeframes 1h 4h \
  --timerange 20240101- \
  --config /freqtrade/project/user_data/config_btc_futures_v6.json \
  -d /freqtrade/project/user_data/data \
  --trading-mode futures

docker stop freqtrade-v6 freqtrade-v61 2>/dev/null || true
docker rm freqtrade-v6 freqtrade-v61 2>/dev/null || true

docker run -d \
  --name freqtrade-v6 \
  --restart unless-stopped \
  -p 8080:8080 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures_v6.json \
  --datadir /freqtrade/project/user_data/data

docker run -d \
  --name freqtrade-v61 \
  --restart unless-stopped \
  -p 8081:8081 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV61 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures_v61.json \
  --datadir /freqtrade/project/user_data/data

sleep 10
curl -s -X POST http://localhost:8080/api/v1/start -u freqtrader:freqtrade
curl -s -X POST http://localhost:8081/api/v1/start -u freqtrader:freqtrade

echo "=== Running ==="
docker ps --filter "name=freqtrade-v6" --filter "name=freqtrade-v61" \
  --format "{{.Names}} {{.Status}} {{.Ports}}" | grep -E "freqtrade-v6|freqtrade-v61"
'@
```

查询两个 bot：

```bash
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/show_config
curl -s -u freqtrader:freqtrade http://localhost:8081/api/v1/show_config
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/profit
curl -s -u freqtrader:freqtrade http://localhost:8081/api/v1/profit
```

### 2.4 仅更新策略代码（不刷新数据）

```powershell
# 本地推送
git add strategies/RegimeAwareV6.py
git commit -m "update V6"
git push origin master

# 远程重启
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 @'
cd ~/freqtrade-strategies && git pull
docker stop freqtrade-v6 && docker rm freqtrade-v6
docker run -d --name freqtrade-v6 --restart unless-stopped \
  -p 8080:8080 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data
sleep 8
curl -s -X POST http://localhost:8080/api/v1/start -u freqtrader:freqtrade
docker ps --filter "name=freqtrade-v6"
'@
```

### 2.5 切换策略版本

把 `RegimeAwareV6` 改成 `RegimeAwareV9`（或其他版本）+ 改容器名：

```powershell
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 @'
cd ~/freqtrade-strategies && git pull

# 停旧版本（假设是 v6）
docker stop freqtrade-v6 && docker rm freqtrade-v6

# 启新版本（假设是 v9）
docker run -d --name freqtrade-v9 --restart unless-stopped \
  -p 8080:8080 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV9 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data

sleep 8
curl -s -X POST http://localhost:8080/api/v1/start -u freqtrader:freqtrade
'@
```

### 2.6 服务器首次部署（从零搭建）

如果服务器上什么都没装，按顺序执行：

```bash
# SSH 到服务器
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69

# === 1. 安装 Docker（如果还没装） ===
sudo apt update && sudo apt install -y docker.io
sudo systemctl enable docker
sudo usermod -aG docker $USER
# 重新登录使权限生效
exit
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69

# === 2. 拉项目 ===
git clone https://github.com/paodingo/freqtrade-strategies.git ~/freqtrade-strategies
cd ~/freqtrade-strategies

# === 3. 拉镜像 ===
docker pull freqtradeorg/freqtrade:stable

# === 4. 下载历史数据 ===
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

# === 5. 启动容器 ===
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

# === 6. 启动 Bot API ===
sleep 8
curl -s -X POST http://localhost:8080/api/v1/start \
  -u freqtrader:freqtrade

# === 7. 设定时数据刷新（每 6 小时） ===
(crontab -l 2>/dev/null; echo '0 */6 * * * docker run --rm -v /home/ubuntu/freqtrade-strategies:/freqtrade/project freqtradeorg/freqtrade:stable download-data --exchange binance --pairs "BTC/USDT:USDT" --timeframes 1h 4h --timerange 20240101- --config /freqtrade/project/user_data/config_btc_futures.json -d /freqtrade/project/user_data/data --trading-mode futures >> /var/log/freqtrade-cron.log 2>&1') | crontab -

# === 8. 验证部署 ===
docker ps --filter "name=freqtrade-v6"
docker logs --tail 20 freqtrade-v6
```

---

## 3. 本地开发环境

### 前提

- Docker Desktop 已安装
- 项目已 clone 到本地

### 克隆

```bash
git clone https://github.com/paodingo/freqtrade-strategies.git
cd freqtrade-strategies
```

### 本地下载数据

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

### 本地跑 bot（可选）

```bash
docker run -d --name freqtrade-local -p 8080:8080 \
  -v "$(pwd):/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data

sleep 8
curl -s -X POST http://localhost:8080/api/v1/start -u freqtrader:freqtrade

# 停止
docker stop freqtrade-local && docker rm freqtrade-local
```

---

## 4. 从本地推代码到服务器

### 标准工作流

```
本地改代码 → 本地回测验证 → git push → SSH 到服务器 → git pull → 重启容器
```

### 详细步骤

```bash
# === 1. 本地修改策略文件 ===
# 编辑 strategies/RegimeAwareV6.py

# === 2. 本地回测验证 ===
docker run --rm \
  -v "$(pwd):/freqtrade/project" \
  freqtradeorg/freqtrade:stable \
  backtesting \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data \
  --timerange 20240101-$(date +%Y%m%d)

# 回测结果正收益 → 继续。负收益 → 回退修改。

# === 3. 提交 & 推送 ===
git add -A
git commit -m "描述你的改动"
git push origin master

# === 4. 远程更新 & 重启 ===
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 @'
cd ~/freqtrade-strategies && git pull
docker stop freqtrade-v6 && docker rm freqtrade-v6
docker run -d --name freqtrade-v6 --restart unless-stopped \
  -p 8080:8080 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV6 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures.json \
  --datadir /freqtrade/project/user_data/data
sleep 8
curl -s -X POST http://localhost:8080/api/v1/start -u freqtrader:freqtrade
echo "=== Running ===" && docker logs --tail 5 freqtrade-v6
'@
```

### 只推文件不上线

```bash
# 有时候你只想备份代码，不上线
git add -A
git commit -m "wip: save work in progress"
git push origin master
# 服务器不受影响，继续跑原来的
```

---

## 5. 回测新策略

### 命令行

```bash
# 替换策略名即可
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

### 输出解读

```
Result for strategy RegimeAwareV6
┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃    Pair    ┃ Trades ┃ Tot Profit % ┃   Drawdown   ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
┃ BTC/USDT   ┃    223 ┃      0.74%  ┃      0.44%   ┃
└────────────┴────────┴──────────────┴──────────────┘
```

**关键指标**：
- **Tot Profit %** — 总收益率。正 = 赚钱
- **Drawdown** — 最大回撤。越小越好
- **Win%** — 胜率，55%+ 正常
- **Profit factor** — >1 才赚钱（$1 风险赚 $1+）

---

## 6. 监控与查看

### 快速健康检查（从本地一行看全部）

```powershell
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 "echo '=== Container ===' && docker ps --filter 'name=freqtrade-v6' && echo '=== Last 10 Logs ===' && docker logs --tail 10 freqtrade-v6 2>&1"
```

### 在服务器上查看

```bash
# 看到信息
docker ps --filter "name=freqtrade-v6"    # 容器状态
docker logs --tail 50 freqtrade-v6        # 最近 50 行日志
docker logs -f freqtrade-v6               # 实时日志（Ctrl+C 退出）

# 看信号
docker logs freqtrade-v6 | grep -i "enter\|exit\|signal"

# 看错误
docker logs freqtrade-v6 | grep -i "ERROR\|WARNING"

# 看 4h 数据加载
docker logs freqtrade-v6 | grep "4h"
```

### API 查询

```bash
# 状态
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/status

# 当前持仓
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/trades

# 盈亏
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/profit

# 余额
curl -s -u freqtrader:freqtrade http://localhost:8080/api/v1/balance
```

---

## 7. 日常维护

### 每周一次

```bash
# 更新 freqtrade 镜像
docker pull freqtradeorg/freqtrade:stable

# 然后按 4. 流程重启容器

# 看一周交易
docker logs freqtrade-v6 --since 168h | grep -i "enter\|exit"
```

### 每月一次

```bash
# 清理 Docker 日志（防止占满磁盘）
sudo sh -c "truncate -s 0 /var/lib/docker/containers/*/*-json.log"

# 清理无用镜像
docker image prune -f
```

### 数据清理

如果发现数据文件损坏或过期（bot 没信号可能是数据太旧）：

```bash
# 删掉重新下载
rm -rf ~/freqtrade-strategies/user_data/data/futures

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
```

---

## 8. 故障排查

### 容器没跑

```bash
docker ps -a --filter "name=freqtrade-v6"

# 退出码含义：
# 137 = OOM（内存不够，降低 max_open_trades）
# 1   = 配置错误（检查策略文件语法）
# 0   = 正常退出
```

### 策略加载失败

```bash
# 看具体报错
docker logs freqtrade-v6 | grep -A 3 "ERROR"
```

常见原因：
- Python 语法错误 → 检查最近改动的策略文件
- 缺依赖 → 不应该出现（freqtrade 镜像自带所有依赖）
- `merge_informative_pair` 报 `'date'` → 4h 数据路径问题

### 长时间 0 信号

三个可能：

1. **数据太旧** → 执行数据清理（见 7.）
2. **行情无机会** → 正常，策略在空仓等待
3. **入口参数太严** → 本地回测同一时间段，对比交易量

快速诊断：
```bash
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 'docker exec freqtrade-v6 python -c "
import pandas as pd; from pathlib import Path
p = Path(\"/freqtrade/project/user_data/data/futures\")
files = list(p.glob(\"*1h*\"))
if files:
    df = pd.read_feather(files[0])
    print(f\"Data: {len(df)} rows, last: {pd.to_datetime(df.iloc[-1].date)}\")
else:
    print(\"No data files found!\")
"'
```

### Binance 连接

新加坡服务器到 Binance 通常没问题。REST API 验证：
```bash
curl -s https://api.binance.com/api/v3/ping
# 返回 {} = 正常
```

---

## 9. 文件结构参考

```
freqtrade-strategies/
├── strategies/
│   ├── __init__.py
│   ├── regime_detector.py         # 市场状态检测（ADX+BB+ATR 投票）
│   ├── risk_manager.py            # 风控模块（熔断、仓位）
│   ├── RegimeAwareV6.py           # V6 基线
│   ├── RegimeAwareV61.py          # V6.1 对比策略
│   ├── RegimeAwareV8.py           # V8（多币种实验）
│   └── RegimeAwareV9.py           # V9（ATR 缩放实验）
├── tests/                         # 单元测试
├── user_data/
│   ├── config_btc.json            # 现货配置
│   ├── config_btc_futures_v6.json # V6 合约配置
│   ├── config_btc_futures_v61.json # V6.1 合约配置
│   ├── config_btc_futures_v61_live.example.json # V6.1 实盘模板（不含密钥）
│   └── data/                      # K 线数据（git ignore）
├── scripts/
│   ├── start_bot.sh               # 启动脚本
│   ├── refresh_data.sh            # 数据刷新和双 bot 健康检查
│   └── check_trades.sh            # V6/V6.1 交易变化监控
├── docs/superpowers/              # 设计文档 & 实现计划
├── STRATEGY_GUIDE.md              # 策略说明书（白话）
├── DEPLOY.md                      # 本文档
└── README.md                      # 项目简介
```

---

## 10. 实盘预备

实盘只考虑 V6.1，不让 V6/V6.1 同时使用同一个真实合约账户。上线前先阅读 [LIVE_TRADING.md](LIVE_TRADING.md)。

当前建议顺序：

1. V6/V6.1 dry-run 继续观察 `stake_amount=2500` 的表现。
2. 准备 Binance 合约独立子账户、交易权限 API Key、IP 白名单。
3. 复制 `user_data/config_btc_futures_v61_live.example.json` 为本机私有 live 配置。
4. 第一阶段实盘使用 `stake_amount=100-250`，验证开仓、平仓、交易所止损、通知和重启接管。
5. 通过冒烟测试后再逐步放大仓位。

---

## 附录：常用命令速查

```bash
# SSH
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69

# 从本地部署（一行）
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 'cd ~/freqtrade-strategies && git pull && docker stop freqtrade-v6 && docker rm freqtrade-v6 && docker run -d --name freqtrade-v6 --restart unless-stopped -p 8080:8080 -v ~/freqtrade-strategies:/freqtrade/project freqtradeorg/freqtrade:stable trade --strategy RegimeAwareV6 --strategy-path /freqtrade/project/strategies --config /freqtrade/project/user_data/config_btc_futures.json --datadir /freqtrade/project/user_data/data && sleep 8 && curl -s -X POST http://localhost:8080/api/v1/start -u freqtrader:freqtrade'

# 本地回测
docker run --rm -v "$(pwd):/freqtrade/project" freqtradeorg/freqtrade:stable backtesting --strategy RegimeAwareV6 --strategy-path /freqtrade/project/strategies --config /freqtrade/project/user_data/config_btc_futures.json --datadir /freqtrade/project/user_data/data --timerange 20240101-20260608

# 服务器健康检查
ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 "docker ps --filter 'name=freqtrade-v6' && echo '---' && docker logs --tail 10 freqtrade-v6"
```
