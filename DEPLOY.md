# 部署与运维手册

> Historical / not-current warning: 本文档保留为旧 V6.x dry-run 部署记录，不是当前 V11.29 操作手册。不要依据本文档启动、停止、重启、部署或操作 V11.29 bot。V11.29 当前真实执行验证仍为 `insufficient`，任何 V11.29 deploy/live/server 操作都需要单独人工授权任务。

这是当前 dry-run 部署的标准手册。当前云端主对比是 V6.5 震荡短线进攻基线与 V6.6 选择性箱体边缘候选；V6.2/V6.3/V6.4 只保留为历史回退版本。

## 当前云端布局

| 项目 | 值 |
| --- | --- |
| 服务器 | `43.134.72.69` |
| SSH 用户 | `ubuntu` |
| SSH 密钥 | `D:/key/openclaw/clf.pem` |
| 仓库路径 | `/home/ubuntu/freqtrade-strategies` |
| V6.5 容器 | `freqtrade-v65`，API `8081`，策略 `RegimeAwareV65` |
| V6.6 容器 | `freqtrade-v66`，API `8082`，策略 `RegimeAwareV66` |
| 监控服务 | `freqtrade-monitor.service`，HTTP `8090` |
| 交易模式 | 合约 dry-run，逐仓 |
| 交易对 | `BTC/USDT:USDT` |

Freqtrade API 只绑定服务器本机 `127.0.0.1`，监控面板只读，不提供 start/stop/forceexit 等交易控制接口。

## 部署前本地验证

在仓库根目录执行：

```bash
bash scripts/run_tests.sh
```

该脚本会检查监控面板 JavaScript 语法，并在官方 Freqtrade Docker 镜像内运行全部策略测试。

## 部署当前 dry-run 双 bot

Windows PowerShell 示例：

```powershell
cd D:\code\freqtrade-strategies
git push origin master

ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 @'
set -e
cd ~/freqtrade-strategies
git pull --ff-only
docker pull freqtradeorg/freqtrade:stable

docker run --rm \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  download-data \
  --exchange binance \
  --pairs "BTC/USDT:USDT" \
  --timeframes 15m 1h 4h \
  --timerange 20240101- \
  --config /freqtrade/project/user_data/config_btc_futures_v65.json \
  -d /freqtrade/project/user_data/data \
  --trading-mode futures

docker stop freqtrade-v6 freqtrade-v62 freqtrade-v63 freqtrade-v64 freqtrade-v65 freqtrade-v66 2>/dev/null || true
docker rm freqtrade-v6 freqtrade-v62 freqtrade-v63 freqtrade-v64 freqtrade-v65 freqtrade-v66 2>/dev/null || true

docker run -d \
  --name freqtrade-v65 \
  --restart unless-stopped \
  -p 127.0.0.1:8081:8081 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV65 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures_v65.json \
  --datadir /freqtrade/project/user_data/data

docker run -d \
  --name freqtrade-v66 \
  --restart unless-stopped \
  -p 127.0.0.1:8082:8082 \
  -v ~/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV66 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures_v66.json \
  --datadir /freqtrade/project/user_data/data

sleep 10
curl -s -X POST http://localhost:8081/api/v1/start -u "$FREQTRADE_API_AUTH"
curl -s -X POST http://localhost:8082/api/v1/start -u "$FREQTRADE_API_AUTH"

docker ps --filter "name=freqtrade-v65" --filter "name=freqtrade-v66" \
  --format "{{.Names}} {{.Status}} {{.Ports}}"
'@
```

如果服务器没有设置 `FREQTRADE_API_AUTH`，临时使用当前 dry-run API 账号密码即可。进入公网或实盘阶段前必须轮换。

## 部署监控面板

首次安装 systemd 服务：

```bash
cd /home/ubuntu/freqtrade-strategies
install -m 600 /dev/null user_data/monitor.env
cat > user_data/monitor.env <<'EOF'
MONITOR_HOST=0.0.0.0
MONITOR_PORT=8090
DASHBOARD_USER=paodingo
DASHBOARD_PASSWORD=replace-with-strong-password
FREQTRADE_API_AUTH=freqtrader:replace-with-api-password
MONITOR_CHART_TIMEFRAME=15m
STRATEGY_MAIN_TIMEFRAME=15m
STRATEGY_INFORMATIVE_TIMEFRAME=4h
BOT_V65_URL=http://localhost:8081
BOT_V66_URL=http://localhost:8082
BOT_V65_LABEL=V6.5
BOT_V66_LABEL=V6.6
MONITOR_HISTORY_DB_FILE=/home/ubuntu/freqtrade-strategies/user_data/monitor_history.sqlite
EOF
sudo cp deploy/freqtrade-monitor.service /etc/systemd/system/freqtrade-monitor.service
sudo systemctl daemon-reload
sudo systemctl enable freqtrade-monitor.service
```

日常重启：

```bash
sudo systemctl restart freqtrade-monitor.service
sudo systemctl status freqtrade-monitor.service --no-pager
curl -u "$DASHBOARD_USER:$DASHBOARD_PASSWORD" http://localhost:8090/api/summary
```

监控面板是只读服务；只访问本机 Freqtrade API。历史采样和监控事件写入 `user_data/monitor_history.sqlite`，该文件不提交到 git。

## 健康检查

```bash
curl -s -u "$FREQTRADE_API_AUTH" http://localhost:8081/api/v1/show_config
curl -s -u "$FREQTRADE_API_AUTH" http://localhost:8082/api/v1/show_config
curl -s -u "$FREQTRADE_API_AUTH" http://localhost:8081/api/v1/status
curl -s -u "$FREQTRADE_API_AUTH" http://localhost:8082/api/v1/status
curl -s -u "$DASHBOARD_USER:$DASHBOARD_PASSWORD" http://localhost:8090/api/history?range=30d
```

预期 dry-run 状态：

- V6.5：`bot_name=freqtrade-v65`，`strategy=RegimeAwareV65`，`timeframe=15m`，`dry_run=true`，`stake_amount=3000`，`max_open_trades=1`。
- V6.6：`bot_name=freqtrade-v66`，`strategy=RegimeAwareV66`，`timeframe=15m`，`dry_run=true`，`stake_amount=2500`，`max_open_trades=1`。

## 交易提醒

`scripts/check_trades.sh` 会在持仓出现、变化、关闭、API 异常或恢复时输出 `TRADE_ALERT:` 行。Linux cron 可以保留，让 OpenClaw 把这些行转发到 Telegram。

```bash
*/1 * * * * cd /home/ubuntu/freqtrade-strategies && bash scripts/check_trades.sh
```

## 回滚

回滚本质上是切回旧 commit 或旧策略名后重启容器。不要删除 dry-run SQLite，除非你明确想重置对比历史。

```bash
cd ~/freqtrade-strategies
git log --oneline -5
git checkout <previous-commit>
docker stop freqtrade-v65 freqtrade-v66
docker rm freqtrade-v65 freqtrade-v66
bash scripts/start_bot.sh
```

回到最新版本：

```bash
git checkout master
git pull --ff-only
```

## 实盘边界

本文档只用于 dry-run。不要从这里直接启动实盘容器。实盘前按 [LIVE_TRADING.md](LIVE_TRADING.md) 准备私有配置，并先运行 `bash scripts/preflight_live.sh <config>`。
