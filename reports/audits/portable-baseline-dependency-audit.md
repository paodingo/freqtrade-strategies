# Portable Baseline Dependency Audit

原 Campaign preflight 在 Candidate 创建前以 `portable_baseline_assets_unavailable` 停止；这是基础设施前置条件阻塞，不是 Campaign 或策略失败。Candidate、Backtest、Validation、Holdout 计数均为 0。

## 分类结论

| 类别 | 数量 | 处理 |
| --- | ---: | --- |
| A Hermetic Test | 2 | 从提交的最小 rows 在临时 SQLite DB 中初始化，不读取全局 Registry。 |
| B Minimal Historical Fixture | 6 | 保存 1 个旧数据完整性投影、1 个 2141-byte 决策报告和 2 个 361-byte reachability 记录；重复引用不重复复制。 |
| C Authoritative External Asset | 0 | 无测试真正需要大型外部资产。 |
| D Invalid/Over-coupled Design | 4 | 将完整 D3B/D4B/E1 结果树依赖替换为来源已验证的最小语义投影。 |

12 个原始异常的逐项 test ID、exception、缺失资产、可变性、来源与修复类别记录在配套 JSON 中。

## Portable 设计

`clean_worktree_portable` 只读取已提交 fixture、经 Manifest 水合的只读 pack，以及测试期间创建的临时 SQLite DB。Pack 共 8 个文件，不包含旧 `research/results` 树、旧 DB、Candidate、运行日志、绝对路径、secret 或账户信息。

Builder 仅接受 Contract 中固定的 authoritative checkpoint 和逐项 source SHA。Hydrator 拒绝不匹配目标、symlink/junction 与未声明文件；Verifier 检查 bytes、SHA-256、semantic fingerprint、只读属性、敏感内容和绝对路径。

`authoritative_asset_audit` 保留为维护者只读来源复核入口，不作为普通 Candidate Campaign 的日常前置条件。
