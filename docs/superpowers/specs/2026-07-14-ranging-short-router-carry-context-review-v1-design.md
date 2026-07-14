# Ranging-Short Router Carry Context Review v1 设计

## 目标

让 Research Director 基于真实运行代码选择一个单一、可在运行时观测的 router context，并由 Campaign Compiler 只进行 dry-run 编译，为后续人工审批准备完整机器可执行规格。本阶段不创建 Candidate、不运行 Backtest，也不访问 Validation 或 Holdout。

## 已批准研究单元

- Proposal ID：`ranging-short-router-carry-context-review-v1`
- 风险等级：`medium`
- 正式研究对象：保留且不修改的 `ranging_short_entry`
- 唯一 router context：`ranging_state_without_current_range_signal`
- 决策来源：人工批准的只读 router 审计

该 context 精确定义为：

```text
regime_4h == "ranging"
AND NOT (
  adx_4h < 20
  AND (
    bb_width_4h <= bb_width_mean_4h
    OR atr_4h <= atr_mean_4h
  )
)
```

其中内部表达式严格复用 `RegimeDetector` 当前 raw ranging signal 的既有语义：ADX 投 ranging 票，并且 BB width 或 ATR 至少再投一张 ranging 票。它不引入新阈值，也不把时间切片解释为 market regime。

context 名称只描述可验证事实：router 输出 `ranging`，但当前 4h candle 的 raw signal 不直接支持 ranging。它可能来自 hysteresis 状态保持或初始化状态；报告不得把所有命中记录武断标记为 hysteresis carry。

## 方案选择

只读审计比较了三个方案：

1. `ranging_state_without_current_range_signal`：能直接区分“当前投票支持”与“router 仍保持 ranging”，信息增益最高，已选择。
2. 当前获得 ranging 多数票：与既有 router 输出高度重合，无法充分解释 temporal contribution 的方向变化。
3. ADX、BB width、ATR 全票 ranging：语义纯，但预期覆盖过窄，容易得到不可判定结果。

## 架构与数据流

### Research Director

Research Director 读取并验证：

- 当前 Research State；
- `ranging_short_entry` retention closure；
- 四个冻结 temporal slice 的有效结论；
- 当前 router structure map；
- `RegimeDetector` 与正式策略受保护哈希；
- Constitution、Evaluation Policy、Runtime、Dataset/Snapshot 哈希。

Director 只能生成一个 medium-risk Proposal。Proposal 必须将上述 context 公式、源文件位置、现有阈值来源、禁止范围和信息增益理由纳入 semantic fingerprint。

### Campaign Compiler

Compiler 验证 Proposal fingerprint 后生成不可执行的完整 Campaign Spec。当前编译预算固定为：

```yaml
max_candidates: 0
max_backtest_calls: 0
max_validation_accesses: 0
max_holdout_accesses: 0
execution_authorized: false
```

Compiler 还应生成一个独立的未来审批 envelope，但不得把它视为当前授权：

```yaml
max_candidates: 1
max_backtest_calls: 16
backtest_formula: 4 frozen Development slices x Baseline/Candidate x RUN-A/RUN-B
additional_temporal_slices: 0
max_validation_accesses: 0
max_holdout_accesses: 0
requires_new_human_execution_approval: true
```

### 审计产物

本阶段生成：

- Proposal JSON/YAML 与 semantic fingerprint；
- dry-run Campaign YAML、compilation metadata、experiment queue；
- router-context evidence matrix；
- implementation brief；
- human decision packet；
- Current Research State 与 Registry 的追加式更新；
- 中文 Markdown 和离线 HTML 报告。

HTML 必须使用 `lang="zh-CN"`，不得依赖 CDN、远程字体、外部脚本或网络资源。

## 单变量和未来 Candidate 边界

本阶段不创建 Candidate。未来只有在新的明确人工执行审批后，才允许创建一个 Candidate，并且只能：

