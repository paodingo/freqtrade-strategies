# Ranging-short Router Carry Context 人工决策报告

## 当前结论

已冻结唯一运行时 context：`ranging_state_without_current_range_signal`。

该 context 表示正式 router 输出 `ranging`，但当前 4h candle 的 ADX、BB width 与 ATR 原始投票并未直接形成 ranging signal。它可能来自 hysteresis 状态保持或初始化状态；本报告不把所有命中样本武断归类为 hysteresis。

## 精确公式

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

评价前置条件为 `bb_width_mean_4h > 0` 和 `atr_mean_4h > 0`。阈值全部来自现有 `RegimeDetector`，没有进行 threshold search。

## 冻结身份

- Proposal fingerprint：`0def1fcab8671e6f43c6f66d1e84716ea0d76fd54e995825a1b066548a34bd3d`
- Compiled Campaign fingerprint：`26ad2ab3e756b8a0b9f7c63bc269d5a9c3028d87a3659b7bfa797fcf08f93330`
- Context contract fingerprint：`77f0cc0f52818fde63cb9e9bdd8b2703fc0d79e38ce0ec0d39bcc3a5d5b5ec7c`
- Slice Policy fingerprint：`bdd0944e67f62a5fd6b70b1d66fc2c373ee8ecd42d3a84ea410f6337612856d4`

## 四个既有切片

- `s01`：`inconclusive`
- `s02`：`positive_contributor`
- `s03`：`negative_contributor`
- `s04`：`negative_contributor`

时间切片只用于未来稳定性比较，不作为 market regime 标签。

## 当前不执行

当前预算为 `0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`。正式 `ranging_short_entry`、`RegimeDetector`、router、阈值和执行配置均保持不变。

未来如另获明确人工执行批准，上限为 `1 Candidate / 16 Development-only Backtests / 0 Validation / 0 Holdout`，复用四个冻结切片且不得增加第五个切片。Backtest 前必须通过 context coverage gate。
