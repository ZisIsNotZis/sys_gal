# v2 Manual Trajectory Audit — 2026-08-25

Scope: manual inspection of `real-2026-08-24-17.json` through
`real-2026-08-24-20.json`, with emphasis on run 20, plus the current v2
kernel, runner, persistent-session code, seed, character prompts, and existing
run logs. This is an audit only. No production files were changed in this
pass. Counts below are supporting evidence, not a substitute for reading the
turns.

## Executive finding

None of runs 17–20 is a valid complete story run. All four stopped with
`agent_failure`; none reached the seeded `world_stops` endpoint on
2026-03-27 21:30. Run 20 is the clearest diagnosis: the characters sometimes
maintain a truthful and surprisingly careful shared investigation, but the
world cannot express several actions they repeatedly discuss, and the agents
continue planning around unavailable objects and locations. The provider 502
at 2026-03-16 10:46:51 then terminates the run before the first day's major
deadlines.

The current code contains meaningful fixes for feedback rendering, wake-up
filtering, GM-record capture, and provider retry handling, but those fixes are
unverified by a post-fix full run. The existing traces therefore demonstrate
neither endpoint completion nor a stable long-run session protocol.

## Run-level status

| Run | Last simulated time | Events | Agent turns | Result | Audit meaning |
|---|---:|---:|---:|---|---|
| 17 | 2026-03-16 19:59:30 | 696 | 257 | `agent_failure` | Rich early investigation, then provider failure; no endpoint |
| 18 | 2026-03-16 08:00:05 | 64 | 28 | `agent_failure` | Very early provider failure |
| 19 | 2026-03-17 01:18:44 | 885 | 355 | `agent_failure` | Longest observed run, but still first day/night only |
| 20 | 2026-03-16 10:46:51 | 428 | 171 | `agent_failure` | Current target failure: HTTP 502 escaped the run |

Run 20 has 164 submitted turns, 4 rejected turns, 2 `none` turns, and 1
`agent_error`. Its last turn is Chen's provider error; its outcome is
`agent_failure`, not a world endpoint. The trace has eight character sessions
but no cat session, matching the current v2 seed rather than the older v1
ensemble.

## Run 20: context continuity and session quality

### What worked

The persistent conversations do preserve local context. For example:

- At 07:00 Gao asks Qiao to review mislabeled audit material. At 07:12 he
  continues the same audit thread in person and later asks for a source and
  draft comparison.
- At 07:15 Chen tells Lin he can talk, then at 08:38 distinguishes his own
  uncertain storm memories from Lin's account. At 08:53 he explicitly refuses
  to merge the memories into a false shared fact.
- At 10:15 He Qian tells Chen she will mark the pipe, whistle, and elder only
  as unverified memory and will not turn them into a certain quotation. At
  10:46 Chen acknowledges that policy and asks to review future source material
  first.

These are genuine context-sensitive developments, not random greetings. They
also show a useful v2 property: agents can preserve uncertainty instead of
being pushed toward a convenient revelation.

The session snapshots, however, show a serious long-run weakness. Most agents'
private `beliefs`, `memories`, and `interpretations` remain empty despite many
hours of consequential conversation; only Gao and Lin have one compacted
memory in run 20. The actual continuity is therefore mostly buried in raw chat
history, not structured private state. This makes later recall, compaction, and
post-run novel reconstruction fragile.

The sessions also receive generic world-result messages such as “Your wait
completed successfully” and “The world records no immediate physical change.”
These are truthful at the primitive level, but they do not tell the person
whether a searched object was found, whether another character received a
request, or whether a planned handoff is now possible. That gap encourages
repetition even when the session itself is continuous.

## Objective feedback: false, generic, or insufficient

The current feedback formatter in `runner.py` correctly distinguishes accepted
actions, rejected actions, in-progress actions, and completed actions. This is
a real improvement over the older failure behavior and should prevent the
session from hallucinating successful movement after a rejection.

It is not yet sufficient for the observed trajectory:

- A successful `search` or `inspect` is reported through generic event text;
  the character is not given a stable, object-level result explaining what was
  found, not found, or inspected.
