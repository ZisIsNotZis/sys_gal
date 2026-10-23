# state — advance of 2026-10-21 (third pass, resume from `d02c395`)

## Terms

- Contract: manager, sys_gal; root's resume instruction of 2026-10-21; 25 minutes wall clock, no new package after 15; idle machine time, no provider calls.
- Base: `master` at `d02c395`; nothing fetched, pulled or switched.
- Outside me, untouched: the M3 gate verdict and the M4 acceptance. Neither was signed here.
- Report filed to `mail/2026-10-21-m5-cross-night.md`, `to: root`.

## What this advance did

| commit | what it is |
| --- | --- |
| `9dc76d4` | S3 crosses its 18:30→08:00 boundary: fifth path `e`, `NIGHT` time mark, `tests/test_m5_cross_night.py` with a negative control; `runs/e.*` added, a–d byte-identical |
| (this) | `mail/` split from `inbox/` (outbound vs inbound, `git mv`, no content edited); `docs/PLAN.md` and this file rewritten against the tree |

## Gate at `9dc76d4` (cwd `契约失效时请勿喂猫/v5`)

| check | reading |
| --- | --- |
| `python3 -m unittest discover -s tests -p 'test_*.py'` | 137 tests OK (was 134) |
| `python3 scripts/v5_lint.py --strict` | 通过（待补 5 项） |
| `python3 scripts/anti_cheat.py --verbose` | 通过（3 支故事）；s3 five paths, five endings |

## Decided here (mine)

- The night crossing is a script path, not a harness flag, so `anti_cheat` polices it and the fifth ending is the morning recovery. `NIGHT` is a time mark, not a verb — it enters no library, so it cannot become a story word the model sees.
- Outbound reports go to `mail/`; `inbox/` is inbound only and emptied on landing. Root's instruction named `mail/`, and the two files sitting in `inbox/` were both addressed `to: root`, so the split is a filing correction rather than a rename of a working convention.

## Open, unchanged

- The M4 signature (root's, then the person's); M3's verdict (the person's).
- May M5 begin — asked of root in the report; my reading is yes on the mechanism.
- The taste call on two paths converging on one ending; the push.
- `R10` pins only the reversion to `2`, not the general rule.
- The night is empty: 14 in-world hours with nobody acting. Continuity proven, density not.

## Next action

Waits on root's answer to "may M5 begin", not on a timeout. If yes, the first M5 slice is the one that makes the night dense rather than merely continuous.

## Advance of 2026-10-23 — the names the person could not read

Root carried the pilot gate question up and the person could not read it: `M3`, `S1`, `S2` and `V5-ROADMAP.md:57` are record handles, not names of things. This advance fixes it in the tree, not in the next message.

| commit | what it is |
| --- | --- |
| `74f542e` | V5 roadmap §2.2/§3 gain a 名字（对人怎么叫） column: every milestone named by what it proves, every story by title plus one clause of its situation; the status paragraph the person was pointed at leads with the names |
| `63a55b9` | the pilot report's title says what the gate proves; its one internal M4 is named in place |
| `b4396e7` | v5 front door: 玩具世界 / 库的第一次通用 / 演员试点 lead, codes follow |
| `2e91fd0` | this layer's roadmap: 半日一局, 一日两个世界, 演员试点, 《夜市》 named where they stood as codes |
| `0472e5b` | the rule itself, first line of `AGENTS.md`: 人读的东西先给名字，编号排在名字后面或干脆不出现 |
| `f1fff42` | `mail/2026-10-23-m3-pilot-gate-question.md`: the gate question as one sentence, no code, to be carried up unchanged |

The gate is not decided here. It is the person's and still open; the sentence only asks whether 《末班车》 needs a model run before the signature.

Gate after the advance, from `契约失效时请勿喂猫/v5`: 137 tests OK, `v5_lint --strict` 通过（待补 5 项）, `anti_cheat --verbose` 通过（3 支故事）.
