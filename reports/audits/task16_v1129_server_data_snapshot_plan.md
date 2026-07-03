# Task 16: V11.29 Server Data Snapshot Plan

状态：已完成，未进入 Task 17。

结论：本任务只生成 V11.29 server-side dry-run SQLite 只读取证方案。未登录服务器，未执行 SSH，未复制 SQLite，未读取 secret，未启动/停止/重启 bot，未运行回测，未修改策略或 bot 配置。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 15 commit：`6f1374e Locate V11.29 execution data sources`

前置 gate：

```text
git status --short --untracked-files=all
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

Task 15 输入结论：

- 本地原始工作区未发现 `user_data/tradesv3_v1129.dryrun.sqlite`。
- V11.29 config 的 `db_url` 指向 `sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite`。
- 本地 `monitor_history.sqlite` 和 `reports/live_window_execution_check/*` 只是候选，不能证明含真实 trades/orders。
- 当前不能生成真实执行验证报告，只能继续 insufficient 报告。

## 2. 需要在服务器确认的对象

后续服务器侧只读任务需要确认：

| 对象 | 需要确认的内容 | 预期/候选 |
|---|---|---|
| V11.29 container | 容器是否存在、是否运行、挂载卷路径 | `freqtrade-v1129` 或服务器实际命名 |
| V11.29 project path | 服务器 repo / project 根目录 | `/home/ubuntu/freqtrade-strategies` 或实际路径 |
| 容器内 SQLite 路径 | dry-run trade DB 是否存在 | `/freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite` |
| host 映射路径 | 容器 DB 在 host 上的实际文件路径 | 由 `docker inspect` 的 mounts 推导 |
| SQLite sidecar | WAL/SHM 是否存在 | `tradesv3_v1129.dryrun.sqlite-wal`、`tradesv3_v1129.dryrun.sqlite-shm` |
| V10.8.2 对照 DB | same-window 对照 DB 是否存在 | `tradesv3_v1082.dryrun.sqlite` 或实际 `db_url` |
| closed-loop report | server-side report 是否存在 | `reports/reliable_strategy_search_v1129/v11_closed_loop_report.json`、`.html` |

## 3. 只读检查命令草案

以下命令是草案，Task 16 未执行。

建议先由人工确认 SSH target、server user、key、repo path 后再执行。命令中的 `SERVER`、`SERVER_REPO`、`CONTAINER_V1129`、`CONTAINER_V1082` 必须由人工替换。

```powershell
$SERVER = "<user>@<host>"
$SERVER_REPO = "/home/ubuntu/freqtrade-strategies"
$CONTAINER_V1129 = "freqtrade-v1129"
$CONTAINER_V1082 = "freqtrade-v1082"
```

只读确认容器和挂载：

```powershell
ssh $SERVER "docker ps --format '{{.Names}} {{.Status}}' | grep -E 'freqtrade|v1129|v1082'"
ssh $SERVER "docker inspect $CONTAINER_V1129 --format '{{json .Mounts}}'"
ssh $SERVER "docker inspect $CONTAINER_V1082 --format '{{json .Mounts}}'"
```

只读确认 SQLite 路径存在性、大小、mtime：

```powershell
ssh $SERVER "docker exec $CONTAINER_V1129 sh -lc 'ls -l /freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite /freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite-wal /freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite-shm 2>/dev/null || true'"
ssh $SERVER "docker exec $CONTAINER_V1082 sh -lc 'ls -l /freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite /freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite-wal /freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite-shm 2>/dev/null || true'"
```

只读确认 server-side report 候选：

```powershell
ssh $SERVER "cd $SERVER_REPO && ls -l reports/reliable_strategy_search_v1129/v11_closed_loop_report.json reports/reliable_strategy_search_v1129/v11_closed_loop_report.html 2>/dev/null || true"
```

## 4. 安全复制 SQLite 快照命令草案

目标：复制一致性快照，不直接修改 live DB，不复制 secret/env，不停止 bot。

优先方案：在服务器临时目录中用 SQLite backup API 生成只读副本，再下载副本。

```powershell
$SNAP_DIR = "/tmp/v1129-sqlite-snapshot-$(date +%Y%m%d-%H%M%S)"

ssh $SERVER "mkdir -p $SNAP_DIR && docker exec $CONTAINER_V1129 sh -lc 'sqlite3 /freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite \".backup /tmp/tradesv3_v1129.snapshot.sqlite\"' && docker cp $CONTAINER_V1129:/tmp/tradesv3_v1129.snapshot.sqlite $SNAP_DIR/tradesv3_v1129.snapshot.sqlite && ls -l $SNAP_DIR/tradesv3_v1129.snapshot.sqlite"
```

V10.8.2 same-window 对照快照草案：

```powershell
ssh $SERVER "mkdir -p $SNAP_DIR && docker exec $CONTAINER_V1082 sh -lc 'sqlite3 /freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite \".backup /tmp/tradesv3_v1082.snapshot.sqlite\"' && docker cp $CONTAINER_V1082:/tmp/tradesv3_v1082.snapshot.sqlite $SNAP_DIR/tradesv3_v1082.snapshot.sqlite && ls -l $SNAP_DIR/tradesv3_v1082.snapshot.sqlite"
```

下载快照草案：

```powershell
New-Item -ItemType Directory -Force -Path reports\v1129_execution_validation\snapshots | Out-Null
scp "$SERVER:$SNAP_DIR/tradesv3_v1129.snapshot.sqlite" "reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite"
scp "$SERVER:$SNAP_DIR/tradesv3_v1082.snapshot.sqlite" "reports\v1129_execution_validation\snapshots\tradesv3_v1082.snapshot.sqlite"
```

可选清理服务器临时快照草案，仅在确认下载成功后执行：

```powershell
ssh $SERVER "rm -f $SNAP_DIR/tradesv3_v1129.snapshot.sqlite $SNAP_DIR/tradesv3_v1082.snapshot.sqlite && rmdir $SNAP_DIR 2>/dev/null || true"
```

## 5. 复制后本地目标路径建议

建议不要放入 `user_data/**`，避免误认为 bot runtime 数据或配置输入。建议使用隔离审计目录：

```text
reports/v1129_execution_validation/snapshots/tradesv3_v1129.snapshot.sqlite
reports/v1129_execution_validation/snapshots/tradesv3_v1082.snapshot.sqlite
reports/v1129_execution_validation/snapshots/SNAPSHOT_MANIFEST.md
```

`SNAPSHOT_MANIFEST.md` 应记录：

- snapshot 时间
- server host alias
- container name
- container SQLite path
- copied local path
- file size
- sha256
- 是否包含 WAL/SHM 或是否用 `.backup`
- 未复制 `.env`、`monitor.env`、config、key 的声明

## 6. 如何避免复制 live secret / env

原则：

- 只复制 `.snapshot.sqlite` 文件。
- 不复制 `.env`、`user_data/monitor.env`、`config*.json`、key files、dashboard auth 文件。
- 不递归复制目录，例如禁止 `scp -r $SERVER:/home/ubuntu/freqtrade-strategies .`。
- 不执行 `docker cp $CONTAINER:/freqtrade/project/user_data .`。
- 不执行 `tar` 打包整个 repo、`user_data` 或 `configs`。
- 传输前后只对 snapshot 文件做 `ls -l` 和 `sha256sum`。

建议校验命令草案：

```powershell
ssh $SERVER "sha256sum $SNAP_DIR/tradesv3_v1129.snapshot.sqlite $SNAP_DIR/tradesv3_v1082.snapshot.sqlite 2>/dev/null || true"
Get-FileHash reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite -Algorithm SHA256
Get-FileHash reports\v1129_execution_validation\snapshots\tradesv3_v1082.snapshot.sqlite -Algorithm SHA256
```

## 7. 如何确认 SQLite 是否包含 trades / orders 表

Task 17 才应读取 snapshot schema。建议只在本地快照上执行，不对 server live DB 执行。

schema inspection 草案：

```powershell
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite ".tables"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite ".schema trades"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite ".schema orders"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite "PRAGMA table_info(trades);"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite "PRAGMA table_info(orders);"
```

字段需要确认：

- trade id / order id
- pair
- side / is_short
- open_date / close_date
- open_rate / close_rate / amount / stake_amount
- fee_open / fee_close / fee fields
- entry_tag
- exit_reason
- realized_profit / close_profit
- order price / filled price / order status
- funding fee 字段是否存在；如果不存在，需要另寻 exchange/funding ledger

## 8. 如何确认样本时间窗口

只在本地快照上执行窗口统计，避免触碰 live DB：

```powershell
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite "select min(open_date), max(open_date), count(*) from trades;"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite "select count(*) from trades where open_date >= datetime('now','-1 day');"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite "select count(*) from trades where open_date >= datetime('now','-7 day');"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite "select count(*) from trades where open_date >= datetime('now','-14 day');"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1129.snapshot.sqlite "select count(*) from trades where close_date is not null;"
```

如果 Freqtrade 使用 millisecond timestamp 或不同日期字段，Task 17 必须先以 schema 为准修正查询。

## 9. 如何确认 V10.8.2 same-window 数据是否存在

同样只对本地 V10.8.2 snapshot 执行：

```powershell
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1082.snapshot.sqlite ".tables"
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1082.snapshot.sqlite "select min(open_date), max(open_date), count(*) from trades;"
```

same-window 规则建议：

- 先用 V11.29 的 `min(open_date)` / `max(open_date)` 得到观察窗口。
- 再查询 V10.8.2 在同一窗口内的 open/closed trades。
- 如果 V10.8.2 没有同窗口样本，则报告 `cannot_compare_reason`，不得做替换判断。

示例查询草案：

```powershell
sqlite3 reports\v1129_execution_validation\snapshots\tradesv3_v1082.snapshot.sqlite "select count(*) from trades where open_date >= '<v1129_window_start>' and open_date <= '<v1129_window_end>';"
```

## 10. 禁止执行的命令类别

后续取证任务中禁止：

- `docker restart`
- `docker stop`
- `docker start`
- `docker compose up`
- `docker compose down`
- `freqtrade trade`
- `freqtrade backtesting`
- `freqtrade download-data`
- 任何会写 live DB 的 `sqlite3` 命令，例如 `insert`、`update`、`delete`、`vacuum`、`reindex`
- 任何 bot start/stop/reload lifecycle 命令
- 任何交易所下单、撤单、同步 wallet、修改 config 的命令
- 任何递归复制 repo、`user_data/**`、`configs/**`、`.env`、secret 的命令

## 11. Task 17 推荐

推荐 Task 17：`V11.29 SQLite Snapshot Schema Inspection`。

Task 17 前置条件应包括：

- 人工确认并执行了 Task 16 的只读 snapshot 复制步骤。
- 本地存在 `reports/v1129_execution_validation/snapshots/tradesv3_v1129.snapshot.sqlite`。
- 如需 same-window comparison，本地存在 `reports/v1129_execution_validation/snapshots/tradesv3_v1082.snapshot.sqlite`。
- `git status --short` 只包含 Task 17 允许文件或为空。

Task 17 应只读取本地 snapshot schema 和聚合统计，不登录服务器、不读取 secret、不启动 bot、不运行回测、不修改策略或 bot 配置。
