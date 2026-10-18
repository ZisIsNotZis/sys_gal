# 104 — 两枚负载敏感门禁的确定性化（extra 回合时序 / 静默放弃自动续接）

Status: fixed
Need-review: yes
Need-test-cases: yes

范围：只动 `v4/harness/tests/`（`test_historical_failures.py` 的 E73 夹具与台账条目、
`test_engine.py` 的 `test_silent_abandonment_auto_continues_pending_action`）。
未改任何产品代码、`world/`、`scripts/`。产品侧残留（正常 advance 路径的钉钟缺口）
仍归票据 74。

本票包含两个夹具（第二个由上级 2026-10-18 授权一并收掉，理由：它已在票据 73 §6.1
立案，且实际在卡"大运行前必须单跑确认"的预门）：

- **门 A** `test_extra_turns_are_recorded_and_conversational`（E73）：世界时钟在路人
  回答在途时被线程调度推进，导致到达 tick / 答话延迟不确定。
- **门 B** `test_silent_abandonment_auto_continues_pending_action`：b 的 interrupt
  与 a 的 move 谁先落地取决于线程到达顺序，输的一方"中断无事可悬挂"，
  `action_resumed` 断言随机 False。

## 1. 现象（观察史，均为本票复现或既有存档）

- 门 A：全量 discover 间歇红，断言形状三种：
  `arrived[0].time.strftime("%H:%M") == "07:01"` 得 `07:02`；
  `first_answer - arrived <= 60s` 得 `120s`；
  `len(extra_turns) == 2` 得 `1`（偶尔 `0`）。
- 既有存档活证（2026-10-16 全量）：`v4/logs/full-suite-20261016-run4.log:140`
  `FAIL: test_extra_turns_are_recorded_and_conversational`，
  `:145` 断言行、`:147` `AssertionError: '07:02' != '07:01'`
  （同遍 `Ran 575 tests … FAILED (failures=2, skipped=1)`）。
- 本票复现（2026-10-18，全部为**未改动前**的夹具）：
  - 单跑子进程 40 次：0 红（冷进程、单测独跑不触发）。
  - 同进程热跑（`/tmp/detprobe/probe2.py`，边跑全量 discover 制造负载）：
    30 次里 3 红——`1 != 2`、`0 != 2`、`120.0 not less than or equal to 60`，
    每次带完整时间线（见 §2.3）。
  - 全量 discover 2 遍：run1 `Ran 690 tests in 207.8s OK (skipped=1)`；
    run2 红，但红的是 `test_silent_abandonment_auto_continues_pending_action`
    （票据 73 §6.1 已登记的另一枚负载敏感测试），不是本夹具。

## 2. 根因（判据 + 时间线证据）

### 2.1 引擎的时钟规则（代码出处）

- `engine.py:717` `_horizon_bound()` 只取 **`_active_inflight()`**（持久角色的决策）
  +1 tick，**不含 `_extra_inflight`**。
- `engine.py:687` `_quiescent()` 含 `_extra_inflight`，但它只守两条路：
  `next_event is None` 与 `next_event > stop_at`（`engine.py:616-633`）。
- 正常推进路（`engine.py:661-666`）只被 `_has_pending_turns()` 守：只要没人"欠一个
  回合"，队列里有 ≤ 当前时刻 + 1 tick 的事件就会 `world.advance(until=next_event)`。
  **路人回答在途不构成"欠回合"**——于是它思考期间时钟照走。

### 2.2 为什么旧夹具里"每 tick 都有事件"

旧夹具把整座 pack 世界搬上台（陈默/林瑶/唐小岚 3 个 mc + 7 个 npc），并且每个角色
的兜底动作是 `wait 3600`。而本 seed 的 `world.longest_wait_seconds = 900`：

```text
python3 -c "... world.submit(Intention('陈默','wait',{'duration_seconds':3600},...))"
→ wait 3600 REJECTED: 单次等待不能超过 900 秒。…
→ wait 900 accepted, busy_until = 07:15:00
```

`wait 3600` 被拒后走引擎的拒绝修复（`engine.py:1332-1334`：`name == "wait"` 时补
`{"duration_seconds": TICK_SECONDS}`），**实际落成 1 tick 的 wait**；1 tick wait 又会被
同地说话（`_wake_waiters`）提前唤醒，于是每个角色每 tick 都在"完成—再等—被唤醒"，
队列里几乎每 tick 都有事件。这正是旧夹具把世界时钟交给线程调度的机理。

