# v4 引擎：时间、并发与调度（async 离散事件内核）

SSOT：引擎时序语义、并发架构、冻结/唤醒/中断机制、失败隔离、检查点与日志。2026-09-08 定稿。配合：`V4-AGENT-INTERFACE.md`（prompt/响应与常数表 SSOT）、`V4-CAST.md`（演员分层与唤醒触发器 SSOT）、`V4-DESIGN.md`（产品目标与世界物理 SSOT）。冲突裁决：引擎事务以本文为准；prompt/工具语义以 AGENT-INTERFACE 为准；角色生命周期以 CAST 为准。

## 0. 总体架构

- 引擎 = **事件队列 + 世界状态 + 可见性投递**。引擎永不阻塞在 LLM 调用内部——阻塞只发生在显式冻结点（§2.3）。
- 每个角色（MC/NPC/extra 一视同仁）是一个 **async 协程循环**：提交意图 → 阻塞于 超时/唤醒/中断 → 收到世界消息 → 下一次 LLM 调用。三层演员只有生命周期不同（CAST §1），协议完全一致。
- 引擎单线程事件循环（单进程 asyncio）；并发 = 多个在途 LLM 调用（wall-clock 重叠），模拟时序保持全序。
- 理论原型：离散事件仿真（DES）+ actor 模型；LLM 连接池（provider 并发上限）只是吞吐旋钮，永远不是正确性假设。

## 1. 模块清单

1. 时钟与事件队列：全序优先队列，键 = (时间, 到达序)；时间只跳向下一事件，从不走墙钟（r 旋钮除外，§5）。
2. 世界状态：角色（位置/物品/忙_until/挂起动作）、地点（开闭/规则层/在场者）、物品、文档与批注。
3. 物理：路线图、移动时长、tick 取整。不可变，模型不可见（AGENT-INTERFACE B1）。
4. 意图校验与执行：schema 校验、链式执行、时间累加、同 tick 竞争判定、调用边界截断。
5. 可见性与投递：为每个事件计算收件人集（在场公共/定向私有），写入每角色信箱；唤醒时渲染。
6. 计时器注册表：角色等待到期、reminder force-interrupt、send_message 投递、导演拍点、空闲心跳。
7. 演员生命周期管理：NPC 唤醒触发器（CAST §2）、extra 生成/销毁、路人池。
8. 调度与背压：多角色同时要回合时排队等 LLM 池，优先级 = 对话中被点名 > 被中断 > 超时到期 > 冷清唤醒。
9. 检查点与日志：append-only journal + 状态快照（§7）。
10. trace：每角色时间线 + 全局 journal（§7）。

## 2. 五条时序不变量

1. **连续时间戳**。引擎内部一律存真实时间点，绝不存 tick 序号。tick（默认 1 分钟，config）只是四种东西的单位：世界动作最短时长与取整格、send_message 投递延迟、决策视界单位、角色间常识预算单位。r>0 时时间戳离格（§5）——一切"≡0 mod tick"的代码假设都禁止。
2. **全局光锥（最大信息流假设）**。事件在 T 提交 → 任何角色最早 T+1 tick 感知（随其下一条世界消息渲染）。依据：电话（1 tick 投递）+ 传言中转使逐对传播延迟不可计算——任何在场第三者都是潜在传话人，闲聊正是信息扩散泵；引擎取保守上界（人人 ≤1 tick）。错冻结的代价是短暂停顿，错光锥的代价是穿帮（impossible knowledge）。`known_contacts` 仅是动作层门控（能否对某人 send_message），在因果与物理层零角色。
3. **全局决策视界（冻结规则）**。在途意图的 deadline 即其唤醒（或中断投递、超时到期）时刻。引擎只处理时间 ≤ `oldest_pending_deadline + 1 tick` 的事件（即：任一决策在途时，世界至多漂移 1 tick）（他人链条完成、投递、reminder、导演拍点都只是事件）；第一个超界事件是**冻结点**——全钟暂停，直到意图落地或静默弃权（§3）。等待最慢的思考者是有界的，不是无限：最老的在飞决定等过 `freeze_tolerance`（§6）后该视界被释放，世界继续前进，迟到意图按当前钟提交。时钟永不跳过未清的 pending deadline；**禁止回填**（backdating）：迟到意图按当前钟提交。对比旧串行 runner 零回归：只是限制了能提前流水线的工作量。force-turn/wake 不得覆盖普通 `busy_until`；被打断的 `pending` 动作例外，仍须立即给出 continue-or-abandon。若串行工具链的前一动作越过一 tick 地平线，后续调用逐项收到真实完成时刻和重试形状的 `not executed` 结果；链不再推动时钟，也不把普通 busy 误称为待恢复中断。
4. **同 tick 排序 = 意图到达序**。同 tick 多个意图按 wall 到达序执行，资源竞争按提交序串行判定（AGENT-INTERFACE m8；**物品归属**这类资源要真的串行，占用就得在提交期成立，窗口 5 的两次 `take 一份晚饭` 正是缺了这一步——票 98 §7.9，E102）。含义：同 tick 竞争不可种子复现——种子调度不得制造其结果依赖的同 tick 竞争；journal 逐字记录实际发生序，回放不受影响（§7）。
5. **中断绑定于执行位置**。意图链按计划提交、按事件**惰性执行**（busy_until/current_action 机制）。中断在执行位置生效：走 12 分钟第 3 分钟被敲门 → 挂起，剩 9 分钟，continue-or-cancel；中断到达时角色尚在思考（无已提交链）→ 等意图落地后在第一个可中断点生效。链"批量预执行"会静默杀死本条——评审重点盯。

## 3. 阻塞、唤醒与中断

阻塞三态：**运行中**（LLM 在途或链在执行）/ **等时间**（wait 到期前）/ **等事件**（无自身计时，等唤醒）。

| 类别 | 触发 | 效果 |
|---|---|---|
| wake | 环境公共事件、排队信件、冷清唤醒 | 等待提前结束，信箱随下条世界消息投递，角色自由决策；无挂起动作 |
| interrupt | 敲门、点名说话/耳语、send_message 送达、reminder 到期（force） | 挂起于执行位置 → 下回合 continue-or-cancel（AGENT-INTERFACE §4） |

- **行动状态**：每回合消息可见一行仅对本人开放的状态：普通动作显示动作/目标/真实完成时刻；等待回应显示说话或短信已完成、回复对象与等待截止；中断显示被谁打断及剩余时间，并指明 continue/abandon。普通 busy 时没有 wait affordance，不能通过再提交 wait 延长/继续动作；动作按既定 `busy_until` 自动完成。`continue_action` / `abandon_action` 只对真实 `pending` 中断开放。
- **静默弃权**：`decision_timeout` 内无意图 → 该回合视为发呆：无世界效果，挂起动作**自动 continue**（沉默 ≠ 同意取消；被敲门者沉默就是继续走过去），计时器重挂，失败计数 +1。
- **deadline 重置**：中断投递给运行中角色时，其回答 continue-or-cancel 的新 deadline 从投递点重新起算 1 tick。
- **唤醒类的两类分支必须分开（票 101，E106）**：普通 `wait` 只由同地社交事件（`WAKE_EVENT_KINDS`）唤醒，全场广播的排程事件不叫醒它；`sleep: true` 的 wait 额外多一条：payload 里 `target` 点名了他的 `world_event`（例如定了向的电话/通知）会经由 `World.wake_sleeper` 提前结束睡眠——否则一条 8 小时的睡眠会把点名事件跨过去，而“睡得太长”正是它存在的理由。
- **空闲心跳**：等事件状态的角色若无事件永不再醒。MC 有空闲心跳 `mc_idle_heartbeat`（默认 30 分钟，醒来时世界消息照常渲染）；NPC 无心跳（只由 CAST §2 触发器唤醒）；extra 无心跳（对话期生命周期，`extra_idle_timeout` 无新对话即销毁，不要求它此前必须说过话）。心跳是一条**点名他的私有排程事件**：到点时若目标在 `sleep` 中，`World._fire_private_wake` 先提交 `private_wake`、再由 `wake_sleeper` 结束睡眠并留下可见的 `wait_woken`，那一拍就换出回合（E110）；目标已不在世界里则记一条 `private_wake_failed {reason: actor_not_present}`，不静默成死信。普通 `wait` 不被心跳打断（它自己的 `action_completed` 会把事件送达，不是死信）。代价是默认 30 分钟的心跳会打断长睡——`mc_idle_heartbeat` 是按剧本调节的旋钮。
- **NPC 唤醒输入（ticket 45）**：除 CAST §2 的事件触发器外，NPC 还有两个“你被指望做点什么”的输入——(1) 自己的定时行 `!at=` 到期（`reminder_due`）以“你的安排到点了：<事项>”进入唤醒队列（kernel 只对忙着的角色做 force-interrupt，空闲 NPC 靠这条才醒）；(2) 被直接点名/定向消息后**未开口回应**的“欠回应”债：开口（`speak` 或发出的消息落地）即清，逾 `owed_response_delay`（默认 600s）仍欠且角色空闲时补一次唤醒（文案“有人当面对你说话，你还没有回应（<对方>）”）。债只补一次、不占冷场唤醒预算，随检查点往返（旧格式缺键即无债）。既无到期行也不欠回应的 NPC 维持原样：无心跳、不被时钟轮询。
- **extra 场景上下文**：一次对话只保留 scene-local、有界 transcript（最近至多 8 句/单句 180 字/总计 1200 字），以世界事件 `visible_to` 的实际投递名单筛选（`speech.payload.heard` 只是与之保持一致的镜像）；speaker 自己刚说的话也可保留。另附一处同一 `visible_to`/同地权威的场景事实块（在场者、眼前物件及其客观描述、可达目的地），使数量类断言有根据；票 98（E103）之后，被种子 `known_to` 限定给别人的物件只给名字、不给描述正文（`scene_perception` 的 `_described_to`），否则“便条正文”会顺着“客观描述”钻进陌生人嘴里。绝不凭当前共处推测历史受众，不向 extra 投递其未听到的 whisper/private speech。对额外角色的公开发言会唤醒同场 extra，即使 speaker 不是最初搭话者；提供方在途期间抵达的可听 speech 要保留为待处理唤醒，不能被清游标吞掉。system 与工具前缀在一个 extra 生命周期中固定（ticket 57：`speak`+`move`/`take`/`place`/`give`，无记忆工具）；没有新可听 speech 时不发模型回合、不伪造空问题（票 101 起，这一种也记一条 `empty_turn`，`reason: no_request`，见 §7.10）；extra 可沉默/告别，超时即销毁，不写长程记忆（AGENT-INTERFACE §5）。

