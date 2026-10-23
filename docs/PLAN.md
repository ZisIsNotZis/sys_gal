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

## Roadmap — 半日一局：押金条在几个人手里传过，每一种归属都真的走得到，一局能从傍晚走到第二天早上（M4「半日 + S3《夜市》」）

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

## Decided

- **半日一局 is the next milestone（M4）** — root, contract to this layer dated 2026-10-21, assent: agreed. The 演员试点's signature (把脚本演员换成真模型，看这一局是被世界推动还是被作者推动；M3) stays with the person and does not block it, whose skeleton is script-actor work needing no provider spend.
- **物权 does not enter the library** — root, same contract, assent: assumed. Placement is the seed layer, recorded in the lint as defined-at-use; S3's 押金条 and S4's 钥匙移交 are expressible with P3 containment. Reversal costs one concept added without its second declaring story.
- **v5 is exempt from the ticket tracker** — root, same contract, assent: agreed. A work package's contract, evidence and decision live in the commit message and in the milestone report; `.scratch/` is for defects found by running.
- **v5 is the main line** — `docs/adr/0002-v5-becomes-the-main-line.md`, assent: agreed.
- **一日两个世界（M5）的入口条件包含"跨《夜市》（S3）的 18:00→08:00 取检查点并续跑"** — 里程碑复核的升级项，我在此裁定：M5 要报"全天故事续跑连续"，就必须先在《夜市》真实跨过半日边界，而不是拿《末班车》（S1）的 23 分钟中点作证。理由：断点落在同一个半日内的续跑不检验跨日的前提（跨日才是 M5 要证的东西），而现在没有任何测试做过这件事。代价：一个小包，若 S3 的种子在跨日处没有可重入的排程，成本上升，届时报上去。
- **S3 跨夜这条边界已经有人切了**（`9dc76d4`）—— 上面那条 M5 入口条件的物证落成：路 `e` 收摊时条子进管理处、门锁上，甲走开，世界自己走到 32:00 开门，第二天把条子领回来。跨夜那一段是脚本里的时间标记 `NIGHT`（`advance_idle`），不是动词，也没有人替角色做决定。判据在 `tests/test_m5_cross_night.py`：夜里的检查点续跑后账本与不中断的那本一字不差，摘掉次日开门则甲开不了门、条子留在管理处。
- **Parallel writers get their own worktree, merged by this layer** — inference from `Git` (`one writer per area`, `worktree`, `integrator`): three packages editing one v5 tree would read each other's half-done edits while running the same gate, so the difference between their results would not come from the package. The manager holds the merge and runs the combined check.

## Open

- **演员试点的签字在人手里（M3）** — `docs/plan/portfolio.md` files it under what waits on the person. Nothing here reconstructs it; 半日一局（M4） does not depend on it.
- **物权 的第二次声明** — the concept returns when a second story needs a held-by relation that containment cannot carry.
- **半天还不存在（已被 `9dc76d4` 部分关闭）** — 里程碑复核当时的读数：最长的脚本只走 13 分钟世界时间，1110 关、1920 再开的排程从未被再次进入；a/b/d 三条路在 18:12–18:14 就结束了，离 18:30 锁门还有十六分钟，所以期限在四条路里三条不做功，只在 c 里被动拦人。claim 3 的边界是 **S1 的 23 分钟中点**（`tests/test_m4_resume.py:half_day_clock`），当时没有任何测试对 S3 取检查点。"半天"那时是标签，不是这一局的形状。这是 M5 的入口条件，不是 M4 的判据违反：M4 的 claim 3 说的是续跑因果连续，机制成立且有负向对照。**现在跨夜这段有了**（`9dc76d4`，路 `e`）；剩下的仍然是真的：过夜那 14 小时是空转的时间，不是被角色走出来的行为，"全天故事"还差 S5/S7 那一档的密集动作。
- **一条故事能不能写两条汇到同一结局的路** — `anti_cheat` 的第三条现在把"路径数"与"结局数"绑在一起（`len(distinct) < len(variants)`），所以一支故事不能再写两条殊途同归的路；要收敛只能把它们写成一条。复核者把它当**口味**上报，我把它原样转给 root：`anti_cheat.py:6` 的那句话本来就是这么写的（"每条被写出来的路径都必须能走到不同结局"），所以修的是实现而不是句子。我的建议是不改这条判据，把"想收敛"当成"一条路写了两遍"；若 root 认为该允许收敛，判据要改成落在**结局**上而不是**路径**上，那是判据的重写，不是这一层的自选。
- **`R10` 只钉住了"退回 2"这一种回退** — 复核者实测：把阈值改成一个常数 `3`，`R10` 仍然通过，因为它的判别式是那句 `"3 条路径只走到 2 个结局"`。再加一个用例（4 条路 / 3 个结局）就能把标题里"门槛跟路径数走"这一半也钉住。不是判据违反，是一颗便宜的补丁，留给下一个碰这个文件的人。
- **`契约失效时请勿喂猫/.scratch/` 在 HEAD 上是 tracked** — 里面是 v3 时代的 `active-work.md` 与 `v3-harness-followups/issues/01–08.md`。本目录的规矩把 `.scratch/` 留给"跑出来的缺陷"（见 Decided），所以它不是违规；但它是旧缓冲的名字，谁下次碰它就把还有价值的搬走、没价值的带理由退役。不是 v5 的事，也不是 M4 的事。
- **T-A 的正文只在参考线里** — `v5/docs/V5-ROADMAP.md` §3 M7 以"结局 T-A"引用它，两处都没有定义；`CONTEXT.md` 现在如实写着定义在 v4 的参考文档里。定稿与否留给 S7，与 M4 无关。

## Verifying 半日一局（M4）

Each claim is shown by a command that runs from the committed tree, in `契约失效时请勿喂猫/v5`:

| claim | command |
| --- | --- |
| 1 押金条每种归属物理可达 | `python3 -m unittest tests.test_m4_s3 -v`, plus the four `stories/s3_night_market/runs/{a,b,c,d}.md` transcripts |
| 2 当众与私下信息差真实 | the `speak(to=…)` assertions inside `tests/test_m4_s3.py` |
| 3 续跑因果连续 | `python3 -m unittest tests.test_m4_resume -v` |
| 3 的前提（跨夜） | `python3 -m unittest tests.test_m5_cross_night -v` |
| gate that must stay green beside them | `python3 -m unittest discover -s tests -p 'test_*.py' && python3 scripts/v5_lint.py --strict && python3 scripts/anti_cheat.py --verbose` |

An independent verdict at `5578a8b` found all three unreached at that revision: no `stories/s3_night_market/`, `speak` taking only `text`, `0` hits for `checkpoint`/`resume` in `engine/`; and the whole of `s3` reachable only as an unreachable commit. The facts it opened are in `Open`; each closes only when the command above runs at a named revision.

## Evidence

- The v5 gate and its three structural checks: `../AGENTS.md` § "v5 gate".
- Milestone definitions and the seven-story ladder: `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md`, scene requirements in `V5-SCENES.md`, primitives and the entry threshold in `V5-PRIMITIVES.md`.
- The orientation evidence for this roadmap: `inbox/2026-10-21-orientation.md`.
- Root's answers of 2026-10-21: landed into the `Decided` list above and into `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §2.1/§3; the message file was deleted after landing.
