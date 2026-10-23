kind:    report
from:    sys_gal
to:      root
spend:   idle class; ~28 minutes wall clock; no provider calls, no metered spend
id:      answer to the withdrawal of the half-day question of 2026-10-23 (`7ef0616`)

## Conclusion

The question is withdrawn and I did not re-ask it. It was not a question because the doubt was about a name, and a false name is mine to fix. Both halves are fixed, and the two things that were false about 「半日」 are now false about nothing.

## What was fixed, and the command that shows it

From `契约失效时请勿喂猫/v5`, at `7ef0616`:

```text
python3 -m unittest tests.test_m5_cross_night -v        Ran 4 tests … OK   (one new: the morning reads the next date)
python3 -m unittest tests.test_historical_failures -v    Ran 14 tests … OK  (R11 is new)
python3 -m unittest discover -s tests -p 'test_*.py'     Ran 147 tests … OK
python3 scripts/v5_lint.py --strict                      通过（待补 5 项）
python3 scripts/anti_cheat.py --verbose                  通过（3 支故事）
```

1. **The morning now reads as the morning.** `engine/surface.py:clock_label(minutes, date)` rolls the day when it has a date: `1920` on 2026-04-02 prints `2026-04-03 08:00`, and the same number without a date still prints `32:00` — that second line is the negative control, so the roll is the date's work and not a formatter's coincidence. `runs/e.md` now shows the next morning at 08:00, 08:02, 08:04.
2. **The false label left the tests.** `tests/test_m4_resume.py:half_day_clock` was the midpoint of 《末班车》's 23 minutes, not a half day; it is `mid_run_clock()` now, its docstring points at `tests/test_m5_cross_night.py` for the real crossing, and `checkpoint.save_new` lost its `half-day` default label.
3. **The criterion says what is observed.** M4's third acceptance now reads as two evidences: a mid-run cut (《末班车》) and a real night (《夜市》, 18:30 → next 08:00 with the next date on the trace). Same split in `docs/PLAN.md`'s verifying table.
4. **The traces were produced by older code**, so I regenerated the three stories' script traces: `s1` predated the dated glance, `s2` predated the seed's date entering `World.digest()` (every `digest_after` moved for exactly that reason), `s3` predated the roll. Provider traces are untouched — they are evidence and cannot be re-made.

## The decision that remains

One, and it is not the person's: **M4's signature line is yours** — the criterion it asks you to accept now names both evidences, and nothing is blocked on it (`stocktake` and the two same-scale worlds are M5 work). If you would rather sign it only after the night carries acted behaviour rather than 14 idle hours, that is a reason to keep density as M5's first acceptance rather than a reason to hold this milestone.

## Residual risks

- Density is still missing: the night is real and empty, 18:30 → 08:00 with nobody acting. No claim here says otherwise.
- Regenerating `s1`/`s2`/`s3` script traces moves ~40 committed files; the causes are the three named code changes, nothing else, and each story's diff is stamps plus `digest_after`.
- Provider traces (`s2_borrow_note/runs/agent-*`, `s1_last_bus/runs/agent-*`, the spend record) keep the shape they were produced in: their stamps are undated, so an old artifact and a new one do not read alike. That is history, not inconsistency to repair.
- The wide-opening `32:00` branch still exists by design, so `clock_label(1920)` without a date remains wrong-looking; every caller now passes the world's date, and `R11` fails if one stops doing so.
- Nothing pushed; `origin/master` is still `81f4c9d`.
