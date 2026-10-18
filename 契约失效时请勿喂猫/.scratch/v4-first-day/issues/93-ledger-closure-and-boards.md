# 93 — 收尾第五轮：台账的结案时机（E94）与三块“钉住的板”

Status: fixed
Need-review: yes
Need-test-cases: yes

> 输入：票 91 §4-2（`Ledger.query` 的 `limit` 分支在正常流程下不可达）、票 91 §4-1（三个公告栏要
> 补 `takeable: false`）、用户裁定 2026-10-18。
> 范围：`v4/harness/`（`system.py` / `engine.py` / `world_loader.py` + 测试）、`v4/docs/`，
> 以及 `v4/world/manifest.yml` 的**两处**（用户明确放开的种子改动：`system.settle_on` 与
> `scheduled: ledger_settlement`）与三块公告栏的 `takeable/fixed_reason`。没有新增动作种类、
> 没有新增世界状态字段。

## 0. 裁定与一处必须先澄清的缺口

裁定原文：**结案由种子排程的结算事件驱动**（既有 `system_reward_granted`/结算路径），首次命中不结案；
查询次数按既有上限递减，超限后闭口（只回“闭口”，不再消耗，也不结案）。

开工先查证了一件事：**种子里原本没有任何结算事件**——`system:` 块只有
`name/bound_actor/case_id/terms/reward/query_limit/facts`，`scheduled:` 全部 92 条事件里没有一条台账结算
（唯一出现“台账”二字的是 `accessibility_check`，那是无障碍改造的另一本台账；`files_closed` 是档案归档）。
若只改 harness/，真种子会变成“答一次 → 超限闭口 → 案件永不结案、`system_reward_granted` 永不发放”，
即把机制修成**永远不结案**——那是功能洞，不是语义正确。此冲突已上报用户，答复是：

- 选 **A**：`system:` 加 `settle_on: ledger_settlement`，`scheduled:` 加一条 `ledger_settlement`（3/22 15:00，
  对应 `V4-STORY-MILESTONES.md` §3 的 d7「台账结算」）；
- 走既有 `system_reward_granted` 私有投递路径；**不绑定、不改动 `memorial_ceremony`**，结算文字不剧透 2013；
- 文件范围放开这两处（仅这两处），并要求验收补一条真种子冒烟。

## 1. 台账的结案时机（E94）

### 1.1 机制

| 位置 | 改动 |
|---|---|
| `harness/system.py:161` `Ledger.settle(world, cause)` | 结算节拍到达时结案：`status = "closed"`、`reward_granted = True`，报酬走**既有** `system_reward_granted` 私有事件（`visible_to == 受约束角色`）。`evidence_event_id` 指向这案唯一那条答案（没答过就**不带这个键**，不拿空值顶）；`settled_event_id` 指向那条排程事件；`condition` 改为 `seeded settlement beat`（诚实：结案的条件是节拍到了，不是“答对了”）。幂等：非 `accepted` 或已 `closed` 时返回 `None`、零事件。 |
| `harness/system.py:215` `Ledger.query` | 命中只提交 `system_answer`、`queries_used += 1`、记 `last_answer_event_id`（`:242`）——**不结案、不发报酬**。额度用尽仍走既有 `limit` 拒绝（只回“闭口”，不消耗、不结案）；`closed` 只在结算之后出现。`status` 终态从 `completed` 改为 `closed`。 |
| `harness/system.py:196` `Ledger._reconcile` | `Ledger` 本身不进检查点（`real_run`/`resume_run` 按种子重建），所以 `queries_used` 与已结案从世界日志重建（`system_answer` / `system_reward_granted` 都只由本台账产生、都在检查点里）：恢复后案子不会又开着，也不会白送一次新额度。（顺带修掉一个旧缺口：恢复后额度曾归零。） |
| `harness/engine.py:874` `_after_advance` | 扫描新事件时只认 `event.payload["event"] == self.system.settle_on` 那一条 → `self.system.settle(self.world, event)`。不是“任何世界事件”，同一个 advance 里的其它节拍不会结案（负向守卫见 §2 的红绿表）。事件驱动而不是轮询：结案与开关在世界日志里可审计、replay 前缀一致。 |
| `harness/world_loader.py:731-739` | 加载时校验 `system.settle_on` 能在 `scheduled:` 里找到同名事件；找不到就 `ValueError`（点错名字 = 永不结案，且要到那一天才看得出来，所以在加载时大声失败）。 |
| `world/manifest.yml:17` / `:1413` | 种子事实：`settle_on: ledger_settlement` 与 `{event: ledger_settlement, time: 2026-03-22T15:00:00+08:00, target: 陈默}`。后者只有一句中性到点叙述（“你心里那桩一直开着口的事到了该了结的时候：台账那边静了一瞬……”），不含任何 2013 内容，也不与 `memorial_ceremony` 绑定。 |

