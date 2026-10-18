# 98 — v4 引擎第六轮（空值语义 / 单件归属 / 陌生人的场景事实）

Status: fixed
Need-review: yes
Need-test-cases: yes

> 输入：`issues/97-window5-findings.md`（E1–E4）、`reports/m1-window5-07to18.md`、票 95、
> run `v4/runs/real-20261018T062031+0800-1910732-547128242.json`（窗口 5，1670 agent turns / 4742 events，07:00→18:00）。
> 范围：`v4/harness/`（`kernel.py` / `action_schema.py` + 回归测试）与 `v4/docs/`（`V4-AGENT-INTERFACE.md` / `V4-ENGINE.md`）。
> **`v4/world/` 与 `v4/scripts/` 一行未动**；不新增动作种类，不新增世界状态字段（`take` 的“在途占用”
> 读的是各 actor 既有的 `current_action`/`pending`，本来就随检查点保存）。
> 记录层只改一处：票 97 的 E3/E4 两条推断按 §5 就地更正（保留原句 + 更正理由，不删历史）。

## 0. 一句话

窗口 5 的四条 P0 全部是“语义词失准”而不是“世界缺可做的事”：两条新参数把**空值**当成了“已提供”，
一条把**提交期**当成了归属已定，一条把**物件的客观描述**当成了公开知识；四条都在既有原语上收口，
并各配一支可复算的红→绿门。E3 的复现结论是**缺陷成立**：第二个 `take` 通过校验、完成事件照写、
世界不动——不是“第二人失败而回执错报”也不是“重复发放”，而是“回执与日志都报成功、世界只给一个人”。

## 1. E100（P0）· `leave_note on: ""` 被当成“在文书上补写”

**窗口证据**：全天 106 条拒绝（陈默 60 / 08:06→17:19、林瑶 23、林瑶室友 8、下棋大爷 3、唐小岚 3、辅导员 2），
形状一律是 `leave_note {"text": …, "persist": true, "on": ""}`。后果不只是丢回合：陈默 11:25 起对外说
“我之前三次尝试留书面说明都没有成功”，16:43 在面核记录上写“我未成功写成并署名自己的书面说明”——
他的《个人情况说明》全天没写成，而世界给他的理由是假的。

**根因**（`kernel._item_duration`）：`on = intention.args.get("on"); if on is not None:` —— 空串满足
`is not None`，于是“留一份新文稿”（`persist: true`）被自己判成“同时声明了 on 与 persist”。

**修法**（一处归一，后面只看一种写法）：

| 位置 | 改动 |
|---|---|
| `World.submit` | `leave_note` 的 `on` 若是空串/纯空白，从 args 里剔除（`Intention` 重建）。校验、`action_payload`、`_complete`、`_commit_interaction`、replay 从此只会见到“没有 on”。 |
| `action_schema` 的 leave_note 说明 | 明写“**不写 on（也不要写空的 on）就是留一份新文稿**，on 与 persist 只能选一个”。 |
| `docs/V4-AGENT-INTERFACE.md` §2 | 同上，并把“可选参数的空值等于未提供”提为 §2 开头的通用约定。 |

**拒绝文案**：`on` 与 `persist` 的互斥拒绝不再可能由空值触发，只有真的同时写了文书名与新文稿才出现；
它不再让模型以为“必须签名”。

**红→绿**：`BlankNoteOnGates`（3 支）——`on: ""` + `persist: true` 成功产生 `note_left`（persistent note 落地、
`document_annotated` 为零）、`on: "   "` 与不写 on 等价（房间字条一张）、`on: "面核记录"` 仍走批注路径（守卫）。

## 2. E101（P0）· `move with: [""]` 被当成“提供了同行者”

