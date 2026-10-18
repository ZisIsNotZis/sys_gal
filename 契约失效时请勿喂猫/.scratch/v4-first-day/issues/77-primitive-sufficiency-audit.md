# 77 — 原语充分性审计：三个死循环族不需要新动作（E76/E77/E78/E77b）

Status: fixed
Need-review: yes
Need-test-cases: yes

> 2026-10-16。起因：M1.5 报告
> （`.scratch/v4-first-day/reports/m1-dot5-postrun-analysis.md` §1.2/§1.4/§1.5/§2.4）
> 记录了 d1 全天三族"不可解循环"——公告栏、静物/库存、12345 借电话，另加 pm
> 段"面核现场无人"。
>
> **本条否决了最初的方案**（给引擎加 `examine` / `call` 动作与 `spawn_extra`
> effect op）：用户裁定引擎必须保持最小原语集，复杂度放在种子层；引入新概念前
> 先证明旧概念做不到，其次是扩展旧概念。已写入的 `examine`/`call`/`spawn_extra`
> 及相关注册表（`examine_defs`/`phone_lines`/`ActorState.alias`）、三个测试类与
> 检查点增量全部撤回，`harness/kernel.py` 回到原样（该文件现存改动只有别的票的
> ticket-71 `Count` 与 ticket-75 take 守卫）。
>
> 本条最终产出：**零引擎改动**的编码方案 + 证明它能闭合每条循环的测试。边界：
> `harness/tests/test_world_pack.py`、`harness/tests/test_historical_failures.py`、
> `docs/V4-ENGINE.md` §7.3、本票。未动 `world/`、`scripts/seed_lint.py`、
> `scripts/check_milestones.py`、检查点格式。

## 审计结论（逐项）

| 缺陷 | 零改动可行？ | 既有概念编码 | 证据测试 |
|---|---|---|---|
| 1 公告栏死循环 | **可行** | `documents:` 行 + `documents/<id>.md`（`content`、`reading_seconds`、默认 `auto_read`）；`read` 的可用对象来自 `document_defs`（`World._available_readables`），停留即读也复用 §7.1 | `PrimitiveSufficiencyTests.test_a_notice_board_is_a_document_and_read_already_covers_it`、`AuditTests.test_notice_board_needs_only_a_document_row` |
| 2 库存/陈设不可查验（关东煮锅、热水壶、菜牌） | **可行** | 陈设/库存 = `items:` 行 + `items/<id>.md` 描写（数量写进正文，`readable: false` + `readable_reason`），在场即随知觉下发并落 `observed` 记忆行（§7.1）；要"读"的价目表/菜牌按 1 登记成文书 | `PrimitiveSufficiencyTests.test_stock_and_fixtures_are_item_descriptions_in_perception`、`AuditTests.test_fixture_stock_needs_only_an_item_description` |
| 3 12345 借电话死胡同 | **可行（种子层）** | 缺的是**世界内出口**：`routes:` + 该地点的用途描写（`locations/<id>.md`）+ 能指路的在场者；`text` 对非人地址的既有拒绝已列出真正可达的收件人 | `PrimitiveSufficiencyTests.test_the_night_dead_end_is_a_missing_route_not_a_missing_verb`、`AuditTests.test_the_hotline_loop_needs_a_world_exit_not_a_verb` |
| 4 值班干事（面核缺主持者/无现场证据） | **可行** | 宿主 = 既有 `actors:` 行（`role: npc`，事件驱动，由既有排程 `target` 唤醒）；场合证据 = `add_document` 效果放下的一条文书，晚到者自己 `read` | `PrimitiveSufficiencyTests.test_a_duty_clerk_is_an_existing_actor_and_absence_leaves_a_record` |

### 残留（记录，不实现）

字面意义上的"打电话给非人端点"（12345 接受诉求并给回执编号）今天确实不可表达：
`text` 的目标只解析 actor（`_canonicalize_persons` → `_resolve_person`），非人地址
必然被拒。**最小泛化**（若将来确需）：把 `text` 的目标类从 actor 扩到"已注册
非人端点"——在 `_raw_duration` 的 `text` 分支与 `_resolve_person` 里多一个端点
解析分支，端点沿用 `known_to` 意识门控，回执作为 `message_delivered` 的私有正文。
**不是**新增 `call` 动作。触发条件：证明"世界内出口"方案在某个具体情节里确实
不适用（例如剧情要求一个无法到场、无法步行抵达的对端）。本票不实施。

## 先红后绿证据说明（与一般票据的区别）

本条没有引擎改动，所以不存在"改前红→改后绿"的实现循环；它的可反驳证据是另一种
形状，每个测试都自带**正反两个夹具**（同一引擎，只换种子声明）：