- Agents repeatedly say they will “search the union office,” “check shared
  drive access notes,” or “locate the drafts,” but the legal `search` primitive
  has no target, search domain, or discoverable result in the current world
  interface. At run 20, Qiao says at 13:04 that he will search the union office;
  Chen then moves among dorm, archive, and union while the source and drafts
  remain absent. The world has not represented a search failure or a physical
  document location.
- A message completion says only that the message was sent successfully. The
  recipient's later response is the only useful semantic feedback, so agents
  often send near-duplicate reminders before the first response can arrive.
- The prompt says “choose the longest offered wait” when no matter requires
  attention, but the world does not provide a structured “waiting for reply” or
  “next relevant event” status. Long waits and frequent polling therefore
  coexist unpredictably.

Current fix status: `Runner._result_message` and the session's
`record_world_result` path are present in the checkout. The runner now also
records bounded GM requests, and the kernel emits objective
`item_inspected`/`location_searched` events. The provider now retries transient
5xx responses with a bounded retry count/backoff and optional duration cap.
None of these changes has been validated by a new full real run.

## Missing physical actions and impossible plans

This is the largest semantic failure in run 20.

The agents reason as if documents can be opened, compared, handed over,
copied, labeled, preserved, and placed beside one another. The objective world
only owns inventory and the actions `take`, `drop`, `inspect`, and `search`.
There is no document-content state, no transfer action, no copy action, no
label/version action, and no targeted search result.

Concrete examples:

- 07:23 Amani takes `original-export`, which is a valid physical action. At
  07:27 she says she is keeping it safe and asks where it should go.
- 08:24–09:39 Amani repeatedly promises to bring the export to the archive or
  keep it for Lin, but there is no handoff or custody primitive. The export is
  only in Amani's inventory.
- 09:43 Gao says he is bringing up both drafts and supporting documents, even
  though neither draft exists as an item in the seed and no “open document” or
  “compare records” action exists.
- 11:58 Chen drops the old permit form, and at 12:29 Gao takes it. That real
  inventory transition is expressible. But the surrounding plan—putting the
  source and two drafts beside it, recording labels, and preserving copies—is
  not.
- 13:04 Qiao asks Chen to search filing cabinets and shared-drive access notes;
  13:15 Chen reports that the exact location is unknown, then travels to the
  archive. No search result changes the objective state.

The resulting behavior is not merely verbose. It is a mismatch between private
intent and public affordances: agents form reasonable intentions that the
engine cannot execute, then substitute movement, speech, and repeated queries.
The current checkout has partially addressed this: `inspect` now creates an
objective item-inspection event and `search` creates a location-search event
listing physically present items. That is a real fix to the former “generic
completion only” problem, but it does not solve the document scenario: drafts
and shared-drive records are still not objective items, `search` has no target
or domain, and there is still no transfer/copy/label/version operation. The
old run-20 claims about the pre-fix trace remain valid, while the new behavior
is explicitly unverified until a run exercises these primitives.

## Retry loops and rejection loops

Run 20 contains four rejections:

- Gao, 09:27:53: `move archive` rejected as `invalid route`.
- Xu, 10:00:24: `move archive` rejected because the destination is closed.
- Gao, 10:06:37: `move archive` rejected because the destination is closed.
- Gao, 10:39:42: the same archive move rejected again because it remains closed.

Gao's 10:39:42 attempt is the clearest retry loop. The feedback is truthful,
but the session still proposes the same illegal destination later. The
character has not learned a durable operational fact such as “archive is
closed; wait for an opening event or use the available route.” This is a
session-memory/action-selection failure, not a privacy failure.

There is also a softer semantic loop: Qiao repeatedly asks for the first
source page or paragraph from 07:45 through 10:15, despite no action having
made that page discoverable. Chen, Gao, and Qiao repeatedly discuss finding the
same missing source and two drafts from 12:48 onward in run 17. The world has
not supplied a stopping condition or an actionable next step.

Runs 17 and 19 show the same pattern at larger scale: many ordinary moves and
conversation turns continue, but the runs eventually fail rather than reach a
deadline, resolution, or endpoint. This makes “more turns” a poor substitute
for progress.

## Privacy and information leaks

No clear private-message leak was found in the manually inspected run-20
turns. Private message delivery is recipient-scoped in the event log, and the
roommate does not receive the message body merely because the sender is in the
dorm. Public speech and co-location behavior look consistent with the current
sound model.

