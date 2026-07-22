# 研究发现人工评审简报

- Discovery run: <code>discovery-run-66c83d41c84027eb</code>
- Shortlist fingerprint: <code>26d2dfd09598b4fd7a604dd871c109de5acdcd1124a0671d40c0af94d7b1aa2b</code>
- 结论: <code>research_recommended</code>
- 说明: 依据冻结评分政策，建议优先评审排名最高的最小研究测试；评分仅表示研究优先级。

## 1. BNB/XRP 1h—4h 多周期一致性审计

- 研究问题: 若 BNB/XRP 的 1h—4h 一致性显著低于 BTC/ETH 且跨分段持续，则多周期条件的跨币种可比性不足；否则该前置风险被否定。
- 当前理由: 比较各币种 1h 聚合结果与已封存 4h 数据在方向、波动和极端区间上的一致性。
- 机制: 多周期一致性决定高周期状态信息能否与低周期观察形成可比较的时间结构。
- 最强反证: ETH 的稳定复现没有证明经济泛化，说明新增币种的描述相似也不能直接支持策略。
- 数据准备度: <code>ready</code>；futures\-dev\-btc\-usdt\-usdt\-20240101\-20240830\-v2；futures\-dev\-eth\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-bnb\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-xrp\-usdt\-usdt\-20240101\-20240830\-v1
- 最小测试: 用固定 UTC 桶将 1h 数据聚合为 4h，与封存 4h 数据做无策略一致性比较并列出异常。
- 成本: experiments=0, wall_clock_minutes=30, compute_class=<code>low</code>
- 停止条件: 任何步骤需要回测、Candidate、策略修改或参数搜索；任何步骤需要 Validation、Holdout、私有 API 或网络下载；任何必需 Development 数据流完整性校验失败
- Critic 结论: <code>pass</code>
- 评分: <code>0.938500</code>
- 不确定性: 不检验策略 informative merge。；不涉及信号或收益。；共同市场冲击；资产波动尺度差异；成交活动结构差异；单一时间窗口偏差
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

## 3. BNB/XRP 状态占用与可达性迁移

- 研究问题: 若 BNB/XRP 在多数时间分段持续缺失 BTC/ETH 可达的状态区域，则共享状态路由的跨币种描述基础不足；若占用结构相近则否定。
- 当前理由: 依据现有只读条件图定义，设计各市场状态代理的占用率、持续时间和方向不平衡描述。
- 机制: 市场状态的可达性差异可能先于任何交易结果暴露跨币种结构偏移。
- 最强反证: ETH 的稳定复现没有证明经济泛化，说明新增币种的描述相似也不能直接支持策略。
- 数据准备度: <code>ready</code>；futures\-dev\-btc\-usdt\-usdt\-20240101\-20240830\-v2；futures\-dev\-eth\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-bnb\-usdt\-usdt\-20240101\-20240830\-v1；futures\-dev\-xrp\-usdt\-usdt\-20240101\-20240830\-v1
- 最小测试: 先冻结条件图中可由允许来源重建的无交易状态代理，再计算四币种分段占用、持续时间和不可达项；无法重建则停止。
- 成本: experiments=0, wall_clock_minutes=45, compute_class=<code>low</code>
- 停止条件: 任何步骤需要回测、Candidate、策略修改或参数搜索；任何步骤需要 Validation、Holdout、私有 API 或网络下载；任何必需 Development 数据流完整性校验失败
- Critic 结论: <code>pass</code>
- 评分: <code>0.809500</code>
- 不确定性: 不能读取策略代码或生成交易信号。；状态代理可能遗漏执行语义。；共同市场冲击；资产波动尺度差异；成交活动结构差异；单一时间窗口偏差
- 来源溯源: Class A <code>research/data/snapshots/futures-dev-bnb-usdt-usdt-20240101-20240830-v1/manifest.yaml</code> — BNB Development 数据已封存且必需数据流零缺口。；Class A <code>research/data/snapshots/futures-dev-xrp-usdt-usdt-20240101-20240830-v1/manifest.yaml</code> — XRP Development 数据已封存且必需数据流零缺口。；Class A <code>research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json</code> — ETH 行为可复现但不证明跨币种经济泛化。；Class A <code>research/director/current-research-state.json</code> — BNB/XRP 已获 Development\-only 描述性研究授权。

批准研究方向不代表盈利判断，也不授权创建 Candidate 或执行 Campaign。