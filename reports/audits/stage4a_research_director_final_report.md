# Stage 4A Research Director Final Report

- 状态：`completed`
- 分支：`stage4a/research-director`
- 起始 checkpoint：`16153cf5a7f6342a722e51c33cf46df20f7d3af6`
- Current Research State：`research-state-21acfc2e39ba874b`
- 状态冲突：`0`
- 生成证据 commit：`69849bc000af3b5790ccc154f484ff5a9c9e6f59`
- 该 commit 后版本控制范围状态：staged `0`、unstaged tracked `0`、unignored untracked `0`

## 结果

Director 基于真实 Registry、Policy、Dataset/Snapshot、Runtime、closure、invalidation/recertification 和 Git 状态生成 3 个 Proposal，并拒绝 4 个不合格方向。最高优先级为 `cross-pair-data-readiness-audit-v1`，风险 `low`，信息增量 `0.92`，路由仅为 `auto_approvable_future`，没有实际批准。

已生成 `stage4a-cross-pair-data-readiness-audit-v1` 完整 Campaign Spec，指纹为 `5950353be61676185d53d7eced07fcbf094ccf10d68f2c60f0812f5820da9581`。Spec 已复用 `scripts/research_control.py:load_campaign` 校验；`compile_mode: dry_run`、`execution_authorized: false`。

## 治理与边界

- Constitution 保持 `pending_human_review`。
- `regime-aware-ranging-thresholds-v1` 保持 `closed_evidence_exhausted / A_keep_current`；相邻阈值搜索被拒绝。
- 未执行 Campaign、未创建 Candidate、未修改策略、未运行回测/Hyperopt、未访问 Validation/Holdout、未启动 Stage 4B。
- Registry 只记录状态、提案、拒绝、路由和编译事实，不包含虚假执行结果。

## 验证

- Targeted tests：`18/18 pass`
- Research tests：`48/48 pass`
- Readiness：Harness diff、secret、trading surface 三项通过
- Full baseline verifier：`errors: []`；仅保留 8 个 Python 和 4 个 Node 已锁定失败
- Python compile / Node syntax：通过
- Source / Director Registry integrity：`ok / ok`
- `RegimeAwareV6.py` SHA-256：`1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509`

首次在独立 worktree 直接运行 baseline 时，缺少未复制的 ignored Stage 3 artifacts，verifier 因此识别出新增缺失文件。随后在临时 detached worktree 中复制 6 组约 21 MB 的本地产物副本进行 artifact-complete 验证，结果 `errors: []`；临时 worktree 已精确移除，原工作树未修改。
