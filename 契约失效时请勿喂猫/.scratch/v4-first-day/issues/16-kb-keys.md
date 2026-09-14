# Ticket 16-kb-keys: KB 行改为 key 集 + 文本提及 + 世界设定入 system prompt

Status: done

## Issue

ticket 15 之后 PO 复审：`person/location/item/concept/memory` 那套「类型化字段」
既要做匹配、又要做展示、又要做定位，模型还在 run 里臆造 `person:林瑶` 这类空值字段。
PO 提出把 KB 行改成**纯 key 集**：key 同时是定位符与唤起词，匹配退化为文本子串；
`todo/reminder` 不是业务逻辑而是**特殊的提及机制**，应当变成 key；`self` 不必存在；
不向角色显示任何魔法 id。另：一般世界设定（地点/走法/时间尺度）应进 system prompt，
具体概念仍走 keyed 行。

## 决策（PO 2026-09-14）

- 行模型 = `{keys: frozenset[str], desc, status}`；**key 集即身份**（无 id）。
- 文本 key ≥2 字；`的/之`/空白/标点归一化后**双向子串**匹配；一行可多 key。
- 指令 key（ASCII 机制层）：`!always`（无条件按间隔重提，上限 12）、
  `!at=M/D(周X) HH:MM`（到点提醒 + force-interrupt，通知后自动 close）。
- 身份 = 每角色恰一行 key 含自己名字；引擎拒绝 close 该行。`self` 字段废除。
- 定位顺序：精确 key 集 → 唯一超集（成功但 tool 结果附 warning）→ 多义（报错列候选）→ 无匹配。
- keys 不可改；改 key = close + open（写进 update_memory 工具描述）。
- `recall` 改收 `keys`（关键词），`!always` 可列出所有常提行。
- `concepts:` 展开为**一行**：`keys=[name,*aliases]`，`desc=定义 + "\n我：" + memory`
  （定义与私人回忆必须合并——两行会同 key 冲突）。name 等于已有实体 id 时并入该行。
- 提取文本（替代旧提及集）= 本回合世界消息去掉 #knowledge 块 + 上一回合 tool 结果正文；
  **不扫 #knowledge 自身**（防自我触发），不扫全局文本（防串味）。
- system prompt = 逐字前言 + 每世界静态 primer（`world_primer`，v4 清理版）。

## 改动文件

- `harness/kb.py`：整体重写（key 集行模型、`hits`/`matched_span`、指令 key、fuzzy 定位、
  snapshot/from_snapshot、旧 `fields` 向下兼容）。
- `harness/engine.py`：`_knowledge_lines` 改用提及文本；`_flashback_query` 用同一 matcher；
  `update_memory`/`recall` 新参数；`_reminder_scan`/`close_scheduled` 走 `!at`；
  记录上一回合 tool 文本（入快照）。
- `harness/world_loader.py`：`_validate_kb`/`_expand_entity_rows`/`_expand_concept_rows` 改 key 集；
  `world_primer` 重写为 v4 版（去掉 observe/ask_stranger/inner/"5 分钟"）；补 `_as_int/_as_float/_as_str`。
- `harness/action_schema.py`：`update_memory`(keys)、`recall`(keys) schema + 描述。
- `harness/natural_agent.py` / `harness/npc_agent.py`：system prompt 追加 `world_primer`；修正 agent 返回标注。
- `harness/real_run.py` / `harness/resume_run.py`：传入 primer；env 解析改用 `tuning.env_int/env_float`。
- `harness/tuning.py`：新增 `env_int`/`env_float`。
- `world/manifest.yml`：`kb:` 全部迁移为 `keys:`（含别名进身份行、todo→`!always`、reminder→`!at=`）。
- `harness/tests/*`：kb/world_pack/engine/proto/historical 全部按新模型重写。
- `docs/V4-AGENT-INTERFACE.md`：§0/§1/§2/§3/§4/§5/§6/§6.1/§7 同步。
- 顺带：完成 ticket 14 遗留的 `ask_stranger` → `ask` 重命名（docs 早已是 `ask`，代码未跟上）。

## 校验结果

- `python3 -m unittest discover -s harness/tests -p 'test_*.py'` → **297 passed, 1 skipped**
- `python3 scripts/seed_lint.py --verbose` → seed lint OK
- `python3 -m harness.dry_run` → 种子排程排空到 22:00（events=17, turns=40）
- 直查：`flashback(陈默,"红色哨子")` 命中「定义+私人回忆」合并行；`"老街坊"` 经别名 key 命中
  `老家属院`；`"陈默的爸爸"` 经归一化命中 `陈默` 行；`"不存在的东西"` 为空；
  `flashback(林瑶,"听见的哭声")` 为空（不越权）。

## 已知边界

- 旧 checkpoint 的 KB 快照用 `fields` 写法仍可 `from_snapshot`（合并到同 key 集的多行会丢后者）；
  新种子一律 `keys:`。
- `fields:` 兼容层保留，待后续清理。
- 世界 primer 现在会列出全部地点与走法（公共设定）；若发现地点不应人人皆知，再收紧。
- 行渲染会列出该行全部 key（多别名时较长）；如嫌吵可改为只显示首个 key（待观察）。

## Comments

- 2026-09-14 agent (pi, 当前会话模型): 实现完成；297 passed / lint OK / dry_run 到端点。
  PO 期间外出，按 "go / ok / main" 三项授权执行；`ask` 重命名为顺带收口 ticket 14 遗留。
