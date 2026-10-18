# 72 — d1-pm 六个 FAIL 锚点的种子层修复（M1.3）

Status: fixed
Need-review: yes
Need-test-cases: no

> 2026-10-16 实施。权威输入：`reports/70-d1pm-anchor-root-causes.md`（逐项修法）
> 与 issue 70。边界：只写 `v4/world/` 种子层与新建本票；harness/、
> scripts/check_milestones.py、docs/ 一律未动。全部修法为"给机制补路径"
> （排程/道具落点与 target/知识注记/共同在场/收集排程/D2 预设对齐），
> 遵守"里程碑是下限不是剧本"——只铺时机与台阶，不写任何角色台词；
> 审计包谜底仍只在文档正文（ticket 47 契约），场合通知不剧透核对结论。

## 逐锚点改动（file:line 证据）

### 锚点 5 d1-审计催办转达（唯一 anchor，优先实施）
- `world/manifest.yml:817` 新增 `audit_relay_task`（16:05，`target: 陈默`）：
  班长捎来值班干事的话——催办单落点（办公室门缝）、催办单原话（"审计核对仍未
  完成，说明最迟明早交"）、转达职责（"由你转告[[辅导员]]协办"）；带
  `actionable_refs` read 审计催办单@学生会办公室（issue 35 覆盖契约）。
- `world/manifest.yml:1121` 陈默 KB 常驻行 `keys: [催办单, 审计催办]`：
  转达职责进入他的持久知识（不止 16:05 一次性感知）。
- 送达/职责两条断链（报告 §5：催办单有实体、无送达、无职责挂钩）各自补上。

### 锚点 1 d1-辅导员介入 + 锚点 2 d1-三份个人说明（同一处改动覆盖两项）
- `world/manifest.yml:831` 新增 `counselor_procedure`（16:30，`target: 辅导员`，
  唤醒她）：辅导员定程序——涉事学生各自提交**个人情况说明**，对外**统一口径**，
  最迟明日交。
- `world/manifest.yml:835` 新增 `statement_request`（16:45，广播）：程序同步到
  班群与公告栏，四个涉事角色（陈默/林瑶/林瑶室友/班长）由此都有可响应的场。
- `world/characters/辅导员.md:21` 知识注记补"个人情况说明、统一口径"程序词汇，
  本场目标示例补"程序介入"——词汇成为她的稳定倾向而非一次性通知。

### 锚点 4 d1-妈妈承诺
- `world/manifest.yml:846` 新增 `mom_evening_call`（19:30，`target: 陈默`）：
  上午例电没接住，晚间补打（落实她角色页 :21 既有的"周一早晨为补打"设定）；
  末句留开口（"学校里都忙些什么"），托付与应承都不写死。
- `world/characters/陈默妈.md:21` 本场目标示例补"应承打听（……**问不到**就直说，
  不编不拖）"——承诺措辞成为她的行为倾向。
- `world/manifest.yml:1125` 陈默 KB 常驻行 `keys: [家属院旧事, 旧记录, 纪念活动]`：
  纪念通知里"旧记录"一出现即浮出的托付钩子（报告修法 4.3）。注：曾先写为
  `!at=3/16(周一) 15:10` 定时行，因 `test_mc_seeds_carry_always_and_scheduled_rows`
  的"每 MC 恰好一条 `!at` 行"契约（test_world_pack.py:634-640）改为常驻知识行。

### 锚点 3 d1-老周托话
- `world/manifest.yml:811` 新增 `laozhou_word`（15:30，`target: [下棋大爷, 食堂大妈]`）：
  闭餐整理空当大爷到食堂托大妈带话（纪念活动要整理 2013 年旧记录，中庭石桌随时
  开讲）——托话链第一环的共同在场排程。**对报告的偏离登记**：报告示例时间为
  午市后 12:10，但该锚点门禁只计 pm 窗（13:00–22:00）事件（check_milestones.py:37,44,1504-1507），
  故移至 15:00–16:30 闭餐整理空当，也贴合大妈"怕冷场"的人设。
- `world/manifest.yml:1291` 食堂大妈 contacts 增 `{of: 下棋大爷, as: [老周]}`、
  `:1315` 下棋大爷 contacts 增 `{of: 食堂大妈}`（issue 66 对称规则；advisory
  对称检查通过）。大妈由此获得"老周"KB key——她的卡与定向通知里的 [[老周]]
  才能对她解析。
