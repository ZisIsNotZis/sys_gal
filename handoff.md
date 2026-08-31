# Handoff: v3 large-scale run monitoring

## Purpose of the next session

Continue monitoring the already-launched large-scale provider-backed v3 story run at five-minute intervals, terminate it only if a serious failure appears, and immediately inspect/report the saved trajectory after it exits. Do not start a second run.

## Repository and current architecture

- Repository: `/home/z/vibe/sys_gal`
- Active story version: `/home/z/vibe/sys_gal/契约失效时请勿喂猫/v3`
- Generic engine: `v3/harness/`
- World seed: `v3/world/`
- Engine contract: `v3/docs/ENGINE_CONTRACT.md`
- Tracker: `/home/z/vibe/sys_gal/.scratch/v3-harness-followups/`
- Run-analysis rules: root `AGENTS.md` and `CLAUDE.md`

The engine is story-neutral. It must not contain plot phases, romance/affection/hate scores, relationship APIs, or protagonist privilege. Romance and comedy emerge from world/character seed data and observable causal events.

## Current issue status

Ready-for-agent: issues 01–07 and 09. Issue 08 remains `needs-triage` and is explicitly deferred until controlled evidence proves streaming causes the prior 502s. Do not implement streaming merely because another client uses it.

Recent approved design decisions:

- Ordinary physical interactions use a generic `interact(target, verb, parameters)` seam; `knock` is only the first example. Do not create a file or top-level action kind for every door or verb.
- Common sense belongs in the system/engine contract; public world facts belong in public seed data; secrets are actor-scoped; objective access conditions are world data.

## Changes already made by subagents

Subagents implemented issues 01/02, 03/04, 05/06, and 07/09. The shared v3 suite was reported and then independently rerun successfully:

```text
cd /home/z/vibe/sys_gal/契约失效时请勿喂猫/v3
python3 -m unittest discover -s harness/tests -p 'test_*.py'
Ran 160 tests in 4.964s
OK
```

`git diff --check` passed. Changes are uncommitted and intentionally belong to the user; do not reset or discard them.

Known compatibility concern: older checkpoint formats may lack newer session fields and may need migration if old checkpoints are restored. The current run should start from scratch and use current checkpoints.

## Active process

The correct current process is the Codex-native PTY session:

- PTY session ID: `72193`
- PID: `976680`
- Command: `env V3_MAX_WALL_SECONDS=7200 V3_MAX_TRANSIENT_FAILURES=3 python3 -m harness.real_run`
- Working directory: `/home/z/vibe/sys_gal/契约失效时请勿喂猫/v3`

There was an earlier duplicate run (PID `975637`) that was interrupted and produced a separate failed/incomplete artifact. It must not be confused with the active run. The earlier process was terminated.

The active run’s latest artifact observed before handoff:

- `/home/z/vibe/sys_gal/契约失效时请勿喂猫/v3/runs/real-20260825T161547+0800-976680-356221843.json`

It was still being written and was about 591 KB at the last check. The earlier duplicate produced:

- `runs/real-20260825T161456+0800-975637-657244603.json`
- `runs/real-20260825T161456+0800-975637-657244603.error.log`

Do not poll every 30–60 seconds. Wait approximately five minutes between checks. Use the existing PTY session with `write_stdin` and a long timeout, or check the PID and artifact modification time. Do not send Ctrl-C unless a serious failure is observed or the user requests termination.

## Monitoring procedure

At each five-minute check:

1. Check whether PID `976680`/session `72193` is still alive.
2. Check the newest active `real-*.json` modification time and size.
3. If still alive and the artifact is advancing, report briefly that it is progressing, then continue the five-minute wait.
4. If it exits, do not relaunch automatically. Locate the unique newest artifact and inspect it immediately.
5. Treat provider errors, agent errors, timeouts, malformed trace state, stalled/no-progress behavior, or duplicated/incoherent session messages as serious; terminate the run if it is still alive and preserve its artifact.

## Required post-run review

Never report only counts or “clean/failed.” Manually inspect the saved trajectory before replying. Read representative early, middle, late, and failure-boundary sections, including:

- agent perceptions and executable intentions;
- action results and world events;
- private-state updates and session messages;
- System and GM records when present;
- acoustic/privacy boundaries and knowledge provenance;
- repeated loops, impossible knowledge, retry duplication, context loss, and action-result misunderstanding;
- whether romance-relevant contact, vulnerability, conflict, or repair actually emerged;
- whether the run reached the objective endpoint and whether that endpoint is narratively useful.

Distinguish infrastructure failure, engine failure, valid objective completion, and useful story trajectory. Do not expose hidden chain-of-thought.

## Important previous mistake

An initial `nohup ... &` launch exited immediately after writing an empty checkpoint. The user explicitly prefers background execution with occasional five-minute checks. The Codex-native PTY session is the currently active launch; avoid creating another terminal or process.

## Suggested skills

- `diagnosing-bugs` if the active run stalls, errors, or exhibits a reproducible harness failure.
- `code-review` after reviewing the accumulated implementation changes.
- `triage` for further issue-state work in `.scratch/v3-harness-followups/`.
- `writing-for-agents` only if modifying `AGENTS.md`, `CLAUDE.md`, or other agent-consumed instructions.
