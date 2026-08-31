# Simulation Contract for This Seed

This is a narrative seed, not implementation code. These rules define what later harness code must preserve.

## Authority

The world harness is authoritative over objective state, time, perception, action preconditions, and committed events. Character agents submit intentions and never mutate the world directly.

The Ledger is an authorized supernatural module with only the permissions listed in [system.md](system.md). A semantic resolver may adjudicate an unresolved action, but may not invent unrelated events, choose for uninvolved characters, or optimize for a route.

## Time

Agent reasoning consumes zero simulated time. Actions consume time. The world advances to the next relevant completion, interruption, scheduled commitment, or externally caused event.

Routine actions use common duration rules. An action may be compound and execute as harness steps. Long actions are interruptible when their definition says so.

## Information

Each character receives a private perception packet. It contains only observations, messages, memories, beliefs, bodily state, accessible objects, and relevant commitments. Objective facts in another character's file are not automatically visible.

The narrator and author analyst may inspect more than characters. Their output must not feed hidden facts back into character dialogue or decisions.

## Affordances

Available actions derive from location, objects, people, condition, skill, time, knowledge, social context, and explicit preconditions. They do not derive from scene labels, romance routes, or desired dramatic beats.

## Evidence discipline

Every belief change should cite an observed event, message, memory, inference, or system disclosure. Every objective state change should have an event and causal source. Character emotions may evolve through interaction and internal processing, but cannot be directly set by the plot.

## Replay

The seed revision, random seed, agent inputs, accepted intentions, resolver results, system events, perception packets, and committed event log must be retained well enough to replay a run and inspect why an outcome occurred.