- `world/characters/食堂大妈.md:21` 知识注记补"下棋大爷（老周）是几十年的老熟人，
  托她带话是常有的事"（常驻熟人基础，不预写本次托话这一实例）。

### 锚点 6 d1-林瑶自查审计包
- `world/manifest.yml:825` 新增 `audit_pack_review`（16:20，广播）：期限已过，
  值班干事按规程当场摊开审计包逐项核对，请经手/核过材料的同学到场面核——
  给审计实质一个进入公共言语的**场合**。通知只铺场合，不说出核对结论
  （"凭证不在包里"等谜底只在 `学生会审计包` 正文，由角色读到后自己说出）。

### D2 跨日预设矛盾的对齐（任务清单第六项）
- `world/manifest.yml:864-867` `statement_receipt` 措辞对齐：原"三份个人情况说明
  **已收齐**并分别封存"断言了 D1 机制从未保证的结果；改为"个人情况说明按昨日
  定的程序在收，**收到的**已分别封存，今日随审计材料一并向院系办公室正式报备"
  ——收多收少都自洽（原措辞/新措辞登记见下节）。
- `mom_text_result`（manifest:869 起）**保留原文**：报告跨项发现 3 裁定 D1 侧补
  排程即自洽（D1 晚间接线 + 应承打听 + 陈默钩子使"托付→打听"有了机制路径）；
  其措辞复核移交 M2.1 D2 种子定稿。

## needle 措辞化石登记（原措辞/新措辞/对应锚点；判定层零改动）

| 锚点 | 判定 needle | 种子侧对齐方式（原措辞 → 新措辞） |
| --- | --- | --- |
| d1-辅导员介入 | "统一口径"、"个人情况说明" | 全种子原 0 命中（涌现措辞化石）→ `counselor_procedure`/`statement_request` 通知与辅导员.md:21 注记直接引入原词（词不变，补出处） |
| d1-三份个人说明 | "情况说明"（⊂"个人情况说明"） | 同上，任一角色复述程序即命中 |
| d1-妈妈承诺 | "问不到" | 全种子原 0 命中 → 陈默妈.md:21 应承打听倾向引入原词 |
| d1-审计催办转达 | "催办单" | 种子本有（document/manifest + concept reminder-slip）；补的是送达与职责路径 |
| d1-老周托话 | "老周" | 种子已注册（actor-chess-uncle 别名）；补大妈侧 key（contact alias）与同场排程 |
| d1-林瑶自查审计包 | "凭证"或"未标用途" | **"未标用途"未对齐**：种子正文措辞是"没有标注用途"，与 needle 不构成子串；但 `ok = (n+n2)>=1` 中"凭证"一针即可通过（审计包正文含"报销凭证"）。改种子正文迎合 needle 会扭曲客观文本，不做——登记为残留风险，M1.5 复核；若 M1.4 仍卡此锚，走报告 §6 修法 2 的判定层放宽路径（须先红后绿并登记历史失败，归 M1.3 owner 裁决） |

## 验证输出（绑定当前工作树；注意并行改动声明）

1. `python3 scripts/seed_lint.py` → `seed lint OK: every named thing resolves to
   an entity or concept`，exit=0（新具名 token 全部经既有注册解析：[[老周]] 走
   contact alias，[[老家属院]]/[[审计催办单]] 等走实体标题；无新 concept 注册需求）。
   仅既有 advisory warning（name collision ×6、2013年台风台账 known_to、ticket 66
   单向通讯录清单），无本票新增项。
2. `OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s
   harness/tests -p 'test_*.py'` → `Ran 573 tests in 284.553s — OK (skipped=1)`。
   **全绿**。已知 flake 项（test_extra_turns_are_recorded_and_conversational，票 73）
   本遍未失败——与票 73 的间歇性定性一致。
3. `python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'`
   → `Ran 130 tests ... OK`（历史失败门、确定性终点门、dead-end 门全绿）。
4. 针对性复验：`test_mc_seeds_carry_always_and_scheduled_rows` +
   `test_scheduled_keys_are_strictly_parseable` + `test_key_sets_are_unique_per_actor`
   → OK（`!at` 行数契约修复后）。
5. **并行改动声明**：本机工作树含其他代理未提交的 harness/ 改动（kb.py、
   kernel.py、test_historical_failures.py、test_kb.py、test_kernel.py）与票据
   69/70 更新，均非本票所为、本票未触碰；上述回归结果绑定的是该混合工作树
   （种子改动 + 并行 harness 改动共存状态），独立复核时应以此为准并核对 git diff 归属。