### 3.1 唤醒与回合调度的不变式（ticket 106，E109）

**不变式**：一个回合内的时钟推进不得越过世界上下一个排程作业（`World.next_event_time()`）。排程表上的一拍由调度器自己走、由调度器把那一拍的回合派出去；回合内的 `advance(until=…)` 只服务“同一回合里前一个动作完成后才成立的后续调用”，所以它的上界是四者的最小值——自己的 `busy_until`、run 的 stop horizon、决策视界（§2.3）、以及下一个排程作业。

**它治的是什么**（D1 工件 `real-20261018T085705+0800-2116654-169068128`，票 103 D1-E1／票 106）：18:34 是当晚最后一个回合；18:35 林瑶提交 `wait 28800 sleep:true`（到 03/17 02:35）。链内推进只夹了 stop horizon 与决策视界，而当时没有别人在思考，于是 `limit` 落到 22:00：一次 `world.advance` 把 18:40–22:00 的六条夜间排程（19:00 `counselor_evening_intake`、19:10、19:30、20:00、20:40、21:30）、三条 `private_wake`（19:02／19:05／19:05）、四条 `reminder_due`、以及 18:45／18:46 两条动作完成全部记进事件日志，却没有任何角色拿到回合；循环顶部的 `_stop_check` 随即以 `stop_at_reached` 停表。22:00 检查点里 陈默／唐小岚／辅导员／食堂大妈 都是 `busy_until: None, sleeping: False`（醒着、空闲），感知游标停在 18:36——事件到了世界上，却从没到过任何人的游标。

三层含义：

1. **到达即回合**：`private_wake`、`reminder_due`、`world_event` 以及别人的 `action_completed` 落在某一拍之后，那一拍必须由调度器派发；被唤醒者只要清醒就获得一次回合机会（`agent_turns` +1、感知游标前移）。睡着的角色先拿到可见的唤醒（`wait_woken`，E106 的 `World.wake_sleeper`），再在下一次 `_ready_now` 里获得回合——心跳的 `private_wake` 也是这条：到点先用 `wake_sleeper` 叫醒睡着的目标（E110），目标已不在世界里则记 `private_wake_failed`，不留死信。
2. **时钟只由调度器走**：被这条界拦下的后续调用按既有规则逐项收到真实完成时刻和重试形状的 `not executed`（§2.3 的“链在争用下降级为一回合一个动作”）；动作照旧自动完成，下一回合可重试。
3. **`sleep` 不退出调度**：睡眠只是“等时间”的一种，靠自己的 `action_completed` 或点名事件重新入场——既不是永久退场，也不需要“每 N 分钟叫醒所有人”这类兜底（空闲心跳仍只是 MC 空转的兜底，见上）。

**看守测试**：`harness/tests/test_historical_failures.py` `WakeReachabilityGates`（E109）——全部角色进入 wait／入睡之后，07:30 的 `private_wake` 仍要在清晨的活人身上换出一回合且进得了他的游标；睡眠中被点名的事件必须先留一条 `wait_woken` 再在那一刻拿到回合。两条都走真实回合路径（`_execute_chain`，即 stub agent 带 `session_obj`），而 `SleepWaitGates③` 走的是旧 callable 路径（`_submit`）——这就是那条门在真实种子上仍然红的原因。

## 4. 对话节奏

- 每条 speak 恰 1 tick。光锥只延迟**回应**，不禁止同 tick 多人各提交一句：N 人各说一句的一轮 = 1 tick，M 轮对话 = M tick。tick=1 分钟 → 十轮对话 ≈ 十分钟模拟时间，节奏自然。
- 子 tick 对话窗（同窗内往返免费）未排期，见 §9。

## 5. r 旋钮（realtime-ness）

- 配置 `realtime_ratio`，默认 0。r>0 时：回合间思考/解析的 wall 延迟 × r 计入模拟时间（意图到达 = 唤醒时刻 + r×wall 延迟，下限 1 tick）；时间戳连续、离格。
- 作用域仅**回合间思考**——链内时间是世界物理，已有建模。后果：think 不再严格免费，犹豫有世界价格；决策越慢越迟到。
- **确定性边界**：r>0 时 wall 延迟不可复现 → 种子级确定性只在 r=0 成立；journal 回放（重放已记录的到达序）与断点续跑不受影响。首验日 r=0。

## 6. 失败隔离

- per-actor：连续 `batch_persistent_failure`（3）次失败 → 该角色弃权发呆，世界继续；**绝不冻结全钟等一个死 provider**。旧"世界停机"闸门语义废除。
- 全局停机仅两途：全体角色连续失败 / `max_wall_seconds` 耗尽（另有下面的连续无进展兜底）。
- **停顿 = 连续无进展（ticket 53）**。`Engine._stall_exceeded()` 量的是**从最近一次世界前进到现在的墙钟秒数**——前进事件 = 任何一次时钟推进（`world.advance`）或任一角色回合作成（有决定/弃权/发呆）。它**不**累积每一次冻结（旧 `stall_budget_ratio` 是累积冻结占墙钟预算的比例，`+=` 从不重置：健康的慢跑会逐步触顶，且把"真挂死"与"总等待多"混成一个信号）。默认阈值 `stall_threshold_seconds = 300s`（`V4_STALL_SECONDS`），命中即以诚实原因 `stall_no_progress` 终止。
- **调度器不被单个任务钉死（ticket 53）**。`_scheduler_loop` 的冻结点等待不再无条件盯住 `min(_inflight)`：只要最老的在飞决定已等过 `freeze_tolerance`（默认 `min(decision_timeout, 120s)`，`V4_FREEZE_TOLERANCE_SECONDS`；`DEFAULT_FREEZE_TOLERANCE_SECONDS=120`），就把它的 wake 从视界里释放（记 `inflight_released`）——世界只有欠着一段前进，延误的意图仍按当前钟提交（§2.3 禁止回填），**不是**取消"等最慢思考者"：容忍依旧存在、连续且有界。
- **两处超时有界（ticket 53）**。`decision_timeout = provider.worst_case_seconds() + 小额余量`（real_run：`V4_DECISION_MARGIN_SECONDS`，默认 60s；旧写法 `×8+5` 曾得到 ~72 min，比它该先于的 stall 预算还长）；`_actor_loop` 的 `await hung`（等一个已超时调用收尾）由 `hung_tolerance`（`V4_HUNG_TIMEOUT_SECONDS`，real_run 默认 60s）封顶，超界即放弃：丢掉该调用、把 v4 会话恢复成决定前的快照（避免两个写者共用一条转录），该角色**仍能参加后续回合**，不永久退出。
- **provider 单次调用的总预算 vs socket 超时（ticket 54）**。`urlopen(timeout=…)` 是 **socket 级**超时（只约束单次连接/单次 recv 的静默），**不是整次请求的上界**；预算检查只在每次 attempt 顶部做时，服务端持续滴流或 hold 住连接就能让一次调用永久挂住（这正是 2026-10-01 的 11:32 冻结：辅导员那一路在 11:13/11:16 已两次 `retry deadline exhausted`，随后一次请求再没返回）。现在每次调用有一个**墙钟总预算** `_call_budget_seconds()`：有 `max_duration`（`V3_PROVIDER_MAX_DURATION`，默认 600s）就取它，否则取重试策略的结构性最坏情况（`(retries+1)×timeout + 退避和`）；每次 attempt 的 socket 超时取 `min(timeout, 剩余预算)`，响应体按 recv 分块读取并在块间复查 deadline（`read1`，见 `_read_response_body`），超界即关闭连接并以既有可重试语义报错（`retryable=True`、`retry_exhausted=True`、`attempts=N`），文案给出“第 N 次尝试、已用 X 秒/总预算 Y 秒…response never finished”以区分“上游慢”与“上游挂死”。可重试错误照旧退避重试，正常响应路径不变；`worst_case_seconds()` 数值不变（= 总预算 + 最后一次 socket 静默，仍是 `decision_timeout` 的真实上界）。
- **结束诊断（ticket 53）**。任何停机路径（`stall_no_progress` / `wall_clock_deadline_reached` / 超时 / 放弃 / 全体失败 …）在 `_finish` 里写一条 `engine_stop_diagnostic` 到 trace（并同步 `flush` 打日志），包含：在飞角色及其起始模拟时刻与已等墙钟秒、额外角色在飞、最近进展时刻与已停秒数、停顿定义字符串、命中的阈值、三处超时。单次超时/放弃也各写 `decision_abandoned` / `hung_decision_abandoned`。ticket 67 起还带 `max_wall_seconds` 与 `wall_overrun_seconds`（已用墙钟 - 预算，正数即实际超出时长）。
- **墙钟不可被内层等待饿死（ticket 67）**。所有停机条件（墙钟 / stall / `max_turns` / `stop_at`）收进 `Engine._stop_check()`，**既在 `_scheduler_loop` 每轮顶部调、也在冻结点内层等待循环里每轮调**：旧写法只在顶层检查，内层循环盯 `min(active)` 直到 ticket-53 释放界（`freeze_tolerance`）才返回，一个永不返回的最老在飞决定会把 2h 安全上限推迟整个释放界（实测 real-20261001T163024 晚 12s 停）。此外 `_freeze_poll()` 与 `_await_activity()` 的等待都再受**剩余墙钟预算**封顶，保证到点必停。

