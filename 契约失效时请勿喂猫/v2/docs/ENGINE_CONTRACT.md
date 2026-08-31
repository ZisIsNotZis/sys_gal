# v2 Engine Contract

The engine exposes a small neutral interface:

```text
observe(actor) -> private perception packet
affordances(actor) -> legal concrete action shapes
submit(intention) -> accepted/rejected
advance() -> next objective events
replay(seed, event log) -> objective state
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
