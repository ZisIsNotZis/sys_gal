# 《契约失效时请勿喂猫》v2

v2 is an emergent romance-component story simulation. It is not yet a
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

Agents submit concrete actions such as sending a specified message to a named
person. They do not submit vague intentions such as “apologize” or “increase
affection”. The world records the message, delivery, location, timing, and
other objective consequences. The recipient decides what it means.

## Current status

This version begins with the engine and seed contract. No expensive experiment
is started until the v2 harness tests establish privacy, determinism,
coroutine time, and absence of narrative state.
