# Short Scenario Policy Report

The deterministic policy seam is deliberately small and uses no judge.

## Implementation change

`Simulation` now advances only to the next scheduled event (or the requested
run boundary), instead of draining the complete queue. This preserves the
coroutine wake-up cycle: Gao's request is delivered, Chen can choose a partial
disclosure, Lin can respond from that incomplete observation, and Luo's later
reminder can wake Chen.

## Causal chain

1. Chen waits, then receives Gao's request not to submit the outdated form.
2. Chen discloses that request to Lin, but not the complete accounting history.
3. Lin responds from incomplete knowledge and asks for the exact reconciliation.
4. Chen asks Gao what he may disclose; Gao deflects by citing a check with Qiao.
5. Luo's seeded 10:30 reminder is private to Chen, who replies precisely but
   distinguishes the old form from the required corrected attachment.

Other turns wait in fifteen-minute chunks. Existing primitive actions are
enough; no semantic adjudication or scene scripting is introduced.

## Meaningful-run checks

- Chen's choice changes later messages.
- Lin's response is caused by a delivered message, not an opening script.
- Luo's reminder remains private and causes a further response.
- The document, deadline, and concealment pressure remain causally relevant.
- Every consequential transition is reconstructable from the event log.

## Ensemble completion pass

The v1 cast pass expands the episode beyond Chen's paperwork loop. Qiao must
choose between protecting an unlabeled summary and protecting his audit record;
Xu must press for cash-flow clarity without asking for falsification; Amani
refuses symbolic accessibility language and supplies a rain-safe detour only
when ownership is named; He Qian verifies before publishing; Luo enforces the
deadline; Lin keeps review separate from approval; Gao admits the source error;
and the cat remains a non-speaking, non-contractual source of a physical clue.

These are policy motivations and observable actions, not scripted emotional
outcomes. The terminal seed event records the resolution of all nine active
participants. A run is invalid if any one of them receives no turn or no
terminal status.
