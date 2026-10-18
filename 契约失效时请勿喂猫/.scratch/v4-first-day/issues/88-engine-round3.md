# 88 — 引擎第三轮：持久文稿、extra 空回合诊断、按别名点名生成路人

Status: fixed
Need-review: yes
Need-test-cases: yes

> 来源：票 86（窗口 2 发现）、`reports/m1-window2-07to1530.md`（run
> `real-20261018T023423+0800-1689172-324441251`）、票 77（原语充分性：先证明旧概念
> 做不到，其次泛化旧概念，最后才谈新原语）。
> 边界：**不新增动作种类**；三项都是既有原语的参数化/泛化或诊断补强。只改
> `harness/`、`docs/` 与本票；未动 `world/`、`scripts/`、检查点格式、事件 kind
> （`note_left` / `document_read` / `item_trashed` / `stranger_asked` / `empty_turn`
> 全是既有 kind，只多带字段）。

## 0. 结论摘要

| 缺陷 | 窗口 2 的证据 | 修法（不新增原语） | 台账 / 看守 |
|---|---|---|---|
| ① "写成纸面稿并交上去"不可表达 | 12:11–15:02：21 次 `item_given` 全是纸笔在三人之间往返、0 次成稿；96 个回合（9.9%）在讨论"留条能不能算稿"（12:47/13:18/13:19/14:55） | `leave_note` 增加可选 `persist`（缺省 false，旧语义一字节不改）；persist 时便条成为可寻址实体 `note-<作者>-<序号>`，留在原地点、进知觉与 `read` 的可用目标、可重复读、可 `trash` | E89 / `PersistentNoteGates`（6 支） |
| ② extra 的零动作回合在 trace 里是空白行 | `result: none` 8 条 vs `empty_turn` 6 条：09:33 林大爷、14:13 陈师傅 零调用、`inner` 空，无任何记录 | extra 真正被问了却一个调用都没返回时，也记一条 `empty_turn`（role=extra、reason=no_output），世界不变、不惩罚 | E90 / `ExtraEmptyTurnGates`（2 支） |
| ③ 点名的角色被随机姓名替换 | 池条目是"后街糕点铺的老板娘"，13:14 生成李师傅、15:09 生成王学长；唐小岚两次到场问"李师傅或店里负责人现在在吗"，要找的人从未出现 | 池条目可声明 `aliases:`；用该别名 `speak(to=[...])` 时走同一条搭话通道（`stranger_asked` 多一个 `alias`），优先生成该条目并让别名成为它的名字；未点名仍随机取样 | E91 / `ExtraPoolAliasGates`（2 支） |

## 1. 三项语义契约（给种子作者）

### 1.1 两种便条

`leave_note` 同一个动作，两种投递语义，靠 `persist` 区分：

```json
{"name": "leave_note", "arguments": {"text": "去后街找我。", "inner": "……"}}
```
缺省（`persist` 不写或 false）= **房间留言**：留在 `locations[...].notes`，第一位非作者进入者私下读到全文后烧掉；作者返场不消费；在场的人只看见"有人留了字条"。2026-09-22 裁定，一字未改。

```json
{"name": "leave_note",
 "arguments": {"text": "审计说明：……（全文）", "persist": true, "inner": "……"}}
```
`persist: true` = **留得住的文稿**：
- 生成稳定编号 `note-<作者>-<序号>`（如 `note-陈默-1`），tool 结果会把这个编号和可执行的 `read` 调用一起交回；
- 它**留在写下的那个地点**，不烧、不会被谁读走；在场的人和之后来到这里的人的表头都有
  `字条：note-陈默-1（陈默 于 3/16(一) 14:41 留，读全文用 read）`，正文不在知觉里；
- `read note-陈默-1` 走与文书同一条私有通道（正文只给读者），**可读多次**；
- `trash note-陈默-1` 按既有 trash 语义销毁；
- **交付 = 把它留在目标地点**：世界没有"交稿"动作，也不需要——要交到某处，就走到收件方会看的地方写 `persist: true`；"交给在场的某人"仍然只有 `give`（递实物），两者不互相冒充。
- 停在原地自动读（§7.1 停留即读）不适用于便条：它是主动读的文稿，"读几次"由角色决定。

### 1.2 池条目按别名点名

