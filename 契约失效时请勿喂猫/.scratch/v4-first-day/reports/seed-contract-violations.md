# 种子契约违规清单（票 78：G1–G4）

Status: ready-for-agent
生成命令：`cd v4 && python3 scripts/seed_lint.py`（退出码 1）
绑定修订：种子 `world/manifest.yml` md5 `7b5632470644d33e9d0d87dc5172bd6c`，
门 `scripts/seed_lint.py` md5 `ee69f44949eec57cb23984da55e2e014`（票 78），仓库 `ea47781`。
本清单只描述**今天的种子**；修完种子后重跑同一条命令，数字归零即验收。

这份清单是下一个代理（种子修复）的工作单。每条给出 `file:line`、缺的声明、
两条合法修法。**不要为了绿而删掉世设**：多数条目有“注册成某个既有类别”
这一条 cheaper 的路。

## 0. 四门的判定语义（一句话各一条）

| 门 | 判定 |
| --- | --- |
| G1 施动者绑定 | 排程通知（世界的客观广播）里“某人做某事”的角色词，必须解析到一个真实 `actors:` 行，否则报错并给出“绑定既有 actor”或“改写为可观测缺席”两条修法（地点 extras 不算绑定：临时邀请的陌生人没有在场保证、库存与留痕）。 |
| G2 角色名词 | 正文（通知 / 概念 desc·memory / kb 行 / item·document 正文 / 地点 rules 与 extras 注记 / characters·items·documents·locations 的 .md）里没被任何注册名覆盖的角色类名词，必须二选一：注册成名字并在正文写成 `[[名字]]`，或在该行 `role_prose:` 里声明它是泛称集合。 |
| G3 可达性 | 每个注册地点都要从每个 MC 出发点按 routes 走得到（`remote: true` 的地点按种子声明免判）；每个注册 item/document 要有可达地点、可达携带者或 `completeness:` 声明；正文派角色“去”的地方必须是注册地点，不能只是 `kind: place` 的概念。 |
| G4 动作覆盖 | 正文提到“要交互”的东西，必须落在引擎既有的动作目标类上：要读的是文书（documents 或带 content 的 items）、要被看见/拿取的是 items、要联系的是 actors 或 kb 联系人行。不在任何既有类别就报错，并指明该注册成哪一类。 |

四门只读种子，不新增原语、不新增顶层声明块，与票 77「原语充分性」的裁定一致
（公告栏 = documents 行、关东煮锅 = items 行、值班干事 = actors 行）。

## 1. 当前读数

```text
seed contract FAILED (104 violation(s), G1-G4):
G1  9
G2 58
G3  3
G4 34
```

名字解析契约（`lint()`）依旧全绿：`seed lint OK`。两条通道分开跑、同一条命令都判失败，
所以旧票据的“种子是干净的”断言不会被本票改写，而预跑门禁从今天起会红到种子修好为止。

## 2. G1 施动者绑定（9 条）

判据：通知里做事的角色词 → 必须是一个 `actors:` 行。

| 位置 | 排程 | 施动者 | 现场事实 |
| --- | --- | --- | --- |
| `manifest.yml:830` | `audit_pack_review` | 值班干事 | d1-pm 16:20 面核：通知说“值班干事按规程把审计包摊开逐项核对”，世界里没有这个人。林瑶 16:13 离开、16:24/16:34/16:45 三次路过都无可感知的现场，16:56 自述“我错过了16:20的面核”。**本票最关键的一条。** |
| `manifest.yml:785` | `application_rejected` | 值班干事 | 同一族的第一次：12:30 “值班干事把话说明白了”，说这句话的人不存在。 |
| `manifest.yml:891` | `admin_resolution` | 管理员 | “管理员 W 周五返岗；三日内完成登记补录” |
| `manifest.yml:915` | `ledger_found` | 管理员 | “管理员 W 返岗前整理旧档案柜” |
| `manifest.yml:947` | `admin_return` | 管理员 | “管理员 W 返岗第一天” |
| `manifest.yml:1023` | `admin_handover` | 管理员 | “管理员 W 和…逐项核对移交清单” |
| `manifest.yml:1101` | `files_closed` | 管理员 | “管理员 W 在移交单上签了字” |
| `manifest.yml:1029` | `coop_thread` | 老板娘 | “老板娘听说他们是纪念活动上做事的学生，态度缓和了些” |
| `manifest.yml:907` | `quest_washer` | 阿姨 | “楼道投币洗衣机今天报修，阿姨在群里说本周维修” |

修法（每条二选一）：

