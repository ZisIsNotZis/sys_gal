# 78 — 种子契约四门：施动者绑定 / 角色名词 / 可达性 / 动作覆盖（E79–E82）

Status: fixed
Need-review: yes
Need-test-cases: no

> 2026-10-16 / M1.5 后。范围：只改 `v4/scripts/seed_lint.py`（新增四门通道）与
> `v4/harness/tests/test_historical_failures.py`（新增 `SeedContractGateTests` 与
> E79–E82 台账），外加本票与违规清单
> `.scratch/v4-first-day/reports/seed-contract-violations.md`。**未改** `world/`（那是
> 下一个修复代理的活）、未改 `harness/` 产品代码、未改 `scripts/check_milestones.py`。
> 用户裁定（本轮中途）：引擎保持最小原语集，复杂度放种子层——因此**没有**新增
> `fixtures:`/`stock:`/`phone_lines:`/`spawn_extra` 之类的概念类别，四门只对既有
> 类别（actors / locations / items / documents / concepts / kb 联系人）做契约检查。

## 为什么要这道门

票 47/58/60/61/62 的名字契约只回答“这个名字能不能解析”。d1-pm 复盘（
`reports/m1-dot5-postrun-analysis.md` §2.2/§2.4）暴露出另一类缺陷：**名字都解析得通，
世界却兑现不了作者写下的事**——

- 16:20 面核通知写着“值班干事按规程把审计包摊开逐项核对”，可世界里没有这个人
  （G1）；
- “值班干事/老板娘/店员/值班学生/管理员…”这些角色名词谁都能读到、却谁也无法解析，
  因为它们没有被注册成任何东西，旧契约只查“已注册的名字”（G2）；
- 唐小岚有一条常驻任务“交接班前去后街糕点铺帮老板娘带话”，而后街糕点铺只是一个
  `kind: place` 概念，没有地点、没有路由——她向 ≥8 个 extra 问路六小时，`move`
  只会回“不是一个你知道的地方”（G3）；
- 公告栏被反复派去看（10:49–13:35，10+ 个错误轮），热水壶/关东煮库存/食堂菜牌被反复
  向路人打听，12345 这条热线是模型自己编的——因为 `read` 的目标只能是文书、
  “看见/拿”的对象只能是 items、能联系的只能是 actor 或联系人（G4）。

## 四门的判定语义（一句话各一条）

1. **G1 施动者绑定**：排程通知里“某人做某事”的角色词必须解析到一个真实 `actors:`
   行；否则报错并给出“绑定既有 actor（票 77b 的宿主编码）”或“改写为可观测缺席”
   两条修法。地点 extras 不算绑定（临时邀请的陌生人没有在场保证、库存与留痕），
   注册成概念也不算（概念没有双手）。
2. **G2 角色名词**：正文（通知 / 概念 desc·memory / kb 行 / item·document 正文 /
   地点 rules 与 extras 注记 / characters·items·documents·locations 的 .md）里没被任何
   注册名覆盖的角色类名词，必须注册成名字（并在正文写 `[[名字]]`），或在该行
   `role_prose:` 里声明它是泛称集合。
3. **G3 可达性**：每个注册地点从每个 MC 出发点按 routes 可达（`remote: true` 免判）；
   每个注册 item/document 有可达地点、可达携带者或 `completeness:` 声明；正文派角色
   “去”的地方必须是注册地点，不能只是 `kind: place` 概念。
4. **G4 动作覆盖**：正文提到“要交互”的东西必须落在既有动作目标类上——`read` 要文书
   （kernel `_available_readables`：documents 或带 content 的 items）、看见/拿要 items
   （描述走知觉与 observed）、联系要 actors 或 kb 联系人行；不在任何既有类别就报错
   并指明该注册成哪一类。

## 实现

### 一条独立通道，不是改写旧契约

