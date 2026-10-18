# 95 — v4 引擎第五轮（台账可答性 / 同行 / 事件作用域 / 文书补写 / 递物候选）

Status: fixed
Need-review: yes
Need-test-cases: yes

> 输入：`reports/m1-window4-07to17.md`、票 94 §1–§4/§7、票 91 §4、票 93、run
> `v4/runs/real-20261018T044104+0800-1847092-804831590.json`（窗口 4，07:00→17:00，1253 turns / 4008 events）。
> 范围：`v4/harness/`（`system.py` / `kernel.py` / `engine.py` / `action_schema.py` / `prompt.py` /
> `runner.py` / `world_loader.py` + 测试）与 `v4/docs/`。**`v4/world/` 一行未动**（种子代理并行改它，见 §4）。
> 原则照旧：不新增动作种类；只做既有原语的参数化/泛化或作用域修正。世界状态零新增字段（唯一新增的是
> 事件日志里的新 kind 与 payload 键，旧检查点与归档工件照常加载）。

## 0. 一句话

窗口 4 的五个缺陷都不是“模型不会”，而是世界缺可做的事或事实投错了人：台账要逐字猜问句、没有“带人一起走”、
排程事件无 target 就全场广播、文书上不能写、食堂大妈的递饭不在候选里。本轮把五处都落成既有原语的
参数化/作用域修正，并给每一处配了可复算的红→绿门。

## 1. 逐条处理

### 1.1 P0 · 台账事实表的可答性 + 拒绝可审计（E95）

**窗口证据**：陈默 5 次 `speak(to=["台账"])` 全部 `submitted`（票 91 的路由成立），但 `system_answer` 0 条；
`Ledger.query` 用 `facts.get(question.strip())` 逐字匹配，而他从没见过三条原始问句；5 次拒绝在世界日志里
0 痕迹，会话 13:32 压缩后连 tool 回执都不可查。

**机制**（`harness/system.py`，无新增动作）：

| 位置 | 改动 |
|---|---|
| `Ledger.__init__` | 事实条目支持两种写法：旧 `问句: 答案`，或 `问句: {answer: ..., keywords: [...]}`。若条目没声明 keywords，回落到条目问句本身。 |
| `Ledger._lookup` | 确定性匹配：问句做 `NFKC + kb.normalize`（全角/半角、空白、标点、`的`/`之`）；① 归一化后与某条问句逐字相等 → 直接命中；② 否则每个条目的每个匹配词计一分（词出现在问句里，或问句整句出现在词里——与 KB 唤起同一条双向子串规则）；③ 唯一最高分且 >0 → 命中；并列或零分 → “不知道”。**不调用模型**。 |
| `Ledger.query` | 命中仍只发 `system_answer` / 计额度 / 记 `last_answer_event_id`（票 93 的结案时机不变）。**每次对话（命中/拒绝）都提交一条只给提问者的 `system_dialogue` 私有事件**：`{system_name, case, question, matched, outcome, answer_event_id?}`，`outcome ∈ answered/unknown/tie/limit/closed/malformed`；命中才带 `answer_event_id`（缺就是缺，不拿空值顶）；仍**不产生公开 `speech`**。 |
| `prompt._event_sentence` | 显式 `system_dialogue` → 不渲染一行：审计不是角色“听见”的一句话 |
| `runner` | 旧驱动的 `system_query` intent 在拒绝路径上也会把审计事件记进该回合 `event_ids`（否则 `turn_system_ids <= recorded_ids` 失真）；`_result_message` 的 `system_*` 口信排除审计事件 |
| `world_loader` | 两处：① strip 循环保留 mapping 形状（`{answer: strip_refs(...), keywords: [strip_refs(...)]}`）—— 对 dict 直接 `strip_refs` 会把整条事实 stringify 成 Python 字典字面量，keywords 能力在真种子上完全不生效，且台账会把那串字面量当作答案投给角色；② 加载时校验形状（answer 非空、keywords 是字符串列表）——写错形状 = 永远答不上，所以大声失败 |

