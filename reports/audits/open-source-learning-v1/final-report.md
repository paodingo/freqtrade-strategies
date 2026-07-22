# 开源量化知识与学习闭环审计报告

## 当前结果

用户明确批准的“6 项通过、0 项拒绝”已完成指纹绑定晋升。6 张候选经验卡全部进入正式 Knowledge Broker 目录，其中 `ranging-short-temporal-retention-v1` 替换旧卡 `ranging-short-branch-negative-contributor-v1`。

正式经验卡由 4 张净增至 9 张；新知识快照为 `86b5d8da34601a7ff59e94029ccf43914d83b14f06764962425875cdbd85ecbc`。

## 晋升与自动调动

- 6 张候选状态均为 `promoted`，拒绝 0 张，待晋升 0 张。
- Registry 新增 6 条 `lesson_promotion` 人工复核事件，总复核事件为 17 条。
- 旧经验卡生命周期标记为 `superseded`，替代卡为 `ranging-short-temporal-retention-v1`。
- Broker 仍按每类最多 4 条确定性 Top-K 自动调动正式知识。
- 固定检索评测已同步替代关系并恢复 `8 / 8` 命中。

## 治理边界

晋升依据绑定人工批准指纹 `22a664f33bd89f4d780a0ec40a7d6d42e3d0d88f18aa642b2d0720668bc94b1e`。自动经验晋升仍为 `false`，本次执行不授予交易执行权限。

本期创建交易 Candidate `0`、运行 Backtest `0`、访问 Validation/Holdout `0 / 0`。正式策略、正式基类、配置和风险语义未修改，也没有 dry-run 或实盘操作。

## 验证

- 相关测试：`108 passed / 0 failed`。
- `guard_harness_diff`、`guard_no_secret_material`、`guard_trading_surface`：全部通过。
- Director Registry Schema：v10；完整性：`ok`。
- 学习闭环健康状态：`healthy`，待人工复核项目 0。
