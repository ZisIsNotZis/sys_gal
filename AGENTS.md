# Run analysis protocol

After every provider-backed story run, manually inspect the saved trajectory before replying to the user. This is mandatory even when the process reaches the seeded endpoint.

Treat the provider runner as a readiness gate: never call a bounded probe or
full run successful merely because it reached a clock endpoint. A provider
failure whose retry budget is exhausted is terminal for fail-fast runs and
must be checkpointed as a failed trace. Every invocation must use a unique run
artifact so no trajectory is overwritten.

The report must lead with concrete observed behavior and causal problems, not counts or a clean/failed label. Read representative early, middle, late, and failure-boundary turns from the actual agent trajectories, plus the corresponding world events, GM records, System records, and session context when relevant. Trace each important problem to its root cause and propose a specific fix, identifying whether it belongs in the harness, provider/session protocol, prompt, seed, or story-analysis layer.

Explain what characters actually perceived, believed, attempted, misunderstood, learned, concealed, or repeated. Check for information leaks, impossible knowledge, action-result misunderstanding, repeated loops, context loss, implausible behavior, missing relationship development, and whether the seeded endpoint produced a meaningful continuation. Distinguish an objective world endpoint from a valid run: reaching `world_stops` alone never proves the trajectory is healthy or complete.

Statistics may support an observation, but they are never the conclusion. Do not answer a post-run request with only event/turn/error counts or a clean/invalid verdict. Always include:

1. What happened in the lived trajectory, with concrete examples.
2. The problems observed and why they occurred.
3. The proposed root-cause fixes and what should be tested next.
4. An honest assessment of whether the run is useful as a story experiment.

For expensive full runs, preserve the complete trace and inspect it after completion. Do not expose hidden chain-of-thought; analyze observable agent outputs, private-state updates, visible perceptions, world events, and recorded session messages.

## Pre-run gate

Before launching any large provider-backed run, every documented historical
failure pattern must be covered by a green regression test. The ledger lives in
`契约失效时请勿喂猫/v3/harness/tests/test_historical_failures.py` and maps each
observed failure (v1/v2 audits, v3 issues 01-09, large-run deadlocks) to its
guarding test. Run the full suite and treat any red historical gate as a block:

```text
cd 契约失效时请勿喂猫/v3
python3 -m unittest discover -s harness/tests -p 'test_*.py'
```

The deterministic endpoint gate (`test_deterministic_seed_run_reaches_seeded_endpoint`)
proves the seed schedule drains to `world_stops`; the dead-end gate
(`test_seed_closed_locations_all_have_a_scheduled_opening_effect`) proves no
closed location is permanently unreachable. A large run is only worth its cost
once these are green.

## Interrupted-run methodology

Provider instability is common and is not a reason to redo a run. The default
resilient provider rides through transient blips with generous capped backoff
(`provider_from_env`, tunable via `V3_PROVIDER_*`). When a problem does stop a
run:

1. Fix the related code or seed file.
2. Restart from the last good checkpoint — `real_run` writes
   `runs/<runid>.checkpoint.json` every batch (world + runner + private state +
   session transcripts).
3. `python3 -m harness.resume_run runs/<runid>.checkpoint.json` continues
   causally (event ids/versions stay contiguous) and writes a new, unique
   artifact.

Conversation history is preserved across the restart (sessions come from the
checkpoint); only the code that runs it may have changed. Start fresh only for
 a large goal-level change that makes prior history meaningless.

## Agent skills

### Issue tracker

Issues and specs are tracked as local Markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository with root `CONTEXT.md` and `docs/adr/` conventions. See `docs/agents/domain.md`.
