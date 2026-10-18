# 111 — 引擎第九轮：心跳对睡着的人是死信 + 两套回合计数的口径

Status: fixed
Need-review: yes
Need-test-cases: yes

> 输入：票 109 §D1-2-E5（P1）与 §附（P2，241 差值）、票 106 §1/§3.1（E109 唤醒不变式）、
> 工件 `v4/runs/real-20261018T100115+0800-2284259-897204743.{json,checkpoint.json}`。
> 范围：`v4/harness/kernel.py`（`advance` 的 `private_wake` 分支 + `_fire_private_wake`
> + 可见性一行 + `schedule_private_wake` docstring）、`v4/harness/engine.py`（`_turns` 定义注释）、
> `v4/harness/prompt.py`（一句簿记注释）、`v4/harness/tests/test_historical_failures.py`
> （新 `PrivateWakeDeliveryGates` 2 支 + 台账 E110/E111 + 既有 extra 门里 2 条计数断言）、
> `v4/docs/V4-ENGINE.md` §3/§3.1/§7。**`v4/world/`、`v4/scripts/` 一行未动**；不新增动作种类、
> 不新增世界状态字段、不改任何裁定语义。

## 0. 一句话

心跳（`private_wake`）过去只在 `World.advance` 里被 `_commit` 成一条日志行——对睡着的目标它
既没有 `wait_woken` 也没有回合，是一封**没人读的死信**；现在它到点先提交事件、再走 E106 的
`wake_sleeper` 把睡者叫醒（目标已不在世界里则记一条带 reason 的 `private_wake_failed`）。
P2 的 241 差值不是漏记：`engine.turns` 只数 persistent actor 的 `_take_turn`，
`trace.agent_turns` 记全部 agent 回合（含 extra），**241 恰好是 29 名 extra 的回合数**，
口径写进 V4-ENGINE §7 并用既有 extra 门的两条断言钉住。

## 1. 任务 1（P1）：证据与判定

D1 工件里 `private_wake` 一共 4 条，逐条对着当时的目标状态复算：

| 事件 | 时刻 | 目标 | 目标当时 | 结果 |
| --- | --- | --- | --- | --- |
| #1836 | 12:34 | 唐小岚 | 醒着、空闲 | **1 个回合**，感知里带着这条 `private_wake`（正常路径） |
| #5183 | 20:41 | 林瑶 | 20:11 `wait 40800 sleep:true`（到 03/17 07:31） | **0 回合**，无 `wait_woken` |
| #5536 | 21:36 | 林瑶 | 21:06 `wait 36600 sleep:true`（到 03/17 07:16） | **0 回合**，无 `wait_woken` |
| #5564 | 21:40 | 陈默 | 21:10 `wait 36000 sleep:true`（到 03/17 07:10） | **0 回合**，无 `wait_woken` |

- 林瑶最后一个回合是 21:05、陈默是 21:09；21:10–22:00 的 74 个回合全部来自唐小岚（MC）、
  下棋大爷（NPC）与三名 extra，五名睡下的 MC（陈默、林瑶、辅导员、陈默妈、林瑶室友）**0 回合**。
- 22:00 检查点：陈默 `busy_until 2026-03-17T07:10, sleeping True`、林瑶 `07:16, True`，
  说明它们不是"被唤醒后又被静默吞掉"——唤醒**从未发生**。
- 对照：同一段里林瑶在 21:02 / 21:05 各有一条 `wait_woken`（同地社交事件，`wake_waiter` 路径），
  证明唤醒机制本身是通的，缺的是 `private_wake` 这一 kind 的触发点。

## 2. 根因（代码级）

修前 `World.advance`（`kernel.py:1225`）只有两个 kind 有专门分支（`move_hop`、`reminder_due`），
`private_wake` 落进通用 `_commit(job.kind, job.actor, …)`：事件被提交（可见性 `{target}`），
然后**什么也没发生**。唤醒路径只有两处：

- 引擎 `AsyncEngine._wake_waiters`（`engine.py:938`）——只处理 `world_event`（点名 → `wake_sleeper`）
  与 `WAKE_EVENT_KINDS`（同地社交 → `wake_waiter`）；
- `World.wake_sleeper` / `wake_waiter` —— 都正常，只是没有任何一条 `private_wake` 调用过它们。

结果是"事件到了世界，但目标在 `sleep` 里，`busy_until > now` 使 `has_wakeup` 为假 → 不 ready → 不派回合"。
票 106 的不变式（到达即回合）在 `private_wake` 上只对**醒着**的目标成立，票 109 说的就是这条缝。

## 3. 修法（kernel 一处分支 + 一个方法）

`World.advance` 新增分支：

```python
if job.kind == "private_wake":
    self._fire_private_wake(job)
    continue
```