**窗口证据**：76 条“move 的 with 里有一个空名字”，相邻形态 `with: ["唐小岚"]`（自己）→ “unknown name”、
`["_self"]` → “unknown name '_self'”、`["陈默"]` → “unverified partial name”、`["陈默(you)"]` → “unknown name”。
唐小岚 08:29–08:59 七连撞空名字、13:04 对外说出“我现在发现移动需要明确同行者”，13:19–15:08 花 88 分钟
逐人求同行；陈默 17:45–17:51 三连撞，17:58 靠辅导员同行才走回男生宿舍。**接口没有“一个人走”的表达法**，
而 `Valid call: move {target}` 实测纠正不了。

**根因**：`_canonicalize_companions` 把空名字当结构化错误（`raise`），schema 又用 `minItems: 1` 堵住空数组
（`with: []` 直接是形状错误）——两条路都只在“省略 with”时通。

**修法**：

| 位置 | 改动 |
|---|---|
| `kernel._canonicalize_companions` | 先过滤空项/纯空白项、解析后去重；**过滤后为空就把 `with` 整个键去掉**，与没写 `with` 完全同一条路径。未知名字的拒绝追加 `kernel.WALK_ALONE_HINT`（“一个人走就只写 target——省略 with，不要写空值或占位符。”）。 |
| `action_schema` 的 move schema | `with` 去掉 `minItems: 1`：空数组合法（等于独自走）。 |
| `action_schema` 的 move 说明 | 加一句“**一个人走就只写 target，省略 with**——不要写空的 with、空字符串或‘自己/我’之类的占位符”。 |
| `docs/V4-AGENT-INTERFACE.md` §2 move 行 | 同上，并说明占位符不会让人走不动。 |

**红→绿**：`BlankCompanionGates`（4 支）——`with: [""]` 等同独自走（只有自己的 leave/enter，同伴留在原地）、
`with: []` 同、`with: ["林瑶","林瑶"]` 仍真的带上人（守卫）、`with: ["_self"]` 仍被拒但拒绝里出现
“target”而不再出现“空名字”（教学）。

## 3. E102（P0，正确性）· 同一件东西被两个人同时 `take`，都算成功

**复现（先做，不改代码）**：最小世界（同一地点两人 + 桌上 `一份晚饭`），同一 tick 两次 `submit`：

```text
# 修前
world.submit(take 一份晚饭 by 辅导员) → 接受
world.submit(take 一份晚饭 by 陈默)   → 接受     ← 第二条不该被接受
advance() → item_locations 已空；辅导员背包 {'一份晚饭'}，陈默背包 set()
event log: #1 action_started 辅导员 / #2 action_started 陈默
           #3 action_completed 辅导员 / #4 action_completed 陈默   ← 两次都写“拿起了”
```

**结论：是缺陷，而且不是报告猜的三种里的“item 被重复发放”，也不是“第二人其实失败而回执错报”——
是“第二人通过校验、拿到成功回执、世界日志也照写一条 `action_completed take`，但 `_complete` 撞上
`item` 已不在 `item_locations` 就走防御性 `return`，世界不变”。** 换句话说：**回执与日志都报成功，
只有世界知道少了一份**。真实事件序列（run `real-20261018T062031`）：

| 事件 | 时刻 | 内容 |
|---|---|---|
| #4694/#4695 | 17:56 | 辅导员 `move 食堂 with 陈默` 到食堂（enter 两条） |
| #4707 | 17:57 | `action_started 陈默 take 一份晚饭`（先提交） |
| #4708 | 17:57 | `action_started 辅导员 take 一份晚饭`（后提交，同样通过校验） |
| #4718 | 17:58 | `action_completed 陈默 take 一份晚饭`（先完成 → 真拿到） |
| #4719 | 17:58 | `action_completed 辅导员 take 一份晚饭`（后完成 → 世界不动） |
| #4734 | 17:59 | 辅导员 `speak`：“谢谢，我们都拿了晚饭。” |

