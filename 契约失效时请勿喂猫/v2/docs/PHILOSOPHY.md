# v2 Philosophy

## Purpose

Create an interesting romance-component story from a purposely designed
System, world seed, and serious autonomous character agents. The engine should
make the trajectory possible and inspectable; it must not manufacture plot.

## Three separate products

1. **Simulation:** objective world plus independent characters.
2. **Novel:** artistic reconstruction of one complete recorded trajectory.
3. **Galgame:** a later interface designed from many sampled trajectories.

The simulation does not contain the novel's chapter structure or the game's
player choices. It produces facts from which those can later be made.

## What the world knows

The world knows only objective state covered by explicit rules: time, place,
objects, physical conditions, schedules, messages, speech, documents,
contracts, and the System's defined effects. It does not know whether a
conversation was romantic, whether a character felt affection, or whether a
trajectory is interesting.

Sound is an objective physical channel. A spoken sentence reaches only actors
within the seeded acoustic geometry after distance and barriers are applied;
private messages do not leak through speech visibility.

## What a character agent is

An agent is the in-fiction decision process of one assigned person. It gets a
private observation packet containing only what that person could currently
know, plus private memory and belief state owned by that agent. It pursues its
own goals and may refuse, misunderstand, conceal, leave, fall in love, lose
interest, or fail. It never receives author intent, plot expectations, other
agents' private states, or the whole seed.

Private affect is not world state. If Lin feels betrayed, the engine does not
write `affection -= 5`; Lin's agent retains that interpretation and may later
send a message, avoid Chen, confront him, or do something unrelated. The
trajectory records observable evidence and actions, not an invented emotion
score.

## Concrete action principle

There are no vague semantic choices such as “apologize to Lin” or “increase
romance”. An agent must choose an executable act with its wording and target,
for example:

```json
{"kind":"send_message","target":"lin-yao","text":"I kept the form since Monday because I was afraid Gao would lose his position."}
```

The harness validates the action and schedules delivery. Lin interprets it.
If an action cannot be expressed by existing primitives, the agent may submit
a bounded request for semantic adjudication; that resolver answers only the
physical/social consequence of this attempt and never updates a plot or an
emotion value directly.

## System boundary

The System is an actual in-world supernatural entity bound to Chen. It may
propose concrete contracts, expose narrowly permitted objective facts, and
apply explicitly seeded rewards or penalties. It cannot force affection,
reveal unearned secrets, make an NPC cooperate, or decide what a message means.
Its absurdity is the designed source of comedy; the rest of the world remains
ordinary and causally constrained.

## Outcome and inspection

The run ends only at a seed-defined objective condition: for example a fair's
real closing, Chen's departure, death, or another explicit world condition.
“Interesting”, “romantic”, and “good ending” are post-run analytical judgments
or authoring goals, never engine state. All agent trajectories, perceptions,
intentions, rejections, semantic calls, and authoritative events are saved.