## 7. 检查点、日志与确定性

- **journal**（append-only：意图提交 + 事件，含时间戳与到达序）是事实流 SSOT；状态 = journal 折叠 + 快照。
- 恢复 = 快照 + journal 尾部重放 + 重挂计时器。KB 与 last_shown 状态引擎侧保存；会话转录与 compaction 边界亦入检查点——恢复不得重放已计 last_shown 的行（防首跑洪泛）。
- extra 的对话期可变状态随检查点往返：冻结的 system 前缀、场景游标 `context_cursor`、待答问题 `pending_question`、待听语音 `pending_heard_speech`、到场/活跃时刻。半天分段续跑（d1-am → d1-pm）恢复后，场上活着的 extra 必须接着答它未答的问题；旧格式行（缺这些键）按 `fragment`/`knowledge_notes`/地点/名字重建前缀并给安全缺省，绝不因缺键 KeyError（ticket 50）。
- trace 改为：每角色时间线 + 全局 journal——比回合快照更强的 happens-before 分析材料。
- **两套回合计数，两个度量（E111）**。`Trace.agent_turns` 是轨迹里记录的全部 agent 回合：MC、NPC、extra 都算，`result: none` 的诊断行也算，报告与轨迹复核（每角色回合数、错误率、`memory_store` 标注）用它。`Engine._turns` 是调度器的 persistent agent 回合数：只在 `_take_turn` 里自增（MC/NPC），extra 的 `_extra_loop` 不经过它；`max_turns` 停机闸与停机诊断里的 `engine.turns` 用它。两者差值恒等于 extra 回合数（D1 2026-03-16：`1720 - 1479 = 241`，29 名 extra；前一轮 `868 - 793 = 75`），**不是丢回合**。看守断言钉在 `test_extra_turns_are_recorded_and_conversational`：每个 persistent 回合在轨迹里恰好一行，两数之差 = extra 回合数。
- **记忆事实只有一处：引擎侧 KB（ticket 68）**。`runner.kb[actor].rows` 是唯一的记忆存储（`update_memory`/`recall`/`flashback`/种子行/`!always`/`!at=` 都读写它，随检查点里的 `runner.kb` 往返）。`PrivateState.memories` 是遗留 v3 字段，v4 不写、恒为空，**不代表丢写**（曾有 reviewer 据它误判 P1）。为免歧义：trace 顶层带 `knowledge`（每个角色最新 `ActorKB.snapshot()`，随每次检查点与收尾写入），每个 v4 轮次的 `private_state` 另带 `memory_store: "engine-kb"` 与 `knowledge_rows: N`；`scripts/check_milestones.py` 的系统健康块并列打印 KB 行数与遗留 `memories` 合计（review-only）。
- 确定性种子与历史失败闸门（v3 pre-run gate 惯例）必须在新排序下全绿后才许大跑。

### 7.1 客观观测与停留即读（ticket 49，2026-09-30 裁定）

- **看见即写记忆**：每个实体（地点/物品/文档）都有一份客观描述（world pack 的 Markdown 正文，`entity_descriptions`）。感知构造（`World.poll`）时按**在场**判定——所在地点、地点内物品、手上的东西（`known_to` 不参与）——把首次进入视野的实体的客观描述写入该角色的 `ActorState.observed`（`{objective, at, where}`），并发出一条只对该角色可见的 `observed` 世界事件。客观描述不再是"首到那一回合的一次性快照"：它落成记忆行，随检查点往返，压缩也不丢。
- **首次投递**：描述仍经既有描述通道（实体 KB 行 / `descriptions`）在首次看见时给出；此后由 `observed` 持有。
- **兜底取用**：角色对一件"看见过但没有可读正文"的东西发起 `read`（`present_without_body` / `known_not_readable_not_here`）时，拒绝文本附上系统层客观描述原文，措辞明确是"你看见过的"客观陈述，不含任何主观推断；没看见过的东西绝不编造描述。
- **停留即读**：可读实体（`document_defs`，且 `available_now`）进入视野后，角色连续停留达到其 `reading_seconds`，引擎自动产出一条 `document_read`（payload `auto: true`），正文投给该角色；同一实体只自动读一次；中途离开（`leave`/到达新地点）作废该次计时，回原处需重新计满；主动 `read` 先于计时完成则不重复。文档行可写 `auto_read: false`（缺省 true）要求必须主动读。`document_read` 事件、私有投递通道与可见性不变；`auto` 标记让里程碑证据（亲读）仍可区分。

### 7.2 反重复与停滞提示（ticket 43，2026-09-30 裁定）

- **注入通道**：`RepetitionMonitor` 在每条世界消息的**前沿**注入一行 `situational_notice`（不改 system/初始化/已埋上下文，缓存不变）。三种检测：同一目标连续未回消息；同一有意义动作（kind + 精确 args）重复；连续 `wait` 造成的停滞。
- **链路径必须记录真实意图**：v4 回合走工具链（`_execute_chain`），监测器收到的是链的 `recorded` Intention（首个调用的 kind + 整条调用列表，一条链按一个整体动作计）。链内世界动作全部被拒时结果记为 `rejected`，否则 `submitted`；引擎旧写法传 `None` 会被 `note_turn` 首句直接丢弃，实测导致整个 run 零计数（九次同样的失败读、十八次 `wait 900` 一条提示都没有）。
- **wait 计入停滞**：`_EXCLUDED_ACTIONS` 只保留 `sleep`/`text`（`text` 另有未回消息计数）。连续 `wait` 达到 `stagnation_threshold`（默认 4）触发一次停滞提示，其后每 `stagnation_stride`（默认 4）再触发，不逐回合刷屏；提示给出已等待的模拟时长，并列出本回合 affordances 中**仍可执行**的动作（move/read/take/speak/text/give/… 取少量，排除 `wait`/`sleep`/`route_hints`）。
- **重置**：任何非 `wait` 动作或 location 变化都打断连续计数，重新起算。
- 阈值全部是 `RepetitionMonitor(...)` 的构造参数，不写死；状态随检查点往返（`state()`/`restore()`）。

### 7.3 原语充分性：读=文书，知觉=物品描述（ticket 77，2026-10-16 裁定）