```yaml
locations:
  - id: 后街糕点铺
    extras:
      - fragment: 后街糕点铺的老板娘
        aliases: [老板娘]          # 新增：可用来说出"我要找谁"的称呼
        rarity: common
        weight: 3
        knowledge_notes: 熟客都认得我……
```
- 角色 `speak(to=["老板娘"])`（开放地点、正常音量，与 `to=["陌生人"]` 同一条搭话通道）→ 引擎优先取该条目、生成这个角色，并让 `老板娘` 成为它的名字（`extra_arrived 老板娘`），它的身份描写也含这个称呼；
- 别名已被在场者占用时退回随机名，但身份描写里写"（人称「老板娘」）"；未点名（`["陌生人"]`）时仍走既有 `sample_extra` 随机取样；
- 生命周期机制不变：idle despawn、E84 落物、一对话一角色、销毁后零记忆。

## 2. 改了什么（逐处）

**A. `leave_note persist`**（`harness/kernel.py`、`harness/replay.py`、`harness/engine.py`、`harness/action_schema.py`）

- `World.persistent_notes: {id: {id, author, location, text, left_at}}` + `_note_serial`；id 在 `submit`
  时分配（`action_started`、`note_left` 与 tool 结果三者同号），因此 `_complete` 与
  `_interaction_payload` 不会各造一个编号。
- `submit` 完成时：physically 留在原地点（不是 `locations[].notes`）。
- 知觉：`poll()` / `scene_perception()` 新增 `notes_here`（id/author/left_at，**无正文**）；
  `harness/prompt.py` 把它渲染成表头的一行"字条：……读全文用 read"。
- 读：`World.readable_body(entity)` 是唯一入口（文书走 `document_defs`，便条走自己的 text，
  `PERSISTENT_NOTE_READING_SECONDS = 30`）；`_available_readables` / `available_now` /
  `_item_duration` / `_interaction_payload` / `_read_rejection` 都走它，所以
  `read` 的候选里有它、读两次都成功、异地读给出"这张字条留在别处"。
- `_stay_reads` 跳过非文书实体（便条只能主动读）。
- `trash`：接受"在当前地点的便条"，`item_trashed` 现在带 `item`，replay 由 `item_trashed`
  的重放移除它（普通物品的 trash 重放仍是既有的老缺口，本票不扩）。
- tool 结果：`_leave_note_yield(..., persist, note_id)` 两种回执；persist 回执给出编号与
  `{"name": "read", "arguments": {"item": "note-…"}}`，并说明"他们也都读得到；要当面递东西仍用 give"。
- `action_schema`：`leave_note` 的 schema 变为 `required: [text]` + 可选 `persist: boolean`；
  工具说明保留 E85 的"写记录/留字条""不需要先拿到纸笔"，补上 persist 的语义与
  "交付=留在对方会看的那张桌上"。

**B. extra 的 `empty_turn`**（`harness/engine.py` `_extra_turn`）

```python
if needs_response and not intention_calls and result == "none":
    self.trace.record_system({"kind": "empty_turn"},
        {"actor": name, "role": "extra", "reason": "no_output", "private_chars": 0})
```
纯文本回复按 T1 会合成 `speak`，所以这一 state 只覆盖"什么也没返回"；不是模型回合时
（`needs_response` false）不记；不改世界、不惩罚角色。

**C. 池别名**（`harness/kernel.py`、`harness/engine.py`）

- `World.pool_entry_for_alias(location, name)`：唯一的别名匹配点（`aliases` 可为列表或字符串）。
- `_canonicalize_speech`：名字解析不到人、但命中本地点池别名且可搭话（开放地点、正常音量）时，
  把它记进 `alias_hits`，与 `["陌生人"]` 一样不当作"未知收件人"；耳语/封闭地点里被点名则结构化拒绝
  （说明未出场的人听不到）。
- `submit` 的 speak 分支：`to` 里有 `陌生人` 或别名时都发 `stranger_asked`，别名时 payload 多一个 `alias`。
- `engine._spawn_extra(..., alias=...)`：命中别名取该条目，别名未被占用就直接用它当名字，
  否则退回 `generate_stranger_name()` 并把"（人称「…」）"写进身份描写；`_handle_extras`
  的两处调用与 `_pending_spawns`（同 tick 未落地）都带上 alias。

**D. 文档**

- `docs/V4-ENGINE.md` 新增 **§7.5 两种便条、extra 的诊断与点名生成（ticket 88）**：两种便条的
  语义、"交付=留在目标地点"、编号稳定性与检查点增量、`empty_turn` 覆盖、别名生成与生命周期不变、
  回归位置。
- `docs/V4-AGENT-INTERFACE.md`：§2 `leave_note` 行（两种语义 + 编号 + 可重复读 + 交付方式）、
  §2 `speak` 行（可点该地点登记的称呼）、§2.3 第三条（补 persist）、§3 表头（新增"字条"行）、
  §5 事件模板表（`leave_note persist` 与 `read` 的便条形态）。
- `docs/V4-CAST.md` §1：池条目可写 `aliases:`，点名生成、未点名仍随机取样。

