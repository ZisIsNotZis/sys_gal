# 90 — M1 第三窗口（07:00→12:00）观察到的引擎/提示层缺陷

Status: needs-triage
Need-review: no
Need-test-cases: yes

> 来源：`.scratch/v4-first-day/reports/m1-window3-07to12.md`，run
> `real-20261018T033115+0800-1755244-201779124`（种子 = 票 89 修后；引擎 = 票 88 修后；
> 07:00→12:00，406 turns / 1315 events，`stop_at_reached` @12:00，wall 671.9s，
> provider transient failures 全 0，replay `contiguous: true` / `world_versions_contiguous: true`）。
> **本票只登记、不修**：窗口运行的边界是不改 `harness/`、`scripts/`、`world/`。
> 种子侧缺口见报告 §"仍需修" N2/N6/N11；本票只收引擎、提示与 trace 记账三处。

本窗口的正面结论先记一句，免得下面九条读成"世界还是坏的"：票 88 的三条主修真的生效了
——纸笔族拒绝 0 次（窗口 2 是 12 次）、`item_given` 全窗口 0 次、8 张 `persist` 文稿全部落盘，
并且第一次出现了"成稿留在收件地点 → 收件人读到 → 用编号回话"的完整链路（`note-班长-8`）。

## 1. 台账案件在 v4 不可达（P0，接口缺口）

### 现象

陈默 09:02 想回答台账的三条款，唯一能想到的通道是把台账当人说话：

```text
09:02 陈默 submitted inner：台账要我给出三项答案；我对着手边的台账说出依据明确的结论，不把代笔者误认成责任人。
      calls: [{"name": "speak", "args": {"text": "这是2013年台风后用于确认邻里撤离与互助事项的通知书；责任人是……",
                                         "to": ["2013年台风台账"], "wait_response": false}}]
      err:   speak: unknown or ambiguous speak recipient: unknown name '2013年台风台账';
             available: 唐小岚 / 宿管阿姨 / 林瑶 / 班长 / 辅导员 / 陈默妈
```

全窗口计数：`system_case_accepted` 1 次（07:00 开局），`system_answer` **0** 次，
`system_reward_granted` **0** 次。案件从开局到端点一次都没有被回答。

### 证据链（代码）

- `harness/kernel.py:273` `World.ACTIONS` 只有 `wait/speak/text/move/take/place/give/read/leave_note/knock/trash/continue_action/abandon_action`——**没有 `ask`**。
- `harness/system.py:57` `Ledger.affordances()` 注释写"台账不是工具（工单 14）：交互走世界内对话（ask），这里无 affordance"，返回 `[]`——它引用的 `ask` 在 v4 的动作集合里不存在。
- `harness/runner.py:266` 处理 `intention.kind == "system_query"`，但 v4 的模型侧只暴露 `action_schema.SCHEMAS` 里的工具（`harness/action_schema.py:43`），其中没有 `system_query`/`ask`。
- `docs/V4-AGENT-INTERFACE.md:194` 明写"受约束角色用 ask/系统通道向它提问"——文档承诺的通道与实现不一致。

### 为什么贵

台账是陈默这条主线的"契约"本体（案件条款：说出它是什么 / 责任人是谁 / 期限）。
不可达意味着**主线的一半在结构上不可能推进**，模型只能转而对着纸面核查（这半边写得很好，
但那是另一条线）。这也解释了 08:42–09:04 的九连空回合（§2）：他在两条线之间没有可选动作。

### 建议（需人裁定方向）

1. 最小修复：`speak` 的收件人解析在"未知名字"分支之前先查系统名（`Ledger.name`），命中即走 `Ledger.query`，把 `ActionRejected` 的四种原因（非绑定角色 / 无案件 / 次数用尽 / 不在事实表）作为结构化回执交回；或
2. 补一个 `ask` 工具（schema 与 `Ledger.query` 的四种拒绝一一对应），并在工具说明里给出"问题必须命中事实表条目"的提示。
两种都要配一支红→绿：拒绝态（未命中事实表、次数用尽）与被拒后世界不变。

## 2. MC 连续空回合没有补偿：九连空烧掉 20 分钟世界时间（P1）

### 现象