- **裁定**：不为"看一看/打个电话/临时加个人"新增原语。引擎保持最小动作集（`wait speak text move take place give read leave_note knock trash continue_action abandon_action`）；表达力缺口先由种子层补，只有证明旧概念做不到时才泛化旧概念，最后才谈新原语。
- **两条既有通道的分工**（给种子作者）：
  - **要"读到内容"→ 登记成文书**（`documents:` 行 + `documents/<id>.md` 描写，可带 `content`、`reading_seconds`、`auto_read`）。凡在世界里被当作信息渠道的东西——公告栏、通知、价目表、面核记录——都是文书。在场时 `read` 的可用对象来自 `document_defs`（`World._available_readables`），读出一条 `document_read`（正文只给读者，同地他人只看见"他在读"），停留够 `reading_seconds` 还会自动读（§7.1 停留即读）。
  - **只是"看见它是什么"→ 登记成物品**（`items:` 行 + `items/<id>.md` 描写）。在场物品的客观描写随知觉下发并落成 `observed` 记忆行（§7.1）；不需要可读正文的实物写 `readable: false` + `readable_reason`。摊位库存、房间陈设都走这条：把数量和状态写进描写，问题就有确定性答案，不必去问在场的人。
- **`items:` 有两种：可携带的东西与固定陈设**（ticket 80，票 79 §8-5 裁定；**`documents:` 同样适用**，票 91）。缺省 `takeable: true`；写 `takeable: false` 的是固定陈设——它照样在场、照样随知觉下发描写，但 `take`（以及能把东西从不持有的位置挪走的 `give` 就地分支与 `trash`）结构化拒绝，理由取该行的 `fixed_reason`，没写就说"这是固定陈设"。这是对旧概念的一处最小泛化，不是新原语：物品位置、`item_locations`、检查点与 replay 一字未改，变的只有"接受还是拒绝"这一判定；`fixed_items` 与 `routes` 一样由种子派生，不进检查点。
- **为什么**：M1.5 报告 §2.4 的三族循环（公告栏不可读、陈设/库存不可查验、12345 借电话）全部是"世界描述里像是有、实际没有实体"或"种子缺一个世界内出口"，不是缺动作。加 look/examine/call 会把"东西有没有被登记"这个种子错误变成引擎的责任，还会让同一件事在文书与陈设两条通道上各有一套语义。
- **世界内出口优先于新动词**：角色卡在"无处可去/无人可问"时，补的是可达地点（`routes:`）、该地点的用途描写（`locations/<id>.md`）与能指路的在场者（`actors:` 常驻配角，由既有排程 `target` 唤醒），而不是给他一个新动作。`text` 只对人说话，对非人地址的拒绝会列出真正可达的收件人。
- **现场人物**：需要一个"值班干事"时，他是常驻配角（`actors:` 行，`role: npc`，事件驱动，由排程 `target` 唤醒），不是引擎临时生成的身影；该场合留下的证据就是一条文书（`add_document` 效果），晚到者自己读。
- **残留（未实现，需另开票据）**：字面意义上的"打电话给非人端点"今天不可表达。最小泛化是把 `text` 的目标类从 actor 扩到已注册非人端点（`_raw_duration` 的 text 分支 + `_resolve_person`），而不是新增 `call` 动作；它只有在证明"世界内出口"方案确实不适用时才值得做。
- **回归**：`harness/tests/test_world_pack.py` `PrimitiveSufficiencyTests`（四种编码的正反夹具）与 `harness/tests/test_historical_failures.py` `PrimitiveSufficiencyAuditTests`（E76/E77/E78/E77b，在真实世界包上只补种子声明）；固定陈设不可拿由 `SeedContractGateTests.test_a_fixed_fixture_cannot_be_taken_and_stays_put`（E83）看守。

### 7.4 物品、写记录与"没有调用"的回合（ticket 83，2026-10-18 窗口 1 裁定）

- **物品不变式（E84）**：任何物品在任何时刻**要么在某人手里、要么在某个地点**，唯一的例外是 `trash` 显式销毁（那是一条被记录的事件，不是漏洞）——不存在"既不在人手里也不在任何地点"的静默空缺，引擎也不引入第二个"completeness 声明"状态去解释它。extra 是对话期演员（CAST §1），它拿走的东西因此在它被回收时**留在原处**：`World.remove_extra` 在提交 `extra_removed` 之前，把背包里的每件物品按既有 `place` 语义放回该 extra 的最后所在地点，每件一条同地可见的 `item_dropped {item, location, reason}` 事件。收益有三：同地的人看得见东西落回原处（此前 12:52 拿走的 `校报草稿` 在 13:07 无声消失，主人查了六小时的目标物凭空不见）、`replay` 在日志的每个前缀上都重建出同一结果、引擎不必引入"物品已销毁"这种第二状态。（残留：`trash` 的后果仍未进入 `replay`，那是票 75/83 之外的老缺口。）`replay` 因此也补上它一直缺的三段重放：`extra_arrived` 建人、`extra_removed` 删人、`item_dropped` 落物（在此之前，任何带 extra 的日志一重放就 `KeyError`），`action_completed` 也照 kernel 的完成期守卫那样，对已经离场的人只让事件成立、不再改状态。
- **写记录动作的可用性（E85）**：`leave_note` 是这个世界里"把话写成文字"的既有动作，**不依赖任何持有物**——kernel 只校验 `text` 非空，`affordances()` 无条件给出它，工具表无条件声明它，纸笔（`可用纸笔` 等）只是世界里的物件，不是前置条件。所以缺的从来不是可用性而是**说法**：它过去只被描述成"给之后进入者留一张会烧掉的字条"，于是一个被要求"把事实记录写到纸上"的角色会认定这不是记录（林瑶 08:34 用它写了 400 字，13:13 拿着纸笔写道"没有可用工具把个人事实记录实际写入纸面"）。现在工具说明与 affordance 提示都先把它说成**写记录/留字条**，并明说不需要先拿到纸笔；投递规则（在场者看不到正文、作者返场不算读者、第一位非作者进入者私下读到后烧掉、要递到手上用 `give`）仍只写在工具说明一处。动作语义、事件、检查点一字未改。
- **没有调用的回合怎么记（E86/E87）**：一回合是否发生了动作，只由工具调用决定，**话语永远不是动作**。三层的记账因此各不相同：MC/NPC 的纯文本正文是私有心声（ticket 64，`content_private`），extra 的纯文本回复按 T1 算作它说的话（`extra_tool_calls` 合成 `speak`）。零调用的回合以前只在 trace 里留一条 `result: none` 的空白行（12:51 林瑶：`inner` 空、零调用，世界只往前走一拍），审阅者看不出原因；现在 `_execute_chain` 为每个零调用回合记一条 system_turn `empty_turn`，带 `actor / turn_id / role / reason / private_chars`，`reason=prose_only` 表示"写了话但没提交意图"、`no_output` 表示"什么都没返回"。这是诊断，不是机制：它不改变世界、不惩罚角色、不让引擎替模型补动作；一个提交了 `speak` 的回合不是空回合（E87 的负向守卫）。
- **NPC"只叙述不施动"的裁定**：这是提示层问题，引擎无需再改。证据：食堂大妈 12:44–12:58 的七次"我马上给你打"都是真的 `speak` 调用，世界照实记了七句话、零次 `give`/`place`；她要交付的 `一份餐食` 就摆在食堂，`give`/`take`/`place` 一直在她的工具表与 affordances 里，所以缺的是她在导演简报下"承诺就用动作兑现、不断言世界状态改变（丢了/坏了/被挪走）"的约束，而不是引擎的表达力。修在 `npc_agent` 的导演简报/角色卡（提示层），不在 kernel；已落地为 `prompt.NPC_WAKE_RULES`（NPC 唤醒 `[director]` 块的固定开头）、`build_extra_system_prompt` 的“你能做的事”与 `give`/`take`/`leave_note` 的工具说明（票 85，V4-AGENT-INTERFACE §2.3）。
- **回归**：`harness/tests/test_historical_failures.py` 的 `ExtraDespawnItemInvariantGates`（E84：落回原处 + replay 重建 + 每个前缀的不变式）、`WriteRecordAffordanceGates`（E85：有/无纸笔两种状态的可用性与文案）、`TurnWithoutActionGates`（E86 空回合的两种 reason、E87 说话不被当成动作）。

### 7.5 两种便条、extra 的诊断与点名生成（ticket 88，2026-10-18 窗口 2 裁定）

窗口 2（07:00→15:30）证明票 83/85 的主修生效，也暴露出三个新的引擎层缺口。三条都只是**既有原语的泛化或诊断补强**，不新增动作种类。

