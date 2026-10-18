# 91 — v4 引擎第四轮（台账对话通道 / 连续空回合回执 / 钉住的文书）

Status: fixed
Need-review: yes
Need-test-cases: yes

> 输入：票 90 §1/§2/§8、`reports/m1-window3-07to12.md`、票 86 §5、run
> `v4/runs/real-20261018T033115+0800-1755244-201779124.json`（窗口 3，07:00→12:00，406 turns / 1315 events）。
> 范围：`v4/harness/`（`system.py` / `engine.py` / `natural_agent.py` / `prompt.py` / `action_schema.py` / `world_loader.py`）
> + `v4/docs/V4-AGENT-INTERFACE.md`、`v4/docs/V4-ENGINE.md` + 测试。**`v4/world/` 一行未动**（种子代理并行改它，收尾移交见 §6）。
> 三条都按"文档/代码漂移修复"处理，没有新增动作种类、没有新增世界状态字段（检查点只多一个可缺省键，见 §5）。

## 1. 逐条处理

### 1.1 P0 · 台账在对话里可达（E92）

**调用写法（本票的对外契约）**：受约束角色对台账说话就是一次 `speak`，把台账的名字写进 `to`：

```json
{"name": "speak",
 "arguments": {"text": "红色哨子在哪里？", "volume": "normal", "to": ["台账"], "wait_response": false}}
```

`text` 就是你要说/要问的那一句；台账只认自己案卷里逐字记着的条目，所以问法要贴着条目。
名字只认种子声明的 `system.name`（本种子 = `台账`，归一化后比较：空白/标点/`的`/`之` 不影响）。
它不是工具：`ask` 与 `system_query` 都不存在（`ask` 在 T6 已并入 `speak`，票 90 §1 引用的 `Ledger.affordances`
注释里的 `ask` 说法一并改掉）。未受约束的角色把台账写进 `to` 时**引擎不做任何路由**——内核照旧判
"未知收件人"，台账不应声，也不把自己的存在解释给别人。

**实现**（三处，都是既有机制的延伸）：

| 位置 | 改动 |
|---|---|
| `harness/system.py` | 新增 `Ledger.answers_to(actor)`（只有受约束角色为真）、`Ledger.addressable(actor, name)`（`answers_to` + 名字归一化等于 `system.name`）、`Ledger.converse(world, actor, line)`（把这句话交给既有 `query`，四种拒绝各翻一句台词：`unknown`→"不知道"、`closed`/`limit`→"闭口"、`malformed`→"一句话问一件事"）。`query` 的异常文本与语义**一字未改**，只多带 `context["ledger"]` 这个机器可读原因（英文措辞不外泄给人）。答案本身仍走既有 `system_answer` 私有事件，**不进 tool 结果**——那是已实现、已测试、只为受约束角色可见的通道。 |
| `harness/engine.py` `_execute_chain` 的 speak 分支 | 收件人里只要有台账的名字且说话人是受约束角色：不 `world.submit`、不产生 `speech` 事件、不触发"说完等回应"；走 `Ledger.converse`，回执按对话语气返回。"一拍时间"由回合末尾那条发呆 `wait` 归因（`world_actions` 不计数，语义与说话一拍一致）。忙态照旧拒绝并写明完成时刻。若同一句 `to` 里还点了别人，回执明说"这些话只对台账说了，同场的人没有听到"并给出重发写法——**不静默丢收件人**。 |
| 发现性（三处提示层措辞） | ① `prompt._system_sentence` 的 `system_case_accepted` 叙述加一句"要问它，就当面对着「台账」说话"；② `action_schema` 的 `speak` 说明加一句"`to` 也可以写世界内一个会回话的对话者的名字"；③ 受约束角色把台账叫错名字时（09:02 原样：`to=["2013年台风台账"]`，那是档案室里那份纸的名字），`AsyncEngine._system_address_hint` 在拒绝里给出真实写法 `to=["台账"]`。三处都不改语义。 |

**约束照旧**：只答事实表内条目（答不了说"不知道"，且**不吞查询额度**）；查询次数硬上限（用尽即闭口）；
案件的答案不与"2013 真相"重叠——事实表三条是"是什么/责任人是谁/期限"，条目本身不含真凶信息（种子未改）。