### 2.3 时间线（未改动夹具的真实红）

形态 A —— 到达晚一 tick、路人 0 回合（probe2 run 5）：

```text
cast 07:00 inflight={陈默,林瑶,唐小岚} next=07:10
cast 07:00 inflight={陈默,唐小岚}      next=07:01   ← 林瑶先提交了 1 tick 动作
advance 07:00→07:01 (1 event)                      ← 陈默仍在决策中，bound=07:01 允许这一步
cast 07:01 阵 inflight={陈默,唐小岚} pending_turns=True
advance 07:01→07:02 (3 events)
spawn 07:02  ← extra_arrived 落在 07:02（断言期望 07:01）
extra_turn+ 07:02 … 时钟继续推进（07:03/07:04/07:05），run 在 07:06 停下 → extra_turns=0
```

形态 B —— 答话晚两拍（静默世界里也复现，证明"非法 wait"是独立来源）：

```text
07:00 陈默 action_started speak → 07:01 action_completed（到达 07:01）
07:01 extra_turn+（路人开始思考，extra_inflight=07:01）
队列：07:02 action_completed 陈默 speak      ← 追问（旧夹具 07:01 立即追问）
advance 07:02；队列：07:03 action_completed 陈默 wait  ← wait 3600 被修复成 60s
advance 07:03
extra_turn- 07:03    ← 答案落到 07:03，比到达晚 120s → 断言红
```

### 2.4 被排除的候选（如实记录）

- **`asyncio.run` 每次新建事件循环**：不是来源。同一进程热跑里，未改动夹具仍红
  （每次 run 都是新 loop），而改动后的夹具在同进程 200/200 绿；loop 只决定回调顺序，
  真正决定 tick 的是"队列里有没有事件"。
- **`sample_extra` 的系统熵**：只决定路人姓名/fragment，不产生世界事件；红过的几次
  采样到的路人各不相同（马大姐/林学长/赵大姐/陈大姐/朱大爷），tick 形状一致。
- **共享 daemon 池冷启动**：票据 73 已修（预热 + `extra_idle_seconds` 抬高），但
  0.66s 的单跑 40 次全绿、全量仍间歇红 → 冷启动不是 07:02/120s 两形态的原因；
  池延迟只是"墙钟延迟"的量级来源，不是耦合本身。
- **世界时钟在决策在飞时按 tick 推进**：**是**，且是唯一根因（§2.1-2.2）。

## 3. 修法（只改夹具，三条规则）

`test_extra_turns_are_recorded_and_conversational`：

1. **台上只留陈默**（`del world.actors[other]`）。旁人的 1 tick wait、环境唤醒都是
   队列事件的来源；本门测的是 extra 路径，不是同场群演。
2. **空等必须合法且长于场景**：`idle_seconds = world.longest_wait_seconds`（900），
   并断言 `idle_seconds > 6 * TICK_SECONDS`。否则 `wait 3600` 会被拒绝修复成 1 tick
   wait，往窗口里再塞一个事件（形态 B 的第二个 tick 就是它）。
3. **追问只在听到回答之后发出**（agent 读 `perception["events"]` 认那句回答），
   且路人的第一句话被**世界状态屏障**卡住：stub 轮询
   `世界.actors["陈默"].current_action.payload.action == "wait"`（1ms 粒度、15s 上限），
   等陈默真的停住了才吐答案。这不是 sleep，是把"谁先动"从线程竞争改成场景约定。

于是路人思考窗口**不欠任何事件**（队列里只剩 > stop_at 的 900s wait 与 pack 的 07:10
世界事件），能钉住时钟的只剩 `_quiescent()` 里的 `_extra_inflight`——正是票据 22
裁决 4 要求的那条钉钟。

### 3.1 断言变化为什么不是削弱（逐条）

