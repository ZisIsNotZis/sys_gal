# 73 — discover 全量下 test_extra_turns_are_recorded_and_conversational 顺序依赖失败（1≠2）

Status: fixed（范围=已确诊机制的测试隔离修复，红→绿；全量层残留见 §6）
Need-review: yes
Need-test-cases: yes

> 2026-10-16 复活会话收口。**根因已活体确诊并修复（测试侧）**：失败当日
> 复现 3 次（含完整 traceback 与探针 trace），机制坐实为
> "extra 答话在共享线程池排队 vs 世界时钟按 tick 飞驰 + idle-despawn 取消"，
> 非导入副作用单因。产品侧两处候选缺陷已登记待另票（本票据边界只许
> harness/tests，未动引擎）。

## 1. 现象与观察史（三种观察并存，间歇性）

- ticket 71：全套 discover 恒定 `failures=1`，`len(extra_turns)` → `1 != 2`；
  单独/随模块/前 6 模块合跑均绿。
- ticket 73 初稿会话（同日早间）：全量 discover 连续两遍绿——"恒定"不成立。
- 本会话（同日晚间）：**活体复现 3 次**——全量 1 次（R1，failures=1，身份
  未捕获）、模块单独 2 次（其一捕获：`test_extra_turns_are_recorded_and_
  conversational`，line 1221 `assertEqual(len(extra_turns), 2)` →
  `AssertionError: 1 != 2`）。
- **结论：间歇性，触发条件是线程调度时机与进程热度，不是确定性的模块
  导入污染。**早前"合跑绿/单跑绿"均为抽样运气；今日模块单独跑也 2/2 红。

## 2. 根因（活体确诊，代码证据）

测试剧本：陈默 07:00 对陌生人问①→07:01 完成tick 生成路人 extra→extra 答①
→追问②（07:01）→extra 应答②，共 2 行 role="extra" 回合。失败时只有 1 行。

**探针**（/tmp 复刻测试体，冷进程第 1 把即红）给出决定性 trace：

```
07:01:00 extra_arrived 赵阿姨 {location: 男生宿舍}
07:01:00 speech 陈默 那签字的人是谁？ {heard: ['赵阿姨']}   ← 追问同 tick 落地
07:01:00 stranger_asked 陈默 {question: 那签字的人是谁？}
07:03:00 extra_removed 赵阿姨 {reason: 'idle'}              ← despawn 在回答在途时动手
extra_turns=0, stub_calls=0                                  ← provider 从未被调用
```

机制链（每一环都有代码出处）：

1. extra 的 provider 调用走 `_run_blocking` → 共享 `_DaemonCallPool`
   （engine.py:237–245、185–201）。**世界时与线程调度解耦**：调度器纯事件
   推进，`await asyncio.sleep(0)` 让位后 worker 线程要等 GIL 才能取队列——
   世界时间几个 tick 在墙钟上是微秒级。
2. `_handle_extras` 顶部的 idle-despawn 只看**世界时**：
   `now - last_active > extra_idle_seconds`（engine.py:2150–2152）。extra 的
   `last_active` 停在 spawn 时刻（07:01），回答在途时无人更新它；测试传
   `extra_idle_seconds=60` = 2 个 tick。调度器在回答落地前跑到 07:03 →
   despawn → `task.cancel()` → **排队中的 provider 调用被取消，永不执行**
   （探针 stub_calls=0、0 行回合的直接原因）。
3. in-suite 的 `1 != 2` 形状：冷启动竞态下第一答抢到了线程、第二答（追问
   路由成 pending_question 之后）被 despawn 吞掉 → 恰 1 行。
4. **为什么顺序/负载敏感**：线程启动与 GIL 延迟随进程热度变化。池文档
   自己记录过同类翻门："spawning one per call … perturbed the wake ordering
   enough to flip the E1/E2/E3 extra-conversation gate"（engine.py:193–196）；
   池在**首次调用时**才起 16 条线程——隔离跑（本测试常是首个 provider
   用户）恰逢冷启动，延迟最大。