**为什么选 `speak` 而不是补 `ask`**：票 90 §1 给了两条路。补 `ask` 要新增动作种类（`World.ACTIONS` + schema +
`Ledger.affordances` + 提示层四处），而 `speak` 已经是"唯一带寻址的说话工具"（T6 裁决），台账本来就是
"世界内对话者"——缺的只是一行收件人解析。选了改动面小、且与文档 §5 原话一致的那条。

### 1.2 P1 · 陈默 08:42–09:04 连空回合：诊断 + 修法（E93）

**结论：模型零工具调用，不是引擎重试、也不是时间凭空消失。** 证据（同一工件）：

```text
agent_turns（陈默）08:40–08:58
  08:40 submitted recall        ver 482→486  content_private 0
  08:42 none      err None      ver 506→523  content_private 102
  08:44 submitted update_memory ver 533→549  08:46 submitted flashback ver 561→577
  08:48 none ver 582→606 (113)  08:50 none 612→628 (142)  08:52 none 637→657 (86)
  08:54 none 658→686 (90)       08:56 none 696→719 (92)   08:58 none 729→745 (122)
system_turns 里这 9 个回合都是 empty_turn{role: mc, reason: prose_only,
  private_chars: 81..142}（全窗口 mc 10 条，9 条扎在这里）
system_turns 全表：empty_turn 20 / extra_removed 5 / engine_stop_diagnostic 1
  —— 没有任何 decision_abandoned、hung_decision_abandoned、actor_task_crash、
     inflight_released、provider 重试耗尽记录
world_events（陈默 08:40–09:06）：action_started(wait) ×13、action_completed(wait) ×13、
  外加一次 read 完成 + 它自己的 document_read
```

即：每个空回合里模型确实产出了 81–142 字的正文（其中 08:48–08:58 的五段是把台账三条款**答完**的成稿），
只是没有发出任何工具调用；引擎按 §4 给每一拍提交了一条 60 秒发呆 `wait`，时钟每拍前进约两分钟
（一分钟是那条 wait，一分钟是决策在飞期间允许的时钟推进）。所以"白烧 20 分钟"是
**零动作的模型回合 × 已成文的发呆一拍**，而不是引擎空转或重试。

**修法（两端都做，都不动时钟）**：

- (a) **记录更有信息量**：`AsyncEngine._empty_streak[actor]` 记连续空回合数，`empty_turn` 的 payload 多一个
  `streak`（有工具调用的回合清零）。它进检查点（键缺失 = 0，旧检查点照常加载）。**不代填动作、不惩罚角色**：
  发呆一拍仍是 §4 的既定语义，而且它本来就有明确的时间归属（一条显式 `wait` 事件），这里不改时钟语义。
- (b) **补提示层反馈**：零调用的回合把 `natural_agent.NO_ACTION_NOTE` 追加成一条 user 消息
  （"上一回合你只写了想法，没有调用任何工具——世界没有因为那段想法改变，时间照常过去了。要把话说出口用
  speak/text，要做事用相应的工具；确实只想待在原地，就用 wait 明确占住这段时间。"），连续第 2 拍起附
  "（这已经是连续第 N 个这样的回合。）"。追加位置与 ticket 56/64 的两条自纠相同（在 tool 结果之后，保证
  assistant 的 `tool_calls` 与其 `role:tool` 配对不断），并且**与它们互斥**：正文像在对话时用 64 的自纠，
  否则用这一条，一拍只发一条、不叠加。

**为什么不是 ticket 64 已经够了**：64 只在正文含引号对白或第二人称时发。陈默写的是一份"已答好"的答案
（"这是**邻里撤离与互助事项的确认通知书**……"），既没有引号也没有"你"，所以九拍里一次提醒都没收到——
这正是本票要补的那一类"只有想法、零调用"。

### 1.3 P2 · `take` 候选里的文书（报 90 §8 / 票 86 §5）—— 裁定