```python
def _fire_private_wake(self, job) -> None:
    actor_id = job.actor
    if actor_id is None or actor_id not in self.actors:
        self._commit("private_wake_failed", actor_id,
                     {"reason": "actor_not_present"}, None)
        return
    self._commit("private_wake", actor_id, {}, None)
    self.wake_sleeper(actor_id)
```

- **先提交事件、后叫醒**：与 `world_event` 的先后一致（事件先落地，`wake_sleeper` 再留
  `wait_woken`），目标下一次 `poll` 同时看到两条，游标前移。
- **`wake_sleeper` 而不是 `wake_waiter`**：普通 `wait` 不被心跳打断（它自己的 `action_completed`
  会把事件送达，不是死信）；`sleep` 是"点名他的排程事件就是在叫他"（E106 判据），
  `wake_sleeper` 内部仍走 `wake_waiter` 的取消与清理，没有第二条唤醒实现。
- **失败不留死信**：目标不在 `self.actors` 时记 `private_wake_failed {reason: actor_not_present}`；
  可见性沿用 `{actor}`，那个 id 已不在世界里 → 没有任何活人收到它，只在 journal 里留下可审计的一行。
  （`extra_removed` 会取消该 extra 的排队作业，所以这一支是恢复/陈旧队列的防御路径。）
- 配套：`_visibility` 把 `private_wake_failed` 并入私有簿记那一组；`schedule_private_wake`
  docstring 与 `prompt._event_sentence` 的簿记清单各补一句，文档见 §5。

## 4. 红 → 绿（台账 E110）

`harness/tests/test_historical_failures.py::PrivateWakeDeliveryGates`（2 支）：

1. `test_a_private_wake_wakes_a_sleeping_mc_and_lands_a_turn` — 07:00 陈默 `wait 12h sleep:true`，
   心跳走**生产路径**（`mc_idle_heartbeat=1800`，bootstrap 的 `_rearm_heartbeat` 把 07:30 的
   `private_wake` 排进队列）。断言：`wait_woken` 恰好 1 条、在 07:30、actor 是陈默、可见性含他；
   07:30 恰有他 1 个回合且感知里同时有 `private_wake` 与 `wait_woken`；`sleeping` 归假；
   没有一条 `action_completed` 带 `sleep`（那段睡眠必须被结束，而不是自然完成）。
   *修前*：`0 != 1`（没有唤醒；07:00 入睡那一回合之后，到 07:33 停表为止一个回合也没有）。
2. `test_a_private_wake_for_an_absent_target_records_the_reason` — 给一个不在世界里的 id 排一条
   07:05 的心跳，`advance` 到 07:10。断言日志里恰好是 `("private_wake_failed", "actor_not_present")`，
   且它的 `visible_to` 与活人集合不相交。
   *修前*：它是 `("private_wake", None)`——与一条正常送达的心跳在日志里无法区分。

变异对照（就地删掉 `advance` 里那 3 行分支 → 只跑该类 → 还原并核对 md5）：

```text
md5 修后 harness/kernel.py = 8d225f411243a8e74530030b57ef7dc6
md5 变异（删 3 行）        = 3fc9f841a7210d6214b8dcacc5efadd4
PrivateWakeDeliveryGates 变异 → 2/2 FAILED（两条都红，见上面两条 *修前* 读数）
还原后 md5 = 8d225f41… ；该类 ×3 次 → 3/3 OK
```

## 5. 副作用与已裁定的边界（请评审重点看这条）

1. **心跳会打断长睡**：`_rearm_heartbeat` 在每个 MC 回合后重挂 30 分钟后的心跳，所以一名 MC
   一旦 `sleep` 超过 `mc_idle_heartbeat`，下一次心跳就会把他叫醒——这是"点名他的排程事件就是
   叫他"（E106）的直接推论，也是本票要求的语义。代价：默认 30 分钟意味着"睡到天亮"最多被切成
   30 分钟一段（每段一个回合）。要长睡不被打断，把 `mc_idle_heartbeat` 设为 0（或按剧本调大）；
   D1 这类"夜里全员睡"的剧本从此夜里会有 ~每 30 分钟一拍的 MC 回合，而不是 0。若 D2 认为夜里
   心跳太吵，那是 `mc_idle_heartbeat` 的剧本参数或另一条裁定，不在本票内。
2. **普通 `wait` 不被心跳打断**：事件留在游标里，等 `action_completed` 的回合送达——不是死信，
   也没有新增"心跳提前结束短等"的行为。
3. **恢复旧检查点会立刻生效**：22:00 检查点里陈默/林瑶仍在睡（`busy_until 07:10/07:16`），
   队列里另有一条 22:17 给唐小岚的 `private_wake`（她当时醒着，走原路径）；一旦续跑跨过下一次
   心跳，睡者会被叫醒——这是修后的预期行为，不是回归。
4. 没有新增动作种类、世界字段或调度器兜底；`_wake_waiters` 一字未改。

## 6. 任务 2（P2）：`engine.turns` vs `trace.agent_turns` —— 两个度量，不是漏记

