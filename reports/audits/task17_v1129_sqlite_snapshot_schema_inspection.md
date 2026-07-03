# Task 17: V11.29 SQLite Snapshot Schema Inspection

状态：已完成，未进入 Task 18。

结论摘要：本任务只读检查了本地 V11.29 与 V10.8.2 SQLite snapshot。两个 snapshot 的 SHA256 均与 Task 16S 记录一致，均包含 `trades` 与 `orders` 表及 Freqtrade 交易字段 schema。V11.29 snapshot 的 `trades` 与 `orders` 表存在，但查询结果为 0 行，因此 V11.29 当前真实执行样本状态为 `insufficient`，不能生成充分的真实执行验证报告，也不能支持 V11.29 替换 V10.8.2 的判断。V10.8.2 snapshot 包含 6 条 closed trades 与 12 条 orders，可作为有限对照数据，但缺少 V11.29 同窗口样本。

## Summary

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- 只读检查方式：bundled Python `sqlite3`，使用 SQLite URI `mode=ro` 并设置 `PRAGMA query_only=ON`
- 未写入、复制、删除、移动或修改 SQLite snapshot
- 未读取 `.env`、`user_data/monitor.env` 或任何 secret
- 未登录服务器，未启动/停止/restart bot，未运行回测
- 未修改策略、bot 配置、dashboard、deploy 或原始脏工作区

## Snapshot files

| Snapshot | Path | Size | SHA256 | Task 16S match |
|---|---|---:|---|---|
| V11.29 | `reports/v1129_execution_validation/snapshots/tradesv3_v1129.snapshot.sqlite` | 94208 bytes | `B8C14EAE337A065CD69BBC6CED26BB1782F088818D5E2B552D4433C837D83EE5` | observed: yes |
| V10.8.2 | `reports/v1129_execution_validation/snapshots/tradesv3_v1082.snapshot.sqlite` | 94208 bytes | `3B953C9DC1AE3F2441375A8CCF31C573E56C05D98E9EFB7C9BC4138EEF426BBC` | observed: yes |

## Tables discovered

两个 snapshot 均发现相同表清单：

| Table | V11.29 rows | V10.8.2 rows | Status |
|---|---:|---:|---|
| `KeyValueStore` | 4 | 4 | observed |
| `orders` | 0 | 12 | observed schema; V11.29 sample `insufficient` |
| `pairlocks` | 0 | 8 | observed |
| `trade_custom_data` | 0 | 0 | observed schema; sample `insufficient` |
| `trades` | 0 | 6 | observed schema; V11.29 sample `insufficient` |
| `wallet_history` | 1 | 7 | observed |

## V11.29 schema inspection

`trades` table status: observed.

Key `trades` columns:

```text
id, exchange, pair, base_currency, stake_currency, is_open,
fee_open, fee_open_cost, fee_open_currency, fee_close, fee_close_cost, fee_close_currency,
open_rate, open_rate_requested, open_trade_value, close_rate, close_rate_requested,
realized_profit, close_profit, close_profit_abs,
stake_amount, max_stake_amount, amount, amount_requested,
open_date, close_date,
stop_loss, stop_loss_pct, initial_stop_loss, initial_stop_loss_pct,
is_stop_loss_trailing, max_rate, min_rate,
exit_reason, exit_order_status, strategy, enter_tag, timeframe, trading_mode,
amount_precision, price_precision, precision_mode, precision_mode_price,
contract_size, leverage, is_short, liquidation_price, interest_rate,
funding_fees, funding_fee_running, record_version
```

`orders` table status: observed.

Key `orders` columns:

```text
id, ft_trade_id, ft_order_side, ft_pair, ft_is_open, ft_amount, ft_price,
ft_cancel_reason, order_id, status, symbol, order_type, side,
price, average, amount, filled, remaining, cost, stop_price,
order_date, order_filled_date, order_update_date,
funding_fee, ft_fee_base, ft_order_tag
```