- 反夹具（复现死胡同）：没有登记 → `read` 的 affordances 里没有它、`read` 报
  "这里没有这样一件能读的文书"；没有路由 → `move to 通宵值班室` 不出现；`text
  12345` 被拒但列出真实收件人。
- 正夹具（编码闭合）：补一条 `documents:` / `items:` / `routes:` 声明 → 同一个
  动作出现在 affordances，事件照既有语义产生（`document_read`、`observed`、
  `enter`）。
- `test_world_pack.PrimitiveSufficiencyTests` 走的是玩具包（反/正各建一个包）。
- `test_historical_failures.PrimitiveSufficiencyAuditTests` 走的是**真实世界包**：
  先 `load_story_pack().build_world()`，再在测试内叠加那一条种子声明（不入种子），
  证明"只差一条声明"而不是"只差一个原语"。删掉文书通道
  （`_available_readables`/`document_read`）、物品描述通道
  （`_visible_descriptions`/`observed`）或路由 affordance，这两组都会红。

实测（本工作树，`OPENAI_MODEL=github_copilot/gpt-6-luna`）：

```text
python3 -m unittest harness.tests.test_world_pack.PrimitiveSufficiencyTests
  Ran 4 tests in 0.676s — OK
python3 -m unittest harness.tests.test_historical_failures.PrimitiveSufficiencyAuditTests
  （同上一条命令合并跑 7 tests — OK）

python3 -m unittest discover -s harness/tests -p 'test_*.py'
  run1 Ran 583 tests — FAILED (failures=1, skipped=1)，唯一红是
       test_engine.EngineTests.test_silent_abandonment_auto_continues_pending_action
  run2 Ran 594 tests — OK (skipped=1)
  run3 Ran 594 tests in 117.770s — FAILED (failures=1, skipped=1)，同一支测试
  （该支测试单跑 3/3 绿、`harness.tests.test_engine` 模块跑 3/3 绿；票据 73/75
   已把这条登记为负载敏感的已知间歇 flake，与本票无路径交集：本票只造 World 与
   临时世界包，不碰 AsyncEngine/线程/墙钟。两两次运行测试总数不同（583/594）是
   别的 lane 同时在加测试，不是本票增删。）
```

`git diff harness/kernel.py` 中本票贡献为 **0 行**（该文件现存改动属 ticket 71 的
`Count` 与 ticket 75 的 take 守卫）；`git diff --cached` 为空。

## 检查点 / replay 兼容证明

零引擎改动 ⇒ `World.checkpoint_state()` / `restore_checkpoint()` / `replay_world`
的字段与语义**一字未动**：没有新增键、没有新增事件 kind、没有新增 effect op、
没有新增动作 kind（`World.ACTIONS` 与 `SCHEMAS` 均未变）。旧检查点照常加载的
理由因此是结构性的，而不是"测了没坏"：本条根本没有触碰这些路径。唯一新增的
运行时行为全部来自**种子声明**（多一条文书/物品/路由/配角），它们走的是既有
装载器（`document_defs`/`item_locations`/`routes`/`actors`），检查点早已覆盖。

## 文档

- `docs/V4-ENGINE.md` 新增 §7.3「原语充分性：读=文书，知觉=物品描述」：裁定、
  两条通道的分工（给种子作者的写法）、世界内出口优先、现场人物用常驻配角、
  残留与最小泛化的边界、回归位置。未引入任何新动作。

## 与票 78 的关系（并行 lane，结论一致）

票 78 把同一个结论做成了**种子合约门**（`scripts/seed_lint.py` 的 G4：正文提到的
交互必须落在既有动作目标类上——`read` 要文书、看见/拿取要 `items:`、联系要
`actors:`/KB 联系人），台账号 E79–E82；本票做的是**原语充分性审计**（同一结论的
正向证据：只补一条声明，`read`/知觉/路由就闭合），台账号 E76/E77/E78/E77b。两边
用不同的号码区间、不同的证据形状（静态门 vs 运行时行为），互不冲突；78 的 G4
规则的正是本票移交项 1/2 的种子修复形态。78 也独立记录了"用户裁定最小原语集，
因此没有引入 `fixtures:`/`stock:`/`phone_lines:`/`spawn_extra:`"。

## 移交（种子 lane，超出本票边界）

1. `教学楼公告栏`（及各处公告栏）：登记 `documents:` 行 + Markdown 描写；同步
   `scripts/seed_lint.py` 的名称解析（另一代理在改 lint）。
2. 关东煮锅 / 热水壶 / 食堂菜牌：`items:`（库存写进描写）或 `documents:`（可读
   的菜牌/价目表）。
3. 过夜线：新增一个可达地点 + 用途描写，或把托付改成可经既有联系人转达。
4. `audit_pack_review`：宿主绑定到既有 actor（辅导员/班长或新增 `actors:` 行），
   并把 `add_document` 的面核记录放进该排程的 `effects`。
