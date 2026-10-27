**English** | [简体中文](README.zh-CN.md)

<img src="assets/logo.svg" alt="sys_gal" width="132">

# sys_gal

### A reproducible Chinese narrative-simulation lab

**`sys_gal` runs small Chinese-fiction worlds on explicit rules — every character acts only on what it itself perceived, and every run leaves a trace you can replay byte for byte and audit.**

This is a research prototype, not a game. Its subject is a narrow question: when a character makes a move, was that the world pushing it or the author arranging it? The answer is only checkable if the world is objective (events happen by rules, not narration), the information boundary is real (a character knows what was delivered to it, and nothing else), and the evidence is complete (the trajectory plus the context behind each decision survives the run).

## Quick start

```bash
git clone git@github.com:ZisIsNotZis/sys_gal.git
cd sys_gal/契约失效时请勿喂猫/v5
pip install pyyaml                    # the only runtime dependency
python3 -m stories.s1_last_bus.run a  # 《末班车》 route a — scripted, deterministic, free
sed -n '1,40p' stories/s1_last_bus/runs/a.md
```

The story writes four artifacts into `stories/s1_last_bus/runs/`: the transcript (`a.md`), the context each actor held before each action (`a.context.md`), the event ledger (`a.events.json`) and the summary (`a.json`). Routes `b` and `c` exist too.

Run the same story with a real model through any OpenAI-compatible endpoint (it defaults to a local LiteLLM gateway on `localhost:4000`, credentials from `LITELLM_BASE_URL` / `LITELLM_MASTER_KEY`):

```bash
python3 -m stories.s1_last_bus.agent_run github_copilot/gpt-6-luna 4   # model, turns per character
```

Real-model runs cost money and leave one immutable directory per run under `runs/agent-<time>-<pid>-<tag>/`.

## What it can do now

- **Five stories, each a different world** — 《末班车》 a 22:30 bus, three stops, a bag left on a seat; 《借条》 one IOU, one added stroke, one person who recognizes the handwriting; 《夜市》 a confiscated stall and a deposit slip passing through many hands; 《夜班》 a convenience-store night shift short 200 at handover; 《婚礼》 a full banquet day and a signature nobody recognizes. Two more are declared on the ladder but have no seed yet.
- **Ten primitives and 26 verbs** — entities, state, containment, time, events, perception delivery, minds, intents, rules, name resolution; the daily verbs (`read`, `write`, `copy`, `sign`, `retell`, `shift`, …) are built from them in `library/`, not in the engine.
- **Perception, not omniscience** — each turn a character receives only its own view: what is in front of it (a page is "written on", not readable), the recent deliveries it actually got, the things it believes (possibly wrong, possibly stale). Reading the text is a separate verb that writes only into that character's memory.
- **Byte-exact replay** — every state change goes through a rule's atomic effects; each event records the world digest after it; replaying the ledger must match digest for digest or it raises `ReplayMismatch`.
- **Checkpoint and resume** — a checkpoint freezes world state plus the ledger prefix; resuming continues event numbering, and the clock rolls the date after midnight (`18:30 → 08:00` reads as the next day, never `32:00`).
- **Evidence that stays whole** — a run's four raw files are packed into one `runs/<story>-<route>.jsonl.zst` with no truncation. Measured on this tree: 100 raw files, 3,172,688 bytes, packed to 25 artifacts of 227,547 bytes (13.9×), every byte recoverable by `unpack`.
- **Gates that can turn red** — a structure lint, three anti-cheat checks, a pack check and the unit suite, plus a numbered ledger (`R01…`) where each historical defect keeps a test that fails if it comes back.

## Architecture

Three layers, and the rule that keeps them honest: a fact lives in exactly one of them.

| Layer | Owns | Must not contain |
| --- | --- | --- |
| `engine/` | the ten primitives, seed parsing, scheduling and turns, replay, checkpoints, the projection each mind sees | any story noun, any concrete verb, any world property |
| `library/` | reusable common sense: properties, rules, renderers, failure receipts, institutions, stocktake, the verb table | a world instance, a plot, a story noun |
| `stories/<story>/` | one `seed.yml` (places, cast, knowledge, schedule), the cast script, this story's acceptance, its runs | logic, engine truths, imperatives aimed at a named character |

A seed is data and nothing else: unknown fields are a load-time `ValueError`, never silently dropped. An intent is adjudicated by the rule registry, which emits atomic effects; the event ledger is the only account of what happened. Renderers project that ledger into a per-mind surface; the packer carries the ledger and the views out as one artifact.

