# 35 — 客观种子通知声称存在的办事物件仍未进入世界状态

Status: ready-for-agent
Need-review: yes
Need-test-cases: yes

## 重大缺陷复现
最新 GPT-6 Luna 3/16 上午工件 `v4/runs/real-20260928T205206+0800-1345945-532332572.json`：07:30 `shift_reminder` 和 08:10 `校史档案室_shift` 都以客观通知断言“签到本在门口桌上”，但 manifest 没有注册“签到本”的 item/document，也没有将其放到档案室的 effect。陈默 07:38 `take(登记本)`、08:11 `read(签到本)`被正确拒绝；林瑶 07:37 `take(档案室登记本)`也失败。若设计是“本该在、现在失踪”，通知应明确为旧规程/预期而不是当前世界事实，且同名物件应有注册实体/失踪状态供查证。当前玩家被世界权威误导，却不是角色理解差。

同日 `kb` 的林瑶 `!at=3/16(周一) 12:30` 行要求交“场地申请表”，但 manifest 既没有该表、空白纸/笔的可定位物件，也没有正式收件人/提交工具路线。她在 12:30 前后经多人询问仍不知渠道，12:58 又反复追问何同学是否真的交来纸笔；只是口头说“递给你”不会创造实物或申请事件。此可作为有代价的失败剧情，但必须由明确可操作的资源/权限缺口构成，不应因世界未建模而只能重复追问。

最新 v4 的 `actionable_refs` 是逐事件**自愿声明**：`audit_notice` 与 `counselor_office_opens` 声明了，`shift_reminder` / `校史档案室_shift` 却没写，所以 lint/test 绿仍允许客观物件声明悬空。直接靠再给这两条补 refs 会修样例，但不是系统性覆盖。

## 验收方向
1. 区分“当前存在”与“规程预计/角色信念/已失踪”：客观通知不得断言不存在的物件当前所在。为可操作物件建立注册描述、位置/缺失状态及合法动作，或把通知改成准确的预期/不确定叙述；不由 notice 预演角色动作。
2. `actionable_refs` 覆盖门不能只检查声明过的引用：在 seed lint 加对客观 notice 与地点描述的高风险具体名词审计（规范标记/受控词表/结构化 props，选最小可行方案），要求每个“X 在 Y / 可从 Y 取、读、交”断言映射到真实 entity/place/effect，或显式标记为信念/预计/失踪。避免把所有普通名词变物品。
3. 回归：删掉注册/placement 但保留客观“签到本在门口”时 lint 红；保留“按惯例本该在，今日未找到”时合法且角色不可读取；申请表/纸笔/提交路径若剧情要求应有可验的取得或失败事件；检查器不把读档文本或到达时间等同申请提交。

- 2026-09-28, pi：本段 `check_milestones.py --half d1-am` 的台账差异锚点 FAIL（林瑶没读两份材料），另两项 PASS；这不证明她没学到差异，也不能降低世界一致性门。人手逐人审阅正在完成，不续下午。

## 裁决与实现（2026-09-29，AREA A+B）

系统性覆盖门已落地，不再逐样例补 `actionable_refs`：
1. **世界加载契约（`harness/world_loader.py`）**：新增行级 `object_presence`
   （`[{name, place, state}]`，`state = present|expected|missing`；`present` 必须与
   真实 placement 一致，否则加载即报错）与行级 `completeness`
   （`expectation|belief|missing`）。`_validate_scene_objects` 扫描每个排程
   notice 与地点场景文本，用“受控高风险物件词 ∪ 已注册 item/document id”+
   “物件词紧邻放置/取得线索”的就近匹配（不做逐名词 NLP）找出具体在场断言；
   断言必须由 `actionable_refs`／`object_presence`／`completeness` 之一承载，
   否则加载失败，`scripts/seed_lint.py` 输出确切修复文本。
2. **回归**：删掉 `签到本` 注册/placement 而保留客观“签到本在门口”→ lint 红；
   “按惯例本该在、今天未找到”+ `completeness: expectation` → lint 绿且角色
   不可读取（未放置）；具体物件断言不覆盖 → 红。测试：
   `test_world_pack.SceneObjectContractTests`（9 项，含上面三条与申请表/纸笔/
   拒收路径）、`HistoricalFailureGates.test_uncovered_concrete_prop_claim_blocks_the_seed`
   （台账 P10）。
3. **种子修复**：`签到本` 注册为 `校史档案室` 的真实 item，值班通知与档案室 KB
   行改写以区分它和缺失案里的 `借阅登记本`（后者也注册为真实 item，开局
   `location: null`，由 day-4 `ledger_found` 的 `add_item` 还原，附
   `object_presence: present`）；08:20 排程在 `学生会办公室` 张贴注册文档
   `场地申请表`（`actionable_refs` read/take）并加入 `可用纸笔` item；
   12:30 增加广播 `application_rejected`——本周不受理场地申请、无收件渠道
   （有界机构性拒收，明确措辞），使“找不到委员会”是设计内失败而非世界缺建模。

- 2026-09-29, /worker（AREA C）：本单提到的 `check_milestones.py --half d1-am`
  台账差异锚点 FAIL 由 issue 36 的路线网检查器解决（亲读互证/当面传达+承认
  待核，防上帝视角；见 36 与 `harness/tests/test_milestones.py`）。属同一
  `fix/v4-world-contracts` 分支，世界完备性门与棋盘修复（上节）不受影响。
