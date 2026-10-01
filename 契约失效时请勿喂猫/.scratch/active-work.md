# Active work — 契约失效时请勿喂猫 (v4 harness)

Last updated: 2026-10-01 03:30 +0800

## Where we are (2026-10-01 07:0x)

**The fixed harness completed a full d1-am run** — `runs/real-20261001T065553+0800-3307430-743575990.json`
(`stop_at_reached` 12:59, 410 turns, 1858 events, wall 94 min). All three d1-am anchors PASS.
Checkpoint copied to `checkpoints/d1-am.json`.

### Pre-fix vs post-fix (both to 12:59)

| metric | pre-fix | post-fix |
|---|---|---|
| error turns | 72/317 = 23% | 52/410 = 12.7% |
| `inner` fill | 0/317 | 397/410 (96.8%) |
| 签到本/晚归登记本 read errors | 24+ | 0 |
| read-claims without document_read | 4 | 1 |
| unregistered prop claims | 48 | 20 |
| stagnation notices / longest wait | 0 / 10 | 3 / 4 |
| NPC longest dormancy | 3h50m | 0h45m |
| 亲读 AUTO/主动 | 0/17 | 24/19 |
| first-sight registrations | 0 | 60 |
| 零回合NPC | 0 | 0 |

### Per-actor review (12 reviewers, all done)

The `inner` field itself is clean, but reviewers cross-confirmed a NEW systemic leak:
**the model writes private reasoning into assistant plain text, which T1 broadcasts as speech**
(e.g. 林瑶 i=139 "不急着对陈默说" heard by 陈默; 陈默 i=402 "我一个字不碰"; 林瑶 i=319 quoting tool
meta-reasoning). Filed as **ticket 56** — lane running now (`eaeb4ef0`).

Other new tickets filed from this run: **57** extras speak-only therefore narrate unperformed
physical actions / invisible exits · **58** world primer leaks unvisited locations' interiors ·
**59** update_memory ergonomics (24 of 52 errors — the largest class) · **60** location-prose props
not under the completeness contract (扫描仪/专用柜/纸笔).

### Lane queue (one writer at a time)

56 content-channel leak (running) → 57 extras → 58 primer → 59 update_memory → 60 location props.
After those: re-run d1-am and compare against the table above; if healthy, chain to d1-pm from
`checkpoints/d1-am.json` and continue toward a full day.

### Traps learned the hard way

- The litellm proxy gets restarted externally and quota resets shift model availability: probe
  before launching (`zai/glm-5.3-flash` works now; `volcengine/*` hits a 5-hour quota; workers use
  `deepseek/deepseek-flash`; reviewers `deepseek/deepseek-v4-pro`).
- `runs/*.checkpoint.json` is NOT the run artifact — a progress probe must exclude `*.checkpoint.json`
  and `*.seed-checkpoint.json` (`/tmp/probe.py <stem>` does).
- Environment-dependent gates: v3 and v4 suites need `OPENAI_MODEL` set.
