# 106 — 驱动层 P0：长睡一回合把整个夜吞掉（唤醒不可达）

Status: fixed
Need-review: yes
Need-test-cases: yes

> 输入：票 103 §D1-E1（P0 现象）、`reports/m1-day1-acceptance.md` 夜间段、票 101 §2（E106 睡眠，本轮新增能力）、
> 工件 `v4/runs/real-20261018T085705+0800-2116654-169068128.{json,checkpoint.json}`（22:00）、
> `v4/runs/real-20261018T062031+0800-1910732-547128242.checkpoint.json`（窗口 5b 的 18:00 状态）。
> 范围：`v4/harness/engine.py`（一处 clamps）、`v4/harness/kernel.py`（一句过时注释）、
> `v4/harness/tests/test_historical_failures.py`（新门 + 台账 E109）、`v4/docs/V4-ENGINE.md` §3.1、
> `v4/docs/V4-AGENT-INTERFACE.md` §2.1 一句。**`v4/world/`、`v4/scripts/` 一行未动**；不新增世界状态字段、不新增动作种类、不改任何裁定语义。

## 0. 一句话

D1 的夜不是“模型睡了”，而是**一次回合内的时钟推进把整个世界推到了 endpoint**：18:35 林瑶 `wait 28800 sleep:true`
那一回合把时钟从 18:35 直接推到 22:00，18:40–22:00 的一切（六条夜间排程、三条 `private_wake`、四条 `reminder_due`、
两条动作完成）都被记进事件日志而没有任何人拿到回合，循环顶部的 `_stop_check` 随即停表；唤醒路径本身
（`_wake_waiters` / `wake_sleeper` / `_ready_now` / `has_wakeup`）全部正常，它们只是再没被轮到。

## 1. 根因（代码级）

修前 `AsyncEngine._execute_chain`（`harness/engine.py:1505`）在提交一个耗时动作后，把世界时钟推进到该动作的
完成时刻，只夹了两个上界：

```python
limit = a.busy_until
if self._stop_horizon is not None:      # run 的 endpoint
    limit = min(limit, self._stop_horizon)
horizon = self._horizon_bound()         # 别的角色正在思考时，钉在它的时刻 + 1 tick
if horizon is not None:
    limit = min(limit, horizon)
if limit > world.now:
    world.advance(until=limit)          # ← 一次推进，逐条提交、不派任何回合
```

* `_horizon_bound()` 只看**在途决策**（`_active_inflight()`，`engine.py:681`）。D1 18:34 之后没有任何人在思考，
  于是 `limit = min(03/17 02:35, 22:00) = 22:00`。
* `world.advance(until=22:00)`（`kernel.py:1206`）把队列里 22:00 之前**所有**作业弹出来逐条提交：排程事件照旧
  `_commit`、`reminder_due` 照旧 `_fire_reminder`、`private_wake` 照旧提交（可见性仍是 `{target}`），但**没有任何
  一个角色被 poll、被唤醒、或被排进回合**——这些事件只是变成了日志行。
* 吃掉的正是那一整段：19:00 `counselor_evening_intake`、19:02/19:05/19:05 三条 `private_wake`、19:10、19:30
  `mom_evening_call`、20:00 `library_last_hour`、20:40、21:30 打烊、四条 `reminder_due`、18:45 宿管阿姨的
  `wait_woken`、18:46 辅导员的 `enter`，以及 18:39 陈默 `wait 300` 的完成。
* 推进结束后回到 `_scheduler_loop`（`engine.py:598`）顶部，第一个动作是 `_stop_check`
  （`engine.py:575`）：`world.now (22:00) >= stop_at` → `stop_at_reached`。**回合永远没有机会被派出**。

时间线（22:00 检查点逐字段复核，`analyze_e109_wakeup.py load`）：

| 时刻 | 世界 | 有人出回合 | 感知游标 |
| --- | --- | --- | --- |
| 18:34 | 陈默 `wait 300`、林瑶最后一回合 | 是 | 陈默 2908 |
| 18:35 | 林瑶 `wait 28800 sleep:true`（→ 03/17 02:35）——**这一回合的链内 `advance(until=22:00)`** | — | — |
| 18:36–22:00 | 上述 20+ 条事件全部落进日志 | **0 个回合** | 游标停在 2908 / 2899 / 2891 |
| 22:00 | `day_boundary` + `stop_at_reached` | — | `busy_until: None, sleeping: False`（醒着、空闲） |

由此把 D1-E1 的四条候选逐一排除：

1. **不是 `wake_waiter`/`sleeping` 的交互**：`wake_waiter`（`kernel.py:724`）只对 payload `action == "wait"`
   生效，`sleep: true` 的 wait 也是 `wait`，所以同地社交事件仍能叫醒（票 101 的裁定）；
   `wake_sleeper`（`kernel.py:746`）对点名 `world_event` 生效。两者在 D1 里都没被调用过——因为事件到达时
   没有人 poll。
