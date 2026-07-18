# BTC MVP / V11.29 冷归档

本目录是从旧工作树 `D:\code\freqtrade-strategies` 提炼出的只读历史归档。旧工作树原来挂在 `codex/btc-mvp-system`，分支 tip 为 `5a5d42611d268124263b053fb34ea107a5787564`。该 tip 已完全包含在 `master` 中；真正未进入 Git 的内容主要是实验代码与生成报告。

## 保留内容

- `v1129-selection-evidence.json`：从 V11.29 最终报告提炼的验收门槛、验收结论和九个评估窗口。
- `v1129-selection-config.json`：去除 API 口令、数据库位置等运行时细节后的关键选择配置。
- `strategy-lineage.md`：从 87 个 `RegimeAwareV*.py` 类提炼出的主干谱系和关键分支决策。
- `btc-system-design.md`：独立 `btc_system` 原型的架构、风险约束、结果与弃用原因。
- `manifest.json`：原始来源、SHA256 和归档完整性信息。

## 未保留内容

- 约 785 MB 的重复或生成型回测报告、HTML、signal audit 与钱包曲线。
- Freqtrade 数据文件、SQLite、Feather、ZIP、截图、临时目录与 Python 缓存。
- 已被 `master` 中运行快照取代的策略源码副本。
- 旧 Dashboard、旧通知脚本和旧部署脚本；这些实现已被当前自动发布和可观测体系替代。
- 原始配置中的开发 API 用户名、密码和 JWT 值。

## 证据边界

原始 V11.29 最终报告是有效 JSON，但它引用的九个底层回测结果在旧工作树中均已不存在。因此本归档证明“当时的汇总结论是什么”，不能单独证明九次回测可重放。生产使用的 V11.29 源码和依赖已另行固定在 `runtime_snapshots/v1129/`。

本归档不参与运行、策略加载或部署。