> 收尾追加（另一位代理实测）：种子代理交付 `keywords` 后，`load_world_pack` 的 strip 循环仍把 mapping
> 值当字符串处理（`strip_refs(dict)` = `str(dict)`），于是 `pack.system["facts"][...]` 是
> `"{'answer': ..., 'keywords': [...]}"`，`Ledger.fact_keywords` 全空，答案会把字典字面量投给角色。
> 已在同一循环里保留形状（并对 keywords 的每一项 strip），并由 `test_world_pack.LedgerFactsSeedTests`
> 与真种子冒烟两支钉住；真正生效的证据是 `LedgerFactMatchingGates.test_the_real_seed_answers_five_natural_questions_with_plain_text`。

**给种子作者的写法**（`v4/world/manifest.yml` 的 `system.facts:`）：

```yaml
system:
  facts:
    2013年邻里撤离通知书的责任人是谁？:
      answer: 当年在许可证上签名的那个人
      keywords: [邻里撤离通知书, 撤离通知书, 责任人, 谁签的字]
    当前记录的期限是什么？:
      answer: 学生会审计核对，2026-03-16T16:00:00+08:00
      keywords: [期限, 最迟什么时候]
    红色哨子在哪里？: 老家属院的地下室   # 旧写法仍可读：只按原问句（归一化后）命中
```

注意两条：① 关键词要能**区分**条目——两个条目共享一个词时，泛问会按设计并列→“不知道”；
② 07:00 那种“一句里同时问是什么/责任人/期限”的句子必然并列（它不是 bug）——种子若要它能答，得让
三个条款各有唯一词，或（更贴近故事）让角色分三次问。

**红→绿**：`LedgerFactMatchingGates`（6 支）——关键词命中窗口 4 09:10 原句、零分“不知道”、
并列（07:00 原句）“不知道”、每次对话恰一条审计且只给提问者且带答案事件 id、无 keywords 的旧条目逐字问仍命中、
**真种子冒烟**（5 句自然问法各自唯一命中、3 句无关问法 `unknown`、`system_answer` 的 answer 是纯文本而不是
`{'answer': ...}`）；另有 `test_world_pack.LedgerFactsSeedTests` 钉种子的 facts 形状。
把 `_lookup` 改回 `self.facts.get(question.strip())` 并让 `_audit` 不提交事件 → 4/5 红（第 5 支是旧写法基线守卫，按设计保持绿）。

### 1.2 P0 · `move` 支持同行（扶/陪）（E96）

**窗口证据**：305 相关发言 219 条 / 17 个角色 / 10:00–16:51；“我不能/没法 + 扶/搀/陪/带”165 条 / 16 个角色；
305 不是地点、也没有“带某人一起走”的动作，17 个角色的拒绝全都是对的。

**机制**（`harness/kernel.py`，无新增动作）：

| 位置 | 改动 |
|---|---|
| `action_schema` | `move` 增加可选 `with: [名字…]`（与 target 同一张 schema；cache 安全的静态声明）。 |
| `World._canonicalize_companions` | `with` 里的名字与 `speak`/`text`/`give` 同一套 T4 解析（昵称唯一命中即规范化；未知/歧义给出“现在在这里的人”）。 |
| `World._raw_duration` 的 move 分支 | 结构化校验：不能写自己；每人必须在发起者所在地点；没有待处理的 continue-or-abandon；**当前动作 `uninterruptable` → 整次 move 拒绝**（说明是谁、在做什么、完成时刻）；自己正在走另一段 `move` → 拒绝（“等他到，或让他自己跟来”）。拒绝发生在 `action_started` 之前，世界零变化。 |
| `World.submit` | 发起者与每位被携带者在原地各提交一条 `leave`（payload 带 `escorted_by`）；hop 任务携带 `with`。 |
| `World._move_hop` | 按发起者的 path 逐跳推进：每位被携带者产生自己的 `enter`（末跳）与 `enter`+`leave`（中间跳），与发起者同一时刻、各占一个连续 world version。`_follows_escort` 在每一跳复核：当前动作不可打断、进入 pending、或自己开始走另一段 move → 不再跟随（“中途拒绝”）；被打断的普通动作（例如正在说话）不脱离。 |
| `World._complete` | 只动发起者（被携带者已由自己的 `enter` 到达）；**不给被携带者伪造动作事件**——走路是发起者的事。 |
| `replay` | 无需改动：`enter` 已定义位置，共同移动的每条 enter 都在日志里。 |