The important remaining risk is not a demonstrated secret leak but misleading
objective visibility:

- `render_world_message` describes visible events but often exposes only
  generic action completion, not the full objective consequence.
- Agents can infer that another actor is working on a document from public
  speech even when they cannot access the document itself; this is acceptable
  only when the speech actually occurred and was audible.
- The agent's private session is correctly separate from other sessions in the
  trace. Run 20 has no evidence that one session received another session's
  prompt, private state, or hidden seed.

The audit therefore marks privacy as provisionally good for the inspected
surface, while marking truthfulness of feedback as incomplete.

## System use

The Ledger is exposed as a System affordance (`system_accept`) in run 20, but
`system_turns` is empty and no System action occurs before the failure. Chen's
perception repeatedly includes the option, yet he spends the observed period
on the storm-memory and paperwork conversations. This is not proof of a bug:
the character may rationally decline or postpone accepting an obligation.
It does show that the current demo has not tested the System contract under a
real persistent session, nor shown a meaningful System consequence.

The current v2 seed correctly keeps System state out of the objective World;
the System adapter is the appropriate boundary. Any future test should verify
that accepting/querying the System produces only its declared external event,
does not reveal hidden world facts, and does not become a plot controller.

## Romance emergence

Run 20 contains the beginning of a plausible interpersonal thread, but no
romance route or romance score is present—and that is correct for the v2
contract. Chen and Lin voluntarily meet, discuss a painful childhood memory,
correct each other's uncertainty, and agree to stop rather than fabricate an
answer (08:23–09:31). He Qian and Chen establish a respectful boundary about
quoting unverified memories (10:15–10:46). These are potentially attractive
relationship developments because they arise from trust, restraint, and
attention rather than an imposed affection variable.

There is no observed confession, date, consent-to-intimacy step, or explicit
romantic action. The agents do not appear to be optimizing for romance. This
is a positive result for the plot-blind requirement, but it is not a completed
romance arc and must not be reported as one.

## Endpoint and terminal story state

All inspected runs fail before `world_stops`. Run 20 stops at 10:46:51 on the
first day; run 17 reaches 19:59:30 on the first day; run 19 reaches only
01:18:44 on March 17; run 18 stops at 08:00:05. None reaches the seeded
permit review, bank call, storm-record availability, review meeting, rain
warning, fair opening/closing, or `world_stops` events.

Consequently:

- no objective terminal state exists in these traces;
- no participant can be considered satisfied, defeated, dead, departed, or
  otherwise resolved by the world;
- no complete story ending can be reconstructed;
- the run-20 trace is useful as an early-act behavioral sample, not as a story
  demo.

## Current fixes versus verified behavior

### Present in checkout, not verified by a post-fix full run

- transient 5xx/connection retry, capped backoff, and optional provider retry
  duration in `provider.py`;
- truthful accepted/rejected/in-progress/completed feedback in `runner.py`;
- idle-agent wake filtering through `World.has_wakeup`;
- explicit bounded GM trajectory records, including rejected GM output;
- persistent `CharacterSession` with bounded compaction;
- session snapshots saved into the trace;
- objective action validation for closed destinations, routes, inventory, and
  targeted inspection, plus objective `inspect`/`search` result events;
- separate private state and recipient-scoped event visibility.

### Verified by these old traces

- event logs are replayable through the observed prefix;
- private messages are recipient-scoped in the inspected records;
- agents can maintain local natural-language context over dozens of turns;
- physical movement, taking/dropping an item, speech, and messaging can produce
  real objective events;
- agents can preserve uncertainty and refuse to turn memory into fact;
- invalid moves are rejected instead of silently changing location.

### Not verified

- provider retries surviving a 502 and allowing the same run to continue;
- the configured real-run retry budget fitting inside the runner's 15-second
  batch deadline under worst-case timeouts/backoff;
- reaching 2026-03-27 21:30;
- all seeded scheduled events being observed and acted upon;
- stable behavior after session compaction;
- any System acceptance/query and bounded consequence;
- an objective way to search, compare, transfer, label, or inspect the missing
  audit documents;
- a complete terminal story or any final satisfaction/departure/death state.

