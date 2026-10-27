# Contributing

`sys_gal` is a research prototype: a reproducible Chinese narrative-simulation lab. Contributions are welcome — code, concepts for `library/`, new stories, documentation, or a defect that should become a regression test. Chinese and English are both fine in issues, commits and docs.

## Scope

The main line is `契约失效时请勿喂猫/v5/`. `v4/` and earlier are archived for provenance and are not a specification; do not "fix" them. Please keep changes inside the layer that owns the fact:

- `engine/` must stay **story-neutral** — no story nouns, no concrete verb, no world property (the lint checks this).
- `library/` concepts arrive as a set: property, rule, renderer, failure receipt, and tests (at least one success, one failure, one "someone else cannot see it"). A concept used by only one story stays in that story's seed as a local override.
- `stories/<story>/` holds facts only: a strict `seed.yml`, the cast script, this story's acceptance. Logic, plot and imperatives aimed at a named character do not belong there.

One fact, one home. If something is already written in a doc, point at it rather than repeating it. Decisions with rejected branches go in `docs/adr/`; milestones and open questions go in `docs/0_ROADMAP.md`.

## Running the checks

From `契约失效时请勿喂猫/v5/` (Python 3, `PyYAML`; `zstd` for packing):

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/v5_lint.py --strict
python3 scripts/anti_cheat.py --verbose
python3 scripts/pack_trajectory.py check
```

All four are green before a change is worth reviewing. There is no CI — the gates are run by hand. If you add a judgement, add the thing that turns it red: a test, an assertion, a lint rule, or a failing example. A gate that cannot fail is not a gate.

If you regenerate trajectories with `python3 -m stories.<story>.run …`, run `python3 scripts/pack_trajectory.py pack` afterwards and commit the packed artifacts, so `git status` is clean and `check` stays green.

## Pull requests

- Small and single-purpose: one atomic fact or fix per commit, with a message that says what changed and what it now proves.
- Say which gate you ran and paste the relevant output; if a claimed number came from a run, name the artifact it came from (`runs/<story>-<route>.jsonl.zst`).
- Do not include credentials, raw run directories (`stories/*/runs/` is ignored on purpose), or large local files.
- New stories are accepted on the terms in `docs/5_PRODUCT.md`: a one-line pitch, at least two physically reachable endings, the three anti-cheat checks green, byte-identical replay, and one reverse fixture for the mistake that story most fears.

## Issues

Use an issue for a defect you can point at (file, route, event number, what you expected), or for a design question the roadmap has not answered. Bug reports that include the failing command and its exact output are worth ten that do not. If you are reporting an observed run problem, attach the trajectory name and the turn where it goes wrong — a fix without a reproducing case is a guess.