文档同步：`docs/V4-AGENT-INTERFACE.md` §5 台账一条（写清“结案 ≠ 首次命中”、`settle_on` 与 d7 的对应、
结案后才闭口）、`docs/V4-ENGINE.md` §7.6 的 `converse` 行 + 新增 §7.7（机制与回归）、
`docs/V4-STORY-MILESTONES.md` §3 的 d7-台账结算一行（补上驱动它的排程事实）。

### 1.2 红→绿（`python3 -m unittest harness.tests.test_historical_failures.LedgerClosureGates`）

新增 5 支（`test_historical_failures.py:6653`），台账条目 E94 写进该文件顶部的失效台账（`:331`）。

| 支 | 断言 | 旧语义下的读数 |
|---|---|---|
| `test_two_hits_in_a_row_each_produce_an_answer_and_the_case_stays_open`（①） | `query_limit: 2` 的台账连问两条不同条目（走 `_execute_chain` 的 speak 通道）：两条 `system_answer` 且答案各自对应条目、`queries_used == 2`、`status == "accepted"`、零 `system_reward_granted`、两次回执都 `ok` | **红**：`['老家属院的地下室'] != ['老家属院的地下室', '学生会审计核对，2026-03-16T16:00:00+08:00']`（第一问就把案子关了，第二问闭口） |
| `test_after_the_limit_the_ledger_silences_without_closing_the_case`（②） | 第三问：回执含“用尽”而**不含**“已经了结”、`queries_used` 仍 2、`status == "accepted"`、零报酬 | **红**：`1 != 2`（只有一条答案） |
| `test_the_seeded_settlement_beat_closes_the_case`（③） | 答过之后 `status == "accepted"`；`world.advance` 到节拍时刻 + `engine._after_advance()` → `closed`、恰好一条 `system_reward_granted`、`visible_to == {陈默}`、`evidence_event_id` 指向那条答案；结案后再问 → “已经了结”、不再产生答案 | **红**：`'completed' != 'accepted'` |
| `test_a_world_beat_that_is_not_the_settlement_keeps_the_case_open`（负向守卫） | 同一个时刻触发的是别的世界节拍（`morning_bell`）→ 仍 `accepted`、零报酬 | **红**（该支钉的是新契约：旧语义下此时早就 `completed`） |
| `test_the_real_seed_schedules_the_settlement_and_it_closes_the_case`（真种子冒烟，用户要求） | 真种子：`settle_on == "ledger_settlement"`、排程里**有且只有一条**、时刻 `2026-03-22T15:00:00+08:00`；D1 答对后仍 `accepted`；advance 到 3/22 15:00 + `_after_advance()` → `closed`、恰好一条 `system_reward_granted`、`visible_to == {陈默}`、`reward` 等于种子那句；**其余 8 个角色跨 6 天一条 `system_*` 都没收到** | **红**：`'completed' != 'accepted'` |

变异对照（可复算）：把 `harness/`、`world/`、`scripts/` 复制到 `/tmp/mut93`，把 `query` 改回“命中即
`completed` + 发报酬”、把 `_after_advance` 的结算转交改成 `if False:`，再跑同一批点类 →
**5/5 转红**（命令与输出见 §5）。

