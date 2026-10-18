# 101 — v4 引擎第七轮（便条可递 / 睡眠 / 没被问的空回合 / 机制不入对白）

Status: fixed
Need-review: yes
Need-test-cases: yes

> 输入：`issues/100-window6-findings.md`（W6-E1…E6）、`reports/m1-window6-18to22.md`、票 98/99、
> run `v4/runs/real-20261018T073833+0800-2019091-492642480.json`（窗口 6，07:00→22:00 全量轨迹，
> 夜间 211 agent turn / 566 新事件，18:00 从窗口 5 第 2 段检查点续跑）。
> 范围：`v4/harness/`（`kernel.py` / `engine.py` / `replay.py` / `action_schema.py` + 回归测试）、
> `v4/docs/`（`V4-AGENT-INTERFACE.md` §1/§2、`V4-ENGINE.md` §3/§7.5/§7.10）。
> **`v4/world/`、`v4/scripts/` 一行未动**；不新增动作种类；不新增世界状态字段（便条的持有者就是背包里的
> 一项，`sleeping` 是本就在检查点里的既有字段）。

## 0. 一句话

窗口 6 把窗口 2 的“纸张族”病灶收窄成一句话：**字写得出、读得到，就是递不出去**——因为“写在一张纸上并
交给他”在世界里没有路径；而“睡觉”没有表达法，于是 4 小时夜里 43% 的回合是 `wait 900`。本轮四条修法都
是既有原语收口：`give` 认便条、`leave_note on=` 认手边的纸、`wait` 多一个 `sleep: true` 参数、extra 的
“没被问”回合补一行诊断；另有一句提示层规矩（机制不入对白）。每一条都有红→绿门与台账编号。

## 1. E105（P0）· 便条/文稿可被当面交付

**窗口证据**（均可在 run 中逐条复核）

| 时刻 | 调用 | 结果 |
|---|---|---|
| 18:44→18:46 | 陈默 `leave_note {text, persist: true}` @男生宿舍 | 成功 → `note-陈默-1`，班长/辅导员/唐小岚读到 |
| 18:48 | 陈默 `give {target: 辅导员, item: note-陈默-1}` | **拒**：“你没有拿着「note-陈默-1」，这里也没有…”＋“可行调用：give 2013年邻里撤离通知书” |
| 19:07 | 陈默 `leave_note {text, persist: false, on: "空白纸"}` @学生会办公室 | **拒**：“这里没有可以在上面写字的文书「空白纸」…要留一张新字条就别写 on” |
| 19:11 | 陈默 `leave_note {text, persist: false}` | 成功，burn 字条，现场三人 `notes_here: []`，到 22:00 仍 `unread_notes: 1` |

**根因**：`give` 只认 `inventory` 与 `item_locations`（`kernel._raw_duration` 的 give 分支），
`persistent_notes` 是另一张表；`leave_note` 的 `on` 只查当前地点的 `document_defs`，而 `空白纸` 是
inventory 里的 item，永远进不了这个集合。主角 D1 的核心目标（“自己写好、签名、亲手交给辅导员”）因此
**结构上不可达**，他用 12 个回合证明了一遍，并且如实承认没交。

**修法（按目标类型分派，不新增动作种类）**