2. **不是 `busy_until` 清零后没重新入队**：`_complete`（`kernel.py:2079`）清空 `busy_until`，该角色的
   `action_completed` 对它自己可见 → `has_wakeup`（`kernel.py:769`）为真 → `_ready_now`（`engine.py:916`）为真。
   修后 18:00→18:40 那段续跑里每个角色的完成节拍都换出回合（陈默 17、林瑶 22、唐小岚 18…，见 §4(b)）。
3. **不是 `has_wakeup`/`_unseen_social_event` 判错**：`has_wakeup` 用游标 `_cursor`（事件序号）比 `event_log[cursor:]`，
   D1 22:00 时陈默游标之后仍有 9 条对他可见的事件——`ready` 判定是**对的**，只是没被问过。
   `_unseen_social_event`（`kernel.py:572`）只用在 `submit` 的 wait 分支（防止“边思考边等”把一条还没读到的社交
   事件睡过去），与本现象无关。
4. **不存在“大家都空闲但调度器认为无人在等”的死角**：`_any_ready`/`_has_pending_turns`（`engine.py:674/694`）
   就是用 `_ready_now` 逐个数；空闲且游标落后 = ready。缺的不是判定，是**时钟走过头**。

**为什么票 101 的门没拦住它**：`SleepWaitGates③`（`test_a_named_scheduled_event_wakes_a_sleeper_and_a_broadcast_does_not`）
用的是旧 callable agent，走 `AsyncEngine._submit`（`engine.py:1998`）——那条路径根本不推进时钟。
真实回合（`make_persistent_agent_v4` → `session_obj`）走的是 `_execute_chain`。同一棵树上两条路径，
门只盖了不生产的那一条。本轮的新门用带 `session_obj` 的 stub 补上这一段。

## 2. 修法（3 行 + 一句注释）

`harness/engine.py:1723`（`_execute_chain` 的链内推进）再加一个上界——**世界的下一个排程作业**：

```python
next_job = world.next_event_time()
if next_job is not None:
    limit = min(limit, next_job)
```

不变式：**一个回合内的时钟推进不得越过世界上下一个排程作业**。排程表上的一拍由调度器自己走、由调度器把
那一拍的回合派出去。它同时覆盖三类“交出回合”的作业（`world_event`、`private_wake`、`reminder_due`）以及
别人的 `action_completed` / `move_hop`——因为任何一条都会在提交后让某个角色变成 ready。没有新增 kernel API、
没有新增字段；`world.next_event_time()` 本来就是队头（`kernel.py:564`）。

配套（不改变行为）：

* `harness/kernel.py:724` `wake_waiter` 的 docstring 原文写“``sleep`` … 不可唤醒”，与票 101 的裁定（同地社交
  事件照旧结束睡眠）和实现都不符——改成陈述现行语义，并指出 `wake_sleeper` 是“点名事件”的额外路径。
* `docs/V4-ENGINE.md` 新增 **§3.1 唤醒与回合调度的不变式**（不变式、D1 证据、三层含义、看守测试）。
* `docs/V4-AGENT-INTERFACE.md` §2.1「串行链」那句补上“也不越过下一个排程作业”。

**为什么不是“每 N 分钟强制唤醒所有人”**：根因是时钟跳过头，不是没人叫醒。心跳（`mc_idle_heartbeat`）本来就在，
它在 D1 里也照常发出（19:02/19:05），只是到达时世界已经不在那一拍。修的是推进上界，不增设任何唤醒机制。

## 3. 红 → 绿（台账 E109）

`harness/tests/test_historical_failures.py::WakeReachabilityGates`（2 支，均走 `_execute_chain` 真实路径）：

1. `test_a_private_wake_still_reaches_an_awake_actor_while_another_sleeps` — 07:15 陈默入睡 12 小时（那一刻
   没有别人在思考，正是 D1 的形状），07:30 有一条给唐小岚的 `private_wake`：
   *修前*：世界被一次推到 stop_at，唐小岚 07:30 之后 0 个回合；*修后*：她在之后的第一拍拿到回合，且感知里带着
   那条 `private_wake`（游标前移）。
2. `test_a_named_scheduled_event_wakes_a_sleeper_on_the_chain_path` — 07:10 陈默入睡，08:00 一条 `target`
   点名的 `world_event`：*修前*：既没有 `wait_woken` 也没有回合；*修后*：`wait_woken` 恰好落在 08:00，08:00 有
   一个回合，且那一回合的感知里带着那条 `world_event`。

变异对照（就地删掉那 3 行 → 只跑该类 → 还原并核对 md5）：

```text
md5 修后 harness/engine.py = 567401c8275a03882a0a49e986ff4a30
md5 变异（删 3 行）        = ddecb2669e3b43f44689a01e18009092
WakeReachabilityGates 变异 ×3 次 → 3/3 FAILED (failures=2)（两条都红）
还原后 md5 = 567401c8… ；该类 ×12 次 → 12/12 OK（同一轮早期版本；删 3 行前也做过 5/5 红）
```

## 4. 真工件回归（本票最重要的证据）