加载期守卫另有 2 支（`test_world_pack.py:1187` `LedgerSettlementSeedTests`）：`settle_on` 点名一条不存在的
事件 → `ValueError: system.settle_on names an undeclared scheduled event …`；点名真事件 → 正常加载。
去掉 `world_loader` 那段校验后第一支转红（`ValueError not raised`）。

### 1.3 按新语义重写的既有测试（旧行为依赖，已核对每一条的量尺）

| 测试 | 旧断言 | 新断言与理由 |
|---|---|---|
| `test_kernel.py:364`（原 `test_ledger_reward_is_emitted_only_after_seeded_objective_condition`）→ `test_a_correct_answer_does_not_settle_the_case` | 命中后 `status == "completed"`、`event_log[-1]` 是 `system_reward_granted`、`condition == "correct objective fact query"` | 命中后 `event_log[-1]` 是 `system_answer`、`status == "accepted"`、无报酬；另加 `test_the_seeded_settlement_closes_the_case_and_grants_the_reward_once`（`:385`）钉结算：`closed`、报酬 `visible_to == {陈默}`、只发一次、结案后查询报 `context["ledger"] == "closed"` |
| `test_runner.py` `test_system_reward_feedback_reaches_bound_character_in_natural_language` | `system_*` 序列含 `system_reward_granted`、报酬文本出现在**回合**流里 | 序列到 `system_answer` 为止且 `status == "accepted"`；答案文本仍在下一回合的知觉里；`ledger.settle(world)` 之后才断言报酬事件（`visible_to == {陈默}`）与 `render_world_message(world.poll("陈默"))` 里的报酬文本。测试标题（“系统反馈以自然语言到达受约束角色”）因此仍在，只是报酬那半挪到结算时刻 |
| `LedgerDialogueGates.test_the_query_limit_itself_closes_the_ledger` → `test_the_query_limit_silences_the_ledger_without_closing_the_case` | 名字说“limit 自己结案” | 回执仍是 `limit` 那句、零事件，但 `status == "accepted"`（额度用尽 ≠ 结案） |

## 2. 三块公告栏（票 91 §4-1 的种子侧）

| 位置 | 改动 |
|---|---|
| `world/manifest.yml:740-741` | `公告栏`：`takeable: false` + `fixed_reason: 整块板钉在门边的墙上，只能就地看着读上面贴的纸。` |
| `world/manifest.yml:757-758` | `教学楼公告栏`：`takeable: false` + `fixed_reason: 玻璃公告栏嵌在正门内侧的墙里，纸角能掀，板抬不走。` |
| `world/manifest.yml:782-783` | `女生宿舍公告栏`：`takeable: false` + `fixed_reason: 软木公告栏钉死在一楼大厅的墙上，只能站在跟前看。` |

理由各不相同（板/玻璃嵌墙/软木钉死），没有一句共用模板；`read` 照旧可用——钉住的是“能不能拿走”，
不是“能不能看”。缺省仍可拿（`场地申请表` 那种让人自取的纸一字未改）。

**红绿**：`test_world_pack.py:1542` `PlaceBoundDocumentTests.test_the_three_seeded_boards_are_fixed_fixtures`
（真种子）——三条都进 `world.fixed_items`、各带非空理由、开局都在原处、`take` 候选里没有它们、
`read` 候选里仍有一个、`take` 的拒绝理由用种子那句原文、拒绝后板还在原处且没进背包。去掉三条声明
后转红：`'公告栏' not found in {'货架': …, '冰柜': …, '柜台': …, '关东煮': …}`（只剩小卖部那四件陈设）。

## 3. 回归读数（收尾实测，`cd 契约失效时请勿喂猫/v4`）

