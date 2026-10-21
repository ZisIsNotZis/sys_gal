## Verdict — `fail` at `5578a8b`, with one blocking item

**Base I used.** `3a8350a` (`mail: root answers the first report, and the next milestone`, 11:33) — the last commit before the advance's first commit `0847af4` (21:53:15). Reason: `work/state.md` opens "advance of 2026-10-21 (M4)" with the contract clock at ~21:39, and every commit from 21:53 to 21:55 is that advance's own work; `3a8350a` is root's earlier mail drop and is outside it.
If the advance is instead read to include root's two mail commits (`bd000f9`, `3a8350a`), the base is `81f4c9d`. I used `3a8350a`.
**Change** = `3a8350a..5578a8b`, 7 commits, doc/record only: `0847af4`, `5bec821`, `87f4d5d`, `617bd49`, `93cc1ba`, `cb6ccfb`, `5578a8b`. No product code moved on `master`:

```text
git diff --stat 3a8350a 5578a8b → CONTEXT.md, docs/PLAN.md, work/{state,report-skeleton,ws1-review-contract}.md
```

**Acceptance used.** `docs/PLAN.md` §"Roadmap — M4 「半日 + S3《夜市》」" (definition at `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §3, row M4): claim 1 押金条的每种归属物理可达, claim 2 当众与私下的信息差真实, claim 3 续跑因果连续. Remaining-acceptance list: `work/state.md` §"Remaining acceptance for M4" (three claims, then `ws-review` per-package verdicts, then root's milestone judgement).

### Commands run by me at `5578a8b` (`master`, worktree clean)

| command | result |
| --- | --- |
| `cd 契约失效时请勿喂猫/v5 && python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 87 tests … OK`, exit 0 |
| `python3 scripts/v5_lint.py --strict` | `通过（待补 5 项）`, exit 0 |
| `python3 scripts/anti_cheat.py --verbose` | `通过（2 支故事…）`, exit 0 |
| `python3 -m stories.s3_night_market.run a b c d` | exit 1, `ModuleNotFoundError: No module named 'stories.s3_night_market'` — this is `work/report-skeleton.md`'s own state command |
| `python3 -m unittest tests.test_m4_s3 tests.test_m4_resume tests.test_historical_failures -v` | 3 errors, `ModuleNotFoundError` for each; `tests/` holds only `test_m1_*`, `test_m2_*`, `test_m3_agent.py` |
| `grep -rn "s3_night_market\|押金\|夜市" engine/` | 0 hits — vacuous, no S3 exists on this line |
| `grep -rn "checkpoint\|resume" engine/ library/ scripts/ tests/ --include='*.py' \| wc -l` | `0` |
| `grep -n "中途打断" docs/V5-PRIMITIVES.md` | `133` still the open deferral sentence |

### What holds

- The v5 structural gate is green at this revision: 87 tests, `v5_lint --strict`, `anti_cheat` all pass on `5578a8b`, so the docs commits of this advance broke nothing in the reference line's M1–M3 invariants.
- The bulk of `docs-v5-shape`'s intent landed: `CONTEXT.md` §运行与证据 (lines 46–70) now speaks about v5 with v4 explicitly the reference, and `README.md` says "The current line is v5".

### What does not hold

- **claim 1 fails** — reproduction: `python3 -m stories.s3_night_market.run a b c d` → `ModuleNotFoundError`.
- **claim 2 fails** — at this revision `speak` takes only `text`: `契约失效时请勿喂猫/v5/library/concepts.py:499-501` (`entity_args=()`) and `:532` (`"speak": (("text", …),)`); there is no per-recipient speech, so `speak(to=…)` has nothing to test.
- **claim 3 fails** — `0` hits for `checkpoint`/`resume` in v5 code; `tests/test_m4_resume.py` absent.
- **`deadline`'s acceptance fails, and merging will not fix it**: `docs/V5-PRIMITIVES.md:133` (the 中途打断 deferral the package must close) is still present on the package's own branch `pi-subagents/task-1-e61cb1b-bdf0-s0-t0` — `git show <branch>:…/V5-PRIMITIVES.md | grep -n 中途打断` → line 133.
- **`docs-v5-shape` is marked `done 2026-10-21` and its acceptance is false**: criterion is "两份文件里不存在指向 v4 为准的句子"; `CONTEXT.md:20, :35, :38, :43` still cite `V4-STORY-MILESTONES.md` §1, `V4-AGENT-INTERFACE.md` §6.1, `V4-CAST.md` as 权威, and the file's own line 4–5 says 冲突时以其权威文档为准, so those entries resolve in favour of v4. Separately `README.md:15` and `:27` point at `契约失效时请勿喂猫/ROADMAP.md` as "milestones and work packages" and "where it stands", while that file's line 3 states it is the v4 line's historical plan and 不再演进.
- **The remaining-acceptance list is untouched**: `work/ws1-review-contract.md:1` still reads "draft, not yet dispatched"; `mail/` holds only `2026-10-21-orientation.md` — the `mail/2026-10-21-m4-report.md` that `work/state.md` and `work/report-skeleton.md` name was never filed.

### Does the stop lose nothing — no

- **S3's only artefact is an unreachable commit**: `git fsck --unreachable` → `d51c1836` "S3《夜市》：种子+卡司+四条脚本路径…" (parent `5bec821`, 2026-10-21 22:00:08, 26 files, +4729), holding `stories/s3_night_market/` (seed, scenario, transcript, `runs/a–d`), `tests/test_m4_s3.py`, and the `library/` growth (impound, `speak(to=)`, four institution effects). It is on no ref: `git for-each-ref refs/heads | grep -i 'ws2\|worker'` → empty, no worktree under `~/vibe/worktrees/sys_gal/`, no reflog entry, no `git log --all` hit, `74af866` → 0 in the log and nothing in `.pi`. A default `git gc` deletes it.
- **`work/state.md` misdescribes its own durable home**: it lists ws2-s3 as "in flight" with branch `pi-subagents/worker-kind-worker-name-ws2-s3-…-74af866-9311-s0-t0` and run id `74af866e-…`, neither of which exists — under this record, the work is lost, not in flight.
- **`work/state.md` is stale inside its own advance**: it says "Master is at `87f4d5d`", false by three commits at `5578a8b`; a resumer reads the wrong base.
- **Nothing of the advance is pushed**: `origin/master` is `81f4c9d`; HEAD is 9 commits ahead, and the three ws1 branches are local only.

### Blocking (unsafe to pass even though the gate is green)

1. S3 unreachable + a record naming a branch that does not exist: a pass invites a merge/resume that either cannot find the package or finds it after gc has removed it.
2. `deadline`'s criterion is open on its own branch, so a green v5 gate merged would still not satisfy it — `ws-review` must not accept on the gate alone.
3. `docs/PLAN.md`'s status column now carries `done` on `docs-v5-shape` where the tree contradicts it; a pass would propagate that status upward.
4. The state record's base/HEAD line and the missing `mail/2026-10-21-m4-report.md` mean nothing here can be resumed from the record without first correcting it.

I do not judge whether stopping before ws-review was the right call; the defects above stand independently of it. `README.zh-CN.md:20` still says 活动线是 v4 while `README.md` and ADR 0002 say v5 — outside `docs-v5-shape`'s two-file scope, so residue rather than a criterion violation. I wrote no file in the project.