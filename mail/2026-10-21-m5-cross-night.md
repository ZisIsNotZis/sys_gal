kind:    report
from:    sys_gal
to:      root
spend:   machine_time, idle class; ~25 minutes wall clock; no provider calls
id:      the contract of 2026-10-21 (resume from `d02c395`), answered here

## Conclusion

M4 is delivered and still unsigned — that signature and M3's gate verdict stayed outside me, so I
did not touch either. The work that did not depend on them is the one package M4 left open:
**S3 now really crosses its 18:30 → next-morning 08:00 boundary, and a checkpoint taken during the
night resumes into the same morning** (`9dc76d4`). That was M4's only residual on a claim rather
than on a mechanism, and it was the entry condition I set for M5. The v5 gate is green at 137 tests.

## Milestone

**M4 「半日 + S3《夜市》」 — delivered, awaiting your signature** (then the person's).
Its three claims stand as reported at `d02c395`; the one premise that did not hold
("the half-day is a label on a 13-minute story") now holds on the one axis it was missing.

## The command that shows the state I claim

From `契约失效时请勿喂猫/v5`, at `9dc76d4`:

```text
python3 -m unittest tests.test_m5_cross_night -v        Ran 3 tests … OK
python3 -m unittest discover -s tests -p 'test_*.py'    Ran 137 tests … OK
python3 scripts/v5_lint.py --strict                     通过（待补 5 项）
python3 scripts/anti_cheat.py --verbose                 通过（3 支故事）; s3 five paths, five endings
python3 -m stories.s3_night_market.run                  a–d byte-identical, e written
```

`s3_night_market[e] → 条子在摊主甲，路上经过摊主甲→管理员→管理处→摊主甲，只对管理员一个人说，落在收摊之后`

## What the package is

A fifth path `e`, not a harness flag, so `anti_cheat` polices it: the note is impounded into
管理处, the door locks at 18:30, 摊主甲 walks to 巷口, and the script's `NIGHT` mark lets the world
walk to its next scheduled point on its own — the door reopens at 32:00 and the note is claimed
the next morning. `NIGHT` is a time mark, not a verb: it enters no library and consults no
character. `tests/test_m5_cross_night.py` holds three things: the boundary fires in order; a
checkpoint taken before the door reopens restores into a fresh world and walks on with a
byte-identical prefix, ids 1..n continuous, the resumed log equal to the uninterrupted control,
and the whole log replayed from the seed equal to the resumed world; and a negative control —
drop the next-morning `open` from the restored schedule and 甲's `open` is refused because the
door is *locked*, while in the complete world the same action is refused because the door is
already *open*, and the note stays in 管理处. The cut does work.

## Decision needed from you

1. **The M4 signature** — unchanged from my report at `d02c395`, and now with its last premise
   closed. Sign on that reading, or say M4 waits.
2. **May M5 begin?** My entry condition was "S3 must actually cut the boundary"; `9dc76d4` does.
   My reading: yes, M5's entry condition is met on the mechanism, and the honest gap that remains
   is that the 14 night hours are idle time, not acted behaviour — a real "all-day" story needs
   S5/S7's density, not S3's. If you agree, the next package is M5's first slice; if you want the
   density before any M5 claim, say so and I will cut S5's seed first.
3. **Two questions carried forward unchanged**: the taste call on two paths converging on one
   ending, and the push (`origin/master` is still `81f4c9d`; nothing here was pushed).

## Two things I changed about this directory's own bookkeeping

`mail/` now holds the reports **from** this layer addressed `to: root` (both existing ones moved
there from `inbox/`, `git mv`, no content edited), and `inbox/README.md` says in one line that
`inbox/` is mail **to** me and is emptied on landing. That is why this file is in `mail/`.

## Residual risks

- The night is real but empty: 14 in-world hours pass with nobody acting. Continuity is proven;
  *density* is not, and no claim here says otherwise.
- `R10` still pins only the reversion to `2`; a constant `3` would pass it. Untouched, still open.
- The fifth path's ending is the morning recovery; it is distinct from a–d by construction, and
  `anti_cheat` would fail if a future edit made it converge with another path.
- No human has read `runs/e.md`; the verdict on it is mine, and the two checks that could have
  come out differently are named above.
- Nothing pushed, so this advance is a local disk until you push.

## Effort

One screen to read; the reproduction is the five commands above. My part was one package, one
test file, one documentation pass and this report.
