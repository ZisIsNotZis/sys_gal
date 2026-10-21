# review of `pin-threshold` — one row, and the tree it protects

kind: worker (reviewer)
name: pin-review
serves: sys_gal roadmap, milestone M4
report: once, at the end. You hold no directory, document or roadmap. You repair nothing.

## rev

`/home/z/vibe/sys_gal`, `master`, `aec870c`, worktree clean; v5 tree `契约失效时请勿喂猫/v5`.

## accept — three checks

1. **The row discriminates.** In a `/tmp` copy, set `scripts/anti_cheat.py:96` back to
   `if len(distinct) < 2:` and run `python3 -m unittest tests.test_historical_failures`; the row must
   go red. Report the failure text. On the committed tree it must be green. Then judge: does the row
   test the predicate, or does it restate the implementation (a row that passes for the wrong reason
   is not a pin)?
2. **The row belongs to the ledger.** `tests/test_historical_failures.py` rows carry a class, an
   origin and what breaks without them. Say whether `R10`'s origin is a real observation (point at it)
   and whether it duplicates `R07`, which already covered endings.
3. **The three claim commands still run from the committed tree.** From
   `契约失效时请勿喂猫/v5`, exactly these, with results:
   `python3 -m unittest tests.test_m4_s3 tests.test_m4_resume tests.test_m4_deadline`,
   `python3 -m unittest discover -s tests -p 'test_*.py'`,
   `python3 -m stories.s3_night_market.run a b c d` followed by `git status --short` (must be empty).

## blocking / budget / escalate / repair

A check violated is `fail` with location and reproduction; `blocked` is not a pass. Wall-clock 10
minutes, no provider calls, no writes inside the project. Model `deepseek/deepseek-flash:high`.
Escalate once at the end if something belongs above this layer.