陈默 08:42–09:04 连续 9 个回合 `result=none`、`inner` 为空、`calls` 为 `null`，
但每个回合世界版本照常前进（482→798）、时钟每个回合前进 2 分钟：

```text
08:42 none  ver 506   private_chars 107     08:48 none ver 582   08:56 none ver 696
08:44 submitted（update_memory）            08:50 none ver 612   08:58 none ver 729
08:46 submitted（flashback）                08:52 none ver 637   09:00 none ver 754
                                            08:54 none ver 658   09:04 none ver 798
```

`system_turns` 里这 9 条都被记为 `empty_turn{role: mc, reason: prose_only, private_chars: 81..142}`
——**记账有了（票 88 的扩展是对的），但世界和提示层都没有任何补偿动作**。

### 判据与影响

- 全窗口 `empty_turn` 20 次 = `mc 10 + npc 10`，`reason` 全是 `prose_only`；其中 mc 的 9 次扎堆在这 22 分钟。
- 故事层表现为"主角对着空气想了二十分钟"：他没有换地点、没有问人、没有动作，而外界（林瑶 09:19 到场读他的便条）在推进。

### 建议

连续 2 次空回合后注入一次"本回合必须给出一个具体动作，或明确 `wait`"的重述（一次性，不叠加）；
或把连续空回合降级为一次显式 `wait` 并记明原因，让世界时间有归属。需补看守测试：连续空回合不吞钟、
或吞钟必须有 `wait` 事件可归因。

## 3. `extra_arrived` 不带身份，评审无法核对"身份 vs 知识 vs 回答"（P1，trace 记账）

### 现象

```text
$ grep extra_arrived
08:00 {"location": "半坡咖啡馆"}
08:38 {"location": "教学楼"}
08:42 {"location": "教学楼"}
08:42 {"location": "半坡咖啡馆"}
09:17 {"location": "教学楼"}
```

只有地点，没有 `fragment`/`knowledge_notes`。而 `runner.extras` 在端点已清空（全部 idle despawn），
`checkpoint` 里也只剩地点池定义——**事后无法回答"这个 extra 是哪条池条目生成的"**。

### 为什么这条要单独开

本窗口最贵的一条无解线索是"课表/教室"（47 条发言、6 人、08:30–09:57）。教学楼池里
`课间的同学` 的 `knowledge_notes` 明写"课程表、辅导员办公室在哪一层"，而三名教学楼 extra
（马学姐 / 胡师傅 / 刘阿姨）全部回答"不知道第一节课在哪间教室 / 你问问附近同学"。
要么是"最该知道的人被随机取名后否认自己的知识"（提示层/采样问题），要么是随机取到的不是那条
（采样问题）——**当前 trace 无法区分**，评审只能存疑。同类问题见票 68（私有状态误导评审）。

### 建议

`extra_arrived` 的 payload 带上 `fragment`（可与票 88 的 `alias` 一并写），
并考虑在 `extra_removed` 上带同一条目的 `knowledge_notes` 摘要（不再是私有推理，只是种子声明）。

## 4. 忙态重复 `speak` 仍然收不了尾（P1，提示层）

### 现象

4 个 `rejected` 回合、8 个片段（4 条 `not executed…cannot start while 'speak' is in progress` + 4 条"不要用 wait"提示），全部是 extra 在上一句 `speak` 未完成时重发客套：

```text
08:48 胡师傅  speak("好，那我先忙值班了。")        cannot start while 'speak' is in progress until 08:49
08:57 马学姐  speak("嗯，先这样。")                 …until 08:58
09:01 胡师傅  speak("好，那我先不打扰你们了。")     …until 09:02
09:03 胡师傅  speak("行，那我先不打扰你们了。")     …until 09:04
```

判定是对的（一回合一个耗时动作），但代价是**客套话说了四遍都没说出口**，读起来像卡带。
票 88 §5-4 记过同一族（"extra 系统提示缺'一回合只说一句'的约束"），本窗口复现。

### 建议

extra 系统提示补一条"上一动作未完前不要重发同一句；宁可下一回合再说"；
引擎侧在忙态拒绝的回执里明确"这句话会在 X 秒后可用，不要在本回合重发"。