没有第三个动作（没有 `give`/`trash` 把东西从一人转给另一人），结束态只有陈默背包里有它。所以报告
“只有一个人背包里有”对；“疑似重复”不对——是**校验时机**错了，不是数量错了。E75（票 75）同族：
那次是第二次完成 `KeyError` 崩钟，修法是完成期防御；本轮把不变量提到提交期。

**修法**：

| 位置 | 改动 |
|---|---|
| `kernel._item_claimant`（新） | 谁正在把这一件从原地拿走：读各 actor 的 `current_action`/`pending`，动作是 `take`，或是 `give` 的“就地拿起再递出”分支（那时东西还在原地、不在发起者背包里）。 |
| `kernel._raw_duration` take 分支 | 位置校验后加在途占用检查：被占用 → 结构化拒绝（“「一份晚饭」正被陈默拿在手里，还没落到你手里：等这一步结束，再看看它还在不在食堂”，`context.claimed_by`），世界零变化。 |
| `kernel._raw_duration` give 分支 | 就地递出同样是“把东西从原地拿走”，同一占用检查（这一条是复现时发现的同族第二个洞：两人各递一次同一份饭，**两个收件人背包里都会有一份**）。 |
| `kernel._take_rejection`（新） | 拿不到时说真话：先报“在 X 手上”，再报“在 Y 地点”，再报“已经不在世上任何地方”；只有**从未注册过**的名字才说“这里没有「X」可拿”（不替不存在的陈设编一段被销毁的历史）。 |
| `kernel._complete` | `take` 的防御分支条件从 `item not in item_locations` 收紧到 `item_locations.get(item) != a.location`；`give` 只在“真的从自己手里或自己脚下递出”时才把东西给收件人，旧检查点里排着的第二次 give 不再凭空变出一份。 |
| `action_schema` / docs | take 说明明写“一件东西只有一个归属：别人正在拿这一件时会被拒绝并被告知在谁手里；被拿走了就问那个人要，不要重复 take 同一件”。 |

**红→绿**：`SingleInstanceTakeGates`（5 支）——同一 tick 第二次 `take` 被拒且点名占用者（`claimed_by`）、
一件东西永远只有一个持有者且日志里不能有第二句“拿起了”、完成之后再 take 会说出“现在在陈默手上”、
被 `force_interrupt` + `abandon_action` 的 take 会释放占用（守卫：占不是永久锁）、
两人各递一次同一份饭不能让两个收件人都拿到。
`HistoricalFailureGates.test_take_race_second_completion_does_not_crash_the_clock`（E75）按更紧的不变量重写：
第二次**提交**已被拒，完成期防御只剩“恢复旧检查点”这条路，于是直接喂给它一次完成，钉住“不崩钟、也不改世界”。

## 4. E103（P0，泄漏）· 陌生人回话携带了别人还没送到的便条正文

**窗口证据**：15:04 唐小岚 `read 代话便条`（`document_read #3656`，正文含“稿子的事我晓得了，别再往吧台上放”），
15:05 她向“陌生人”求同行（`stranger_asked #3669`），15:06 `extra_arrived 张学长`（#3678）后立刻回：
“愿意啊。老板娘还留了话：稿子的事她晓得了，别再往吧台上放；她说改天自己过去一趟。”（#3685）

**诊断（结论与报告假设不同）**：extra **没有**拿到提问者的 KB、记忆或 `document_read` 正文——
`_extra_turn` 的输入只有 `build_extra_briefing(transcript, scene)`，transcript 只筛 `speech` 里
`visible_to` 命中它的行，system prompt 只有身份碎片 + 该地点的 `knowledge_notes`。
泄漏通道是**场景事实块**：`scene_perception` 把同地每件东西的 `entity_descriptions` 全文放进 `descriptions`，
而 `代话便条` 的客观描述（`world/documents/代话便条.md`）就是便条正文，种子已经把它声明成
`known_to: [唐小岚]`。该回合的 `perception.descriptions["代话便条"]` 就是那段正文，逐字可核。
`partner_gone` 等路径没有复用旧 session 的问题（回收即 `remove_extra` + 取消任务 + `_extras.pop`）。

