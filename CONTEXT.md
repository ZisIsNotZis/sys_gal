# CONTEXT — 领域词汇表

本仓库是叙事模拟实验工作区。本文件是**共享词汇表**：给每个反复出现的领域词
下定义并指向其权威文档（SSOT）。词汇表本身不重述设计细节；冲突时以其权威
文档为准。新增领域词或架构决策时，优先在此登记并（重要者）补 `docs/adr/`。

## 项目与目标

- **叙事实验室（narrative lab）**：最终目标——一个可复现的实验环境，其中
  自主角色依据自身动机与合法获知的信息行动，世界按显式规则运行，任何轨迹
  都可检查、回放。不是成品游戏，不宣称人类级故事质量。
  （权威：`README.md`, `docs/PRINCIPLE.md`）
- **本实验（《契约失效时请勿喂猫》）**：一个 12 个模拟日的中文校园故事弧
  （2026-03-16 → 03-27）。权威：`契约失效时请勿喂猫/README.md`,
  `契约失效时请勿喂猫/v4/docs/V4-STORY-MILESTONES.md`。
- **版本线 v1…v4**：依次迭代的实验版本。**只有 v4 是当前活动线**；v1/v2/v3
  是历史归档，其文档不作为现行要求。
- **T-A（目标结局）**：弧线的目标结局"成功但有代价"——档案室记录缺失案按
  正式渠道了结、台账差异被解释或立案、2013 真相由人说出、恋爱线有明确终局、
  草稿命运被决定。权威：`V4-STORY-MILESTONES.md` §1。

## 世界与知识

- **种子（seed / world pack）**：作者手工捏制的初始世界状态与排程。编译成
  与运行时同格式的初始检查点（`harness/compile_seed.py` → `v4-checkpoint-2`）。
  作者设计种子，世界运行它；作者不得静默修补运行中的一局。
- **世界 harness / 内核（harness / kernel）**：权威的世界实现。角色只提交
  *意图*，harness 校验、排程、结算、提交为事件。引擎保持 story-neutral：不含
  剧情阶段、好感度、路线、主角特权。
- **客观世界 / 感知 / 信念 / 记忆 / 公开记录**：五层必须分离。事件只经 harness
  改变客观现实；角色发言是可观测的话语，不改变事实；听者自行决定信不信。
  权威：`docs/PRINCIPLE.md` §3。
- **KB（知识库）**：角色的持久记忆行（`runner.kb[actor].rows`）。v4 的记忆事实
  存放在引擎侧 KB；轨迹里的 `private_state.memories` 是遗留字段
  （见 ticket 68）。权威：`V4-AGENT-INTERFACE.md` §6.1。
- **MC / NPC / 匿名路人（extra）**：三层演员制。MC 事件驱动+空闲心跳、完整
  记忆；NPC 事件驱动、被唤醒时拿导演简报；extra 对话期生命周期、销毁即零记忆。
  权威：`V4-CAST.md`。
- **导演简报（director briefing）**：NPC 唤醒时的私有上下文（知道世界事实与
  MC 公开行为，不知道 MC 私有状态；不许剧透"未来事件内容"，只可铺垫）。
- **System / 契约失效（the System / contract failure）**：故事里绑定 MC 的
  非常规系统，是本作标题的机制。其规则与"有界客观澄清"边界见
  `V4-STORY-MILESTONES.md`。

## 运行与证据

- **run / 轨迹（trajectory / artifact）**：一次 provider-backed 运行的完整记录
  （`v4/runs/<runid>.json` + `.checkpoint.json`），格式 `v3-trajectory-1`。每次
  调用必须产生唯一工件，绝不覆盖。
- **provider**：模型上游（经本地 LiteLLM 代理）。瞬时故障常见，用带退避的
  重试；预算是有限的，失联要有界放行。
- **检查点（checkpoint）**：每批写入的完整运行快照（世界+runner+私有状态+
  会话）。`harness.resume_run` 从检查点因果续跑（event id/version 连续）。
- **半天检查点（half-day checkpoint）**：弧线以半天为粒度推进（am=07:00–12:59,
  pm=13:00–22:00，12 天×2=24 个）。跑到边界 → 存档检查点 → 过门 → 人工审阅 →
  PASS 续跑 / FAIL 调种子并从上一个好检查点重跑。
- **剧情锚点 / 路线 / 纹理（anchor / route / flavor）**：剧情里程碑的判定模型。
  **锚点**=路线无关、必须达成的关键事实；**路线**=同一目标的多种合法走法，
  任一成立即算通过；**纹理**=路线点缀，记录不裁决。权威：
  `V4-STORY-MILESTONES.md` §2.1。
- **剧情里程碑 vs 项目里程碑**：**剧情里程碑**是半天/逐日的剧情锚点，由
  `scripts/check_milestones.py` 判定（`V4-STORY-MILESTONES.md`）。**项目里程碑**
  是面向用户同步与验收的交付垂直切片（`ROADMAP.md`）。两者不可混称。
- **预门（pre-run gate）**：大型 provider 运行前必须全绿的回归套件——历史失败
  台账 `harness/tests/test_historical_failures.py` + 确定性终点门 + 种子自洽门
  （`scripts/seed_lint.py`）。红即阻断。权威：`契约失效时请勿喂猫/AGENTS.md`。
- **运行后分析（run analysis）**：每次 provider 运行后必须人工检查保存的轨迹，
  以具体行为与因果问题开头，不以计数或 clean/failed 标签下结论。权威：
  `契约失效时请勿喂猫/AGENTS.md`。

## 流程与文档

- **Ticket / 工作记录**：变更与项目管理的**过程**记录（`.scratch/<feature>/`）。
  记录契约、证据、命令/结果、变更、修订引用、决定与理由；append 风格。
- **SSOT / fact doc**：当前事实的唯一权威文档。一份事实只有一个家；变更时
  原地重写，不留日期叙事、changelog、errata、"曾是 A 后改 B"、重复或冲突。
- **Milestone（项目里程碑）**：预定的用户同步与有意义验收点，是一个可独立
  判断的垂直切片。见 `ROADMAP.md`。
- **Work Package（工作包）**：里程碑下一个内聚、可独立核对、可独立验收的
  产出单元。见 `ROADMAP.md`。
- **Independent Review（独立复核）**：用新上下文、只看最终工件与证据（不看
  执行者对话、不看完成声明）的技术验收。自动执行模式下每个工作包默认需要。