## 5. 日常称呼不可寻址：'小满' 叫不到、'林瑶室友' 是描述（P1，概念缺口）

### 现象

```text
08:51 辅导员 speak(to=["林瑶室友"])  → unverified partial name '林瑶室友'
09:25 班长   text(target="林瑶室友") → unverified partial name '林瑶室友'
                                     Names in your personal knowledge or here: 刘阿姨, 唐小岚, 宿管阿姨, 林瑶, 辅导员, 陈默
```

但世界内部所有人都在用"小满"叫她：林瑶 07:03"小满，我刚看了晚归登记本"、
宿管阿姨 07:26"小满，记不清就先这样"。**"小满"不可寻址，"林瑶室友"也不是可用称呼**，
于是室友对班长与辅导员同时不可达（他们当时正需要问她课表）。

### 建议

票 88 给地点池条目加了 `aliases`；同一机制可推广到角色小名/关系称呼（"小满"、"陈默他室友"），
或让 `known_contacts` 行支持"关系+正式名"的解析。需要人裁定是"补数据"还是"补解析"。

## 6. `outcome.unread_notes` 不计 persistent 文稿（P2，报告记账）

```text
outcome  = {"reason": "stop_at_reached", "time": "2026-03-16T12:00:00+08:00",
            "world_version": 1315, "unread_notes": []}
```

而 `note-唐小岚-6`（09:19，半坡咖啡馆，写给草稿主人）到 12:00 无人读：全窗口 8 次文稿读取
里没有一条命中它的正文。`unread_notes` 只统计会烧掉的缺省字条，persistent 文稿未读不计入。
评审只看 outcome 会误以为投递全部完成（票 68 同族：记账让人误判）。

### 建议

outcome 增计 `unread_persistent_notes`（或统一改成"未读文稿"并给出 id 列表）。

## 7. `wait` 的 900 秒上限没写在工具说明里（P2，提示层）

4 次撞墙后全部自愈（回执带 `Valid call`），但每次都浪费一个回合：

```text
07:03 唐小岚 / 07:09 下棋大爷 / 09:19 林瑶室友 / 11:50 唐小岚
  err: wait: 单次等待不能超过 900 秒；如需更久，请分几次等待。
```

### 建议

把上限写进 `action_schema` 里 `wait` 的 description（一句话），不改语义。

## 8. `take` 候选仍混入文书（P2，未在拒绝路径复现）

票 88 §5-2 记的"take 候选列文书"本窗口**没有造成拒绝**（`take` 只被用于 `一份餐食`/`签到本`/
`场地申请表`/`一份午饭`/`例汤`，全部成功），但候选清单本身仍然混着文书：

```text
11:21 林瑶 perception.nearby_items（学生会办公室）
  [值班簿, 公告栏, 可用纸笔, 圆珠笔, 场地申请表, 学生会审计包, 学生会审计通知, 空白纸]
```

`公告栏`（固定陈列）、`学生会审计通知`（文书）、`学生会审计包`（文书）与可拿的复制件
`场地申请表` 在同一张清单里，读者无法从清单本身判断哪些拿得走。票 81 §1 未修。

## 9. 未验证项（不是缺陷，但本窗口一个都没被走到）

| 项 | 本窗口读数 | 说明 |
|---|---|---|
| `empty_turn{role: extra, reason: no_output}` | 0 | 61 个 extra 回合都有输出；票 88 新增的诊断路径未被真实轨迹触发 |
| `inflight_released` | 0 | 窗口 2 有 1 次（林瑶室友 11:37）；本窗口无在飞释放 |
| `item_given` | 0 | 全窗口没有一次"递东西"；服务岗 `give`（票 89 §3 验证过的路径）未被触发 |
| `item_dropped` | 0 | E84 的 extra 落物路径仍未被真实轨迹触发（连续第二个窗口） |

### 建议

下一窗口（12:00–17:00）应专门制造三个触发场景：服务岗在饭点被要求"递一份"（触发 `give`）、
咖啡馆/教学楼出现"给在场的人一张纸"的需要（触发 `give` 的边界问题）、
以及 extra 池的 no_output（可用一次强约束的探针运行，而非靠巧合）。
