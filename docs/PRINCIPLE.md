# Design Principles

This project is a reproducible, event-driven narrative simulation presented as a visual novel. It combines a silly system, serious autonomous characters, and a mostly deterministic world harness.

The goal is not to prove that simulated people are literally human. The goal is to preserve causal and epistemic integrity: characters act from their own motives and information, the world follows explicit rules, and unusual outcomes can be inspected and replayed.

## 1. The fiction contract

Every important character is a serious autonomous person within the fiction.

Character agents must:

- pursue their own goals rather than the MC's success;
- act from their motives, needs, personality, abilities, commitments, and circumstances;
- know only what they could have learned;
- retain private beliefs, including false or incomplete beliefs;
- remember imperfectly when the character's design permits it;
- make mistakes for character-grounded reasons, not because the plot requires them;
- refuse, ignore, misunderstand, compete with, or oppose the MC when appropriate;
- treat the world as real and never acknowledge the simulation, agents, prompts, routes, or author.

Agents must not silently become stupid, cooperate for unexplained reasons, or optimize for an entertaining story. They are not actors trying to play a role from outside the fiction; they are the character's decision-making process inside the fiction.

The MC has no narrative privilege. The world may help the MC only through explicitly designed mechanics, ordinary probability, or consequences earned through actions.

## 2. The author designs the seed; the world runs it

The author or design process defines the initial seed:

- geography, society, history, institutions, technology, magic, and supernatural rules;
- the complete backgrounds, capabilities, relationships, schedules, needs, and secrets of important characters;
- the existence, ownership, location, discoverability, and provenance of objects and information;
- the system bound to the MC, including its powers, limits, task rules, rewards, and penalties;
- all explicit exceptions to ordinary reality.

After initialization, the simulation should run from the seed, character policies, world rules, and recorded randomness. The author-level process may inspect a run and revise the seed between replays, but it must not silently repair the current run.

Comedy and romance should emerge from rational people colliding with one another, with circumstances, and with one deliberately irrational system. The world should not manufacture convenient allies, coincidences, emotional conversions, or enemy blunders merely to advance a route.

## 3. Separate objective reality from subjective knowledge

The simulation must keep these layers distinct:

1. **Objective world state** — what is actually true and what actually happened.
2. **Perception** — what an observer could see, hear, read, or otherwise detect.
3. **Belief** — what a character currently thinks is true.
4. **Memory** — what the character retains from prior experience.
5. **Public records** — messages, documents, announcements, rumors, surveillance, and other persistent evidence.

An event changes objective reality only through the world harness. A character's statement is an observable utterance; it does not directly change the truth of the statement. A listener may believe it, doubt it, or misunderstand it through that listener's own decision process.

No character agent may receive the whole world seed, another character's private thoughts, hidden route information, author intent, or facts that have not reached it through a valid information channel.

## 4. The world harness is authoritative

Character agents never directly mutate the world. They submit intentions. The harness validates, schedules, resolves, and commits them as events.

The harness is a deep module: its external interface should remain small while its implementation hides scheduling, preconditions, duration, perception, interruption, conflict resolution, state mutation, and replay.

A conceptual interface is:

```text
observe(character, wake_context) -> perception_packet
submit(character, intention) -> accepted | rejected
advance() -> next_world_events
replay(seed, event_log) -> world_state
```

Every accepted state change must have an event, an actor or authorized world cause, and a valid causal chain. Rejected intentions must not mutate state.

The harness, not an LLM, owns facts such as movement, visibility, audibility, inventory, money, object ownership, deadlines, appointments, recipes, travel duration, sleep, fatigue, hunger, weather, injury, and message delivery whenever those facts are covered by explicit rules.

## 5. Event-driven coroutine time

Agent reasoning consumes zero simulated time. Actions consume simulated time.

Characters may be:

```text
ready
performing(action, completion_time)
sleeping
waiting_for(event)
travelling
unavailable
```

The harness jumps to the next meaningful event instead of simulating every second. It wakes a character when an action completes, a relevant event occurs, a commitment begins, a need crosses a threshold, a plan becomes impossible, an interruption occurs, or a deadline becomes relevant.

Action duration comes from world rules or a common timetable, not from an agent improvising convenient timing. Speaking can use a defined relationship between text and duration; cooking, travel, sleep, and similar activities use explicit duration models.

Long activities must be interruptible when appropriate. A request such as `sleep for at least six continuous hours` is a harness-level condition, not a promise that six uninterrupted hours will occur.

## 6. Affordances, not plot options

The harness generates affordances: actions that a particular character could plausibly attempt from its current state and knowledge.

Affordances depend on:

- location, possessions, visible people and objects;
- physical and mental condition;
- skills and available resources;
- known commitments, time, and deadlines;
- social context and current conversation;
- explicit action preconditions;
- character habits and restrictions.

They must not depend on route labels, desired scenes, romance targets, or what would be entertaining.

An affordance is an attempt, not a guaranteed result. Typical universal options include continuing, stopping, waiting, leaving, asking for clarification, doing nothing, and attempting an unmodeled action.

Visual-novel choices are a presentation of legal MC affordances. The UI may group or rank them for usability, but it must not invent outcomes such as “make someone fall in love.” It may offer “offer soup,” “ask why they came,” “pretend not to notice,” or “leave.” Emotional and social consequences emerge afterward.

## 7. Prefer primitive, composable actions

Routine and common actions should be executable without an LLM judge:

- movement along a known route;
- observing, speaking, listening, reading, and messaging;
- handling objects and changing inventory;
- known recipes and other defined procedures;
- eating, sleeping, working, studying, and waiting;
- transactions, appointments, schedules, and deadlines.