复算入口：`python3 ../.scratch/v4-first-day/analyze_e109_wakeup.py {load,short,night,night_all}`
（stub provider 直接替换 `resume_run.resume` 的 `call`，所以走的是生产路径 `V4Session` + `_execute_chain`；
stub 按世界消息里的 `在场：<名字>(you)` 分派，并带协议要求的非空 `inner`）。

**(a) D1 22:00 检查点加载**

```text
loaded D1 22:00 checkpoint: now=2026-03-16T22:00:00+08:00, events=2936, version=2936, queue=68, turns=793
awake+idle: 陈默 {busy_until: None, sleeping: False, cursor: 2908}
            唐小岚 {None, False, 2899}  辅导员 {None, False, 2891}  食堂大妈 {None, False, 2891}
            (睡着: 林瑶 busy 03/17 02:35, 班长 busy 03/17 05:06)
```

——与票 103 的读数一致：夜里的死信不是“角色在忙”，而是**没人被 poll**。

**(b) 18:00 检查点短程续跑（endpoint 18:40，stub 只 `wait 60`）**

```text
/tmp/e109-short.json reason=stop_at_reached events=4893 turns=1742 time=2026-03-16T18:40:00+08:00
resumed-segment turns = 72（无 lost turn），18:00–18:40 每个角色按自己的节拍出回合
```

**(c) 唤醒驱动回合（18:00 → 20:00，全部角色第一拍睡 12 小时 = D1 的形状）**

| | 修前（变异） | 修后 |
| --- | --- | --- |
| 续跑段回合数 | **6** | **40** |
| 世界 | 18:00/18:06 之后一次跳到 20:00 | 18:00 → 19:59 逐拍推进 |
| `wait_woken` | **0 条** | 18:06 辅导员（同地 `enter`）、**19:30 陈默**（点名事件） |
| 19:30 `mom_evening_call` | 无回合、无唤醒 | 陈默 19:30 一回合；感知 = `[18:07 action_started, 18:30 world_event(rain_stops), 18:52 private_wake, 19:30 world_event, 19:30 wait_woken]` |

最后一行正好把两条语义同时摆在明处：**18:52 的心跳到达时他在睡**（没有回合，只是一条留在游标里的事件——
票 101 的裁定），**19:30 的点名事件叫醒他并换来回合**（本轮要保的不变式）。18:30 的全场广播
`rain_stops` 没有叫醒任何人，也符合 E106。

## 5. 回归读数

* `python3 -m unittest discover -s harness/tests -p 'test_*.py'` → **Ran 692 — OK (skipped=1)**
  （票 103 的基线 690 + 本票新增 2 支；跑过一次 702，是并行写者当时在树上多出的 10 支，随后又被他们收回——
  计数随树变化，**绿的结论两次一致**；票 103 记录的两条间歇族本轮未触发）。
* `python3 scripts/seed_lint.py --verbose` → **exit 0**（`seed lint OK`），warning 与窗口 2–6 同族，无新增。
* 本票未 stage、未 commit 任何文件；证据绑定当前工作树（`harness/engine.py` md5 `567401c8…`、
  `harness/kernel.py` 只多了一句 docstring 修正）。

## 6. 残余与不做的事

1. **链的降级面变大**：以前“同一回合里前一个动作没做完就调用第二个世界动作”只在别人思考时被拒；现在只要
   队头那一拍（含别人那条 60 秒 wait 的完成）落在自己动作的窗口内，后续的世界动作就会被拒（回执照旧给出真实
   完成时刻与重试形状，属 §2.3 已裁定的“争用下降级为一回合一个动作”）。D1 全天 868 个回合里只有一个回合
   提交过 2 个以上的世界动作（14:43 林瑶 `read`×3），实测影响接近于零；若日后模型开始大量链式动作，这条要重新量。
2. **睡着的角色仍会被同地的社交事件叫醒**（`enter`/`speak`/`knock`…经 `wake_waiter`）。这是票 101 的既定裁定
   （`sleep` 只是 `wait` 的一个参数），本票只把 `wake_waiter` 的过时 docstring 改正，没有改行为。若 D2 觉得
   夜里“一有人回宿舍就醒”太脆，那是另一条裁定（要动 E106 的语义）。
3. **上界是“队头”，不是“下一个会唤醒人的作业”**：队列空时 `next_event_time()` 返回 `None`，这一夹就不存在，
   但这正好是没有事件会被吞的时刻。没有更细的分类（一开始试过只认 `world_event`/`private_wake`/`reminder_due`
   三类，新增的门第一条就红：别人的 `action_completed` 同样会让他变成 ready，漏掉它就是同一类洞）——
   上界取队头，规则只有一条，也不依赖心跳开关。
4. **不变式靠 clamp 而不是调度器守卫**：`_execute_chain` 是唯一一处回合内的 `advance`，未来若有人再写一处
   回合内推进，必须先看 §3.1 与 `WakeReachabilityGates`。本票没有在 `World.advance` 上动刀（那会把 kernel
   的通用时钟能力改坏）。
5. **不改 `_scheduler_loop` 的 endpoint 语义**：`stop_at_reached` 仍然是“到点即停”，本票只保证到点之前
   每一拍都派得出去；没有新增“到点时还欠回合就继续跑”的后门。
