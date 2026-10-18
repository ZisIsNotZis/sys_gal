# 83 — M1 第一窗口（07:00→14:00）引擎侧缺陷修复：物品随 extra 消失、写记录的可用性、无输出的回合

Status: fixed
Need-review: yes
Need-test-cases: yes

> 来源：票据 81（`.scratch/v4-first-day/issues/81-window1-findings.md`，run
> `real-20261018T012247+0800-1592449-689352756`，07:00→14:00，510 turns / 1757 events）。
> 票 81 只登记不修（窗口边界）；本票按优先级修 4 项，每项独立红→绿，全部登记进
> `harness/tests/test_historical_failures.py` 台账。**边界：只动 `harness/` 与
> `docs/V4-ENGINE.md`，不动 `world/`、不动 `scripts/`。**

## 结论摘要

| # | 项 | 裁定 | 代码位置 | 台账 |
|---|---|---|---|---|
| 1 | extra 消散不得破坏客观世界 | **修引擎**：回收 extra 前把背包落到它最后所在地点（`item_dropped`），replay 补齐 extra 三段 | `harness/kernel.py` `World.remove_extra` / `_visibility`、`harness/replay.py` | E84 |
| 2 | 写入动作的可发现性 | **修文案**：动作不依赖持有物，缺的是"写记录"这个说法 | `harness/action_schema.py` `_TOOL_DESCRIPTIONS`、`harness/kernel.py` `affordances` | E85 |
| 3 | NPC/extra"只叙述不施动" | **裁定：引擎无需改**（话语从不被当成动作），缺口在 `npc_agent` 导演简报；引擎侧只补可诊断性 | `harness/engine.py` `_execute_chain` | E87 |
| 4 | MC 静默丢回合 | **修记录**：零调用回合记 `empty_turn` + reason | `harness/engine.py` `_execute_chain` | E86 |

第 3 项与第 4 项共用同一处改动（`empty_turn` 诊断）：它既是第 4 项要求的"至少要有可见的失败记录"，也是第 3 项要求的"让话语不产生动作这件事在 trace 里可诊断"，且不改变世界（不惩罚、不代填动作）。第 3 项本身**没有造机制**——见 §3 的裁定与证据。

## 1. P0 — extra 消散不得破坏客观世界（E84）

### 现象（票 81 §5 的机制那一半）

```text
12:51 extra_arrived 陈阿姨 @半坡咖啡馆
12:52 陈阿姨 take 校报草稿 成功            （她的 inner：先把这份草稿收好…）
13:07 extra_removed 陈阿姨（idle）         ← 草稿随她一起离开世界
13:17 唐小岚 enter 半坡咖啡馆，nearby_items 只剩 ['裂纹马克杯']
```

复现（本工作树，实现前）：

```text
inv {'draft'} {}
after {} ['extra_arrived', 'action_started', 'action_completed', 'extra_removed']
replay FAILED: KeyError '路人甲'
```

两个缺陷叠在一起：(a) `take` 把物品从 `item_locations` 里删掉、放进 extra 的
`inventory`，`remove_extra` 只删角色，物品从此既不在任何地点也不在任何人手里，
且没有一条事件说明它去了哪里；(b) `replay_world` 从来就不重放
`extra_arrived`/`extra_removed`，所以任何带 extra 的日志一重放就在
`action_completed` 上 `KeyError`——"replay 能重建同一结果"这条根本无从谈起。

### 修法（选"落到原处"，不选"拒绝 despawn 直到空手"）

- `World.remove_extra` 在提交 `extra_removed` **之前**，把背包里的每件物品按既有
  `place` 语义放回该 extra 的最后所在地点：一件一条 `item_dropped {item, location,
  reason}`，`visible_to` = 同在地点的人（`_visibility` 显式一条），然后
  `item_locations[item] = location`、清空背包。
- 不变式因此是：**任何物品在任何时刻要么在某人手里、要么在某个地点**；不需要
  引入"物品已销毁/处于 completeness 声明状态"这种第二状态，也没有任何种子需要
  声明例外。
