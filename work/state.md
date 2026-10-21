# state — advance of 2026-10-21 (second half)

## Terms

- Contract: manager, sys_gal; answers the independent verdict at `5578a8b`; wall-clock 120 minutes from ~22:07 +0800 → terminator 00:07; no new package after 23:07.
- Spend: machine_time, idle class, no device held exclusively, no provider calls.
- Base: `master` at `b64ae22` (the commit that filed the verdict and the contract). The verdict's base for the judged advance was `3a8350a`, change `3a8350a..5578a8b`.
- Report goes to `inbox/`, `to: root`, four header lines.

## Which commits are which

| step | commit | what it closed |
| --- | --- | --- |
| verdict landed, `mail/` became `inbox/` | `5b35c9a` | item 4 (state record) and the message-shape migration |
| `deadline` merged | `09962fb` (package `d7b8219`) | item 2, first half: the code and its 13 checks |
| 中途打断 deferral killed, P4 stated | `d62eb37` | item 2, second half: `V5-PRIMITIVES.md` §8 |
| `resume` merged | `7ebdde5` (package `95cee2a`) | claim 3's mechanism |
| `ledger` merged | `d8af14c` (package `e20e8a5`) | the pre-gate v5 must have before a real run |
| `s3` merged | `a0e307a` (package `d51c183`) | item 1: the unreachable artefact is an ancestor of `master` |
| `ws-review` dispatched | `cbf54bd` | the verdict on the four packages, by someone else |
| `docs-v5-shape` repaired | `263fa0c` | item 3 |
| `m4-milestone-review` dispatched | `3562e85` | the verdict on the three claims as a whole |
| `ws-review` verdict landed | `a802289` | four `pass`, one residual kept, one reviewer claim refuted |
| `milestone-review` verdict landed | `df26ef3` | claims 1 and 2 reached, 3 reached in mechanism only, one unfalsifiable test |
| `fix-endings` dispatched | `20649f5` / `a4dd6c9` | the unfalsifiable test, with a probe that must go red |

## Gate after each merge (run from `契约失效时请勿喂猫/v5`)

| rev | tests | v5_lint --strict | anti_cheat |
| --- | --- | --- | --- |
| `b64ae22` (baseline) | 87 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `09962fb` | 100 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `7ebdde5` | 104 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `d8af14c` | 114 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `a0e307a` | 132 OK | 通过（待补 5 项） | 通过（3 支故事） |

## What the reviews said, in one line each

- **ws-review** (`a0e307a`, re-gated at `8c8b881`): `deadline`, `resume`, `ledger`, `s3` all `pass`; its two mutation probes (unknown-effect guard, checkpoint `os.link`) are what separates a live test from a tautology. Two residuals: S3's `结局` is a hand-written label; the ledger's v4 citations point outside the repo. The second is refuted — `git ls-files 契约失效时请勿喂猫/v4 | wc -l` → 215, the file it named exists, and the reviewer's search used a path pattern that could not match.
- **milestone-review**: claim 1 `reached` (with the note that 乙 never ends holding the note), claim 2 `reached` (leak mutation turns the test red), claim 3 `reached` for the mechanism and not for the premise — the boundary is S1's 23-minute midpoint and no test checkpoints S3. Defect: `test_four_paths_reach_four_endings` cannot fail (path `d` := path `a` → 18/18 green). Escalation: M5 must not claim all-day continuity before something cuts S3 at its 18:00→08:00 boundary — decided that way in `docs/PLAN.md` §Decided.

## Combined check at `a0e307a` — mine, not the sum of package verdicts

```text
cd 契约失效时请勿喂猫/v5
python3 -m unittest tests.test_m4_s3 tests.test_m4_resume tests.test_m4_deadline tests.test_historical_failures
  → Ran 45 tests … OK
python3 -m stories.s3_night_market.run a b c d
  a: 条子在摊主甲 / 决定性的话私下 / 收摊前赶上：是 / 认账
  b: 条子在摊主丙 / 决定性的话当众 / 收摊前赶上：是 / 推给下一个
  c: 条子在管理处 / 决定性的话私下 / 收摊前赶上：否 / 拿不回来（管理处锁着）
  d: 条子在摊主甲 / 决定性的话当众 / 收摊前赶上：是 / 当众澄清
grep -rn "s3_night_market\|押金\|夜市" engine/   → no output (blindness gate at source)
```

Note the shape of these four: three distinct terminal holders across four paths, and `a`/`d` differ
by audience rather than by ownership. That is a fact about what the story proves, not a defect in it.

## What is still open

- `fix-endings` in flight (`20649f5` contract, base `2af2880`); its verdict is the reviewer's, not
  this file's. It needs one fresh review after it lands.
- The milestone signature: root's, and above that the person's. Nothing here signs it.
- Not pushed: `origin/master` is `81f4c9d`; this advance is local only, as the contract says.

## Next action

Review `fix-endings` in a fresh context, land its verdict, then file the report to `inbox/` and
return.
