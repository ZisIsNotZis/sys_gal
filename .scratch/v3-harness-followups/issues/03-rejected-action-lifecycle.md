# Consume rejected-action feedback instead of replaying it forever

Status: done
Type: bug

Rejected operational facts accumulate in character context and are repeated on later turns. Give each rejection an event identity and lifecycle so it is acknowledged once, remains available as relevant history, and is not injected as a fresh unresolved prompt every wake-up.

## Agent Brief

**Category:** bug
**Summary:** Deliver rejected-action feedback once while preserving authoritative history and actor isolation.

**Current behavior:**
The runner appends rejected actions to an actor's operational-fact list and injects the entire list into every later perception. Old warnings therefore appear as if they were new, unresolved feedback.

**Desired behavior:**
Each rejection has a stable identity, is delivered as fresh feedback once, and remains available in durable trace/session history without being re-announced on every wake-up. A rejection may become relevant again only after a relevant objective condition changes. Rejections remain private to the actor who made the rejected attempt.

**Acceptance criteria:**

- [ ] Every rejected action receives a stable event or feedback identity.
- [ ] Fresh rejection feedback is delivered exactly once to the affected actor.
- [ ] The rejection remains auditable in the trace and session history.
- [ ] Rejections are never visible to unrelated actors.
- [ ] A repeated identical attempt does not cause unbounded repeated warning injection.
- [ ] A test covers re-announcement after a relevant condition change, if that behavior is supported.
- [ ] Existing action rejection semantics remain unchanged: rejected actions have no world-state effect.

**Out of scope:**

- Changing the agent's private beliefs or memories automatically.
- Adding plot, romance, affection, or relationship state.
- Suppressing the rejection from durable audit records.

## Comments


## Comments

- 2026-09-14 agent (pi, 当前会话模型): closed: implemented; guarded by v4 historical ledger I03.
