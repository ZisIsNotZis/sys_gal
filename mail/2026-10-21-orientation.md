kind:    report
from:    orient-sys_gal (package launched by root)
to:      root
spend:   idle-compute
id:      none — first contract, answered in the run final message

First orientation report, filed here by root. Body is the run report verbatim.

I have enough evidence. Writing the report (no files changed — read-only package).

---

# 报告：`sys_gal` 首次定向

**Report target:** root (`/home/z/vibe`) — 这是一份 `completion` 型报告：**decision = none 之外还有三处需要上层裁定的问题**（见 §3）。
**Spend:** idle-compute，只读；未启动任何 provider，未写任何文件。
**Abstract (EN):** `sys_gal` is a Chinese narrative-simulation research workspace whose only substantive project is `契约失效时请勿喂猫`. The active line is **v5** (ADR 0002): a 10-primitive engine + a concept library + per-story seeds, driven by a seven-story ladder S1–S7. Its gate is green today (87 tests, `v5_lint --strict`, `anti_cheat`). M0–M2 are done; M3 (actor pilot) has a committed model-run report, but only for S2 — S1 has no model pilot and no `agent_run.py`. Proposed next milestone: **M4 — 半日 + S3《夜市》**, whose skeleton is script-actor work and therefore needs no provider spend. Four questions I cannot answer are in §3; four defects found in §4.

## 1. 这个项目是什么

`sys_gal` 是一个**叙事模拟实验室**的仓库，不是游戏：目标是一个可复现的环境，其中自主角色只依据自身动机与合法获知的信息行动，世界按显式规则运行，任何一条轨迹都可以检查与回放（`CONTEXT.md:9-12`，`契约失效时请勿喂猫/README.md:1-13`）。

树里只有一个实质性项目，其余是它的版本线与归档：

| 目录 | 是什么 |
| --- | --- |
| `契约失效时请勿喂猫/v5/` | **当前主线**：引擎（十条原始项）+ 库（16 个动词）+ 库概念 + 种子；`engine/`、`library/`、`stories/`、`tests/` |
| `契约失效时请勿喂猫/v4/` | 参考线（归档）：中文沉浸接口、两层演员制、半天检查点环、剧情锚点检查器；保留为运行纪律的出处 |
| `v1/ v2/ v3/` | 历史归档，不得据以判断当前行为（`契约失效时请勿喂猫/v1..v3/README.md:1`） |
| `vendor/chinese-novelist-skill/` | git submodule，写作技能供给，与运行无关 |

v5 的核心设计是**三个受众分离**：引擎里只有十条原始项（`v5/docs/V5-PRIMITIVES.md:10-23`），模型只看见由库概念生成的日常动词，种子只写实例、制度与例外（`v5/docs/V5-ROADMAP.md:14-19`）。故事阶梯 S1–S7 每级换一个世界，因为"一个概念只在一个世界成立，它就不是库概念，而是那个世界的方言"（同上 `§2.1`）。

**今日实测状态（我自己跑的，不是引述）**：

```text
cd 契约失效时请勿喂猫/v5
python3 -m unittest discover -s tests -p 'test_*.py'   → Ran 87 tests ... OK
python3 scripts/v5_lint.py --strict                    → 通过（待补 5 项）
python3 scripts/anti_cheat.py --verbose                → 通过（2 支故事）
```

`v5_lint` 读数：状态键渲染 15 个已登记；库动词 16 个（copy/erase/examine/give/knock/move/open/place/read/recognize/speak/take/touch/unlock/wait/write）；故事 2 支；**待补 5 项**：`copy`、`erase`、`recognize`、`unlock`、`write` 各自只有 `s2_borrow_note` 真用过（已声明 2–5 支）。`anti_cheat` 读数：S1 三个可达结局、S2 四个，无具名祈使句、无天意事件。这个"待补"正是路线图 §2.1 那条孤儿规则的未结债务，而不是缺陷——它由下一支故事来还。

## 2. 建议的下一个里程碑

**M4 — 半日 + S3《夜市》**（`v5/docs/V5-ROADMAP.md:50`，权威定义在该行）

> 交付：制度角色、传递链、公开/私下感知、期限；半天检查点环与续跑。
> 验收：**押金条的每种归属都物理可达；当众与私下的信息差真实；续跑因果连续。**

**为什么是它，而 M3 不再作为"下一个里程碑"来推**——M3 是用户门（`V5-ROADMAP.md:49` "演员试点（用户门，先于花钱）"），它已经产出了自己的报告（`v5/docs/V5-M3-PILOT.md`，工件在 git 里：`v5/stories/s2_borrow_note/runs/agent-20261020T234959-2684263-baseline2/` 与 `…-pressure2/` 各含 `transcript.md`/`context.md`/`run.json`/`events.jsonl`）。按它自己写下的验收（"报告能回答这一局是被世界推动还是被作者推动，并附证据"），S2 这一半已经成立；剩下的是 S1 那一半与用户点头，见 §3 的 Q1。把 M3 当成"要继续做的工作"会把一次签字拖成一轮开发。

