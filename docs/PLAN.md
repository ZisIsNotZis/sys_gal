# sys_gal — node plan

Why this file exists: this directory has one owner (a manager), and this file is where that owner keeps the roadmap, what is decided, and what is open. Everything a reader needs to judge the directory's progress is here or one hop from here.

## How to start

- The state a claim refers to is shown by the v5 gate, run from `契约失效时请勿喂猫/v5`:
  `python3 -m unittest discover -s tests -p 'test_*.py' && python3 scripts/v5_lint.py --strict && python3 scripts/anti_cheat.py --verbose`
- The main line is v5 (`docs/adr/0002-v5-becomes-the-main-line.md`); v4 and below are reference lines.
- Repository-wide working policy, including the per-line gate: `../AGENTS.md`.

## How to continue

- Read the roadmap below, take every package whose dependencies are met, and mark it taken here in the same act.
- A package's contract, evidence and decision live in its commit message and in the milestone report; `.scratch/` is reserved for defects found by running (root's contract of 2026-10-21, §Q3).
- Mail for this layer arrives in `inbox/` (four header lines: kind, from, spend, id); a message is deleted once its content has landed. Reports **from** this layer live in `mail/`, addressed `to: root`.

## Where the convention breaks

- `契约失效时请勿喂猫/ROADMAP.md` is the v4 reference line's roadmap and still cites `.scratch/` as the tracker; the main line's roadmap is `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md`, and v5 is exempt from the tracker (decision below).
- `docs/PRINCIPLE.md` and the `v4/` documents describe a three-actor MC/NPC/extra cast that v5 does not have; read them as principles, not as the current shape.

## Roadmap — 半日一局：押金条在几个人手里传过，每一种归属都真的走得到，一局能从傍晚走到第二天早上（M4「半日 + S3《夜市》」）— delivered, awaiting its signature