- `harness/replay.py` 补齐三段：`extra_arrived`（建一个 role=extra 的 actor 并
  起游标）、`extra_removed`（删人删游标）、`item_dropped`（落物，并从持有者背包
  里移除）；`action_completed` 对已离场的 actor 改为"事件成立、状态不改"，与
  kernel 的完成期守卫（票 75/take 竞争、despawn 防御性 return）对齐。
- `harness/prompt.py` 给 `item_dropped` 一句可读行（`{who} 离开时，{item} 留在了
  {location}`），否则同地的人虽然收到事件却读不到它。
- 检查点与 replay 的**格式**一字未改：没有新增 state 键、没有改 `item_locations`
  的语义、没有改 `World.checkpoint_state()` 的字段；新增的只有一种事件 kind。

### 红 → 绿

红（实现前，本工作树）：

```text
python3 -m unittest harness.tests.test_historical_failures.ExtraDespawnItemInvariantGates
FAIL: test_despawn_leaves_carried_items_at_the_last_location
      AssertionError: None != '半坡咖啡馆' : 回收 extra 不能把物品一起带走
ERROR: test_replay_rebuilds_the_same_item_location
      KeyError: '陈阿姨'（harness/replay.py:43 world.actors[event.actor]）
ERROR: test_every_prefix_keeps_the_item_somewhere
      KeyError: '陈阿姨'
Ran 3 tests — FAILED (failures=1, errors=2)
```

绿（实现后）：

```text
Ran 3 tests in 0.893s — OK
```

三条断言分别钉住：物品落回 `半坡咖啡馆` 且同地的唐小岚收到 `item_dropped`、落地的
道具重新出现在她的 `take` 候选里；`replay_world` 重建出同一个位置且事件序列逐条
相同；日志的**每个前缀**之后草稿都在某人手里或某个地点（不变式的形状）。
负向证据：把 `remove_extra` 里那段落物循环删掉，前两条立刻回到上面的红。

## 2. P0 — 写入动作的可发现性（E85）

### 诊断（先回答任务给的两个分支）

- `leave_note` **在** `affordances()` 里（`World.affordances` 无条件给），**在** agent
  工具表里（`action_schema.TOOLS`），`SCHEMAS` 只要求非空 `text`；
- 它**不依赖任何不明显的持有物**：kernel 的 `_item_duration`/`_complete` 从不查
  `inventory`，`copy_material_items` 只服务已退役的 `copy`，`纸笔`（`可用纸笔`、
  `空白纸`…）只是世界里的物件。
- 所以走的是任务里的第二个分支：动作本来就在，缺的是**说法**。真实证据：
  林瑶 08:34 用 `leave_note` 写了 400 字事实记录（turn 93，`note_left` 落地），
  08:53 却说"记录应分别写好再交，不把口头说明或留字条当成完成"，13:13 手里握着
  `可用纸笔`、affordances 里明确有 `leave_note`，`inner` 却是"纸笔在我手上，但
  没有可用工具把个人事实记录实际写入纸面；不能假称写成"。
- 根因：工具说明与 affordance 提示只把它写成"给之后进入的人留一张字条、阅后
  即焚"——一个被要求"把记录写到纸上"的角色据此判定"这不是记录"。

### 修法（不改语义、不造机制）

- `_TOOL_DESCRIPTIONS["leave_note"]` 改为先给动作的两个名字：**写记录/留字条**，
  并明说"不需要先拿到纸笔或其他持有物"；投递规则（在场者看不到正文、作者返场
  不算读者、第一位非作者进入者私下读完后烧掉、要递到手上用 `give`）仍是这一段
  唯一的完整说法。
- `World.affordances` 的 `leave_note` 提示同步成一句指针（`写记录/留字条：把文字
  留在当前地点；不需要先拿到纸笔`），不再复述整段投递规则（同一事实一处完整）。
- 动作、事件、检查点、replay 一字未改。

### 红 → 绿

红（实现前）：

```text
python3 -m unittest harness.tests.test_historical_failures.WriteRecordAffordanceGates
FAIL: test_leave_note_is_described_as_writing_a_record_with_or_without_paper
      AssertionError: '写记录' not found in '留一张字条在当前地点，写给之后进入的人。…'
Ran 2 tests — FAILED (failures=1)
```

