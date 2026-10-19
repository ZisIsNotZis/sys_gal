# 113 — 票 112 的四条 P0/P2 修法 + 工件持久化

Status: fixed
Need-review: yes
Need-test-cases: landed（见 §5）

> 输入：票 112（D1 第三次全天验收发现）与 `reports/m1-day1-acceptance3.md` §6 的
> “进 D2 前只做四件事”，外加一次证据丢失（票 112 引用的工件已不在磁盘上）。
> 范围：E1 纸的容量、E2 收件人在岗、E7/E8 两条 D2 判据、工件持久化。
> 不在范围：E4 老周无住处、E5 班长消失、E9 妈妈“没有第二户可敲”、E10–E16 纹理项。

## 0. 一句话

四处修法都是**补机制**而不是补台词：一沓纸有了张数、值班 npc 有了上岗的排程事实、
两条 D2 判据改成“只有真发生才 PASS”，轨迹工件不再只是本地文件。
套件 `Ran 707 tests ... OK (skipped=2)`，`scripts` 38 支全绿，`seed_lint` 全绿，
`artifacts.py check` 55 件全部核对通过。

---

## 1. E1（P0，engine/seed）纸是单件耗材 → 一件纸有张数

**观察（票 112 §E1）**：18:00 投放的 `说明用纸` 只有 1 件；18:25 陈默取走，
18:27 `leave_note on=说明用纸` 把整张纸写成 `note-陈默-28`；18:42 起班长、林瑶室友、
林瑶、陈默、**辅导员自己** 依次 `take 说明用纸/空白纸` 失败（“已经被拿走或销毁”），
19:00–22:00 收件档零交件。

**根因**：世界是“一个 id = 一样东西”，票 110 的应对是加 id 数（六个纸 id 各一件）+
补货，可一键写掉一个 id；而真正的缺口是“沓”**没有容量**。

**修法**：

- `items:` 行可声明 `sheets: N`（正整数，`world_loader._validate` 装载期校验；
  不写 = 一张，旧语义完全不变）。
- `world.item_sheets` 是**余数**（世界状态，随检查点走）。提交 `leave_note on=<纸>` 时
  把 `sheets_left` 写进 action payload，所以回执、replay、中途检查点看到同一个数。
- `_complete` 写一张少一张：余数 > 0 → 那张纸仍是纸（位置与持有关系都不动，别人还能
  接着写）；余数到 0 → 那张纸才从此变成这份文稿（旧行为）。
- 种子按“沓/叠/包”的描写给容量：`空白纸` 12、`可用纸笔` 12、`一叠空白纸` 20、
  `一包打印纸` 50、`草稿纸` 12、`说明用纸` 24。
- **顺带修掉一处动作—结果误解**：`_leave_note_yield` 原来对任何 `on` 都回
  “作为一条批注追加进《空白纸》”——写在纸上也说成批注。现在按目标类型分派：批注
  只说批注，纸张路径说清“在你手里、还剩几张、要交出去用 `give`”。

**验收（机械）**：`harness/tests/test_item_sheets.py` —— 写一张少一张且纸仍可用、
最后一张归入文稿、不写 sheets 保持旧语义、手上那沓不动、检查点与 replay 同余数、
回执说余数、六个纸 id 都声明容量、装载期拒绝非法容量。
**验收（真工件，未做）**：票 112 §6 的口径是 D2 08:00 缺件清点当次至少三人各写成
一份、`take` 拒绝 ≤10；这一条要靠 M1.9/D2 的重跑读真轨迹，本轮未跑 provider。

## 2. E2（P0，engine/seed）收件人在收件档期间不在自己的办公室

**观察（票 112 §E2）**：19:00–22:00 辅导员在其办公室 0 回合；19:29 起收件档“没有任何
已核实的纸源”，20:00 后“没有一个能收的人”。而 18:30/19:00 两条通知、两处知识行都
写着“十九点到二十一点我在办公室”。

**根因**：制度面齐全，但世界没有任何机制把她放到那个岗位上——排程效果只有
open/close/add_item/add_document/move_item/remove_item，没有 actor-move。