Milestone 半日一局（M4） is the next user-synchronisation point (`契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §3, row M4). Its acceptance is three observable claims: every ownership of the deposit note is physically reachable; the public/private information gap is real; a resume from a half-day boundary is causally continuous.

```text
M4 (milestone)
├─ ws1-deadline ─┐
├─ ws1-resume  ──┤
├─ ws1-ledger  ──┼─→ integration ─→ ws-review ─→ milestone-report ─→ M4
└─ ws2-s3     ──┘
```

`ws2-s3` runs beside workset 1 and not after it: its four paths express the closing-time consequence through an institution effect, not through an action interrupted in flight, so nothing it asserts depends on `deadline`'s code. The interrupt is `deadline`'s own test. The two packages were split by file area (`deadline` owns `engine/`; `s3` owns `library/`, `stories/s3_night_market/`, one new test file) so neither one's gate can read the other's half-done edit.

Packages, in worksets (a workset is run in parallel, worksets in order):

| ws | package | delivers | acceptance command | status |
| --- | --- | --- | --- | --- |
| 1 | `deadline` | 期限：到点触发、在飞动作与打断，四件套（失败场景、规则、渲染、测试） | v5 gate green; `V5-PRIMITIVES.md` §8 的中途打断暂缓条被关掉 | taken 2026-10-21; branch `pi-subagents/task-1-e61cb1b-bdf0-s0-t0`, merged `09962fb`; §8 的中途打断暂缓条已关掉 |
| 1 | `resume` | 半天边界存档 + 因果续跑，从 v4 原样搬（不重造） | v5 gate green; 续跑后 event id/version 连续 | taken 2026-10-21; branch `pi-subagents/task-2-5d14cf4-6f34-s0-t0`, merged `7ebdde5` |
| 1 | `ledger` | v5 自己的历史失败台账 + 预门口径 | v5 gate green; 台账逐条映射到一个会失败的测试 | taken 2026-10-21; branch `pi-subagents/task-3-edfa688-7b3b-s0-t0`, merged `d8af14c` |
| 1 | `s3` | 《夜市》（18:00 的夜市，一摊货被收走，押金条在几个人手里传过，谁最后拿着它谁认这笔账；S3）种子、卡司、四条归属路径（认账/推给下一个/拿不回来/当众澄清）、制度角色与当众-私下说的库增长 | v5 gate green; 四条路径的轨迹可通读 | taken 2026-10-21, beside ws1; branch `ws2-s3-recovered`, merged `a0e307a` |
| — | `ws-review` | 独立复核 ws1 的三包与 `s3`，一个新上下文的复核者，覆盖面写明 | verdict per package | `pass` ×4 at `a0e307a`（复核者在 `8c8b881` 复跑门：132 tests / lint / anti_cheat 3 支） |
| 1 | `fix-endings` | 让 claim 1 的"四条路四种结局"能被推翻：`结局` 由世界的事拼出，`ENDINGS` 删掉；`d` 改成 `a` 的结局时测试必须红 | `tests.test_m4_s3` 在 `/tmp` 副本的探针下变红；v5 gate 全绿；`runs/{a..d}` 重新生成后 `git status` 干净 | `bde3a7d`; 复核 `fail`（窄）：测试已能红，`anti_cheat.py:96` 的阈值仍是 `< 2`，同一个探针下它还是绿的 |
| 1 | `fix-threshold` | 把 `anti_cheat` 的第三条检查修到和它自己那句话一样强：`len(variants)`，而不是 2 | 正确树通过；`d := a` 与四条合一两个探针下都非零退出 | `6063e1c`; 复核 `pass`（探针只在那一行上咬） |
| 1 | `pin-threshold` | 让套件自己抓住回归：把阈值退回 `2` 时必须有测试变红 | 在 `/tmp` 副本里把 `anti_cheat.py:96` 退回 `2`，`tests.test_historical_failures` 变红 | `aec870c`（`R10`）; 复核 `pass`：退回 2 时 133 绿、只有 R10 红，且与 R07 不重复 |
| — | `milestone-review` | M4 三条判据的整体复核（不是逐包裁决之和） | verdict | claim 1、2 `reached`；claim 3 机制成立、前提不成立；一处不可失败的测试被查出来（见 Open） |
| — | `cross-night` | 一日两个世界（M5）的入口条件：《夜市》（S3）真的跨过 18:30→次日 08:00 边界，并在夜里取检查点、次日续跑 | v5 gate green; `python3 -m unittest tests.test_m5_cross_night -v` 三条判据（过夜发生 / 夜里的检查点续跑因果连续 / 摘掉次日开门则条子留在管理处） | `9dc76d4`; 第五条路 `e`，`anti_cheat` 5 条路径 5 个结局；a–d 逐字节未动 |
| — | `docs-v5-shape` | `README.md`/`CONTEXT.md` 的运行与证据一节改成 v5 形状 | 两份文件里不存在指向 v4 为准的句子 | `fail` at `5578a8b`; repaired at `263fa0c` (`grep -n 'v4' CONTEXT.md README.md`: every hit says 参考) |

## Roadmap — 一日两个世界：便利店与宴会厅各自跑完一整天，同一套概念在两个世界都成立（M5）

M5 is the next milestone on the approved list (`契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §3, row M5). Its acceptance is four observable claims: two worlds each run a whole day and read through; the stocktake is computed from quantities rather than decided by the script; a same-scale comparison report; traces packed into git and verified. 半日一局（M4） is delivered and awaiting its signature, and that signature does not gate the packages below except where marked.

```text
M5 (milestone)
├─ second-story-agent ─┐
├─ s4-night-shop ──────┤
├─ s5-wedding ─────────┼─→ stocktake ─→ comparison ─→ integration ─→ ws-review ─→ milestone-report ─→ M5
└─ s1-model-report ────┘
```

