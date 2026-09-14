# Ticket 18: 联系人系统 + 名字解析 + [[引用]]标记

Status: done

## Issue

真实运行反复出现 `text {"target":"妈妈"} → unknown actor: 妈妈`。根因：陈默的
KB 里**没有一行关于他母亲**（known_contacts 只存种子内部 id，模型永远看不到；
"妈妈" 只存在于描述散文里）。PO 裁决五点（2026-09-14）：

1. 所有取名字的参数共用一套**模糊名字解析**（精确优先，同 KB 规则）。
2. **联系人 = `!contact` KB 行**：模型自己维护；听到名字 ≠ 联系人；种子给初始联系人。
3. 同一套中文 prior（的/之/空白/标点归一化，双向子串）。
4. KB 命名本就私人：陈默记他母亲就是「妈妈」。
5. 种子散文里**每一个**人/地/物/概念引用都写成 `[[名字]]`，脚本按作用域检查可解析。

## 实现

- **`resolve_name(query, candidates)`**（kb.py）：精确相等优先（不 warning）→
  模糊双向子串 → 恰一命中：采用 + teaching note → 多义：拒绝并列候选 →
  无命中：拒绝并列出可用项。
- **`!contact` 指令 key**；manifest `contacts:` 段展开为带 `!contact` 的 KB 行
  （keys = 正式名 + 私称，desc = 通讯录行）。`known_contacts` 种子字段废除。
- **kernel**：`submit()` 在校验前调用 `_canonicalize_persons`（text/give.target、
  speak.to），昵称在提交点改写为正式 id——校验与落账事件都见正式名。
  `ActorState` 新增 `contact_aliases`（昵称→正式 id），入 checkpoint。
- **engine**：`_sync_contacts` 每回合从 open `!contact` 行重导 known_contacts
  （首个 key = 正式名，其余 = 私称）；`build_world` 用种子 contacts 初始化。
- **`[[name]]` 标记（T5）**：`strip_refs()` 在所有作者串入口剥离（concept
  desc/memory、kb desc、文档 content、`DescriptionCatalog`（world primer 与
  实体描述的单一读点）、character 四段、scheduled notice、extras knowledge_notes、
  system.facts）；`ref_names()` 供 lint。
- **lint 双向检查**：① 每个 `[[x]]` 必须在**每个收文角色**的 key 中可解析
  （角色本人→自己；地点/物品/文档→持有者；concept→known_to∪memory；notice→target；
  facts→所有人）；② 未标记的「名字样」token 是错误。两条互补，缺一不可。
  解析规则：generic 概念人人可解析；公 cast 成员作为「公众人物」可解析；
  generic 无行；`[[]]` 为零时提示跑 mark_seed。
- **`scripts/mark_seed.py`**：自动加标记（最长优先、sentinel 防嵌套、幂等、
  YAML 值加引号防 flow-sequence）。本次给种子加了 303 个标记。

## 修掉的真 bug

- `_raw_duration`（校验路径）不可变参 mutation：`dict(x)["to"]=…` 是无效副本——
  解析移到 `submit()` 的 `_canonicalize_persons`。
- **昵称解析到昵称自身**：known_contacts 只含正式名，`妈妈` 解析"成功"返回
  `妈妈`，`_actor` 仍拒。修：`contact_aliases` 昵称→正式 id，解析后映射。
- `restore_checkpoint` 的 ActorState 位置参数被新字段错位 → 改关键字构造并持久化
  `contact_aliases`。
- `DescriptionCatalog` 未剥离标记 → item 描述/world primer 泄漏 `[[ ]]`（自己的
  泄漏测试抓到的）。
- `mark_seed.py` 三处：YAML 值起始 `[[` 是 flow-sequence（需引号）、短别名嵌套进
  已标记长名（sentinel）、`as` 为空合法（联系人可只有正式名）。
- 概念重名（洪水路线旁注重复注册）→ 并入既有 Tier-A 概念并加公开别名。

## 验证

- **304 passed / 1 skipped**；`seed_lint.py` OK；`dry_run` 到 22:00 端点。
- **泄漏检查**：303 个标记，模型可见面（KB desc、primer、实体描述、人设、
  notice、facts）0 泄漏（专测 `test_reference_markers_never_reach_the_model`）。
- **确定性证明**：`text` 目标 `妈妈`/`我妈`/`陈默妈` 全部送达 `陈默妈`；
  `林瑶`/`爸` 被拒并列出可联系名单（回归测试
  `test_contact_nickname_resolves_to_formal_id`）。
- **真实运行** `runs/real-20260914T104044+0800-184827-365599685.json`
  （07:00→08:00，19 回合 64 事件，0 agent_error）：陈默**主动**给妈妈发短信
  （`text {"target":"陈默妈"}` → ok）；flashback 命中概念+memory 合并行；
  模型上下文 0 标记泄漏。陈默妈对自己的"代表"查询返回空——正确（她没有该行）。

## 已知边界

- lint 的 `[[ ]]` 作用域检查对「地点描述里提到在场人物」用公众人物规则放行；
  若未来要「必须先认识才能知道某人存在」，再收紧。
- `[[ ]]` 标记会进 git diff（303 处）；`scripts/mark_seed.py` 幂等可重跑。
- 陈默妈对该案查询返回空是**正确**行为；若想让长辈知道 2013 内情，给她的
  concept 加 memory 即可（lint 会要求同时进 known_to）。

## Comments

- 2026-09-14 agent (pi, 当前会话模型): 五点裁决全实现；两轮 live smoke +
  确定性回归；发现并修复 6 个真 bug（含一个测试漏掉的昵称自解析缺陷）。