**修法**：

- 排程效果新增 `place_actor {id, location}`：陈述“这段时间这个 npc 在这个岗位上”的
  制度事实。它不替角色做主——她说什么、还去不去别处仍由她自己的回合决定。
- `world_loader` 装载期只允许 `role: npc`；把玩家角色放到某处是替他做主，是剧本而不是
  世界，所以直接大声失败。
- `apply_world_effects` 是运行与 replay 的同一入口，重建一致。
- 种子：`counselor_evening_intake`（3/16 19:00）加 `place_actor 辅导员 → 辅导员办公室`。

**验收（机械）**：同文件的 `PlaceActorTests`（排程到点把 npc 放到岗位、玩家角色一步
不动、replay 同位置、装载期拒绝放玩家角色）。
**验收（真工件，未做）**：19:00–21:00 辅导员在其办公室有回合、`d1-三份个人说明` ≥3——
同样要靠重跑。

## 3. 种子补齐 3/17 08:00 的缺件清点

三条通知/两处知识行都写着“明早八点的缺件清点在同一个地方当面做”，可排程里**没有**
这个八点的事件：一个声明了却没有机制的事实。新增 `statement_count_d2`（3/17 08:00，
点名辅导员与四名经手人）并把辅导员放到岗位上；不替任何学生到场、写稿或交件。

## 4. E7/E8（P2，checker）两条 D2 判据没有区分力

**观察**：`d2-恋爱私人对话` 只要求“同场互有发言”——D1 已有 65 条，全部是任务性对话；
`d2-审计说明提交` 只要发言里同时出现“说明”与“提交”——“我还没提交说明”也 PASS。

**修法（判据层，`scripts/check_milestones.py`）**：

- `d2-恋爱私人对话`：那条发言的 `heard` 只有对方（说这话时在场没有第三个人）+
  正文不含案子上的词（`D2_TASK_WORDS`）+ 双方各至少一条。
- `d2-审计说明提交`：本人 `leave_note` 写出、正文读作《个人情况说明／情况说明／
  书面说明》的文稿，本人 `item_given` 交到辅导员手上，且在 08:00 清点档内
  （`≤09:00`）；迟到只在证据行报为迟到，不计入；别人的稿子转交不算。
- 口径写进 `docs/V4-STORY-MILESTONES.md` 的第 2 天条目（判据的 SSOT）。

**验收**：`scripts/test_check_milestones_d2_anchors.py` 九支——D1 形态（任务性同场
对话／“我没提交说明”）必须 FAIL，真私人对话与真交付物必须 PASS，迟到不算，别人的
稿子不算，核对记录不算。

## 5. 工件持久化：证据不能只是一个本地文件

**观察**：票 112 与 `reports/m1-day1-acceptance3.md` 引用 `runs/real-20261018T113143…json`
与 `runs/day1-acceptance3-md5-before.txt`——两者在磁盘上都不存在；`checkpoints/d1-am.json`
也不在。根因：`.gitignore` 用 `契约失效时请勿喂猫/**/runs/` 把整个目录挡在 git 外面，
被挡住之后它们仍然只是本地文件，一次清理/换机就没有了；而报告与票据继续引用它们，
等于所有读数不可复核（违反 `AGENTS.md` 的“保留完整轨迹、运行后复盘”）。

**修法**：

- `.gitignore` 改成**只按大小挡**（`runs/*.json`、`checkpoints/*.json`），同一目录里的
  小文本（门禁读数、md5 快照）照常入库；删掉整目录那条规则。
- `v4/artifacts.tsv` 是声明：路径 / 字节数 / sha256 / 第二处持久位置。
- `v4/scripts/artifacts.py`：`archive` 复制到第二处位置并登记，`check` 逐条核对
  （在不在、字节数、sha256），`--strict` 把“还有未归档工件”也算失败。
- 第二处持久位置默认 `/home/z/hf/vibe-artifacts/v4`（另一块物理盘），`$V4_ARTIFACT_ARCHIVE`
  可覆盖。本轮已把磁盘上现存的 55 件（321 MB）全部归档并核对通过。