Compound activities should compile into harness-level steps where useful. For example, making soup may become obtaining ingredients, washing, cutting, boiling, simmering, and serving. The character agent can request the activity, while the harness owns its execution, timing, preconditions, and interruptions.

An agent may request an action not represented by the current affordance set. The harness should compile it into known primitives when possible, reject it when impossible, or send it to semantic adjudication when its meaning or outcome cannot be determined mechanically.

## 8. Agents should not be general-purpose operators

Character agents should not have unrestricted tools for inspecting or manipulating the simulation. General-purpose tools encourage an agent to behave like an operator outside the fiction rather than a person living inside it.

The wake packet should contain the information the character can currently access. If the character wants new information, obtaining it must be an in-world action: looking, listening, asking, searching, reading, calling, remembering, or inferring.

Routine behavior should be handled by schedules, habits, and action macros. Invoke an LLM for meaningful decisions, interpretation, planning, and dialogue—not for every second of ordinary life.

Agents may deliberate privately, but private chain-of-thought is not world state and must not be used as authoritative fact. If diagnostics are needed, record only a compact decision trace: goal, relevant beliefs, risk, and chosen intention.

## 9. Deterministic scheduling and synchronization

At a simulation timestamp:

1. The harness applies scheduled deterministic events.
2. It computes who can perceive each event.
3. It wakes affected or otherwise ready characters.
4. It generates each character's private affordances and perception packet.
5. Agents independently submit intentions from the same prior world version.
6. The harness validates intentions and resolves conflicts using explicit rules.
7. Accepted intentions become events or scheduled actions.
8. The clock advances to the next wake-up, completion, or world event.

The completion order of LLM calls must never accidentally determine causality. Concurrent decisions should be based on a consistent snapshot, with deterministic tie-breaking for simultaneous effects.

## 10. Semantic adjudication is a constrained fallback

The simulation is not a GM that continuously invents scenes. A semantic resolver is invoked only when a submitted action has a meaningful unresolved outcome that the world rules cannot express.

Examples include an improvised excuse, a complicated negotiation, an unusual joke, an obscure recognition, or an unfamiliar interaction between magical effects.

The resolution pipeline is:

```text
character intention
    -> deterministic precondition checks
    -> known rule execution, when available
    -> semantic resolver, only when necessary
    -> constrained outcome
    -> deterministic validation and event commit
```

The resolver may inspect the complete objective history, current state, applicable rules, and causal history relevant to the attempt. It may not see narrative goals or use its knowledge to reveal private information to characters.

It must answer a narrow question—what can happen as a consequence of this attempt—not advance the plot. Its output must use an allowed outcome schema and cite existing facts or explicit rules. It may not:

- invent unrelated facts or events;
- decide for uninvolved characters;
- force affection, trust, forgiveness, or cooperation;
- rescue or specially punish the MC;
- override authoritative state;
- optimize for entertainment, route progress, or a preferred ending.

If the resolver produces an illegal effect, the harness rejects it. The resolver is an exceptional semantic adapter, not an alternative world authority.

## 11. The system is the intentional exception

The MC must be bound to a real system in the fiction. The system is the one deliberately irrational or supernatural mechanism, and its powers are part of the seed.

The system may issue absurd tasks, expose supernatural information, track conditions, and apply predefined rewards or penalties. It must still obey fixed, inspectable, replayable rules.

The system should impose constraints on ordinary behavior rather than directly controlling other people's minds. For example:

```text
Return the blue umbrella to its owner before 18:00
without saying “umbrella,” “rain,” or “sorry.”
```

This can be verified from events. The system must not silently force the owner to cooperate, change a character's feelings, or turn an NPC into a plot device unless such a power is explicitly part of the seed.

The system may know more than the MC only through its defined interface. It must not leak arbitrary hidden thoughts or future choices.

## 12. Replayability and evidence

The simulation should record an append-only event log containing, as appropriate:

- seed and randomness identifiers;
- world versions and timestamps;
- submitted intentions and validation results;
- accepted events and causal links;
- perception packets delivered to characters;
- character-visible messages;
- semantic resolver requests and constrained results;
- system tasks, checks, rewards, and penalties.

The design should make these claims testable:

- the same seed and inputs reproduce the same run;
- an agent cannot use information outside its knowledge state;
- every state change has an authorized cause;
- physical and social preconditions are enforced;
- rejected actions do not mutate state;
- character emotions do not change without an interaction or defined internal process;
- the MC receives no hidden narrative preference;
- semantic adjudication cannot create effects outside its schema.

These are proofs of model consistency and causal integrity, not proofs that the simulated characters are objectively human.

## 13. Author-level inspection happens between runs

An author analyst may inspect the event history after or during a run to identify boring stretches, implausible assumptions, missing affordances, broken causal chains, or unexpectedly funny butterfly effects.

The analyst may suggest changing the seed, character dossier, world rule, system rule, or simulation granularity. It must not alter the current run silently. Changes are made explicitly and tested by replaying from a new seed or revision.

The simulation discovers the plot. The author tunes the conditions that generate it.

## 14. Initial scope

The first useful prototype should remain small:

- one MC and roughly five important characters;
- one neighborhood or school-sized setting;
- one system;
- approximately fourteen simulated days;
- event-driven time;
- private beliefs and memories;
- movement, speech, messaging, sleep, travel, routine activities, and interruptions;
- a complete event and perception log;
- deterministic replay;
- a small semantic-adjudication fallback.

The prototype succeeds if it can produce a believable misunderstanding, a relationship change grounded in observable interaction, and a genuinely funny system consequence without requiring a constantly active GM.
