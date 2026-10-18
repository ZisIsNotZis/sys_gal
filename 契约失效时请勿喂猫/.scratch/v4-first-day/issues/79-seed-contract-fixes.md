# 79 — 把票 78 的 104 条种子契约违规全部修完（G1–G4 归零）

Status: fixed
Need-review: yes
Need-test-cases: no

> 工作单：`.scratch/v4-first-day/reports/seed-contract-violations.md`（票 78 生成，
> 绑定种子 md5 `7b5632470644d33e9d0d87dc5172bd6c`）。范围：只改 `v4/world/`
> （`manifest.yml` + 新增的 `documents/`、`items/`、`locations/` Markdown 与 `locations/*.md`
> 里被新登记名影响的标记），外加本票。**未改** `v4/harness/`、`v4/scripts/`、
> `v4/scripts/check_milestones.py`：门与引擎一行未动，修的是“世界能不能兑现写下的
> 事”，不是把门放宽。
> 修法约束（票 77 裁定）：只用既有概念类别 actors / locations / items / documents /
> concepts / kb 联系人，不新增原语、不新增顶层声明块；不为绿删世设。

## 1. 读数（同一条命令、两条通道）

修前（绑定 md5 `7b5632470644d33e9d0d87dc5172bd6c`）：

```text
seed contract FAILED (104 violation(s), G1-G4):  G1 9  G2 58  G3 3  G4 34
```

修后（本票种子 md5 `54df4a64865e4edb2176f3e45cf4a1b9`，门 md5 `ee69f44949eec57cb23984da55e2e014` 未变）：

```text
python3 scripts/seed_lint.py
  seed lint OK: every named thing resolves to an entity or concept   (exit 0)
lint() 名字解析通道 findings: 0
contract_gate_findings() 四门通道 findings: 0
```

advisory `warning:` 行与修前同一条不差（名字撞车 6 条、台账 known_to 1 条、通讯录
单向 1 条），本票没有新增或消掉任何 warning。

## 2. G1 施动者绑定（9 条）

| # | 基线 file:line | 排程 | 采用的修法 | 落成了什么 |
|---|---|---|---|---|
| 1 | `manifest.yml:830` | `audit_pack_review` | 绑定既有 actor（裁定条目） | 通知改为“[[学生会办公室]]的值班干事就是[[班长]]；他按规程把[[学生会审计包]]当场摊开逐项核对……[[面核记录]]当场留痕”，并加 `role_prose: [值班干事]`；16:20 的现场证据由本行 `effects` 放下 `面核记录`（@学生会办公室），`actionable_refs` 让晚到者可读（票 77 移交第 4 条）。**不放 `target:`**——E72b 要求这场面核保持公开广播，收窄成 target 会让林瑶听不到 |
| 2 | `manifest.yml:785` | `application_rejected` | 绑定既有 actor | 主语改成 `[[班长]]`（同一个人替值班岗说话；`值班簿` 里 3/10、3/12、3/14 记的都是他的本名纪风，是种子里已有的当值证据），不再出现无主的“值班干事把话说明白了” |
| 3 | `manifest.yml:891` | `admin_resolution` | 可观测缺席 | “管理员 W 仍在请假，周五才返岗——三日内完成登记补录……”；另加 `role_prose: [负责人, 管理员]` |
| 4 | `manifest.yml:907` | `quest_washer` | 绑定既有 actor | 主语改成 `[[宿管阿姨]]`（既有 actor，阿姨已是它的称呼，不再有裸“阿姨”） |
| 5 | `manifest.yml:915` | `ledger_found` | 同分句缺席声明 | “管理员 W 在请假期间抽空回来翻了一遍旧档案柜：[[借阅登记本]]在底层柜缝里被找到了……”；`role_prose: [管理员]` |
| 6 | `manifest.yml:947` | `admin_return` | 同分句缺席声明 | “请假回来的管理员 W 返岗第一天。他捧着登记本看了很久……”；`role_prose: [管理员]` |
| 7 | `manifest.yml:1023` | `admin_handover` | 同分句缺席声明 | “请假回来的管理员 W 和[[陈默]]逐项核对移交清单……”；`role_prose: [管理员]`；`actionable_refs` 读 [[移交存根]] 保留 |
| 8 | `manifest.yml:1029` | `coop_thread` | 改写为无主施动 | “老板娘的态度缓和了些——她听说他们是纪念活动上做事的学生……”（把“听说”落在她自己的认识上，不再是世界的客观施动）；`role_prose: [老板娘]` |
| 9 | `manifest.yml:1101` | `files_closed` | 同分句缺席声明 | “……请假回来的管理员 W 在移交单上签了字，说了句“辛苦”。”；`role_prose: [负责人, 管理员]` |

