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

## Gate after each merge (run from `契约失效时请勿喂猫/v5`)

| rev | tests | v5_lint --strict | anti_cheat |
| --- | --- | --- | --- |
| `b64ae22` (baseline) | 87 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `09962fb` | 100 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `7ebdde5` | 104 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `d8af14c` | 114 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `a0e307a` | 132 OK | 通过（待补 5 项） | 通过（3 支故事） |

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

The four terminal holders are four different places and the four decisive sentences split two
public and two private, so claim 1 and claim 2 are at least *exercised* by the integrated tree;
whether they are *reached* is the milestone reviewer's verdict, not this file's.

## What is still open

- `ws-review` verdict per package, and `m4-milestone-review` on the three claims. Both contracts
  are in `work/`, both reviewers run in a fresh context and neither repairs.
- The milestone signature: root's, and above that the person's. Nothing here signs it.
- Not pushed: `origin/master` is `81f4c9d`; this advance is local only, as the contract says.

## Next action

Land both verdicts into `docs/PLAN.md`, then file the report to `inbox/` and return.