- 保留全部原始 `ranging_short_entry` 指标、条件、tag 和 pre-gate mask；
- 计算已冻结的 `ranging_state_without_current_range_signal` mask；
- 仅在该 mask 为 true 的行，将 `ranging_short_entry` 对最终 `enter_short` 的贡献 gate 为 false；
- 保持其他 signal group、router 输出、阈值、entry/exit、ROI、stoploss、leverage、protections、fee、funding 和执行配置不变。

不得修改正式策略、`RegimeDetector`、正式 router 或已冻结 Candidate。不得重新开启 threshold 或整体分支删除研究。

## 覆盖门与停止条件

未来执行前必须从 Development-only 输入计算 context/pre-gate mask 覆盖。以下任一情况必须在 Backtest 启动前停止：

- context 公式、Proposal fingerprint 或 Campaign fingerprint 漂移；
- context 所需列缺失或不可计算；
- context 与 `ranging_short_entry` pre-gate mask 的交集为零；
- context 不能区分至少一个“当前 raw ranging signal”样本和一个“无当前 raw ranging signal”样本；
- Candidate 同时改变第二个 branch、threshold、router 输出或交易语义；
- 正式策略、Policy、Runtime、Dataset/Snapshot 或受保护 manifest 漂移；
- Validation/Holdout 预算非零；
- 工作树不干净、Registry integrity 失败或 readiness guard 失败。

覆盖门只判断实验是否可识别，不得基于收益、Profit Factor、回撤或未来结果选择 context。

## 未来评价范围

如后续另获执行批准，16 次 Development-only Backtest 必须复用现有四个冻结时间切片。每个切片执行 Baseline/Candidate 的 RUN-A/RUN-B，并先证明角色内复现，再比较：

- context 命中 candle 数；
- context 与 `ranging_short_entry` pre-gate mask 的交集；
- 被隔离 signals 和变化 trades；
- total/long/short trades；
- return、Profit Factor、最大回撤、fee、funding；
- tags、exit reasons、remaining branch behavior；
- normalized trade hash。

所有 delta 使用 `Candidate - Baseline`。时间切片只用于检验稳定性，不得充当 router context 标签。

## 决策状态

未来 Campaign 的确定性结果只能使用：

- `router_context_negative_contributor`
- `router_context_positive_contributor`
- `router_context_mixed_temporal_dependency`
- `router_context_redundant`
- `router_context_contribution_inconclusive`
- `router_context_execution_invalid`

任何结果都不得自动修改或删除正式 `ranging_short_entry`，不得自动申请 Validation，也不得自动执行下一 Proposal。

## 测试设计

实施阶段必须先写失败测试，再修改 Director/Compiler。测试至少证明：

- Proposal 只包含一个 context，且公式与批准设计逐字段一致；
- context 阈值全部来自现有 `RegimeDetector`，未引入 threshold search；
- Proposal 与 Campaign fingerprint 覆盖 context 公式和受保护输入；
- 当前预算严格为 `0/0/0/0` 且 `execution_authorized: false`；
- 未来 envelope 严格为 `1 Candidate / 16 Development-only Backtests / 0 Validation / 0 Holdout`；
- 四个冻结切片顺序和 fingerprint 不变；
- 没有 Candidate、Backtest execution 或新 results 路径；
- 正式策略、router、Policy、Runtime、Dataset/Snapshot 不变；
- 中文 Markdown/HTML 可生成，HTML 不含外部网络依赖；
- Guard 只允许本 Proposal 的小型治理、Compiler、测试和报告路径。

完成前运行 targeted、Research、Stage、readiness、Portable baseline、Registry integrity 和全部冻结哈希校验。只允许精确路径暂存；不得 push、merge 或启动后续 Campaign。

## 完成定义

只有以下条件全部满足，dry-run 编译准备才算完成：

1. Proposal 和 Campaign 都有可重算且匹配的 fingerprint；
2. 唯一 context 与本设计完全一致；
3. Candidate、Backtest、Validation、Holdout 均为零；
4. 正式 `ranging_short_entry` 和全部冻结输入未变化；
5. 中文 Markdown/HTML 决策包已生成；
6. 所有验证通过；
7. 逻辑 commit 已建立且工作树干净；
8. 未 push、未 merge、未自动执行任何 Campaign。
