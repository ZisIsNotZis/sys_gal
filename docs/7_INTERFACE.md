# INTERFACE — 组件之间与对外的契约

只写"两边必须一致的东西"：种子文件、动词表、运行工件、命令行入口、错误语义。实现与内部机制在 `docs/8_DETAIL.md`；跑门的命令与工具链惯例在 `docs/9_IMPLEMENTATION.md`。

## EXPLICIT

### `seed.yml` 的形状

顶层认七个键：

| 键 | 含义 |
| --- | --- |
| `story` | 这支故事的标识（人读） |
| `date` | 世界日期（ISO 日期字符串）；有一眼里的日期，也决定过了午夜是否翻日 |
| `start_clock` | 开局时钟，从当天 00:00 起的分钟数 |
| `places` / `people` / `objects` | 三个实体区段 |
| `schedule` | 到点触发的世界效果列表，每项 `{at, effect}` |

每个实体行只允许下面列出的字段；**多写一个字段就是加载期错误**（`ValueError`，不静默丢弃）：

| 区段 | 允许的字段 | 默认与说明 |
| --- | --- | --- |
| `places` | `id`、`name`、`kind`、`parent`、`prose`、`state`、`aliases` | `kind` 默认 `place`；`parent` 缺省表示根地点 |
| `people` | `id`、`name`、`kind`、`parent`、`prose`、`identity`、`knows`、`believes`、`reads_hands`、`state`、`aliases` | `kind` 默认 `person`；`identity` 是第一人称的自我描述（进系统提示）；`knows` 是实体 id 列表；`believes` 是 `{about, says}` 列表；`reads_hands` 是 `{字形: 实体}`（谁认得出这种字） |
| `objects` | `id`、`name`、`kind`、`parent`、`prose`、`state`、`aliases` | `kind` 默认 `object` |

`state` 的键是库声明的物性（如 `marks`、`portable`、`locked`、`closed`、`door`）；lint 要求每个用到的状态键都有渲染模板。实体的 `parent` 必须解析得到，父子关系成环或指向不存在的父都是加载期错误。顶层目前没有白名单：代码只读上面七个键，其余键不报错也不生效。

**当前边界**：`schedule.effect` 没有加载期形状约束（这是登记过的加固项，人确认过不为脚本花太多时间）；现在由 `scripts/anti_cheat.py` 的第二检代偿——效果种类必须在 `EFFECTS` 里、不带 `actor`/`say`/`do`、`place` 必须真实存在。

### `schedule` 与效果的种类

排程到点执行的东西必须是物理或制度，不能是"命运让某事发生"。`at` 是分钟数；`effect.kind` 必须是 `library/institutions.py` 的 `EFFECTS` 之一：

| 效果 | 参数 | 做什么 |
| --- | --- | --- |
| `arrive` | `place`、`station` | 车到站，在场的人感到停了一下，并记下站名 |
| `stops` | `place` | 终点站：熄火、灯暗，给世界打上"已停"的旗标 |
| `close` | `place` | 到点关门并上锁，看得见的人听见门与锁的响 |
| `open` | `place` | 到点开门、摘锁 |
| `pickup_due` | `who`、`place` | 到点只提醒登记上的那个人来领东西 |
| `post` | `item`、`place` | 把一张纸贴到某处；看见的人只知道贴了张纸，内容要读 |
| `deliver` | `item`、`place` | 到点的送货：货车卸下东西，附近的人听见动静 |
| `stamp` | `item`、`station`、`place`（后两者可省） | 到点有人在登记本上落一行（印刷体） |
| `clean` | `place` | 到点清扫/收拾，是这一班的收尾，不归某个人的决定 |
| `remind` | `who`、`about`、`place`（后两者可省） | 到点提醒许下承诺的人；只说那件事本身 |

每个效果只准产生 P9 的原子效果；它不能替任何角色做决定。

### 动词表

工具表由 `library/concepts.py` 的 `_CONCEPTS` / `DOCS` / `PARAMS` 生成，**代码是权威**。表中"给模型看的一句话"就是模型收到的工具说明；`target` 等指称参数由引擎的 P10 解析成世界里的实体；带"（可选）"的参数可以缺省。行数与 `DOCS` 的键一一对应。