- **`leave_note` 有两种语义（E89）**。旧语义（2026-09-22 裁定）是房间留言：留在 `locations[...].notes`，第一位非作者进入者私下读到全文后烧掉——按定义交不到在场的收件人手里，也读不了第二遍。窗口 2 的 12:11–15:02 因此空转：21 次 `item_given` 全是纸笔往返、0 次成稿，96 个回合（9.9%）在讨论“留条能不能算稿”。扩展是一处参数化：
  - **缺省（`persist` 缺省 false）**：一字未改——`locations[...].notes`、第一位非作者进入者私下读全文、阅后即焚、作者返场不消费。
  - **`persist: true`**：便条成为**可寻址实体** `note-<作者>-<序号>`，存在 `World.persistent_notes`（不进 `document_defs`，也不进 `locations[].notes`），事件 `note_left {location, text, persist: true, note}` 同时带 id 与 text，故 `replay` 能重建同一 id。它的语义：
    - **在知觉里**：停留在地点的人在表头看到“字条：<编号>（<作者> 于 <时间> 留）”，正文不在知觉里。
    - **可读多次**：`read <编号>` 走与文书同一条 `document_read` 私有通道（正文只给读者），读完**不销毁**；停留自动读（§7.1）不适用于便条——它是主动读的文稿，这样“读几次”由角色决定。
    - **可丢弃**：`trash <编号>` 按既有 trash 语义销毁，事件 `item_trashed {item}` 带 id，replay 同步移除。
    - **当面交出去用 `give`**（票 101 修订）：便条本身可以 `give` 给在场的人，详见 §7.10；把说明交到对方会看的地点仍可走 `leave_note persist=true`，两条都是既有语义。
    - **编号稳定性**：id 在 `submit` 时分配（因此 `action_started`/`note_left` 与 tool 结果三者同号），计数器 `next_note_serial` 与 `persistent_notes` 一起进检查点，恢复后不重用旧编号；旧检查点缺这两个键 → 空表 = 没有持久便条（向后兼容增量，不迁移）。
- **零动作的 extra 回合也有诊断（E90）**。E86 的 `empty_turn` 只在 MC/NPC 的链路径上记，extra 走 `_extra_turn`，于是 09:33 林大爷、14:13 陈师傅 的 `result: none`/`calls: []` 在 trace 里仍是空白行（8 条 `result: none` 对 6 条 `empty_turn`）。现在 extra 真正被问了（`needs_response`）却一个调用都没有时，也记一条 system_turn `empty_turn`（`role: extra`、`reason: no_output`、`private_chars: 0`）。纯文本回复按 T1 会合成 `speak`，所以这一 state 只覆盖“什么也没返回”。世界不变、不惩罚角色——与 E86 同一层诊断。
- **点名的路人按别名生成（E91）**。池条目可声明 `aliases:`（`{fragment, rarity, knowledge_notes, weight, aliases}`）；`speak(to=["老板娘"])` 与 `to=["陌生人"]` 走同一条搭话通道（都发 `stranger_asked`），只是 payload 多一个 `alias`，`_spawn_extra` 据此**优先取该条目**，并让别名成为它的名字（别名已被占用时才退回随机名，并把别名写进身份描写的“（人称「…」）”）。未点名时仍是既有 `sample_extra` 随机取样；生命周期（idle despawn、E84 落物）一字未改。窗口 2 的对照：池里写的是“后街糕点铺的老板娘”，实际生成 13:14 李师傅、15:09 王学长，唐小岚两次到场问“李师傅或店里负责人现在在吗”，要找的人从未出现。
- **回归**：`harness/tests/test_historical_failures.py` 的 `PersistentNoteGates`（E89：读两次同文、默认字条仍烧、replay 同 id、检查点编号不复用、旧检查点仍加载）、`ExtraEmptyTurnGates`（E90：零动作记 reason、说话回合不算空回合）、`ExtraPoolAliasGates`（E91：点别名生成该条目并以别名出场、未点名仍随机）。

### 7.6 台账的对话通道、连续空回合的回执与"钉住的文书"（ticket 91，2026-10-18 窗口 3 裁定）

窗口 3（07:00→12:00）里三条都与**文档/代码漂移**有关，没有一条是新设计：

- **台账在对话里可达（E92）**。窗口 3 全段 `system_answer` 为 0：09:02 陈默 `speak(to=["2013年台风台账"])` 被内核判成"未知收件人"，而 `World.ACTIONS` 里既没有 `ask`、`Ledger.affordances()` 也按工单 14 返回 `[]`，文档却写着"所有交互走对话"。修法是把**既有**的 `speak` 收件人解析扩到一个已接受案件的 System 对话者，不新增动作种类：
  - `Ledger.addressable(actor, name)`：只有受约束角色、且 `name` 归一化后等于种子 `system.name` 才为真（不猜别名——猜出来的名字会把它变成万能应答口子）。`Ledger.answers_to(actor)` 是同一判据的简写：**别人点名它时引擎不做任何路由**，内核照旧判"未知收件人"，因此它不会对未受约束的角色应声，也不把自己的存在泄进别人的回执。
  - `Ledger.converse(world, actor, line)`：把这句话交给既有 `query`（fact table 逐字匹配、查询次数硬上限、命中只给答案——**结案与报酬不在命中时**，见下文 E94），把四种拒绝（`closed` / `limit` / `malformed` / `unknown`）各翻成一句台词：答不了就是"不知道"，用尽/结案就是"闭口"。`query` 的异常文本与语义只在结案时机上改（票 93），并带 `context["ledger"]` 这个机器可读原因。答案本身仍走既有 `system_answer` 私有事件（下一回合由 `prompt._system_sentence` 渲染成它听见的一句话），**不进 tool 结果**——那是已实现、已测试、只为受约束角色可见的那条通道。
  - 引擎侧在 `_execute_chain` 的 speak 分支路由（受约束角色点名台账 → 不 `speak` 进世界、不产生 `speech` 事件、不触发说完等回应；**账目上仍算一拍**，由回合末尾那条发呆 `wait` 归因）。忙态照旧拒绝。若同一句 `to` 里还点了别人，回执明说"这些话只对台账说了，同场的人没有听到"并给出重发的写法——不静默丢收件人。
  - 发现性：`system_case_accepted` 的叙述里点明"要问它，就当面对着「台账」说话"，`speak` 的工具说明加一句"`to` 也可以写世界内一个会回话的对话者的名字"，受约束角色把台账叫错名字时拒绝里给出真实写法。三处都是提示层措辞，不改变任何语义。
- **连续空回合的后果要说回给角色（E93）**。诊断先说清楚：陈默 08:42–09:04 的九个回合是**模型零工具调用**（`intention: null`、`content_private` 81–142 字、provider 故障 0、无重试、无 `decision_failure`），每拍世界只发生一件事——引擎按 §4 提交的那条 60 秒 `wait`（`action_started`/`action_completed` 成对，时钟每拍前进约两分钟，其中一分钟是决策在飞期间的时钟推进）。所以不存在"引擎重试"或"时间凭空消失"，问题在**反馈**：`empty_turn` 记了，但那一拍的后果从没回到他的输入里，于是他在正文里把台账的三条款答了五遍，每一遍都像已经答过了（ticket 64 的自纠只在正文像在对人说话时发；他写的是一份"已答好"的答案）。修法两处、都不改时钟：
  - `_empty_streak[actor]` 计数（进检查点，旧检查点缺键 → 0），`empty_turn` 的 payload 多一个 `streak`；有工具调用的回合清零。
  - 零调用的回合把 `NO_ACTION_NOTE`（`natural_agent`）追加成一条 user 消息，走与 ticket 56/64 相同的排序规则（在 tool 结果之后），内容说清"那段想法没有改变世界、时间照常过去"，并给出两条出路（工具 / 明确 `wait`）；连续第 2 拍起附连续次数。有界：一拍一条，不叠加，有调用即不再追加。
- **"钉住的文书"用既有的固定陈设声明（报 90 §8 / 票 86 §5）**。裁定：文书默认是**可移动的纸**（`场地申请表` 就是让人自取的），一块钉在墙上的公告栏、一张贴在板上的通知则是固定陈设——它们由种子写 `takeable: false` + `fixed_reason`，与 `items:` 同一机制。引擎侧只做一处泛化：`fixed_items` 现在也从 `documents:` 行派生（`world_loader`），`_validate_descriptions` 对文书同样校验这两个键的类型。缺省仍是可拿，语义没有悄悄改变；三个公告栏要由种子标上 `takeable: false`，引擎不靠名字猜"哪个听起来像板"。
- **回归**：`harness/tests/test_historical_failures.py` 的 `LedgerDialogueGates`（E92：受约束角色拿到事实表答案且只投递给它、条目外答"不知道"且不吞额度、用尽即闭口、未受约束角色不被应答、叫错名字拿回真实写法）、`ConsecutiveEmptyTurnGates`（E93：每拍记 `streak`、每拍只有一条发呆 `wait`、下一拍收到反馈、有调用即清零）、`NoActionNoticeTextGates`（反馈文本本身）；`harness/tests/test_world_pack.py` `PlaceBoundDocumentTests`（文书 `takeable: false` 不进候选、拒绝用种子的理由、缺省仍可拿）。

### 7.7 台账的结案时机与三块“钉住的板”（ticket 93，2026-10-18 裁定）

票 91 §4-2 留了一个产品语义问题：`Ledger.query` 一命中就把 `status` 置成 `completed` 并发报酬，于是 `query_limit > 1` 的种子实际只答一次，`limit` 分支在正常流程下不可达；而接口文档写的是“查询次数硬上限”，故事文档把结算排到了 d7/d12。用户裁定：**结案由种子排程的结算事件驱动**，首次命中不结案。