## Newly discovered current-checkout blocker

The retry implementation is bounded, but its real-run configuration still needs
an end-to-end timing check. `real_run.py` gives each provider call a two-second
socket timeout, permits six attempts, and uses exponential backoff capped at
two seconds, while the runner's entire decision batch deadline is 15 seconds.
In a worst-case transient outage, the provider's possible socket time plus
backoff can exceed that batch deadline. The runner can therefore record a
`decision_timeout` while provider worker threads are still unwinding, or fail
for a provider error depending on exact timing. Unit tests prove the arithmetic
and error metadata, but no real trace proves that recovery works under the
runner deadline.

The newer runner also has an important semantic distinction: an agent returning
`None` is put into a waiting set and is woken only by visible events, inbox
delivery, or its own completion. This should reduce polling, but it changes the
conditions under which an agent gets another turn. A full run must verify that
targeted scheduled events and delayed message deliveries wake the right session
without starving an idle actor or skipping a same-time event.

Finally, the checkout now supports `system_decline` and records GM attempts,
but run 20 contains no System turn and no GM turn. These are implementation
capabilities, not observed story behavior.

## Second-pass test audit: most former seams pass; compaction remains red

The current public-interface test suite was run from `v2` with:

    python -m unittest discover -s harness/tests -v

The latest checkout run completed 87 tests and ended with 2 failures. This is
newly verified checkout evidence, not a historical-trace observation. The
three previously red seams for item transfer, rejection wake-up, and objective
event prose now pass. The remaining failures are both in session compaction,
so the long-run continuity safeguard is still not covered by passing tests.

The concrete remaining failures are:

- `test_compaction_keeps_authoritative_feedback_in_order_without_duplicate_turns`
  now reaches compaction, but the rebuilt session contains each authoritative
  result twice. The current implementation preserves a consolidated feedback
  block while older world-feedback messages can still survive in the retained
  tail. This is a concrete duplicate-history defect, not merely an untested
  concern.
- `test_compaction_keeps_initialization_and_recent_turns` still exceeds its
  bounded-message assertion (1596 characters versus the required 1500). The
  compaction threshold prevents unbounded growth in the tested scenario, but
  the resulting context is not within the intended size budget.

Passing tests now cover item transfer and replay, private rejection feedback
and its wake-up behavior, objective inspect/search events, natural-language
rendering for inspection and transfer, provider retry arithmetic and transient
HTTP/socket classification, bounded backoff, private visibility, GM audit
records, and several isolated wake-up cases. These are unit/interface results;
they do not prove a realistic multi-day run. “Covered by a test” must still be
distinguished from “verified end-to-end.”

## Priority conclusions for the next experiment

1. Treat a provider error as a resumable infrastructure condition and verify
   the retry path in a real run; do not call the resulting trace complete if a
   provider error remains.
2. Assign and fix the remaining red compaction seam first: remove duplicate
   authoritative feedback from the rebuilt transcript and meet the tested
   context-size bound. Re-run the full local suite until it is green.
3. Close the action-language gap before another expensive run: seed every
   object the agents are expected to handle, and define exact objective
   results for `search`, `inspect`, and any document custody operation needed
   by the characters.
4. Persist operational facts in the session or expose them in the next
   perception so a rejected move cannot recur unchanged.
5. Add a run-level progress/endpoint check that distinguishes “many events”
   from reaching `world_stops` and observing the late scheduled arcs.
6. Preserve the plot-blind boundary. The strongest material in run 20—the
   careful childhood-memory disagreement and He Qian's quotation boundary—was
   generated by character goals and available evidence, not by a romance or
   plot controller.

## Bottom line

The current v2 traces show a promising cast: the characters can be cautious,
truth-seeking, socially distinct, and locally consistent. They do not show a
working full simulator or a complete story. The dominant blocker remains the
seam between what a persistent character naturally intends and what the
objective world can physically represent. The current checkout has cleared the
`give`, rejection-wake, and objective-event-rendering regressions in its local
tests, but still has a concrete lossy/duplicating compaction defect and a
context-size-bound failure. Provider recovery and the full long-run endpoint
remain unverified. Until the local suite is green and a run reaches
`world_stops`, v2 should remain explicitly incomplete.
