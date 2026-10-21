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
- Mail for this layer arrives in `mail/`; the shape is declared in `mail/README.md`.

## Where the convention breaks

- `README.md` and `CONTEXT.md` were written for the v4 line. Claims about which line is current, and about the shape of run artefacts, are authority-marked at v5 and are stale elsewhere they survive in those two files (package `docs-v5-shape`, not started).
- `契约失效时请勿喂猫/ROADMAP.md` and `CONTEXT.md` still cite `.scratch/` as the ticket tracker; v5 is exempt from it (decision below).

## Roadmap — M4 「半日 + S3《夜市》」

Milestone M4 is the next user-synchronisation point (`契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §3, row M4). Its acceptance is three observable claims: every ownership of the deposit note is physically reachable; the public/private information gap is real; a resume from a half-day boundary is causally continuous.

```text
M4 (milestone)
├─ ws1-deadline ─┐
├─ ws1-resume  ──┼─→ integration ─→ ws2-s3 ─→ milestone-review ─→ M4 report
└─ ws1-ledger  ─┘                      ↑
                                  (needs ws1-deadline)
```

Packages, in worksets (a workset is run in parallel, worksets in order):

| ws | package | delivers | acceptance command | status |
| --- | --- | --- | --- | --- |
| 1 | `deadline` | 期限：到点触发、在飞动作与打断，四件套（失败场景、规则、渲染、测试） | v5 gate green; `V5-PRIMITIVES.md` §8 的中途打断暂缓条被关掉 | taken 2026-10-21 |
| 1 | `resume` | 半天边界存档 + 因果续跑，从 v4 原样搬（不重造） | v5 gate green; 续跑后 event id/version 连续 | taken 2026-10-21 |
| 1 | `ledger` | v5 自己的历史失败台账 + 预门口径 | v5 gate green; 台账逐条映射到一个会失败的测试 | taken 2026-10-21 |
| 2 | `s3` | S3《夜市》种子、卡司、四条归属路径（认账/推给下一个/拿不回来/当众澄清）、制度角色与当众-私下说的库增长 | v5 gate green; 四条路径的轨迹可通读 | — |
| — | `s3-review` | 独立复核 ws2 | verdict per `Review` | — |
| — | `milestone-review` | M4 三条判据的整体复核（不是逐包裁决之和） | verdict | — |
| — | `docs-v5-shape` | `README.md`/`CONTEXT.md` 的运行与证据一节改成 v5 形状 | 两份文件里不存在指向 v4 为准的句子 | — |

## Decided

- **M4 is the next milestone** — root, contract to this layer dated 2026-10-21, assent: agreed. M3's signature stays with the person and does not block M4, whose skeleton is script-actor work needing no provider spend.
- **物权 does not enter the library** — root, same contract, assent: assumed. Placement is the seed layer, recorded in the lint as defined-at-use; S3's 押金条 and S4's 钥匙移交 are expressible with P3 containment. Reversal costs one concept added without its second declaring story.
- **v5 is exempt from the ticket tracker** — root, same contract, assent: agreed. A work package's contract, evidence and decision live in the commit message and in the milestone report; `.scratch/` is for defects found by running.
- **v5 is the main line** — `docs/adr/0002-v5-becomes-the-main-line.md`, assent: agreed.
- **Parallel writers get their own worktree, merged by this layer** — inference from `Git` (`one writer per area`, `worktree`, `integrator`): three packages editing one v5 tree would read each other's half-done edits while running the same gate, so the difference between their results would not come from the package. The manager holds the merge and runs the combined check.

## Open

- **M3 的签字在人手里** — `docs/plan/portfolio.md` files it under what waits on the person. Nothing here reconstructs it; M4 does not depend on it.
- **物权 的第二次声明** — the concept returns when a second story needs a held-by relation that containment cannot carry.
- **冲突记录**: `CONTEXT.md` 称"冲突时以其权威文档为准" and then states the v4 line is current; the authority it points at (v5) says otherwise. Resolved in favour of the ADR; the file itself is repaired by `docs-v5-shape`.

## Evidence

- The v5 gate and its three structural checks: `../AGENTS.md` § "v5 gate".
- Milestone definitions and the seven-story ladder: `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md`, scene requirements in `V5-SCENES.md`, primitives and the entry threshold in `V5-PRIMITIVES.md`.
- The orientation evidence for this roadmap: `mail/2026-10-21-orientation.md`.
- Root's answers of 2026-10-21: landed into the `Decided` list above and into `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §2.1/§3; the mail file was deleted after landing.
