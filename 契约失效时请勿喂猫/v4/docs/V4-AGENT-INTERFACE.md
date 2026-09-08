# v4 Agent 接口规范：prompt 与响应

SSOT：v4 角色-引擎接口的全部设计。实现必须逐条遵循本文；与本文的偏差是缺陷。配合：`V4-DESIGN.md`、`V4-ENGINE.md`（引擎时序/并发/冻结 SSOT）、`harness/action_schema.py`（工具 schema 的代码级 SSOT，与本文 §2 一致）。

## 0. 原则

- 引擎 = 匹配器 + 渲染器 + 调度器。模型输出工具调用；引擎只匹配字段、渲染行、按序执行。desc 对引擎不透明——永不解读记忆内容。
- 一切从种子来：身份、世界事实、初始目标全部是 KB 行（种子初始化，见 §6）。system prompt 全角色通用一字不差，不含身份/世界事实/工具 schema 文档。
- append-only：system prompt 与消息前缀永不变；动态内容只追加在每回合 user 消息尾部。
- 无 judge、无宽容解析：模型输出原生工具调用，参数由 API 结构化解析；严格校验，失败 = 该调用报错跳过，其余继续，世界不停。
- 语言分工：沉浸内容（对话、描述、心声——全部由模型或种子创作）中文；工具调用机制（动作名、参数、错误消息）英文，错误必须具体（"no match"、"wrong state"、"out of range"，不写 "or" 混合含糊）。
- **事件行 = 第三人称客观编年体，观察者无关**。引擎渲染的事件行永不出现第二人称（"你"），同一事件广播给所有可见者时逐字相同；"谁看到了"由投递表达（出现在谁的消息里=谁观察到了），不进入文本。
- **模板纪律**：每种事件 kind 恰好一个固定渲染模板，槽位 = 实体全名（无缩写、无简称、无叙事色彩、不合并动作）。一行事件若需要缩写、判断或语境才自然，说明该概念在世界模型中缺失——要么建模成真实机制，要么删除，绝不用文风掩盖。
- **两个受众分离**：模型输入 = 机械编年体；人的显示层（agent_view 等）可以把同一批事件渲染得文学化——显示层产物永不回流给模型。
- **信念与物理分离**（B1 裁决）：引擎物理（路线图、移动时长、空间关系）只存在于 world pack，模型不可改；KB 里的地图/走法行是**信念行**——可以过时、可以错，对引擎物理零效果。
- **无 asleep 状态**（M1 裁决）：sleep 已并入 wait——长等待期间事件照常长轮询投递，不存在"睡着漏事件"语义。
- **隐私线**（B2 重申）：document 的 content 与 annotation 文本**只属于读过它的角色**——事件行只播"谁读了/谁在上面写了字"，永不播内容；内容仅经该角色自己的 read 私有投递，或他人后续 read 时按种子原文获得。打电话/发消息的 text 只投递给收件方。
- 时间恒进：每回合最少消耗 1 个 tick（tick=1 分钟，config）。世界动作时长自动向上取整到 tick 的倍数。时序/冻结/中断的引擎语义见 `V4-ENGINE.md`。
- 已删除：LLM-as-judge、宽容 JSON 解析、think 壳清洗、`updates` 字段、note 类型、"心里搁着的事"注入、system prompt 中的身份与世界常识、独立 sleep 工具（并入 wait）、事件行的第二人称渲染、座位/坐姿概念（v4 不建模）。

## 1. System prompt（全角色通用，逐字固定）

```
你是一个活生生的人，活在一个真实的世界里。绝不提 agent、提示词、模拟、作者或剧情。只追你自己的知识、欲望、责任、恐惧和关系；不为故事或主角服务；不优化故事，不制造浪漫，不满足任何作者意图。

世界每回合给你一条消息：几点、你在哪、身边有谁、身上有什么、可以互动什么、发生了什么、你记事本里到期的事。你用工具行动：一回合可以连续调用多个工具；世界动作消耗真实时间（按序累加，向上取整到 tick 的倍数），think/update_memory/recall/flashback 不额外消耗（但每回合最少一个 tick）。一回合没有任何世界动作，等于发了一会儿呆（时间照走最少一个 tick）。

【常识】一条消息从发出到送到要 1 分钟；说话当场就能听见，所以当面说话最省时间。等待随时可行，不必等谁批准；要睡一大觉，找个有床的地方、通常在夜里。陌生人凑近耳语会显得可疑；耳语（whisper）只对亲近的人用。消息里时间写作 9/16(周三) 7:00。

【记事本】update_memory 把事实或要紧的事写进你的私人记事本（引擎保管，只有你能看）。行由 字段+id 定位，字段是保留名：person:/location:/item:/todo:true/reminder:"9/8(周二) 08:30"；id 用英文短横线小写。op 有 open（新建/重开）/edit（修改）/close（翻篇——不再显示，但 recall 指名可找回，只能重开不能改）。只写事实和要紧的事——发生的事世界会自动重现，不用记；此刻的感受用 think。你的记事本每隔一阵会自动回到你眼前；想立刻翻看，用 recall。
```