**语义（也写进了 `docs/V4-AGENT-INTERFACE.md` §2 move 行与 `docs/V4-ENGINE.md` §7.8）**：被携带者
**仍保有感知与自主**——可以边走边说、可以自己走开；引擎只移动位置，**不替其行动**。发起者被打断时，
被携带者停在最后一跳；`continue_action` 续跑时按 remaining path 继续带仍在原地的同伴。

**给种子作者的写法**：

```json
{"name": "move", "arguments": {"target": "教学楼", "with": ["林瑶室友"]}}
```

（先确认两人同处一地；被携带者若正被不可打断的动作锁着，这次 move 会被整次拒绝并说明原因——种子不需要
为“扶”再写新动作或新文案。）

**红→绿**：`EscortMoveGates`（4 支）——两人同到目的地且事件序列逐条正确（leave A / leave B / enter A /
leave A / enter B / leave B / enter A / enter B）、不可打断时整次拒绝且零事件、replay 后两人位置一致、
不同处一地时拒绝。变异（hop 不移动同伴 + 去掉不可打断拒绝）→ 3/4 红（第 4 支是“不同处一地”守卫）。

### 1.3 P0 · `world_event` 的可选地点作用域（E97）

**窗口证据**：26 条 `world_event` 中无 target 的全部广播 10–14 人；陈默整天在档案室，却在 16:02 引用了
16:05 才定向告诉他的原话，16:22 又“刚获知”办公室长桌上的审计包；唐小岚在咖啡馆也知道 16:20/16:45 两件事。

**机制**（`harness/kernel.py` `_visibility`）：`world_event` payload 支持可选 `location`——
有 `location` 时可见集 = 当时在该地点的人 +（若有）`target`；只有 `target` 时不变；两者都没有仍是既有
全局广播（校园公告、铃声、天气）。`world_loader` 在加载时校验 `location` 是已知地点（点名不存在的地点 =
没人看得见，所以大声失败）。

**给种子作者的写法**：

```yaml
- event: audit_pack_review
  time: '2026-03-16T16:20:00+08:00'
  location: 学生会办公室          # 只有当时在那里的人（+ target）看得见
  target: 班长                   # 要叫醒某个 NPC 时必须写它（location 只决定谁能感知）
  notice: '长桌上摊开了审计包和一张还空着的面核记录。'
```

**红→绿**：`WorldEventScopeGates`（3 支）——同一事件有/无 `location` 的可见集合不同、`location+target`
同时覆盖二者、replay 后可见集与正文一致。变异（去掉 location 分支）→ 3/3 红。

### 1.4 P1 · 在既有文书上补写/签名（E98）

**窗口证据**：`面核记录` 正文要求“谁到场核对，谁就往自己那一栏里填”；工具面没有 annotate
（`document_annotated` 事件与 `annotations` 存储早已存在却无入口），班长只能另贴字条，面核记录 0 人签。

**机制**（`harness/kernel.py` + `action_schema`，无新增动作）：

