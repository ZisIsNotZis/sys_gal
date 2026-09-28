# Make checkpoints fully resumable

Status: done
Type: enhancement

Checkpoints do not fully serialize the pending queue, mutable actor state, inbox cursors, and pending actions. Persist and restore all scheduler and session state so an interrupted run resumes causally rather than replaying, skipping, or duplicating events.

## Agent Brief

**Category:** enhancement
**Summary:** Make checkpoints true causal resume points for world, scheduler, runner, and character sessions.

**Current behavior:**
Trace checkpoints preserve an auditable event history, but they do not fully capture pending scheduled work, actor busy state and inbox cursors, runner waiting/retry state, operational feedback, or all persistent session state required to continue.

**Desired behavior:**
A checkpoint can be loaded into a fresh process and resumed at the same next observable boundary as an uninterrupted run. Recovery neither repeats nor skips accepted events, world messages, agent turns, queued work, or retry decisions.

**Acceptance criteria:**

- [x] Pending scheduled events and their ordering/cause data are serialized and restored.
- [x] Mutable actor state, `busy_until`, inventories, inboxes, and event cursors are restored.
- [x] Runner waiting sets, transient-failure counters, retry timing, and operational feedback are restored.
- [x] Character session transcripts, compact memories, authoritative feedback, and state snapshots are serialized without cross-actor leakage.
- [x] An interrupted/resumed deterministic run reaches the same next boundary and objective state as an uninterrupted run.
- [x] Recovery tests prove no duplicate or skipped event, message, action, or session turn.
- [x] Corrupt/incompatible checkpoints fail explicitly without mutating a live run.

## Evidence

- Added `World.checkpoint_state`/`restore_checkpoint`, atomic checkpoint JSON I/O,
  runner operational-state snapshots, and trace checkpoint composition.
- `harness.tests.test_checkpoint`: 4 tests passed; complete v3 harness suite: 158
  tests passed.
- Deferred: rebuilding provider callables from a checkpoint remains an application
  integration concern; actor-local `CharacterSession.from_snapshot` is the restore
  seam and hidden provider state is intentionally not serialized.

**Out of scope:**

- Changing the story seed or adding narrative checkpoints.
- Reconstructing hidden model chain-of-thought.
- Adding romance, affection, or plot state to the generic engine.

## Comments


## Comments

- 2026-09-14 agent (pi, 当前会话模型): closed: implemented; guarded by v4 historical ledger I07.
