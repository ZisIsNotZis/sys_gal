# review of `fix-endings` — one package, one verdict

kind: worker (reviewer)
name: fix-endings-review
serves: sys_gal roadmap, milestone M4; review of the package `fix-endings`
report: once, at the end. You hold no directory, document or roadmap. You repair nothing.

## rev

`/home/z/vibe/sys_gal`, `master`, commit `bde3a7d`, worktree clean. The package is that commit
against `b37b55f`: `stories/s3_night_market/scenario.py`, `tests/test_m4_s3.py`, and the eight
regenerated `stories/s3_night_market/runs/{a,b,c,d}.{md,json}`.

## accept

The contract was `work/fix-endings-contract.md` (deleted on dispatch; its text is in the dispatch
commit `20649f5`). The defect: `test_four_paths_reach_four_endings` could not fail because it
counted distinct values of `ENDINGS[variant]`, a table keyed by the variant.

Judge four things:

1. **Is the ending now a fact about the world?** `ENDINGS` and `DECISIVE` are gone. Check that
   nothing in `scenario.py` or `tests/test_m4_s3.py` still maps a variant name to an outcome: no
   dict keyed by `"a".."d"` that decides a sentence, no fallback path that reinstates a label.
2. **Can the check fail?** Make path `d` end the way path `a` ends in a copy under `/tmp` (never in
   the project) and run `python3 -m unittest tests.test_m4_s3`; report the failure text. Then do
   the same for `scripts/anti_cheat.py`, since it reads the same value. If either stays green, that
   is a `fail` with the reproduction.
3. **Were the world outcomes preserved?** The four paths ended with the note in 摊主甲 (a), 摊主丙
   (b), 管理处 (c), 摊主甲 with a public decisive sentence (d), and 收摊前/后 = 是/是/否/是. Compare
   the four `runs/*.md` at `bde3a7d` against `b37b55f` (`git diff b37b55f bde3a7d -- …/runs`) and
   say whether anything but the 结局 / 决定性那句话 sentence moved.
4. **Is the decisive sentence still the decisive one?** `_decisive_turn` now picks the last speech by
   whoever held the note at that turn. Judge whether that can pick a sentence that is not the
   decision — and whether that weakens claim 2 (the public/private gap) relative to the old table.

## ran

The manager ran at `bde3a7d`, from `契约失效时请勿喂猫/v5`: 133 tests OK, `v5_lint --strict` 通过
（待补 5 项）, `anti_cheat --verbose` 通过（3 支故事）, the four runs print four distinct derived
endings, and `git status` is clean straight after a run. Re-run the gate yourself.

## blocking / budget / escalate / repair

A criterion above violated is `fail`: give the location and a reproduction. `blocked` with what is
missing is not a pass. Wall-clock 15 minutes, no provider calls, no writes inside the project, no
edits. Model `deepseek/deepseek-flash:high`. Escalate once, at the end, only if something belongs
above this package.
