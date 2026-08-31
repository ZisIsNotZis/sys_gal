# v1 Harness Decisions

These decisions are the minimum canon needed to implement and test the first harness. Questions about richer psychology, adjudication heuristics, and narrative outcomes remain experimental.

## Resolved for v1

### Simulation identity

The simulation uses a fixed ISO timestamp with an explicit timezone: `2026-03-16T07:00:00+08:00`. Event ordering is determined by `(simulated time, monotonic sequence)`; external LLM completion order must never become simulated causality.

### Event authority

Only the world harness commits objective state changes. An intention is a request. It is accepted only if its action kind is known and its preconditions pass against the current world version. Every committed event records its cause and actor where applicable.

### Time model

Reasoning consumes zero simulated time. An action has a deterministic duration supplied by its action definition or an explicit duration policy. The harness schedules its completion and advances to the earliest queued event.

### Observation model

An observer can receive an event only when the event's visibility/audibility rule says so. v1 models coarse location and open/closed doors. Speech is audible only to actors in the same open location; v1 does not yet model line-of-sight geometry, distance, attention, language fluency, or memory distortion.

### Character state

Objective facts, perceptions, beliefs, and memories are separate concepts. v1 stores objective observations and leaves belief/memory updates to future character-agent work. A perception packet is private and generated for one observer.

### Actions

v1 includes `wait`, `speak`, `send_message`, `move`, `open`, `close`, `take`, `drop`, `sleep`, and `finish_activity`. Zero-duration actions complete immediately. Unknown semantic actions are rejected rather than sent to a judge; the semantic resolver is a later adapter.

### Compound actions

No compound-action planner is included yet. A future layer may compile a compound request into primitive actions, but the kernel only executes typed primitive actions in v1.

### System authority

The Ledger's initial case is data and can be displayed to Chen. Acceptance and settlement are not implemented in the first kernel. The Ledger may later commit only explicitly allowed supernatural events; it cannot mutate NPC emotions or make an NPC act.

### Randomness

The kernel is deterministic in v1. Randomness, when introduced, must use a named seeded stream and be recorded in the event log. No random stream is needed for the current actions.

### Versioning

Seed and code changes are copied into a new `v<N>` directory before an experiment. A run records the source version. No experiment is started from an unlabelled working tree.

## Deferred experiments

- how much attention and partial perception to model;
- character belief and memory update policies;
- compound-action compilation;
- semantic resolver input reduction and output schema;
- whether action durations need character-specific modifiers;
- how much routine life can be represented by schedules/macros;
- how agents request actions not present in the affordance set.