| 断言 | 改前 | 改后 | 为什么检测力不降 |
|---|---|---|---|
| 到达 tick | `=="07:01"` | `=="07:01"`（不变） | 到达 tick 现在完全由场景决定（07:00 提问、07:01 完成、无人能推钟） |
| 答话延迟 | `<= 60s`（允许 1 tick 抖动） | **`first_answer.time == arrived[0].time`**（0 tick） | 更强：本场景不欠任何事件，1 tick 就是钟在路人脚下跑了；票据 22 的缺陷（旧轨迹晚 17 个世界分钟、7:12 的 ask 7:16 才回来）在改后会晚 5 tick（07:01→07:06，见 M1）或 2 tick（M2），必红 |
| 两回合 / 一次 spawn / `calls==2` | 原样 | 原样 | E1/E2/E3 检测面未动 |
| 旧夹具的群演 | 有 | 无 | 群演带来的不是检测力，而是"每 tick 一个事件"的不确定性；且它抓的其实是 §2.1 的
正常推进路缺口（票据 73 §6.2a），那条缺口从未被这个夹具**确定性地**抓到（50% 概率），
改由票据 74 修完后另立确定性夹具 |

补充一条显式的**前提断言**：`stub.mc_parked` 为假时直接报"世界在路人思考时已经走动
（world now / arrivals / provider calls）"，把 ticket 22 的失败本体说出来，而不是让
下面 `next(...)` 抛 StopIteration。

## 4. 验收证据（2026-10-18，全部本票当场跑）

改后（绿）：

```text
# 单测
python3 -m unittest harness.tests.test_historical_failures.HistoricalFailureGates.test_extra_turns_are_recorded_and_conversational
Ran 1 test in 0.18s — OK        # 子进程连跑 40/40 绿
# 热跑（同进程）
python3 /tmp/detprobe/warm.py 200      → 0 reds in 200 warm runs
python3 /tmp/detprobe/warm.py 200（8 个 CPU 占用进程压着） → 0 reds in 200 warm runs
# 模块
python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
Ran 236 tests in 102.9s — OK
# 全量（本票验收标准：连续 10 遍全绿）
python3 -m unittest discover -s harness/tests -p 'test_*.py'   ×10 见 §4.2
```

### 4.1 变异对照（隔离副本 `/tmp/detprobe/mutant_*`，产品代码只在副本里改）

- **M1 = 拆掉票据 22 的钉钟**（`_quiescent()` 去掉 `not self._extra_inflight`）：

```text
FAILED (failures=1)
AssertionError: False is not true : 陈默 never parked in its idle wait: the world
moved on while the stranger deliberated (world now 07:06, arrivals ['07:01'],
provider calls 1)
```

  即：世界冲到 stop_at，路人的回答根本没落地。原夹具在本变异下也**不是确定性红**
  （要恰好撞上静默相位），改后是确定性红。

- **M2 = "答话晚两拍"**（在路人提交动作前让世界推进 `2 * TICK_SECONDS`）：

```text
FAILED (failures=1)
  File ".../test_historical_failures.py", line 1782, in test_extra_turns_are_recorded_and_conversational
    self.assertEqual(first_answer.time, arrived[0].time)
AssertionError: ... 7, 3, ... != ... 7, 1, ...
```

  两 tick 迟到被 `answer == arrival` 精确断住（改前 `<=60s` 需要 2 tick 才红，同样红）。

- **基线**：未变异的隔离副本跑同一夹具 `Ran 1 test — OK`。

### 4.2 全量 discover 连跑 10 遍

**第二轮（09:47:43 起，每遍记录门禁文件 hash）：10/10 绿**

```text
run1  hash=d7b36736  Ran 692 tests in 106.7s  OK (skipped=1)
run2  hash=d7b36736  Ran 702 tests in 132.8s  OK (skipped=1)
run3  hash=d7b36736  Ran 702 tests in 135.0s  OK (skipped=1)
run4  hash=d7b36736  Ran 692 tests in 123.5s  OK (skipped=1)
run5  hash=d7b36736  Ran 692 tests in 124.9s  OK (skipped=1)
run6  hash=1910fd0f  Ran 692 tests in 101.9s  OK (skipped=1)
run7  hash=1910fd0f  Ran 692 tests in 102.8s  OK (skipped=1)
run8  hash=1910fd0f  Ran 692 tests in 116.2s  OK (skipped=1)
run9  hash=1910fd0f  Ran 692 tests in 117.3s  OK (skipped=1)
run10 hash=1910fd0f  Ran 692 tests in 111.2s  OK (skipped=1)
日志：/tmp/detprobe/ten2/run*.log
```

（run5→run6 之间另一个写者又改了一次 `test_historical_failures.py`（票 106 的 E109 门），
hash 从 d7b36736 变为 1910fd0f；本票的两处改动在现文件里逐字未变（已 diff 校验），
`test_engine.py` 全程 sha256=b49ce38e 未变。）

