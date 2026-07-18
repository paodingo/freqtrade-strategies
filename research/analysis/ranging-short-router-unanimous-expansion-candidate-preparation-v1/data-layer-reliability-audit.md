# 数据层可靠性审计

- 审计时间：`2026-07-18T19:11:31.204296Z`
- 总体结论：`not_reliable_for_current_strategy_decisioning`
- Binance USD-M 公共接口：`7/7` 可达
- Dashboard Node 代理根因：`true`
- Dashboard / Freqtrade 本地监听：`false / false`
- Monitor 最新采样：`2026-07-16T08:47:47.029000Z`，stale=`true`
- 当前模拟盘收益库：`false`

## 分层结论

| 层 | 评级 | 原因 |
|---|---|---|
| `sealed_historical_research_integrity` | `reliable` | sealed manifests, byte hashes, UTC continuity and exact local rehydration are enforced |
| `public_binance_source_reachability` | `reliable_at_observation_time` | all audited unauthenticated USD-M public endpoints responded |
| `dashboard_live_fetch_path` | `unreliable` | Node fetch bypasses required environment proxy; NODE_USE_ENV_PROXY=1 restores reachability |
| `local_persistence_freshness` | `unreliable` | no continuously updated market history is persisted and monitor samples exceed the 2h freshness SLA |
| `current_simulated_performance` | `unavailable` | no current Freqtrade trade SQLite store exists |
| `feature_completeness` | `partial` | OHLCV/mark/funding/OI/taker are available on demand, but continuous historical alpha, order-book, liquidation and trade-tick datasets are absent |

## 解释

冻结研究数据可按清单和 SHA-256 精确复现，因此适合可重复的历史研究；但它不是实时数据。当前 Binance 公共源本身可用，故障发生在本机 Node 运行链路没有使用所需代理。即使修复代理，本机仍没有持续运行的 Dashboard/Freqtrade 服务、连续增量落盘和当前模拟盘交易库。

现有字段覆盖也只是部分完整：按需可取得 OHLCV、mark/index、funding、OI 和 taker flow；缺少连续历史 OI/taker/多空比，以及订单簿、清算和逐笔成交的研究级落盘。

## 修复门槛

- launch Dashboard Node with environment proxy support when HTTP(S)_PROXY is required
- restore a supervised Freqtrade dry-run service and current trade SQLite store
- schedule incremental 15m/1h/4h futures OHLCV plus mark and funding persistence with gap alarms
- persist time-aligned OI, taker flow and long/short ratios for research instead of relying only on ephemeral snapshots
- add freshness SLOs and fail-closed UI states for each source independently