Observed schema supports the required execution-report fields structurally, but V11.29 has no trade/order rows in this snapshot, so value-level verification remains `insufficient`.

## V10.8.2 schema inspection

`trades` table status: observed.

Key `trades` columns are the same as V11.29 and include `pair`, `is_short`, `enter_tag`, `exit_reason`, `open_rate`, `close_rate`, `amount`, `stake_amount`, `close_profit`, `close_profit_abs`, `realized_profit`, `fee_open`, `fee_close`, `fee_open_cost`, `fee_close_cost`, `funding_fees`, `open_date`, and `close_date`.

`orders` table status: observed.

Key `orders` columns are the same as V11.29 and include `price`, `ft_price`, `average`, `filled`, `order_date`, `order_filled_date`, `order_update_date`, and `funding_fee`.

## V11.29 sample counts

| Metric | Result | Classification |
|---|---:|---|
| `trades` total rows | 0 | observed |
| open trades | 0 | observed query result |
| closed trades | 0 | observed query result |
| `orders` total rows | 0 | observed |
| open orders | 0 | observed query result |
| closed orders | 0 | observed query result |
| earliest `open_date` | `null` | insufficient |
| latest `open_date` | `null` | insufficient |
| latest `close_date` | `null` | insufficient |

说明：这里的 0 是对已存在表执行 `count(*)` 的 observed 查询结果，不表示缺失字段，也不表示策略行为结论。

## V10.8.2 sample counts

| Metric | Result | Classification |
|---|---:|---|
| `trades` total rows | 6 | observed |
| open trades | 0 | observed query result |
| closed trades | 6 | observed query result |
| `orders` total rows | 12 | observed |
| open orders | 0 | observed query result |
| closed orders | 12 | observed query result |
| earliest `open_date` | `2026-06-26 06:15:33.352116` | observed |
| latest `open_date` | `2026-07-01 02:16:09.203505` | observed |
| earliest `close_date` | `2026-06-26 07:14:40.367000` | observed |
| latest `close_date` | `2026-07-01 10:27:37.736000` | observed |
| earliest `order_date` | `2026-06-26 06:15:33.200000` | observed |
| latest `order_date` | `2026-07-01 10:27:37.634000` | observed |
| earliest `order_filled_date` | `2026-06-26 06:15:33.349000` | observed |
| latest `order_filled_date` | `2026-07-01 10:27:37.736000` | observed |

## Observation windows: 1d / 7d / 14d

V11.29:

| Window | Sample status |
|---|---|
| 1d | insufficient: no `trades` rows |
| 7d | insufficient: no `trades` rows |
| 14d | insufficient: no `trades` rows |

V10.8.2, using latest observed close time `2026-07-01 10:27:37.736000` as reference:

| Window | Open-date samples | Close-date samples | Classification |
|---|---:|---:|---|
| 1d | 2 | 3 | derived |
| 7d | 6 | 6 | derived |
| 14d | 6 | 6 | derived |

V10.8.2, using current task date `2026-07-03` as reference:

| Window | Open-date samples | Close-date samples | Classification |
|---|---:|---:|---|
| 1d | 0 | 0 | observed/derived, but current 1d sample is insufficient |
| 7d | 3 | 3 | derived |
| 14d | 6 | 6 | derived |

## Field availability matrix