| 位置 | 改动 |
|---|---|
| `kernel._raw_duration` give 分支 | 可递物 = 物品 ∪ 已存在的便条 id。便条在作者背包里，或留在他所在地点且不被人拿着 → 可递；否则结构化拒绝，**只说它在谁手上/哪里**，不再列无关文书的“可行调用”。 |
| `kernel._complete` give 分支 | 便条：从发出者背包移到收件人背包并更新 `note["location"]`；事件仍是既有的 `item_given {item, from, to}`。 |
| `kernel.available_now` / `_note_carrier` / `_notes_here` | 被递出去的便条属于持有者：只由持有者读到；同地他人不能隔着手读，`notes_here` 也不再把它当“留在这里的纸”。 |
| `kernel._complete` place 分支 | 放下一张便条 = 它又变回“留在这里的纸”（不进 `item_locations`，它没有 item 行）。 |
| `kernel._raw_duration` leave_note 分支 | `on` 指向**无正文的纸张**时（不是文书、不是固定陈设、手上或眼前，描述里既是“纸”又能“写”，`WRITING_SURFACE_HINTS`）→ 写在这张纸上：产出带编号的文稿（同 `persist` 的那一种），纸被用掉、文稿进作者手上（因此可以 `give`）。`on` 指向文书仍走既有批注路径。 |
| `kernel._unwritable_on_rejection` | 两样都不是 → 拒绝并列出此刻真的能写的（文书 + 纸张），不再推荐别的东西。 |
| `kernel.affordances` | leave_note 的 hint 说出能写的纸与“写好的纸可以 give”；give 候选与 trash 候选含手上的便条。 |
| `replay._apply_consequence` | 重建三件事：`note_left` 带 `on`+`persist`（纸被写掉、文稿在作者手上）、`item_given` 一只手换到另一只手、`place` 把便条放回地点。 |

**红→绿**：`NoteDeliveryGates`（5 支）——写在纸上的说明交出后收件人读到全文且作者不再持有；留在桌上的
persist 文稿也能当场递出（收件人拿在手上，别人读要经过他）；被拒的交付回执里不出现无关文书；replay 同 id
同手、空白纸不会复活；affordance hint 说得出能写的纸，`on: 圆珠笔` 被拒且 `context.writable_sheets ==
["可用纸笔","空白纸"]`。

## 2. E106（P0）· 睡眠

**窗口证据**：7 次 `wait 34200–48960`（≈9.5–13.6 小时，“睡到明早”）被 `longest_wait_seconds=900` 拒收
（18:04 班长、18:09 林瑶、18:44 唐小岚、18:48 林瑶室友、19:51 辅导员、21:24 辅导员、21:30 陈默）；
夜间 `wait` 90 次（900s×62），占 211 个回合的 43%；19:14–21:24 是 2h10m 的结构空转。

**根因**：半个语义早就在（`ActorState.sleeping`、`payload.action in {"wait","sleep"}` 的可见性分支、
`continue_action` 的 `uninterruptable` 注释），缺的只是入口：`wait` 没有“我在睡”的表达，而 900 秒的
上限是“守一会儿”的尺度，不是“过夜”的尺度。

**修法**

| 位置 | 改动 |
|---|---|
| `kernel.SLEEP_WAIT_SECONDS` | `12 * 3600`：`sleep: true` 的 wait 上限。普通 wait 仍是 `longest_wait_seconds`；超限的普通 wait 拒绝时直接教 `sleep: true`（`kernel.WAIT_SLEEP_HINT`）。 |
| `kernel._raw_duration` | 校验 `sleep` 只能是布尔；按 `sleep` 选上限。 |
| `kernel.submit` / `_complete` / `_resume` | 起睡置 `sleeping=True`，完成/叫醒/被打断/恢复时与 payload 对齐。 |
| `kernel.wake_sleeper`（新） | `target` 点名了他的 `world_event` 能提前结束睡眠；只对 `sleep` 生效（普通 wait 的唤醒类不变）。 |
| `engine._wake_waiters` | 新增 `world_event` 分支：按 payload `target` 调 `wake_sleeper`；**未点名的全场广播不叫醒**。同地社交事件仍走既有 `wake_waiter`。 |
| `action_schema` / 文档 | `wait` schema 增加可选 `sleep`，工具说明写清上限、语义与唤醒路径。 |

语义：**睡到指定时长，或被打断/被唤醒**。睡着时世界照旧走、事件照常投递（无 asleep 过滤，M1 裁决不变），
他人看不见你在睡（既有可见性）。