`lint()`（名字解析契约）连同它下面所有旧票据的判据**一行未改**；四门由
`contract_gate_findings(world_root)` 计算（与既有的 `collision_warnings` /
`document_state_warnings` 同一种“拿 world_root、自己 load”的写法），`main()` 两条通道
一起跑、任一出非空即 exit 1。理由：旧票据的测试断言的是“整份种子在这条通道上干净”，
把四门塞进 `lint()` 会逼着改掉十来处别人票据的断言；分成两条通道后，各自的历史可独立
核查，而预跑门禁（`python3 scripts/seed_lint.py`）从今天起会一直红到种子修好为止——
这正是本票要的“门抓住真缺陷”的状态。

### 门的构成（`scripts/seed_lint.py`）

| 部分 | 作用 |
| --- | --- |
| `_ROLE_NOUNS` / `_AGENT_VERBS` / `_ABSENCE_FORMS` / `_VERB_PREFIX_CHARS` | G1/G2 的受控词表：角色类名词后缀表、施动动词、可观测缺席写法、否定前缀（“不代表你已到场”里的“代表”是动词） |
| `_INTERACTION_KINDS` + `_CALL_CUES` + `_PHONE_NUMBER_RE` | G4 的三类交互与拨打线索；“妈妈来电话”这类叙述不算承诺一条通信路径 |
| `_authored_texts(pack, root)` | 作者正文的**单一语料**（通知/概念/kb/正文/rules/注记/.md），G2 与 G4 共用，两门不会各扫一套 |
| `_blank_quotes` / `_mask_names` / `_clause_bounds` / `_role_hits` | 引号内转述不参与 G1；注册名先抹掉再找“裸角色词”；分句边界用于“角色词之后有没有动词” |
| `bare_role_tokens` / `_acting_role_tokens` | G2 只看没被任何注册名覆盖的词；G1 只抹掉演员名（注册成概念并不能让世界有人做事） |
| `_route_graph` / `_mc_reachability` / `_reachable_locations` / `_entity_paths` / `_has_a_path` | G3 用 `world_loader` 已解析的 locations/routes/inventory/scheduled effects，不另建地图 |
| `_manifest_rows` / `_row_line` / `_text_line` | 违规坐标：每门给 `file:line`，修的人不用再去搜 |

四门都**只读**种子（G3 用 loader 已解析的图，不写回任何东西），无新顶层声明块，
不需要引擎配合；`spawn_extra` 一类的想法按用户裁定不予引入（票 77b 已裁定事件宿主
= 既有 `actors:` 行）。

### 当前读数（绑定种子 md5 `7b5632470644d33e9d0d87dc5172bd6c`，门 md5 `ee69f44949eec57cb23984da55e2e014`）

```text
seed contract FAILED (104 violation(s), G1-G4):
G1  9      G2 58      G3  3      G4 34
```

按门分组、带 `file:line` 与两条修法的完整清单见
`reports/seed-contract-violations.md`（下一个代理的工作单）。最关键的 5 条：

1. `manifest.yml:830`（G1）`audit_pack_review` 的“值班干事”——d1-pm 16:20 面核没有
   宿主，林瑶错过了面核，锚点因此 FAIL。
2. `manifest.yml:745/866/891/915/947/1023/1101` + `concept archive-keeper`（G1/G2）
   “管理员 W 返岗/核对移交清单/签字”——一个不存在的管理员完成了档案室的移交。
3. `kb[唐小岚] 15:00`（G3 + G2）后街糕点铺带话：6 小时死任务，地点只有概念没有路由。
4. 公告栏 15 处（G4）——d1-pm 上午主循环族的根因。
5. `manifest.yml:1156` 与 `items/一碗关东煮.md:3` 等（G4）关东煮/热水壶/菜牌/货架/冰柜
   ——静物不可查验那一族。

## 测试（先红后绿，每条都钉住一类已测缺陷）

`SeedContractGateTests`（11 个测试，全部在最小世界包夹具上红→绿；另有 1 个在**真实种子
副本**上注入四类缺陷证明门与真实种子的接线）：

