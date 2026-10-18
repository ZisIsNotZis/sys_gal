全部证据已收齐（22 次工具调用，未超预算）。我的工具集没有 shell/写文件能力，两项机械检查命令须由监督者执行、报告文件内容由运行时落盘。以下为完整报告工件（目标路径：`契约失效时请勿喂猫/.scratch/v4-first-day/reports/m1-dot3-review.md`）：

---

# M1.3 改动集独立复核报告（m1-dot3-review）

- 复核人：独立复核代理（fresh context，不修复、不提交）
- 日期：2026-10-16
- 对象：工作树相对基线 `ea47781`（仓库唯一快照提交，2026-10-15，见 ticket 69 Comments 的 git 取证；`watchdog_diff` 对 reviewer-launch HEAD 出 diff，单提交仓库下即该基线）的未提交改动，共 11 文件 +273/−16，外加 4 个未跟踪票据/报告文件
- 方法与边界：逐 hunk 读全量 diff + 定向读源码验证语义声明；只读代码，仅产出本报告
- **重大局限（如实声明）**：本代理工具集无 shell，**两项必做机械检查未能亲自执行**，命令与期望值见下节，须由监督者复跑后本报告才完全生效。代码级语义审查全部完成。

## 总体 verdict：**PASS-with-notes**（有条件放行 M1.4）

无 P0/P1 缺陷。三部分改动均符合各自约束，票据证据链完整且与代码实况一致。放行条件：监督者复跑两项机械检查并全绿（若再现间歇失败，按 ticket 73 §6.1 保留全量输出并定位身份）。

## 机械检查（命令、期望、现状）

```bash
cd 契约失效时请勿喂猫/v4
python3 scripts/seed_lint.py                                    # 期望：seed lint OK
OPENAI_MODEL=github_copilot/gpt-6-luna python3 -m unittest discover -s harness/tests -p 'test_*.py'
                                                                # 期望：Ran 575 tests — OK (skipped=1)
```

- 本代理未能执行（无 shell）。票据内留存的运行证据：ticket 71（lint OK；errors 9→0）、ticket 72（lint OK；573 tests OK skipped=1；历史门 130 tests OK）、ticket 73 §4（**修复后全量 575 tests OK skipped=1，281.503s**）。数字对拢：571（基线）+2（E71 回归）=573，+2（E72a/E72b）=575 ✓。
- **必须知悉**：ticket 73 §6.1 自述修复后全量 6 跑 = 2 红 4 绿（身份均未捕获），即**全量层稳定性未确立**，可能存在第二个负载敏感测试。复跑若红：保留完整输出、定位测试身份、记入 ticket 73，不构成本改动集的缺陷。

## 逐部分判定

### A) py3.14 计数器修复（ticket 71；kernel.py / kb.py / test_kernel.py / test_kb.py）— **PASS**

- `Count`（kernel.py:42-73）：`__next__` 单调步进、`__iter__` 返回 self、`__getstate__/__setstate__` 以 `(value, step)` 元组走 pickle/copy 协议、`__slots__`——与 `itertools.count` 在 `next()`/deepcopy/pickle 三个被消费的面上语义一致；`Count(-1,-1)` 保住正史负 id 空间（kernel.py:314→:356）。
- **与旧检查点逐字兼容（实读验证）**：`checkpoint_state()`（kernel.py:363 起）仍写 `next_sequence`（max 队列序+1）/`next_event_id`（len+1）int；恢复端（kernel.py:483-484）`Count(int(state[...]))` 与旧 `itertools.count(int(...))` 完全同义。KB 侧 `snapshot()`（kb.py:779）仍写 `shown_seq`（`next()` 消耗一次——旧语义就是消耗式），`from_snapshot`（kb.py:801）同义播种。**序列化 schema 零改动**，ticket 71 的兼容性声明与代码相符。
- 替换完备：v4 下 `itertools` 残留仅存在于注释/docstring（grep 全仓验证），6 处构造点全换、调用点零改动；kb.py 新增 `from .kernel import Count`，kernel.py 无反向导入，无循环依赖（kernel.py 头部仅 import action_schema）。
- 新回归有效：`test_world_deepcopy_survives_and_event_ids_stay_unique`（test_kernel.py:126-141，克隆后 id 连续无复用、原子独立）、`test_deepcopy_keeps_shown_seq_allocating`（test_kb.py:313-324，消耗式快照下等位、克隆后独立单调）。红→绿证据在票（修复前 errors=9 定向复现，含 stash 后基线对照，排除了本修复引入）。

