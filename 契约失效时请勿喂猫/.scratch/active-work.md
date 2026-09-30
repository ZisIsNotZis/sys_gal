# Active work — 契约失效时请勿喂猫 (v4 harness)

Last updated: 2026-09-30 15:58 +0800

## In flight

Nothing running. D1-AM completed 2026-09-30 17:12.

**D1-AM result** — artifact `v4/runs/real-20260930T160727+0800-522904-846830380.json`
(+ `.checkpoint.json`), model `zai-coding/glm-5.3-flash`, 317 turns / 1362 world events,
stopped exactly at 2026-03-16T12:59:00+08:00 (`stop_at_reached`).
Gates: all three d1-am anchors PASS; provider HTTP errors 0; marker leaks 0;
BUT 72/317 turns were error turns (23%) — see issues 38–48.
Per-actor review done: 12 fresh-context reviewers, each verified against its exact turn count.

To continue: run the `d1-pm` segment from `checkpoints/d1-am.json` **only after** the P0s
(38 inner channel, 39 unreadable items) are fixed — the morning's defects shaped the story.

- process: `python3 -m harness.real_run`, background, log `v4/runs/seg-d1-am.log` (block-buffered: an empty log early on is normal; check the artifact dir instead).
- stop condition: `V3_CLOCK_STOP=2026-03-16T12:59:00+08:00` — reached.
- env used (also in `/tmp/d1am-env.sh`):
  `OPENAI_BASE_URL=http://127.0.0.1:4000/v1`, `OPENAI_MODEL=zai-coding/glm-5.3-flash`,
  `V3_PROVIDER_API=chat`, `OPENAI_API_KEY=$LITELLM_API_KEY` (proxy master key),
  `V3_PROVIDER_CONCURRENCY=8`, `V4_STALL_BUDGET_RATIO=0.60`, no `V3_RESUME_CHECKPOINT`.

## New issues filed (2026-09-30, from this run)

`v4-first-day/issues/38…48-*.md` — all systemic, each with a failing-first test requirement:

- **38** `inner` private-thought channel unreachable (0/1356 turns across 3 runs) → all
  deliberation is spoken aloud and heard by co-located actors. P0 information boundary.
- **39** `world/items/*.md` bodies are not readable at runtime; error lies ("不在你手边" while
  the item is in inventory) and suggests calls that cannot succeed. 24/72 error turns. P0.
- **40** `known_to` doubles as a remote read grant (harness suggested an off-site read).
- **41** 25/81 scheduled notices have no audience → scene-local dialogue broadcast world-wide.
- **42** extra path: raw JSON + `inner` delivered as speech; extras fabricate props and narrate
  unperformed actions; extras don't know their own name; idle-removal erases a delegated duty.
- **43** anti-repetition monitor is a **no-op on the chain path** (`engine.py:1067` passes `None`)
  and excludes `wait` → 9 identical failed reads / 18 waits drew zero nudges.
- **44** `leave_note` silently ineffectual when the recipient is co-located (林瑶's 借条 never read).
- **45** NPC wake ignores pending questions and `reminder_due` (宿管阿姨 3h12m, 陈默妈 2h13m silent).
- **46** perception snapshot vs submit-time validation mismatch; one bad recipient voids the whole
  utterance.
- **47** seed: mystery answer pre-injected in a character's knowledge; inhibition rows unreachable
  by story vocabulary; signature props never modelled.
- **48** unperformed actions / unread content asserted as verified fact, then propagated into other
  actors' memories.

## Repo state

- repo: `v4` (harness), branch **`fix/v4-world-contracts`**, HEAD `013297f`.
  `master` is at `87a7157`; the branch is **not merged** (merge once the D1 segment validates).
- uncommitted: `v4/scripts/half_day_flow.sh` (model switch, see below);
  untracked `契约失效时请勿喂猫/.scratch/v4-first-day/review-claims-a.diff`.
- gates run green at this revision on 2026-09-30 15:52: v4 unittest suite **377 OK** (1 skip),
  `scripts/seed_lint.py` OK. v3 suite 218 not re-run this session.

## Decisions in force

- Story model: user ruled 2026-09-30 "always use the zai/ model, via the endpoint
  litellm provides", corrected to **`zai-coding/glm-5.3-flash`**. Route disambiguation:
  `zai-coding/glm-5.3-flash` works (verified with native tool calls); `zai/glm-5.3-flash`
  and every other `zai/glm-5*` group are **429 余额不足**; `volcengine/*` is **not** the
  sanctioned route. Copilot `gpt-6-luna` (Responses transport) is monthly-quota
  exhausted; switch back when it resets.
- The machine proxy on `127.0.0.1:4000` rejects `sk-noauth` (400); the master key is required.
- copy the finished artifact to `checkpoints/d1-am.json` before resuming (`segment()` in
  `scripts/half_day_flow.sh` does this); per-actor review used
  `/tmp/d1am-review/<actor>.json` extracts + 12 `reviewer` subagents.

## Known blockers

- `zai` (non-coding) account balance (user-only action) if that route is ever wanted.
- Copilot monthly quota (resets on its own schedule).

## Open follow-ups

- Issues ledger: `v4-first-day/issues/27…37-*.md` (last filed: 37 world-contract review).
- P2s noted but not yet done: single compaction regression test; 值班簿-style sweeps
  are now lint-gated, so no further per-sample patches.
- Merge `fix/v4-world-contracts` → `master` after the D1 segment passes its checks.