**M4 确实还没开始，逐条证据**：

1. **S3 不存在。** `ls -d v5/stories/s3*` → 不存在；`stories/` 下只有 `s1_last_bus`、`s2_borrow_note`。
2. **期限所需的中途打断没有。** `V5-PRIMITIVES.md:133` 自己写着："动作的中途打断：现在只有'耗时'，没有在飞动作与打断（S3 的截止时间会逼出它）。"这条是路线图预期的下沉点：M4 必须补"失败的场景 + 规则 + 渲染 + 测试"四件套。
3. **制度角色层只有 S1 的内容。** `v5/library/institutions.py` 的 `EFFECTS = {"arrive", "stops"}`，即"车到站/车熄火"；"谁有权收东西""到点来领"这类制度效果一条都还没有。
4. **检查点与续跑在 v5 里完全不存在。** `grep -rn "checkpoint\|resume" v5/{engine,library,stories,scripts,tests}` → 0 命中（只有 `provider` 相关命中）。而 M4 的交付里写着"半天检查点环与续跑"。按 `V5-ROADMAP.md §5` 与 ADR 0002 后果第 2 条，这一块**不重造**，从 v4 原样搬回（`v4/harness/resume_run.py`、`v4/scripts/half_day_flow.sh`）。
5. **成本纪律站在这一边。** `V5-ROADMAP.md §7`：`S1/S2/S3 的骨架用脚本演员跑，provider 只在里程碑边界花。` 所以 M4 的主体工作在无 provider、无预算的环境里就能完成并验收三分之一（可达性 + 公开/私下信息差）；只有"续跑因果连续"这一条需要一次真跑。

**建议的工作包切分（仅是提议，切分权在 root）**：

| 提议包 | 产出 | 可独立验收 |
| --- | --- | --- |
| S3 种子与卡司 | `stories/s3_night_market/{seed.yml,scenario.py,run.py}`：四块场地（摊区/管理处/巷口/旁摊）、五个角色、四条可达路径（认账/推给下一个/拿不回/当众澄清） | 四条路径各自可达 + `anti_cheat` 仍绿 |
| 期限与制度角色（库） | 到点触发、在飞动作与打断、制度角色的授权效果 + 渲染 + 测试 | `V5-PRIMITIVES.md:133` 那条暂缓决定被关掉，四件套齐全 |
| 检查点环与续跑（搬回） | 半天边界存档、因果续跑、唯一工件命名 | 从半天边界续跑后 event id/version 连续 |
| 预门收口 | v5 自己的历史失败台账（见 §4 D4）、孤儿债读数 | 预门在 M4 第一次真跑前全绿 |

**M4 开始前必须先绿的东西**：今天的三项门禁已经全绿（§1 实测），可以直接开工。

## 3. 它不能回答的问题

### Q1 — M3 算"通过了"吗？S1 那一半交付还在不在范围内？

- **为什么不能回答**：`V5-ROADMAP.md:57` 的状态行只写"**M3 已跑出第一份模型试点**"，没有写"已完成"；M3 又是用户门，签字权不在我这一层。而 M3 的交付栏（`:49`）要求 **"S1/S2 的真人模型首轮报告"**，实际只有 S2：`v5/stories/s1_last_bus/` 里没有 `agent_run.py`，`runs/` 只有 `a/b/c` 三条脚本路径（`git ls-files v5/stories/s1_last_bus` 可复核），S2 才有 4 个 `agent-*` 目录。
- **试过什么**：读 `V5-ROADMAP.md:49,57`、`V5-M3-PILOT.md` 全文；`git ls-files v5/stories/s1_last_bus v5/stories/s2_borrow_note`；`git log --oneline` 找" M3 完成 / 已批准 "一类提交 → 没有；`ls .scratch/` → 没有 issue 目录可查签字记录（见 Q4）。
- **什么会重新打开它**：用户一句"M3 过了"（或" S1 试点砍掉 "），或出现一份记录该裁决的 ticket/提交。在那之前，S3 的种子工作**不依赖**这个答案，可以并行推进——这是它不构成阻塞的理由。

### Q2 — 试点里被推到"M4 的制度层"的那条，属于 M4 吗？

- **不能回答的原因**：`V5-M3-PILOT.md §三` 最后一张表的第 2 行写着"乙直接拉开甲的抽屉、把借条拿走，除了被看见没有任何后果"，根因归给"世界有'谁能看见'，没有'这是谁的东西'"，处置是"**未修**：不改规则，改成让'看见'有社会后果（关系、责任、事后追究）"，并把这一层标成 "M4 的制度层"。但 `V5-ROADMAP.md:50` 给 M4 列的概念是**制度角色、传递链、公开/私下感知、期限**，不含"物权`. 这是"库要不要新增一个概念"的裁决，按 `V5-PRIMITIVES.md §9` 的第十一条门槛和 §2.1 的孤儿规则，它必须先被两支故事声明才准进库（S3 的押金条、S4 的钥匙移交都能用上），所以它既可能属于 M4，也可能属于 M5。
- **试过什么**：读 `V5-PRIMITIVES.md` P2/P3 的"不含"段（P3 明确把"隐藏"推到状态键、把距离推到库）、`§7 非目标`、`§9 门槛`；读 `V5-SCENES.md:25-30`（S3 的"必须能表达"清单里**没有**物权）与 `:83-95`（S4 的钥匙移交）；试点报告该行。
- **什么会重新打开它**：root 或用户一句范围裁定；或者一次 S3 种子实验证明"谁最后拿着"只用 P3 的包含关系就能表达、不需要新概念（那么这条就留在种子层，按"定义在使用处"记在 lint 里）。