- **结案 ≠ 首次命中（E94）**。四处变化：
  - `query` 命中只提交 `system_answer`、`queries_used += 1`、记下 `last_answer_event_id`；不再改 `status`、不再发报酬。额度用尽只回 `limit`（“闭口”），不再消耗配额、也不结案；只有 `status == "closed"` 之后才是 `closed` 那句台词。
  - `Ledger.settle(world, cause)`：结算节拍到达时结案，报酬仍走**既有** `system_reward_granted` 私有事件（只投给受约束角色），payload 的 `evidence_event_id` 指向这案唯一那条答案（没答过就不带这个键，不拿空值顶）、`settled_event_id` 指向那条排程事件。幂等：未接受或已结案时什么都不做，所以同一节拍被扫描两遍也只发一次。
  - 引擎在 `_after_advance` 扫描新事件时，只认 `event.payload["event"] == Ledger.settle_on` 的那一条（不是“任何世界事件”，同一个 advance 里的其他节拍不会结案）→ 调 `settle`。`settle_on` 是种子事实（本种子 `ledger_settlement`，3/22 15:00，对应 V4-STORY-MILESTONES §3 的 d7「台账结算」）；`world_loader` 在加载时校验这个名字点得到 `scheduled:` 里一条真事件——点错名字的后果是“永不结案”，所以就在加载时大声失败。
  - `Ledger._reconcile`：`Ledger` 本身不进检查点（`real_run`/`resume_run` 按种子重建），所以 `status` 与 `queries_used` 从世界日志重建（`system_answer` / `system_reward_granted` 都只由本台账产生、都在检查点里）——恢复后案子不会又开着，也不会白送一次新额度。
- **三块公告栏是钉住的陈设（种子侧，E92 移交的那一项）**。票 91 只把机制泛化到 `documents:`（`takeable: false` + `fixed_reason`），并在 §4 把“哪个听起来像板”留给种子判断；本票在种子里把 `公告栏` / `教学楼公告栏` / `女生宿舍公告栏` 三条标成固定陈设，各带一句自己的 `fixed_reason`。于是它们照旧在场、照旧可 `read`，但 `take`/`give` 就地分支/`trash` 结构化拒绝，理由是种子那句原文，“这里能拿的”清单里不再出现它们；缺省仍可拿（`场地申请表` 那种让人自取的纸一字未改）。
- **回归**：`harness/tests/test_historical_failures.py` 的 `LedgerClosureGates`（E94：两次命中都得到答案且案子仍开着、超限闭口而不结案、结算节拍到达才 `closed` 且报酬只投给陈默且只发一次、不是结算的世界节拍不结案、真种子冒烟：`ledger_settlement` 确在排程里且 3/22 15:00 到点才结案）；`test_world_pack.py` 的 `LedgerSettlementSeedTests`（`settle_on` 点错名字 → 加载失败）、`PlaceBoundDocumentTests`（新增真种子三块板的一支：在 `fixed_items`、不在 `take` 候选、拒绝理由用种子原文、`read` 照旧）；`test_kernel.py` 的 `test_a_correct_answer_does_not_settle_the_case` / `test_the_seeded_settlement_closes_the_case_and_grants_the_reward_once`（旧 `status == "completed"` 那支按新语义重写）。

### 7.8 台账可答性、同行、事件范围、文书补写与递物候选（ticket 95，2026-10-18 窗口 4 裁定）

窗口 4（07:00→17:00）的五个缺陷都在“世界可做性”上，修法要么是既有原语的参数化，要么是作用域修正——没有新增动作种类，没有新增世界状态字段。

- **台账事实表的确定性匹配（E95）**。窗口 4：陈默 5 次 `speak(to=["台账"])` 全部 `submitted`，`system_answer` 0——`facts.get(question.strip())` 要求逐字命中三条问句，而他从没见过那三句；拒绝在世界日志里也 0 痕迹。修法：
  - 条目两种写法：旧 `问句: 答案` 与 `问句: {answer, keywords: [...]}`；条目自己的问句永远也算匹配词（旧逐字问照旧命中）。
  - 归一化：NFKC（全角/半角）+ 既有 `kb.normalize`（空白/标点/`的`/`之`）；命中 = 词出现在问句里或问句整句出现在词里；按命中词数打分，唯一最高分且 >0 即答，并列或零分答“不知道”。**不调用模型**。
  - 每次对话（含拒绝）提交一条只给提问者的既有命名空间的私有事件 `system_dialogue`：`{system_name, case, question, matched, outcome, answer_event_id?}`（`outcome` 区分 `answered/unknown/tie/limit/closed/malformed`；命中才带答案事件 id；引用缺失不拿空值顶）。`_reconcile` 仍只数 `system_answer`，所以恢复后的额度不受审计事件影响；`prompt._event_sentence` 明确不为它渲染一行，`runner` 也只把真正的 `system_*` 口信交给角色。`world_loader` 的 strip 循环现在**保留 mapping 形状**（对 dict 直接 `strip_refs` 会把整条事实 stringify 成 Python 字典字面量，keywords 能力在真种子上失效且答案变成 dict 字面量），并在加载时校验 facts 形状（写错 = 永远答不上，所以大声失败）。
- **`move` 可以带上人一起走（E96）**。窗口 4：世界没有“扶/陪”原语，305 又不是地点，17 个角色在 6h51m 里重复“我不能实际扶你”。修法：`move` 的可选 `with=[同在此地的人]`。
  - 校验：每位被携带者必须同处一地、不是自己、没有待处理的 continue-or-abandon；当前动作 `uninterruptable` 或自己正在走另一段 `move` → **整次 move 结构化拒绝**（回执点名是哪一个人、为什么，不开始任何动作）。
  - 执行：发起者提交时各自 `leave` 原地；`_move_hop` 按发起者的 path 逐跳推进，每位被携带者产生自己的 `leave`/`enter`（payload 带 `escorted_by`），与发起者同一时刻、共享连续 world version；`action_started`/`action_completed` 仍是发起者私有的簿记，不给被携带者伪造动作。
  - 自主与脱离：被携带者保有感知与自己的动作（边走边说可以）；若其当前动作不可打断、进入 pending、或自己开始走另一段 move，`_follows_escort` 判定不再跟随（“中途拒绝”）。replay 只靠 `enter` 重建位置，已覆盖中断/脱离。
- **`world_event` 的可选地点作用域（E97）**。窗口 4：`_visibility` 对 actor is None 的 `world_event` 返回全场，于是 16:00/16:20/16:45 三条排程事件连正文一起广播 12–14 人（陈默在档案室提前 3 分钟知道定向给他的原话）。修法：payload 支持可选 `location`——有它时可见集 = 该地点在场者 +（若有）`target`；只有 `target` 时不变；两者都没有仍是既有全局广播（校园公告/铃声/天气）。`world_loader` 在加载时校验 `location` 是已知地点（点名不存在的地点 = 没人看得见，所以大声失败）。
- **`leave_note on=<文书>`：在既有文书上补写/签名（E98）**。窗口 4：`面核记录` 要求“谁到场核对谁填自己那一栏”，但工具面没有 annotate（`document_annotated` 与 `annotations` 存储早已存在却无入口），班长只能另贴字条，面核记录 0 人签。修法：`leave_note` 的可选 `on`——
  - 校验：文书必须是 `document_defs` 里的一份且当前可读（同地或手上）；`on` 与 `persist` 互斥；不在这里 → 结构化拒绝并列出“手边能写的”。
  - 执行：`_complete` 把文字追加进该文书的 `annotations`（`{text, by, time}`，只追加、不覆盖），`_commit_interaction` 改发既有的 `document_annotated`（同地点可见），不再是 `note_left`。批注正文与文书正文同一条隐私线：`_public` 对非作者剥掉 `annotation`，同地的人只看见“谁写了字”；读过的人在 `read` 的 tool 结果/`document_read` payload 里拿到全部批注。replay 用既有 `document_annotated` 分支重建。
  - 发现性：`action_schema` 的 leave_note 说明与 `engine.VERB_GAP_TEACHING` 的签字/批注条都改为指向 `leave_note on=`（旧的“写不了”已不成立；§2.2 文档块仍与常量逐字一致）。
- **手边物品出现在 `give` 候选里（E99）**。窗口 4：食堂大妈全天 `give` 0 次，窗口 11:00 的“有人守窗口”只兑现成一句招呼，两份饭都被自取（11:00 上台的午饭 48 分钟后才被拿走）。引擎早已支持“就地取再递”（ticket 63），缺的只是可见性：`affordances()` 的 `give` 候选 = 背包 ∪ 当前地点可拿物品（排除固定陈设）；拒绝回执的可行调用清单也含手边物品；工具说明写明可以直接递。
- **回归**：`harness/tests/test_historical_failures.py` 的 `LedgerFactMatchingGates`（E95）、`EscortMoveGates`（E96）、`WorldEventScopeGates`（E97）、`DocumentAnnotationGates`（E98）、`GiveAtHandAffordanceGates`（E99）；`test_kernel` 的两支台账测试按“审计事件也入日志”的新事实校准；`test_world_pack` 的 facts 形状校验与 `test_historical_failures` 的 verb-gap 块仍与文档逐字一致。