绿（实现后）：`Ran 2 tests in 0.272s — OK`。

两条断言：**空手**与**拿着 `可用纸笔`** 两种状态下各断言一次——affordance 里有
且只有一条 `leave_note`、提示里出现"写记录"、`submit` 都成功并真的落下 `note_left`
（可用性不依赖持有物，且拒绝文案里不出现"先取纸笔"）；工具说明里出现"写记录"
与"字条"。

## 3. P1 — NPC/extra"只叙述不施动"（E87）：裁定"引擎无需改"

### 判定与证据

- **extra 的纯文本**：按 T1 计为它说的话（`npc_agent.extra_tool_calls` →
  `_extra_calls_from_reply` 在无 `tool_calls` 时合成 `speak`）。这不是本窗口的问题。
- **MC/NPC 的纯文本**：是私有心声（ticket 64，记进 `content_private`），引擎**不**
  把它当动作，也因此不产生任何世界事件——这正是要的语义。
- **食堂大妈的七次"我马上给你打"全部是真的 `speak` 调用**（12:44 #383、12:46 #391、
  12:49 #404、12:51 #411、12:53 #417、12:55 #422、12:57 #436），世界照实记了七句话，
  `item_given`/`place` 零条。她要交付的 `一份餐食` 就摆在食堂（`item_locations`），
  `give`/`take`/`place` 一直在她的工具表与 affordances 里——**引擎的表达力不是瓶颈**。
- 11:48–11:59 那段"长柄勺找不着"同理：模型断言了一个世界状态的改变（东西被挪走），
  而 `例汤` 的描写原文是"桶边搭着一把长柄勺"；引擎里没有任何机制会把一句
  `speak` 变成物品移动，所以这是**提示层**（`npc_agent` 的导演简报 / 角色卡）缺少
  "不得断言世界状态改变、只能陈述当前客观事实""承诺交付要真的调用 give"的约束。
- **引擎侧仍然要能看懂这件事**：零调用的回合以前只留一条 `result: none` 的空白行
  （见 §4），现在有一条带 reason 的 `empty_turn`；同时 E87 的负向守卫钉住"提交了
  `speak` 的回合**不是**空回合"，于是"说话"与"什么都没做"在 trace 里彻底分开。

### 红 → 绿（诚实说明）

E87 **没有自己的红**：它守的两件事（只有 `speak` 时没有 `item_given`；提交了
`speak` 的回合不被记成空回合）在修前都平凡成立。它的价值是给 E86 的新记录当
**负向对照**（防止诊断过度上报），外加把"话语不是动作"这条裁定钉成可执行断言。
台账照此登记，不把它算成一次红→绿。

```text
python3 -m unittest harness.tests.test_historical_failures.TurnWithoutActionGates
Ran 4 tests — OK
```

### 移交（提示层，超出本票边界）

1. `npc_agent` 的导演简报/角色卡：NPC 不得断言世界状态的改变（丢了/坏了/被挪走/
   已经办好了），只能陈述当前客观事实；承诺交付时必须真的调用 `give`/`place`。
2. 种子侧：食堂窗口的 `一份餐食` 已经存在，可直接交付；若希望 NPC 主动"打饭"，
   在角色卡里写清它会把 `一份餐食` 递给点餐的人。

## 4. P2 — MC 静默丢回合（E86）

### 现象

```text
real-20261018T012247 turn 414  2026-03-16T12:51:00+08:00 林瑶 (mc)
  result=none  inner=None  calls=[]  content_private='我握着纸笔，但还没有实际写成记录；…'
```

回合确实在 `agent_turns` 里，但除了一条空的 `intention` 之外没有任何说明：读者
看不出这是"模型只写了话"还是"模型什么都没返回"，也看不出这一回合的唯一世界效果
只是"发呆 1 tick"（`_execute_chain` 末尾的自动 `wait`）。同一 run 另有 5 个 NPC
空回合（08:55/08:58/11:49/12:00/13:08），形状相同。

### 修法（只加诊断）

`_execute_chain` 在零调用的回合记一条 system_turn：