“同分句缺席声明”是什么：门只认“通知不声称有人在场执行”这一条合法路（可观测
缺席写法）。管理员 3/16–3/27 的每条通知都必须在**同一个分句**里交代他还处在请假
这一事实（“在请假期间…”“请假回来的…”），否则门读到的仍是“一个不存在的人在做
事”。这不是绕过门：请假是他在这段时间里的世界事实（`admin_reply` 3/17：“原管理员
因家事请假，返岗时间另行通知”），写出来比不写更准确。

裁定说明：`值班干事` 按工单裁定绑定既有 actor `[[班长]]`（不是新增 NPC）——理由是
他被注册为“学生会办公室值班岗位”的当值人这件事，种子里已有物证（`值班簿` 内容，
3/10、3/12、3/14 记的都是纪风）。`管理员 W` 不新建成 actor：他在 3/16–3/18 明确
“因家事请假、人不在档案室”，给他一个 `actors:` 行等于让他开局就站在档案室里，
与既有排程和地点 extras 直接冲突；因此 5 条（891/915/947/1023/1101）统一采用
“同分句缺席声明”：891 只陈述状态（“仍在请假，周五才返岗”），把补录这件事交给
收信人自己；915/947/1023/1101 保留他返岗前后的动作（翻档案柜、捧登记本、核对移交
清单、签字），但在同一分句里写明“在请假期间 / 请假回来的”，并尽量与已在场的
`[[陈默]]`/`[[林瑶]]` 并写或写成被动（“被翻了一遍”“被找到了”），让“谁在场、谁不
在场”在句面上可读，而不是靠读者猜。

## 3. G2 角色名词（58 条）

除第 4 条（`阿姨`→`[[宿管阿姨]]`）外，全部走“在该行 `role_prose:` 声明泛称集合”
——正文一字不改，只是把“这个角色词指的不是某个具体名字”写成声明（`role_prose`
只被 lint 读，不进模型可见文本）。

