# Active work — 契约失效时请勿喂猫 (v4 harness)

Last updated: 2026-10-01 03:30 +0800

## Where we are (2026-10-01 20:2x)

### The fixed harness completed a full d1-am (two segments, resume exercised)

`runs/resumed-20261001T185442+0800-848182-951549918.json` — reached `stop_at_reached` at 12:59.
The run hit the 2h wall deadline at sim 11:22 (`runs/real-20261001T163024+0800-629102-384711601.json`),
then `harness.resume_run` continued it from the checkpoint to the endpoint — the resume path works.
Anchor check: **all three d1-am anchors PASS**. Checkpoint copied to `checkpoints/d1-am.json`.

### Before → after (all three are full 07:00–12:59 mornings)

| metric | baseline (09-30) | +lanes 38–55 | +lanes 56–66 (this) |
|---|---|---|---|
| error turns | 72/317 = 23% | 41/390 = 10.5% | 97/746 = 13% |
| `inner` fill | 0/317 | 388/390 | 716/746 (96%) |
| private reasoning broadcast | 77 (suspected) | 4 | **1** |
| content kept private (new) | — | — | 660 (26 flagged possibly-dialogue) |
| dialogue from `speak/text` | — | 96 | healthy per 11 reviewers |
| 签到本/晚归本 read failures | 24+ | 0 | 0 |
| read-claims w/o document_read | 4 | 1 | 2 |
| unregistered prop claims | 48 | 20 | 13 |
| NPC longest dormancy | 3h50m | 0h45m | 3h43m (下棋大爷, one actor) |
| stagnation notices | 0 | 3 | 9 |

### 11-reviewer verdict on the latest morning

Verdicts: 林瑶/陈默/宿管阿姨/班长/唐小岚/下棋大爷 = **健康**（私密推理不再被广播、对白未被压塌）。
Remaining reports are **provider-driven or world-modelling P2s**, not semantic regressions:
- provider 429s / retry-deadline at the end (esp. 辅导员, the decision-maker) truncated the climax;
- "手机" is a narrative object but not holdable, so `give 手机` fails while `text` works → the model
  narrates around it (手机失踪 became a plot thread);
- 305备用钥匙/查寝表 etc. promised in room prose without being modelled (ticket 60 class, new cases);
- 陈默妈 fabricated "大巴不通" and later denied her own message (memory self-consistency, model-side).
- **False P1 corrected**: reviewers read `private_state.memories == []` as "writes dropped"; the KB in the
  checkpoint has all 38 of 唐小岚's rows. Filed as ticket 68 (trace field misleads reviewers).

### Tickets filed this session: 38–68 (31 total). Fixed: 38–66 (29). Open: 67 (wall deadline starved by
the in-flight wait loop), 68 (trace `private_state` misleading). Both are small.

### Next steps
1. Fix 67 + 68, then decide on the remaining P2s (provider flakiness is environmental; 手机/钥匙 modelling is seed work).
2. Continue the day: `d1-pm` from `checkpoints/d1-am.json`, then chain through day 1 and beyond
   (`scripts/half_day_flow.sh` does half-day segments with the anchor gate between them).
3. Hand the day to the user for manual inspection.

### Traps (unchanged and new)
- Story model route: `zai/glm-5.3-flash`; workers `deepseek/deepseek-flash`; reviewers `deepseek/deepseek-v4-pro`.
  `volcengine/*` hits a 5-hour quota; the proxy gets restarted externally.
- Two-hour wall deadline is currently **exceeded** in practice (ticket 67) because the in-flight wait loop
  starves the outer check — so budget for ~3h wall per morning, or resume as we did.
- v3 and v4 suites need `OPENAI_MODEL` set. Probe with `/tmp/probe.py <stem>` (exclude `*.checkpoint.json`).
- When briefing a reviewer/worker, verify the artifact evidence yourself first: one of my briefs mis-attributed
  four leaks to the `speak` channel when `world_events` showed no `to` field on those speech events.
