# state — advance of 2026-10-23 (third pass: 一日两个世界 built, measured, and the numbers twice caught lying)

## Terms

- Contract: manager, sys_gal; the person's answer of 2026-10-23 that the anti-cheat script is a measuring tool, not a goal, and that a package is judged by its own milestone AC; idle machine time plus 4 worker rounds; zero provider spend.
- Base: `master` at `7120164`; nothing fetched, pulled or switched. Landed through `HEAD` at this writing.
- Report filed to `mail/2026-10-23-m5-two-worlds.md`, `to: root`.

## What this advance landed

| commit | what it is |
| --- | --- |
| `514310e` / `c2526ac` / `0be9bd5` | 《夜班》 and 《婚礼》 as two new worlds, merged by this layer (one conflict in `library/concepts.py`, union of both vocabularies); plus the fix that every 婚礼 path now reaches the 22:00 close, with a test that goes red if one quits early |
| `f458777` → `05571b8` → `9752808` | `same-scale`, three passes. Pass 1 was fake (13–17 failed actions counted as actions); pass 2 zeroed failures and made the day real; pass 3 unified the no-silent-gap rule across both stories and filled 婚礼's afternoon |
| `7950513` | `stocktake`: one reading, one exit (`library/stocktake.py`), reverse controls prove the number comes from the seed count |
| `521f582` | `pack`: 25 zstd artefacts for 100 raw files (3,172,688 bytes out of the index), `check` catches four kinds of bad |
| `v5/docs/V5-M5-COMPARISON.md` | the comparison report — seven concepts hold in both worlds, three do not |
| `9e25ce5`, `11677aa`, `2caaa9b`, this | plan, decisions, and the two lessons from the fake measurements |

## Gate at this tree (cwd `契约失效时请勿喂猫/v5`)

| check | reading |
| --- | --- |
| `python3 -m unittest discover -s tests -p 'test_*.py'` | 208 tests OK |
| `python3 scripts/v5_lint.py --strict` | 通过（待补 9 项） |
| `python3 scripts/anti_cheat.py --verbose` | 通过（5 支故事，各四条路四个不同结局） |
| `python3 scripts/pack_trajectory.py check` | 25 件工件与原始逐件一致 |

## Decided here (mine)

- The anti-cheat third check stays. Convergence is written as one path; no invented differences to feed it. The person's words, landed in `docs/PLAN.md`.
- Numbers are measured on what was done, never on what was attempted, and one rule measures both stories at once.
- The report's three "not yet true" findings are stated in the document the person reads, not left to a later reviewer.

## Open

- The person's judgement on `V5-M5-COMPARISON.md` — the only acceptance M5 has that no command can settle.
- Two small packages it opened: 婚礼's ten people present but barely participating; 夜班's manager speaks once per path.
- `R10`'s second half and the `schedule.effect` shape guard — queued, not pursued (the person's "don't spend time on the script").
- Library: `sign` vs `shift` express one act twice; split when a third world needs it without a shift boundary.
- The push: still nobody's, and the local line is now 85+ commits ahead of `upstream/master`.
- A second real-model run on 《末班车》 with its premise staged in the seed — needs a new authorization.