| # | 基线 file:line | 名词 | 声明/改写落在哪一行 |
|---|---|---|---|
| 1 | `manifest.yml:745` | 管理员 | `scheduled 校史档案室_shift` → `role_prose: [值班学生, 管理员]` |
| 2 | `manifest.yml:785` | 值班干事 | `application_rejected` → **改写**：主语换成 `[[班长]]`，该词不再出现 |
| 3 | `manifest.yml:820` | 值班干事 | `scheduled audit_relay_task` → `role_prose: [值班干事]`（这一句是捎话，不是现场面核） |
| 4 | `manifest.yml:830` | 值班干事 | `scheduled audit_pack_review` → `role_prose: [值班干事]` |
| 5 | `manifest.yml:866` | 负责人 | `scheduled admin_reply` → `role_prose: [负责人, 管理员]` |
| 6 | `manifest.yml:866` | 管理员 | 同上 |
| 7 | `manifest.yml:891` | 负责人 | `scheduled admin_resolution` → `role_prose: [负责人, 管理员]` |
| 8 | `manifest.yml:891` | 管理员 | 同上 |
| 9 | `manifest.yml:907` | 阿姨 | `quest_washer` → **改写**：`[[宿管阿姨]]`，该词不再出现 |
| 10 | `manifest.yml:915` | 管理员 | `scheduled ledger_found` → `role_prose: [管理员]` |
| 11 | `manifest.yml:947` | 管理员 | `scheduled admin_return` → `role_prose: [管理员]` |
| 12 | `manifest.yml:1023` | 管理员 | `scheduled admin_handover` → `role_prose: [管理员]` |
| 13 | `manifest.yml:1029` | 老板娘 | `scheduled coop_thread` → `role_prose: [老板娘]` |
| 14 | `manifest.yml:1101` | 负责人 | `scheduled files_closed` → `role_prose: [负责人, 管理员]` |
| 15 | `manifest.yml:1101` | 管理员 | 同上 |
| 16 | `manifest.yml:1384` | 老板娘（desc） | `concepts: back-street-bakery` → `role_prose: [老板娘]` |
| 17 | `manifest.yml:1384` | 老板娘（memory[唐小岚]） | 同上 |
| 18 | `manifest.yml:1402` | 代表 | `concepts: old-neighbor-rep` → `role_prose: [代表]` |
| 19 | `manifest.yml:1417` | 值班学生 | `concepts: zhou-student` → `role_prose: [值班学生]` |
| 20 | `manifest.yml:1424` | 值班学生 | `concepts: chen-student` → `role_prose: [值班学生]` |
| 21 | `manifest.yml:1433` | 编辑（memory[唐小岚]） | `concepts: paper-editor` → `role_prose: [编辑, 记者]` |
| 22 | `manifest.yml:1433` | 记者（memory[唐小岚]） | 同上 |
| 23 | `manifest.yml:1445` | 负责人 | `concepts: co-op-boss` → `role_prose: [负责人]` |
| 24 | `manifest.yml:1455` | 管理员（desc） | `concepts: archive-keeper` → `role_prose: [管理员]` |
| 25 | `manifest.yml:1455` | 管理员（memory[陈默]） | 同上 |
| 26 | `manifest.yml:1138` | 负责人 | `kb[林瑶]` 身份行 → `role_prose: [负责人]` |
| 27 | `manifest.yml:1146` | 值班干事 | `kb[林瑶]` 12:30 常驻行 → `role_prose: [值班干事]` |
| 28 | `manifest.yml:1157` | 老板娘 | `kb[唐小岚]` 15:00 常驻行 → `role_prose: [老板娘]` |
| 29 | `manifest.yml:1165` | 阿姨 | `kb[食堂大妈]` 身份行 → `role_prose: [阿姨]` |
| 30 | `manifest.yml:1167` | 阿姨 | `kb[食堂大妈]` 食堂行 → `role_prose: [阿姨]` |
| 31 | `manifest.yml:1177` | 代表 | `kb[陈默妈]` 街坊代表行 → `role_prose: [代表]` |
| 32 | `manifest.yml:391` | 值班学生（签到本 content） | `items: 签到本` → `role_prose: [值班学生]` |
| 33 | `manifest.yml:401` | 值班学生（借阅登记本 content） | `items: 借阅登记本` → `role_prose: [值班学生]` |
| 34 | `manifest.yml:425` | 值班干事（值班簿 content） | `items: 值班簿` → `role_prose: [值班干事]` |
| 35 | `manifest.yml:508` | 编辑（校报草稿 content） | `documents: 校报草稿` → `role_prose: [编辑, 记者]` |
| 36 | `manifest.yml:514` | 值班干事（场地申请表 content） | `documents: 场地申请表` → `role_prose: [值班干事]` |
| 37 | `manifest.yml:75` | 值班学生 | `locations: 校史档案室`（rules[1]）→ `role_prose: [值班学生, 管理员]` |
| 38 | `manifest.yml:76` | 管理员（rules[2]） | 同上 |
| 39 | `manifest.yml:76` | 管理员（extras 注记） | 同上 |
| 40 | `manifest.yml:134` | 编辑（半坡咖啡馆 extras 注记） | `locations: 半坡咖啡馆` → `role_prose: [编辑, 记者]` |
| 41 | `manifest.yml:152` | 大爷（中庭 extras 注记） | `locations: 中庭` → `role_prose: [大爷]` |
| 42 | `characters/下棋大爷.md:17` | 大爷 | `actors: 下棋大爷` → `role_prose: [大爷]` |
| 43 | `characters/唐小岚.md:11` | 值班学生 | `actors: 唐小岚` → `role_prose: [值班学生, 老板娘]` |
| 44 | `characters/唐小岚.md:11` | 老板娘 | 同上 |
| 45 | `characters/林瑶.md:5` | 负责人 | `actors: 林瑶` → `role_prose: [负责人]` |
| 46 | `characters/班长.md:13` | 老师 | `actors: 班长` → `role_prose: [老师]` |
| 47 | `characters/辅导员.md:13` | 老师 | `actors: 辅导员` → `role_prose: [老师, 代表]` |
| 48 | `characters/辅导员.md:17` | 代表 | 同上 |
| 49 | `characters/食堂大妈.md:5` | 阿姨 | `actors: 食堂大妈` → `role_prose: [阿姨]` |
| 50 | `items/一碗关东煮.md:3` | 老板娘 | `items: 一碗关东煮` → `role_prose: [老板娘]` |
| 51 | `items/签到本.md:3` | 值班学生 | 见第 32 行（同一 items 行） |
| 52 | `documents/场地申请表.md:3` | 值班干事 | 见第 36 行（同一 documents 行） |
| 53 | `documents/校报草稿.md:3` | 记者 | 见第 35 行（同一 documents 行） |
| 54 | `locations/图书馆.md:5` | 学生馆员 | `locations: 图书馆` → `role_prose: [学生馆员]` |
| 55 | `locations/小卖部.md:5` | 老板娘 | `locations: 小卖部` → `role_prose: [老板娘]` |
| 56 | `locations/校史档案室.md:5` | 管理员 | 见第 37–39 行（同一 locations 行） |
| 57 | `locations/校史档案室.md:5` | 值班学生 | 同上 |
| 58 | `locations/食堂.md:5` | 师傅 | `locations: 食堂` → `role_prose: [师傅]` |

## 4. G3 可达性（3 条）

