# TASK-0020D: Repository Documentation Currency Audit

状态：已完成。未修改入口文档正文。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只读审计仓库文档是否仍硬编码旧版本或过期运行状态，尤其是 `README.md`、`DEPLOY.md`、`LIVE_TRADING.md`、`STRATEGY_GUIDE.md` 中的 `V6.5` / `V6.6` 当前状态叙事。

## 主要发现

- `README.md` 仍把当前重点写成 `V6.5` / `V6.6` dry-run 对比。
- `DEPLOY.md` 仍把当前部署写成 `freqtrade-v65` / `freqtrade-v66` 和 `RegimeAwareV65` / `RegimeAwareV66`。
- `LIVE_TRADING.md` 仍引用 `V6.3` / `V6.5` live 准备路径。
- `STRATEGY_GUIDE.md` 仍围绕 `V6.5` / `V6.6` 当前目标。
- 当前实际阶段已经是 V11.29 真实执行验证链路，但 V11.29 状态仍为 `insufficient`，不能写成已通过或可替换。

## 输出

- `reports/audits/task20d_repository_documentation_currency_audit.md`

## 后续建议

- Task 20E：只更新 `README.md` 和 `STRATEGY_GUIDE.md` 的当前状态叙事。
- Task 20F：先规划 `DEPLOY.md` / `LIVE_TRADING.md` 的历史冻结或拆分方案，不直接改 deploy/live 命令。
- 技术链路继续 Task 20：`V11.29 Data Coverage and Runtime Performance Audit`。

## 未执行事项

- 未修改 `README.md`
- 未修改 `DEPLOY.md`
- 未修改 `LIVE_TRADING.md`
- 未修改 `STRATEGY_GUIDE.md`
- 未修改策略
- 未修改 bot 配置
- 未修改 dashboard / deploy
- 未读取 secret
- 未登录服务器
- 未启动、停止或重启 bot
- 未运行回测
