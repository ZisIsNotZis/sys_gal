# pin-threshold — the fixed predicate must be enforced by a check that runs unasked

kind: worker
name: pin-threshold
serves: sys_gal roadmap, milestone M4, verification regime of the v5 line
report: once, at the end. You hold no directory, document or roadmap.

## goal

The reviewer of `6063e1c` found that the repaired anti-cheat predicate is protected only by a
remembered step: revert `scripts/anti_cheat.py:96` from `len(distinct) < len(variants)` to
`len(distinct) < 2` and all 133 tests stay green. A check nobody re-runs is a check that can rot.
Make the suite catch that reversion.

## scope

- `契约失效时请勿喂猫/v5/tests/test_historical_failures.py` — one new row in that file's own shape
  (class, origin, what breaks without it), following the file's existing convention for `R` rows.
  It must fail if the threshold is weakened: the row builds a tiny scenario with N paths and fewer
  than N endings, runs the anti-cheat reachability check, and requires it to refuse.
- Nothing else. Not `scripts/anti_cheat.py` (the predicate is already right), not `engine/`, not
  `library/`, not a story, not a document.

## accept

1. On the committed tree, from `契约失效时请勿喂猫/v5`:
   `python3 -m unittest discover -s tests -p 'test_*.py'` green, `python3 scripts/v5_lint.py --strict`
   green, `python3 scripts/anti_cheat.py --verbose` green.
2. The reversion probe, in a `/tmp` copy: set `scripts/anti_cheat.py` line 96 back to
   `if len(distinct) < 2:` and run `python3 -m unittest tests.test_historical_failures` — the new
   test MUST fail. Report the failure text. Delete the copy.
3. `git diff --stat` names only `tests/test_historical_failures.py`; `git status --short` clean.

## paths / spend / stop

Working tree `/home/z/vibe/sys_gal`, branch `master`, one commit whose message quotes the reversion
probe. Do not push, do not switch branch. machine_time, idle class, no provider calls. Wall-clock
15 minutes, model `deepseek/deepseek-flash:high`, attempts 2. If the row cannot be written without
touching `anti_cheat.py`, stop and report `blocked` with what stood in the way.