**结论：文书是否可被 `take` 是种子的事实，不是引擎猜的。** 文书默认是一张纸，可拿（`场地申请表` 就是
让林瑶 11:21 自取的那张）；一块钉在门边的公告栏、一张贴在板上的通知是**固定陈设**，由种子写
`takeable: false` + `fixed_reason`，与 `items:` 早已有的那套同一机制。引擎侧只做一处泛化：
`world_loader` 的 `fixed_items` 现在也从 `documents:` 行派生，`_validate_descriptions` 对文书同样校验这两个键的
类型。于是这类实体照样在场、照样可 `read`，但 `take`/`give` 就地分支/`trash` 结构化拒绝，拒绝理由用种子
那句 `fixed_reason`，"这里能拿的"清单里不再出现它。**缺省仍可拿**（不悄悄改语义）。
引擎不去按名字猜"哪个听起来像板"——那是种子的判断。

**移交种子（`v4/world/`，本票未动）**：`documents:` 里的 `公告栏`、`教学楼公告栏`、`女生宿舍公告栏` 需要补
`takeable: false` + 一句 `fixed_reason`（例如"它钉在门边的墙上，只能就地看着、读上面贴的纸"），
另外 10:00/15:00 才贴出的通知类文书若也要钉住，同一写法。

### 1.4 文档同步

- `docs/V4-AGENT-INTERFACE.md`：§5 台账一条重写（"对话通道唯一：`speak` 点名它"，写明 `to=[台账]`、只答事实表、
  答不了说不知道、用尽即闭口、`ask`/`system_query` 已作废、未受约束者不被应声、叫错名字拿回真实写法、
  实现落点与看守测试）；§2 工具表的 `speak` 行补"世界内的对话者同样在 `to` 里点名"；§4 的
  "一回合既无文字输出也无世界动作 → 发呆 1 tick"补上 E93 的记录与回执语义；§3 的 `take/place` 行补
  "能不能拿起是种子的事实"（`documents:` 也可写 `takeable: false`）。
- `docs/V4-ENGINE.md`：新增 §7.6（E92 / E93 / 钉住的文书三条的机制、诊断与回归清单），并把 §5 的
  "`items:` 有两种"一段补上"`documents:` 同样适用"。

## 2. 红→绿证据

新增 14 支（618 → 632），全部落在 `harness/tests/test_historical_failures.py` 与 `test_world_pack.py`，
台账条目 E92/E93 已写进该文件的覆盖台账。

| 支 | 断言 | 变异对照（去掉本轮改动后） |
|---|---|---|
| `LedgerDialogueGates.test_the_bound_character_gets_a_fact_table_answer_by_naming_the_ledger` | ① 受约束角色点名台账 → 恰好一条 `system_answer`，`answer` = 种子里 `红色哨子在哪里？` 的条目，`visible_to == {陈默}`；**没有任何 `speech` 事件**（话没进公开场）；`queries_used == 1`；tool 结果 ok 且提到台账；下一回合渲染出的消息里真有那条答案，林瑶的知觉里一条 `system_*` 都没有 | 红（`0 != 1`：没有任何 system_answer） |
| `…test_a_question_outside_the_fact_table_gets_the_ledger_s_dont_know` | ② 事实表外的问题 → 没有 `system_answer`、`queries_used == 0`（不吞额度）、回执含"不知道"、世界没有 `speech` | 红 |
| `…test_a_used_up_ledger_stops_answering_instead_of_answering_again` | ③ 答过一条之后再问 → 仍然只有 1 条 `system_answer`，第二次回执含"闭口" | 红 |
| `…test_the_query_limit_itself_closes_the_ledger` | ③' `query_limit: 0` 的台账 → `converse` 返回 `DIALOGUE_REPLIES["limit"]` 且**零事件** | 红（方法不存在） |
| `…test_an_unbound_character_naming_the_ledger_is_not_answered_by_it` | ④ 林瑶点名台账 → 没有 `system_answer`、`queries_used == 0`、回执是未知收件人拒绝、且**不含**台账通道的解释 | 绿（负向守卫，本就该绿：它钉的是"不许应答"） |
| `…test_a_misnamed_attempt_gets_the_ledger_s_real_address_back` | 09:02 原样（`to=["2013年台风台账"]`）→ 拒绝照旧，但回执给出 `to=["台账"]` 与"世界内的对话者" | 红 |
| `…test_a_line_naming_the_ledger_and_others_is_not_dropped_silently` | 同一句 `to=["台账","林瑶"]` → 仍只有 1 条 `system_answer`、没有 `speech`，回执明说"同场的人没有听到"并点名林瑶（不静默丢收件人） | 红 |
| `…test_a_busy_actor_cannot_address_the_ledger_mid_action` | 忙态下发这句话 → 台账不应答（0 条 `system_answer`），回执是 `not executed … 下一回合`（一回合一个耗时动作） | 红 |
| `ConsecutiveEmptyTurnGates.test_each_empty_turn_is_recorded_as_a_streak_and_owns_one_wait` | 三拍连空 → `empty_turn` 的 `streak` = 1/2/3、`reason == prose_only`、`private_chars > 0`；这三拍里陈默只有 `wait`（`duration_seconds == TICK_SECONDS`），**没有一条 `speech`、没有别的动作** | 红（`streak` 键不存在） |
| `…test_the_next_input_says_the_thought_changed_nothing` | 每拍一条反馈，带连续次数 `no_action:1/2/3` | 红（`[] != [...]`） |
| `…test_a_turn_with_a_call_resets_the_streak_and_gets_no_notice` | 空 → 有调用 → 空：streak = 1/1，反馈也只有两条 `no_action:1`，且没被 ticket 64 的自纠抢走 | 红（streak 键不存在） |
| `NoActionNoticeTextGates.test_the_note_states_the_consequence_and_the_two_ways_out` | 反馈文本本身说清"没有调用任何工具/时间照常过去/speak/wait"，连续第 3 拍带次数、第 1 拍不带 | 红（文本不存在） |
| `test_world_pack.PlaceBoundDocumentTests.test_a_declared_place_bound_document_is_not_a_take_candidate` | 文书写 `takeable: false` → 不在 `take` 候选中，`take` 拒绝理由用种子的 `fixed_reason`，拒绝后的 `takeable_here` 里没有它、`场地申请表` 仍在；板还在原处、没进背包 | 红（`'公告栏' unexpectedly found in ['公告栏','场地申请表']`） |
| `…test_an_undeclared_document_is_still_movable_paper` | 没写 `takeable` 的文书照旧可拿（缺省语义未改） | 绿（正向基线守卫） |