| # | 基线 file:line | 缺陷 | 采用的修法 | 落成了什么 |
|---|---|---|---|---|
| 1 | `kb[唐小岚] 15:00`（`manifest.yml:1156`） | 派角色“去[[后街糕点铺]]”，而它只是 `kind: place` 概念 | 注册成地点 + 双向路由（不删任务） | 新增 `locations: 后街糕点铺`（`x: 44, y: 18, sound_radius: 8, known_to: [唐小岚], primer: false`，教工/校外板不进世界前言）+ `locations/后街糕点铺.md`（第一段公开身份、第二段内部细节，票 58）+ 路由 `夜市 ↔ 后街糕点铺 300s`。实测：`_route_path("半坡咖啡馆", "后街糕点铺")` = 半坡咖啡馆→小卖部→夜市→后街糕点铺（420+780+300s），`move` 提交后唐小岚真的到场 |
| 2 | `item 红色哨子` | 放在 `remote: true` 的老家属院，没有任何获取路径 | `completeness: expectation` | 行内声明“按惯例该在，此刻不在手上”（人过不去，世界不假造一条路） |
| 3 | `item 蓝色兔子雨伞` | 同上 | `completeness: expectation` | 同上 |

## 5. G4 动作覆盖（34 条）

| # | 基线 file:line | 词 | 类别 | 采用的修法 | 落成了什么 |
|---|---|---|---|---|---|
| 1 | `manifest.yml:751` | 公告栏 | read | 注册成 documents 行 | `documents: 公告栏`（@学生会办公室，reading_seconds 20，content 就是板上的字；`object_presence` 声明它在场） |
| 2 | `manifest.yml:765` | 公告栏 | read | 同上 | 同上 |
| 3 | `manifest.yml:795` | 公告栏 | read | 同上 | 同上 |
| 4 | `manifest.yml:840` | 公告栏 | read | 同上 | 同上 |
| 5 | `manifest.yml:1417` | 值班表 | read | 注册成 documents 行 | `documents: 值班表`（@校史档案室，content = 3 月第二周的表：小周/小陈被改成陈默/林瑶，备注“排班调整”，无签名无理由——只给物证，不给答案） |
| 6 | `manifest.yml:1424` | 值班表 | read | 同上 | 同上 |
| 7 | `manifest.yml:1455` | 电话 | call | 改写为世界内出口（不新增 call） | `concepts: archive-keeper` desc：“……常年不在，重大事项要报备[[辅导员]]。”——接电话/处理报备的是既有 actor `[[辅导员]]`，不是 12345 |
| 8 | `manifest.yml:1582` | 值班表（desc） | read | 同第 5 行 | 同上 |
| 9 | `manifest.yml:1582` | 值班表（memory[陈默]） | read | 同第 5 行 | 同上 |
| 10 | `manifest.yml:1624` | 公告栏 | read | 同第 1 行 | 同上 |
| 11 | `manifest.yml:1141` | 值班表 | read | 同第 5 行 | 同上 |
| 12 | `manifest.yml:1160` | 热水壶 | examine | 注册成 items 行 | `items: 热水壶`（@女生宿舍，`known_to: [宿管阿姨]` → 她的 KB 因此有条水壶行）+ `items/热水壶.md`（描述走知觉/observed） |
| 13 | `manifest.yml:76` | 电话（校史档案室 rules[2]） | call | 同第 7 行 | 规则改为“管理员不在时，重大事项须报备给辅导员” |
| 14 | `manifest.yml:101` | 公告栏（学生会办公室 extras 注记） | read | 同第 1 行 | 同上 |
| 15 | `manifest.yml:245` | 公告栏（教学楼 rules[1]） | read | 同第 1 行 | 另注册 `documents: 教学楼公告栏`（@教学楼）+ `object_presence`，房间写在正门内侧的那块板 |
| 16 | `manifest.yml:245` | 公告栏（教学楼 extras 注记） | read | 同上 | 同上 |
| 17 | `characters/宿管阿姨.md:5` | 热水壶 | examine | 同第 12 行 | 正文标成 `[[热水壶]]`（`items: 热水壶` 的 known_to 让这行在她 KB 里解析得通） |
| 18 | `characters/班长.md:21` | 公告栏 | read | 同第 1 行 | 正文标成 `[[公告栏]]` |
| 19 | `characters/辅导员.md:21` | 公告栏 | read | 同第 1 行 | 同上 |
| 20 | `items/一份餐食.md:3` | 例汤 | examine | 注册成 items 行 | `items: 例汤`（@食堂，当天的汤桶）+ `items/例汤.md` |
| 21 | `items/一包零食.md:3` | 货架 | examine | 注册成 items 行 | `items: 货架`（@小卖部）+ `items/货架.md` |
| 22 | `items/一瓶饮料.md:3` | 冰柜 | examine | 同上 | `items: 冰柜`（@小卖部）+ `items/冰柜.md` |
| 23 | `items/一瓶饮料.md:3` | 货架 | examine | 同上 | 见第 21 行 |
| 24 | `items/一瓶饮料.md:3` | 柜台 | examine | 同上 | `items: 柜台`（@小卖部）+ `items/柜台.md` |
| 25 | `items/一碗关东煮.md:3` | 关东煮 | examine | 同上 | `items: 关东煮`（@小卖部，那口九格汤锅；与已注册的“一碗关东煮”是两回事）+ `items/关东煮.md` |
| 26 | `documents/台风纪念活动通知.md:3` | 公告栏 | read | 同第 1 行 | 正文标成 `[[公告栏]]` |
| 27 | `documents/学生会审计通知.md:3` | 公告栏 | read | 同第 1 行 | 同上 |
| 28 | `locations/女生宿舍.md:5` | 公告栏 | read | 同第 1 行 + 本地板注册 | 另注册 `documents: 女生宿舍公告栏`（@女生宿舍）+ `object_presence`；正文改为写这块本地板 |
| 29 | `locations/学生会办公室.md:3` | 公告栏 | read | 同第 1 行 | 正文标成 `[[公告栏]]`（该行 `object_presence` 声明它在场） |
| 30 | `locations/小卖部.md:3` | 关东煮 | examine | 同第 25 行 | 正文标成 `[[关东煮]]` |
| 31 | `locations/小卖部.md:5` | 冰柜 | examine | 同第 22 行 | 正文标成 `[[冰柜]]` |
| 32 | `locations/小卖部.md:5` | 货架 | examine | 同第 21 行 | 正文标成 `[[货架]]` |
| 33 | `locations/教学楼.md:3` | 公告栏 | read | 同第 15 行 | 正文改为写 `[[教学楼公告栏]]` |
| 34 | `locations/食堂.md:5` | 例汤 | examine | 同第 20 行 | 正文标成 `[[例汤]]` |

