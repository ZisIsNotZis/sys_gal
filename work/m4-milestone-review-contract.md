# milestone-review — M4's three claims, judged whole rather than as the sum of four package verdicts

kind: worker (reviewer)
name: m4-milestone-review
serves: sys_gal roadmap, milestone M4 「半日 + S3《夜市》」
report: once, at the end. You hold no directory, document or roadmap. You repair nothing.

## rev

`/home/z/vibe/sys_gal`, `master`, worktree clean; name the commit you read in your report.
The v5 tree is `契约失效时请勿喂猫/v5`.

## accept

M4's acceptance is three observable claims, quoted from `v5/docs/V5-ROADMAP.md` §3 row M4:

1. 押金条的每种归属都物理可达 — every ownership of the deposit note is physically reachable.
2. 当众与私下的信息差真实 — the public/private information gap is real.
3. 续跑因果连续 — a resume from a half-day boundary is causally continuous.

The milestone definition is `契约失效时请勿喂猫/v5/docs/V5-ROADMAP.md` §3; the story requirements
are `v5/docs/V5-SCENES.md` §S3 and §D.

## judge

Two questions, and they are different:

- **Is each claim reached as stated?** Not "does a test with this name exist". For claim 1, decide
  whether each terminal holder of the note follows from the seed and the rules, and whether the
  four paths are four different endings rather than one ending re-labelled. For claim 2, decide
  whether the gap is carried by the world (who is delivered which words) rather than asserted by
  the scenario. For claim 3, decide whether what is proved is causal continuity — replay equality
  across the boundary — rather than a file being written and read back.
- **Is this the thing the milestone promised?** Read `stories/s3_night_market/runs/{a,b,c,d}.md`
  as a stranger would: can the stakes be stated after reading one of them, does the closing-time
  institution do the work, is the cast's knowledge bounded by what they were delivered.

Run these yourself and say what they showed:

```text
cd /home/z/vibe/sys_gal/契约失效时请勿喂猫/v5
python3 -m unittest tests.test_m4_s3 tests.test_m4_resume tests.test_m4_deadline -v
python3 -m stories.s3_night_market.run a b c d
python3 -m unittest discover -s tests -p 'test_*.py' && python3 scripts/v5_lint.py --strict && python3 scripts/anti_cheat.py --verbose
grep -rn "s3_night_market\|押金\|夜市" engine/
```

## change / ran / blocking / escalate

`change`: report what you compared (the commit, the commands). `ran`: the commands and their
results. `blocking`: a claim that is `fail` gets the violated part and a reproduction; `blocked`
with what is missing is not a pass. `escalate`: one line to the manager at the end, only if
something belongs above this milestone. You do not repair, you do not sign for the person, and you
do not decide whether M4 ships: you decide whether the three claims hold and whether the thing
delivered is the thing promised.

## budget / repair

Wall-clock 20 minutes, no provider calls, no writes inside the project. Model
`deepseek/deepseek-flash:high`.
