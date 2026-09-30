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
3. **全局决策视界（冻结规则）**。在途意图的 deadline 即其唤醒（或中断投递、超时到期）时刻。引擎只处理时间 ≤ `oldest_pending_deadline + 1 tick` 的事件（即：任一决策在途时，世界至多漂移 1 tick）（他人链条完成、投递、reminder、导演拍点都只是事件）；第一个超界事件是**冻结点**——全钟暂停，直到意图落地或静默弃权（§3）。时钟永不跳过未清的 pending deadline；**禁止回填**（backdating）：迟到意图按当前钟提交。对比旧串行 runner 零回归：只是限制了能提前流水线的工作量。force-turn/wake 不得覆盖普通 `busy_until`；被打断的 `pending` 动作例外，仍须立即给出 continue-or-abandon。若串行工具链的前一动作越过一 tick 地平线，后续调用逐项收到真实完成时刻和重试形状的 `not executed` 结果；链不再推动时钟，也不把普通 busy 误称为待恢复中断。
4. **同 tick 排序 = 意图到达序**。同 tick 多个意图按 wall 到达序执行，资源竞争按提交序串行判定（AGENT-INTERFACE m8）。含义：同 tick 竞争不可种子复现——种子调度不得制造其结果依赖的同 tick 竞争；journal 逐字记录实际发生序，回放不受影响（§7）。
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
- **空闲心跳**：等事件状态的角色若无事件永不再醒。MC 有空闲心跳 `mc_idle_heartbeat`（默认 30 分钟，醒来时世界消息照常渲染）；NPC 无心跳（只由 CAST §2 触发器唤醒）；extra 无心跳（对话期生命周期，`extra_idle_timeout` 无新对话即销毁，不要求它此前必须说过话）。
- **extra 场景上下文**：一次对话只保留 scene-local、有界 transcript（最近至多 8 句/单句 180 字/总计 1200 字），以世界事件 `visible_to` 的实际投递名单筛选（`speech.payload.heard` 只是与之保持一致的镜像）；speaker 自己刚说的话也可保留。绝不凭当前共处推测历史受众，不向 extra 投递其未听到的 whisper/private speech。对额外角色的公开发言会唤醒同场 extra，即使 speaker 不是最初搭话者；提供方在途期间抵达的可听 speech 要保留为待处理唤醒，不能被清游标吞掉。system 与 speak-only 工具前缀在一个 extra 生命周期中固定；没有新可听 speech 时不发模型回合、不伪造空问题；extra 可沉默/告别，超时即销毁，不写长程记忆（AGENT-INTERFACE §5）。

## 4. 对话节奏

- 每条 speak 恰 1 tick。光锥只延迟**回应**，不禁止同 tick 多人各提交一句：N 人各说一句的一轮 = 1 tick，M 轮对话 = M tick。tick=1 分钟 → 十轮对话 ≈ 十分钟模拟时间，节奏自然。
- 子 tick 对话窗（同窗内往返免费）未排期，见 §9。

## 5. r 旋钮（realtime-ness）

- 配置 `realtime_ratio`，默认 0。r>0 时：回合间思考/解析的 wall 延迟 × r 计入模拟时间（意图到达 = 唤醒时刻 + r×wall 延迟，下限 1 tick）；时间戳连续、离格。
- 作用域仅**回合间思考**——链内时间是世界物理，已有建模。后果：think 不再严格免费，犹豫有世界价格；决策越慢越迟到。
- **确定性边界**：r>0 时 wall 延迟不可复现 → 种子级确定性只在 r=0 成立；journal 回放（重放已记录的到达序）与断点续跑不受影响。首验日 r=0。

## 6. 失败隔离

- per-actor：连续 `batch_persistent_failure`（3）次失败 → 该角色弃权发呆，世界继续；**绝不冻结全钟等一个死 provider**。旧"世界停机"闸门语义废除。
- 全局停机仅两途：全体角色连续失败 / `max_wall_seconds` 耗尽。
- **冻结记账**：每次冻结按 wall+sim 时长与责任角色入 trace（模型 A/B 经济学：谁在拖累世界）；`stall_budget_ratio`（默认 0.25）——冻结累计占墙钟预算超比例 → 以诚实原因终止。

## 7. 检查点、日志与确定性

- **journal**（append-only：意图提交 + 事件，含时间戳与到达序）是事实流 SSOT；状态 = journal 折叠 + 快照。
- 恢复 = 快照 + journal 尾部重放 + 重挂计时器。KB 与 last_shown 状态引擎侧保存；会话转录与 compaction 边界亦入检查点——恢复不得重放已计 last_shown 的行（防首跑洪泛）。
- extra 的对话期可变状态随检查点往返：冻结的 system 前缀、场景游标 `context_cursor`、待答问题 `pending_question`、待听语音 `pending_heard_speech`、到场/活跃时刻。半天分段续跑（d1-am → d1-pm）恢复后，场上活着的 extra 必须接着答它未答的问题；旧格式行（缺这些键）按 `fragment`/`knowledge_notes`/地点/名字重建前缀并给安全缺省，绝不因缺键 KeyError（ticket 50）。
- trace 改为：每角色时间线 + 全局 journal——比回合快照更强的 happens-before 分析材料。
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