```text
{"request": {"kind": "empty_turn"},
 "result": {"actor": …, "turn_id": "turn-…", "role": "mc|npc",
            "reason": "prose_only" | "no_output", "private_chars": N}}
```

`prose_only` = 模型写了正文但没提交任何工具调用；`no_output` = 什么都没返回。
它不改变世界、不惩罚角色、不让引擎替模型补动作；`check_milestones` 等消费者按
kind 过滤，新增 kind 不影响既有读数。

### 红 → 绿

红（实现前）：

```text
python3 -m unittest harness.tests.test_historical_failures.TurnWithoutActionGates
FAIL: test_a_turn_with_text_and_no_call_is_recorded_as_prose_only
      AssertionError: [] is not true : 有输出但没有调用的回合必须留下可审计记录
FAIL: test_a_turn_with_nothing_at_all_is_recorded_as_no_output
      AssertionError: [] is not true : 既无调用又无输出的回合必须留下可审计记录
```

绿（实现后）：`Ran 4 tests — OK`（含 E87 的两支）。

## 兼容性：旧检查点与 state 模式

- 本票的 state 侧改动是**零**：`World.checkpoint_state()` / `restore_checkpoint()` /
  `World.from_checkpoint()` 的字段与语义未变，没有新增键；新增的只有一种事件 kind
  （`item_dropped`）与一段 replay 分支，而 `replay_world` 只按 kind 分发。
- 手测（同一进程，本工作树）：

```text
runs/archive-20261016-attempt1/d1-am.json            # 7.3MB，12:59 的旧检查点
  World.from_checkpoint(pack.build_world(), data["world"])
  → now 2026-03-16 12:59:00+08:00, events 1535, actors 12（含 2 个 extra）, items 17
  AsyncEngine(...).restore_checkpoint(data["runner"])
  → extras {'杨大叔': ('唐小岚', 12:39), '何大爷': ('林瑶', 12:37)}（沿票 50 的 rehydrate）
  engine._despawn(<该 extra>, 'idle')
  → item_dropped + extra_removed；草稿回到该 extra 最后所在地点
  sorted(world.checkpoint_state().keys()) == sorted(data["world"].keys())  → True
```

  即：旧检查点照常加载，state 模式没有新增键，且加载后的世界也满足新的物品不变式。

- 目标模块读数：`python3 -m unittest discover -s harness/tests -p
  'test_historical_failures.py'` — 157 tests，一次 FAILED（唯一红是同一支已知
  extra 时序族），一次 OK。

## 改动文件

- `harness/kernel.py`：`World.remove_extra` 落物；`_visibility` 增 `item_dropped`；
  `affordances` 的 `leave_note` 提示改写。
- `harness/replay.py`：`extra_arrived` / `extra_removed` / `item_dropped` 三段重放；
  `action_completed` 对已离场 actor 变成"事件成立、状态不改"。
- `harness/engine.py`：`_execute_chain` 的 `empty_turn` 诊断。
- `harness/action_schema.py`：`leave_note` 的工具说明。
- `harness/prompt.py`：`item_dropped` 的可读渲染行。
- `harness/tests/test_historical_failures.py`：台账 E84/E85/E86/E87 与三个测试类
  （`ExtraDespawnItemInvariantGates`、`WriteRecordAffordanceGates`、
  `TurnWithoutActionGates`，共 9 支）。
- `docs/V4-ENGINE.md` §7.4：物品不变式、写记录动作的可用性语义、零调用回合的记录
  语义、NPC"只叙述"的裁定。
- **未动**：`world/`、`scripts/`、检查点格式。

## 验证读数（本工作树）

