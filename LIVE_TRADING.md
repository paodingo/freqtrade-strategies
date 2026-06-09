# V6.1 实盘预备清单

当前目标不是立刻实盘，而是把实盘所需的安全边界提前补齐。实盘只考虑 **V6.1**，V6 继续作为 dry-run 对照。

## 上线前必须满足

- 使用交易所独立子账户，不与手动交易或其它 bot 共用。
- API Key 只开交易权限，关闭提现权限，并开启服务器 IP 白名单。
- 只运行一个实盘 bot。合约/杠杆账户不要让多个 bot 共用同一个账户。
- 先用小额冒烟测试，建议 `stake_amount=100-250`，不要直接用 dry-run 的 `2500`。
- 启用交易所止损：`stoploss_on_exchange=true`。
- 8080/8081/8082 不对公网开放，实盘 API 只绑定到本机访问或通过 SSH 隧道访问。
- Telegram 必须能收到开仓、平仓、API 异常、bot 停止/恢复提醒。

## 配置模板

模板文件：

```text
user_data/config_btc_futures_v61_live.example.json
```

首次实盘时复制为本机私有文件，不要提交真实密钥：

```bash
cp user_data/config_btc_futures_v61_live.example.json user_data/config_btc_futures_v61_live.json
```

推荐用环境变量覆盖敏感字段：

```bash
export FREQTRADE__EXCHANGE__KEY="你的交易所 API key"
export FREQTRADE__EXCHANGE__SECRET="你的交易所 API secret"
export FREQTRADE__API_SERVER__PASSWORD="强密码"
export FREQTRADE__API_SERVER__JWT_SECRET_KEY="至少 32 位随机字符串"
```

## 第一阶段实盘参数

建议第一阶段只做验证，不追求收益：

```json
{
  "dry_run": false,
  "stake_amount": 250,
  "max_open_trades": 1,
  "trading_mode": "futures",
  "margin_mode": "isolated"
}
```

通过冒烟测试后，再考虑从 `250` 提高到 `500` 或 `1000`。只有当连续几天验证正常，才讨论更大仓位。

## 启动命令示例

实盘容器端口只绑定本机：

```bash
docker run -d \
  --name freqtrade-v61-live \
  --restart unless-stopped \
  -p 127.0.0.1:8082:8082 \
  -e FREQTRADE__EXCHANGE__KEY \
  -e FREQTRADE__EXCHANGE__SECRET \
  -e FREQTRADE__API_SERVER__PASSWORD \
  -e FREQTRADE__API_SERVER__JWT_SECRET_KEY \
  -v /home/ubuntu/freqtrade-strategies:/freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --strategy RegimeAwareV61 \
  --strategy-path /freqtrade/project/strategies \
  --config /freqtrade/project/user_data/config_btc_futures_v61_live.json \
  --datadir /freqtrade/project/user_data/data
```

确认没问题后再启动交易：

```bash
curl -X POST http://localhost:8082/api/v1/start -u freqtrader:"$FREQTRADE__API_SERVER__PASSWORD"
```

## 冒烟测试验收

第一笔真实交易只验证流程：

- 能开仓，且仓位金额符合预期。
- 开仓后交易所能看到止损单或止损保护。
- 面板能显示实盘 bot 状态。
- Telegram 收到开仓提醒。
- 能正常平仓，Telegram 收到平仓提醒。
- 容器重启后能识别并接管旧仓。
- 如 API 异常或 bot 停止，Telegram 能提醒。

## 回滚

如果发现异常：

```bash
curl -X POST http://localhost:8082/api/v1/stopentry -u freqtrader:"$FREQTRADE__API_SERVER__PASSWORD"
docker logs --tail 100 freqtrade-v61-live
```

必要时手动在交易所处理仓位，然后停止容器：

```bash
docker stop freqtrade-v61-live
```

## 当前状态

当前线上仍是 V6/V6.1 双 dry-run 对比。实盘配置模板已经准备好，但没有启动实盘，也没有提交任何真实 API 密钥。