变异方法（可复算）：把 `harness/`、`world/` 复制到 `/tmp/mut`，去掉本轮 `engine.py`/`system.py`/`world_loader.py`
的改动后跑同一批点类 —— **14 支里 11 支转红（`failures=8, errors=3`），3 支仍绿**，而这 3 支按设计本来就该绿：
`test_an_unbound_character_naming_the_ledger_is_not_answered_by_it` 与
`test_an_undeclared_document_is_still_movable_paper` 是负向/缺省语义守卫，
`NoActionNoticeTextGates` 钉的是 `natural_agent` 里的文本常量（这一层没有参与变异）。

## 3. 回归读数（本票收尾实测）

```text
cd 契约失效时请勿喂猫/v4
python3 -m unittest discover -s harness/tests -p 'test_*.py'
  632 支（基线 618，+14 本票新增）；修复收尾后连跑 6 次：2 次全绿、4 次各红 1 支
  （最后一次：Ran 632 / OK (skipped=1)），红的两支见下"间歇族"（每支都单跑复核为绿）
python3 -m unittest harness.tests.test_historical_failures          # 183 支 — OK
python3 scripts/seed_lint.py
  seed lint OK: every named thing resolves to an entity or concept
  warning 8 条（与窗口 3 同族同数：6 条名字撞车 + 《2013年台风台账》known_to 空 + 通讯录不对称）
  ——本轮种子代理在飞时的两条红（`documents/课表.md` / `教学楼公告栏.md` 未打标引用）已由其修复，收尾读数为此
python3 -m unittest harness.tests.test_historical_failures.PersistentNoteGates   # 含旧检查点 / 归档 d1-am 加载
  Ran 6 tests — OK
```

- **向后兼容**：世界状态零新增字段（E92 只读 fact table、E93 只加诊断），检查点只多一个可缺省键
  `empty_streak`（缺失 = 空表）；`runs/archive-20261016-attempt1/d1-am.json` 仍由
  `PersistentNoteGates.test_the_archived_d1_am_checkpoint_still_loads` 看守并绿。
