# CONTEXT — 领域词汇表

本仓库是叙事模拟实验工作区。本文件是**共享词汇表**：给每个反复出现的领域词
下定义并指向其权威文档（SSOT）。词汇表本身不重述设计细节；冲突时以其权威
文档为准。新增领域词或架构决策时，优先在此登记并（重要者）补 `docs/adr/`。

## 项目与目标

- **叙事实验室（narrative lab）**：最终目标——一个可复现的实验环境，其中
  自主角色依据自身动机与合法获知的信息行动，世界按显式规则运行，任何轨迹
  都可检查、回放。不是成品游戏，不宣称人类级故事质量。
  （权威：`README.md`, `docs/1_PROBLEM.md`, `docs/2_GOAL.md`）
- **本实验（《契约失效时请勿喂猫》）**：一个 12 个模拟日的中文校园故事弧
  （2026-03-16 → 03-27）。权威：`契约失效时请勿喂猫/README.md`、
  `docs/0_ROADMAP.md`（S7 是它的现行落点）。
- **版本线 v1…v5**：依次迭代的实验版本。**v5 是当前活动线**（`docs/adr/0002-v5-becomes-the-main-line.md`）；
v4 及更早是参考/历史归档，其文档不作为现行要求。
- **T-A（目标结局）**：弧线的目标结局"成功但有代价"——档案室记录缺失案按
  正式渠道了结、台账差异被解释或立案、2013 真相由人说出、恋爱线有明确终局、
  草稿命运被决定。现行文档只以名字引用它（`docs/0_ROADMAP.md` 的 M7 行），
  唯一写下的正文定义在参考线的 `v4/docs/V4-STORY-MILESTONES.md` §1——那是参考，不是要求。

## 世界与知识

- **种子（seed / world pack）**：作者手工捏制的初始世界状态与排程。v5 的形状是一支
  故事一个 `stories/<story>/seed.yml`，严格模式由 `engine/seed.py` 校验（未登记的
  名字即红）。作者设计种子，世界运行它；作者不得静默修补运行中的一局。
- **世界 harness / 内核（harness / kernel）**：权威的世界实现。v5 的它是 `engine/`
  （十条原始项）+ `library/`（动词、物性与制度效果）+ `stories/<story>/`（种子与卡司）。
  角色只提交*意图*，引擎校验、排程、结算、提交为事件。引擎保持 story-neutral：不含
  剧情阶段、好感度、路线、主角特权。
- **客观世界 / 感知 / 信念 / 记忆 / 公开记录**：五层必须分离。事件只经 harness
  改变客观现实；角色发言是可观测的话语，不改变事实；听者自行决定信不信。
  权威：`docs/3_REQUIREMENT.md`（五层分离）。
- **KB / 记忆（knowledge base / memory）**：角色的持久记忆与知识。v5 里它是心智的
  记忆与知识（`docs/8_DETAIL.md` 的 P7）：记忆由感知投递累积，渲染文本与保真度
  由库规则决定；v4 参考线是 `runner.kb[actor].rows` 与轨迹里遗留的 `private_state.memories`。
- **MC / NPC / 匿名路人（extra）**：**v4 参考线**的三层演员制——MC 事件驱动+空闲心跳，
  NPC 被唤醒时拿导演简报，extra 销毁即零记忆。v5 不设这一层：每个在场的人各有一个
  心智，制度角色（摊主见的管理员、公交司机）与主要人物一样由种子声明、一样走感知投递
  （`docs/4_USECASE.md` 的两支故事）。
- **导演简报（director briefing）**：**v4 参考线**的机制——NPC 被唤醒时拿到一份私有
  上下文，只可铺垫、不许剧透。v5 没有它：引擎不替任何角色写剧情，谁知道什么只由感知
  投递决定。
- **System / 契约失效（the System / contract failure）**：故事里绑定主角的
  非常规系统，是本作标题的机制。**v4 参考线**写下它的规则与"有界客观澄清"边界
  （`v4/docs/V4-STORY-MILESTONES.md`，参考而非要求）；v5 要到 S7 才承载它，表述尚未定稿。