### B) 六锚点种子修复（ticket 72 + 报告 70；manifest.yml + 三角色页）— **PASS，带 3 条 P2 备注**

- **门禁判定层禁改：核实成立。** `scripts/check_milestones.py` 与 `v4/harness/` 产品码均不在 B 的 diff 中（stat 全列核对）；harness 侧仅 A/C 的改动。
- **"只铺机制路径、无剧本台词"：6 处中 5 处干净。** `laozhou_word`（间接转述托话内容，措辞时机留白）、`audit_relay_task`（引催办单原文属文书引用+职责指派，非台词）、`audit_pack_review`（只开场合不泄谜底，符合 ticket 47 契约）、`counselor_procedure`/`statement_request`（间接陈述程序）均为间接语态；唯 `mom_evening_call`（manifest.yml:846-849）末句含妈妈的直接引语"最近学校里都忙些什么，说来妈听听"——见 P2-1。
- **跨日预设矛盾真解决**：`statement_receipt`（:864-869）"已收齐"→"在收，收到的已分别封存"，收 0 收 3 皆自洽；`mom_text_result` 保留原文的前提（D1 晚来电 + 应承打听倾向 + 陈默"旧记录"钩子行 :1125-1130）已在 D1 侧补齐机制路径。裁定合理。
- **needle 化石处理符合"不改判定层"**：判定 needle 实读核实——`凭证`/`未标用途` 并列求和（check_milestones.py:297-300）、`老周`（:267）、且 `d1-老周托话` 为 flavor + `half="pm"`（:852/:949）。据此：(a) 把托话从报告建议的 12:10 移到 15:30 的偏离**有据**（half 门只计 pm 窗）；(b) "未标用途"≠"没有标注用途"的子串失配属实（manifest.yml:473/:1598），但审计包正文含"报销凭证"（:1600），单"凭证"针即可过——不改客观正文、不放宽判定、登记残留，处置正确；(c) "统一口径/个人情况说明/问不到"三词经通知与角色页注记引入原词，属种子侧对齐，票内逐字披露（见 P2-2）。
- contacts 对称（:1289-1291/:1315，issue 66 规则）使"老周"对大妈可解析；陈默 KB 新增 `!at` 契约冲突已按 test_world_pack 契约改为常驻行——首遍失败 (a) 的归因与修复闭环在票。

### C) flake 收口（ticket 73；test_historical_failures.py）— **PASS，带 2 条 P2 备注**

- **断言零放宽（核实）**：唯一被改测试 `test_extra_turns_are_recorded_and_conversational` 的改动仅为 (1) `_call_pool().submit(lambda: None).result(timeout=5)` 预热共享池（engine.py:237 存在，导入有效）；(2) `extra_idle_seconds` 60→3600。`len(extra_turns)==2` 与"答案 ≤1 tick 落地"断言原样保留——属隔离/时序修复，不在禁改之列。despawn 本就不是该测试的被测行为，钉大 idle 窗不构成覆盖损失。
- 根因诊断质量高：线程池冷启动 vs 世界时钟飞驰 + idle-despawn 取消在途调用，探针 trace（`extra_removed 'idle' 07:03, stub_calls=0`）与代码逐环对上；"导入副作用"假说被活体证据取代的推理如实入票。
- **E72a/E72b 夹具确实能拦住缺陷形状**：E72a（:870-905）——删 16:05 `audit_relay_task` 或其 `target` → 无"晚于落点 + target 陈默 + notice 含单据与职责"的行 → 红；把转达挪到落点之前同样红。E72b（:906-929）——删 `audit_pack_review` → 无 pm 窗"审计包"场合 → 红；给场合加 target 收窄 → 红。两条均入台账（:73-95）并定向绿（票 73 §7 记录 2/2 OK）。
- **两个已知移交项确认如实记录**：ticket 73 §6.2 (a) `_horizon_bound` 只含 `_active_inflight()` 不含 `_extra_inflight`——**代码实锤**（engine.py:709-716，`_extra_inflight` 仅在 `_quiescent`:683 与 extra 簿记 :2272-2295 出现）；(b) idle-despawn 以纯世界时判定、取消在途回答且不落盘被丢弃的 pending 状态——**代码实锤**（engine.py:2150-2152）。两项按任务要求仅确认记录，不要求修。

