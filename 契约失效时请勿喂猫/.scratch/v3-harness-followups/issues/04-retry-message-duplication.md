# Make provider retries idempotent

Status: done
Type: bug

An outer provider retry can append the same world message repeatedly without an intervening assistant response. Separate attempt-local transport messages from committed session history and commit an observation only after a valid response, preserving one causal world update per turn.

## Agent Brief

**Category:** bug
**Summary:** Make provider and runner retries idempotent at the character-turn boundary.

**Current behavior:**
An inner provider retry may be safe before an action is submitted, but an outer runner retry can cause the same world observation to be appended again without an intervening assistant response. This corrupts the persistent character transcript and can induce repeated behavior.

**Desired behavior:**
A decision boundary has one stable turn identity. Transport retries reuse that identity and do not append duplicate world/user messages. Session history is committed only when the model response has reached a terminal parse/result state; no action or world event is duplicated by recovery.

**Acceptance criteria:**

- [ ] A retry of the same provider request does not duplicate the world observation in session messages.
- [ ] A successful retry produces exactly one assistant response and at most one submitted world action.
- [ ] A failed retry sequence is auditable without fabricating an assistant response or world event.
- [ ] Inner and outer retry behavior is bounded and does not create concurrent calls for one character session.
- [ ] Tests cover one retry, repeated retry, terminal failure, and recovery after a transient failure.
- [ ] Other actors' observations and private session messages remain unchanged.

**Out of scope:**

- Changing provider model selection or prompt content.
- Changing world action semantics.
- Adding plot, romance, or relationship state.

## Comments


## Comments

- 2026-09-14 agent (pi, 当前会话模型): closed: implemented; guarded by v4 historical ledger I04.