**判定：两个不同度量。** 证据（同一工件逐行数）：

| 量 | 定义 | D1 读数 |
| --- | --- | --- |
| `engine.turns`（停机诊断，`Engine._turns`） | 只在 `_take_turn` 自增 → **persistent actor（mc+npc）** 的调度器回合；`max_turns` 与停机诊断用它 | **1479** |
| `trace.agent_turns` | `Trace.record_agent` 的每一行 → 全部 agent 回合，含 extra 的 `_extra_loop` 与 `result: none` 的诊断行；报告/轨迹复核用它 | **1720** |

- 差值 241 = `role == "extra"` 的回合数（29 名 extra；mc 708 + npc 771 = 1479）。
- 上一轮同族：`868 - 793 = 75` = 75 个 extra 回合。两轮都是"差 = extra 回合"，没有第三种成分。
- 因此**不修计数**，只补口径：`docs/V4-ENGINE.md` §7 新增「两套回合计数，两个度量（E111）」
  一条，写明各自含义、用途与差值的含义；`Engine._turns` 的定义注释落在 `engine.py:364`。
- 断言（不新增测试、不加运行时间）：`test_extra_turns_are_recorded_and_conversational` 里两条——
  ① 停机诊断里报告的 `engine.turns` == persistent 回合计（每个 persistent 回合在轨迹里恰好一行）；
  ② `len(trace.agent_turns) - engine.turns == len(extra 回合)`。若日后有人把 extra 塞进
  `_take_turn`（或漏记一个 persistent 回合），这两条会红。
- 台账：`E111`（"V4-ENGINE §7 计数口径裁定（无独立门）"，指向上面两条断言）——与 `I09` 一样
  是"非引擎门"条目，不伪装成独立 gate。

## 7. 回归读数（本票自己的验证）

```text
cd 契约失效时请勿喂猫/v4
python3 -m unittest discover -s harness/tests -p 'test_*.py'
→ Ran 694 tests in 102.5s — OK (skipped=1)     # 基线 692 + 本票 2 支；11:28:51 的当前树（seed 11:22:16），验证期间连跑 5 次全绿
python3 scripts/seed_lint.py --verbose → exit 0；末行 "seed lint OK: every named thing resolves …"
checkpoint 加载：
  loaded: now=2026-03-16T22:00:00+08:00 events=5624 version=5624 queue=77 actors=10
  陈默 busy_until=2026-03-17 07:10, sleeping=True
```

**如实记录一次中途红**：11:12–11:14 的第一次全量跑出现过 `NoteDeliveryGates` 2 条失败
（`'空白纸' unexpectedly found in item_locations`）。单跑确认是并行写者当时的
ticket 110 中间态：`world/manifest.yml` 的 12:00/18:00 补货 `add_item 空白纸` 与
`NoteDeliveryGates` 的 `world.advance()`（排空整个队列）撞在一起，那两条断言仍按"纸写成便条后
世上不再有 `空白纸`"写的。该写者 11:16 把补货 id 改成 `草稿纸`/`说明用纸` 后，同一条
`discover` 命令变为 **694 OK**；本票的 5 个文件与那次红无关（当时 red 的复现脚本显示
`office_paper_restock_noon → add_item 空白纸`）。

## 8. 残余与不做的事

1. **心跳频率是剧本旋钮，不是新机制**：本票没有引入"夜里不要叫醒人"的规则，也没有按地点/时段
   区分心跳；D1-2-E5 的另一半（"19:30 全员睡到次日"的世界约束，如熄灯/登记）仍需 seed 侧决定。
2. **失败分支是防御路径**：`remove_extra` 会取消已排队作业，所以 `actor_not_present` 只在
   "检查点/队列里的目标已不存在"时可能出现；没有为它再造一条可见性通道（journal 里有 reason）。
3. **`next_event_time()` 不看 `_cancelled`**：重挂心跳会在堆里留下一条已取消的同刻作业，
   票 106 的链内 clamp 可能停在那条"空拍"上（自测时见过一次：07:10 的链推进停在已取消的 07:30，
   随后心跳被重挂到 08:00）。它不吞事件、不改变唤醒语义，只是多一次空的 `advance`；本票未动它，
   登记给后续调度器清理（heap 惰性删除 + 队头判活的差）。
4. **`max_turns` 只约束 persistent 回合**：extra 回合不受 `max_turns` 闸；它们由对话与
   `extra_idle_timeout` 约束。已写进 §7；若日后要给 extra 设总量闸，那是一条新裁定。
5. 本票未 stage、未 commit 任何文件；证据绑定当前工作树
   （`kernel.py` md5 `8d225f41…`、`engine.py` `55186200…`、`prompt.py` `0fb86e8e…`、
   `test_historical_failures.py` `61c28d64…`、`V4-ENGINE.md` `a802c3d5…`）。