## 运行与证据

- **run / 轨迹（trajectory / artifact）**：一次 provider-backed 运行的完整记录。v5 的
  形状是 `stories/<story>/runs/agent-<时间>-<pid>-<标签>/` 四个文件：`transcript.md`
  故事视图、`context.md` 每回合的完整上下文与原始工具调用、`run.json` 与
  `events.jsonl` 可重放记录（权威：`docs/7_INTERFACE.md`）。每次调用必须
  产生唯一工件，绝不覆盖；没有 `context.md` 的一局回答不了"他当时知道什么"，不算证据。
  v4 参考线的形状是 `v4/runs/<runid>.json` 及其紧凑形态 `.jsonl.zst`。
- **provider**：模型上游（经本地 LiteLLM 代理）。瞬时故障常见，用带退避的重试；
  预算有限，失联要有界放行；重试预算耗尽的失败是终局，必须存成失败轨迹。
- **检查点（checkpoint）**：一局在中途停下来还能因果接着跑的完整快照。v4 参考线的实现是
  `v4/harness/resume_run.py` 从 `.checkpoint.json` 续跑；v5 的实现在里程碑 M4 的
  `resume` 工作包里，形状以该模块的文档字符串为准。
- **半天检查点（half-day checkpoint）**：弧线以半天为粒度推进（am=07:00–12:59,
  pm=13:00–22:00）。跑到边界 → 存档 → 过门 → 人工审阅 → 续跑或调种子重跑。v4 参考线
  按 12 天×2 用满这一粒度；v5 的 M4 把它降到一个半日的单支故事（S3《夜市》）。
- **剧情锚点 / 路线 / 纹理（anchor / route / flavor）**：**v4 参考线**的剧情里程碑判定
  模型——锚点=路线无关且必须达成的事实，路线=同一目标的多种合法走法（任一成立即通过），
  纹理=记录不裁决。定义写在 `v4/docs/V4-STORY-MILESTONES.md` §2.1（参考，不是要求）。v5 用故事阶梯的
  "必须能表达"清单与反作弊三检代替它（`docs/4_USECASE.md`、`docs/8_DETAIL.md` 的反作弊一节）。
- **预门（pre-run gate）**：大型 provider 运行前必须全绿的回归套件，红即阻断。v5 的预门是
  v5 套件 + `scripts/v5_lint.py --strict` + `scripts/anti_cheat.py --verbose`，外加每支故事
  自己的历史失败台账；v4 参考线的是它自己的台账 + 确定性终点门 + `scripts/seed_lint.py`。
  权威：`AGENTS.md` 与 `docs/9_IMPLEMENTATION.md`。
- **运行后分析（run analysis）**：每次 provider 运行后必须人工检查保存的轨迹，以具体行为与
  因果问题开头，不以计数或 clean/failed 标签下结论。权威：`AGENTS.md`。

## 流程与文档

- **Ticket / 工作记录**：变更与项目管理的**过程**记录。v5 不走票制：一个工作包的契约、
  证据与决定进它的提交信息和里程碑报告，`.scratch/` 只留给跑出来的缺陷
  （权威：`docs/0_ROADMAP.md`）。v4 参考线的票在 `.scratch/<feature>/`。
- **SSOT / fact doc**：当前事实的唯一权威文档。一份事实只有一个家；变更时
  原地重写，不留日期叙事、changelog、errata、"曾是 A 后改 B"、重复或冲突。
- **Milestone（项目里程碑）**：预定的用户同步与有意义验收点，是一个可独立判断的垂直切片。
  全部里程碑与工作包在 `docs/0_ROADMAP.md`。
- **Work Package（工作包）**：里程碑下一个内聚、可独立核对、可独立验收的产出单元。
- **Independent Review（独立复核）**：用新上下文、只看最终工件与证据（不看
  执行者对话、不看完成声明）的技术验收。自动执行模式下每个工作包默认需要。