- **间歇族（如实记录，不宣称套件级全绿稳定）**：修复收尾后连跑 6 次全量 = 2 绿 4 红，每次只红 1 支，
  且只用两支身份（本机同时有并行种子代理在跑，负载偏高）；两支都**不走本票的代码路径**，单跑复核均绿
  （3/3、以及另一支 10 次 5 红 5 绿见下）：
  1. `HistoricalFailureGates.test_extra_turns_are_recorded_and_conversational`（票 73 §6.1 登记过的那一支；
     extra 走 `_extra_turn`，本票未动）。三次捕获到的症状分别是 `all(t["result"] == "submitted")` 为假、
     `len(extra_turns) 1 != 2`、`arrived[0].time == '07:02' != '07:01'`——同一测试的三处时序断言。
  2. `EngineTests.test_silent_abandonment_auto_continues_pending_action`（`test_engine.py:125`
     `action_resumed` 未出现）。**单跑 10 次 5 红 5 绿**，该用例用非 v4 的 `Scripted` agent 走 `_submit`
     分支、`system=None`，本票的四处改动（`_execute_chain` 的 speak 路由、`_action_rejection_text` 的台账
     提示、`_empty_streak` 的记录/检查点、零调用回合的回执）在这一分支上一个都不执行，因此与本票无关；
     但它的红色率说明它不是"偶发噪声"而是半个硬币——**建议另开票**（票 73 §6.1 要求的"下次出现必须保留
     全量输出再定性"这次做到了：症状、行号、单跑率都在这里）。
  全量输出留在 `/tmp/suite7.log`（绿）/`suite3.log`（绿）/`suite4.log`/`suite5.log`/`suite6.log`（未入仓）；`test_historical_failures.py`
  模块单跑 183 支全绿。

## 4. 仍然开着 / 移交

1. **种子侧（`v4/world/`，本票禁改）**：三个 `公告栏` 需要补 `takeable: false` + `fixed_reason`（§1.3）。
2. **`Ledger.query` 的 `limit` 分支在正常流程下不可达**：一次命中后 `status` 就变 `completed`，之后的提问走
   `closed`（实测回执是"这一案已经了结，它闭口了"）。两种都满足"超限即闭口"，但 `query_limit > 1` 的种子
   实际上仍只答一次。要让多次提问有意义，得改"什么时候算结案"的产品语义——**需人裁定**，本票未动。
3. **事实表逐字匹配**：`Ledger.query` 要求问题与条目逐字一致（既有语义与既有测试
   `test_invalid_ledger_query_does_not_consume_quota` 一起钉住）。所以台账能答的前提是模型问法贴着条目，
   而 `speak` 通道本身不负责改写问法。09:02 的实际原话是一段陈述句，命不中条目时它会答"不知道"（这正是
   本票要求的行为）。**若下一窗口出现"问了却答不上"，应开种子票给模型可用的问法线索（例如案卷条目本身
   作为可读文书），而不是放宽匹配**——放宽会把 `unknown`/`known` 这类子串变成命中。
4. **同步 `Runner`（遗留驱动）未接对话通道**：`runner.py` 仍只认 `system_query` 意图，v4 生产入口
   （`real_run`/`resume_run`）走 `AsyncEngine`，所以不影响真实轨迹；这条与票 51（sync/async 漂移）同族，未在本票扩张。

## 5. 复算命令

```text
cd 契约失效时请勿喂猫/v4
python3 -m unittest harness.tests.test_historical_failures.LedgerDialogueGates
python3 -m unittest harness.tests.test_historical_failures.ConsecutiveEmptyTurnGates
python3 -m unittest harness.tests.test_historical_failures.NoActionNoticeTextGates
python3 -m unittest harness.tests.test_world_pack.PlaceBoundDocumentTests
python3 -m unittest discover -s harness/tests -p 'test_*.py'
python3 scripts/seed_lint.py
```

窗口 3 的空回合诊断可原样复算（只用归档工件，不再调 provider）：

```text
python3 - <<'EOF'
import json
d = json.load(open("runs/real-20261018T033115+0800-1755244-201779124.json"))
print([t["result"] for t in d["system_turns"] if t["request"].get("kind") == "empty_turn"])
print([(t["perception"]["time"], t["result"], t["error"])
       for t in d["agent_turns"] if t["actor"] == "陈默"
       and "08:42" <= t["perception"]["time"][11:16] <= "09:04"])
EOF
```