1. **绑定既有 actor**（票 77b 的编码：事件宿主就是一个 `actors:` 行，由既有
   `target:` 唤醒）。`值班干事` / `档案室管理员` / `合作社老板娘` / `宿管阿姨` 都可以
   变成 NPC 层的 actors 行，然后把通知主语写成 `[[名字]]`。
   注意加载契约：新增 actor 必须同时补 `kb:` 该角色的身份行与
   `characters/<id>.md`，否则 `load_world_pack` 直接报错。
   `阿姨` 已有 `宿管阿姨`，直接改主语即可。
2. **改成可观测缺席**：不声称有人执行，只陈述状态（“值班干事今天不在，窗口关着”、
   “管理员请假，返岗时间另告”）。`admin_reply`（866 “原管理员因家事请假”）已经是这种写法，
   门不会报它——它可以当模板。

## 3. G2 角色名词（58 条，13 个名词）

判据：角色类名词要么注册、要么在该行 `role_prose:` 声明泛称。按名词分组（修法相同，
所以按组修最快）。

| 名词 | 条数 | 位置 |
| --- | --- | --- |
| 管理员 | 12 | `manifest.yml:745` `866` `891` `915` `947` `1023` `1101`（排程通知）、`1455`×2（`concept archive-keeper` desc + 陈默 memory）、`76`×2（`location 校史档案室` rules[2] + extras 注记）、`locations/校史档案室.md:5` |
| 值班学生 | 8 | `manifest.yml:1417` `1424`（小周/小陈 desc）、`391`（签到本 content）、`401`（借阅登记本 content）、`75`（`location 校史档案室` rules[1]）、`characters/唐小岚.md:11`、`items/签到本.md:3`、`locations/校史档案室.md:5` |
| 值班干事 | 7 | `manifest.yml:785` `820`（“捎来…值班干事的话”）`830`、`1146`（林瑶 12:30 常驻行“交值班干事登记”）、`425`（值班簿 content）、`514`（场地申请表 content）、`documents/场地申请表.md:3` |
| 老板娘 | 7 | `manifest.yml:1029` `1384`×2（`concept back-street-bakery` desc + 唐小岚 memory）、`1157`（唐小岚 15:00 带话行）、`characters/唐小岚.md:11`、`items/一碗关东煮.md:3`、`locations/小卖部.md:5` |
| 负责人 | 6 | `manifest.yml:866` `891` `1101`（“临时负责人”是陈默的头衔）、`1445`（`concept co-op-boss` desc）、`1138`（林瑶常驻行“项目的负责人”）、`characters/林瑶.md:5` |
| 阿姨 | 4 | `manifest.yml:907`、`1165` `1167`（`kb[食堂大妈]` 两行：“打菜阿姨”/“喊我阿姨”）、`characters/食堂大妈.md:5` |
| 代表 | 3 | `manifest.yml:1402`（`concept old-neighbor-rep` desc）、`1177`（`kb[陈默妈]` “街坊代表”）、`characters/辅导员.md:17` |
| 编辑 | 3 | `manifest.yml:1433`（`concept paper-editor` memory）、`508`（校报草稿 content）、`134`（`location 半坡咖啡馆` 注记） |
| 记者 | 2 | `manifest.yml:1433`（同上）、`documents/校报草稿.md:3` |
| 老师 | 2 | `characters/班长.md:13`、`characters/辅导员.md:13` |
| 大爷 | 2 | `manifest.yml:152`（`location 中庭` 注记）、`characters/下棋大爷.md:17`（“大爷可以讲古…”） |
| 学生馆员 | 1 | `locations/图书馆.md:5` |
| 师傅 | 1 | `locations/食堂.md:5`（“[[后勤]]师傅手写的今日例汤”） |

修法，每行二选一：

1. `role_prose: [名词]` 写在**拥有这段正文的那一行**上：
   - 排程 → 该排程行；概念 desc/memory → 该 `concepts:` 行；
   - item/document 正文与其 .md → 该 `items:`/`documents:` 行；
   - 地点 rules/extras 与 `locations/<id>.md` → 该 `locations:` 行；
   - `characters/<id>.md` → 该 `actors:` 行；
   - `kb[角色]` 的单行 → 该 kb 行。
   `role_prose` 不进入模型可见文本（它只被 lint 读），所以这是“保留正文、声明泛称”的
   最省事路径。泛称组（值班学生、打菜阿姨、师傅、老师、负责人这些“谁知道都算”的）优先走这条。
2. **注册成名字**：具体的某个人给 `concepts:`（`kind: person` + `known_to`）；
   “谁都可以”的泛称给 `kind: generic`（不给任何人发知识行），正文写成 `[[名字]]`。
   注意：注册后正文里就必须写标记，否则名字解析契约（旧通道）会红。