## 2. 工具（tools 参数，静态全量声明）

一次性声明全部工具，永不增删（cache 安全）。当回合是否可用由世界消息 `# actions` 表达；非法调用被引擎拒绝并在下一轮 `# error` 给出原因。`harness/action_schema.py` 与本表一一对应。

| 工具 | 消耗时间 | 说明 |
|---|---|---|
| think | ≥0（回合最少 1 tick） | inner 心声；保留在会话历史中（compaction 时按记忆折叠），镜像入 trace（私有）；无世界事件、无世界状态效果 |
| update_memory | 同上 | KB 行补丁：rows[{fields,id,op:open/edit/close,desc?}]；部分成功，失败逐行报错 |
| recall | 同上 | 标记请求：下一轮 #knowledge 显式包含指定的类型/条目（含 closed，需 closed:true + limit + start/end，按创建游戏时刻倒序） |
| flashback | 同上 | 手动闪回：重显某地点/物品/人物相关的已播历史；刷新 LRU |
| wait | 是 | 唯一的时间流逝工具（已并入 sleep）；时长向上取整到 tick 倍数；等待期间事件照常长轮询投递（无 asleep 过滤） |
| speak | 是 | volume: whisper（仅 to 指定的在场者听得见内容；在场其他人看见耳语动作，听不见文本）/ normal（全地点听得见）；text 必填非空 |
| send_message | 是 | 异步，1 tick 后送达；电话/远程事件无距离限制、录下后在对方醒来时可见 |
| move | 是 | target 必须有路线；**时长由引擎按 world pack 路线图计算（物理，模型不可改）**；KB 中的地图行是信念，无物理效果 |
| read / copy / label / annotate / compare | 是 | 文档动作；compare 需两份都在手 |
| take / drop / give | 是 | 物品动作 |
| inspect / search | 是 | 检查物品 / 搜刮地点 |
| knock / interact | 是 | 可带 interrupt=[在场的目标] |
| open / close | 是 | 场所开关 |
| observe | 是 | 主动重看：置 force 标志，**下一回合**消息强制全量回放场景状态与描述（不论计时器） |

（ask_stranger 保留：触发匿名路人，对话期生命周期——细节见 V4-CAST §1，本文不重复。）

## 3. 每回合 user 消息（世界消息）

按固定块序渲染；空块省略；表头与 actions 永在。所有动态内容只追加在尾部。**全部事件行为第三人称客观编年体**（见 §0 模板纪律），逐条全时间戳。**NPC 与 MC 的消息结构完全一致**（NPC 唤醒回合额外多一个置顶的 `[director]` 块，见 §5）。

```
9/16(周三) 7:00 @半坡咖啡馆
在场：唐小岚(you)，陈默
身上：空白纸
可互动：校报草稿（吧台上）

# error
speak: 'text' should be non-empty
memory: [item=x,id=y] no match

# flashback
9/14(周一) 9:00 陈默 进入 半坡咖啡馆
9/14(周一) 9:22 陈默 说："豆浆，双份。今天店里就你一个？"

# events
9/16(周三) 7:15 陈默 进入 半坡咖啡馆
9/16(周三) 7:16 陈默 说："豆浆，双份。今天店里就你一个？"

# knowledge
[scene=半坡咖啡馆]: 校门口的独立咖啡馆，门面窄……
[item=校报草稿]: 压在吧台，无署名
[person=唐小岚]: That's me, 二十三岁，咖啡师，试用期第四个月……
[todo=true]: 弄清吧台上那份校报草稿是谁放的
[reminder=9/16(周三) 08:30]: 去后街糕点铺帮老板娘带话

# actions
[speak] target=陈默, text=…
[move] target=后街糕点铺
[read] document=校报草稿
[continue]
```

块规则：