**修法**：extra 的输入 = **当面听到的话 + 该地点的公开可见物 + 自己的身份**。
`kernel._described_to` 让被种子 `known_to` 限定给别人的东西只出现在 `nearby_items`（看得见它摆在吧台上），
不再把描述正文交给名单外的人；公开物件（`校报草稿`）照旧给描述，票 57 的“一份不是一摞”锚点没有被削弱。

**红→绿**：`ExtraScenePrivacyGates`（3 支）——陌生人组装出的场景块与整份 perception 都不含便条正文、
却仍看得见 `代话便条` 在场；公开物件的描述与“一份”仍在（守卫）；`known_to` 名单里的唐小岚自己仍看得到
描述与正文（守卫）。另有一次性端到端核对（真实引擎 + 真实种子，脚本未入库）：

```text
【你此刻在半坡咖啡馆】在场的人：唐小岚。
【你眼前的实情…】- 代话便条 / - 备品清单 / - 校报草稿：…（正文）/ - 裂纹马克杯
【你实际听见的近处交谈】唐小岚（对你说）：同学，我受老板娘所托去后街糕点铺带句话，你愿意陪我去吗？
leak? False   代话便条 present? True
```

## 5. 顺带（P2）· 两条推断的核对与记录更正

1. **`辅导员 take 一份晚饭` 与 `陈默 take` 的先后**：陈默先提交（#4707 在 #4708 之前）、先完成（#4718），
   他拿到；辅导员那条同样“成功”但世界不动（#4719）。差别只在**提交顺序**，与角色身份无关。
   结论：**缺陷**（见 §3），已在提交期修掉。
2. **`张学长` 缺 `extra_arrived` 的生成路径**：**记录存在，报告读错**。#3678 15:06
   `extra_arrived 张学长 {"location": "半坡咖啡馆"}` 就在轨迹里，其后 15:06/15:08 两次 `speech`、15:08
   `leave {"escorted_by": "唐小岚"}`、15:15 `enter 小卖部`、15:19 `extra_removed {"reason": "idle"}`，
   全链可核。复算式 `analyze_window5.py` 里根本没有 extra 分节，这个判断是人工翻轨迹时的误读。
   **结论：记录缺失不成立**；已在票 97 §3 补一行更正，本票不复述第二次。
3. **顺带发现（本票不修，登记给下一窗口）**：上面那条链里，张学长 15:19 在**同行途中**被
   `extra_idle_seconds` 当“闲”回收（当时两人都在小卖部，`alive` 为真、只命中 `idle`），
   于是“愿意陪你去”的路人走到一半消失，唐小岚独自走完 15:28 夜市 → 15:33 后街糕点铺。
   机制位置：`AsyncEngine._handle_extras` 的 `idle` 判定（`now - last_active > extra_idle_seconds`），
   它不区分“没人跟它说话”和“它正跟着人赶路”。要么给在 `escorted_by` 链上的 extra 免 idle 回收，
   要么把回收理由降级为一次可见的中断；两条都要动 `_handle_extras` 的判据，属于下一轮。
   → 已在票 99（E104）修掉：idle 判据排除“在飞同行”与“没结的对话”，被携带者离开仍走“途中可脱离”。

## 6. 红→绿证据（变异对照，均在 `/tmp/mut98*` 副本上复算）

