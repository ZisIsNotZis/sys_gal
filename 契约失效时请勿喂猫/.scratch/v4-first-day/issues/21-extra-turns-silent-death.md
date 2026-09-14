# 21 — extras: silent death, chatter loop, silent strangers (live-run E1/E2/E3)

Status: done

## Issue
The litellm live run (2026-09-15) proved the full MC arc works, but **every
`stranger_asked` spawned an extra that never spoke and was never recorded** —
zero extra turns across all three recent runs (t18/t19 smokes + t21 live),
despite 4–8 asks per run. Follow-up asks to an existing extra also went
nowhere, and one answer that did land was raw decision JSON spoken verbatim.

## Root causes (all found by deterministic stub-provider repro)
- E1 silent death: engine `_extra_turn` passed a *plain dict* to
  `Trace.record_agent`, which reads `intention.actor/.kind/.args` →
  AttributeError AFTER the speech was submitted but BEFORE the record;
  `_extra_loop` caught only CancelledError so the task died silently and
  `gather(return_exceptions=True)` swallowed the exception. No record, no
  conversation continuation.
- E3 silent strangers: extras answer in prose (no tool call); the old
  `extra_tool_calls` dropped content-only replies — T1 文本即说话 must apply
  to extras too. Also, models sometimes return an *inline decision JSON*
  instead of a tool call; that JSON was being spoken verbatim.
- E2 chatter loop: the extra's own speech is visible to itself; without
  draining its perception cursor, `has_wakeup()` stayed True and the extra
  answered every scheduler pass (repro: 7 turns of the same line).
- Continuation: follow-up `ask`s fire `stranger_asked`, which is not a wake
  kind and was `continue`d when a partner existed — the extra never saw the
  new question and despawned idle.

## Fix
- kernel: `World.dismiss_events(actor)` (advance cursor) +
  `World.has_external_wakeup(actor)` — wake-class event from someone else
  (mirrors `_unseen_social_event`, WAKE_EVENT_KINDS, actor != self).
- engine: `_extra_turn` records a real `Intention`; `_extra_loop` reads
  `pending_question` from the info dict each iteration, drains the cursor
  after every turn, parks on `has_external_wakeup OR pending_question`;
  `_handle_extras` routes follow-up asks to the existing partner extra
  (pending question + wake, one conversation per MC holds); `_notify_ready`
  treats a parked pending_question as ready for extras.
- npc_agent: `extra_tool_calls` parses inline decision JSON (code fences
  handled) into the intended call; plain content becomes a `speak` with no
  volume (kernel T1 path → normal broadcast speech).

## Gates
- test_historical_failures: E1/E2/E3 ledger entries +
  test_extra_turns_are_recorded_and_conversational (initial tool-call speak,
  follow-up ask routed to the SAME extra, inline-JSON reply parsed to clean
  text, exactly 2 provider calls — no chatter, no task crash).
- 306 passed / 1 skipped; seed_lint OK.

## Live proof (litellm, 2026-09-15 06:23 run)
- 4 extra turns, all recorded + submitted, 0 marker leaks.
- 何大叔 answered 林瑶's initial ask AND 3 follow-ups, each in honest
  in-character prose ("这个我真不清楚…直接问值班老师比较靠谱") — no JSON
  leakage, no chatter, no despawn before the conversation ended.
