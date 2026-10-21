# state — advance of 2026-10-21 (second half)

## Terms

- Contract: manager, sys_gal; answers the independent verdict at `5578a8b`; wall-clock 120 minutes from ~22:07 +0800 → terminator 00:07; no new package after 23:07.
- Spend: machine_time, idle class, no device held exclusively, no provider calls.
- Base: `master` at `b64ae22`. The verdict's own base for the judged advance was `3a8350a`, change `3a8350a..5578a8b`.
- Report filed to `inbox/2026-10-21-m4-report.md`, `to: root`. This file stays as the advance record.

## The chain of commits, in order

| commit | what it is |
| --- | --- |
| `5b35c9a` | verdict landed; `docs/PLAN.md` and this file rewritten against the tree; `mail/` became `inbox/` |
| `09962fb` | `deadline` merged (`d7b8219`) — 100 tests |
| `d62eb37` | `V5-PRIMITIVES.md` §8's 中途打断 deferral killed; P4 states the interval |
| `7ebdde5` | `resume` merged (`95cee2a`) — 104 tests |
| `d8af14c` | `ledger` merged (`e20e8a5`) — 114 tests |
| `a0e307a` | `s3` merged (`d51c183`, the artefact the verdict found unreachable) — 132 tests |
| `cbf54bd` | `ws-review` dispatched, contract with rev and four per-package questions |
| `263fa0c` | `docs-v5-shape` repaired — no front-door file points at v4 as 权威 |
| `3562e85` | `m4-milestone-review` dispatched |
| `a802289` | `ws-review` verdict: four `pass`; one residual kept, one reviewer claim refuted by search |
| `df26ef3` | milestone verdict: claim 1, 2 `reached`; claim 3 mechanism only; one unfalsifiable test |
| `bde3a7d` | `fix-endings` — `结局` derived from the end-of-run world; `ENDINGS`/`DECISIVE` deleted |
| `e730c09` | review of `fix-endings`: `fail`, narrow — `anti_cheat`'s threshold still `< 2` |
| `6063e1c` | `fix-threshold` — `len(distinct) < len(variants)` |
| `6c096e6` | review: `pass`; residual — nothing pins the new predicate |
| `aec870c` | `pin-threshold` — ledger row `R10`, red when the threshold reverts to `2` |
| `c719997` | review of the pin: `pass`; residual — a constant `3` would still pass `R10` |

## Gate, after each merge (from `契约失效时请勿喂猫/v5`)

| rev | tests | v5_lint --strict | anti_cheat |
| --- | --- | --- | --- |
| `b64ae22` baseline | 87 OK | 通过（待补 5 项） | 通过（2 支故事） |
| `09962fb` | 100 OK | 通过 | 通过（2 支故事） |
| `7ebdde5` | 104 OK | 通过 | 通过（2 支故事） |
| `d8af14c` | 114 OK | 通过 | 通过（2 支故事） |
| `a0e307a` | 132 OK | 通过 | 通过（3 支故事） |
| `aec870c` (final) | 134 OK | 通过（待补 5 项） | 通过（3 支故事） |

## The three claims, at `aec870c`

- **claim 1** — `python3 -m unittest tests.test_m4_s3`; four paths end with the note in 摊主甲, 摊主丙, 管理处, 摊主甲-with-a-public-sentence. Milestone review: `reached`, with the note that 乙 is never a terminal holder, so "each ownership reachable" is proven as reachability, not as an ending.
- **claim 2** — `speak(to=…)` delivers words to the addressee and 「低声说话」 to onlookers; the leak mutation turns the test red. Milestone review: `reached`.
- **claim 3** — `python3 -m unittest tests.test_m4_resume`: prefix equality, whole-log replay equality against an uninterrupted control, tampered checkpoint refused. Milestone review: `reached` for the mechanism, **not** for the premise — the boundary is S1's 23-minute midpoint and no test cuts S3.

## What is mine to decide here, and what is not

- Mine, decided: M5 may not claim all-day continuity before something actually cuts S3 at its 18:00→08:00 boundary (recorded in `docs/PLAN.md` §Decided).
- Mine, decided: `anti_cheat`'s threshold was a code gap, not a wording gap — the sentence was right and the implementation was weaker.
- Not mine: whether a story may write two paths that converge on one ending — taste, forwarded in the report; my recommendation is to keep the sentence and treat convergence as one path written twice.
- Not mine: the M4 signature. Root's, then the person's.

## Residual risks, named

- claim 3's premise (above); the "half day" is a label on a 13-minute story, and the 1110 close does no work in three of four paths.
- 乙 never ends holding the note.
- `R10` pins the reversion to `2` but a constant `3` would still pass it; one extra case closes it.
- Every verdict here came from a `deepseek/deepseek-flash` reviewer in a fresh context; no human has read the four transcripts.
- Nothing pushed: `origin/master` is `81f4c9d`.

## Next action

The report to root; then this layer waits for the signature, not on a timeout.
