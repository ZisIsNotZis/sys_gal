# v4 引擎首跑分析：AsyncEngine + volc/deepseek-v4-flash（2026-09-08）

Trajectory：`runs/real-20260908T145714+0800-1794461-691971812.json`（7.1 MB，本地保存）；
checkpoint：同目录 `.checkpoint.json`。分支 `a63e8a3`（ticket 11 实现切片）。

## 结果一句话

新引擎一次跑通整个种子日（07:00→22:00 `world_stops`），1024 决策回合 / 2607 事件，
wall 时间约 57 分钟（预算 4 小时），零致命错误——种子日 × 速度 ≈ 15 sim-h/h，
新引擎的 wall 并发流水线比旧串行 runner 快一个量级。

## 实际发生了什么（lived trajectory）

- **社交密度**：376 条 speech，305/375 相邻发言对间隔 ≤2 tick——wake-early 机制让
  对话按 M 轮=M tick 的节奏真实往返；唐小岚（111 句，咖啡馆枢纽）、陈默（114）、
  林瑶（68）三线全程活跃，9 个匿名路人经 ask_stranger 现场生成并有效参与
  （胡学姐帮查电子台账、孙阿姨指路公告栏），44 条 message_delivered（电话/远程线在用）。
- **剧情纵深**：台账调查弧贯穿全天——陈默与唐小岚对汇总表两处无用途总额的复核
  （14:04-14:23），林瑶在档案室当面质询（11:26-11:28），晚间胡大爷"登记本可查不可抄"
  的规则谈判与陈默以值班学生身份的合规破解（21:56-21:59，唐小岚帮腔）。文档动作
  69 read / 24 compare / 11 annotate——调查型玩法成立。
- **MC 不可分辨性**：NPC（班长/宿管阿姨/胡大爷/罗阿姨等 12 人）被触发唤醒共 100+
  回合，消息结构与 MC 一致，无导演穿帮。

## 问题与根因（按协议逐条）

1. **NPC 输出格式崩坏（10 次 agent_error，全部是 NPC）**：班长 3、宿管阿姨 4、
   下棋大爷 1、朱阿姨 1——`output is not recognizable JSON` / `inner must be a string`
   / `unexpected top-level keys: ['speak']`。根因：MC 的持久会话代理内建格式重试与
   宽容重解析，NPC 代理（npc_agent.py 路径）没有等价的 format-retry；volc 偶发不守
   协议时 NPC 直接丢回合。修法：给 NPC 代理补一层与 MC 相同的格式重试（harness 层）。
2. **重复 identical 拒绝（F5 复发，轻度）**：3 例 ≥3 次——陈默 move 学生会办公室 ×3
   （直达路线不存在）、唐小岚 read 值班簿/审计包 ×3-4（文档不在手边）。repetition
   monitor 的 notice 未拦住跨回合 identical 拒绝。修法：repetition 监控纳入
   rejected-intention 指纹；更深一层：move 只支持直达路线是 16 次 move 拒绝的共同
   根因——agent 心智模型是"导航"，引擎物理是"邻接表"。建议：要么在 #knowledge 常识
   里给路线图（信念行），要么 move 支持多跳（引擎寻路，时长=最短路）。需用户裁决。
3. **ask_stranger 空问题（16 次拒绝）**：模型提交 `{"question": ""}`——schema 允许
   空串进来才被拒绝。修法：parse 层直接拒空（省一个来回）。
4. **none 回合 64 次**：MC 返回 None（协议级无决策）。当前不消耗 tick、靠心跳兜底，
   成本可接受；AGENT-INTERFACE 迁移（多工具链 + 发呆语义）落地后自然消解。
5. **冻结记账未入 trace（实现缺口）**：`stall_budget_ratio` 闸门已生效，但逐次冻结
   的 wall/sim 时长与责任角色没写进 trace（V4-ENGINE §6 承诺）。本跑无僵局所以无感，
   补上才能做 provider A/B 的拖累归因。
6. **舞台指示污染（10/376）**：speak text 以"（…）"开场——模型把动作写进台词。
   persona prompt 层加一句约束即可。

## 成本与速度

1024 回合 / 57 min wall ≈ 18 回合/min（并发 8，flash 档）。旧估算 435 回合/日是
5-min tick + 串行时代的数；1-min tick + 事件驱动下，日回合数 ~1000，但 wall 成本
反而更低（流水线 + 快模型）。4 小时预算可容纳 ~4 个种子日——正式弧（3 天）的
wall 成本预估 < 3 小时。

## 结论

作为引擎验证：**通过**。五条时序不变量在真实 provider 负载下无一处违反
（事件日志连续、2607 事件时间戳单调、无死锁、无冻结爆表），社交产出与剧情
纵深达到 V4-DESIGN §6 的通过线（每人 ≥2 次共处对话——远超；秘密跨配对流动——
台账线索经唐小岚/胡学姐多手传递）。作为故事实验：可用且高产出，上述 6 项
修复后即可支撑 3 天正式弧。
