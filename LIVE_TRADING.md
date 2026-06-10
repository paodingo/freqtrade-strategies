# 实盘准备清单

当前系统还没有进入实盘阶段。V6.3 和 V6.5 应继续 dry-run 观察，直到提醒、风控检查、小额真实订单冒烟测试都补齐。

## 不能妥协的要求

- 使用交易所独立子账户，不和手动交易或其他 bot 共用。
- API Key 只开放交易权限，关闭提现权限，并启用服务器 IP 白名单。
- 每个合约账户只运行一个实盘 bot。
- 第一阶段只用 `stake_amount=100-250`，不要复制 dry-run 的仓位。
- 启用交易所止损：`stoploss_on_exchange=true`。
- Freqtrade API 不对公网开放；实盘 API 只绑定 `127.0.0.1`，通过 SSH 隧道、VPN 或私有反代访问。
- Telegram 必须能收到开仓、平仓、API 异常、bot 停止/恢复提醒。
- 必须验证 `stopentry` 和交易所手动平仓流程。

## 实盘配置模板

保守默认模板：

```text
user_data/config_btc_futures_v63_live.example.json
```

V6.5 进攻模板：

```text
user_data/config_btc_futures_v65_live.example.json
```

首次实盘前复制为私有文件，例如：

```bash
cp user_data/config_btc_futures_v63_live.example.json user_data/config_btc_futures_v63_live.json
```

真实密钥不要提交到 git，建议用环境变量覆盖：

```bash
export FREQTRADE__EXCHANGE__KEY="exchange-api-key"
export FREQTRADE__EXCHANGE__SECRET="exchange-api-secret"
export FREQTRADE__API_SERVER__PASSWORD="strong-live-api-password"
export FREQTRADE__API_SERVER__JWT_SECRET_KEY="random-string-at-least-32-chars"
```

模板默认把 API 绑定到 `127.0.0.1`。实盘配置不要改成 `0.0.0.0`。

## 第一阶段参数

第一阶段只验证真实成交链路，不追求收益：

```json
{
  "dry_run": false,
  "stake_amount": 250,
  "max_open_trades": 1,
  "trading_mode": "futures",
  "margin_mode": "isolated"
}
```

连续几次开平仓正常后，再考虑从 `250` 提到 `500`。更大仓位要等滑点、手续费、资金费、止损行为和提醒可靠性都有数据后再讨论。

## 启动前预检

启动任何实盘容器前先执行：

```bash
bash scripts/preflight_live.sh user_data/config_btc_futures_v63_live.json
```

预检会拦截常见危险配置：`dry_run=true`、API 绑定公网、没有交易所止损、占位密码、缺失交易所密钥等。

## 启动示例

```bash
docker run -d \
  --name freqtrade-v63-live \
  --restart unless-stopped \
  -p 127.0.0.1:8082:8082 \
  -e FREQTRADE__EXCHANGE__KEY \
  -e FREQTRADE__EXCHANGE__SECRET \
  -e FREQTRADE__API_SERVER__PASSWORD \
  -e FREQTRADE__API_SERVER__JWT_SECRET_KEY \
  -v /home/ubuntu/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV63 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures_v63_live.json \
  --datadir /freqtrade/project/user_data/data
```

日志和监控都健康后，再启动交易：

```bash
curl -X POST http://localhost:8082/api/v1/start \
  -u freqtrader:"$FREQTRADE__API_SERVER__PASSWORD"
```

## 验收清单

- 第一笔订单金额符合小额配置。
- 开仓后交易所能看到止损保护。
- 监控面板能显示实盘 bot 状态，同时实盘 API 没有暴露公网。
- Telegram 能收到开仓和平仓提醒。
- 容器重启后能识别旧仓并接管。
- `stopentry` 能阻止新开仓。
- 用极小订单测试过交易所手动平仓流程。

## 应急命令

```bash
curl -X POST http://localhost:8082/api/v1/stopentry \
  -u freqtrader:"$FREQTRADE__API_SERVER__PASSWORD"

docker logs --tail 100 freqtrade-v63-live
docker stop freqtrade-v63-live
```

如果 bot 和交易所状态不一致，先在交易所手动处理仓位，再看日志排查。