## 6. 因此新增/新建的登记（全部落在既有类别里）

- `documents:` 新增 5 行：`公告栏`（@学生会办公室）、`教学楼公告栏`（@教学楼）、
  `女生宿舍公告栏`（@女生宿舍）、`值班表`（@校史档案室）、`面核记录`（不由开局摆放，
  由 `audit_pack_review` 的 `effects: add_document` 在 16:20 放到学生会办公室）。
  每行都有 `documents/<id>.md`；行文一律单行（`test_descriptions_have_no_manual_wrapping_or_meta_voice`）。
- `items:` 新增 6 行：`货架`、`冰柜`、`柜台`、`关东煮`（@小卖部）、`例汤`（@食堂）、
  `热水壶`（@女生宿舍，`known_to: [宿管阿姨]`）。都是 `readable: false` + `readable_reason`，
  描述走知觉与 ticket-49 的 observed 路径（票 77 的 `test_stock_and_fixtures_are_items…` 同编码）。
- `locations:` 新增 1 行：`后街糕点铺`（+ 双向路由 300s）。
- `object_presence`：`女生宿舍` += `女生宿舍公告栏`，`教学楼` += `教学楼公告栏`，
  `学生会办公室` += `公告栏`（三处都按“这块板在本房间”声明，与放置一致）。
- `role_prose:` 共 41 处声明，按行分：scheduled 10、concepts 7、kb 6、items 4、
  documents 2、locations 6、actors 6（同一声明可盖多个词，如 `[值班学生, 管理员]`），
  只被 lint 读，不进模型可见文本。
- `completeness: expectation` 2 行：`红色哨子`、`蓝色兔子雨伞`。
- 没有新增原语、没有新增顶层声明块、没有新增 actor。

## 7. 回归（`OPENAI_MODEL=github_copilot/gpt-6-luna`）

```text
python3 scripts/seed_lint.py
  seed lint OK（exit 0；四门 0 条）

python3 -m unittest harness.tests.test_historical_failures.SeedContractGateTests
  Ran 11 tests — OK

python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
  Ran 147 tests in 116.134s — OK

python3 -m unittest discover -s harness/tests -p 'test_*.py'（最终树上全套 5 轮）
  run1 Ran 594 tests in 114.514s — OK (skipped=1)
  run2 Ran 594 tests in  74.156s — OK (skipped=1)
  run3 Ran 594 tests in  86.220s — FAILED (failures=1, skipped=1)
       唯一红：test_extra_turns_are_recorded_and_conversational
       assertEqual(arrived[0].time.strftime("%H:%M"), "07:01") → '07:02' != '07:01'
  run4 Ran 594 tests in  80.593s — FAILED (failures=1, skipped=1)
       仍只有同一支：assertLessEqual((first_answer.time - arrived[0].time), 60) → 120.0
       ——工单已点名的“extra 时序间歇家族”（票 73：共享线程池排队 vs 世界时钟按 tick
       飞驰 + idle-despawn），两次红的子断言不同（到场上晚一拍 / 答话晚两拍），
       都不是确定性失败：同一棵树单跑该测试连 3 次全绿。
       这条测试与本次种子改动无路径交集（它只构建真实世界打一次 speak→extra），
       且票 73 §6.1 正留着“全量层间歇 failures=1、身份未捕获”这个开放项——本票顺手
       把身份捕获到了（就是这一支，两种子断言形状），移交不改它的引擎侧。
  run5 Ran 594 tests in  87.080s — OK (skipped=1)   ← 最终树、最终文字上的最后一轮
```

