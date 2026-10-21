# review of the two closing commits — `fix-endings` cure and `anti_cheat` threshold

kind: worker (reviewer)
name: threshold-review
serves: sys_gal roadmap, milestone M4; review of `bde3a7d` (the `fix-endings` package) and
`6063e1c` (the one-line cure the previous review asked for)
report: once, at the end. You hold no directory, document or roadmap. You repair nothing.

## rev

`/home/z/vibe/sys_gal`, `master`, `6063e1c`, worktree clean. v5 tree `契约失效时请勿喂猫/v5`.
Previous review, which you may read as a claim and not as evidence:
`work/fix-endings-review-contract.md` states its criteria; the verdict it returned is the commit
message of `e730c09`.

## accept

One verdict covering both commits, and these four checks, each with a reproduction:

1. **The threshold now enforces the sentence.** `scripts/anti_cheat.py:96` tests
   `len(distinct) < len(variants)`. Probe in a `/tmp` copy: `SCRIPTS["d"] = SCRIPTS["a"]` appended to
   `stories/s3_night_market/scenario.py` → `python3 scripts/anti_cheat.py --verbose` must exit
   non-zero and name 3 of 4. Report the exit code and the line.
2. **The stronger threshold does not invent failures.** On the committed tree it exits 0 and prints
   通过 for all three stories. Check what the new threshold would do to the two stories you did not
   touch: can a legitimate story in this library have two paths that end the same way? If yes, name
   it — that would make the cure a rejection of a legal world rather than a defect fix.
3. **Nothing else moved.** `git diff --stat b37b55f 6063e1c` names only `scenario.py`,
   `tests/test_m4_s3.py`, the eight run files and `scripts/anti_cheat.py`. The four world outcomes
   are still (甲,私下,是) (丙,当众,是) (管理处,私下,否) (甲,当众,是).
4. **The gate is green and the runs are the scenario's own bytes.** 133 tests, `v5_lint --strict`,
   `anti_cheat`; and `git status --short` empty straight after
   `python3 -m stories.s3_night_market.run a b c d`.

## blocking / budget / escalate / repair

A check above violated is `fail` with the location and the reproduction; `blocked` with what is
missing is not a pass. Wall-clock 12 minutes, no provider calls, no writes inside the project.
Model `deepseek/deepseek-flash:high`. Escalate once, at the end, only if something belongs above
this layer.