| 组 | 变异 | 读数 |
|---|---|---|
| E100 | 删掉 `submit` 里“空 `on` 剔除”那一段 | `BlankNoteOnGates`：**2 红 / 1 绿**（红的正是空串与纯空白；绿的是“真文书仍走批注”守卫） |
| E101 | 把空名字改回 `raise`，并把 schema 的 `minItems: 1` 装回去 | `BlankCompanionGates`：**2 红 / 2 绿**（红＝空项与空数组；绿＝真同行、教学提示——教学句在未知名字分支里，未动） |
| E102 | 删掉 take 的在途占用检查 | `SingleInstanceTakeGates`：**2 红 / 3 绿**（红＝第二次提交被拒、日志只许一句“拿起了”；绿＝完成期措辞、占用释放、`give` 那一半） |
| E102（give） | 只删掉就地递出的占用检查 | `SingleInstanceTakeGates`：**1 红 / 4 绿**（红＝两人各递一次同一份饭） |
| E103 | 去掉 `scene_perception` 的 `_described_to` 过滤 | `ExtraScenePrivacyGates`：**1 红 / 2 绿**（红＝便条正文出现在陌生人输入里；绿＝公开物件与本人可见两支守卫） |

## 7. 回归读数（收尾实测，`cd 契约失效时请勿喂猫/v4`）

```text
python3 -m unittest discover -s harness/tests -p 'test_*.py'
  675 支（基线 660；本票 +15：BlankNoteOnGates 3 + BlankCompanionGates 4
        + SingleInstanceTakeGates 5 + ExtraScenePrivacyGates 3）→ OK (skipped=1)
  全量共跑 6 次（收尾前后）：4 次 `OK (skipped=1)`（674 支 1 次、675 支 3 次），
  2 次只红 1 支——两次都是已登记的半硬币 `test_extra_turns_are_recorded_and_conversational`
  （票 73 §6.1 族，见下），一次发生在 674 支、一次在 675 支
python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
  221 支（基线 206，+15；`test_take_race_...` 是重写不是新增）→ OK
python3 -m unittest harness.tests.test_historical_failures.PersistentNoteGates
  6 支 OK（含 runs/archive-20261016-attempt1/d1-am.json 的加载）
python3 scripts/seed_lint.py
  seed lint OK（exit 0；warning 8 条，与票 91/92/93/95 同数同族）
```

- **按新事实校准的既有测试**（每条都核对过量尺）：
  - `HistoricalFailureGates.test_take_race_second_completion_does_not_crash_the_clock`：原本钉“两次完成都成立、
    世界只动一次”，现钉“第二次**提交**被拒 + 完成期防御仍不改世界”（理由见 §3）。
  - `SeedLocationPropGates.test_unregistered_interior_props_still_offer_a_real_next_call`、
    `Ticket65CanteenServeGates.test_rope_is_declared_unavailable_where_it_was_reached_for`、
    `SameKindFailureGates.test_same_kind_rejections_reach_the_chain_path_notice`：三支都念“这里没有「X」可拿”，
    在“名字从未注册”这一支上原样保留（`_is_entity` 为假时才说这句），所以只是行为对齐，没有改断言。
- **已知间歇族（如实记录，与本票代码路径无关）**：`test_extra_turns_are_recorded_and_conversational`
  （票 73 §6.1 的 extra 时序族；本轮单跑 17 次，2 次红，症状 `(first_answer.time - arrived[0].time) = 120s > 60s`）
  与 `test_silent_abandonment_auto_continues_pending_action`（`test_engine.py:125`，非 v4 `Scripted` agent、
  `system=None`；本轮单跑 6 次全绿）。全量最后两次均 `OK (skipped=1)`。
- **向后兼容**：世界状态零新增字段；`current_action`/`pending` 本来就随检查点保存，占用判定不引入新状态；
  `leave_note` 的空 `on`、`move` 的空 `with` 只是提交期归一，日志/检查点里不会再出现这两种写法，
  旧检查点与归档工件照常加载（`PersistentNoteGates` 绿）。

## 8. 仍然开着 / 移交

1. **`poll` 的 `descriptions` 仍是宽的**（主角色，不是 extra）：站在半坡咖啡馆的任何人（林瑶、陈默……）
   都能从 `descriptions` 拿到 `代话便条` 的正文。收窄它要动票 49/61 已裁定的“走到/拿到就给客观描述”，
   属于另一条裁定，本票不动；E103 只钉住 extra 这条已发生泄漏。