被本票改动**差点弄红**的两支既有回归（都已修好并复跑）：

1. `HistoricalFailureGates.test_speech_anchor_requires_a_scheduled_occasion`
   （E72b）要求 16:20 面核保持公开广播：我先给 `audit_pack_review` 加了
   `target: 班长` 而变红。已删掉 `target`（宿主绑定只写在通知正文与 `effects` 里）。
2. `HistoricalFailureGates.test_uncovered_concrete_prop_claim_blocks_the_seed`
   （issue 35）靠字面替换 `"- id: 签到本\n  location: 校史档案室\n"` 注入缺陷：
   我把 `role_prose` 插在 `- id: 签到本` 后面打断了这个相邻，已把它移到
   `known_to:` 之后，注入重新生效。

## 8. 仍需人读复核（8 条）

1. **`[[班长]]` 当 16:20 面核宿主，但引擎没有“移动 actor”的 effect**：通知说他在
   学生会办公室开面核，他的 `location` 仍是教学楼——世界不会把他搬到现场，晚到者能
   读到的是 `面核记录`（本票新放的文书）。是否够用（还是需要把 `班长` 的常驻位置或
   一条 actor-move 效果另案处理）要人判断。
2. **`值班干事` 的绑定只写在文本层**：`application_rejected` / `audit_pack_review` 把
   岗位落到 `[[班长]]`，依据是 `值班簿` 里 3/10、3/12、3/14 记的“纪风”。若希望
   `班长` 的角色页也明写“学生会有他的值班时段”，那是角色卡改动，本票没动。
3. **“请假回来的”这一写法出现 4 次**（891/947/1023/1101）：它同时承担“真实事实
   （3/17 起家事请假）”和“本句的缺席声明”。语义上没错，但语感是否自然、会不会被
   玩家读成“每次都要强调一次”，建议人读一遍。
4. **三块公告栏的命名不对称**：门板叫 `公告栏`（全校主板，剧情通知都贴这块），另两块
   叫 `教学楼公告栏` / `女生宿舍公告栏`。不对称是刻意的（G4 的受控词表要求恰好存在
   一个叫“公告栏”的可读文书），但要不要给三块统一命名/给另两块加别名，值得人判断。
5. **新登记的陈设是可拿的**：`货架`/`冰柜`/`柜台`/`关东煮`/`例汤` 是 items，模型
   可以 `take` 一台冰柜——引擎今天没有“固定陈设”这一档（票 77 明确不加原语）。是
   否需要一条 take 守卫另案决定；本次至少让“看见/描述”这一层通了。
6. **“电话报备”改成“报备[[辅导员]]”**：这是把规矩的对方定成辅导员（既有 actor，
   也是种子里负责走正式流程的人）。若世界观希望报备对象是院系办公室/教务处（都不是
   actor），那需要另一条世界内出口。
7. **后街糕点铺 `primer: false` + `known_to: [唐小岚]`**：只有她的 KB 有这块地方，
   她能走到（实测多跳 25 分钟）；若希望别的角色也能去/能指路，需要放开 known_to。
8. **`值班表` 内容与既有台账的日期对齐**：我按 `签到本` 的 3/11 08:05 陈默、
   3/12 13:10 林瑶、3/13/3/15 陈默 反推“改写从 3 月 11 日开始”。数字是自洽的，但仍
   建议人对照 `签到本`/`值班簿`/`移交存根` 再读一遍。

## 9. 已知残留（不进本票，避免悄悄扩大范围）

- `audit_pack_review` 的通知仍承诺“面核记录当场留痕”——现在**真的有**一份 `面核记录`
  被放下，但它是一张栏目表，不写谁到场、不写核对结论（不伪造结果）。要更厚的现场
  证据（到会名单、逐项结论）需要另一个设计，且会触碰谜底边界。
- 世界内仍无“打电话给非人端点”（12345）的表达；本票只把“必须报备”的对方换成真实
  actor。票 77 §残留给的最小泛化路径未实施。

## Comments — 收尾（ticket 80，2026-10-16）

用户对 §8 的 8 条逐项裁定，本节是落实结果。引擎只动了一处、且是用户批准的
最小泛化（`items:` 的 `takeable`），其余全在 `world/`：

