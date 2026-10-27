# Sys Gal 🧠

English | [简体中文](README.zh-CN.md)

An experimental Chinese narrative-simulation workspace. It studies autonomous characters, information boundaries, and reproducible story trajectories through versioned scenario and harness work.

## Where to start

- [AGENTS.md](AGENTS.md) — repo-wide agent working policy; read before provider-backed work.
- [`契约失效时请勿喂猫/`](契约失效时请勿喂猫/) — the primary experiment; start at its [README](契约失效时请勿喂猫/README.md).
- [CONTEXT.md](CONTEXT.md) — shared domain glossary.

## The docs, by layer

One home per fact. Lower number = closer to purpose.

| level | file | holds |
| --- | --- | --- |
| — | [docs/0_STAGING.md](docs/0_STAGING.md) | facts worth keeping that have not reached their layer yet |
| — | [docs/0_ROADMAP.md](docs/0_ROADMAP.md) | milestones, work packages, what is decided, what is open |
| 1 | [docs/1_PROBLEM.md](docs/1_PROBLEM.md) | why this is worth doing |
| 2 | [docs/2_GOAL.md](docs/2_GOAL.md) | what success looks like, and what it does not claim |
| 3 | [docs/3_REQUIREMENT.md](docs/3_REQUIREMENT.md) | the fiction contract, layer separation, determinism, replayability |
| 4 | [docs/4_USECASE.md](docs/4_USECASE.md) | who completes what, the four flows, the seven stories as value slices |
| 5 | [docs/5_PRODUCT.md](docs/5_PRODUCT.md) | story ladder, coverage matrix, known findings, rejected branches |
| 6 | [docs/6_ARCHITECTURE.md](docs/6_ARCHITECTURE.md) | engine / library / seed boundaries and quality strategies |
| 7 | [docs/7_INTERFACE.md](docs/7_INTERFACE.md) | seed schema, verb table, run artefacts, CLI, error semantics |
| 8 | [docs/8_DETAIL.md](docs/8_DETAIL.md) | primitives, clock, checkpoint, stocktake, anti-cheat internals |
| 9 | [docs/9_IMPLEMENTATION.md](docs/9_IMPLEMENTATION.md) | environment, gates, testing strategy, run and pack discipline |

Decisions with their rejected branches live in [docs/adr/](docs/adr/).

## Status and future

This is an evolving research prototype, not a finished game or claim of human story quality. The current line is v5 (`契约失效时请勿喂猫/v5`); the goal is a reproducible narrative laboratory where character behavior, knowledge, failures, and causal continuity can be inspected. Progress is in [docs/0_ROADMAP.md](docs/0_ROADMAP.md).

Issues and PRs are welcome. Agents may help investigate and document; maintainers review and merge.
