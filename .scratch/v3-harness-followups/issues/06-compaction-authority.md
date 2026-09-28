# Test and guarantee authoritative facts survive compaction

Status: done
Type: enhancement

Compaction was observed for only one actor, and preservation of authoritative action results, private facts, and current obligations is not established. Define a compact session schema with provenance and test it across every actor, including facts that must remain private and facts that must not be invented.

## Agent Brief

**Category:** enhancement
**Summary:** Make session compaction preserve authoritative facts with provenance and privacy.

**Current behavior:**
The session attempts to preserve world feedback during compaction, but authoritative feedback is not fully represented in snapshots, oversized entries may be truncated, and tests do not establish the contract across actors or restoration.

**Desired behavior:**
Compaction produces a bounded working memory while the trace remains lossless. Objective world results remain distinguishable from model memories, preserve chronological provenance, and remain scoped to the actor who could observe them. Private facts never enter another actor's context or a world/GM prompt.

**Acceptance criteria:**

- [ ] The compact session schema explicitly represents authoritative feedback, compacted memories, and their provenance/order.
- [ ] Session snapshot and restoration preserve all live authoritative facts required by the contract.
- [ ] Compaction never invents an objective fact or silently changes the meaning of a retained result.
- [ ] Oversized feedback is handled by whole-record omission/archival or structured representation, not arbitrary semantic truncation.
- [ ] Tests cover every character session, repeated compaction, snapshot/restore, and ordering.
- [ ] Tests prove private state and actor-local facts cannot leak to another actor or the GM.
- [ ] The lossless trace retains the complete original event and session history.

**Out of scope:**

- Choosing what characters believe or feel.
- Adding affection, hate, plot, or romance state.
- Replacing the provider with a deterministic summarizer.

## Comments

Implemented in v3 session: snapshots now carry actor-local state, ordered
authoritative world facts with source provenance, and ordered compaction
memories; `from_snapshot` restores the working session. Tests cover repeated
compaction, restore, all test actors, and GM/private isolation.


## Comments

- 2026-09-14 agent (pi, 当前会话模型): closed: implemented; guarded by v4 historical ledger I06.