| Field | V11.29 | V10.8.2 | Notes |
|---|---|---|---|
| `pair` | observed schema; sample insufficient | observed schema and rows | `trades.pair` |
| `side` | observed schema; sample insufficient | observed schema and rows | `trades.is_short` can derive side; `orders.side` exists |
| `entry_tag` | observed schema; sample insufficient | observed schema and rows | Freqtrade column is `enter_tag` |
| `exit_reason` | observed schema; sample insufficient | observed schema and rows | `trades.exit_reason` |
| `open_rate` | observed schema; sample insufficient | observed schema and rows | `trades.open_rate` |
| `close_rate` | observed schema; sample insufficient | observed schema and rows | `trades.close_rate` |
| `amount` | observed schema; sample insufficient | observed schema and rows | `trades.amount`, `orders.amount` |
| `stake_amount` | observed schema; sample insufficient | observed schema and rows | `trades.stake_amount` |
| `profit` | observed schema; sample insufficient | observed schema and rows | `trades.close_profit_abs`, `trades.realized_profit` |
| `profit_ratio` | observed schema; sample insufficient | observed schema and rows | `trades.close_profit` |
| fee | observed schema; sample insufficient | observed schema and rows | `fee_open`, `fee_close`, `fee_open_cost`, `fee_close_cost`; not interpreted as actual fee values for V11.29 because there are no rows |
| funding fee | observed schema; sample insufficient | observed schema and rows | `trades.funding_fees`, `orders.funding_fee` |
| order price | observed schema; sample insufficient | observed schema and rows | `orders.price`, `orders.ft_price`; V11.29 has no order rows, so value-level verification is `insufficient` |
| filled price | observed schema; sample insufficient | observed schema and rows | `orders.average`; V11.29 has no order rows, so value-level verification is `insufficient` |
| latency | derived schema only; sample insufficient | derived from rows | requires `orders.order_date` and `orders.order_filled_date`; V11.29 has no order rows |
| unfilled signals | unknown | unknown | not provable from these SQLite snapshots alone |
| blocked signals | unknown | unknown | not provable from these SQLite snapshots alone |
| API errors / jq parse errors / stopped alerts | unknown | unknown | not stored in these SQLite snapshots |

## Same-window comparison readiness

Status: `insufficient`.

- V10.8.2 has closed-trade and order samples from `2026-06-26` through `2026-07-01`.
- V11.29 has matching schema but no `trades` rows and no `orders` rows in the acquired snapshot.
- Therefore, same-window comparison cannot be established from the current snapshots.
- Current data can support schema-aware report generation and an honest insufficient report; it cannot support real execution quality comparison.

## Blocking data gaps

- V11.29 missing sample rows: `trades` table has 0 rows and `orders` table has 0 rows.
- V11.29 open/closed trade behavior is `insufficient`; no trade row exists to inspect pair, side, entry tag, exit reason, rates, fees, funding, PnL, or timestamps at value level.
- V11.29 order price, filled price, and latency are structurally available in schema but cannot be verified without order rows.
- Unfilled signals, blocked signals, API errors, jq parse errors, stopped alerts, and bot uptime remain `unknown` from SQLite alone.
- Current SQLite snapshots do not prove V11.29 execution quality and do not prove V11.29 replacement readiness.

## Whether Task 18 can proceed

Task 18 can proceed only with a restricted scope:

- Allowed scope: build a SQLite-backed execution report builder that reads these snapshots read-only, emits `sample_status = insufficient` for V11.29, and refuses any replacement verdict when V11.29 sample rows are absent.
- Not allowed scope: generating a positive V11.29 real execution validation result or claiming V11.29 can replace V10.8.2.

## Recommended Task 18 scope

Recommended Task 18: `V11.29 Execution Report Builder`.

Task 18 should:

- read local SQLite snapshots in read-only mode;
- compute schema, counts, windows, and field availability;
- emit JSON and Markdown reports matching `docs/harness/v1129_execution_report_schema.md`;
- set V11.29 `sample_status` to `insufficient` when `trades` or `orders` rows are absent;
- include V10.8.2 as limited observed comparison data;
- mark same-window comparison as `insufficient` until V11.29 has real trade/order samples;
- avoid any conclusion that V11.29 passed execution validation or can replace V10.8.2.

## Verification

Final verification commands were run after writing this report:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task17_v1129_sqlite_snapshot_schema_inspection.md
tasks/active/TASK-0017-v1129-sqlite-snapshot-schema-inspection.md
```
