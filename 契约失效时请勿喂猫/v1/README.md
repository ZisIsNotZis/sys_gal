# 《契约失效时请勿喂猫》

**English working title:** *When the Contract Fails, Do Not Feed the Cat*

**Version:** v1

This directory contains the versioned seed and the first harness implementation. Each later revision gets a new sibling directory (`v2`, `v3`, ...); a revision is never edited in place after it has been used for an experiment.

## Premise

At Haicheng's private Luming University, a student community fair is threatened by an accounting discrepancy. Chen Mo, a conflict-avoidant student who habitually accepts vague responsibilities, becomes bound to the **Mutual Obligation Settlement System**, nicknamed **The Ledger**.

The Ledger offers contracts rather than commands. It rewards precisely defined voluntary obligations and penalizes ambiguous commitments. Its rules are supernatural; its interpretation of human motives is painfully literal. It cannot make anybody love, trust, forgive, or help Chen Mo.

## Database map

- [World](docs/world.md)
- [Simulation contract](docs/simulation-contract.md)
- [Timeline](docs/timeline.md)
- [System: The Ledger](docs/system.md)
- [Characters](docs/characters/)
- [Organizations](docs/organizations/)
- [Locations](docs/locations/)
- [Items and records](docs/items/)
- [Relationships](docs/relationships.md)
- [Open design questions](docs/open-questions.md)

## Harness map

- [Harness decisions](docs/harness-decisions.md)
- [Harness source](harness/)
- [Harness tests](harness/tests/)

## v1 scope

The playable seed begins on **2026-03-16 at 07:00**, ten days before the planned community fair. The initial implementation provides an event log, immutable-ish world snapshots, event-driven time, typed intentions, deterministic affordance generation, private perception packets, visibility/audibility checks, and the Ledger's initial case data.

The deterministic cast runner now exercises nine independent participants:
Chen, Gao, Lin, He Qian, Luo, Qiao, Xu, Amani, and a non-speaking stray cat.
The intended complete v1 arc runs from 2026-03-16 07:00 through the fair's
close on 2026-03-27 21:30, records private agent trajectories and the
authoritative world log, and terminates only after every major participant has
an explicit outcome. The current policy agents are a
cheap reproducible harness stand-in; model-backed agents and constrained
semantic adjudication remain later work.