- `v4/runs/README.md` 写清规则与每次运行结束时的动作。

**验收**：`scripts/test_artifacts.py` 五支（归档后 check 通过／唯一副本丢失即失败／
内容变了哈希即失败／未归档只在 strict 下失败／空声明不算通过）；真跑
`artifacts.py check` → `artifacts OK：55 件声明全部核对通过`。

## 6. 改动清单

| 文件 | 改动 |
| --- | --- |
| `harness/kernel.py` | `World.item_sheets`（参数/序列化/恢复）、`_consume_sheet`、`_complete` 的 leave_note 分支、`sheets_left` 进 action/interaction payload、`trash`/`remove_item` 清余数、`place_actor` 效果 |
| `harness/engine.py` | `_leave_note_yield` 按目标类型分派 + 余数回执；`_tool_yield` 取 `sheets_left` |
| `harness/replay.py` | `note_left` 的纸张路径按 `sheets_left` 重建余数 |
| `harness/world_loader.py` | `sheets` 装载期校验、`item_sheets` 注入 World、`place_actor` 校验（只许 npc） |
| `world/manifest.yml` | 六个纸 id 的 `sheets`；`counselor_evening_intake` 的 `place_actor`；新增 `statement_count_d2` |
| `scripts/check_milestones.py` | `D2_TASK_WORDS`/`D2_STATEMENT_RECIPIENT`/`D2_STATEMENT_DUE`；重写两条 D2 判据 |
| `scripts/artifacts.py`（新） | 工件声明/归档/核对 |
| `scripts/test_artifacts.py`（新） | 五支夹具 |
| `scripts/test_check_milestones_d2_anchors.py`（新） | 九支正反向夹具 |
| `harness/tests/test_item_sheets.py`（新） | 13 支 |
| `harness/tests/test_historical_failures.py` | `NoteDeliveryGates` 按新契约校准（纸不再“写满即消失”，改为张数减少且仍可写；清掉排程以隔离场景） |
| `docs/V4-ENGINE.md` §7.11 | 本轮裁定 |
| `docs/V4-AGENT-INTERFACE.md` | `leave_note on=<纸>` 的容量语义 |
| `docs/V4-STORY-MILESTONES.md` | 第 2 天两条判据的口径 |
| `.gitignore` / `v4/artifacts.tsv` / `v4/runs/README.md` | 工件持久化 |

## 7. 未做 / 留给后续

- **真工件验收**（E1 的“三人同写”、E2 的“19:00–21:00 有回合”）需要一次 provider
  重跑；本轮没有跑，所以这两条只有机械夹具，没有真轨迹读数。**因此 M1.9（重跑 D1）
  是 D2 之前的必需项。**
- E4/E5/E9/E10–E16 未处理（见票 112）。
- `seed_lint` 没有“`sheets` 只能写在纸类道具上”的检查：写错对象（例如给一支笔声明
  张数）目前不会被挡。属可加的机械检查，见票 112 §E13 一类的 lint 债。

## Comments

- 2026-10-19：`NoteDeliveryGates` 的四支旧断言（“那张纸已经写满了字，不再是空白纸”）
  与“写一张少一张”直接冲突。改法是保留它守护的性质（文稿是真实体、可读、可递、
  重放同 id 同手、缺的那一张不会复活），把“纸被整件吞掉”换成“张数减少 1 且纸仍可写”，
  并在夹具里清掉排程——否则 `advance()` 会把 19:00 的值班排程也走一遍，把辅导员从
  测试摆好的场景里挪走（本轮 E2 带来的新语义）。
- 2026-10-19：`scripts/artifacts.py` 的 `read_manifest`/`write_manifest` 一开始用
  `path: Path = MANIFEST` 作默认参数，默认值在定义时绑定，于是测试里替换 `ROOT` 之后
  仍然写进真实仓库的 `artifacts.tsv`。改为 `path=None` 再取模块级 `MANIFEST`；被污染
  的那份声明已删除，真实归档是干净的 55 件。