```text
# 本票的四组新测试
python3 -m unittest \
  harness.tests.test_historical_failures.ExtraDespawnItemInvariantGates \
  harness.tests.test_historical_failures.WriteRecordAffordanceGates \
  harness.tests.test_historical_failures.TurnWithoutActionGates
  Ran 9 tests in 1.929s — OK

# 相邻模块
python3 -m unittest harness.tests.test_action_schema harness.tests.test_proto \
  harness.tests.test_kernel harness.tests.test_world_pack
  Ran 171 tests — OK
python3 -m unittest harness.tests.test_kernel harness.tests.test_world_pack \
  harness.tests.test_checkpoint harness.tests.test_milestones harness.tests.test_engine
  Ran 198 tests — FAILED (failures=1)：已知间歇 test_silent_abandonment_auto_continues_pending_action
  （票 73/77 已登记为负载敏感 flake；单跑 OK、test_engine 模块随后连跑 3/3 OK，本票不碰该路径）

# 全量（OPENAI_MODEL=github_copilot/gpt-6-luna）
python3 -m unittest discover -s harness/tests -p 'test_*.py'
  run1（基线，本票改动前） Ran 595 tests in 83.276s — OK (skipped=1)
  run2（改动后，被并行 lane 的种子半成品打断） Ran 604 — FAILED (failures=10, errors=147)
        全部源自同一条 load_story_pack() ValueError（items 缺 Markdown 正文）
  run3（并行 lane 修好 pack、但它的新 documents/公告栏.md 尚未标 [[学生会]]）
        Ran 604 tests in 105.029s — FAILED (failures=4)：2 例属并行 lane 的种子 lint
        （该文件 1 分钟后被其作者修好，单跑 OK），2 例属已知 extra 时序族
  run4  Ran 604 tests in 137.717s — OK (skipped=1)
  run5  Ran 604 tests in 151.265s — FAILED (failures=1)：已知间歇
        test_silent_abandonment_auto_continues_pending_action（legacy `_submit` 路径，
        v4 链路径都不经过它；票 72/73/77 已登记）
  run6  Ran 604 tests in 157.716s — FAILED (failures=1)：同一支 extra 时序族
  run7  Ran 604 tests in 164.421s — OK (skipped=1)      ← 最终读数（同 run4）

python3 scripts/seed_lint.py
  seed lint OK（exit 0；只剩 name-collision / contact-asymmetry 等提示级 warning）

# 已知间歇族的定量对照（证明本票没有加入它）
python3 -m unittest harness.tests.test_historical_failures.HistoricalFailureGates.test_extra_turns_are_recorded_and_conversational ×10
  本票改动前（把 engine.py 恢复到改动前，/tmp/flakeprobe 影子树）：9 OK / 1 FAILED
  本票改动后（本工作树）：9 OK / 1 FAILED
  —— 同一支测试、同一失败形状（'07:02' != '07:01'，即票 73 §2 的在途回答与 despawn 竞态），
     改动前后发生率相同，属票 73/77/80 已登记的负载敏感族，不计入本票失败。
```

604 = 595（基线）+ 9（本票新增）。

## Comments

- **2026-10-18（窗口 1 引擎修复代理）**：四项修复落地，红绿证据如上。全量套件
  在收尾时两次被**并行 lane 的种子半成品**打断（本票边界不许动 `world/`，故不代修）：
  ① `world/manifest.yml` 新增 `空白纸`/`圆珠笔`/`便签本` 三行 `items:` 而
  `world/items/` 下还没有对应正文，`world_loader._validate_descriptions` 直接
  `ValueError`，全量 147 个 ERROR / 10 个 FAIL 全部来自 `load_story_pack()`；
  ② 该 lane 修好 pack 后，它的新 `world/documents/公告栏.md` 里 `学生会` 未标
  `[[…]]`，种子 lint 两例红（该文件 1 分钟后被其作者补好，两例单跑即绿）。
  两次都与本票的改动面（`harness/` 的 kernel/replay/engine/action_schema/prompt）
  无交集；pack 与 lint 恢复后 run4 全量 `Ran 604 — OK (skipped=1)`。

- **2026-10-18（续，第 3 项的裁定留档）**：第 3 项（NPC 只叙述不施动）的结论是
  **引擎无需改**，理由不是"改不动"而是证据：七次承诺都是真的 `speak`，世界照实
  记账；`一份餐食` 在食堂、`give` 在她的工具表里，引擎的表达力不是瓶颈。缺的是
  导演简报里的两条约束（不得断言世界状态改变；承诺交付要用 give 兑现）与种子
  侧的角色卡写法——两者都在提示层，已作为移交项 1/2 写在 §3。本票只为它加了
  "可诊断"（`empty_turn` 与 E87 的负向守卫），没有为它造任何机制。