### 7.9 可选参数的空值、单件归属与陌生人的场景事实（ticket 98，2026-10-18 窗口 5 裁定）

窗口 5（07:00→18:00，run `real-20261018T062031`）的五件事里有四件真的落地了（同行、台账、文书补写、排程作用域），但票 95 给它们新增的**可选参数**都缺一条“空值等于未提供”的语义，于是同一天 182 条拒绝片段（175/1670 = 10.5% 的回合）烧在两条自循环上，并把两条假的世界规则教给了角色。本轮的四处修法都不新增动作种类、不新增世界状态字段。

- **`leave_note` 的空 `on`（E100）**。校验用 `if on is not None` 判“同时声明了 on 与 persist”，`on: ""` 于是把“留一份新文稿”自己判成冲突：全天 106 条拒绝（陈默 60，08:06→17:19），他从 11:25 起逢人就说“我三次尝试留书面说明都没有成功”，而他的《个人情况说明》全天没写成。修法：`on` 只有**非空字符串**才算写进既有文书；`submit` 入口一次性把空串/纯空白的 `on` 从 args 里剔除，后面的校验、`action_payload`、`_complete`、`_commit_interaction` 与 replay 只看一种写法（不做双份判定，避免“只有一处 strip”的分歧）。
- **`move` 的空 `with`（E101）**。76 条“with 里有一个空名字”，相邻形态 `["_self"]`/`["陈默(you)"]`/自己——模型在找“一个人走”的表达法，而接口只有“不写 with”，回执里的 `Valid call` 实测 7 连未纠正；唐小岚 13:04 因此对外说出“移动需要明确同行者”，13:19–15:08 逐人求同行。修法：`_canonicalize_companions` 先过滤空项/纯空白项、去重，过滤后为空就把 `with` 整个键去掉（与没写完全同一条路径）；`action_schema` 的 `with` 去掉 `minItems: 1`（空数组合法）；工具说明与未知名字的拒绝都明写“一个人走就只写 target”，常量 `kernel.WALK_ALONE_HINT` 是那一句的唯一出处。
- **单件归属（E102）**。17:57 陈默与辅导员各自 `take 一份晚饭`：两条 `action_started`/`action_completed` 全部成立、只有先完成的那位背包里真的有它（辅导员 17:59 还对外说“我们都拿了晚饭”）。成因：`take` 的归属只在**完成时**写进世界，提交期只查 `item_locations`，同一 tick 的两次提交都看到它还在桌上。修法：提交期加一次“在途占用”检查——`_item_claimant` 读各 actor 的 `current_action`/`pending`（随检查点保存，无需新字段），第二个 `take` 得到“正被 X 拿在手里”的结构化拒绝；`give` 的“就地拿起再递出”（票 63）是同一个族（两个人各递一次同一份饭会让两个收件人背包里都有一份），同样占用；完成期的防御分支保留（旧检查点里可能真的排着两条），但条件收紧到“还在我这里/还在这个地点”，不再隔空取物。拿完之后再 `take` 的回执改说真话：`_take_rejection` 依次报“在 X 手上 / 在 Y 地点 / 已经不在世上”，只有**从未注册过的名字**才说“这里没有”，不替不存在的东西编一段被销毁的历史。
- **陌生人的场景事实（E103）**。15:04 唐小岚读了 `代话便条`，15:06 她向“陌生人”求同行，当场生成的 `张学长` 把便条原文当“老板娘留的话”说了出来——她还没送到的话被提前兑付一次。诊断（该回合的 perception 实录）：extra **没有**拿到提问者的 KB/记忆，泄漏通道是**场景事实块**——`scene_perception` 把同地每件东西的 `entity_descriptions` 全文给它，而这份便条的“客观描述”就是便条正文，种子已把它声明为 `known_to: [唐小岚]`。修法：extra 的输入 = 当面听到的话 + 该地点的**公开**可见物 + 自己的身份；`_described_to` 让被 `known_to` 限定给别人的东西只出现在 `nearby_items`（看得见它在场），不发描述正文。公开物件（`校报草稿`）照旧给描述，票 57 的“一份不是一摞”数量锚点没有被削弱。
- **同行途中的 extra 被当成“闲”回收（E104）**。15:06 张学长应下“愿意陪你去”，15:08 随唐小岚 `move 后街糕点铺 with 张学长` 出发，15:15 两人同到小卖部，15:19 它在下一跳（780 秒）途中得到 `extra_removed reason: idle`——唐小岚 15:28 独自到夜市、15:33 独自到糕点铺。成因：idle 判据只看 `last_active`（上一次开口/动手的时刻），而被携带的整段路它没有也不该有动作事件。修法：`AsyncEngine._extra_is_idle` 把两种在场状态排除在 idle 之外——它正被一次 `move` 携带着赶路（它自己也在这段路上，或它是别人 `with` 里的同行者），或它还有一笔没结的对话（`pending_question`、已听到还没回的 `pending_heard_speech`、供给方还在写的那一句 `_extra_inflight`）。被携带者要离开仍走既有“途中可脱离”的路：他自己开始走另一段 `move`，`_follows_escort` 便不再带他；到站站定后 idle 照常计时——回收不是他离开的出口。存量 `Runner` 的同名路径本轮不动：它不执行同行的 extra（extra 自己 move 即结束对话，§8）。
- **回归**：`harness/tests/test_historical_failures.py` 的 `BlankNoteOnGates`（E100）、`BlankCompanionGates`（E101）、`SingleInstanceTakeGates`（E102）、`ExtraScenePrivacyGates`（E103）、`EscortIdleGates`（E104）；`HistoricalFailureGates.test_take_race_second_completion_does_not_crash_the_clock`（E75）按更紧的不变量重写——第二次**提交**已被拒绝，完成期防御分支只剩恢复旧检查点这一条路，于是直接喂给它一次完成；`SeedLocationPropGates` / `Ticket65CanteenServeGates` / `SameKindFailureGates` 三支按“未注册的名字不说被销毁”的事实校准。
- **仍然开着**：`poll` 的 `descriptions`（主角色，不是 extra）同样把 `known_to` 限定物件的描述发给同地的其他人——窗口 5 里任何站在半坡咖啡馆的角色都能看到便条正文。收窄它要动票 49/61 已定的“走到/拿到就给客观描述”，属于另一条裁定，本票不动（见票 98 §4）。

### 7.10 便条可递、睡眠与“没被问”的诊断（ticket 101，2026-10-18 窗口 6 裁定）

窗口 6（18:00→22:00，run `real-20261018T073833`）把同一个病灶换了一种形状暴露出来：字写得出、读得到，就是递不出去；而“睡觉”没有表达法，于是 4 小时夜里 211 个回合中 43% 是 `wait 900`。四处修法都不新增动作种类、不新增世界状态字段（便条的持有者就是背包里的一项，随检查点与事件一起重建）。

- **便条可递（E105a）**。18:44 陈默在宿舍写了一份署名说明（`note-陈默-1`，三人读到），18:48 想 `give note-陈默-1` 给辅导员被拒——“你没有拿着「note-陈默-1」…可行调用：give 2013年邻里撤离通知书”，而那张 2013 年的通知书与他的意图毫无关系。成因：`give` 只认 `inventory` 与 `item_locations`，`persistent_notes` 是另一张表。修法：可递物 = 物品 ∪ **已存在的便条 id**——便条本来就在世界上，递它就是递那张纸：
  - 校验：便条必须在作者手上（`inventory` 里）或留在他所在的地点且不在别人手上；否则拒绝并只说它在谁手上/哪里，不再给无关文书的“可行调用”。
  - 执行：`_complete` 把便条 id 从发出者背包移到收件人背包并更新它的 `location`；事件仍是既有的 `item_given {item, from, to}`，replay 把同一 id 放回同一只手上。
  - 可见性：`available_now` 对不在任何背包里、且位于本地的便条才算“留在这里”；被递出去的便条同地其他人不能隔着手读（读被拒时说清它在谁手上）。`place` 放下一张便条 = 它又变回“留在这里的纸”。