| 动词 | 给模型看的一句话 | 参数 | 声明它的故事（`used_by`） |
| --- | --- | --- | --- |
| `announce` | 对同一处的所有人高声说一句；看不看得见都听得见，传不到别的屋子 | `text` | s5_wedding、s6_parcel_station |
| `call` | 对着一部接通的电话说话：另一头听得到声音，两头互相看不见 | `text` | s4_night_shop、s5_wedding、s6_parcel_station |
| `copy` | 用复写纸把一份纸上的字复写下来（要空白纸） | `target` | s2_borrow_note、s4_night_shop、s7_campus_12d |
| `count` | 数一数眼前的东西有几份；封着口的地方数不到 | `target` | s4_night_shop、s5_wedding、s6_parcel_station |
| `erase` | 用橡皮擦掉铅笔写的字，会留下擦痕 | `target` | s2_borrow_note、s7_campus_12d |
| `examine` | 把眼前的东西看到能看清细节的程度（不读内容） | `target` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `give` | 把手里的东西递给眼前的某个人 | `target`、`to` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `hail` | 冲一个你说不出名字的人喊话，只能靠他穿什么、长什么样来指他 | `who`、`text` | s5_wedding、s6_parcel_station |
| `impound` | 以制度身份把一件东西收走，并在登记本上记下一行 | `target` | s3_night_market、s4_night_shop |
| `knock` | 敲某间屋子的门；里面的人会听见 | `target` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `lock` | 用钥匙把门或容器锁上 | `target` | s4_night_shop、s6_parcel_station |
| `move` | 走到另一个地方 | `target` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `open` | 打开容器或一扇门 | `target` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `place` | 把手里的东西放下（放到某处或某个容器里） | `target`、`to` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `promise` | 答应别人一件事，并说定到哪一刻；到点你会被提醒 | `to`、`text`、`at` | s4_night_shop、s6_parcel_station |
| `read` | 读出纸上的字；只有你自己知道内容 | `target` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `recognize` | 盯着纸上的字迹看：你能认出是谁的字吗 | `target` | s2_borrow_note、s7_campus_12d |
| `retell` | 把听来的话转述出去；每经一张嘴，话就短一截 | `to`（可选）、`text`、`about`（可选） | s5_wedding、s6_parcel_station |
| `shift` | 在交接记录上落一行，并把钥匙交给接班的人 | `target`、`to`、`key`（可选） | s4_night_shop、s6_parcel_station |
| `sign` | 在签到本这类登记簿上记下一行；只有写下的才算数 | `target`、`text` | s5_wedding、s6_parcel_station |
| `speak` | 说一句话：不带 to 就是当众说，在场的人都听得见；带 to 就只对那个人说，旁人只看见你们在低声说话 | `to`（可选）、`text` | s1_last_bus、s2_borrow_note、s3_night_market、s5_wedding、s7_campus_12d |
| `take` | 把东西拿到手里 | `target` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `touch` | 碰一下，什么也不会改变 | `target` | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `unlock` | 用钥匙打开某把锁 | `target` | s2_borrow_note、s4_night_shop、s6_parcel_station、s7_campus_12d |
| `wait` | 等一会儿，什么也不做 | — | s1_last_bus、s2_borrow_note、s7_campus_12d |
| `write` | 在某张纸上添一笔字（用你手里的笔） | `target`、`with`（可选）、`text` | s2_borrow_note、s3_night_market、s4_night_shop、s5_wedding、s7_campus_12d |

`used_by` 是声明，不等于目录已经存在：当前树里只有 `s1_last_bus`…`s5_wedding` 五支故事有种子；`s6_parcel_station` 与 `s7_campus_12d` 目前只是声明。

### 运行工件契约

一次运行留下四件原始材料，每一个工件都是证据，不是缓存：

| 路 | 四件 | 各是什么 |
| --- | --- | --- |
| 脚本局 | `<路>.md` / `<路>.context.md` / `<路>.json` / `<路>.events.json` | 故事视图、逐回合上下文、事件账 + 摘要、事件账（按事件逐行） |
| 模型局 | `agent-<时间>-<pid>-<标签>/transcript.md` / `context.md` / `run.json` / `events.jsonl` | 同上四件的角色，目录一局一个，绝不覆盖 |

- `transcript.md`：故事视图，带 `[世界]` / `[脚本]` / `[角色]` 标记；脚本动作只证明"物理上做得到"，不代表角色的意愿。
- `context.md`：每个动作前这个角色拿到的**全部**上下文，加上模型的原始工具调用；抬头按这一局真实情况生成（脚本局说脚本不读上下文，模型局说读了）。没有它的一局回答不了"他当时知道什么"，不算证据。
- `events.jsonl` / `.events.json`：可重放的事件账，一行（或一项）一个事件，每件带应用后的世界摘要。
- `run.json`：模型局的运行记录 `{summary, spend, items, digest}`；`spend` 是这一局自己的账（授权、模型、上限、tokens、价钱），没有授权就不该有钱的账。脚本局的 `<路>.json` 是 `{events, summary}`。

