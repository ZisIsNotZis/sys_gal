# state — advance of 2026-10-21 (second half)

## Terms

- Contract: manager, sys_gal; answers the independent verdict at `5578a8b`; wall-clock 120 minutes from ~22:07 +0800 → terminator 00:07; no new package after 23:07.
- Spend: machine_time, idle class, no device held exclusively, no provider calls.
- Base: `master` at `b64ae22` (the commit that filed the verdict and the contract). The verdict's base for the judged advance was `3a8350a`, change `3a8350a..5578a8b`.
- Report goes to `inbox/`, `to: root`, four header lines.

## Tree as it stands (written through at each step)

- `master` at `b64ae22`, integration branch, worktree clean, no push (root holds the push).
- v5 gate at `b64ae22`: 87 tests OK, `v5_lint --strict` 通过（待补 5 项）, `anti_cheat --verbose` 通过（2 支故事）. This is the baseline; a red gate after a merge belongs to that merge.
- Four package branches exist and each has commits ahead of its merge-base; none is merged:
  - `pi-subagents/task-1-e61cb1b-bdf0-s0-t0` `d7b8219` — deadline (engine/agent.py, engine/rules.py, tests/test_m4_deadline.py), base `0847af4`
  - `pi-subagents/task-2-5d14cf4-6f34-s0-t0` `95cee2a` — resume (engine/checkpoint.py, tests/test_m4_resume.py), base `0847af4`
  - `pi-subagents/task-3-edfa688-7b3b-s0-t0` `e20e8a5` — ledger (tests/test_historical_failures.py), base `0847af4`
  - `ws2-s3-recovered` `d51c183` — s3 (stories/s3_night_market/*, library growth, tests/test_m4_s3.py), base `5bec821`; recovered from the unreachable commit of the same id by root.

## Verdict at `5578a8b` — what it opened

Independent verdict, `fail`, one blocking class and four items. Landed into `docs/PLAN.md` §Verifying M4; this file keeps only the disposition.

1. `ws2-s3`'s only artefact was unreachable and the record named a branch that does not exist → closed by merging `ws2-s3-recovered`.
2. `deadline`'s criterion (the 中途打断 deferral at `v5/docs/V5-PRIMITIVES.md` §8) is open on its own branch → closed by the merge of `d7b8219` plus the doc sentence killed in the same act.
3. `docs-v5-shape` carries `done` where the tree contradicts it → closed by repairing the tree and then the status line.
4. `work/state.md` described a tree it was not in (stale HEAD, a mail file that was never filed) → closed by this rewrite.

## Remaining acceptance for M4

- claim 1 押金条每种归属物理可达 → `test_m4_s3` + the four `runs/a…d` transcripts.
- claim 2 当众与私下信息差真实 → the `speak(to=…)` assertions in `test_m4_s3`.
- claim 3 续跑因果连续 → `test_m4_resume`.
- Independent review of each package (ws-review) and the milestone judgement, which is root's, not this layer's.

## Next action

Merge the four branches one at a time, gate after each, then the combined check; then dispatch one fresh reviewer over the four packages; then report to root.