5. **产品侧候选缺陷（另票，未动）**：`_horizon_bound()` 只含
   `_active_inflight()`，**不含 `_extra_inflight`**（engine.py:709–715）——
   ticket 22 的"回答在途时钟钉"只在 `_quiescent()` 的两个 stop_at 分支生效，
   正常 `world.advance(until=next_event)` 路径不受约束，时钟于是越过在途
   回答直抵 despawn 阈值。探针 trace 即其活证。
6. 非机制记录（如实排除）：`sample_extra`/`generate_stranger_name` 的
   `random.Random()` 影响路人内容不影响回合数；后 16 个测试模块的 import
   面 AST 扫描无全局污染——"导入副作用"假说被活体证据取代。

## 3. 修复（harness/tests 内，最小测试隔离）

`test_extra_turns_are_recorded_and_conversational`（test_historical_failures.py）：

1. `engine.run` 前 `_call_pool().submit(lambda: None).result(timeout=5)`
   **预热共享池**——消除 16 线程冷启动竞态（首次调用即建池的延迟源）。
2. `extra_idle_seconds` 60 → 3600（>6 tick 场景跨度）——**在途回答不再可能
   被 despawn 取消**，也让 idle 判定不再干扰本测试（E2 的闲聊驻停断言不依
   赖 despawn）。
3. 断言一条未放宽——"答案 ≤1 tick 落地"仍真实约束回答延迟；台账新增
   **E73** 条目指向本测试（engine.py:193–196 的池注释与本票据互证）。

## 4. 验收证据（全部命令与结果，2026-10-16）

红（修复前）：
- 模块单独：`python3 -m unittest discover -s harness/tests -p
  'test_historical_failures.py'` → `FAILED (failures=1)`，FAIL 块：
  `test_extra_turns_are_recorded_and_conversational … AssertionError: 1 != 2`
  （两跑两红，其一存档 /tmp/module_solo2.log）。
- 全量：R1 `FAILED (failures=1, skipped=1)`（身份被 tail 截断）。
- 探针冷进程第 1 把即红（§2 trace）。

绿（修复后）：
- 目标单测连跑 8/8 `OK`。
- 全量 discover：`Ran 575 tests in 281.503s — OK (skipped=1)`（575 = 573 +
  E72 两个新夹具；存档 /tmp/full_run5.log）。
- 代码编译/导入：目标夹具定向跑 2/2 OK（E72a/E72b）。

## 5. 票据 72 移交项——已落地（本票据范围）

1. **E72a `test_audit_slip_delivery_requires_a_scheduled_relay`**：钉死
   "add_document 落地 ≠ 送达"——审计催办单必须存在 target=陈默、notice 带
   单据与职责的转达排程（报告 §5.3）；删 16:05 audit_relay_task 或其
   target 即红。
2. **E72b `test_speech_anchor_requires_a_scheduled_occasion`**：登记"读取
   通过但言说场合缺失"形状——锚点计"说"则种子必须排开放的公共言语场合
   （audit_pack_review 16:20，学生会办公室广播；报告 §6.3）。
   两条均已入台账（E72a/E72b）并定向绿。

## 6. 残留与移交（需要上级裁决/另票）

1. **[已关闭 2026-10-18／票 104] 全量层间歇 failures=1 已定位到两枚并按票据 104 收掉。**
   两例身份均已捕获：`test_extra_turns_are_recorded_and_conversational`（到达 07:02 /
   答话 120s）与 `test_silent_abandonment_auto_continues_pending_action`
   （`action_resumed` 为 False）。两枚同根：夹具把世界切片交给线程到达顺序
   （前者的队列每 tick 都有事件→时钟被墙钟推进；后者的 interrupt 与 move
   谁先落地不定）。修法均只在 `harness/tests/`：世界状态屏障 + 合法空等 + 只留必要
   角色；断言未放宽（门 A 反而从 ≤1 tick 收紧为"答案 tick == 到达 tick"）。
   证据：门 A 子进程 40/40、同进程热跑 200/200、8 核压满 200/200 全绿；
   门 B 同进程 200/200、8 核压满 300/300 全绿（改前旧夹具在同条件下 70/300 红）；
   变异对照 M1（拆票据 22 钉钟）5/5 红、M2（答话晚两拍）5/5 红、
   M3（放弃后不再自动续接）5/5 红；**全量 discover 连跑 10 遍全绿**
   （`Ran 692 tests … OK (skipped=1)` ×10，日志 /tmp/detprobe/ten2/run*.log）。
   根因与时间线见票据 104。