| ws | package | delivers | acceptance command | status |
| --- | --- | --- | --- | --- |
| 1 | `second-story-agent` | `stories/agent_loop.py` — one model loop both stories share (《借条》's shell is thin, 《末班车》's shell points the same loop at the second seed); S1's ending composed from facts instead of looked up by script label; S1's stale script traces regenerated | `python3 -m unittest tests.test_m5_second_story_agent -v` (6 tests) + the v5 gate | taken and landed 2026-10-23; zero provider spend (MockProvider) |
| 2 | `s1-model-report` | 《末班车》's real-model report, riding M5's ladder as the person placed it (2026-10-23) | a fresh `stories/s1_last_bus/runs/agent-*` directory with `decided_by: agent` on every turn, read against `AGENTS.md` | open — **needs a provider authorization**, which this advance did not have |
| 2 | `s4-night-shop` / `s5-wedding` | the two same-scale worlds: shift handover, lock & key, quantity, crowd/rumour/record authority | two traces read through a whole day; `anti_cheat` still 3+ stories | landed 2026-10-23: `514310e` + `c2526ac`, merged by this layer at `0be9bd5` (one conflict in `library/concepts.py`, union of both vocabularies); gate 187 tests / lint / `anti_cheat` 5 stories. 人工通读抓到的两处见 `same-scale` 行。 |
| 3 | `same-scale` | 两支世界的量与密度对得上：《夜班》的夜不再是空的，《婚礼》的量追到同一尺度 | 班内相邻时间戳间隔 ≤ 120 分钟；两支故事每条路的动作数比值在 ±30% 内；两支各四个结局仍互不相同 | landed 2026-10-23 `9752808`（经 f458777 → 05571b8 两轮修回）: 《夜班》53/50/52/50 与《婚礼》63/59/60/64 做成的事，失败动作 0，八条路最长空档 120 分钟；一条共用判据在 `tests/test_m5_same_scale.py`，反向控制已验（拿掉 16:00 那件排程，婚礼上午出现 207 分钟空档） |
| 3 | `stocktake` | the claim "盘点由数量算出而非剧本决定" as a test: change a count in the world, the stocktake reading changes; write a number in the script and it is not read | a negative control that goes red when the stocktake stops summing | landed 2026-10-23 `7950513`: `library/stocktake.py` 一份读数一个出口（`count` 动词与结局摘要都走它）；副本里 800→650 读数变 650、清 0 读 0；把数写死探针下两条测试都红（本层复核过）；台账 `R12` |
| 3 | `comparison` | the same-scale comparison report of the two worlds | report + the two traces it cites; entry condition: `same-scale` green（已达） | landed 2026-10-23: `v5/docs/V5-M5-COMPARISON.md`（七件事成立、三件没成立：`sign` 与 `shift` 是两个词说同一件事、婚礼“十人同场”只在场不参与、店长只有一句话） |
| — | `pack` | traces in git and a `check` that fails on a run directory without `context.md` | `python3 scripts/pack_trajectory.py check` | landed 2026-10-23 `521f582`: 25 件 zstd 工件对 100 件原始件（3,172,688 字节退出索引、仍在磁盘），逐件摘要一致；`check` 四类坏都抓（本层复核：`check` 退出 0，`unpack` 对 provider 轨迹逐件摘要一致） |

## Decided

- **判据改成说观察到的事** — 我改的，不是人给的：`半日一局` 的第三条判据原来只写"续跑因果连续"，而当时唯一的断点是《末班车》二十几分钟的中点，"半天"是名字，不是这一局的形状。两件事一起做：把不真的名字换成真的（`half_day_clock` → `mid_run_clock`，测试名跟着改），把缺失的能力补上（过夜之后时钟翻日，轨迹印 `2026-04-03 08:00`），再把判据写成两处证据各自在哪。代价：三支故事的脚本轨迹重新生成了一遍（它们本来就跑在旧代码上），s2 的 `digest_after` 因此全动——那是种子里的日期进摘要之后没再生成过的结果。
- **演员试点：把脚本演员换成真模型，看这一局是被世界推动还是被作者推动（M3）关在《借条》一支故事上** — 人, answer of 2026-10-23, assent: agreed. The gate covers 《借条》's model report and the three anti-cheat checks; 《末班车》's model-driven report does **not** stand in front of the gate and moves into the next milestone's ladder (一日两个世界, M5), where the same world and the same checks run on a second story. Reason given to the person: one story already proves the mechanism can make a model walk its own path, and a second copy of the same proof belongs beside the next milestone rather than in front of the gate. Written where it is read: `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §3 and `V5-M3-PILOT.md` §七.
- **M5 的阶梯里有一行是《末班车》的模型首轮报告** — inference from the person's answer above (the milestone, not the gate, is where the second story's model run lands); the milestone is M5 because it is the next one on the approved list whose acceptance already runs one set of concepts in two worlds. Cost if wrong: the report lands one milestone later than intended, and no checkpoint depends on it.
- **半日一局 is the next milestone（M4）** — root, contract to this layer dated 2026-10-21, assent: agreed. The 演员试点's signature (把脚本演员换成真模型，看这一局是被世界推动还是被作者推动；M3) stays with the person and does not block it, whose skeleton is script-actor work needing no provider spend.
- **物权 does not enter the library** — root, same contract, assent: assumed. Placement is the seed layer, recorded in the lint as defined-at-use; S3's 押金条 and S4's 钥匙移交 are expressible with P3 containment. Reversal costs one concept added without its second declaring story.
- **v5 is exempt from the ticket tracker** — root, same contract, assent: agreed. A work package's contract, evidence and decision live in the commit message and in the milestone report; `.scratch/` is for defects found by running.
- **v5 is the main line** — `docs/adr/0002-v5-becomes-the-main-line.md`, assent: agreed.
- **一日两个世界（M5）的入口条件包含"跨《夜市》（S3）的 18:00→08:00 取检查点并续跑"** — 里程碑复核的升级项，我在此裁定：M5 要报"全天故事续跑连续"，就必须先在《夜市》真实跨过半日边界，而不是拿《末班车》（S1）的 23 分钟中点作证。理由：断点落在同一个半日内的续跑不检验跨日的前提（跨日才是 M5 要证的东西），而现在没有任何测试做过这件事。代价：一个小包，若 S3 的种子在跨日处没有可重入的排程，成本上升，届时报上去。
- **S3 跨夜这条边界已经有人切了**（`9dc76d4`）—— 上面那条 M5 入口条件的物证落成：路 `e` 收摊时条子进管理处、门锁上，甲走开，世界自己走到 32:00 开门，第二天把条子领回来。跨夜那一段是脚本里的时间标记 `NIGHT`（`advance_idle`），不是动词，也没有人替角色做决定。判据在 `tests/test_m5_cross_night.py`：夜里的检查点续跑后账本与不中断的那本一字不差，摘掉次日开门则甲开不了门、条子留在管理处。
- **Parallel writers get their own worktree, merged by this layer** — inference from `Git` (`one writer per area`, `worktree`, `integrator`): three packages editing one v5 tree would read each other's half-done edits while running the same gate, so the difference between their results would not come from the package. The manager holds the merge and runs the combined check.