**红→绿**：`SleepWaitGates`（4 支）——8 小时睡眠成功且时钟走到 15:00、任务事件带 `sleep`、行动作对他人
不可见、睡完 `sleeping=False`；被叫醒提前结束且普通 wait 不受 `wake_sleeper` 影响；引擎里点名的 09:00
事件把 8 小时睡眠叫醒（那一回合就发生在 09:00），而同样时刻的全场广播不叫醒；replay 事件与时钟一致、
检查点带着睡眠状态且恢复后仍叫得醒。

## 3. E107（P1）· extra 的空回合仍然静默——判定：这一回合模型根本没被请求

**窗口证据**：18:00 胡大叔 `result: "none"`、`calls: []`、`inner: null`、`role: extra`；夜间 `system_turns`
与本段 turn id 的交集为空，**没有任何 `empty_turn`**；18:02 只有一条 `extra_removed idle`。

**定位过程**（按事件的因果顺序，而不是按计数字段）：

1. 18:00 前后 胡大叔 已无任何 wake-class 事件：`events` 里 `visible_to` 含他的最后几条是 17:49 唐小岚的
   一句“好，谢谢您配合”与他自己 17:50 的回话，之后只有 18:01 的 `time_advanced`（不在 `WAKE_EVENT_KINDS`）
   和 18:02 他自己的 `extra_removed`。
2. 18:00 正是从窗口 5 检查点续跑的那一刻（`window6-18to22.log`；本段 engine turn 1600→1810 的接续）。
   `run()` 对 `self._extras` 的每个条目重建 `_extra_loop(name, "")`，而 restored 行的 `context_cursor` 已是
   旧日志末尾——第一拍 `needs_response = bool(question) or extra_heard_speech_since(...)` 两项都为假。
3. `_extra_turn` 里 `if not needs_response: pass`，于是 `result="none"`、`intention_calls=[]`，trace 只记一行
   `record_agent(result="none")`；`empty_turn` 那一支的条件是 `needs_response and …`，因此**不记**。

**判定**：这一回合**没有被请求**（provider 调用 0 次），所以它既不是“模型沉默”也不是“引擎丢回合”；
现场读数是 `calls: []`、`inner: null`、`error: null` 三项同时为空——模型被请求时至少会留下正文或一个错误
（同段其他 extra 回合都有）。E90 的 `no_output` 覆盖不了这一种，因为它以“真的问了”为前提。

**修法（只加诊断，与 MC/NPC 一致）**：`needs_response` 为假时也记一条 `empty_turn`
（`role: extra`、`reason: no_request`、`private_chars: 0`）。世界不变、不惩罚角色，两种空回合从此可分辨。

**红→绿**：`ExtraNoRequestTurnGates`（1 支）——先让引擎跑出一段真实对话（路人被问过），取
`checkpoint_state()`，再把引擎状态恢复到一个新引擎上跑 3 分钟；断言续跑段 provider 调用 **0** 次、
`empty_turn(reason=no_request, actor=路人)` 记录存在，并且被诊断的正是那一行 `result: none` 的 agent 回合。

## 4. E108（P2，提示层）· 机制语义不得进入对白

**窗口证据**：19:12 陈默（`speech`，在场辅导员/班长）：“刚才的留字只生成了下一位进入者才看得到的字条…”
机制上正确（19:11 的 burn 字条现场三人 `notes_here: []`），**正因为对**，才证明它是从 affordance hint
与回执里推出来的引擎知识，而不是任何世界内的感知。诱导源是 leave_note 的 hint 本身
（“不需要先拿到纸笔”“要留一份别人能再读到…就加 persist=true”）。

**修法**：新增常量 `action_schema.NO_MECHANISM_IN_SPEECH`——“不要向他人描述引擎机制（事件、便条生命周期、
工具名称）；只说你做了什么、谁看见了什么。”只拼在 **MC 的工具说明**（`leave_note`）上。NPC 与路人的提示
（`build_npc_system_prompt` / `build_extra_system_prompt` / `build_extra_briefing`）一字未加；路人的工具面
（`EXTRA_ACTION_KINDS` 不含 `leave_note`）也不带这句。

