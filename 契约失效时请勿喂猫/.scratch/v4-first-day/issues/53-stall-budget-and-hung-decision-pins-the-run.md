# 53 — 单个挂死的决策会钉死整个运行；stall 预算是累积等待而非连续无进展

Status: fixed
Need-review: yes
Need-test-cases: yes

## 观测（2026-10-01 01:50 重跑 `real-20261001T015004+0800-2399431-601906903`）

- 运行在模拟时钟 11:32 **冻结**，回合数停在 248（此后 15 分钟一个回合都没加），最终
  `[engine] stop: stall_budget_exceeded`，`RuntimeError: real experiment stopped before endpoint`，
  以及 `note: 2 agent errors survived as lost turns`。
- 冻结点状态（检查点）：`now=11:32`，三个角色 `busy_until` 在未来（唐小岚 11:38 / 林瑶 11:40 /
  陈默 11:44），`pending` 全为 None，`npcs_pending={}`，`waiting=[]`；回合 `result` 分布
  `{submitted: 245, agent_error: 2, none: 1}` —— **没有任何 `decision_timeout`**，说明那不是超时，
  而是"某个决策调用根本没返回"。
- **上游本身很快**：同一时刻用大提示直连代理实测 **1.8s** 返回。所以这不是"模型慢"。

## 根因（代码级）

1. **调度器被单个挂死任务钉死**：`_scheduler_loop` 在 `self._inflight` 非空时以
   `target = min(self._inflight.values())` 为目标，`while min(...) == target: await 2s`。
   只要**一个**决策永不返回、且它持有最老的 wake 时间，`min()` 恒定不变 ⇒ 永不离开等待分支
   ⇒ 时钟不再前进、停顿秒数一路累积。
2. **stall 预算语义错**：`self._stall_seconds` 是**累积等待**（`+= elapsed`，从不重置），阈值是
   `stall_budget_ratio * max_wall_seconds`（本次 0.60×7200=4320s）。它衡量的不是"连续无进展"，
   而是一个健康但慢的运行也会触顶；同时它把"真挂死"和"总等待多"混成一个信号。
   （`scripts/half_day_flow.sh` 里那句"stall 预算放宽到 60%"正是踩过这个坑后的加宽，属于治标。）
3. **没有真正的兜底超时**：`decision_timeout = provider.worst_case_seconds() * 8 + 5 ≈ 4325s(72min)`
   （`real_run.py:39`），比 stall 预算还长，所以挂死发生在任何超时之前；而 `_actor_loop` 里
   `await hung`（等一个已超时的调用收尾）**完全没有超时**，一个真挂死的线程会让该角色永远不再行动。
4. **不可诊断**：结束日志只有一行 `stall_budget_exceeded`，没有"谁在飞、飞了多久、哪个调用"，
   只能靠事后翻检查点重建现场。

## 验收方向

1. **stall 改成连续无进展**：记录"上一次世界前进（回合提交/世界推进）的时刻"，停顿 = now - last_progress；
   超过可配阈值才算停摆。健康的慢运行**永不触顶**；真挂死应在**可接受的短时间**内被判定（远小于 72 分钟，
   给一个默认值并可通过环境变量调整）。
2. **调度器不被单个任务钉死**：等待目标要能识别"该目标已超出容忍时限"并放行（例如以
   `min(inflight) + 容忍上限` 计算下一个推进点），不能让一个失联决策冻结全世界。
3. **决策与残留任务的兜底超时**：`decision_timeout` 必须是一个**有限且合理**的上界（例如 provider
   最坏情况 + 小额余量，而不是 ×8）；`_actor_loop` 里 `await hung` 必须有界，超界后放弃该线程并走
   既有 `_recovery`/发呆路径，让该角色还能继续参与后续回合。
4. **可诊断**：运行结束（含 stall/超时路径）时把"当时在飞的决策（角色、起始时间、已等时长）、
   最近的进展时刻、停顿定义与命中阈值"写进 trace/结束日志（并 `flush`），不必再靠翻检查点。
5. **不许放宽忙/动作时长语义**，也不许把"等待最慢的思考者"整体取消——容忍是**连续**的、有界的。

## 强制要求
- **先写红测试再改实现**，至少覆盖：
  (a) 一个决策永不返回（用可控的假 provider/假任务）→ 引擎在**有限时间**内放弃它，其余角色继续推进，
      运行最终仍能到达端点（不得整轮钉死）；
  (b) 健康但慢的运行（每回合都有小量等待、持续有进展）**不会**触发 stall；
  (c) 真无进展（世界停止前进）会在阈值后被判定为 stall，且结束记录里写明在飞的角色与时长；
  (d) `_actor_loop` 的残留等待有界：超界后该角色仍能在后续回合行动。
  历史失败登记进 `v4/harness/tests/test_historical_failures.py`（ledger 风格，写清 11:32 冻结观测与
  `min(_inflight)` 钉死机制）。
- 门禁全绿：`python3 -m unittest discover -s harness/tests -p 'test_*.py'`（当前 462 项）、`python3 scripts/seed_lint.py`、`git diff --check`；
  旧工件跑 `python3 scripts/check_milestones.py runs/real-20260930T160727+0800-522904-846830380.json --half d1-am`
  三个锚点必须仍 PASS（本 lane 不碰里程碑判定）。
- **不要跑真实 provider 故事**（用假 provider/假任务做确定性复现）；不要动 `world/` 种子、不要改
  inner/反重复/唤醒/字条/extra 逻辑。
- 提交一条，**只提交本 lane 文件**（显式 `git add`），信息注明 ticket 53。

## 汇报
- 停顿的最终定义、默认阈值与可调项；调度器放行规则；两处超时的具体上界
- 每条测试的"修前会红"证据与修后实测
- 三条门禁 + 检查器输出、提交 sha、遗留风险
- 另外告诉我：本次 11:32 挂死**是否可能是我们这轮改动引入的**（例如 ticket 45 的唤醒债、ticket 43 的
  提示注入、ticket 50 的 extra 恢复）——如果你在排查中发现任何指向新代码的证据，直接说出来，不要掩盖。
