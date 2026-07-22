# Research R189 Guard Exception

该例外仅允许 `open-source-learning-v1` 的精确知识资产路径：十五个知识Schema、一个固定检索评测集、构建/检索/自动召回脚本、provider-neutral租约队列、Campaign经验草稿渲染器、来源刷新/生命周期/检索评测/健康检查维护器、统一人工复核包、追加式复核事件入口、无决策权限的证据绑定建议、一个指纹绑定反馈复核批次与一个指纹绑定人工经验晋升批次及其精确归档、六张已晋升候选经验卡、七个测试文件、六个固定commit来源快照、十二张clean-room机制卡、九张正式内部经验卡、一个有界Discovery上下文和精确审计报告。Knowledge Broker 只允许向Researcher任务包注入每类最多四条的确定性Top-K结果，并在既有知识血缘表登记幂等的 `retrieved_for` 关系；Campaign结果先进入 `pending_human_review` 草稿；上游变更先形成 `pending_human_approval` 提案；建议不能自动转为决定；经验晋升必须绑定明确的人类批准与候选指纹，禁止自动晋升，已拒绝来源更新不能改变固定提交。

不允许 `research/knowledge/**`、`reports/audits/**` 或 `scripts/**` 等目录通配；不保存上游完整源码，不复制策略参数或实现，不创建Candidate，不运行Backtest，不访问Validation/Holdout，也不修改正式策略、配置、退出、仓位、杠杆、止损、ROI或任何实盘/dry-run表面。