```text
契约失效时请勿喂猫/
├── v1/ v2/ v3/       archived version lines
├── v4/               reference line (archived): harness, world, long-run discipline
└── v5/               the main line
    ├── engine/       10 primitives, seed parsing, rules, replay — no story nouns
    ├── library/      properties, rules, renderers, failures, stocktake, institutions
    ├── stories/      one seed.yml + cast script + acceptance per story, plus runs/
    ├── scripts/      v5_lint.py, anti_cheat.py, pack_trajectory.py
    ├── runs/         packed trajectories (committed)
    └── tests/        engine, gates, replay, story acceptance, historical failure ledger
```

Only `v5` describes current behaviour; `v4` and earlier are kept for provenance. The design record is layered: [`docs/0_ROADMAP.md`](docs/0_ROADMAP.md) for milestones and open questions, [`docs/1_PROBLEM.md`](docs/1_PROBLEM.md) … [`docs/9_IMPLEMENTATION.md`](docs/9_IMPLEMENTATION.md) for each layer of the argument, [`docs/adr/`](docs/adr/) for decisions with their rejected branches, and [`CONTEXT.md`](CONTEXT.md) for the shared vocabulary.

## How to develop

All commands run from `契约失效时请勿喂猫/v5/`. Requirements: Python 3, `PyYAML`, and the `zstd` binary for packing.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'   # the suite
python3 scripts/v5_lint.py --strict                    # seed shape, renderers, orphan concepts, engine blindness
python3 scripts/anti_cheat.py --verbose                # no imperatives, no providential events, endings not unique
python3 scripts/pack_trajectory.py check               # every artifact packed, fresh, and byte-identical
python3 scripts/v5_lint.py                             # report mode, orphans are warnings
```

There is no CI: the four gates above are run by hand before any run whose numbers get quoted, and a red gate blocks rather than invites "let's just try it". Test strategy and run discipline are in [`docs/9_IMPLEMENTATION.md`](docs/9_IMPLEMENTATION.md); the post-run analysis protocol is in [`AGENTS.md`](AGENTS.md).

Start reading here if you are new: [`AGENTS.md`](AGENTS.md) (working policy), [`契约失效时请勿喂猫/README.md`](契约失效时请勿喂猫/README.md) (the experiment), [`CONTEXT.md`](CONTEXT.md) (vocabulary).

## How to contribute

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Short version: run the four gates, keep the engine free of story nouns, keep one fact in one home, and make a claim falsifiable or don't make it.

## Roadmap

**Implemented**

| Milestone (named by what it proved) | Evidence in the tree |
| --- | --- |
| Specs frozen — engine, concept library, story ladder and route written before any code | `docs/1…9`, `docs/adr/` |
| Toy world — 《末班车》 runs from seed to close, replay identical byte for byte | `stories/s1_last_bus/`, `tests/test_m1_*` |
| First generalization — 《借条》 in a second world, two routes, no story noun in `engine/` | `stories/s2_borrow_note/`, `tests/test_m2_*` |
| Actor pilot — scripted cast replaced by a real model, the world decides whether it was pushed or staged | `stories/agent_loop.py`, real-model trajectories in `v5/runs/`, `tests/test_m3_*` |
| Half day — 《夜市》 runs from 18:30 past midnight, every ownership of the slip physically reachable | `stories/s3_night_market/`, `tests/test_m4_*` |
| One day, two worlds — 《夜班》 and 《婚礼》 each run a full day on the same concepts, at the same measured scale | `stories/s4_night_shop/`, `stories/s5_wedding/`, `tests/test_m5_*` |

**Planned**

| Milestone | What it must show |
| --- | --- |
| 《快递站》 — three days, one lost parcel, everyone changes their story once | cross-day state, memory drift, responsibility, trust; the record is the only thing that did not change |
| 《契约失效时请勿喂猫》 — the twelve-day campus arc | the signature on the 2013 notice is spoken by a person and never spoiled by the ledger; the full ladder of concepts on one long story |

The direction is a laboratory where a long story arc is reproducible: you can rerun it, stop it mid-way, resume it, hand the trajectory to someone else, and they can check every claim you make about it. Open problems — a wedding where ten people are present but only two carry the scene, a night shift whose manager has one line per route, two verbs implementing one institutional act — are listed honestly in [`docs/0_ROADMAP.md`](docs/0_ROADMAP.md).

## License

GNU Affero General Public License v3.0 (AGPL-3.0-only). Copyright © ZisIsNotZis. See [`LICENSE`](LICENSE).
