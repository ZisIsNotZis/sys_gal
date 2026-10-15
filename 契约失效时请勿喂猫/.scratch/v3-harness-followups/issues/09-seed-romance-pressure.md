# Strengthen romance emergence through the world seed

Status: wontfix
Type: enhancement

The current seed drives document and audit investigation more strongly than romance. Rework only the world/character seed: add credible attraction, incompatible obligations, repeated contact, vulnerability, and consequences that can produce intimacy or separation. Keep the engine story-neutral and do not add affection or hate scores.

## Agent Brief

**Category:** enhancement
**Summary:** Strengthen romance emergence through believable world and character causality.

**Current behavior:**
The current seed produces document and audit investigation, but does not sufficiently force independent characters into repeated meaningful contact with asymmetric attraction, emotional risk, competing obligations, or consequences. Romance therefore has little opportunity to emerge from behavior.

**Desired behavior:**
Revise world and character seed data so relationships can develop, stall, or fail through observable actions, timing, information, vulnerability, misunderstanding, and conflicting goals. Characters remain independent people: none exists to help the protagonist or satisfy a narrative route.

**Acceptance criteria:**

- [ ] At least two characters have concrete, asymmetric interest, uncertainty, or attraction that affects plausible choices without becoming a numeric relationship field.
- [x] Seeded duties, secrets, resources, or risks create repeated contact and meaningful reasons to cooperate or refuse.
- [x] Helping another character can impose a believable cost on the helper.
- [x] Vulnerability, concealment, embarrassment, misunderstanding, and repair are possible through observable events.
- [x] Other characters retain independent goals and continue acting when the protagonist is absent.
- [x] Multiple trajectories can plausibly produce closeness, missed connection, conflict, separation, or unresolved feelings.
- [x] A bounded causal chain is documented in the character seed text and schedule.
- [x] No affection, hate, relationship-score, route, chapter, or romance API is added to the generic harness.

## Evidence

- Added independent accessibility walkthrough/follow-up pressure to the world
  schedule and expanded Lin/Chen and Gao/Qiao seed motivations, costs,
  boundaries, and possible repair or separation.
- `validate_story_pack` and world-pack loader validation pass; all 158 v3
  harness tests pass.
- Deferred: no provider-backed story run was added; this seed change creates
  causal opportunity but does not guarantee a romance outcome.

**Out of scope:**

- Guaranteeing a romance outcome.
- Making every character interested in the protagonist.
- Converting feelings into engine-managed points.
- Rewriting the engine to recognize romance or plot phases.

## Comments


## Comments

- 2026-09-14 agent (pi, 当前会话模型): closed: superseded by V4-DESIGN §4 social economy (desire/fear personas, secrets, gossip pump).