2. **产品侧两项建议另开引擎票**（本票据禁改 harness 产品代码）：
   (a) `_horizon_bound` 不含 `_extra_inflight`——正常 advance 路径越过
   在途 extra 回答，ticket 22 时钟钉不完整；
   (b) idle-despawn 会取消在途回答且不记录被丢弃的 pending_question/
   pending_heard_speech（extra_removed 只带 location/reason）——E1 类
   "静默丢失"在引擎层仍未设门。引擎修复后应把本测试的
   `extra_idle_seconds` 恢复贴近生产默认并补红→绿回归。
3. **[已关闭 2026-10-18／票 104] 验收计划中"两遍全量连绿"已达成并超出**：门 A 与门 B
   确定化后全量 discover 连跑 10 遍全绿（证据见 §6.1）。

## 7. 复现/验证命令

```text
# 红（修复前）
cd 契约失效时请勿喂猫/v4 && python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
# 绿（修复后）
python3 -m unittest harness.tests.test_historical_failures.HistoricalFailureGates.test_extra_turns_are_recorded_and_conversational   # 8/8 OK
OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py'   # 575 tests, OK (skipped=1)
python3 -m unittest harness.tests.test_historical_failures.HistoricalFailureGates.test_audit_slip_delivery_requires_a_scheduled_relay \
                             harness.tests.test_historical_failures.HistoricalFailureGates.test_speech_anchor_requires_a_scheduled_occasion  # 2/2 OK
```

## Comments

- **2026-10-18（测试确定性代理，票 104 收口）**：§6.1 的两枚负载敏感门已关闭。
  根因：两枚夹具都把世界切片交给了线程到达顺序（门 A：整座 pack 世界每 tick 都有 1 tick
  wait 完成/环境唤醒，路人回答在途时时钟被墙钟推进；门 B：b 的 interrupt 与 a 的 move
  谁先提交不定）。修法只在 `harness/tests/`：世界状态屏障（轮询世界状态而非 sleep）+
  合法空等 + 只留必要角色；断言未放宽（门 A 从 ≤1 tick 收紧为"答案 tick == 到达 tick"）。
  证据：热跑/压满跑 200–300 次 0 红（门 B 改前旧夹具同条件 70/300 红）；变异 M1/M2/M3
  各 5/5 红；全量 discover 连跑 10 遍全绿（692 tests ×10，`OK (skipped=1)`）。
  细节与时间线：票据 104。

- **2026-10-16 晚（M1.4 运行代理，机械证据）**：今日全量套件四跑观察=绿/红/绿/红；第 4 遍完整日志已存档 `v4/logs/full-suite-20261016-run4.log`（`Ran 575 tests in 222.208s — FAILED (failures=2, skipped=1)`）。两例红的身份均已捕获，皆属 extra 时序家族——§6.1 开放项首次定位到具体测试：(a) `test_extra_envelope_is_never_broadcast_as_speech`（E42 envelope 家族，line 1330 `AssertionError: [] is not true : 路人仍然必须开口`）；(b) `test_extra_turns_are_recorded_and_conversational`（E73 tick 迟到，line 1249 `AssertionError: '07:02' != '07:01'`，arrived 晚一个 tick）。§6.1 要求的"保留全量输出再定性"已满足；两例与 §6.2 产品侧候选缺陷（已登记票据 74）同族，归 extra 生命周期修复一并裁决。套件级全绿仍未确立，维持 §6.1 记录。

- **2026-10-16 晚（M1.4 运行代理，续记）**：§6.1 预言的“另一个负载敏感测试”
  第二次被捕获并定性：`test_silent_abandonment_auto_continues_pending_action`
  （E75 修复后全量 576 tests 遍，failures=1，`action_resumed` 断言 False；完整
  输出存档 `v4/logs/full-suite-20261016-run5-576tests.log`）。该测试单跑 OK、
  test_engine 模块 31 tests 合跑 OK，且不含 take 路径（与同遍的 kernel 守卫改动
  无语义交集），与票 72 首遍归因（同测试、合成世界、负载敏感）一致，维持 flake
  定性；套件级稳定性仍开放。