分组建议：`管理员` 与 `值班干事` 的首选是让它们变成 actor（G1 那一条），
再把正文主语写成 `[[档案室管理员]]` / `[[值班干事]]`；其余泛称走 `role_prose`。

## 4. G3 可达性（3 条）

| 位置 | 缺陷 | 现场事实 |
| --- | --- | --- |
| `manifest.yml:1156`（`kb[唐小岚]` 15:00 常驻行） | 派角色“去[[后街糕点铺]]”，但后者只是一个 `kind: place` 概念（`manifest.yml:1381`），没有 `locations:` 行、没有路由 | d1-pm 12:21–19:54：唐小岚向 ≥8 个 extra 与同学问路，全部“不知道”；`move 后街糕点铺` 报“不是一个你知道的地方”；一个注定完不成的任务跑了 6 小时 |
| `item 红色哨子`（`manifest.yml` 开局的 `location: 老家属院`） | 全部路径都不通：`老家属院` 是 `remote: true`（只通电话/消息），没有 scheduled `add_item`，也没有 `completeness:` | 第 1 天的任务链要求明确“哨子在哪”，但没有任何角色拿得到它 |
| `item 蓝色兔子雨伞` | 同上（同在 `老家属院`） | 陈默的念想物，可获取性未落地 |

修法：

1. **后街糕点铺**：三选一——(a) 注册成 `locations:` 行 + 双向 routes（`夜市 ↔ 后街糕点铺`
   最短），(b) 把这条派工改成不需要走过去（电话/托人带话，与既有 contacts 一致），
   (c) 删掉这条常驻行。选 (a) 时要补 `locations/后街糕点铺.md`（第一段是可公开的地点身份、
   第二段才是内部细节，票 58）、`primer` 与双向路由。
2. **哨子 / 雨伞**：给一条可达的获取路径——用既有 `scheduled` 的 `add_item` 在某个
   可达地点投放（例如某次“回老家属院”的排程之后），或把 location 改到可达地点，
   或在该行显式声明 `completeness: expectation`（“按惯例该在，此刻不在手上”）。
   最省事且最诚实的是 `completeness:`：它们本来就是“还没拿到”的东西。

## 5. G4 动作覆盖（34 条，9 个被要求交互的东西）

判据：正文要求的交互必须落在既有动作目标类上。按词分组：

| 词 | 类别 | 条数 | 位置 |
| --- | --- | --- | --- |
| 公告栏 | 读 → documents | 15 | `manifest.yml:751` `765` `795` `840`（四条排程通知）、`1624`（`concept student-union` desc）、`101`（`location 学生会办公室` 注记）、`245`×2（`location 教学楼` rules[1] + 注记）、`characters/班长.md:21`、`characters/辅导员.md:21`、`documents/台风纪念活动通知.md:3`、`documents/学生会审计通知.md:3`、`locations/女生宿舍.md:5`、`locations/学生会办公室.md:3`、`locations/教学楼.md:3` |
| 值班表 | 读 → documents | 5 | `manifest.yml:1417` `1424`（小周/小陈 desc）、`1582`×2（`concept shift-swap` desc + 陈默 memory）、`1141`（`kb[林瑶]` !always 值班表） |
| 货架 | 看见/拿 → items | 3 | `items/一包零食.md:3`、`items/一瓶饮料.md:3`、`locations/小卖部.md:5` |
| 冰柜 | 看见/拿 → items | 2 | `items/一瓶饮料.md:3`、`locations/小卖部.md:5` |
| 柜台 | 看见/拿 → items | 1 | `items/一瓶饮料.md:3` |
| 关东煮 | 看见/拿 → items | 2 | `items/一碗关东煮.md:3`、`locations/小卖部.md:3`（“一台关东煮”，与已注册的“一碗关东煮”不是同一个东西） |
| 例汤 | 看见/拿 → items | 2 | `items/一份餐食.md:3`、`locations/食堂.md:5`（“今日例汤”黑板） |
| 热水壶 | 看见/拿 → items | 2 | `manifest.yml:1160`（宿管阿姨常驻行“热水壶是她的情”）、`characters/宿管阿姨.md:5` |
| 电话 | 联系 → actors/联系人 | 2 | `manifest.yml:1455`（`concept archive-keeper` desc“重大事项要电话报备”）、`manifest.yml:76`（`location 校史档案室` rules[2]） |

关于 **12345**：种子里没有这个号码，它是模型在现场自己发明的公共热线（
`.scratch/v4-first-day/reports/m1-dot5-postrun-analysis.md` §1.5/§2.4，
19:36–22:00 的“借电话”循环）。种子侧的对应缺陷是上面两条「电话报备」：
一个“必须打电话”的规矩，而世界里没有任何可联系的对方——所以角色只能自己造一个号码。
门对号码本身也有检查（≥5 位数字必须是一个 actor 或 kb 联系人，今天种子里没有号码）。