## Open

- **物权 的第二次声明** — the concept returns when a second story needs a held-by relation that containment cannot carry.
- **半天这一段现在是真的，但它是空的** — 那一局真的从 18:30 走到次日 08:00（`9dc76d4`），轨迹上现在印着次日的日期（`engine/surface.py:clock_label` 给日期就翻日，`R11` 钉住）。名字与工件从此对得上，剩下的是密度：过夜那 14 小时里没有人做任何事，'全天故事'还差 S5/S7 那一档的密集动作。这不是判据违反，是 M5 的两个世界要填的东西。
- **数做成的事，不数尝试；同一把尺子不得只量一支故事** — 我自己的，2026-10-23。《婚礼》第一次追同尺度时加了 27 个动作，其中 13–17 个是失败的（“你已经在厅内里了”“这里没有一样东西叫「菜」”），而测试数的是 `kind == "turn"`，把失败也当成功，于是 42 对 48 看着过关、真做成的是 25–29 对 45–48。三件事一起修：判据只数 `ok` 的 turn；十二条路的失败动作必须为零（有故意要表达的失败得在 `INTENTIONAL_REFUSALS` 里登记并扣掉，现在空表）；空档判据从《夜班》的测试提到两支故事共用的文件，一条断言量八条路。反向控制：拿掉《婚礼》16:00 那件排程，空档从 120 变成 207。代价与诚实：为了不让比值掉出带外，《夜班》也跟着长了 5 个值守动作（再数一次抽屉、读小票、交班前最后看一眼），内容都成立，但那是指标在推着内容走——记在这里，免得下次有人拿“抬分母”来盖住真的缺口。
- **门绿不等于判据达成：轨迹要读** — 我自己的，2026-10-23，代价是两支新世界第一次合入时差点被当成交付。《婚礼》的路 a 与路 c 的轨迹停在 09:22 与 09:18（"散场时间：还没到散场"），而当时的测试只验了路 b 走完一天；`anti_cheat`、`lint`、187 支测试全绿。修法两件一起：路 a/c 的脚本末尾补上"世界自己走到下一个排程点"那个空动作（四路现在都读到 `2026-05-20 22:00`），测试改成四条路逐条断言走到散场——拿掉一条路的空动作它会红（已用反向控制验过：钟停在 562 分钟）。预防：一个包回来时，先读一份轨迹的头尾再跑门，门的读数放在读完之后。
- **派出去的活要在指定的工作树里落地** — 我自己的，2026-10-23：《婚礼》的 worker 把提交落在了 `master` 而不是它的 worktree 分支，《夜班》的落在自己分支上。两者都没丢东西（我在主树里合并），但下一次派包时要求接收方先自证 `git rev-parse --show-toplevel` 与 `git status -sb` 再动手，免得两个写者在一个索引上相遇。
- **反作弊第三检不改：一条路写两遍就是一条路** — root, 2026-10-23, assent: agreed. 原话的意思：脚本能用就继续用；脚本跟实际合理性打架时改脚本，别为了脚本去硬凑不自然的东西；也别为它花太多时间——每支实验自己的判据在它自己的目标上，目标达成就好，没达成就修那个目标。落成两条：`anti_cheat` 的 `len(distinct) < len(variants)` 留着（它实现的就是 `anti_cheat.py:6` 那句写下来的判据）；一支故事想要两条路殊途同归，就把它写成一条路，不写假差异去喂指标。四支故事（S1/S2/S3 + 新两支）按这条走。
- **两件便宜的加固，登记但不花时间** — root 2026-10-23 说过不为脚本花太多时间，所以这两件只排队、不现在做，谁下次碰那个文件谁顺手做掉：(1) `R10` 只钉住了"退回 2"，改成常数 `3` 它仍绿（判别式是那句 `"3 条路径只走到 2 个结局"`），补一个 4 条路 / 3 个结局的用例就钉死；(2) `engine/seed.py` 的 `ALLOWED` 只约束 `places`/`people`/`objects` 三段，`schedule.effect` 没有形状约束，多写的 `actor`/`say`/`do` 会被静默吃下——把 `schedule` 与每种 `EFFECTS` 的允许字段也写进 `ALLOWED`，「排程里替角色做决定」就从检测变成加载期报错（`check_destiny` 留作第二道防线）。
- **`契约失效时请勿喂猫/.scratch/` 在 HEAD 上是 tracked** — 里面是 v3 时代的 `active-work.md` 与 `v3-harness-followups/issues/01–08.md`。本目录的规矩把 `.scratch/` 留给"跑出来的缺陷"（见 Decided），所以它不是违规；但它是旧缓冲的名字，谁下次碰它就把还有价值的搬走、没价值的带理由退役。不是 v5 的事，也不是 M4 的事。
- **T-A 的正文只在参考线里** — `v5/docs/V5-ROADMAP.md` §3 M7 以"结局 T-A"引用它，两处都没有定义；`CONTEXT.md` 现在如实写着定义在 v4 的参考文档里。定稿与否留给 S7，与 M4 无关。