**红→绿**：`NoMechanismInSpeechGates`（2 支）——该句出现在 `TOOLS` 的 leave_note 说明里、不出现在
`EXTRA_TOOLS`；不出现在 NPC 提示与路人提示/简报里。

## 5. 种子写法（本轮只登记，不改 `world/`）

本轮四条修法都不要求种子变化；以下两条是**新能力生效后**窗口 6 种子里会立刻起作用/需要下一轮决定的东西：

1. **`空白纸` / `可用纸笔` 是可写的纸**：判据读的是物件自己的客观描述（`world/items/空白纸.md`、
   `可用纸笔.md` 都同时含“纸”与“写”）。新写在纸上的文稿会**用掉**那一份纸——`空白纸` 在种子里代表
   “一沓”，所以第二次写就没有纸了。若 D2 需要多次成稿，种子应拆成几份纸（同窗口 4 对纸笔的处理方式），
   这是 seed 层的决定，不在本票里做。
2. **`便签本`/`值班簿` 仍走批注**：它们有正文（在 `document_defs` 里），按“目标类型分派”落在批注路径上，
   因此“在便签本上写”= 追加一条批注（可 `read 便签本` 读到），不是生成一张可递的纸。若剧情需要“从本子上
   撕一页写”，那是种子里“便签本”该不该有正文的问题，同样属于 seed 层。

## 6. 回归读数

- `python3 -m unittest discover -s harness/tests -p 'test_*.py'` → 本轮共跑 6 遍（同修订）：3 遍
  **690 OK (skipped=1)**、3 遍 **690 FAILED (failures=1)**。三次红全是**同一支**、**同一条断言**：
  `test_extra_turns_are_recorded_and_conversational` → `AssertionError: '07:02' != '07:01'`。
  这就是**票 73 §6.1 已立案的 extra 时序族**（演出的完成拍晚一分钟），**不是本轮引入**：
  - 该族历史命中率为「2 红 / 6 跑」（`reports/m1-dot3-round2-review.md`）；本轮 3/6 在其量级内。
  - **反证**：把本轮 12 支全部排除、只跑 `HistoricalFailureGates` 单类，18 跑里 4 红（2/10 + 2/8），
    身份同样是 `'07:02' != '07:01'`；该支单跑 15 次里 1 红，也是同一条。即：不跑本轮新类也照红。
  - 本轮 12 支全部是**新增**用例，且不碰 spawn 时序（E107 那支只读 trace，不碰 extra 生命周期）。
  → 因此**不宣称**“套件级全绿稳定”；间歇族本身留给票 73。
  另一条已登记间歇族（`test_silent_abandonment_auto_continues_pending_action`）本轮 0 次出现。
  本轮的单模块验收读数（无新类参与的那一层）：见下一条。
- `python3 -m unittest harness.tests.test_historical_failures`（单模块，即“先红后绿”台账本体）→
  **Ran 236 — OK**，一次通过（本轮验收读数）。
- 本轮新增 12 支；同一棵树上**不含**本轮新类的读数是 678（用 loader 直接计数），与 `reports/m1-window6`
  记录的 680 差 2——差值早于本票，见 §7.4。
- `python3 scripts/seed_lint.py` → **exit 0**（`seed lint OK`）；warning 与窗口 2–6 同族（6 条名字撞车、
  `2013年台风台账.md` 提“折痕”而 `known_to` 空、contact asymmetry 14 组），无新增。
- `runs/real-20261018T073833+0800-2019091-492642480.checkpoint.json`（22:00 检查点）→ 世界与引擎状态
  都能 `World.from_checkpoint` / `AsyncEngine.restore_checkpoint` 加载：`now=2026-03-16T22:00:00+08:00`、
  `events=5308`、`version=5308`、`persistent_notes=['note-陈默-1','note-陈默-2']`、`extras={}`（当时没有
  在场路人）、10 份会话与私人状态齐全、`trace`/`runner`/`world` 三块齐备。本轮没有新增检查点键。