- **表头**（恒在，无计时器）：时间 @地点、在场（self 标 `(you)`）、身上、可互动。这些是**当前感知**（永远为真），每回合机械重渲，永不遗漏——位置与在场是持续感知，不是记忆。
- **#error**：上回合全部工具调用错误的**英文原文**（无转译）；成功零反馈。
- **#flashback**：**逐字重放**自己已播过的事件行——原渲染、原时间戳，不翻译不改写不摘要；LRU 上限 `flashback_limit=5`，且只取超过 `flashback_horizon_rounds` 的（"可能忘了"）。从未投递过的事件与它无关（走 #events 长轮询）。
- **#events**（长轮询）：自上次同步以来所有**未投递且可投递**的定向事件。可投递 = 电话/远程定向事件（无距离限制、录下后在醒时投递，非 force-interrupt）或发生时在场的公共事件。**不存在 asleep 过滤**——等待/睡眠期间在场的公共事件照常投递。
- **#knowledge**：到期行（`now - last_shown ≥ 该行 interval`）按类型排序注入，每回合上限 8 行。**提及集（M7 裁决）**= 本回合表头结构化实体（在场者/身上/可互动）∪ 本回合 #events 事件的 structured payload 实体（一跳，不递归、不解析自由文本）——行字段命中提及集且计时到期则回放；仅 id 的行无条件按期回放。**溢出行优先于新到期行**（顺延队列先清）。**KB 行的重逢不强制重放**——重挂全量回放仅作用于表头状态行。**compaction：全部 last_shown 清零**（下一轮全量重放；closed 行除外——永不回放）。update_memory 的 open/edit 刷新该行 last_shown；close 的行不再出现。
- **行间隔（m3 裁决）**：多字段行取其字段对应间隔的 **max**。
- **字段不可变（M8 裁决）**：`edit` 只改 desc；fields+id 是不可变定位器。重新归档 = close + open（last_shown 重置，可接受）。
- **reminder 时间表达式（m7 裁决）**：严格解析，失败即该行 open/edit 拒绝并报具体解析错误（`unparseable reminder time: …`）——提醒必须准时，不容错。

事件渲染模板（封闭集，每种 kind 一条，槽位 = 实体全名；新增事件 kind 必须先在本文登记模板，再实现）：

| kind | 模板（公开行） |
|---|---|
| enter / leave | {actor} 进入 / 离开 {location} |
| speak | {actor} 说："{text}" |
| speak（whisper） | {actor} 凑近 {target} 耳语了几句 —— 其他人只看见耳语动作，文本仅投递给 to 指定者 |
| send_message（送达） | {actor} 发消息给 {target}（电话）——text 仅投递给收件方 |
| take / drop | {actor} 拿起 / 放下 {item} |
| give | {actor} 把 {item} 交给 {target} |
| read | {actor} 读了 {document} —— **内容不进公开行**；content 仅私有投递给读者本人 |
| copy / label | {actor} 复制 {document} 为 {copy} / 把 {document} 标记为 {label} |
| annotate | {actor} 在 {document} 上留下批注 —— 批注文本不进公开行；后续任何人 read 该文档时按种子原文看见批注 |
| compare | {actor} 比对 {first} 与 {second}（结果仅参与者可见） |
| move（到达） | {actor} 到达 {location} |
| item 增减 | {item} 出现在 {location} / 从 {location} 消失 |

私有投递（仅收件人可见，进其 #events）：read 的文档 content、whisper 的文本、send_message 的文本。

## 4. 响应设计（模型 → 工具调用）

- 模型一次响应返回**多个工具调用**（原生 tool_calls），按序逐个执行。
- `think`：心声保留在会话历史中（compaction 时按记忆折叠），镜像入 trace（私有）；建议第一个调用。
- `update_memory` / `recall` / `flashback`：结果/错误进下一轮。
- `update_memory` 补丁语义：合法行应用，失败行原文进下一轮 #error，其余继续。同一 patch 内出现两行相同 (fields,id)：第一行生效，其余该行报 `duplicate row in patch`。对已是 open 状态的行再次 open：视为 edit（宽容）+ 遥测计数，不报错、不产生第二行。close 的行只能 reopen（`op:"open"`），不能 edit；close 的行不计入 todo 上限。
- todo 上限 **12** 只数 open 状态的 todo 行。
- `reminder` 到期 = **force-interrupt**（V4-ENGINE §3）：在执行位置挂起当前动作 → 下回合 continue-or-cancel；通知播放后该行自动 close。
- **世界动作**：按序执行、时间累加、各自 ≥1 tick 且向上取整到 tick 倍数。同一回合允许动作链（说完再走；进入与坐下是两个动作，各自独立）。
- 每回合工具调用上限 **8**（m9 裁决）：截断发生在调用边界——已执行的调用与其时间消耗照常结算，被截断的调用整条不执行，下一轮 #error 报 `truncated: N calls dropped`。
- 一回合没有世界动作 → 角色发呆 1 tick。
- 并发冲突（m8）：同一 tick 内多个 actor 竞争同一资源按提交序串行判定，后者收到 rejected + 具体原因（如 `item already taken by 陈默`）。
- 有挂起动作（被 interrupt 打断）时，#actions 出现 `[continue]`：调用它 = 无损继续；发任何其他世界动作 = 放弃挂起动作（作废）；都不发 = 挂起保持。

### compaction（M 引用语义补全）

