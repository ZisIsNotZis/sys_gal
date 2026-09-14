# Ticket 15-seed-self-consistency: concepts 注册表 + memory 行 + flashback 重写 + 名字检查

Status: done
Need-review: true

## Issue

v4 首验日 run（`runs/real-20260914T060016+0800-4169077-451294762.json`）暴露：
陈默用 `flashback({"entity":"红色哨子"})` / `flashback({"entity":"老街坊"})`
得到的都是「（没有与你经历相关的可回放历史。）」——尽管种子里写了红色哨子、
老街坊、九岁那年的承诺、蓝色兔子雨伞。根因（审计见 V4-AGENT-INTERFACE §6.1）：

1. `flashback` 只回放本次 run 已投递的公开事件行，且 `t <= now-120min`，不读 KB、
   不读前史 → 起步即空。
2. 角色 `.md` 的私人材料（Private starting state / 秘密清单 / Goals）对 MC 完全
   不进入运行时（`V4Session` 只用 `seed.actor_id`）。
3. `manifest kb:` 每 MC 只有 5 行骨架；关系/往事/私人物品认知为 0。
4. 名字（老街坊、老赵头、小周、小陈、蓝色兔子贴纸…）只在散文里，运行时拿不到。

PO 裁决（2026-09-14）：Tier A 即可，但要**完全自洽**——凡是种子里提到的名字/概念
都必须有「它是什么」（knowledge）且（有来历者）有 flashback memory；并建立
名字迁移/检查机制，杜绝再犯。不要旁路白名单，而是把名字注册进系统。

## 决策

- 新增 manifest `concepts:` 注册表：非 actor/location/item/document 的有名之物，
  含 `name`/`aliases`/`kind`/`desc`/`known_to`/`memory`。
- `concept:` 行 = 世界知识（无条件、按 knowledge 间隔重放）；`memory:` 行 = 私人回忆
  （提及集门控 + flashback 可检索）。`kind: generic` = 仅注册不展开。
- `name` 等于已有实体 id 时为「补充条目」：不重复知识行，只贡献 memory。
- `flashback` 改为三源并集（memory/concept 行 → person/item/location 行 → 已投递历史），
  经 lexicon 解析别名、容忍子串；废 `flashback_horizon_minutes` 旧语义。
- `scripts/seed_lint.py` 为名字检查闸门：散文里任何「名字样」token 未解析到
  实体/concept/alias 即失败；无白名单。`test_seed_names_all_resolve` 锁绿。

## 改动文件

- `docs/V4-AGENT-INTERFACE.md`：§2 flashback 语义、§6 保留字段 + §6.1 concepts 注册表 + 名字检查、§7 常数
- `harness/kb.py`：保留字段 concept/memory、提及集、渲染/排序、`match_rows`
- `harness/world_loader.py`：`concepts:` 校验 + 展开 + `lexicon`、WorldPack 字段
- `harness/engine.py`：lexicon、`_flashback_query` 三源重写（首位优先，非末位截断）
- `harness/real_run.py` / `harness/resume_run.py`：传入 `pack.lexicon`
- `harness/action_schema.py`：flashback 工具描述
- `world/manifest.yml`：`concepts:` 53 条（Tier A 全量 + Tier C generic 注册）
- `scripts/seed_lint.py`（新）
- 测试：`test_kb.py`（concept/memory 行 + match_rows）、`test_world_pack.py`（注册表校验 + lint）、`test_historical_failures.py`（P9 flashback 闸门）

## 校验结果

- `python3 -m unittest discover -s harness/tests -p 'test_*.py'` → 302 passed, 1 skipped
- `python3 scripts/seed_lint.py --verbose` → seed lint OK（无未注册名字、无死别名）
- 直查（`_init_kb` 后）：`flashback(陈默,"红色哨子")` 返回 3 行（老家属院 memory、
  红色哨子 memory、红色哨子 item）；`"老街坊"` 经别名命中老家属院/老街坊代表等；
  `flashback(陈默,"不存在的东西")` 为空；`flashback(林瑶,"听见的哭声")` 为空（不越权）
- 首条世界消息（陈默）已带 `[concept=…]` 行，且 todo/reminder 仍在最前

## Comments

- 2026-09-14 agent (pi, 当前会话模型): 实现 + 测试 + 文档 + lint 完成。Tier B/C 仅注册
  名字（generic），未写 knowledge/memory 行——按 PO「Tier A 即可，别太复杂」。

- 2026-09-14 agent (pi) 验收: PO go（"go"+批准 commit）。302 passed / 1 skipped；seed_lint OK；P9 闸门绿。提交见本 commit。
