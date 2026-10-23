kind:    report
from:    sys_gal
to:      root
spend:   idle class; ~30 minutes wall clock; no provider calls, no metered spend
id:      answer to the actor-pilot gate of 2026-10-23 and the advance that follows it (`3a95a3e`, `1253248`)

## Conclusion

The actor-pilot gate is closed, and it is closed as the person's answer, not as this layer's reading: **on 《借条》 alone**. 《末班车》's model-driven report does not stand in front of the gate — it moves into the next milestone's ladder, where the same world and the same checks run on a second story. I did not reopen it, and I did not touch M4's signature.

Then I carried the roadmap into **一日两个世界（M5）** and landed its first package: the model loop is now one loop that both stories share, and 《末班车》 runs it. That is the piece the person's placement actually needs — the *checks* now hold on a second story, so the second story's report is a run rather than a new implementation.

## Milestone advanced

**一日两个世界：便利店与宴会厅各自跑完一整天，同一套概念在两个世界都成立（M5）** — first package `second-story-agent`, landed at `1253248`. M5's own four acceptance claims are not claimed here and stay open.

## The command that shows it

From `契约失效时请勿喂猫/v5`, at `1253248`:

```text
python3 -m unittest tests.test_m5_second_story_agent -v       Ran 6 tests … OK
python3 -m unittest discover -s tests -p 'test_*.py'          Ran 143 tests … OK   (was 137)
python3 scripts/v5_lint.py --strict                           通过（待补 5 项）
python3 scripts/anti_cheat.py --verbose                       通过（3 支故事）
```

The six tests are the same checks that stood on 《借条》, now asked of 《末班车》: every action decided by the model, the context carried per turn, no state key and no other person's private belief in the prompt, the `context.md` header computed rather than written (with a negative control that flips the decider and requires the header to change), and the ending built from the story's own facts. Zero provider spend — a MockProvider drives the same loop.

## Two defects the second story surfaced, and what I did about them

Both are the kind of thing a second story is for; neither changed a rule.

1. **《末班车》's ending was looked up by script label.** A model run raised `KeyError` before it could write a trace — the story assumed its ending was one of its own three paths. Fixed the way 《借条》 already works: the ending is composed from world facts, and the three scripted sentences are unchanged.
2. **《末班车》's committed traces were stale.** They predated the date-in-glance fix and the `context.md` header fix (`R03`) and still said "M1/M2 的演员是脚本, 不读这些上下文" — so the evidence on disk contradicted the code, and the digests no longer reproduced from the tree. Regenerated with the documented command. That is a change to committed evidence, named here because it moved without a new run.

## Decisions needed from you

1. **The M4 signature** — unchanged from `mail/2026-10-21-m5-cross-night.md`, still with you and then the person. Nothing in M5's first package depends on it.
2. **A provider authorization for 《末班车》's real-model run** — the only reason that line is not also landed. It is now a run, not a build: `python3 -m stories.s1_last_bus.agent_run github_copilot/gpt-6-luna 3`, one unique `runs/agent-*` directory, read per `AGENTS.md`. Without a yes it stays open on the M5 ladder, and I will not spend it on my own reading.
3. **The two carried forward unchanged**: the taste call on two paths converging on one ending, and the push (`origin/master` is still `81f4c9d`; nothing here was pushed).

## Residual risks

- No real model has run 《末班车》. The gate's coverage is 《借条》's report plus the anti-cheat three; "pressure changes the agenda, not the floor" still comes from one world, two runs, one model.
- The six new tests prove the loop and the surface, not a model's choices on the second story.
- Regenerating 《末班车》's traces means the three committed script runs now differ from their earlier revisions (only through the two fixes above); anyone comparing across `9dc76d4..1253248` will see nine files move.
- M5's acceptance claims — stocktake computed from quantities, two worlds read through a whole day, same-scale comparison, packed traces — are all still open, and `stocktake` is the one most likely to force a library decision (quantity as first-class, or the seed carries it).
- `R10` still pins only the reversion to `2`.
- Nothing pushed: this advance is local disk until you push.

## Effort

Two commits, four files of new code, one test file, three documents. My part was the gate's landing, one package, and this report.
