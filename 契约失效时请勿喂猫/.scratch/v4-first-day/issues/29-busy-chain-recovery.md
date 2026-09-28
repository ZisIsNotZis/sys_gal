# 29 — 忙碌链与 continue_action 恢复语义

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes
Blocked by: 27-d1am-gpt6-trajectory-review.md（发现来源）

## 缺陷与验收
首段 611 轮中 43 次 busy 拒绝、12 次无效 `continue_action`，多次在行动尚未完成时让模型获得新轮次；例如班长 08:23 双短信第一条已排程、第二条 busy，08:24 误试 continue_action；宿管 08:43 move、08:44 再 move busy。`engine.py:_execute_chain` 故意按其他角色思考地平线截断动作完成时间，使同一链的后续耗时调用被拒；`kernel.affordances` busy 时只列 wait，但内核又拒绝 busy 时启动 wait；`engine._ready_now` 先认 force_turn 后判 busy。`continue_action` 只适用真正 pending 的中断，不适用于正常忙碌。

先用最小回归复现不同路径：两次串行 text、移动中收到提醒、speak 自动等回复后再 wait、force_turn 与 busy 同时成立。修复应保持慢思考者地平线约束，不无界推进时间；同时不能向不可行动角色提供自相矛盾的 wait affordance 或误导性恢复信息。可选择延迟后续链调用并逐项回填结果，或显式终止后续链并告知真实 busy_until/何时自动完成、无需 continue_action；改变行为需更新工具说明和历史回归。目标不是消灭正常的不可达/无联系人错误，而是减少状态矛盾和盲目重试。

- 2026-09-28, pi：首段为复现工件，暂停续跑；错轮细节见 issue 27。
