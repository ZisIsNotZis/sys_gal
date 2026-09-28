Status: claimed
Issue: 3/22 scheduled notices pre-narrate named characters' unperformed actions, and the milestone SSOT has stale calendar/run claims.
Objective: Make the v4 memorial-day notices describe plans and actionable cues rather than completed character actions; preserve the existing day-level route-network anchors and physically plausible 中庭-to-河堤 path. Correct only stale V4-STORY-MILESTONES facts needed to accurately prepare the next run.
Acceptance criteria:
- The 3/22 memorial notices do not state that named characters arrived, handled objects, recognized evidence, hosted, spoke, or walked unless a corresponding action occurs.
- The ceremony cue requires participants to be physically present for their own actions; do not add presence-gating engine behavior unless the current architecture supports it.
- The river cue reflects the existing direct 中庭-to-河堤 route and its travel time; do not weaken story-route anchors.
- A regression test prevents the known notice anti-pattern from returning.
- The milestone document has correct weekdays, clearly distinguishes world_stops from story acceptance, and states the route-network and prior-run facts accurately.
- Full v4 unit suite, seed lint, safe deterministic dry run, and git diff --check pass; no provider simulation is run.
Blockers: None.
Need-review: yes.
Need-test-cases: yes.

## Comments
- 2026-09-28 pi: Confirmed scheduled world_event targets are delivery scopes, not location/presence predicates; use a seed-only agenda/invitation design, keep co-location and actor action under agent control. Historical 2026-09-20 artifact reached 2026-03-27 21:30, while runs/day10-12.log records 195 agent errors as lost turns; do not call that full-arc acceptance.
- 2026-09-28 pi: Rechecked the preserved D1 artifact against the current 12-item checker: 11 items pass, the note-read flavor fails, and both story routes/required anchors pass. Updated the SSOT so the prior 10/10 report is not represented as current.
- 2026-09-28 pi: Added memorial-notice regression coverage; full unittest suite passed (318 run, 1 skipped), seed lint passed, and deterministic `harness.dry_run` reached 3/27 21:30. No provider simulation was run. Independent review remains required.
