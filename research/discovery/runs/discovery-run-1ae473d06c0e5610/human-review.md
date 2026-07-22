# 研究发现人工评审简报

- Discovery run: <code>discovery-run-1ae473d06c0e5610</code>
- Shortlist fingerprint: <code>e1897e4be00e9c9c67c5c207f11df5076d10946df1deb19a46cbea09b73ab128</code>
- 结论: <code>research_recommended</code>
- 说明: 依据冻结评分政策，建议优先评审排名最高的最小研究测试；评分仅表示研究优先级。

## 1. BNB/XRP 收益与波动分布迁移画像

- 研究问题: 若 BNB/XRP 在多数冻结分段的波动与尾部幅度相对 BTC/ETH 保持稳定排序，则后续跨币种研究可采用分层而非单一尺度；若排序频繁翻转则否定。
- 当前理由: 只计算四个 Development 币种的收益、实现波动、尾部幅度和成交量分位数，形成同窗描述矩阵。
- 机制: 资产波动尺度和尾部厚度差异可能改变固定信号条件的可达性，但描述差异本身不授权策略调整。
- 最强反证: ETH 的稳定复现没有证明经济泛化，说明新增币种的描述相似也不能直接支持策略。
- 数据准备度: <code>ready</code>；futures\-dev\-btc\-usdt\-usdt\-20240101\-20240830\-v2；futures\-dev\-eth\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-bnb\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-xrp\-usdt\-usdt\-20240101\-20240830\-v1
- 最小测试: 读取 1h/4h Development 数据，按预先固定的全窗和四个时间分段输出分位数与稳健尺度；不生成信号或交易。
- 成本: experiments=0, wall_clock_minutes=35, compute_class=<code>low</code>
- 停止条件: 任何步骤需要回测、Candidate、策略修改或参数搜索；任何步骤需要 Validation、Holdout、私有 API 或网络下载；任何必需 Development 数据流完整性校验失败
- Critic 结论: <code>pass</code>
- 评分: <code>0.939500</code>
- 不确定性: 描述统计不能证明策略泛化。；不包含订单簿和成交成本。；共同市场冲击；资产波动尺度差异；成交活动结构差异；单一时间窗口偏差
- 来源溯源: Class A <code>research/data/snapshots/futures-dev-bnb-usdt-usdt-20240101-20240830-v1/manifest.yaml</code> — BNB Development 数据已封存且必需数据流零缺口。；Class A <code>research/data/snapshots/futures-dev-xrp-usdt-usdt-20240101-20240830-v1/manifest.yaml</code> — XRP Development 数据已封存且必需数据流零缺口。；Class A <code>research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json</code> — ETH 行为可复现但不证明跨币种经济泛化。；Class A <code>research/director/current-research-state.json</code> — BNB/XRP 已获 Development\-only 描述性研究授权。

## 2. BNB/XRP 资金费率与标记价格压力画像

- 研究问题: 若 BNB/XRP 的极端资金费率与标记价格压力共现率持续高于 BTC/ETH，则衍生品持仓环境存在可描述的币种层差异；否则否定。
- 当前理由: 利用封存 8h funding\_rate 与 mark 流描述极端资金费率、标记收益和波动压力的共现。
- 机制: 永续合约资金压力可能与标记价格波动共同刻画拥挤状态，但不等同于可交易基差。
- 最强反证: ETH 的稳定复现没有证明经济泛化，说明新增币种的描述相似也不能直接支持策略。
- 数据准备度: <code>ready</code>；futures\-dev\-btc\-usdt\-usdt\-20240101\-20240830\-v2；futures\-dev\-eth\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-bnb\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-xrp\-usdt\-usdt\-20240101\-20240830\-v1
- 最小测试: 固定分位数定义后计算 8h funding\_rate 与 mark 变化的共现表、持续时长和分段稳定性。
- 成本: experiments=0, wall_clock_minutes=30, compute_class=<code>low</code>
- 停止条件: 任何步骤需要回测、Candidate、策略修改或参数搜索；任何步骤需要 Validation、Holdout、私有 API 或网络下载；任何必需 Development 数据流完整性校验失败
- Critic 结论: <code>pass</code>
- 评分: <code>0.902000</code>
- 不确定性: 不包含现货价格、订单簿或真实资金成本。；不得推导套利或持仓建议。；共同市场冲击；资产波动尺度差异；成交活动结构差异；单一时间窗口偏差
- 来源溯源: Class A <code>research/data/snapshots/futures-dev-bnb-usdt-usdt-20240101-20240830-v1/manifest.yaml</code> — BNB Development 数据已封存且必需数据流零缺口。；Class A <code>research/data/snapshots/futures-dev-xrp-usdt-usdt-20240101-20240830-v1/manifest.yaml</code> — XRP Development 数据已封存且必需数据流零缺口。；Class A <code>research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json</code> — ETH 行为可复现但不证明跨币种经济泛化。；Class A <code>research/director/current-research-state.json</code> — BNB/XRP 已获 Development\-only 描述性研究授权。

## 3. BNB/XRP 1h—4h 多周期一致性审计

- 研究问题: 若 BNB/XRP 的 1h—4h 一致性显著低于 BTC/ETH 且跨分段持续，则多周期条件的跨币种可比性不足；否则该前置风险被否定。
- 当前理由: 比较各币种 1h 聚合结果与已封存 4h 数据在方向、波动和极端区间上的一致性。
- 机制: 多周期一致性决定高周期状态信息能否与低周期观察形成可比较的时间结构。
- 最强反证: ETH 的稳定复现没有证明经济泛化，说明新增币种的描述相似也不能直接支持策略。
- 数据准备度: <code>ready</code>；futures\-dev\-btc\-usdt\-usdt\-20240101\-20240830\-v2；futures\-dev\-eth\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-bnb\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-xrp\-usdt\-usdt\-20240101\-20240830\-v1
- 最小测试: 用固定 UTC 桶将 1h 数据聚合为 4h，与封存 4h 数据做无策略一致性比较并列出异常。
- 成本: experiments=0, wall_clock_minutes=30, compute_class=<code>low</code>
- 停止条件: 任何步骤需要回测、Candidate、策略修改或参数搜索；任何步骤需要 Validation、Holdout、私有 API 或网络下载；任何必需 Development 数据流完整性校验失败
- Critic 结论: <code>pass</code>
- 评分: <code>0.897500</code>
- 不确定性: 不检验策略 informative merge。；不涉及信号或收益。；共同市场冲击；资产波动尺度差异；成交活动结构差异；单一时间窗口偏差
- 来源溯源: Class A <code>research/data/snapshots/futures-dev-bnb-usdt-usdt-20240101-20240830-v1/manifest.yaml</code> — BNB Development 数据已封存且必需数据流零缺口。；Class A <code>research/data/snapshots/futures-dev-xrp-usdt-usdt-20240101-20240830-v1/manifest.yaml</code> — XRP Development 数据已封存且必需数据流零缺口。；Class A <code>research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json</code> — ETH 行为可复现但不证明跨币种经济泛化。；Class A <code>research/director/current-research-state.json</code> — BNB/XRP 已获 Development\-only 描述性研究授权。

批准研究方向不代表盈利判断，也不授权创建 Candidate 或执行 Campaign。