**第一轮（已作废但如实记录，09:25:52 起）**：run1–run8（门禁文件 sha256=55f8010a，
690 tests）全绿；run9（另一写者新增 2 个测试后，692 tests）绿；run10 红——红的是那个
**新增的外部测试** `WakeReachabilityGates.test_a_named_scheduled_event_wakes_a_sleeper_on_the_chain_path`
（E109，票 106；`wait_woken` 为空），本票两枚门在同遍全绿。该外部测试单跑 3/3 绿、
同进程热跑 100/100 绿，且 run10 跑的过程中该文件正在被写（09:45:58 mtime），
属另一张票的工作区，本票不动它。

## 5. 门 B：`test_silent_abandonment_auto_continues_pending_action`

### 5.1 根因（活证）

夹具：a 走 120s 的 `move`；b 用 `interrupt=("a",)` 说一句话挂起它；a 的下一次决策
抛 `RuntimeError`；引擎的静默放弃应自动续接挂起的 move（`engine.py:2053-2063`
`_recovery` 里 `if a.pending is not None: world.submit(continue_action)`）。

两个角色都是 mc，bootstrap 同时给它们第一回合，而**决策一律走 `_run_blocking`
线程池**：a 的 move 与 b 的 speech 谁先提交，取决于哪个 worker 先拿到 GIL。
若 b 先提交，`interrupt=("a",)` 时 a 还没有在途动作 → 没有 `action_interrupted`，
也就没有 `action_resumed` → `assertTrue(any(...action_resumed))` 随机 False。
世界时钟此时是钉住的（a 决策在飞 → bound=+1 tick，而 move 完成在 +120s），
所以这不是"时钟跑了"，而是**提交顺序**本身没被约定。

复现（隔离副本里把 b 换回旧写法 `Scripted([...])`，同进程热跑 300 次、8 核压满）：

```text
70 reds in 300 warm runs of the PRE-FIX fixture   （首个红：AssertionError: False is not true）
```

与全量发现的特征一致（本票红猎与 10 遍验收的 run1 都是它，且它单跑多为绿）。

### 5.2 修法

b 的第一个回合在吐 intencion 前，用**世界状态屏障**等 a 的 move 真的在途
（轮询 `world.actors["a"].current_action.payload.action == "move"`，1ms 粒度、2.0s 上限
——低于引擎 `decision_timeout=5`），然后才说那句话；b 仍只说一次（第二回合起返回
`None`，与旧 `Scripted` 一次脚本等价）。断言**一条未改**，另加一条前提断言
`observed["b_saw_move"]`：屏障没等到就直说"中断无事可悬挂，这次跑什么也没证"。

### 5.3 验收与变异

```text
python3 -m unittest harness.tests.test_engine.EngineTests.test_silent_abandonment_auto_continues_pending_action
5/5 OK（子进程）；同进程热跑 200 次 0 红；8 核压满 300 次 0 红
python3 -m unittest discover -s harness/tests -p 'test_engine.py'   → Ran 31 tests — OK
```

变异对照（隔离副本 `mutant_m3`，把 `_recovery` 的自动续接改成 `if False:`，即
"放弃后不再续接"），5/5 红：

```text
AssertionError: 'room' != 'far' : pending move was not auto-continued
```

基线（未变异副本）同夹具 OK。

## 6. 残留与移交

1. **产品侧（票据 74，仍旧开放）**：`_horizon_bound()` 不含 `_extra_inflight`，正常
   advance 路可以越过在途的路人回答（票据 73 §6.2a）。本票按边界未动引擎；修完后应
   补一条**确定性**夹具覆盖"忙世界 + 路人在途"（做法：给另一个角色排一个恰在
   +1 tick 的事件，断言路人的回答不被这 tick 吃掉），那是本夹具现在**不再**覆盖的形状。
2. **同族负载敏感测试**：票据 73 §6.1 登记的两枚（本票的门 A 与门 B）已按本票收掉；
   2026-10-18 09:45 之后另一写者在同一文件新增的 E109 门
   （`test_a_named_scheduled_event_wakes_a_sleeper_on_the_chain_path`，票 106）在负载下红过
   一次（第一轮 run10），属票 106 的在建工作，本票不改。
3. 票据 73 §6.1 的两枚负载敏感测试已按本票关闭（附证据见 §4、§5）；
   `harness/tests/test_historical_failures.py` 台账 E73 条目已更新。
