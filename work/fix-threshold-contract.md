# fix-threshold — make `anti_cheat`'s third check as strong as its own sentence

kind: worker
name: fix-threshold
serves: sys_gal roadmap, milestone M4; the `fail` returned by the review of `fix-endings`
report: once, at the end. You hold no directory, document or roadmap. You repair only what this
contract names.

## goal

`契约失效时请勿喂猫/v5/scripts/anti_cheat.py:96` reads `if len(distinct) < 2:`, while the same
file's criterion on line 6 and line 80 says every written path must reach a different ending. A
reviewer proved the gap: with `SCRIPTS["d"]` set to `SCRIPTS["a"]` in a copy, `anti_cheat` exits 0
and prints two identical endings for `a` and `d`. The same reviewer verified the cure: threshold
`len(variants)` makes the correct tree pass and the mutated tree fail with
`4 条路径只走到 3 个结局`.

I rule it a code gap, not a wording gap: the check's sentence is right and its implementation is
weaker.

## scope

- `契约失效时请勿喂猫/v5/scripts/anti_cheat.py` — the threshold, and the failure message if it
  does not already name how many endings were reached out of how many paths.
- Nothing else. Not `engine/`, not `library/`, not a story, not a seed, not a document.

## accept

1. On the committed tree, from `契约失效时请勿喂猫/v5`:
   `python3 scripts/anti_cheat.py --verbose` exits 0 and still prints 通过 for all three stories
   (so no story currently relies on two paths sharing an ending — if one does, stop and report
   `blocked` with which story and which two paths, because then the decision is mine to make, not
   yours).
2. `python3 -m unittest discover -s tests -p 'test_*.py'` and `python3 scripts/v5_lint.py --strict`
   stay green.
3. Probes, in `/tmp` copies only, each reported with its exit code and output line:
   a. `SCRIPTS["d"] = SCRIPTS["a"]` → `anti_cheat` exits non-zero and names 3 of 4;
   b. all four paths collapsed onto `a` → exits non-zero and names 1 of 4.
4. `git status --short` clean afterwards; `git diff --stat` names only `scripts/anti_cheat.py`.

## paths / spend / stop

Working tree `/home/z/vibe/sys_gal`, branch `master`, one commit with a message that quotes the old
threshold and the probe that now refuses. Do not push, do not switch branch. machine_time, idle
class, no provider calls. Wall-clock 15 minutes, model `deepseek/deepseek-flash:high`. Attempts 2.
If a story legitimately shares an ending between two paths, stop and report `blocked`.
