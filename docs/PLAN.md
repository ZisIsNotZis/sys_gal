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
- Mail for this layer arrives in `inbox/` (four header lines: kind, from, spend, id); a message is deleted once its content has landed.

## Where the convention breaks

- `契约失效时请勿喂猫/ROADMAP.md` is the v4 reference line's roadmap and still cites `.scratch/` as the tracker; the main line's roadmap is `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md`, and v5 is exempt from the tracker (decision below).
- `docs/PRINCIPLE.md` and the `v4/` documents describe a three-actor MC/NPC/extra cast that v5 does not have; read them as principles, not as the current shape.

## Roadmap — M4 「半日 + S3《夜市》」

Milestone M4 is the next user-synchronisation point (`契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §3, row M4). Its acceptance is three observable claims: every ownership of the deposit note is physically reachable; the public/private information gap is real; a resume from a half-day boundary is causally continuous.

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
| 1 | `deadline` | 期限：到点触发、在飞动作与打断，四件套（失败场景、规则、渲染、测试） | v5 gate green; `V5-PRIMITIVES.md` §8 的中途打断暂缓条被关掉 | taken 2026-10-21; branch `pi-subagents/task-1-e61cb1b-bdf0-s0-t0`, merged at — |
| 1 | `resume` | 半天边界存档 + 因果续跑，从 v4 原样搬（不重造） | v5 gate green; 续跑后 event id/version 连续 | taken 2026-10-21; branch `pi-subagents/task-2-5d14cf4-6f34-s0-t0`, merged at — |
| 1 | `ledger` | v5 自己的历史失败台账 + 预门口径 | v5 gate green; 台账逐条映射到一个会失败的测试 | taken 2026-10-21; branch `pi-subagents/task-3-edfa688-7b3b-s0-t0`, merged at — |
| 1 | `s3` | S3《夜市》种子、卡司、四条归属路径（认账/推给下一个/拿不回来/当众澄清）、制度角色与当众-私下说的库增长 | v5 gate green; 四条路径的轨迹可通读 | taken 2026-10-21, beside ws1; branch `ws2-s3-recovered`, merged at — |
| — | `ws-review` | 独立复核 ws1 的三包与 `s3`，一个新上下文的复核者，覆盖面写明 | verdict per package | — |
| — | `milestone-review` | M4 三条判据的整体复核（不是逐包裁决之和） | verdict | — |
| — | `docs-v5-shape` | `README.md`/`CONTEXT.md` 的运行与证据一节改成 v5 形状 | 两份文件里不存在指向 v4 为准的句子 | `fail` at `5578a8b`; repair is this advance's own work |

## Decided

- **M4 is the next milestone** — root, contract to this layer dated 2026-10-21, assent: agreed. M3's signature stays with the person and does not block M4, whose skeleton is script-actor work needing no provider spend.
- **物权 does not enter the library** — root, same contract, assent: assumed. Placement is the seed layer, recorded in the lint as defined-at-use; S3's 押金条 and S4's 钥匙移交 are expressible with P3 containment. Reversal costs one concept added without its second declaring story.
- **v5 is exempt from the ticket tracker** — root, same contract, assent: agreed. A work package's contract, evidence and decision live in the commit message and in the milestone report; `.scratch/` is for defects found by running.
- **v5 is the main line** — `docs/adr/0002-v5-becomes-the-main-line.md`, assent: agreed.
- **Parallel writers get their own worktree, merged by this layer** — inference from `Git` (`one writer per area`, `worktree`, `integrator`): three packages editing one v5 tree would read each other's half-done edits while running the same gate, so the difference between their results would not come from the package. The manager holds the merge and runs the combined check.

## Open

- **M3 的签字在人手里** — `docs/plan/portfolio.md` files it under what waits on the person. Nothing here reconstructs it; M4 does not depend on it.
- **物权 的第二次声明** — the concept returns when a second story needs a held-by relation that containment cannot carry.
- **`docs-v5-shape` 的 `done` 不成立** — 独立裁决 at `5578a8b`: `CONTEXT.md:20, 35, 38, 43` still name `V4-*` documents as 权威 (and lines 4–5 make them win on conflict), `README.md:15, 27` point at the v4 `ROADMAP.md` for milestones and where it stands, and `README.zh-CN.md:20` calls v4 the active line. The status line stays `fail` until the tree carries the criterion; the repair is this advance's own work, not a new package.
- **v4 detail in `CONTEXT.md` is reference, not authority** — each v4-only entry (KB/`V4-AGENT-INTERFACE.md`, MC/NPC/extra/`V4-CAST.md`, 导演简报, 剧情锚点) either carries v5's counterpart in the same entry or says in one line that it describes the reference line.

## Verifying M4

Each claim is shown by a command that runs from the committed tree, in `契约失效时请勿喂猫/v5`:

| claim | command |
| --- | --- |
| 1 押金条每种归属物理可达 | `python3 -m unittest tests.test_m4_s3 -v`, plus the four `stories/s3_night_market/runs/{a,b,c,d}.md` transcripts |
| 2 当众与私下信息差真实 | the `speak(to=…)` assertions inside `tests/test_m4_s3.py` |
| 3 续跑因果连续 | `python3 -m unittest tests.test_m4_resume -v` |
| gate that must stay green beside them | `python3 -m unittest discover -s tests -p 'test_*.py' && python3 scripts/v5_lint.py --strict && python3 scripts/anti_cheat.py --verbose` |

An independent verdict at `5578a8b` found all three unreached at that revision: no `stories/s3_night_market/`, `speak` taking only `text`, `0` hits for `checkpoint`/`resume` in `engine/`; and the whole of `s3` reachable only as an unreachable commit. The facts it opened are in `Open`; each closes only when the command above runs at a named revision.

## Evidence

- The v5 gate and its three structural checks: `../AGENTS.md` § "v5 gate".
- Milestone definitions and the seven-story ladder: `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md`, scene requirements in `V5-SCENES.md`, primitives and the entry threshold in `V5-PRIMITIVES.md`.
- The orientation evidence for this roadmap: `inbox/2026-10-21-orientation.md`.
- Root's answers of 2026-10-21: landed into the `Decided` list above and into `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §2.1/§3; the message file was deleted after landing.
