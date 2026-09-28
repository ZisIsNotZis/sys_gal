# 11-engine-async-semantics-docs

Status: done
Need-review: false（纯文档；SSOT 一致性经 fresh-context reviewer 验证）

## Issue

v4 引擎改为 async 离散事件内核（每角色一个协程循环 + 引擎事件队列）的时序语义需要落档，并清理既有文档中与新语义及既有裁决冲突的陈述。

## 裁决内容（用户 2026-09-08 会话确认）

- tick = 1 分钟（config）；全局光锥：T 提交 → T+1 tick 才可感知（最大信息流假设）。
- 全局决策视界：只处理 ≤ oldest_pending_deadline + 1 tick 的事件，超出即冻结全钟；静默弃权 = 发呆 + 挂起动作自动 continue。
- wake ≠ interrupt；中断绑定于执行位置；同 tick 排序 = 意图到达序（同 tick 竞争不可种子复现）。
- realtime_ratio 旋钮（默认 0；r>0 失去种子确定性，journal 回放不受影响）。
- 对话节奏：1 tick/utterance，同 tick 多人各一句，M 轮对话 = M tick。
- known_contacts 降级为动作层门控，因果零角色。

## 变更文件

- `v4/docs/V4-ENGINE.md`（新建，引擎 SSOT）+ `V4-ENGINE.qa.md`（验证问答）
- `v4/docs/V4-AGENT-INTERFACE.md`：tick/常数表改 sim 分钟；常识 5→1 分钟；新增引擎常数（decision_timeout/stall_budget_ratio/mc_idle_heartbeat/extra_idle_timeout/realtime_ratio）；reminder 统一为 force-interrupt（消除文内自相矛盾）
- `v4/docs/V4-DESIGN.md`：SSOT 指针、tick 措辞、asleep 残留清除（对齐 M1）、首验日段落
- `v4/docs/V4-CAST.md`：MC"时钟驱动"→"事件驱动 + 空闲心跳"；NPC 滚动摘要残留下线（对齐 AGENT-INTERFACE §5）
- `.scratch/v4-first-day/spec.md`：tick=1min，设计真理指针加 V4-ENGINE.md

## Comments

- 2026-09-08 agent(pi, 当前会话模型): fresh-context reviewer 五问全答对（仅凭 ENGINE 单文）；发现 2 处矛盾（reminder 语义文内自相矛盾、CAST 滚动摘要残留）均已回修。否决项（逐对光锥、回填时间戳、因果级通讯录追踪）与未排期项（子 tick 对话窗）记录于 ENGINE §9。
- 2026-09-08 agent(pi, 当前会话模型) 实现切片: 引擎迁移落地——`harness/engine.py` 新增 `AsyncEngine`（协程循环 + 冻结规则 + 静默弃权 + 失败隔离 + 冻结记账 + MC 心跳 + CAST 机制移植）；kernel 语义迁移（tick=60s、全动作 ≥1 tick 取整、speak=1 tick、wait 同 tick 社交事件无操作化、wake_waiter 早醒、private_wake/heartbeat）；real_run/resume_run 切换 AsyncEngine（Runner 留作存量测试遗留驱动）；新增 test_engine.py 五条不变量测试 + historical gate 的 engine 版（F9/P1 双驱动）。全套 248 passed。决策记录：①None 意图不消耗 tick（协议级无决策，非世界内发呆；发呆由 wait 表达）；②NPC 不被环境事件唤醒（仅 CAST §2 触发器 + 非等待动作完成续拍，保持 1~N 动作/唤醒）；③冻结视界措辞按实现对齐（deadline=唤醒时刻，漂移 ≤1 tick）。待办：多工具链、think/update_memory/recall/flashback、kb: 种子段（AGENT-INTERFACE 迁移第二波）。
- 2026-09-08 agent(pi, 当前会话模型) 首跑验证: AsyncEngine + volc/deepseek-v4-flash 全种子日通过——1024 回合/2607 事件/57 min wall，零致命错误，事件日志连续无违反。遗留 6 项（详见 v4/runs/v4-engine-volc-analysis.md）：NPC 格式重试缺失、move 多跳寻路裁决、ask_stranger 空参前置拒绝、none 回合待接口迁移、冻结记账未入 trace、舞台指示 prompt 约束。
- 2026-09-08 agent(pi, 当前会话模型) 第二切片: ①multi-hop move 落地——引擎 Dijkstra 寻路（时长=地图物理），离散事件序列 leave A(t0)/enter B/leave B(同时刻)/enter C，逐地点可见性（被动地点可见、移动者全程可见），中途打断从最后进入地点续走（remaining_path/hops），replay 以 enter 事件重建位置；②schema 级校验补齐——send_message/annotate/label 的 text/label 加 minLength，校验消息派生 "expects 'x' to be non-empty"；③resume KeyError 胡大爷修复（extras 不要求 agents/states，engine init 按 non-extra 集合校验）+ 回归测试；④竞态修复——wait 无操作化谓词改为"存在未感知的社交事件"（对比 poll cursor），消除决策跨 tick 错过唤醒；⑤actor task 崩溃不再静默卡死引擎（trace 记 actor_task_crash）。252 passed；resume 冒烟通过（22:00→23:00 真实 provider 续跑 95 回合）。原 run 的 16 次 move 拒绝类问题随 multi-hop 消解。
