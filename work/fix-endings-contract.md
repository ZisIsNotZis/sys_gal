# fix-endings — make claim 1's "four paths, four endings" able to fail

kind: worker
name: fix-endings
serves: sys_gal roadmap, milestone M4, defect recorded in `docs/PLAN.md` §Open
report: once, at the end. You hold no directory, document or roadmap. You repair only what this
contract names and nothing else.

## goal

`tests/test_m4_s3.py::test_four_paths_reach_four_endings` cannot fail. It counts distinct values
of `summary(...)["结局"]`, and that value is `ENDINGS[variant]` in
`stories/s3_night_market/scenario.py:98` — four literals keyed by the variant, so it is distinct
by construction. A milestone reviewer proved it unpoliced: replacing path `d`'s script with path
`a`'s leaves 18/18 tests green. This is the only gate on M4's claim 1's "four different endings,
not one ending re-labelled", so it is a real defect.

Make the ending a fact about the world, so that two paths which end the same way are counted as
one ending.

## scope

- `契约失效时请勿喂猫/v5/stories/s3_night_market/scenario.py` — `summary()`'s `结局` must be
  computed from what the world holds at the end: who the note's container is, who it passed
  through, whether the decisive sentence was said to one listener or to everyone in sight, and
  whether the last action fell before or after the scheduled close. Delete `ENDINGS`; do not keep
  it as a fallback.
- `契约失效时请勿喂猫/v5/tests/test_m4_s3.py` — the ending test must compare the derived values
  and must go red when two paths end the same way.
- `契约失效时请勿喂猫/v5/stories/s3_night_market/runs/{a,b,c,d}.md` (and any other committed run
  file whose bytes change) — regenerate them; they are evidence and must match what the scenario
  now emits.
- `契约失效时请勿喂猫/v5/scripts/anti_cheat.py` only if the derived value forces it; say so in the
  report if you touch it.
- Do not touch `engine/`, `library/`, the seed, or any other story.

## accept

1. Gate green from `契约失效时请勿喂猫/v5`, all three:
   `python3 -m unittest discover -s tests -p 'test_*.py'` and
   `python3 scripts/v5_lint.py --strict` and `python3 scripts/anti_cheat.py --verbose`.
2. The four paths still end in the four world outcomes they end in today: note in 摊主甲 (a),
   摊主丙 (b), 管理处 (c), 摊主甲 with the decisive sentence public (d); `收摊前/后` unchanged
   (是/是/否/是). These are facts to preserve, not to redesign.
3. The falsifiability probe, which is the whole point: in a copy of the tree under `/tmp` (never in
   the project), make path `d` end the way path `a` ends, then run
   `python3 -m unittest tests.test_m4_s3` — it MUST fail, and you report the failure text. Then
   delete the copy.
4. `python3 -m stories.s3_night_market.run a b c d` regenerates the committed run files exactly:
   `git status --short` is clean straight after a run on the committed tree.
5. `git diff --stat` names only the files this contract allows.

## paths

Working tree `/home/z/vibe/sys_gal`, branch `master`, commit at one cohesive step with a message
that says what was wrong and why the new value cannot be gamed. Do not push and do not switch
branch.

## spend

machine_time, idle class, no device held exclusively, no provider calls. Wall-clock 25 minutes.
Model deepseek/deepseek-flash:high.

## stop

At 25 minutes stop, commit what works, and report. Attempts 2; if you cannot make the probe go
red without redesigning the story, stop and report `blocked` with what stood in the way — do not
redesign the four paths.
