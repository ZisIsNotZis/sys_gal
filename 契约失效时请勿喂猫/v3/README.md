# 《契约失效时请勿喂猫》v3

v3 is an emergent romance-component story simulation. It is not yet a
galgame and does not project a novel while running.

The run consists of an objective world, a bound System, and independent
character agents. A later authoring stage may turn a selected trajectory into
prose. A later game-design stage may sample trajectories and discover useful
player actions.

## Non-goals

The engine has no romance score, affection score, hate score, plot chapter,
scene label, protagonist privilege, route, scripted resolution, or narrative
quality claim. It does not know whether an event is romantic or funny.

## Causal seam

```text
seed -> mindless world -> private perception -> concrete intention
     -> deterministic validation -> objective event -> time advancement
     -> new perception
```

## World-pack seam

The neutral harness is under `harness/`. Story data is under `world/`.
`manifest.yml` is authoritative machine-readable state, schedules, routes,
acoustic barriers, entities, and document contents. Markdown descriptions live
under the corresponding `locations/`, `items/`, and `documents/` directories.
`harness/world_loader.py` validates references and builds the generic kernel;
the kernel does not contain the city's names or plot facts.

Documents are objective entities. Reading, copying, labeling, and comparing
are timed actions with actor-scoped results. Copies carry a `copied_from`
provenance link, and unavailable descriptions are not resolvable through the
engine.

Agents submit concrete actions such as sending a specified message to a named
person. They do not submit vague intentions such as “apologize” or “increase
affection”. The world records the message, delivery, location, timing, and
other objective consequences. The recipient decides what it means.

## Current status

This version begins with the engine and world-pack contract. No expensive
experiment should start until the harness tests establish privacy, determinism,
coroutine time, and absence of narrative state.

## Run scripts

- `python3 -m harness.dry_run` / `python3 -m harness.mock_run`: deterministic
  full-schedule runs to `world_stops` (no provider).
- `python3 -m harness.agent_view runs/<trajectory>.json --actor lin-yao` (or
  `--all --out runs/views`): render a saved trajectory from one agent's angle —
  the exact session transcript the model saw, delivered world feedback, private
  state, and the agent's own decision log. Use this instead of reading the
  omniscient world log when judging whether behavior is a harness or an
  agent-reasoning problem.

Repetition awareness (frontier-only, no system-prompt edits): when an actor
has sent several messages to the same person without a reply, or repeated the
same meaningful action, the runner appends a short ``situational_notice`` to
the *current* world message (``You have sent X N messages in a row without a
reply...``). This makes the actor's own repetition visible so a real persona
can react (pause, change tactic, drop it); it never forbids anything. The
notice is per-turn frontier text that compaction naturally drops. Counters
reset when a reply arrives or the action succeeds, and they survive
checkpoint/resume (see ``harness/repetition.py``).
- `python3 -m harness.scenario_run --anchors all --hours 6`: several game-hours
  of simulated time, each resumed from a checkpoint snapshot taken just before
  an "interesting boundary" (a scheduled world event that changes objective
  state). A deterministic reactor policy acts on each change (route there, read
  the new document, tell a contact), producing trajectories for manual review.
  See `harness/scenario_run.py` for named anchors and options.
- `python3 -m harness.small_real_run` / `python3 -m harness.real_run`:
  provider-backed probes and full experiments. `real_run` writes
  `runs/<runid>.checkpoint.json` every batch so an interrupted run can be
  resumed instead of redone.
- `python3 -m harness.resume_run runs/<runid>.checkpoint.json [--clock-stop ISO]`:
  fix the related code/file, then continue from the last good checkpoint.
  Session transcripts are preserved (conversation history survives); only the
  code that runs them may have changed. The resumed artifact keeps the whole
  history, contiguous, under a new unique name.

## Fast profile (wall-time tuning)

Provider wall time is dominated by the number of agent turns; idle waits were
about 55% of turns in the last large run. Three independent knobs cut it
(measured deterministically; provider already sends `thinking: none`):

| config | agent turns | est. wall @ ~3.3 s/turn |
|---|---|---|
| full arc (3/27), 1 h idle | 2232 | ~2 h (missed budget, as observed) |
| short arc (3/21 12:00), 1 h idle | 1000 | ~55 min |
| short arc (3/21 12:00), 6 h idle | 169 | ~9 min |
| short arc (3/21 12:00), 12 h idle | 89 | ~5 min |

- `OPENAI_MODEL=luna...` picks a faster model; `OPENAI_MAX_CONCURRENCY=8`
  runs more agents in parallel.
- `V3_CLOCK_STOP=2026-03-21T12:00:00+08:00` ends the arc after the evidence
  and review-meeting climax instead of the full fair arc. The runner inserts a
  `world_stops` marker at the shortened end so the completion gate still holds.
- `V3_IDLE_WAIT_SECONDS=21600` (or the manifest `engine.idle_wait_seconds`)
  makes idle agents wait 6 h instead of 1 h per turn. Trade-off: an agent
  inside a long wait reacts to messages/boundaries only when that wait ends.
  Use a short arc (≤3/21) so the story beats still land with bounded latency.

A reasonable, complete short arc is therefore: `V3_CLOCK_STOP=2026-03-21T12:00`
`V3_IDLE_WAIT_SECONDS=21600` plus a fast model, which should finish well inside
a two-hour budget with every scheduled climax event firing.