| §8 | 裁定 | 落地 | 落在哪 |
|---|---|---|---|
| 5 固定陈设可被拿走 | 修（先红后绿 + 台账 + 文档） | 见 `## Comments` §A | `harness/kernel.py` / `harness/world_loader.py` / `world/manifest.yml` / `docs/V4-ENGINE.md` §7.3 / 票 80 |
| 2 值班干事由班长担任 | 写进角色卡 | 班长卡的知识注记行明写“值班干事也是他自己”，`actors: 班长` 的 `role_prose` 加该词 | `world/characters/班长.md:21`、`world/manifest.yml`（actors 段 `班长`） |
| 7 后街糕点铺只对唐小岚 | 核对 move 解析后保持 | `primer: false` 只管世界前言，不管 `move`：move 只认注册地点 + 路由。核过 `_route_path`/`_reachable` 都不读 `primer` 也不读 `known_to`；夜市↔后街糕点铺双向 300 秒，到场的人回得来。因此保持只对唐小岚，理由写进该条目的注释 | `world/manifest.yml`（locations `后街糕点铺`） |
| 3/4/8 语感、公告栏命名、值班三本册子 | 修 | 见 `## Comments` §B/§C/§D | `world/manifest.yml`、`world/documents/*.md`、`world/characters/*.md` |
| 1 面核宿主无 actor-move 效果 | 保留 | 见 `## Comments` §E | — |
| 6 报备对象是辅导员 | 保留 | 同上 | — |

### §8-2 的核对结果（一条与指令前提不符的事实）

指令要求“确认 `manifest.yml:830` 的 notice 已是 `target: [[班长]]`”。**核对的结论是：
不是，而且不该是。** 三件事：

1. 该行现在是 `scheduled: audit_pack_review`（`world/manifest.yml:970`，notice 在 976；
   票 79 的报告里记的是修前基线的行号 830），它的 `target:` **不存在**——票 79 §2 第 1
   条当时就把 `target` 删掉了。
2. `target:` 在排程里是**投递范围**（actor id 列表），不是名字绑定：写成
   `target: [[班长]]` 既不是合法的 actor id，语义也不对。
3. 加上 `target: 班长` 会让这场面核只送到班长一个人手里，`E72b`
   （`HistoricalFailureGates.test_speech_anchor_requires_a_scheduled_occasion`）明确要求
   16:20 的面核保持公开广播——“`self.assertTrue(all(not row.get("target") …)`”。票 79
   §2 记录了当时加 target 后变红、删掉才转绿的过程。

宿主绑定已经用另一条路写死了：通知正文写“[[学生会办公室]]的值班干事就是[[班长]]”，
`effects` 把 `面核记录` 放到学生会办公室，晚到者自己读。这一条 **未改动**。

另外，把这句话写进角色卡还带出一个门的要求：`值班干事` 是角色类名词，G2 要求它在该行
注册或声明为泛称，所以 `actors: 班长` 的 `role_prose` 从 `[老师]` 变成
`[老师, 值班干事]`。实测这份声明是承重的——把它改回 `[老师]`，`role_prose_findings`
立刻在 `characters/班长.md:21` 报“角色类名词 '值班干事' 既没注册，也没声明是泛称”。
声明只说明“这是个岗位词、不是某人的注册名”，不否认这个岗位由他担任，后者由角色卡的
那句话承担。

### A. §8-5 固定陈设（票 80 / E83）

`items:` 增加可选布尔 `takeable`（缺省 true）；`takeable: false` 即固定陈设，
`take` 结构化拒绝，理由取 `fixed_reason`（缺省“这是固定陈设”）。同一条判定也用在
`give` 的就地分支与 `trash` 上——那两条同样能把陈设从原处抹去，只守 `take` 会留下
同一个缺陷的另一扇门。`item_locations`、检查点与 replay 一字未改，`fixed_items` 与
`routes` 一样由种子派生、不进检查点。种子标了 5 件：`货架`/`冰柜`/`柜台`/`关东煮`/
`例汤`；**`热水壶` 保持可携带**——它是值班台上能提着走的日常物件（宿管阿姨的卡原文
“热水壶是我的情”，烧水、倒水、拎去水房都要经手它），把它钉死反而不符合世界事实。
红→绿：`SeedContractGateTests.test_a_fixed_fixture_cannot_be_taken_and_stays_put`
先红在“冰柜出现在 take 候选”，实现后转绿；装载器类型校验也在同一测试里（`takeable:
'no'` 必须报错，不许静默降级成可携带）。

### B. §8-3 “请假回来的”（同一族的 4 处）

§8-3 把它记成“‘请假回来的’出现 4 次”；实际是 **3 条通知用了这个短语**
（`admin_return` / `admin_handover` / `files_closed`）+ **1 条用了同一族的
“在请假期间抽空回来”**（`ledger_found`），四条一起改。