修法：

1. **公告栏**：注册成 `documents:` 行（票 77 已裁定这条编码，见
   `test_world_pack: test_a_notice_board_is_a_document_and_read_already_covers_it`）。
   建议按板注册（`学生会办公室公告栏` / `教学楼公告栏`），`content` 就是此刻张贴的内容；
   `read` 的目标类就是文书，`actionable_refs` 让它在房间里可读。
2. **值班表**：注册成一份 `documents:` 行（这周排班的表）——它本来就是“这周为什么换了人”
   的物证，角色应当在档案室/学生会办公室读得到。
3. **货架 / 冰柜 / 柜台 / 关东煮 / 例汤 / 热水壶**：注册成 `items:` 行
   （`location` + `known_to` + `items/<id>.md` 描述；不可读给 `readable: false` +
   `readable_reason`），描述走知觉与 ticket-49 的 observed 路径。票 77 的
   `PrimitiveSufficiencyTests.test_stock_and_fixtures_are_item_descriptions_in_perception`
   就是这条编码的样板（关东煮锅 = items 行，描述走知觉）。
   只建“问题中那个东西”的行（关东煮锅、菜牌、热水壶），不要把整间店拆成家具清单。
4. **电话**：让“接电话的那个人”成为一个 actor（或某角色的 kb 联系人行），
   或把这两条规矩改写成不需要拨号的表述（“重大事项报备给[[档案室管理员]]”）。

## 6. 建议的修复顺序（按“解掉的违规数 / 顺带解开的故事锚点”排）

1. **值班干事 + 档案室管理员 → 既有 actors 行**（一次同时清 G1 的 7 条、G2 的 19 条，
   并给 d1-林瑶自查审计包 一个真的在场宿主）。这是全清单最高杠杆的一条。
2. **公告栏 → documents 行**（清 G4 15 条，并解掉 d1-pm 10:49–13:35 的公告栏循环族）。
3. **泛称的 `role_prose` 声明**（值班学生/老板娘/负责人/老师/编辑/记者/学生馆员/师傅/
   阿姨/大爷/代表，约 27 条）——纯声明，不改正文，风险最低。
4. **仓库与摊位实物 → items 行**（关东煮锅/热水壶/菜牌/货架/冰柜/柜台，清 G4 12 条）。
5. **后街糕点铺**：注册地点+路由，或把常驻派工改成电话/托人（G3 1 条 + 一条死任务）。
6. **哨子/雨伞**：`completeness: expectation`（G3 2 条）。
7. **值班表 → documents 行**（G4 5 条）。
8. **电话报备**：绑定接电话的人或改写（G4 2 条）。

## 7. 验收

```text
cd v4
python3 scripts/seed_lint.py                       # 期望：exit 0，seed lint OK 且无 seed contract 行
python3 scripts/seed_lint.py --verbose             # 同上，附 advisory 清单
python3 -m unittest harness.tests.test_historical_failures.SeedContractGateTests
python3 -m unittest discover -s harness/tests -p 'test_*.py'   # 全套（extra 时序家族偶发 1 红）
```

修完种子后本清单的每一条都应消失；**不要**改 `scripts/seed_lint.py` 的词表去消数字——
门报的是故事做不到的事，词表放宽等于把契约改小。

## 8. 门的边界（已知限额，改种子时请照此理解）

1. **不做逐名词 NLP**：词表受控（角色类名词后缀表、需交互名词表、施动动词/缺席写法表），
   所以“爷爷/儿子/姑娘/同学/老人”这类泛称不在门内；遇到没覆盖的同类缺陷，
   正确的动作是把词加进 `scripts/seed_lint.py` 的受控表，而不是绕着写。
2. **引号内是转述**：G1 只看引号外（`'…'`/`"…"`/`“…”`/`「…」` 内的内容属于某个角色的
   话，不是世界的客观陈述）。`admin_reply` 的“原管理员因家事请假”也因此是合法缺席写法。
3. **地点 extras 的 fragment 不扫**：那就是“这个地点常出现的陌生人”的声明本身；
   它的 `knowledge_notes` 扫。
4. **远程地点**（`remote: true`）不按步行走路判；但放在那儿的实物没有路径照样报（见 §4）。
5. **四门走独立通道**：`lint()`（名字解析契约）的语义不变，四门由 `contract_gate_findings()`
   计算、CLI 一起跑一起判失败。两个通道的历史各自可核，旧票据测试不受影响。
6. **`role_prose:` 只被 lint 读**：它是种子作者给门看的声明，不进入模型可见文本
   （`world_loader` 不认识这个键）。拼错键名等于没声明，门会继续报同一条。