| 位置 | 改动 |
|---|---|
| `action_schema` | `leave_note` 增加可选 `on: <文书 id>`；`on` 与 `persist` 互斥（校验期拒绝）。 |
| `World._item_duration` | 文书必须存在于 `document_defs` 且当前可读（同地或手上）；否则拒绝并列出“手边能写的”，并提示“要留新字条就别写 on”。 |
| `World._complete` | 把文字追加进该文书的 `annotations`（`{text, by, time}`）——**只追加、不覆盖**。 |
| `World._commit_interaction` | `leave_note` + `on` 改发既有的 `document_annotated`（`{document, location, annotation}`），不再是 `note_left`。 |
| `World._public` | 批注正文与文书正文同一条隐私线：对非作者剥掉 `annotation`——同地点的人只看见“谁在上面写了字”，内容要自己 `read`；`replay` 用既有 `document_annotated` 分支重建。 |
| `prompt._event_sentence` | 恢复 `document_annotated` 的公开行模板（“{actor} 在 {document} 上留下批注”；此前是一段不可达的死代码）。 |
| `engine._leave_note_yield` | 回执说明“已写入《X》作为一条批注、不覆盖别人写的、同地的人只看见你写了字、要读全文用 read X”。 |
| `engine.VERB_GAP_TEACHING` 的签字/批注条 | 旧的“写不了”已不成立：改为指向 `leave_note on=<文书>`（`docs/V4-AGENT-INTERFACE.md` §2.2 的块仍与常量逐字一致，由看守测试钉住）。 |

**给种子作者的写法**：

```json
{"name": "leave_note",
 "arguments": {"text": "到场核对：材料三份，缺说明一页。", "on": "面核记录"}}
```

（文书必须在该角色所在地点或手上；`on` 只接受 `documents:`/可读 `items:` 的正式 id，不接受 `note-*` 持久便条。）

**红→绿**：`DocumentAnnotationGates`（4 支）——签名追加为批注且他人 `read` 能看到、第二个人追加不覆盖、
replay 重建、文书不在手边时拒绝且零事件。变异（去掉 `_complete` 追加与 `document_annotated` 转交）→ 3/4 红
（第 4 支是“不在场拒绝”守卫）。

### 1.5 P2 · `give` 的可发现性（E99）

**窗口证据**：食堂大妈全天 `give` 0 次；11:00 的“窗口要有人守”只兑现成一句招呼，两份饭都是自取
（午饭从 11:00 上台到 11:48 被取走）。引擎早已支持“就地取再递”（ticket 63），缺的只是可见性。

**机制**（`harness/kernel.py` `affordances`）：`give` 候选 = 背包 ∪ **当前地点可拿物品**（排除 `fixed_items`）；
拒绝回执的可行调用清单也含手边物品；`action_schema` 的 give 说明写明“就在你手边的东西可以直接递”。

**给种子作者**：不需要新写法——只要“饭/东西”是当前地点的可拿物品、递东西的人在场，`give <item> <to>`
就会出现在候选里。食堂如果要演“守窗口”，让大妈与午饭同处一地即可。

**红→绿**：`GiveAtHandAffordanceGates`（1 支）——当前地点的午饭出现在 `give` 候选里、固定陈设不会、直接
`give` 后午饭到对方背包且离开地点。变异（候选只取背包）→ 1/1 红。

## 2. 红→绿证据（变异对照，全部可复算）

变异方法：把 `harness/`、`world/`、`scripts/` 复制到 `/tmp/mut95*`，按每节所述去掉本轮改动后跑同一批点类。

| 组 | 变异 | 读数 |
|---|---|---|
| E95 | `_lookup` 改回逐字 `facts.get`；`_audit` 不提交事件 | 5 红 / 1 绿（旧写法基线守卫，按设计绿） |
| E95（加载） | strip 循环改回 `strip_refs(value)` | 2 红（`LedgerFactsSeedTests` + 真种子冒烟） |
| E96 | hop 不移动被携带者；删掉不可打断拒绝 | 3 红 / 1 绿（不同处一地守卫） |
| E97 | `_visibility` 去掉 location 分支 | 3 红 |
| E98 | `_complete` 不追加批注；`document_annotated` 不转交 | 3 红 / 1 绿（不在场拒绝守卫） |
| E99 | `give` 候选只取背包 | 1 红 |

确定性复算（不调 provider，只跑内核/引擎桩）见 §5。

## 3. 回归读数（收尾实测，`cd 契约失效时请勿喂猫/v4`）