- **证据绑定**：本轮改动与读数绑定到当前工作树，不是某个 commit（树在 `ea47781` 之上还带着前几轮的
  未提交改动，另有别的写者在本轮期间动了 `v4/world/`（`便签本.md`、`manifest.yml` 的 mtime 落在本轮）。
  本轮未 stage、未 commit 任何文件；便签本的改动不影响本票判据（它有正文，仍走批注路径）。

## 7. 残余与不做的事

1. **便条不进物品行**：`note-<作者>-<n>` 没有 `entity_descriptions` 的客观描述，所以 `take`/`place` 在它身上
   走便条分支（`place` 已处理，`take` 仍只认物品）。要让“地上的字条也能捡起来”，需要给便条一个描述来源，
   那是另一条裁定。
2. **`blank paper` 判据是描述层的启发式**：`WRITING_SURFACE_HINTS = ("纸", "写")` 读的是物件自己的客观
   描述。窗口 6 种子上它的判定是 `空白纸`/`可用纸笔`（对），`圆珠笔`/`蓝色兔子贴纸`（错，正确排除）。
   更硬的写法是种子里声明 `writable:`，但那要动 `world/`，本轮不做。
3. **`sleep` 与停滞提示的交互未改**：`_EXCLUDED_ACTIONS` 里 `sleep` 已排除，但本轮没有把 `sleep: true`
   的长等待从“结构空转”的统计口径里区分出来——报告层的事，报告已按 `payload.sleep` 可分辨。
4. **678 与 680 的差**：窗口 6 报告记录基线 680，本轮在同一棵工作树上用 loader 直接计数（去掉本轮 12 支）得 678；
   差值不是本轮引入（本轮 12 支全部新增）。来源未追，登记给下一窗口。
5. **E105 的“现场可见性”未改**：burn 字条仍只给后到者（W6-E2 的第 ② 条建议）。本轮只处理“写得出、
   递得出”，没有动 burn 字条的投递语义——那是 2026-09-22 裁定的世界规则，改它需要单独裁定。

## 8. 复算命令

```text
cd 契约失效时请勿喂猫/v4
python3 -m unittest harness.tests.test_historical_failures.NoteDeliveryGates
python3 -m unittest harness.tests.test_historical_failures.SleepWaitGates
python3 -m unittest harness.tests.test_historical_failures.ExtraNoRequestTurnGates
python3 -m unittest harness.tests.test_historical_failures.NoMechanismInSpeechGates
python3 -m unittest discover -s harness/tests -p 'test_*.py'
python3 scripts/seed_lint.py --verbose
```

变异对照（就地改一处→只跑对应点类→按预先存下的副本还原并核对 md5；本轮实跑的读数）：

```text
# 红①：便条不可递 + 纸不可写（give 去掉 note_here 条件；_writable_sheets 返回 []）
NoteDeliveryGates → Ran 5 … FAILED (failures=2, errors=3)

# 红②：睡眠上限不区分 sleep（limit 恒为 longest_wait_seconds）
SleepWaitGates → Ran 4 … FAILED (failures=1, errors=3)

# 红③：引擎不按 target 叫醒睡眠（删掉 _wake_waiters 的 world_event 分支）
SleepWaitGates.test_a_named_scheduled_event_wakes_a_sleeper_and_a_broadcast_does_not
  → FAILED：'2026-03-16T09:00:00+08:00' not found in ['2026-03-16T07:00:00+08:00']

# 红④：删掉“没被问”的那条 empty_turn
ExtraNoRequestTurnGates → FAILED：[] is not true（没被问的回合也必须留一行可审计记录）

# 红⑤：工具说明不带那句规则
NoMechanismInSpeechGates → FAILED：该句 not found in leave_note 说明
```