2. **种子侧（`v4/world/`，本票禁改）**：`备品清单`（`known_to: [唐小岚]`）与 `裂纹马克杯`
   （`known_to: [唐小岚]`）的描述同样不再发给路人——若某件东西的**外在样子**本就该让所有客人看见，
   种子就别给那一行写 `known_to`（这个声明的所有者是种子，不是引擎）；`代话便条` 则正该保持受限。
3. **占用的粒度是“整件东西”**：一件东西被占期间，别人连“拿走一份”都要等（本种子里同一 id 就是一份，
   所以这是对的）。如果要演“锅里还有很多份”，那需要多个实例 id，不是放宽占用。
4. **在途占用不含 `place`/`trash`**：那两条都不会复制物品（`place` 从背包放进地点、`trash` 只做删除），
   本轮不扩大到它们；“同一个 tick 里 take 与 trash 同一件”仍是未测组合。

## 9. 复算命令

```text
cd 契约失效时请勿喂猫/v4
python3 -m unittest harness.tests.test_historical_failures.BlankNoteOnGates
python3 -m unittest harness.tests.test_historical_failures.BlankCompanionGates
python3 -m unittest harness.tests.test_historical_failures.SingleInstanceTakeGates
python3 -m unittest harness.tests.test_historical_failures.ExtraScenePrivacyGates
python3 -m unittest harness.tests.test_historical_failures.HistoricalFailureGates.test_take_race_second_completion_does_not_crash_the_clock
python3 -m unittest harness.tests.test_historical_failures.SeedLocationPropGates
python3 -m unittest harness.tests.test_historical_failures.Ticket65CanteenServeGates
python3 -m unittest harness.tests.test_historical_failures.SameKindFailureGates
python3 -m unittest discover -s harness/tests -p 'test_*.py'
python3 -m unittest harness.tests.test_historical_failures.PersistentNoteGates
python3 scripts/seed_lint.py
```

变异对照（每组一个副本，改完只跑对应点类）：

```text
rm -rf /tmp/mut98a && mkdir -p /tmp/mut98a && cp -r harness world scripts /tmp/mut98a/
# kernel.submit：删掉 leave_note 的空 on 剔除
cd /tmp/mut98a && python3 -m unittest harness.tests.test_historical_failures.BlankNoteOnGates
  → Ran 3 … FAILED (errors=2)

rm -rf /tmp/mut98b && mkdir -p /tmp/mut98b && cp -r harness world scripts /tmp/mut98b/
# kernel._canonicalize_companions：空名字改回 raise；action_schema：with 装回 minItems: 1
cd /tmp/mut98b && python3 -m unittest harness.tests.test_historical_failures.BlankCompanionGates
  → Ran 4 … FAILED (errors=2)

rm -rf /tmp/mut98c && mkdir -p /tmp/mut98c && cp -r harness world scripts /tmp/mut98c/
# kernel._raw_duration：删掉 take 的在途占用检查
cd /tmp/mut98c && python3 -m unittest harness.tests.test_historical_failures.SingleInstanceTakeGates
  → Ran 5 … FAILED (failures=2)

rm -rf /tmp/mut98e && mkdir -p /tmp/mut98e && cp -r harness world scripts /tmp/mut98e/
# kernel._raw_duration：只删掉 give 就地递出的占用检查
cd /tmp/mut98e && python3 -m unittest harness.tests.test_historical_failures.SingleInstanceTakeGates
  → Ran 5 … FAILED (failures=1)

rm -rf /tmp/mut98d && mkdir -p /tmp/mut98d && cp -r harness world scripts /tmp/mut98d/
# kernel.scene_perception：去掉 _described_to 过滤
cd /tmp/mut98d && python3 -m unittest harness.tests.test_historical_failures.ExtraScenePrivacyGates
  → Ran 3 … FAILED (failures=1)
```