### Q3 — v5 的过程记录该落在哪里？

- **不能回答的原因**：`CONTEXT.md:73` 声明"Ticket / 工作记录：变更与项目管理的过程记录（`.scratch/<feature>/`）"，`契约失效时请勿喂猫/ROADMAP.md:196-197` 还引用 `.scratch/README.md` 作追踪器。**实际 `git ls-files .scratch` 只返回两个文件**：`.scratch/m1-wave2.js`、`.scratch/m1-workflow.js`（v4 时期的编排脚本）。没有 `issues/`、没有 `README.md`、没有一份 v5 的票。v5 的 M0→M3 过程事实只存在于提交信息里（`561da16`、`095a05f`、`1ebf971`、`732ecfd`、`81f4c9d`）。
- **为什么这是问题而不是小事**：它决定 M4 的验收证据该长什么样——如果 v5 豁免票制，那"每个工作包的契约、证据与决定进入其 ticket"（`ROADMAP.md` 跨里程碑规则）在 v5 上就只能指提交信息；如果不豁免，M4 开工前要先补一个追踪器。
- **试过什么**：`git ls-files .scratch`、`ls -la .scratch/`、读两份 `.js` 的抬头；`grep -rn "scratch" CONTEXT.md ROADMAP.md`。
- **什么会重新打开它**：用户/root 的裁定；或 `.scratch/v5*/` 下出现第一张票。

## 4. 找到的缺陷（事实已定，只差落笔）

| # | 缺陷 | 证据指针 | 归属 |
| --- | --- | --- | --- |
| D1 | **根目录两份文档仍说 v4 是主线**，与 ADR 0002 及项目 README 相反 | `README.md:24`（"The current line is v4"）、`CONTEXT.md:16`（"只有 v4 是当前活动线"）、`v5/README.md:72`（"v4 仍是可跑的主线"） vs `docs/adr/0002-v5-becomes-the-main-line.md:10-12`、`契约失效时请勿喂猫/README.md:20-22`、`AGENTS.md:68-71` | root（这三份是 root 侧的文档，我无写权）。事实已由 ADR 定，所以不是裁决，只是一次修改 |
| D2 | **`CONTEXT.md` 的"运行与证据"整节是 v4 的形状**：工件格式 `v3-trajectory-1`、`v4/runs/`、半天检查点环、`check_milestones.py` | `CONTEXT.md:38-66` vs v5 的实际形态（`v5/stories/*/runs/agent-<时间>-<pid>-<标签>/` 四个文件，见 `v5/README.md:44-50`） | root（同上；`CONTEXT.md` 自称"冲突时以其权威文档为准"，但它指向的权威现在是 v5） |
| D3 | **M3 交付只做了 S2**（上文的 Q1 的事实面） | `V5-ROADMAP.md:49` 要求 S1/S2 首轮报告；`v5/stories/s1_last_bus/` 无 `agent_run.py`，`runs/` 只有脚本路径 | 需要用户/root 一次范围裁定（Q1） |
| D4 | **v5 没有自己的历史失败台账**，而路线图把"每一支故事自己一份"列为必须继承的资产 | 要求：`V5-ROADMAP.md §5` 表末行 + `AGENTS.md:68-84` 的 v5 预门口径（只点了 suite + `v5_lint` + `anti_cheat`，**没有**要求台账）；现状：`v5/tests/` 8 个模块 `test_m1_*.py`/`test_m2_*.py`/`test_m3_agent.py`，`grep -rln historical v5/tests` → 0 命中（v4 的台账在 `v4/harness/tests/test_historical_failures.py`，502 KB） | 建议在 M4 第一次真跑前补，且先决定预门口径以哪份为准 |

## 5. 它有用吗（对这次定向本身的诚实判断）

有用，但边界要说清：v5 的门禁是**真的可跑**（我重跑了三项，全绿；不是引述路线图），M3 的模型轨迹**真的在 git 里**且带 `context.md`（能回答"他当时知道什么"），这两件事合起来足以支撑"下一里程碑是 M4"的判断。反过来说，v5 目前**没有任何一条长弧证据**——只有两支 3–5 人、15–60 回合的短故事，S3 是第一次引入制度与期限，`V5-PRIMITIVES.md:133` 明确承认打断机制还没被逼出来。所以 M4 不是"照抄 S2 再加人"，而是一次**库概念的第一次真增长**（制度 + 期限 + 传递链 + 公开/私下），失败风险集中在这里，而不是在写种子上。

---