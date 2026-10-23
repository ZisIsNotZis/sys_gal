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