| 门 | 测试 | 红 | 绿 |
| --- | --- | --- | --- |
| G1 | `test_g1_an_acting_role_noun_needs_a_real_actor` | 通知“值班干事把话说明白了” → 报，并给 actors/缺席两条修法 | ①主语换成 `[[甲]]` ②“值班干事今天不在” |
| G1 | `test_g1_quoted_speech_and_absence_forms_are_not_agents` | —（边界） | 引号内转述不算施动 |
| G2 | `test_g2_a_bare_role_noun_needs_registration_or_a_generic_declaration` | 裸“值班干事” → 报，给出 `role_prose:` | ①`role_prose: [值班干事]` ②注册 `kind: generic` |
| G3 | `test_g3_every_location_needs_a_route_from_an_mc_start` | 无路由地点 → 报，给出 routes 修法 | ①双向路由 ②`remote: true` |
| G3 | `test_g3_a_prose_destination_must_be_a_location_not_a_place_concept` | 派去 `kind: place` 概念 → 报 | 注册成地点 + 路由 |
| G3 | `test_g3_an_item_needs_a_path_or_a_completeness_declaration` | 物品在远程地点 → 报 | ①背包 ②`completeness: missing` |
| G4 | `test_g4_a_read_mention_needs_a_document` | 房间正文提“公告栏” → 报 | 注册 documents 行（+ ticket 35 的 `actionable_refs`） |
| G4 | `test_g4_an_examine_mention_needs_an_item` | 正文提“热水壶” → 报 | 注册 items 行 |
| G4 | `test_g4_a_call_mention_needs_a_person_to_reach` | “重大事项须电话报备”无对方 → 报 | 打电话给一个真实 `actors:` 行 |
| — | `test_the_gates_bite_on_the_shipped_pack` | 真实种子副本注入：排程里没演员的“保安”、摘掉河堤全部路由、食堂正文加“菜牌” → 四门各自报出 | —（这一条只证明接线） |
| — | `test_the_four_gates_run_as_one_command_on_a_clean_pack` | — | 干净包零违规 |

台账登记（E79–E82，见 `test_historical_failures.py` 文件头）把每一门映射到它防的
已测缺陷：E79 = 排程里的无主施动者（830 面核）、E80 = 裸角色名词、E81 = 无路径的
地点/物件（后街糕点铺、老家属院的哨子/雨伞）、E82 = 正文要求交互却不是既有类别
（公告栏 / 静物 / 电话）。

## 验证输出（绑定本次工作树）

1. `python3 scripts/seed_lint.py` → exit 1，`seed contract FAILED (104 violation(s),
   G1-G4)`，其中 `G1 9 / G2 58 / G3 3 / G4 34`；同一份种子的名字契约仍是
   `seed lint OK`（旧通道未被本票改写）。
2. `python3 -m unittest harness.tests.test_historical_failures.SeedContractGateTests`
   → `Ran 11 tests ... OK`。
3. `python3 scripts/seed_lint.py --verbose` → 同样 exit 1，104 条 G 行；advisory 段
   （name collision / 台账 known_to / 单向通讯录）与改动前一致，无本票新增。
4. `python3 -m unittest harness.tests.test_historical_failures` → `Ran 147 tests ... OK`。
5. 全套：`python3 -m unittest discover -s harness/tests -p 'test_*.py'`
   → `Ran 594 tests in 214.152s — OK (skipped=1)`，日志
   `v4/logs/full-suite-20261016-run8-ticket78.log`（绑定最终工作树；本树基线 583 +
   本票新增 11 = 594）。票 73 口径的 extra 时序家族间歇失败本次未出现。

## 移交

1. **种子修复**：`reports/seed-contract-violations.md` 是工作单，按 §6 的顺序修；
   修完 `python3 scripts/seed_lint.py` 必须 exit 0。
2. **不要靠放宽词表消数字**：门报的是故事做不到的事；遇到没覆盖的同类缺陷，把词加进
   受控表（`_ROLE_NOUNS` / `_INTERACTION_KINDS` / `_AGENT_VERBS`），不要绕写。
3. **门自身的已知限额**（写进清单 §8）：不做逐名词 NLP；引号内是转述；地点 extras 的
   fragment 不扫（它本身就是声明）；远程地点不按步行走路判，但放在那儿的实物照样报。
4. **若日后把四门合进 `lint()`**：需要同时改写旧票据里十余处“整份种子干净”的断言，
   本票刻意不这么做。
