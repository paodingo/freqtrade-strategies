# 开源参考审计

## 审计边界

第二阶段只参考开源项目的工程结构、回测流程、风控思想和执行建模，不复制公开策略参数、买卖条件或收益承诺。

参考来源：

- Freqtrade 官方文档：https://www.freqtrade.io/en/stable/
- Freqtrade backtesting：https://www.freqtrade.io/en/stable/backtesting/
- Freqtrade lookahead analysis：https://www.freqtrade.io/en/stable/lookahead-analysis/
- Freqtrade recursive analysis：https://www.freqtrade.io/en/stable/recursive-analysis/
- NostalgiaForInfinity GitHub：https://github.com/iterativv/NostalgiaForInfinity
- Hummingbot 官方文档：https://hummingbot.org/
- Hummingbot exchange connectors：https://hummingbot.org/exchanges/

## Freqtrade 可借鉴点

### 可借鉴

1. 策略必须通过回测、dry-run、成本输出、未来函数检查和递归指标检查分层验证。
2. 回测报告必须保留交易数、回撤、胜率、Profit Factor、单笔贡献、手续费和资金费。
3. dry-run 不是实盘资格，只是模拟盘观察层。
4. protections 可作为风控思想参考，例如冷却、止损后保护、低收益过滤，但不能用来掩盖策略本身缺陷。
5. lookahead/recursive 分析应成为第二阶段验收门之一。

### 当前系统差距

1. 当前 `btc_system` 有回测和成本模型，但还缺统一的第二阶段矩阵 runner。
2. 当前报告有第一阶段 HTML，但没有统一输出 30/45/70/滚动窗口和成本压力的完整矩阵。
3. 当前没有把 future leakage、lookahead、recursive 风险作为第二阶段汇总报告的强制门禁。
4. 当前 paper 观察层已经接入运行中 Freqtrade REST candles，但第二阶段还需要把“数据新鲜度”写入报告。

### 不能照搬

1. 不能直接把 Freqtrade protections 当作盈利来源。
2. 不能因为 Freqtrade 支持某个插件，就把它加入默认核心组合。
3. 不能用 dry-run 表现替代多窗口回测和成本压力测试。

## NostalgiaForInfinity 可借鉴点

### 可借鉴

1. 复杂策略需要清晰组织：信号条件、保护条件、配置参数、开关管理要分层。
2. 多条件过滤必须可审计，不能只输出最终买卖信号。
3. 参数很多时，需要配置化和分组，而不是散落在策略文件中。
4. 保护机制应默认保守，特别是趋势末端追入、急跌后做空、区间边缘反抽。

### 当前系统差距

1. 当前三个策略臂代码较清晰，但参数仍硬编码在 arm 文件中，不利于矩阵扫描。
2. `core_combo`、`combo`、`research_only` 的策略臂角色没有集中配置文件。
3. 当前信号理由和 blocked reasons 已经存在，但 phase2 报告还没有统一展示“被过滤信号的虚拟盈亏/机会成本”。

### 不能照搬

1. 不能复制 NFI 的参数、买入卖出逻辑或具体信号组合。
2. 不能把复杂条件堆叠当作稳健性。
3. 不能为了提高回测收益添加不可解释的条件。

## Hummingbot 可借鉴点

### 可借鉴

1. 执行层要区分 maker/taker 成本。
2. 成交失败、撤单、滑点、部分成交和订单生命周期是模拟盘前必须检查的风险点。
3. 成本压力测试应覆盖更差成交情况，而不是只看理想成交。
4. dry-run checklist 应包含订单、日志、异常恢复和风控状态机。

### 当前系统差距

1. 当前 `CostModel` 有 maker/taker fee 和 slippage，但回测 CLI 还不能直接指定 “滑点 × 1.5 / 滑点 × 2 + taker 保守”。
2. 当前 paper 输出偏决策层，还没有订单生命周期 checklist。
3. 当前没有将成交失败、撤单失败、API 异常恢复映射到第二阶段模拟盘门禁。

### 不能照搬

1. 第二阶段不把系统改成做市机器人。
2. 不引入挂单做市逻辑作为收益来源。
3. 不用 maker 假设美化回测，除非报告明确分开 maker/taker 情境。

## 对当前系统的差距清单

| 编号 | 差距 | 影响 | 第二阶段处理 |
|---|---|---|---|
| G1 | 缺少统一 phase2 runner | 实验不可复现 | 新增 `scripts/run_phase2_experiments.py` |
| G2 | 策略臂角色未集中配置 | `trend_pullback` 容易误入核心组合 | 新增 `btc_system/signals/arm_registry.py` |
| G3 | 成本压力 CLI 不完整 | 无法验证保守成本 | 扩展 `CostModel` 和 backtest CLI |
| G4 | 参数扫描靠手工跑 | 容易漏测和挑结果 | 新增参数扫描输出 CSV |
| G5 | 滚动窗口缺失 | 不知道结果是否依赖单一窗口 | 新增 rolling 30d / 14d |
| G6 | OI 增益/减益未独立汇总 | 容易误把 OI 当强过滤 | 新增 OI delta 表 |
| G7 | 模拟盘 checklist 不完整 | 进入 dry-run 前缺门禁 | 新增 `docs/phase2_dry_run_checklist.md` |
| G8 | 数据新鲜度没有成为门禁 | paper 层可能读旧数据 | 在 phase2 summary 加 `data_freshness` |

## 第二阶段采用原则

1. 借鉴工程方法，不复制策略参数。
2. 把复杂度留在报告和配置里，不让核心策略文件无限膨胀。
3. 优先证明“稳定、可解释、抗成本”，再考虑收益。
4. 如果某个策略臂无法在多窗口和保守成本下站住，保持 `research_only`。
