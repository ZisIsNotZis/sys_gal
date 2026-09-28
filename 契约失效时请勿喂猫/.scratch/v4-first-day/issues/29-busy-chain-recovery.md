# 29 — 忙碌链与 continue_action 恢复语义

Status: ready-for-human
Need-review: yes
Need-test-cases: yes
Blocked by: 27-d1am-gpt6-trajectory-review.md（发现来源）

## 缺陷与验收
首段 611 轮中 43 次 busy 拒绝、12 次无效 `continue_action`，多次在行动尚未完成时让模型获得新轮次；例如班长 08:23 双短信第一条已排程、第二条 busy，08:24 误试 continue_action；宿管 08:43 move、08:44 再 move busy。`engine.py:_execute_chain` 故意按其他角色思考地平线截断动作完成时间，使同一链的后续耗时调用被拒；`kernel.affordances` busy 时只列 wait，但内核又拒绝 busy 时启动 wait；`engine._ready_now` 先认 force_turn 后判 busy。`continue_action` 只适用真正 pending 的中断，不适用于正常忙碌。

先用最小回归复现不同路径：两次串行 text、移动中收到提醒、speak 自动等回复后再 wait、force_turn 与 busy 同时成立。修复应保持慢思考者地平线约束，不无界推进时间；同时不能向不可行动角色提供自相矛盾的 wait affordance 或误导性恢复信息。可选择延迟后续链调用并逐项回填结果，或显式终止后续链并告知真实 busy_until/何时自动完成、无需 continue_action；改变行为需更新工具说明和历史回归。目标不是消灭正常的不可达/无联系人错误，而是减少状态矛盾和盲目重试。

- 2026-09-28, pi：首段为复现工件，暂停续跑；错轮细节见 issue 27。
- 2026-09-28, pi：已在 685eab4（issue 28 单人字条修复）之上实现本票，未启动 provider story。修复选择是保持决策地平线、对因地平线仍忙而未运行的后续链调用逐个返回带真实完成时刻与原调用重试形状的 `not executed` 结果；不会额外推进时间或要求 `continue_action`。`force_turn` 不再绕过 `busy_until`；普通 busy 不显示 `wait`，只有真实 pending 中断显示 continue/abandon。角色消息显示本人当前动作/截止时刻、独立的“等待回应”状态或中断恢复选项；寻址说话在一个 tick 后结束，再另行等待回应。

  已加回归并先确认旧代码失败：busy+force_turn 曾让 `_ready_now` 提前返回 true；地平线为 1 tick、`move(target="far")` 需 2 tick 时，同轮 `speak(to=["b"],...)` 曾只得到含糊的“正在忙”；自动回应等待在可见上下文里没有状态。现在上述 targeted tests 通过，另测了真实 `busy_until` / `wait` 拒绝、pending 与普通 busy 区别、按 call id 回填、不 ratchet、说话结束时刻与回复等待、`read(item="wrong")` 建议手边文档 `read(item="ledger")`。schema 键名误用也会给出保留实体值的合法工具调用。

  文档已同步 `V4-AGENT-INTERFACE.md`、`V4-ENGINE.md` 与工具说明。最终验证：`OPENAI_MODEL=unit-test-model python3 -m unittest discover -s harness/tests -p 'test_*.py'`（v3）218 OK；v4 同命令 330 OK（1 skipped）；`python3 scripts/seed_lint.py --verbose` OK；`python3 -m harness.dry_run` 到 3/27 21:30；`git diff --check` 通过。未运行 provider story。v4 全套通过但 `test_resume_run` 的 mock callable 与 V4Session 的 `chat_with_tools` 协议不符，测试把 27 轮记为 lost turns，并在 runner 停止时输出未取回后台 task 的 AttributeError；该 resume test seam 未纳入 issue 29 修复。等待独立 review/parent 验收。