## 3. 红 → 绿

测试：`harness/tests/test_historical_failures.py` 三个新类（10 支）＋台账 E89/E90/E91。

**红（把三处改动逐一还原到改前行为的隔离副本 `/tmp/eng88red`，其余文件逐字节相同）**

```text
# 还原：action_schema 的 leave_note 回到 _schema(text=…)（无 persist 参数）；
#       engine._extra_turn 删掉 empty_turn 诊断；
#       kernel._canonicalize_speech 的池别名分支短路为 False。
python3 -m unittest ...PersistentNoteGates ...ExtraEmptyTurnGates ...ExtraPoolAliasGates
ERROR: test_a_persistent_note_can_be_read_twice_with_the_same_text
    ActionRejected: leave_note: got an unexpected argument 'persist'; expected one of: text.
ERROR: test_replay_rebuilds_the_same_persistent_note_id          （同上）
ERROR: test_a_checkpoint_keeps_the_note_and_never_reuses_its_id  （同上）
ERROR: test_an_old_checkpoint_without_notes_still_loads          （同上）
FAIL: test_a_zero_action_extra_turn_is_recorded_with_its_reason
    AssertionError: [] is not true : 零动作的 extra 回合必须留下可审计记录
FAIL: test_naming_a_pool_alias_spawns_that_entry_under_that_name
    AssertionError: 0 != 1        （没有任何 extra 到场：`老板娘` 被当成未知收件人拒绝）
Ran 10 tests — FAILED (failures=2, errors=4, skipped=1)
```

两个负向守卫在红状态下照旧绿（`test_a_default_note_still_burns_after_its_first_reader`、
`test_an_unnamed_ask_still_samples_the_pool`、`test_an_answering_extra_turn_is_not_an_empty_turn`）——
它们钉的是"旧语义不被改动"，正是该有的形状。

**绿（本工作树）**

```text
python3 -m unittest harness.tests.test_historical_failures.PersistentNoteGates \
  harness.tests.test_historical_failures.ExtraEmptyTurnGates \
  harness.tests.test_historical_failures.ExtraPoolAliasGates -v
Ran 10 tests in 1.879s — OK     （连跑 10 轮 10/10 OK）

python3 -m unittest harness.tests.test_historical_failures
Ran 171 tests in 58.358s — OK
```

三支核心断言（票面要求的三支）：

1. `test_a_persistent_note_can_be_read_twice_with_the_same_text`：同一张便条读两次都成功且正文
   逐字相同（两条 `document_read`）、读后仍在原处；他人到场也读得到（表头 `notes_here` 有编号、
   `read` 成功）。**反夹具同时钉住** `locations["男生宿舍"].notes == []`（没退化成会烧掉的字条）。
2. `test_a_default_note_still_burns_after_its_first_reader`：不带 persist 的字条仍由第一位非作者
   进入者烧掉，`persistent_notes` 为空，且不产生可寻址的 `document_read`。
3. `test_replay_rebuilds_the_same_persistent_note_id`：`replay_world` 用事件里的 id+text 重建同一张
   便条并可再读；`trash` 之后的世界与 replay 之后的世界都读不到它。
   另两支补兼容：检查点带着便条与编号计数器往返（恢复后新写的一张不撞旧号）；缺
   `persistent_notes`/`next_note_serial` 的旧检查点照常加载。

## 4. 兼容与验证

```text
# 旧检查点（v4-checkpoint-2，窗口 1 的 d1-am）仍能恢复
python3 - <<'PY'
cp = json.loads(Path('runs/archive-20261016-attempt1/d1-am.json').read_text())
world = World.from_checkpoint(load_story_pack().build_world(), cp['world'])
PY
  → now 2026-03-16T12:59:00+08:00, events 1535, persistent_notes {}, note_serial 1
  （同样断言已固化为 PersistentNoteGates.test_the_archived_d1_am_checkpoint_still_loads）

python3 -m unittest harness.tests.test_world_pack harness.tests.test_kernel \
  harness.tests.test_action_schema harness.tests.test_engine
Ran 183 tests in 5.042s — OK

OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py'
  run1 Ran 618 tests in 79.081s — FAILED (failures=1)：test_extra_turns_are_recorded_and_conversational
  run2 Ran 618 tests in 88.375s — OK (skipped=1)      ← 全绿读数
  run3 Ran 618 tests in 101.430s — OK (skipped=1)     ← 全绿读数
  run4 Ran 618 tests in 82.029s — FAILED (failures=1)：
        test_silent_abandonment_auto_continues_pending_action
  （618 = 窗口 2 基线 608 + 本票 10；两条红都是任务书点名的已知间歇族，见下）

python3 scripts/seed_lint.py    exit 0（seed lint OK，仅提示级 warning）
```