```text
python3 -m unittest discover -s harness/tests -p 'test_*.py'
  641 支（基线 632 = 票 91 收尾读数；本票 +9：LedgerClosureGates 5 + LedgerSettlementSeedTests 2
        + 真种子三块板 1 + test_kernel 拆成 2 支 +1）
  连跑 2 次：1 次 OK (skipped=1)、1 次红 1 支 = test_silent_abandonment_auto_continues_pending_action
  （`test_engine.py:125` `action_resumed` 未出现；票 91 §3 已登记的半硬币家族：单跑曾 5 红 5 绿，
  本票接手后单跑 6 次全绿；它用非 v4 的 `Scripted` agent、`system=None`，不经过本票任何一行）
python3 -m unittest discover -s harness/tests -p 'test_historical_failures.py'
  188 支（票 91 读数 183，+5）；本次收尾 OK
  （会话中另有两次单支红，都是既有的 extra 间歇族、与本票无关：
   `test_extra_turns_are_recorded_and_conversational`（票 73 §6.1 登记）与
   `test_extra_envelope_is_never_broadcast_as_speech`，同一模块内的时序断言）
python3 -m unittest discover -s harness/tests -p 'test_world_pack.py'
  75 支 OK（票 91/票 92 读数 72，+3：三块板 1 + settle_on 2）
python3 scripts/seed_lint.py
  seed lint OK（findings 0 / contract 0），warning 8 条——与票 91/92 同数同族
  （6 条名字撞车 + 《2013年台风台账》known_to 空 + 通讯录不对称），本票没引入新 warning
python3 -m unittest harness.tests.test_historical_failures.PersistentNoteGates
  6 支 OK（含 runs/archive-20261016-attempt1/d1-am.json 的加载）
```

向后兼容：`runs/archive-20261016-attempt1/d1-am.json` 仍可加载（该归档的 world 日志里只有一条
`system_case_accepted`，没有答案与报酬，恢复后的台账状态与之前一致）；旧语义产生的工件里若有
`system_reward_granted`，恢复时 `_reconcile` 会把案子当已结案——那也是事实（报酬确实发过了）。

## 4. 仍然开着 / 移交

1. **`query_limit` 仍是 1**：机制现在支持多次提问（①用 `query_limit: 2` 证明），但种子没改这个数字——
   要不要让陈默能问第二条（“责任人是谁”“期限”），是产品/种子决定，本票不擅改。
2. **d12 的结算场景仍未排**：本票只落了用户点名的 d7（3/22 15:00）。`V4-STORY-MILESTONES.md` §3 的
   d12「结算不是宽恕」要求陈默陈述“继续做/停止做/不能承诺的事”，那是第二个节拍（且需要种子写清
   系统只给种子载明的客观澄清），不在本票范围。
3. **同步 `Runner`（遗留驱动）不接结算转交**：与票 91 §4-4（它也不接对话通道）同族；v4 生产入口
   （`real_run`/`resume_run`）走 `AsyncEngine`，不影响真实轨迹。
4. **结算节拍本身会给陈默一条 world_event 叙述**：`ledger_settlement` 带 `target: 陈默` 与一句中性到点话，
   同点再收到台账的履约句（两句话描述同一拍）。种子里不带 notice 会渲染成“发生了一件事：ledger_settlement。”
   ——那才是泄漏内部 id，所以选了带一句中性叙述；若下一窗口觉得重复，删的是那句 notice，不是节拍。

## 5. 复算命令

```text
cd 契约失效时请勿喂猫/v4
python3 -m unittest harness.tests.test_historical_failures.LedgerClosureGates
python3 -m unittest harness.tests.test_world_pack.PlaceBoundDocumentTests
python3 -m unittest harness.tests.test_world_pack.LedgerSettlementSeedTests
python3 -m unittest harness.tests.test_kernel.WorldTests  # 两支台账语义
python3 -m unittest discover -s harness/tests -p 'test_*.py'
python3 scripts/seed_lint.py
```

变异对照（旧语义 → 5/5 转红）：

```text
rm -rf /tmp/mut93 && mkdir -p /tmp/mut93 && cp -r harness world scripts /tmp/mut93/
# 1) query 恢复“命中即 completed + 发 system_reward_granted”
# 2) engine._after_advance 的结算转交改成 if False:
cd /tmp/mut93 && python3 -m unittest harness.tests.test_historical_failures.LedgerClosureGates
  → Ran 5 tests … FAILED (failures=5)
```