```text
python3 -m unittest discover -s harness/tests -p 'test_*.py'
  660 支（基线 641；本票 +19：LedgerFactMatchingGates 6 + EscortMoveGates 4
        + WorldEventScopeGates 3 + DocumentAnnotationGates 4 + GiveAtHandAffordanceGates 1
        + test_world_pack.LedgerFactsSeedTests 1）
  全量共跑 3 次（658×2、660×1）：2 次 `OK (skipped=1)`；1 次只红 1 支 = 已登记的半硬币
  `test_silent_abandonment_auto_continues_pending_action`（`test_engine.py:125`，非 v4
  `Scripted` agent、`system=None`，不经过本票任何一行；单跑 10/10 绿）
python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
  206 支（基线 188，+18）；单跑 3 次：2 次各红 1 支、1 次全绿，红的都是票 73 §6.1 登记的 extra 时序族
  `test_extra_turns_are_recorded_and_conversational`（捕获到的症状：
  `(first_answer.time - arrived[0].time) = 120s > 60s`，同一测试的 tick 断言；
  单跑 12 次里 2 红 10 绿，与本票代码路径无关）
python3 -m unittest discover -s harness/tests -p 'test_world_pack.py'
  76 支 OK（含 LedgerFactsSeedTests）
python3 -m unittest discover -s harness/tests -p 'test_kernel.py'
  75 支 OK
python3 -m unittest harness.tests.test_historical_failures.PersistentNoteGates
  6 支 OK（含 runs/archive-20261016-attempt1/d1-am.json 的加载）
python3 scripts/seed_lint.py
  seed lint OK（findings 0 / contract 0），warning 8 条——与票 91/92/93 同数同族
```

- **向后兼容**：世界状态零新增字段；新 kind（`system_dialogue`）与 payload 键（`with`/`on`/`escorted_by`/
  `annotation`/`location`）都只是日志/动作参数，旧检查点缺这些键照常加载；`runs/archive-20261016-attempt1/d1-am.json`
  仍由 `PersistentNoteGates` 看守并绿。
- **间歇族（如实记录）**：本票全量 3 次 —— 2 次 `OK (skipped=1)`，1 次只红已登记的半硬币
  `test_silent_abandonment_auto_continues_pending_action`（`test_engine.py:125`，非 v4
  `Scripted` agent、`system=None`，不经过本票任何一行；单跑 10/10 绿）；
  `test_extra_turns_are_recorded_and_conversational`（票 73 §6.1 的 extra 时序族：
  `(first_answer.time - arrived[0].time) = 120s > 60s`；单跑 12 次 2 红 10 绿）同样不在
  本票代码路径上。两者都不能当作“套件级全绿稳定”。
- **按新事实校准的既有测试（每条都核对过量尺）**：
  - `test_kernel.test_invalid_ledger_query_does_not_consume_quota`：夹具改为中文互不包含的问句——
    匹配不再是逐字的，但它钉的仍是“表外问题不吞额度”。
  - `test_kernel.test_a_correct_answer_does_not_settle_the_case`：命中后最后一条事件现在是
    `system_dialogue` 审计；“没有报酬”改看事件种类，并新增审计 payload 断言。
  - `test_runner.test_system_reward_feedback_reaches_bound_character_in_natural_language`：`system_*`
    序列里每次查询都多一条审计（额度用尽后的拒绝也留痕）；改为断言“除审计外只有 accepted+answer，
    审计恰一条 matched=True 且只投给陈默”。
  - `LedgerDialogueGates.test_the_query_limit_silences_the_ledger_without_closing_the_case`：闭口时
    “什么都没有发生”改为“只有一条 `system_dialogue{outcome: limit}`，没有答案”。
  - `Ticket48NarratedFactGates.test_verb_gap_teaching_names_the_real_action`：签字/批注的指向从
    `update_memory` 改为 `leave_note`（§2.2 的完整文案与常量仍逐字一致）。

## 4. 仍然开着 / 移交

1. **种子侧（`v4/world/`，本票禁改）**：三条事实已由并行种子代理补上 `keywords`（E95 的真种子冒烟与
   `LedgerFactsSeedTests` 已验）；16:00/16:20/16:45 三条排程已写好 `location:`（票 96）——注释里“引擎侧
   待落地”的括注在本票落地后可以删掉；16:20 的“审计包在长桌上”与 11:50 已被 `give` 给辅导员的客观状态
   仍矛盾（窗口 4 R5，种子票）；食堂若要“守窗口”，让大妈与饭同处一地（§1.5）。