两条间歇族的复核（本会话实跑）：

- `test_extra_turns_are_recorded_and_conversational` 单跑 20 轮：13 绿 7 红；红有两种形状，同一根因：extra 答话落地晚一个 tick（`07:02 != 07:01`），或第二问追上还没完成的
  第一次 `speak`（busy 拒绝）。两条都由 `_extra_loop` 的 provider 排队时序决定，本票在它们之间
  没有任何代码路径（`_spawn_extra` 的取样与命名在 `alias=None` 时逐行等价，`empty_turn` 只多记一条
  system_turn）。
- `test_silent_abandonment_auto_continues_pending_action` 单跑 10 轮：6 红 4 绿；红时的事件序是
  `b 的 speak` 先于 `a 的 move`（a 还没忙，打断无从生效），属 asyncio 启动顺序，与本票无交集。

## 5. 未做而认为需要的项

1. **"交给在场的某某" 仍只有 `give` 递实物**。本票让它不再需要冒充成稿（persist 文稿能被反复读、
   能留在指定地点），但"把一份文字直接塞到在场某人手里"依旧不可表达。若剧情必须"当面递交文字"，
   最小泛化是把 `give` 的目标物类从 `items:` 扩到便条 id（正文随 `item_given` 私有投递给收件人），
   而不是新增动作——需要人裁定，因为那会改变 `give` 的语义边界（票 86 §1 的另一个候选方向）。
2. **`take` 的候选仍会列出文书**（票 86 §5，票 81 §1 未修）。窗口 2 的 14 条拒绝文案里
   "这里能拿的："出现 `公告栏`、`学生会审计通知`。这是 `_takeable_here`/`_fallback_next_actions`
   的过滤问题，不在本票三条之内。
3. **在飞决策释放（`inflight_released`）没有补偿**（票 86 §3）。12 条记账可见，但那一回合的决策
   永久消失；是否应重新入队要人裁定。
4. **extra 一回合两个动作仍整轮 `rejected`**（票 86 §4）：判定对，但 extra 的系统提示缺"一回合
   只说一句"的约束（5 次里 4 次是 extra）。属提示层，未改。
5. **服务岗 NPC 不在饭点被唤醒 / 广播 `world_event` 没有 `target`**（票 86 §7）：引擎侧与种子侧
   各有一条路，需分诊。
6. **未验证的部分**：本票只证明世界与 trace 层的语义与诊断，不证明模型会用 `persist: true` 或
   会点名 `老板娘`。要证明后者需要一次 provider-backed 运行并按 `AGENTS.md` 的运行后分析协议
   人读轨迹（建议下一窗口专看 15:00 后街糕点铺段与 12:00–15:00 学生会办公室的"交说明"段）。
   E84 的 `item_dropped` 路径在真实轨迹上仍未被触发（窗口 2 零尝试），继续标未验证。

## 6. 改动文件

- `harness/kernel.py`：`persistent_notes`/`next_note_serial`（检查点增量）、`readable_body`、
  `available_now`、`_available_readables`、`_item_duration`（read/trash）、`_read_rejection`、
  `_stay_reads`、`_complete`（leave_note/trash）、`_interaction_payload`、`submit`（note id、
  `stranger_asked.alias`）、`_next_note_id`、`_notes_here`、`poll`/`scene_perception` 的
  `notes_here`、`affordances`（trash 可选便条、leave_note 提示）、`pool_entry_for_alias`、
  `_canonicalize_speech`（别名）。
- `harness/engine.py`：`_tool_yield`（read 走 `readable_body`、leave_note 传 persist/id）、
  `_leave_note_yield`（第二种回执）、`_extra_turn` 的 `empty_turn`、`_spawn_extra` 的别名选择、
  `_handle_extras`/`_pending_spawns` 的 alias 传递。
- `harness/replay.py`：`note_left persist` 重建、`item_trashed` 移除便条。
- `harness/prompt.py`：表头"字条"行、`note_left` 的 persist 文案。
- `harness/action_schema.py`：`leave_note` schema + 工具说明。
- `harness/tests/test_historical_failures.py`：台账 E89/E90/E91 + `PersistentNoteGates`（6）、
  `ExtraEmptyTurnGates`（2）、`ExtraPoolAliasGates`（2）。
- `docs/V4-ENGINE.md`（§7.5）、`docs/V4-AGENT-INTERFACE.md`（§2 两行、§2.3、§3 表头、§5 模板）、
  `docs/V4-CAST.md`（§1 池别名）。
- **未动**：`world/`、`scripts/`、事件 kind 集合、检查点格式版本、`World.ACTIONS`/`SCHEMAS` 的动作集合。
