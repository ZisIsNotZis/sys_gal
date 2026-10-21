# ws1 review contract (draft, not yet dispatched)

Dispatched after the three workset-1 packages are merged; one fresh reviewer covering all three, coverage explicit. This file is deleted on dispatch.

kind: worker
name: ws1-review
serves: sys_gal roadmap, milestone M4; review of packages `deadline`, `resume`, `ledger`
report: once, at the end. You hold no directory, document or roadmap.

## rev

The commit ids the manager names in the dispatch line, merged into `master` of `/home/z/vibe/sys_gal`, worktree clean.

## accept / change / ran / judge

You are given, per package, the commit id and the gate output the implementer claims. Re-run the gate yourself: `cd 契约失效时请勿喂猫/v5 && python3 -m unittest discover -s tests -p 'test_*.py' && python3 scripts/v5_lint.py --strict && python3 scripts/anti_cheat.py --verbose`.
Do not read the implementers' conversation or their completion claims. Read the diff (`git show <id>`) and the code as it stands.

Judge only what a program cannot decide:
1. `deadline`: is a scheduled effect still physics-or-institution rather than destiny? Does the interrupt change what the actor and the onlookers perceive, or does it only flip a flag? Is the engine still free of story nouns? Could the new verb be expressed with the ten primitives without every user re-implementing the same invariant (V5-PRIMITIVES §9)?
2. `resume`: does the continuity assertion actually prove causality (replay equality of the whole log), or does it assert something weaker while claiming continuity? Does a checkpoint ever overwrite an existing artefact?
3. `ledger`: does each row name a failure that was observed somewhere real (path + section, or commit)? Is at least one row a tautology that cannot fail? Is any row merely re-running an existing test without adding discrimination?

## blocking

A package is `fail` when a criterion above is violated; give the violated criterion and a reproduction command. `blocked` with what is missing is not a pass.

## budget / escalate / repair

wall-clock 20 minutes, no provider calls, model deepseek/deepseek-flash:medium. You do not repair: you report. Escalate to the manager, once, at the end.