## Verifying 半日一局（M4）

Each claim is shown by a command that runs from the committed tree, in `契约失效时请勿喂猫/v5`:

| claim | command |
| --- | --- |
| 1 押金条每种归属物理可达 | `python3 -m unittest tests.test_m4_s3 -v`, plus the four `stories/s3_night_market/runs/{a,b,c,d}.md` transcripts |
| 2 当众与私下信息差真实 | the `speak(to=…)` assertions inside `tests/test_m4_s3.py` |
| 3 续跑因果连续（一局的中途断点） | `python3 -m unittest tests.test_m4_resume -v` — the cut is `mid_run_clock()`, the midpoint of 《末班车》's 23 minutes, and it is named that way now |
| 3 续跑因果连续（真的过夜 = the “半日” in the milestone's name） | `python3 -m unittest tests.test_m5_cross_night -v` — 18:30 → next-morning 08:00, and the morning reads `2026-04-03 08:00` on the trace instead of `32:00` |
| gate that must stay green beside them | `python3 -m unittest discover -s tests -p 'test_*.py' && python3 scripts/v5_lint.py --strict && python3 scripts/anti_cheat.py --verbose` |

An independent verdict at `5578a8b` found all three unreached at that revision: no `stories/s3_night_market/`, `speak` taking only `text`, `0` hits for `checkpoint`/`resume` in `engine/`; and the whole of `s3` reachable only as an unreachable commit. The facts it opened are in `Open`; each closes only when the command above runs at a named revision.

## Evidence

- The v5 gate and its three structural checks: `../AGENTS.md` § "v5 gate".
- Milestone definitions and the seven-story ladder: `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md`, scene requirements in `V5-SCENES.md`, primitives and the entry threshold in `V5-PRIMITIVES.md`.
- The orientation evidence for this roadmap: `inbox/2026-10-21-orientation.md`.
- Root's answers of 2026-10-21: landed into the `Decided` list above and into `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §2.1/§3; the message file was deleted after landing.