2. **`world_event location` 不唤醒在场 NPC**：唤醒仍只认 `target`（`engine._after_advance`）。这是刻意的分工
   ——`location` 决定“谁能感知”，`target` 决定“谁必须醒来反应”。种子若要某个 NPC 当场动作，就写 `target`；
   若下一窗口证明这不够，再开票把 location 加进 NPC 唤醒，而不是本轮先猜。
3. **同行没有独立的“拒绝”事件**：被携带者的拒绝就是结构化拒绝（submit 前，零事件）或途中脱离（不再跟随，
   没有 `escort_refused` 之类的新 kind）。不新增事件种类是本轮原则；复核可用 `leave`/`enter` 序列判断谁跟到了。
4. **发起者被中断后的续跑未单独测试**：`_resume` 会带 remaining path 与 `with` 继续（代码路径已处理），
   但“多跳中途被打断 → continue_action → 同伴继续跟随”没有专门一支部；若下一窗口出现，按 E96 的同一量尺补测。
5. **`on` 只写 `document_defs`**：持久便条（`note-*`）不是有“栏”的文书，不能用 `on` 批注；要对便条追加内容
   目前只能再留一张/`trash` 旧的。这是现行语义，不扩张。
6. **关键词匹配是字符包含**：不做同义/语义匹配（本轮明确禁止模型判定）。种子写区分性关键词即可；
   泛问并列时“不知道”是设计行为。

## 5. 复算命令

```text
cd 契约失效时请勿喂猫/v4
python3 -m unittest harness.tests.test_historical_failures.LedgerFactMatchingGates
python3 -m unittest harness.tests.test_world_pack.LedgerFactsSeedTests
python3 -m unittest harness.tests.test_historical_failures.EscortMoveGates
python3 -m unittest harness.tests.test_historical_failures.WorldEventScopeGates
python3 -m unittest harness.tests.test_historical_failures.DocumentAnnotationGates
python3 -m unittest harness.tests.test_historical_failures.GiveAtHandAffordanceGates
python3 -m unittest harness.tests.test_historical_failures.Ticket48NarratedFactGates
python3 -m unittest discover -s harness/tests -p 'test_*.py'
python3 -m unittest harness.tests.test_historical_failures.PersistentNoteGates
python3 scripts/seed_lint.py
```

变异对照（每组一个副本，改完只跑对应点类）：

```text
# E95
rm -rf /tmp/mut95 && mkdir -p /tmp/mut95 && cp -r harness world scripts /tmp/mut95/
# system.py: `answer, outcome = self.facts.get(question.strip()), "answered"`；`_audit` 返回 None
cd /tmp/mut95 && python3 -m unittest harness.tests.test_historical_failures.LedgerFactMatchingGates
  → Ran 6 … FAILED (failures=4, errors=1)

# E95（加载形状）
rm -rf /tmp/mut95f && mkdir -p /tmp/mut95f && cp -r harness world scripts /tmp/mut95f/
# world_loader.py：strip 循环改回 `manifest["system"]["facts"][key] = strip_refs(value)`
cd /tmp/mut95f && python3 -m unittest harness.tests.test_world_pack.LedgerFactsSeedTests \
  harness.tests.test_historical_failures.LedgerFactMatchingGates.test_the_real_seed_answers_five_natural_questions_with_plain_text
  → Ran 2 … FAILED (failures=2)

# E96
rm -rf /tmp/mut95b && mkdir -p /tmp/mut95b && cp -r harness world scripts /tmp/mut95b/
# kernel.py: `_move_hop` 的同伴循环改为空；删除不可打断拒绝
cd /tmp/mut95b && python3 -m unittest harness.tests.test_historical_failures.EscortMoveGates
  → Ran 4 … FAILED (failures=3)

# E97 / E98 / E99 同理，见 §2 表。
```