“请假回来的管理员 W 返岗第一天”→“管理员 W 请假回来了，今天是返岗第一天”；
“请假回来的管理员 W 和[[陈默]]…核对”→“管理员 W 请假回来，和[[陈默]]…核对”；
“——请假回来的管理员 W 在移交单上签了字”→“——管理员 W 请假回来，在移交单上签了字”；
`ledger_found` 的“在请假期间抽空回来翻了一遍旧档案柜”→“趁家事请假回校跑了一趟，
翻了旧档案柜”。事实不变（他仍在请假、返岗后签的字），G1 要求的“同分句缺席声明”
也仍然成立（“请假”与角色词同句）。顺手改掉一处不成词的错字：`有搴角`→`卷了角`
（与 `公告栏` 正文的“卷了角的纸”同一说法）。

### C. §8-4 三块公告栏

保持三个独立文书，但把所有指向“公告栏”的正文改成指得死的那一块：两道通知文书
（`学生会审计通知`/`台风纪念活动通知`）与四条排程通知（`application_form_posted`/
`audit_notice`/`typhoon_anniversary_notice`/`statement_request`）都写成
“[[学生会办公室]]门边那块[[公告栏]]”（剧情通知贴的正是这块）；`辅导员` 的唤醒场景
同样点到这块；`班长` 的知识注记写成“[[教学楼公告栏]]与[[公告栏]]”，两块各指一份文书。
三块板的命名仍不对称（`公告栏`/`教学楼公告栏`/`女生宿舍公告栏`）——这是刻意的：
G4 的受控词表要恰好存在一个叫“公告栏”的可读文书，另两块用带地点的实名。

### D. §8-8 `值班表`/`签到本`/`值班簿`

- **日期不自洽的一处**：`签到本` 3 月 10 日 13:02 签的是林瑶（下午那一栏），而
  `值班表` 写“改写从 3 月 11 日开始”——改写前一天下午已经是新名字。修的是派生物：
  `值班表` 的改写日期改成 **3 月 10 日**（内联 content 与 `documents/值班表.md` 两处），
  3 月 11 日 08:05 陈默（上午那一栏）仍是改写后的第一条。`签到本` 是原始事实，不动。
- **叫法**：同一本册子在三处被叫成三个名字——清单 content 自称“值班签到本”、
  `items/签到本.md` 自称“签到簿”、它的登记名是 `签到本`。统一成 `签到本`（两处都改），
  `值班表` 的 mounting 也统一成“钉在档案室门口的木板上”（内联 content 原写“贴在”）。
- **`值班簿` 的“交给值班干事”**：§8-2 把值班干事定成班长本人之后，“3 月 12 日
  12:00–16:00 纪风，16:00 交给值班干事”就成了自己交给自己的班，改写成
  “3 月 12 日 12:00–18:00 纪风”（同一段连续值班），3/11、3/13、3/15 那几条“值班干事”
  照旧（同一人有时写名字、有时写岗位）。
- 三本册子的分工与名字本来就不混：`签到本`（档案室到岗）、`借阅登记本`（档案室借还）、
  `值班表`（档案室的周排班）、`值班簿`（学生会办公室的现场随手记）。这一层没有改动。

### E. 保留不动的两条（附理由）

- **§8-1 面核宿主没有 actor-move 效果**：引擎仍无“移动某个演员”的 effect，16:20 的
  面核只有 `[[面核记录]]` 这条现场留痕。保留的理由：加 actor-move 就是新原语/新 effect
  op，票 77 的裁定要求先证明既有概念做不到；而本场合里“晚到者读得到留痕”已经闭合
  E77b，要不要让他真的站在那儿属于产品取舍，不该由收尾工作顺手决定。
- **§8-6 报备对象是辅导员**：保留。`辅导员` 是既有 actor，也是种子里唯一走正式流程的
  人；换成院系办公室/教务处需要新增 actor 或新出口，同属产品取舍。

### F. 读数（本收尾树）

```text
python3 scripts/seed_lint.py
  seed lint OK: every named thing resolves to an entity or concept   (exit 0)
  lint() 名字解析通道 0 findings；contract_gate_findings() 四门通道 0 findings
  advisory warning 与修前逐字相同（8 条，diff 为空）
python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
  run1 Ran 148 tests — FAILED (failures=1)
       唯一红：test_extra_turns_are_recorded_and_conversational
       assertEqual(arrived[0].time.strftime("%H:%M"), "07:01") → '07:02' != '07:01'
       ——票 73/§7 已点名的 extra 时序族（共享线程池排队 vs 世界时钟），
       单跑 3/3 绿、与本票无路径交集
  run2 Ran 148 tests in 58.452s — OK
  run3 Ran 148 tests in 52.660s — OK（最终树上的最后一轮）
python3 -m unittest harness.tests.test_kernel harness.tests.test_world_pack
  Ran 144 tests in 4.683s — OK
python3 -m unittest discover -s harness/tests -p 'test_*.py'（最终树，两轮）
  Ran 595 tests in 74.495s — OK (skipped=1)      ← 基线 594 + E83 一支
  Ran 595 tests in 73.126s — OK (skipped=1)
```

种子 md5（本收尾最终树）：`50434b937a26e8ed25b3650819279eb3`。