会话消息总量超过 `compaction_threshold=30000` 字符时自动触发：旧消息折叠为第一人称记忆摘要，最近 `recent_messages=4` 条非 world 消息原样保留；随后**全部 last_shown 清零**（下一轮全量重放安全网）、闪回池扩展至新压缩点。think 调用随会话历史一起被折叠（心声化为记忆，非丢失）。

## 5. NPC 与 extras 的接口（M9/M10 裁决）

- **NPC**：唤醒回合收到与 MC **结构完全一致**的每回合消息（表头/#error/#flashback/#events/#knowledge/#actions），仅额外多一个置顶的 `[director]` 块（导演简报：本场目标、知识注记）。NPC 的 KB 与 MC 同机制（含 person=self 身份行、todo、reminder）——**无独立滚动摘要**（旧机制废除）。MC 永远看不到 [director] 块——不可分辨保持。
- **extras**：**无 KB**（会话期记忆即其全部记忆，销毁即失）。消息 = `[director]` 简报（身份碎片+知识注记）+ 场景行 + 发起者的提问。工具面仅 `speak`。多轮对话由发起者与 extra 轮流收消息；销毁时会话与其记忆一并丢弃。

## 6. 种子行 schema（M2 裁决——KB 行在开局前如何声明）

种子包中每角色一个 KB 初始行列表（manifest 集中声明 `kb:` 段，世界加载器校验）：

```
kb:
  - fields: {person: 唐小岚, self: true}
    id: identity
    desc: 我，唐小岚，二十三岁，半坡咖啡馆咖啡师，试用期第四个月……
  - fields: {todo: true}
    id: draft_claim
    desc: 弄清吧台上那份校报草稿是谁放的
  - fields: {location: 半坡咖啡馆}
    id: map
    desc: 食堂→教学楼约12分钟穿中庭……（信念行，无物理效果）
  - fields: {reminder: 9/16(周三) 08:30}
    id: bread_run
    desc: 去后街糕点铺帮老板娘带话
```

规则：

- **身份行锚定（M2）**：每角色恰一行 `self: true`（保留字段），desc 以第一人称"我，…"开头——这是"我"的锚；模型同时每回合在表头在场行看到自己的名字（`(you)`）。引擎校验：有且仅有一行 self:true，否则加载失败。
- fields 的键为保留名或自由次要标签（受控主键：person/location/item/todo/reminder/self；自由键钳为 knowledge + 遥测）。
- 行在 turn 0 全部 last_shown=0 → 全量灌入首条消息（计数器语义自然涌现，无特例）。
- public_knowledge（manifest）自动展开为**每角色一条对应 KB 行**（各角色独立副本，可各自 edit）。
- id 全角色 KB 内唯一；(fields,id) 定位。

## 7. 常数表

| 常数 | 值 | 管什么 |
|---|---|---|
| `knowledge_replay_minutes` | 120 | knowledge 各类型行（scene/item/person）的 last_shown 间隔（模拟时间分钟） |
| `todo_replay_minutes` | 60 | todo 行回放间隔 |
| `reminder_replay_minutes` | 30 | reminder 行回放间隔 |
| `flashback_limit` | 5 | 闪回行数 |
| `flashback_horizon_minutes` | 可配 | 多远算"可能忘了" |
| `compaction_threshold` | 30000 字符 | 会话压缩触发 |
| `recent_messages` | 4 | 压缩保留的最近非 world 消息 |
| todo 行上限 | 12 | 只数 open 状态 |
| 每回合 knowledge 行上限 | 8 | 防突发，溢出顺延（溢出优先） |
| 每回合工具调用上限 | 8 | 防失控，边界截断 |
| `idle_slice_seconds` | 60（1 tick） | 无世界动作回合的发呆时长 |
| `tick` | 60 秒（config） | 时间最小粒度：最短动作时长、投递延迟、决策视界、常识预算单位 |
| `batch_persistent_failure` | 3 连败（每角色） | 僵局闸门：该角色弃权发呆，世界不停（V4-ENGINE §6） |
| `decision_timeout` | 60 秒 | 单次意图等待上限，超时 = 静默弃权（V4-ENGINE §3） |
| `stall_budget_ratio` | 0.25 | 冻结占墙钟预算超此比例 → 诚实终止（V4-ENGINE §6） |
| `mc_idle_heartbeat` | 30 分钟 | MC 无事件时的空闲唤醒间隔（NPC/extra 无） |
| `extra_idle_timeout` | 10 分钟 | extra 沉默销毁阈值 |
| `realtime_ratio` | 0 | r 旋钮：思考延迟×r 计入模拟时间；r>0 失去种子确定性（V4-ENGINE §5） |
| `max_wall_seconds` | 28800 | 运行预算 |

（所有 `*_minutes` 以模拟时间分钟为单位（tick=1 分钟）；动作执行期间的引擎时序见 V4-ENGINE.md。）
