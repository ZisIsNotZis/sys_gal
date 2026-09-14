# Ticket 17: P0–P2 cleanups + live validation of ticket 16

Status: done

## Issue

ticket 16 收尾时列出的 P0–P2 遗留。PO 指令：全做，并与 ticket 16 一起用一次
真实运行验证。

## 切片与结果

### P0.1 v4 resume（正确性缺口）
`resume_run.py` 用的是 v3 路径（`make_persistent_agent` / `CharacterSession` /
`make_provider_gm` LLM judge），而 `real_run.py` 是 v4（原生 tool calls、无 judge）。
恢复一个 v4 checkpoint 会用错协议。
**修**：resume 改用 `V4Session.from_snapshot` + `make_persistent_agent_v4` /
`make_npc_agent_v4`，传 `world_primer`、`kb_seeds`、`director_brief`；删除 GM。
3 个 resume 测试绿。

### P0.2 `_init_kb` 覆盖恢复的记事本
`restore_checkpoint()` 先跑，`_run()` 里的 `_init_kb()` 后跑并无条件用种子行覆盖
——恢复后运行中记的行会静默丢失。
**修**：跳过已在 `self._kb` 里的角色。新增回归测试
`test_restored_kb_is_not_clobbered_by_seed_rows`。

### P1.1 悬空引用建模
- 新增远程地点 `老家属院`（`remote: true`，当日不可步行到达，`primer: false`）。
- `红色哨子` 落位 `老家属院`（原 `location: null`，案件 fact 指向空）；
- 新增物品 `蓝色兔子雨伞`（老家属院，known_to 陈默）、`蓝色兔子贴纸`（林瑶随身）。

### P1.2 Tier-A 关系补注册
`陈默爸`（别名 陈默的爸爸）、`食堂大妈的丈夫`、`食堂大妈的儿子`、
`唐小岚的前同事`、`唐小岚的前老板` —— 各带 known_to + memory。

### P2.1 `fields:` 兼容层退役
种子与 `update_memory` 只接受 key 集；`fields` 仅在 `from_snapshot`（旧 checkpoint）
保留。测试改为「种子拒绝 fields / 旧快照仍可恢复」。

### P2.2 `agent_view` 显示运行时的工具清单
`Trace` 记录 `tools`（静态清单，一次写入），`render_chatml_view` 优先用它；
旧 trace 才回退到当前代码声明。含回归测试。

### P2.3 行渲染收敛
`[<指令> <首个 key> +N]: desc` —— 标签取 key 列表中第一个（概念名在前），
其余以 `+N` 计数，避免六别名行占满一行；任何单个 key 仍可定位（模糊定位）。

### P2.4 私有地点不进公共 primer
地点支持 `primer: false`（`陈默家`、`老家属院` 已标）与 `known_to`
（`陈默家` 仅 陈默/陈默妈 有 KB 行）。

### P2.5 名字检查加强
新增 `阿X` 与「名+亲属后缀」（陈默爸）模式；加函数词守卫避免
`会催的妈`/`都是我妈` 这类过度捕获。lint 仍全绿。

## 运行验证（ticket 16 + 17 同验）

两次真实 provider 运行（`gh/gpt-5.6-luna` 网关，07:00→09:30，wall < 1 分钟）：

- `runs/real-20260914T084209+0800-91826-834152268.json`（57→63 回合，199 事件）
- `runs/real-20260914T084620+0800-106602-197386236.json`（57 回合，183 事件）

**ticket 16 机制确认可用**（第一次运行）：
- 陈默 `flashback("老家属院")` → 合并行（定义+私人回忆）+ 实体行；
- 林瑶 `flashback("蓝色兔子贴纸")` → 新物品行 + 她的 memory；
- `!always` / `!at=` 行按期出现并渲染为 `[!always 签名人]` / `[!at=3/16(周一) 08:30 上午班]`；
- `reminder_due` 触发 1 次（未挂起动作，故无 interrupt）；
- system prompt 全角色 2607 字符、均含 primer、均以逐字前言开头（无私有泄漏）；
- 零 agent_error。

**暴露并修掉的两个真问题**：
1. `老家属院` 渲染**两次**（location 自动行 + concept 行）——合并逻辑只在 key 集
   完全相等时触发，别名破坏了它。修：概念名命中实体行时**就地扩充**该行的 key 并
   追加 memory。第二次运行确认 0 重复。
2. `update_memory` 的**工具描述仍是旧的 `fields:/id/kinds` 文案**（ticket 16 那次
   描述编辑漏掉了，只改了 schema），模型因此写出 `item:2013年台风台账` 这种 key。
   修：描述改为 key 集语义并明说不带前缀；新增守卫测试
   `test_memory_tool_descriptions_match_the_key_set_schema`。第二次运行确认
   0 个带前缀 key，模型写出 `["2013年外借记录导出件","时间戳不一致"]` 这类正确形状。

**第二次运行确认 token 级行为**：`flashback("2013年台风台账")` → 台账行；
`recall(["签名人","借出记录","案子期限"])` → 两条 `!always` 行 + 模型自己的笔记行
（模糊匹配按设计命中）。

## 遗留观察（未修，非本 ticket 范围）

- `text` 目标用昵称被拒（`unknown actor: 妈妈`）：affordances 每回合已列出
  `text {target: 陈默妈}`，属模型合规问题；如需可在拒绝文案里再列一次可及目标。
- 名字检查仍是模式匹配：无后缀的纯昵称（阿强已覆盖，但形如「小李子」）可能漏。

## Comments

- 2026-09-14 agent (pi, 当前会话模型): P0–P2 全部实现；测试 303 passed/1 skipped；
  seed lint OK；dry_run 到端点；两次真实运行验证 ticket 16+17，发现并修复上述 2 个真问题。