### 票据 69/70 修订（.scratch）— 核实无异议

- 69 → wontfix：以 `find`/`ls` 取证声明 10-05/10-06 工件 **declared missing**（不可再生），复盘义务显式转 M1.4/M1.5，`Need-review: yes` 保留——符合"缺席是声明而非编造"，处置正当。
- 70：根因表与报告一致，status 诚实保持 `ready-for-agent`；**门禁语义口径冲突（half 逐项 vs --day 路线网 vs ROADMAP"12 项"）正确上报用户而非代决**。注意：此裁决未决不影响本次修复（按最严口径全修），只会放宽过门标准。

## 缺陷清单

- **P0：无。**
- **P1：无。**
- **P2（报告性，不阻塞）：**
  1. **B / 台词边界最近点**：`mom_evening_call` 通知含妈妈的直接引语（manifest.yml:846-849）。违反准则：ticket 72 自设"不写任何角色台词"；证据：五处皆间接语态、此处为直接引语；最小修法：改间接语态（"末了多问她学校里忙些什么"），语义不变。
  2. **B / 锚点过门的词汇性**：三个 needle 词（"统一口径""个人情况说明""问不到"）现以种子文本形式在场，锚点可凭词汇命中而非行为达成。票内已披露、有真实机制承载（收集程序/场合/倾向），非判定层改动的替代品；但 **M1.5 必须核查这些词出现在活的言语流中、且经由新铺的场合**，而非仅存在于种子。
  3. **C / 夹具脆度**：E72b 的 `all(not target)` 全称约束比缺陷形状更严（未来任何带 target 且提"审计包"的正当通知会误红）；E72a 未钉陈默 KB 职责行（只钉转达排程）。均为作者意图内的取舍，记录备查。
  4. **A / 前既有（非本 diff 引入，报告性）**：`_history_id` 无 checkpoint state 键，恢复后续排依赖"同一种子重建时 inject_history 消耗出相同计数位"（kernel.py:314/:356；restore 不重播种）。本 diff 未改变该行为，且 M1.4 从原始种子起跑使其无暴露面；唯未来"改种子正史后跨检查点续跑"可能静默撞 id——建议将来随引擎票一并补 state 键。
  5. **流程**：全量套件间歇失败未定性（ticket 73 §6.1，2 红/6 跑）——开放项，禁止对外宣称"套件级全绿稳定"。

## M1.4 放行建议

**建议放行**，且**从原始种子起跑**（勿从 `checkpoints/d1-am.json` 续跑）。ticket 72 的失配分析经代码核实成立：restore 从 checkpoint 重建队列（kernel.py:~500-507）与 KB（engine 侧 from_snapshot），6 个新排程事件与全部新知识/注记在 12:59 冻结点上**静默缺失且无加载报错**——按 fail_loud 必须显式择路，票已择。附带收益：am 三锚点旧 PASS 证据对新种子本已失效，从种子重跑即重建。执行时一并落两件事：监督者先复跑上节两条命令（期望 575 OK skipped=1）；M1.4 门禁报告中记录用户对门禁语义口径（half vs day）的裁决。两个引擎移交项（`_horizon_bound`/idle-despawn）已如实记录在 ticket 73 §6.2，按任务边界不阻本次放行，建议尽快另开引擎票——它们是"在途回答被静默吞掉"一类缺陷的现存活体通道，M1.4 大工件上再撞到会浪费一次全日跑。