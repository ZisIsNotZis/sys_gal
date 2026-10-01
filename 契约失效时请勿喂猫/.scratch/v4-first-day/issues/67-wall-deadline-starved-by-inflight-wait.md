# 67 — 墙钟上限被"等在飞决策"的内层循环饿死：运行超过 2h 仍未停

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes

## 观测（2026-10-01 第二次对照跑 `real-20261001T163024+0800-629102-384711601`）
- 该 run 启动于 16:30:24，`V3_MAX_WALL_SECONDS` 默认 **7200s（2h）**，即应在 **18:30:24** 由
  `wall_clock_deadline_reached` 结束。
- 实测到 **18:35 仍在运行**（模拟时钟 11:00、401 回合，仍在推进），说明墙钟检查被跳过。
- 该 run 期间日志有多次 `[engine] in-flight decision released after ~120s`（上游挂起，ticket 53 的放行机制在工作）。

## 根因（代码级，待复核确认）
`_scheduler_loop` 的墙钟检查在**外层**每轮一次；而当 `self._inflight` 非空时，代码进入内层循环
`while self.stop_reason is None and self._inflight and min(self._inflight.values()) == target:`
等待最老的在飞决策。放行机制（ticket 53）把超时决策标记为 released 但**仍留在 `_inflight`**，
于是 `min()` 可长时间保持不变 → 内层循环长时间不返回 → **外层的墙钟/停止条件检查得不到执行**。
（`_await_activity` 分支同样是 `await`，但它有 1s 超时，问题相对小。）

## 影响
墙钟上限是**安全属性**（"无论如何 2 小时必须停"），被饿死意味着一个慢/抖动严重的运行可能远超预算，
在无人值守时尤其危险（本次就是无人值守跑了几十分钟）。

## 验收方向
1. **墙钟检查不可被饿死**：内层等待循环必须周期性复查墙钟与 stall 条件（或把这些检查下沉到内层），
   保证"到点必停"。同样适用于其它可能长时间不返回的等待点。
2. **诊断**：因墙钟停止时，结束诊断里要显示实际超出的时长（便于发现同样问题）。
3. **回归（先红后绿）**：构造一个"在飞决策永不返回但一直被 released"的夹具，断言引擎在墙钟到点后
   **有限时间内**结束并给出 `wall_clock_deadline_reached`（今天必红）。
4. 历史失败登记进 `test_historical_failures.py`。
5. 顺带核对：`max_turns` 与 `stop_at` 是否也会被同一内层循环饿死（若会，一并修）。
