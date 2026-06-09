# 部署与运维手册

这是当前 dry-run 部署的标准手册。旧 V6-only 命令已移除，避免把当前 V6.2
基线和历史策略版本混在一起。

## 当前云端布局

| 项目 | 值 |
| --- | --- |
| 服务器 | `43.134.72.69` |
| SSH 用户 | `ubuntu` |
| SSH 密钥 | `D:/key/openclaw/clf.pem` |
| 仓库路径 | `/home/ubuntu/freqtrade-strategies` |
| V6.2 容器 | `freqtrade-v6`，API `8080`，策略 `RegimeAwareV62` |
| V6.1 容器 | `freqtrade-v61`，API `8081`，策略 `RegimeAwareV61` |
| 监控服务 | `freqtrade-monitor.service`，HTTP `8090` |
| 交易模式 | 合约 dry-run，逐仓 |
| 交易对 | `BTC/USDT:USDT` |

V6.2 继续使用 `user_data/config_btc_futures_v6.json` 这个配置文件名，方便沿用旧 V6
槽位。该配置当前实际是 `bot_name=freqtrade-v62`、`stake_amount=1500`、
`tradesv3_v62.dryrun.sqlite`。

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
  --strategy RegimeAwareV62 \
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
curl -s -X POST http://localhost:8080/api/v1/start -u "$FREQTRADE_API_AUTH"
curl -s -X POST http://localhost:8081/api/v1/start -u "$FREQTRADE_API_AUTH"

docker ps --filter "name=freqtrade-v6" --filter "name=freqtrade-v61" \
  --format "{{.Names}} {{.Status}} {{.Ports}}"
'@
```

如果服务器没有设置 `FREQTRADE_API_AUTH`，临时使用当前 dry-run API 账号密码即可。进入
公网或实盘阶段前必须轮换。

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
BOT_V6_URL=http://localhost:8080
BOT_V61_URL=http://localhost:8081
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

监控面板是只读服务。历史采样写入 `user_data/monitor_history.jsonl`，该文件不提交到 git。

## 健康检查

```bash
curl -s -u "$FREQTRADE_API_AUTH" http://localhost:8080/api/v1/show_config
curl -s -u "$FREQTRADE_API_AUTH" http://localhost:8081/api/v1/show_config
curl -s -u "$FREQTRADE_API_AUTH" http://localhost:8080/api/v1/status
curl -s -u "$FREQTRADE_API_AUTH" http://localhost:8081/api/v1/status
curl -s -u "$DASHBOARD_USER:$DASHBOARD_PASSWORD" http://localhost:8090/api/history?range=30d
```

预期 dry-run 状态：

- V6.2：`bot_name=freqtrade-v62`，`strategy=RegimeAwareV62`，`dry_run=true`，
  `stake_amount=1500`，`max_open_trades=1`。
- V6.1：`bot_name=freqtrade-v61`，`strategy=RegimeAwareV61`，`dry_run=true`，
  `stake_amount=2500`，`max_open_trades=1`。

## 交易提醒

`scripts/check_trades.sh` 会在持仓出现、变化、关闭、API 异常或恢复时输出 `TRADE_ALERT:`
行。Linux cron 可以保留，让 OpenClaw 把这些行转发到 Telegram。

```bash
*/1 * * * * cd /home/ubuntu/freqtrade-strategies && bash scripts/check_trades.sh
```

## 回滚

回滚本质上是切回旧 commit 或旧策略名后重启容器。不要删除 dry-run SQLite，除非你明确想重置对比历史。

```bash
cd ~/freqtrade-strategies
git log --oneline -5
git checkout <previous-commit>
docker stop freqtrade-v6 && docker rm freqtrade-v6
bash scripts/start_bot.sh
```

回到最新版本：

```bash
git checkout master
git pull
```

## 实盘边界

本文档只用于 dry-run。不要从这里直接启动实盘容器。实盘前按 [LIVE_TRADING.md](LIVE_TRADING.md)
准备私有配置，并先运行 `bash scripts/preflight_live.sh <config>`。
