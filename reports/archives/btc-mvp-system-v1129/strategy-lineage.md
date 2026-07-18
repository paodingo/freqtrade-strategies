# RegimeAware 策略谱系提炼

旧工作树包含 87 个 `RegimeAwareV*.py` 策略类。它们大多是实验节点，不应继续作为 87 个并列生产策略维护。下面只保留对 V11.29 形成过程有解释力的主干和分支决策。

## 主干

```text
V6/V6.1
  -> V6.2-V6.6：趋势、震荡边缘、分批仓位和基础保护
  -> V6.6 AlphaRisk：引入 alpha 风险过滤
  -> V6.6.1-V9.9：回撤保护、反弹陷阱、资金费率、账户风险与信号评分
  -> V10.2：回到可靠的 V6.6 趋势做空核心，移除弱侧臂
  -> V10.3-V10.8.2：盈利延伸、多币对与 pair contribution 分层
  -> V11.0/V11.1：高攻击约束和过滤后的做空核心
  -> V11.5：成本感知的做空核心
  -> V11.13/V11.15/V11.16：反弹陷阱、衰竭下跌和选择性山寨币仓位
  -> V11.18：波动冲击小仓剪枝
  -> V11.22：ADA capitulation 半仓
  -> V11.24：反弹追空风险缩仓
  -> V11.27：两个已确认陷阱的微仓化
  -> V11.29：保留 V11.27 获利簇，对残余负贡献簇微仓/探针化
```

V11.29 的直接继承关系为：

```text
RegimeAwareV66AlphaRisk
  -> RegimeAwareV102ReliableShortCoreAlpha
  -> RegimeAwareV103ProfitRunnerShortCoreAlpha
  -> RegimeAwareV107MultiPairShortCoreAlpha
  -> RegimeAwareV108PairTieredShortCoreAlpha
  -> RegimeAwareV1082PairTieredShortCoreAlpha
  -> RegimeAwareV110HighAttackShortCore
  -> RegimeAwareV111HighAttackFilteredShortCore
  -> RegimeAwareV115CostAwareShortCore
  -> RegimeAwareV1113MicroReboundTrapGuard
  -> RegimeAwareV1115ExhaustedSelloffRiskSizer
  -> RegimeAwareV1116SelectiveAltRecoverySizer
  -> RegimeAwareV1118VolatilityShockSmallShortPruner
  -> RegimeAwareV1122AdaCapitulationHalfSizer
  -> RegimeAwareV1124ReboundChaseSizer
  -> RegimeAwareV1127DualTrapMicroSizer
  -> RegimeAwareV1129ResidualDragMicroSizer
```

## 主要旁支

- V7.x-V8.x：账户级停机、区间样本和 rebound trap 的密集搜索。
- V9.x：移除弱区间空单，尝试 squeeze guard、资金费率和风险/止损距离定仓。
- V10.4-V10.6：更宽盈利目标和质量门控，未成为最终主干。
- V11.2/V11.3：breakout 与多臂 router，未进入最终 V11.29 主干。
- V11.10-V11.12：弱币对禁用/冷却和全市场 squeeze 冷却。
- V11.17/V11.19-V11.21/V11.23：不同的尾部风险与 capitulation 处理。
- V11.25/V11.26/V11.28：chop、core recoil 和 selective drag 的替代缩仓方案；V11.29 最终回到 V11.27 主干。

## 归档判断

生产运行所需的 V11.29 依赖闭包已固定在 `runtime_snapshots/v1129/strategies/`。旧工作树中的完整 87 类更适合作为实验谱系而非运行代码，因此本归档保留关系与来源哈希，不复制所有历史实现。