**打包形态**：事实的家是 `runs/<story>-<路>.jsonl.zst`，格式 `v5-run-pack-1`，一行一条记录：先一条 `pack` 元记录（`story`、`unit`、`dir`、`files[{name, role, bytes, sha256}]`，`role` 是 `context` / `events` / `run` / `transcript`），再逐件全文记录。压缩**不裁剪内容**，展开回来与原始四件逐字节相同。

`pack_trajectory.py check` 判四类失败，各自点名故事与路：原始四件没有工件（未打包）、工件比原始文件旧（跑完忘了打包）、展开后与原文不逐字节一致（含原始件缺件与多出未打包件）、运行没有 `context.md`（不是证据）。

### 命令行入口

| 入口 | 用法 | 产出 |
| --- | --- | --- |
| 故事脚本局 | `python3 -m stories.<story>.run [路…]` | 该故事每条路四件原始材料，写进 `stories/<story>/runs/`；不给路时用这支故事的默认路径 |
| 故事模型局 | `python3 -m stories.<story>.agent_run [model] [每角色回合数]` | 唯一目录 `stories/<story>/runs/agent-…/` 四件；当前只有 `s1_last_bus` 与 `s2_borrow_note` 有这一层，其余故事只有脚本局 |
| 结构检查 | `python3 scripts/v5_lint.py [--strict]` | 状态键渲染、孤儿概念、引擎盲区、种子严格性、脚本动词的机械检查；`--strict` 让孤儿概念也失败 |
| 反作弊三检 | `python3 scripts/anti_cheat.py [--verbose]` | 无具名祈使句、无天意事件、结局不唯一；`--verbose` 打印每条路走到哪个结局 |
| 轨迹打包 | `python3 scripts/pack_trajectory.py pack\|check\|unpack [路径]` | `pack` 幂等打包；`check` 四类失败非零退出；`unpack` 展开并逐件自校验 |

### 错误语义

- **拒绝回执**：`Receipt` 是 `{ok, what, reason, hints, texts, note, event, interrupted}`。拒绝时 `ok=false`，`reason` 是"为什么不成"，`hints` 是"眼前有什么可用"；世界状态一个原子都不改，账本里落一条 `kind="refused"` 的事件（`note` 带 `reason`、`hints`、`requested`、`digest_after`）。
- **指称失败也是可行动的回执**：解析不到时给"这里没有一样东西叫「…」"+ 眼前能看见的清单；知道但不在眼前时给"你知道它，但它不在眼前"；某个动词自己的前提不成立时给它自己的可行清单（例如写：手上能写的、眼前能写的）。
- **没有登记的动词**是 `KeyError`，不是拒绝回执；工具表由库生成，模型看不到未登记的动词。
- **`DecisionParseError`** 是模型工具调用无法解析：它被记成**一条失败的回合**（`verb="-"`、`ok=false`、`reason="模型的工具调用无法解析"`，原始调用保留在 `raw`），整局继续。provider 的重试预算耗尽则是终局的 `ProviderError`，不会伪装成一条失败回合。
- **被打断**不是"没成"：动作在飞时前提被抽走（期限到了、门关了、东西没了），回执 `interrupted=true`，账本落一条 `kind="interrupted"` 的事件；本人知道没做完，在场的人只看见动作停在半路。
- **世界终点**由排程的 `stops` 效果表达：给世界打上 `stopped` 旗标，并让在场的人听到"终点站到了，司机熄了火"这一句；`advance_idle` 见到旗标就停。结局文字由故事从世界事实拼出，不由引擎分配目标。

## CONFIRMED

- **种子的严格性只到实体行为止**：`schedule.effect` 的字段白名单还没做，因为人确认过不为脚本花太多时间；代偿是反作弊第二检。把它提升为加载期报错是登记过的加固项。

## INFERRED

- **四件工件按文件名判角色**（我读 `pack_trajectory.py` 的 `role_of` 得到的推论）：`context.md`/`*.context.md` → context，`events.jsonl`/`*.events.json` → events，`run.json`/`*.json` → run，其余 → transcript。所以一局里如果多放一个别的 `.json`，它会被当成 run 件打包；命名本身就是契约的一部分。
- **脚本局与模型局的四件不是同一种目录形状**（推的）：脚本局平铺在 `runs/` 里以路名为前缀，模型局一局一个子目录。打包器把两者都归成"一个 unit"，因此"路"这个名字对脚本局是前缀、对模型局是目录名。