### 首遍全量的一次性失败归因（如实记录，勿重复修）

本票首次全量 discover（`!at` 修复前）出现 2 个失败：
(a) `test_mc_seeds_carry_always_and_scheduled_rows`（2 != 1）——**本票种子改动
导致**（陈默两条 `!at` 行违反"每 MC 恰好一条"契约），已按契约改为常驻知识行，
复验通过；
(b) `test_silent_abandonment_auto_continues_pending_action`——**非本票导致**，
归为 discover 顺序/负载敏感的间歇性 flake（票 73 同类）。依据：该测试用合成世界
（test_engine.py:19-25 `_world()`，actors a/b、room/far），完全不加载 world/ 种子；
单独跑 OK、test_engine 模块 31 tests 合跑 OK；同日复跑全量 573 tests 全绿。
本票未改 harness/（票 73 的修复归其 owner）。

## M1.4 起点判定：**从原始种子跑**（不从 checkpoints/d1-am.json 续跑）

每处修复对 D1 上午（07:00–12:59）的影响判定：

| 修复 | 事件时间窗 | 影响 D1 am 事件？ |
| --- | --- | --- |
| audit_relay_task + 陈默催办职责行 | 16:05（pm） | 否 |
| counselor_procedure + statement_request + 辅导员.md | 16:30/16:45（pm） | 否 |
| mom_evening_call + 陈默妈.md + 陈默钩子行 | 19:30（pm） | 否（钩子为常驻 KB 行，07:00 起在库，但 keys 只被"纪念活动/旧记录"类词激活，am 窗内无对应排程事件，检索面影响可忽略） |
| laozhou_word + contacts + 食堂大妈.md | 15:30（pm） | 否 |
| audit_pack_review | 16:20（pm） | 否 |
| statement_receipt 对齐 | D2 | 否 |

六处改动均不触碰 D1 am 窗的排程、道具与事件。**但这不意味着从 d1-am.json 续跑
安全——恰恰相反，判定为不安全，且失配形式是静默缺事件而非加载报错**：

1. 世界队列在 checkpoint 里冻结：`harness/kernel.py:480`（restore_checkpoint 将
   `self._queue` 逐行重建自 checkpoint，base 世界只供静态定义）。6 个新排程事件
   （15:30–19:30）全不在 d1-am.json（12:59 冻结）的队列里，续跑后**一个都不会触发**。
2. 角色 KB 在 checkpoint 里冻结：`harness/engine.py:2529`（`if state.get("kb")` 时
   逐角色 `ActorKB.from_snapshot`）。陈默两条新知识行、大妈的"老周"key、三个角色页
   的导演注记，续跑后全部不在场。
3. `harness/resume_run.py:43-49` 自述契约："the checkpoint supplies every piece of
   mutable state"，种子 pack 续跑时只供 routes/capabilities 等静态定义。
4. 兼容性检查（format=v4-checkpoint-2、actor set 一致）都会通过——即**没有任何
   加载报错会提醒修复丢失**，按 fail_loud 原则必须在票面显式声明。
5. 附带收益：从原始种子起跑会重新覆盖 d1-am 段，am 三锚点（登记缺失知晓/台账差异
   记录/恋爱并肩）的旧 PASS 证据对新种子本已失效（invalidate 规则），重跑即重建。

**M1.4 执行口径**：`real_run` 从原始种子跑 07:00→22:00（或先跑 am 段存档新
d1-am 检查点再续 pm，两段均出自本次修复后的种子），产出唯一新工件 +
`checkpoints/d1-pm.json`，然后 `check_milestones.py --half d1-pm` 过门。

## 移交与残留风险

1. `test_historical_failures.py` 增两个防回归夹具（报告 §5.3/§6.3：催办送达路径
   存在性；"读取通过但言说场合缺失"形状）——harness/ 本票禁改，移交 harness 侧
   代理在票 73 修复后一并落。
2. "未标用途"needle 化石未对齐（见上表末行），M1.5 复核；必要时走判定层单独论证。
3. `mom_text_result` 措辞复核 → M2.1。
4. 本票只保证"机制给了路径"；角色是否走到（陈默是否真的转达、大妈是否真的带话）
   由 M1.4 新工件 + M1.5 运行后分析验证——种子修复不预测涌现结果。
