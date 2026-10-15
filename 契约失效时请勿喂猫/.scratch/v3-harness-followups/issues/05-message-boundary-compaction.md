# Preserve message boundaries when bounding context

Status: done
Type: bug

`_bounded_messages()` truncates the beginning of an individual message, which can cut JSON or world feedback into incoherent fragments. Bound by whole-message retention and invoke structured compaction before dropping content; add tests for oversized action results and natural-language observations.

## Agent Brief

**Category:** bug
**Summary:** Bound provider context without sending incoherent fragments of a character message.

**Current behavior:**
When the live session exceeds the provider request budget, `_bounded_messages()` preserves the prologue and newest content but truncates an oversized individual message from its beginning. This can send incomplete JSON, clipped world feedback, or a natural-language fragment detached from its cause.

**Desired behavior:**
Provider requests contain complete messages whenever possible. Structured compaction is preferred before dropping historical content. The system and initialization messages remain intact; dropped messages are represented by the session's compacted memory or trace rather than silently sliced.

**Acceptance criteria:**

- [ ] No provider request contains a partial message created solely by request bounding.
- [ ] JSON assistant responses are either retained whole or omitted as a whole, never sliced.
- [ ] World feedback and natural-language observations are either retained whole or omitted as a whole.
- [ ] System and initialization messages remain complete and ordered.
- [ ] Context remains within the configured request character limit.
- [ ] Tests cover oversized assistant JSON, world feedback, natural-language observations, and compaction interaction.
- [ ] The lossless trace remains unaffected by live-context bounding.

**Out of scope:**

- Changing the provider's context limit.
- Rewriting historical trace artifacts.
- Adding plot or character-state semantics to compaction.

## Comments

Implemented in v3 session: provider bounding now retains or omits complete
messages, and oversized authoritative feedback is archived in the actor-local
fact list rather than sliced. Focused tests cover JSON, feedback, natural
language, prologue limits, compaction, and lossless-session behavior.


## Comments

- 2026-09-14 agent (pi, 当前会话模型): closed: implemented; guarded by v4 historical ledger I05.
