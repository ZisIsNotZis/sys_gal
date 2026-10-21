# ws-review — four packages of workset 1 and 2, one reviewer, coverage explicit

kind: worker (reviewer)
name: ws-review
serves: sys_gal roadmap, milestone M4; review of packages `deadline`, `resume`, `ledger`, `s3`
report: once, at the end. You hold no directory, document or roadmap. You repair nothing.

## rev

`/home/z/vibe/sys_gal`, `master`, commit `a0e307a` — all four merged, worktree clean. Read the
diff of each package against its merge-base and the code as it stands at `a0e307a`:

- `deadline` — `git show d7b8219`, merge-base `0847af4`; `engine/agent.py`, `engine/rules.py`, `tests/test_m4_deadline.py`
- `resume` — `git show 95cee2a`, merge-base `0847af4`; `engine/checkpoint.py`, `tests/test_m4_resume.py`
- `ledger` — `git show e20e8a5`, merge-base `0847af4`; `tests/test_historical_failures.py`
- `s3` — `git show d51c183`, merge-base `5bec821`; `stories/s3_night_market/`, `library/` growth, `tests/test_m4_s3.py`

Do not read the implementers' conversation or their completion claims. Read the diff and the
code.

## ran / accept

The manager ran at `a0e307a`, from `契约失效时请勿喂猫/v5`: 132 tests OK, `v5_lint --strict`
通过（待补 5 项）, `anti_cheat --verbose` 通过（3 支故事）, and `python3 -m stories.s3_night_market.run a b c d`
printing four one-line summaries. Re-run the gate yourself before judging:

```text
cd /home/z/vibe/sys_gal/契约失效时请勿喂猫/v5
python3 -m unittest discover -s tests -p 'test_*.py' && python3 scripts/v5_lint.py --strict && python3 scripts/anti_cheat.py --verbose
```

Judge only what a program cannot decide. Four questions per package:

1. `deadline`: is the scheduled effect still physics-or-institution rather than destiny? Does the
   interrupt change what the actor and the onlookers perceive, or does it only flip a flag? Is the
   engine still free of story nouns? Is the new capability expressible with the ten primitives
   (`V5-PRIMITIVES.md` §9), or does it smuggle an eleventh one in?
2. `resume`: does the continuity assertion actually prove causality (replay equality of the whole
   log), or does it assert something weaker while claiming continuity? Can a checkpoint overwrite
   an existing artefact? Is the story-module import path in `engine/checkpoint.py` free of story
   nouns?
3. `ledger`: does each row name a failure that was observed somewhere real (path + section, or
   commit)? Is at least one row a tautology that cannot fail? Is any row merely re-running an
   existing test without adding discrimination?
4. `s3`: are the four ownership paths physically reachable — that is, does each terminal holder
   follow from the rules and the seed rather than from a script that asserts the outcome? Is the
   public/private gap carried by `speak(to=…)` and the render layer rather than by a note on an
   event? Is the closing-time effect an institution effect rather than an actor's action? Do the
   `runs/a…d` transcripts exist as committed evidence and match what the scenario produces?

## blocking

A package is `fail` when a criterion above is violated: give the violated criterion, the location
and a reproduction command. `blocked` with what is missing is not a pass.

## budget / escalate / repair

Wall-clock 20 minutes, no provider calls, no file writes inside the project. Model
`deepseek/deepseek-flash:high`. You do not repair: you report. Return one verdict per package,
each `pass` / `fail` / `blocked`, and escalate to the manager once, at the end.