- **写在一张纸上（E105b）**。19:07 `leave_note on:"空白纸"` 被拒——“这里没有可以在上面写字的文书「空白纸」”：`on` 只查当前地点的 `document_defs`，而空白纸是背包里的物品，于是“我在手里这张纸上写”没有任何一个参数组合能表达。修法：`on` 按**目标类型分派**——
  - 有正文的文书（`document_defs`）→ 既有批注路径（E98，`document_annotated`）；
  - 无正文的纸张（不是文书、不是固定陈设、手上或眼前，且自己的客观描述里既是“纸”又能“写”，`WRITING_SURFACE_HINTS`）→ 那张纸变成一份带编号的文稿（同 `persist` 的那一种）：`note_left {on, persist: true, note, text}`，纸从背包/地点出账，文稿进作者手上（可以直接 `give` 给别人）。
  - 两样都不是 → 拒绝，列出此刻真的能写的（文书 + 纸张），不推荐别的东西。
- **睡眠（E106）**。夜里 7 次 `wait 34200–48960`（“睡到明早”）被 900 秒上限拒收，模型只能 15 分钟一觉撑到天亮；19:14–21:24 有 2h10m 的结构空转。修法：`wait` 增加可选 `sleep: true`（仍是同一个动作，§2 早已裁定 sleep 并入 wait）：时长上限 `SLEEP_WAIT_SECONDS`（12 小时），`sleeping` 字段在起睡时置真、完成/被叫醒/被打断时清零，可见性沿用既有“等待不是风景”（他人看不见你在睡）。唤醒：同地社交事件照旧经 `wake_waiter` 提前结束；另加 `World.wake_sleeper`——payload 里 `target` 点名他的 `world_event` 也能叫醒睡着的人（未点名的全场广播不叫醒）。超出上限的普通 `wait` 拒绝时直接教给 `sleep: true`（`kernel.WAIT_SLEEP_HINT`）。
- **“没被问”也是空回合的一种（E107）**。18:00 胡大叔 `result: none`、`calls: []`、`inner: null` 而夜间没有一条 `empty_turn`——它不是“被问了没输出”（E90 已覆盖），而是 18:00 从检查点续跑时 restored extra 的第一拍：既无待答问题、也无新听到的话，`needs_response` 为假，**模型根本没被请求**（判定依据：续跑后 provider 调用 0 次，而 trace 里仍有一行 `result: none` 的 agent 回合）。修法只加诊断：这一种也记 `empty_turn`（`reason: no_request`），两种空回合从此可分辨；世界不变、不惩罚角色。
- **机制不得进入对白（E108，提示层）**。19:12 陈默对在场三人说“刚才的留字只生成了下一位进入者才看得到的字条”——机制上正确，因此才证明它是从提示语/回执里推出来的引擎知识。“引擎只管写自己在做什么、谁看见了什么”这一句以常量 `action_schema.NO_MECHANISM_IN_SPEECH` 只加在 MC 的工具说明上（`leave_note`），NPC 与路人的提示一字未加。
- **回归**：`harness/tests/test_historical_failures.py` 的 `NoteDeliveryGates`（E105：写在纸上→交出→读到全文、留在桌上的文稿也能递、拒绝不推荐无关文书、replay 同 id 同手、纸被写掉、提示里说得出能写的纸）、`SleepWaitGates`（E106：8 小时睡眠且时钟推进、被叫醒提前结束且普通 wait 不受影响、点名事件叫醒而广播不叫醒、replay 与检查点带睡眠）、`ExtraNoRequestTurnGates`（E107：续跑首拍 provider 0 次调用仍留一行可审计记录）、`NoMechanismInSpeechGates`（E108：那句规则在 MC 工具说明里、不在 NPC/路人提示里）。

### 7.11 一沓纸的容量、值班岗位与两条 D2 判据（ticket 113，2026-10-19 裁定）

D1 第三次全天验收（`real-20261018T113143`，已丢失，见 `runs/README.md`）首次三门禁全绿，但断在两件机制上：**整座校园只剩一份纸，而且已经被写掉**；**收件档开张，收件人不在自己的办公室**。四处修法都不新增动作种类。

- **一件纸有几张（E1，`count: N`）**。票 110 以为缺的是 id 数量，给六个纸 id 各补了一件；真正缺的是“沓”的容量：18:25 陈默取走唯一一份 `说明用纸`，18:27 `leave_note on=说明用纸` 把整叠纸写成一份便条，18:42 起班长/林瑶室友/林瑶/陈默/辅导员依次 `take` 失败（“已经被拿走或销毁”），19:00–22:00 收件档零交件。修法：
  - 数据：`items:` 行可声明 `count: N`（正整数，装载期校验；不写 = 一张，旧语义不变）。它同时是**容量**（种子）与**余数**（运行状态，`world.item_counts`，随检查点与事件走）。
  - 执行：`_complete` 的 `leave_note on=<纸>` 改为“写一张少一张”——余数 > 0 时那沓仍是纸（位置与持有关系都不动，别人拿去还能写），余数到 0 时那沓空了、从世界上出账；写好的那份文稿**一直是作者手上另一样东西**，不是纸变来的。提交时把 `count_left` 写进 action payload，所以回执、replay 与中途检查点看到同一个数。
  - 回执：旧回执把写在纸上的文稿说成“作为一条批注追加进《空白纸》”（`on` 一律按文书分派），这是动作—结果误解；现在按目标类型分派，纸张路径说清余下几张、文稿在谁手上、要交出去用 `give`。
- **值班岗位就位（E2，`place_actor`）**。18:00–22:00 辅导员在自己的办公室里 0 回合：制度、18:30/19:00 两条通知、她自己的知识行都写着“十九点到二十一点我在办公室”，可世界没有任何机制把她放到那个岗位上。修法：排程效果新增 `place_actor {id, location}`——它陈述的是“这段时间这个 npc 在这个岗位上”的制度事实，不替他做主（她说什么、还去不去别处仍由她自己的回合定）。装载期只允许 `role: npc`：把玩家角色放到某处就是替他做主，是剧本不是世界。`apply_world_effects` 是运行时与 replay 的同一入口，所以重建一致。
- **种子补齐八点清点**。18:30 与 19:00 两条通知、两处知识行都写着“明早八点的缺件清点在同一个地方当面做”，但排程里**没有**这个八点的事件——一个声明了却没有机制的事实。新增 `statement_count_d2`（3/17 08:00，点名辅导员与四名经手人）并把辅导员放到岗位上；不替任何学生到场、写稿或交件。
- **两条 D2 判据要有区分力（E7/E8）**。旧 `d2-恋爱私人对话` 只要两人同场互有发言——D1 已有 65 条，全是任务性对话；旧 `d2-审计说明提交` 只要出现“说明”与“提交”——“我还没提交说明”也 PASS。修法在判据层（`scripts/check_milestones.py`）：私人对话 = 那条发言的 `heard` 只有对方（无第三方）且正文不含案子上的词，双方各至少一条；说明提交 = 本人 `leave_note` 写出的《个人情况说明》文稿本人 `item_given` 交到辅导员手上，且在 08:00 清点档内（≤09:00），迟到只报不计。两条各配反向夹具（D1 形态必须 FAIL）。
- **回归**：`harness/tests/test_item_counts.py`（写一张少一张／最后一张用完后这沓出账／不写 count 保持旧语义／手上那沓不动／检查点与 replay 同余数／回执说余数／六个纸 id 都声明容量／装载期拒绝非法容量／排程放 npc 上岗／replay 同位置／装载期拒绝放玩家角色）、`scripts/test_check_milestones_d2_anchors.py`（九支正反向夹具）、`harness/tests/test_pack.py`（紧凑工件）；`test_historical_failures.py` 的 `NoteDeliveryGates` 按新契约校准（那张纸不再“写满即消失”，改为张数减少且仍可写，并清掉排程以隔离场景）。

## 8. 实现映射

- **替换**：runner.py 轮询主循环与 waiting/npc_pending/extras 三条 ad-hoc 路径 → 统一协程循环（§0）。迁移期间旧 `Runner` 仅作为存量测试的遗留驱动保留，生产入口（real_run/resume_run）已切换 `AsyncEngine`。
- **直迁**：kernel 校验、事件渲染模板、KB 机制、别名遥测——渲染层管"是什么"，改为唤醒时调用即可。
- **常数迁移**：`*_rounds`（poll 计数）→ `*_minutes`（模拟时间；AGENT-INTERFACE §7 已更新）；迁移时 last_shown 语义一次性核定。
- **语义变化**：`batch_persistent_failure`（§6）、`idle_slice`（=1 tick）、`decision_timeout`（= 静默弃权触发器）。

## 9. 已裁决否决与未排期项

- **否决——逐对光锥/局部时钟偏斜**（远距无电话者放宽偏斜）：传言网络使真实传播延迟不可计算，最大流假设是唯一安全上界（§2.2）。
- **否决——冻结规则回填时间戳**（迟到意图按原 deadline 落账）：破坏全序与渲染因果（§2.3）。
- **否决——引擎追踪谁知道谁用于因果**：known_contacts 降级为动作层门控（§2.2）。
- **未排期——子 tick 对话窗**：同窗内同对话方往返免费；若首验日显示对话节奏仍太慢再议。
