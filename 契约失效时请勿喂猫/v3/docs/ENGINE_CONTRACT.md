# v3 Engine Contract

The engine exposes a small neutral interface:

```text
observe(actor) -> private perception packet
affordances(actor) -> legal concrete action shapes
submit(intention) -> accepted/rejected
advance() -> next objective events
replay(world pack, event log) -> objective state
```

The kernel must not contain `story_phase`, `chapter`, `scene`, `route`,
`romance`, `affection`, `hate`, `relationship_score`, `actor_resolution`, or
any validator that declares a trajectory narratively meaningful.

Character private memory, beliefs, goals, and affect are agent-owned. The
kernel can expose only observable events and objective body/world state.

Every accepted action has a typed intention, actor, preconditions, duration,
and event chain. Every rejected action has no state effect. Concurrent agent
decisions use a deterministic snapshot/tie-break rule. Time advances through
scheduled world events and action completions; agent reasoning consumes zero
simulated time.

The System must use the same observable intention/event seam as any other
world participant, with only its explicit supernatural permissions added.

World-pack loading is a separate adapter seam. The kernel accepts typed
objective definitions and knows no story identifier. The loader rejects
unknown references before a run starts. Markdown is never injected globally;
an actor receives its description only through a legal observation or a
world-defined private result.

The document actions are generic: `read(document)`, `copy(document)`,
`label(document, label)`, and `compare(first, second)`. They validate physical
availability, consume seeded time, and emit actor-private results. A copy
consumes a seeded copy material and creates an objective provenance link.

Ordinary physical actions use the generic `interact(target, verb, parameters)`
request. The loader derives target capabilities from objective world data;
the kernel resolves targets against the actor's reachable perception and
validates capability and parameters. Closed boundaries may derive `knock`
without a separate scenery entity. Public and actor-private objective
knowledge are likewise scoped in the world packet; private knowledge is never
included for another observer.

## Map and acoustic boundary

Locations have objective map coordinates, openness, and a speech radius.
Speech is not automatically heard by everyone in a location or everyone in
the world. For each listener, the kernel compares map distance plus seeded
wall/barrier loss and the source/listener acoustic loss against the speaker's
radius. A closed source location blocks ordinary speech from leaving. The
speaker always receives a record of their own speech. Private messages remain
delivery events and never become audible room speech.

The map is part of the seed, not a hidden author convenience. Agents receive
their current location and nearby actors, but not the coordinates or the
whole map unless the seed gives that person an ordinary reason to know them.
Message affordances are likewise actor-scoped: a person can address someone
who is co-located or listed as a seeded known contact. The roster is not
automatically a telephone directory, and the kernel rejects an attempted
message to an unknown, remote person.

A location may be marked `controllable: true` in the world pack. Only then
may an actor change that place's open/closed state. Shared places default to
not controllable, so one character cannot accidentally lock the whole map;
scheduled world events can still open or close any place as an objective
effect.

## Feedback

Every accepted action produces observable feedback, major or minor, and every
rejection explains why. The kernel derives this from objective state, never
from secrets or other actors' private knowledge:

- Rejections carry a reason plus concrete alternatives from current state
  (``item not here; present here: X, Y``, ``target is closed; open neighbors:
  A, B``, ``place does not support verb V; supported: knock``). The runner
  delivers them to the actor as an authoritative local operational fact with a
  feedback id.
- The executable argument shape of every action is defined as a JSON Schema
  (``harness/action_schema.py``) and validated before any semantic check.
  Shape errors are reported by deriving the message from the schema — they
  name the required key, the key actually provided, and the expected keys, so
  an agent that guesses an argument name (``read {item: X}`` instead of
  ``document``) can self-correct instead of looping on an opaque error.
- Accepted actions report their observable consequence: arrival location,
  picked-up/dropped item, opened/closed place, message delivery, speech reach.
  Delayed actions report that they are in progress and when they complete.
- `knock`/`interact` events record an objective `responded` flag: whether
  anyone was present at the target when the action completed. The actor
  therefore learns whether they were heard, rather than only that the knock
  executed.
- The supernatural System is named from the world pack (`system.name`); the
  engine never hardcodes a story label into feedback.

## Seeded scheduled effects

Scheduled world events may carry an `effects` list that mutates objective
state at the event time. The grammar is generic and story-neutral; replay and
checkpoints reconstruct the same state:

- `open_location: <id>` / `close_location: <id>` — change an open flag.
- `add_item` / `add_document: {id, location}` — place an existing entity that
  started absent (`location: null`).
- `move_item: {id, location}` / `remove_item: <id>` — relocate or withdraw.

A scheduled event may name a single `target` actor or a list of targets;
visibility follows exactly the listed actors. This lets the world announce
meetings or reopenings to the people they concern without leaking to everyone.
The loader rejects effects that reference unknown locations, items, or
documents before a run starts.
