"""Run v1 and reject traces that are mechanically busy but narratively empty.

This file is intentionally the evaluation seam.  It does not infer quality
from prose and it does not alter the kernel: a demo passes only when its
authoritative trace proves a voluntary choice, a cost, a caused consequence,
and an earned Ledger reward, while preserving private observations.
"""

from pathlib import Path
import sys
from datetime import datetime

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).parents[1]))

from harness.agents import Simulation
from harness.seed import create_v1_world
from harness.trace import TraceRecorder
from harness.vn import project_vn


def _message_events(events, *, sender=None, target=None):
    return [event for event in events if event.kind == "message_delivered"
            and (sender is None or event.actor == sender)
            and (target is None or event.payload.get("target") == target)]


def _subjective_state_checks(events, recorder: TraceRecorder) -> dict[str, object]:
    """Check only observable proxies for subjective state.

    The kernel does not expose private chain-of-thought or authorial emotions.
    Therefore this deliberately proves less: a character must receive private
    evidence and subsequently make an attributable stance/commitment visible
    in an action.  A future agent can add explicit belief snapshots, but the
    validator must never infer them from prose alone.
    """
    failures: list[str] = []
    messages = _message_events(events)
    # These are evidence -> stance transitions in the current episode.  The
    # message fragments are stable semantic anchors, not an LLM judgement.
    transitions = [
        # Gao's private warning changes Chen's next concrete question.
        ("gao-rui", "chen-mo", "old form", "chen-mo", "exact reconciliation", "lin-yao"),
        # Lin's demand changes Chen's commitment to a written scope.
        ("lin-yao", "chen-mo", "exact reconciliation", "chen-mo", "written scope", "lin-yao"),
        # Chen's bounded disclosure changes Lin's stance; this is deliberately
        # an observable social update, not an inferred feeling.
        ("chen-mo", "lin-yao", "bounded correction", "lin-yao", "review it", "chen-mo"),
    ]
    proved = []
    for sender, target, evidence, actor, stance, response_target in transitions:
        evidence_events = [e for e in messages if e.actor == sender
                           and e.payload.get("target") == target
                           and evidence.lower() in str(e.payload.get("text", "")).lower()]
        response_events = [e for e in messages if e.actor == actor
                           and e.payload.get("target") == response_target
                           and stance.lower() in str(e.payload.get("text", "")).lower()]
        if not evidence_events:
            failures.append(f"subjective state lacks observable evidence for {actor}: {evidence}")
            continue
        if not response_events or response_events[0].time <= evidence_events[0].time:
            failures.append(f"subjective stance has no later attributable action: {actor}/{stance}")
            continue
        proved.append({"actor": actor, "evidence_event": evidence_events[0].id,
                       "stance_event": response_events[0].id})

    # If explicit state snapshots are ever emitted, validate their provenance
    # rather than accepting arbitrary plot-controlled state changes.
    explicit = [e for e in events if e.kind in {"update_belief", "update_relationship", "subjective_state"}]
    belief_updates = [e for e in explicit if e.kind == "update_belief"]
    relationship_updates = [e for e in explicit if e.kind == "update_relationship"]
    if len(belief_updates) < 2:
        failures.append("fewer than two evidence-linked belief updates")
    for event in explicit:
        if not event.payload.get("evidence_event_id"):
            failures.append(f"subjective state event {event.id} has no evidence_event_id")
        elif event.payload["evidence_event_id"] not in {e.id for e in events}:
            failures.append(f"subjective state event {event.id} cites missing evidence")
    if failures:
        raise AssertionError("subjective-state pass failed: " + "; ".join(failures))
    return {
        "observable_transitions": proved,
        "explicit_state_events": len(explicit),
        "belief_updates": len(belief_updates),
        "relationship_updates": len(relationship_updates),
    }


def _vn_scene_sequence(events) -> dict[str, object]:
    """Validate a minimal visual-novel episode structure from event order.

    Scene labels are derived from authoritative facts.  No scene writer or
    judge is allowed to insert a beat merely because it would be dramatic.
    """
    labels: list[tuple[str, int]] = []
    for event in events:
        payload = event.payload
        text = str(payload.get("text", "")).lower()
        if event.kind == "system" and payload.get("case") == "three-way-ambiguity" and payload.get("status") is None:
            label = "setup"
        elif event.kind == "ledger_case_accepted":
            label = "choice"
        elif event.kind == "ledger_cost":
            label = "cost"
        elif event.kind in {"update_belief", "update_relationship"}:
            # A private mental update is a state beat, but never dialogue.
            label = "inner_change"
        elif event.kind == "message_delivered" and "acknowledge" in text:
            label = "confrontation"
        elif event.kind == "message_delivered" and ("exact reconciliation" in text or "written scope" in text):
            label = "disclosure"
        elif event.kind == "world_event" and payload.get("event") == "luo_reminder":
            label = "deadline"
        elif event.kind == "story_beat":
            label = "deadline" if payload.get("phase") in {"deadline", "ending"} else "disclosure"
        elif event.kind == "system" and payload.get("status") == "settled":
            label = "settlement"
        elif event.kind in {"story_terminal", "story_terminal_epilogue"}:
            label = "resolution"
        else:
            continue
        labels.append((label, event.id))

    # The first internal update may occur while Chen is formulating his first
    # disclosure; later updates must still precede the deadline.  Treat this
    # as a partial-order check rather than pretending every mental beat has a
    # single author-scripted slot.
    required = ["setup", "choice", "cost", "disclosure", "deadline", "resolution"]
    positions = {}
    for label, event_id in labels:
        # Settlement is an important consequence, but the story's resolution
        # is the explicit terminal beat.  Keep the last terminal marker rather
        # than mistaking an earlier Ledger settlement for the episode ending.
        if label == "resolution":
            positions[label] = event_id
        else:
            positions.setdefault(label, event_id)
    missing = [label for label in required if label not in positions]
    if missing:
        raise AssertionError("VN scene pass failed: missing beats " + ", ".join(missing))
    out_of_order = [(a, b) for a, b in zip(required, required[1:]) if positions[a] >= positions[b]]
    if out_of_order:
        raise AssertionError("VN scene pass failed: beats out of order " + repr(out_of_order))
    # The projection consumes the same serializable shape used by trace
    # replay; do not hand it mutable kernel Event objects.
    projection = project_vn([{
        "id": event.id, "time": event.time.isoformat(), "kind": event.kind,
        "actor": event.actor, "payload": dict(event.payload),
        "cause": event.cause, "visible_to": sorted(event.visible_to),
        "world_version": event.world_version,
    } for event in events])
    records = [record for scene in projection["scenes"] for record in scene["records"]]
    if not any(record["type"] == "choice" for record in records):
        raise AssertionError("VN scene pass failed: projection has no player choice record")
    if not any(record["type"] == "system" and record.get("status") == "settled" for record in records):
        raise AssertionError("VN scene pass failed: projection has no terminal system record")
    if len(projection["chapters"]) < 10:
        raise AssertionError(f"VN scene pass failed: expected at least 10 chapters, got {len(projection['chapters'])}")
    if projection["dialogue_count"] < 30:
        raise AssertionError("VN scene pass failed: complete arc has too little dialogue")
    return {
        "format": projection["format"],
        "scene_count": len(projection["scenes"]),
        "dialogue_count": projection["dialogue_count"],
        "beats": [{"name": label, "event_id": positions[label]} for label in required],
    }


def validate_meaningful_endpoint(world, recorder: TraceRecorder, *, until: datetime) -> dict[str, object]:
    """Validate the endpoint plus the narrative contract for a complete demo.

    Criteria are deliberately trajectory-derived:

    * choice: Chen makes an explicit, voluntary case decision;
    * cost: the decision has a traceable negative consequence;
    * consequence: a later consequential event cites the decision or its
      immediate action, rather than merely following it in wall-clock time;
    * reward: the Ledger records a bounded reward after a satisfied condition;
    * privacy: every observed event/message was visible to that observer and
      every recorded intention is available from that observer's affordances.

    The current policy run is expected to fail until the story implements the
    Ledger settlement path.  That is useful: this check prevents a future run
    from being reported as meaningful merely because it contains many waits.
    """
    failures: list[str] = []
    actor_ids = set(world.actors)
    turns_by_actor = {actor_id: 0 for actor_id in actor_ids}
    events = list(world.event_log)
    by_id = {event.id: event for event in events}
    delivered = {(e.payload.get("target"), e.payload.get("text"))
                 for e in events if e.kind == "message_delivered"}
    for turn in recorder.agent_trajectory:
        actor = turn["actor"]
        if actor not in actor_ids:
            failures.append(f"unknown actor in trace: {actor}")
            continue
        turns_by_actor[actor] += 1
        for event in turn["perception"].get("events", []):
            authoritative = by_id.get(event["id"])
            if authoritative is None:
                failures.append(f"perception references missing event: {event['id']}")
            elif actor not in authoritative.visible_to:
                failures.append(f"privacy leak: {actor} saw event {event['id']}")
        intention = turn.get("intention")
        if intention:
            if intention["actor"] != actor:
                failures.append(f"intention actor mismatch on turn by {actor}")
            if intention["kind"] not in {"wait", "update_belief", "update_relationship", "declare_resolution"}:
                available = {option["kind"] for option in turn.get("affordances", [])}
                if intention["kind"] == "send_message" and turn["time"][:10] >= "2026-03-27":
                    available.add("send_message")
                if intention["kind"] not in available:
                    failures.append(f"unoffered action: {actor}/{intention['kind']}")
            elif intention["kind"] in {"update_belief", "update_relationship"}:
                # Mental updates are zero-time kernel operations triggered by
                # private evidence; they are intentionally not scene options.
                start_version = turn.get("world_version", -1)
                end_version = turn.get("world_version_after", world.version)
                if not any(event.kind == intention["kind"] and event.actor == actor
                           and start_version < event.world_version <= end_version
                           for event in events):
                    failures.append(f"unproven mental action: {actor}/{intention['kind']}")
        for message in turn["perception"].get("inbox", []):
            if (actor, message.get("text")) not in delivered:
                failures.append(f"unproven inbox message for {actor}")

    if world.now != until:
        failures.append(f"run stopped at {world.now.isoformat()}, expected {until.isoformat()}")
    if world.story_phase != "terminal":
        failures.append(f"story did not reach terminal phase: {world.story_phase}")
    if not world.terminal_reason:
        failures.append("terminal story has no terminal_reason")
    unresolved = [actor for actor in world.major_actors if not world.actor_resolutions.get(actor)]
    if unresolved:
        failures.append(f"major actors unresolved at story end: {unresolved}")
    terminal_events = [e for e in events if e.kind == "story_terminal"]
    if not terminal_events:
        failures.append("authoritative story_terminal event is missing")
    elif terminal_events[-1].payload.get("terminal_reason") != world.terminal_reason:
        failures.append("terminal reason does not match authoritative terminal event")
    if set(turns_by_actor) != actor_ids or any(count == 0 for count in turns_by_actor.values()):
        failures.append(f"not all actors participated: {turns_by_actor}")

    event_kinds = {event.kind for event in world.event_log}
    required_kinds = {"system", "action_started", "action_completed", "message_delivered"}
    missing = required_kinds - event_kinds
    if missing:
        failures.append(f"missing primitive activity: {sorted(missing)}")
    if any(event.time > until for event in world.event_log):
        failures.append("world event occurs after endpoint")
    if any(world.event_log[index].world_version != index + 1 for index in range(len(world.event_log))):
        failures.append("world versions are not contiguous")
    # Narrative checks use only event kinds/payloads and causal IDs.  They do
    # not ask an LLM to grade style or guess an actor's hidden motivation.
    chen_system = [e for e in events if e.kind == "system" and e.actor == "chen-mo"]
    decisions = [e for e in events if e.kind == "ledger_case_accepted" and e.actor == "chen-mo"]
    costs = [e for e in events if e.actor == "chen-mo" and any(
        key in e.payload for key in ("cost", "penalty", "debt", "relationship_cost")
    )]
    # A consequence must be later than the choice and either carry a direct
    # cause or be an observable social/world result.  Mere waiting and the
    # choice's own completion do not count.
    choice_time = min((e.time for e in decisions), default=None)
    caused = [e for e in events if choice_time is not None and e.time > choice_time
              and e.kind in {"message_delivered", "world_event", "system"}
              and (e.cause is not None or e.actor is not None)]
    rewards = [e for e in chen_system if any(key in e.payload for key in ("reward", "reward_granted", "clarification"))]
    if not decisions:
        failures.append("no explicit voluntary Ledger choice")
    if not costs:
        failures.append("choice has no traceable cost/penalty")
    if not caused:
        failures.append("no later consequential event causally linked to Chen's choice/action")
    if not rewards:
        failures.append("no bounded Ledger reward recorded")

    # A reward is not an ending by itself: an accepted/settled case and a
    # verifiable reward disclosure must both be present.  This catches the
    # common failure mode where the runner prints a reward in bootstrap data.
    terminal = [e for e in chen_system if e.payload.get("status") in {"settled", "completed", "accepted"}]
    if not terminal:
        failures.append("Ledger case has no terminal acceptance/settlement event")
    if decisions and not any(e.time >= decisions[0].time for e in rewards):
        failures.append("reward precedes the voluntary choice")

    subjective = _subjective_state_checks(events, recorder)
    scenes = _vn_scene_sequence(events)

    if failures:
        raise AssertionError("narrative pass failed: " + "; ".join(failures))

    return {
        "valid": True,
        "endpoint": until.isoformat(),
        "actors": len(actor_ids),
        "agent_turns": len(recorder.agent_trajectory),
        "turns_by_actor": dict(sorted(turns_by_actor.items())),
        "world_events": len(world.event_log),
        "event_kinds": sorted(event_kinds),
        "story_phase": world.story_phase,
        "terminal_reason": world.terminal_reason,
        "actor_resolutions": dict(sorted(world.actor_resolutions.items())),
        "judge_turns": len(recorder.judge_trajectory),
        "narrative": {
            "choice_events": len(decisions),
            "cost_events": len(costs),
            "caused_consequence_events": len(caused),
            "reward_events": len(rewards),
            "privacy_checked": True,
            "subjective_state": subjective,
            "vn_scene_sequence": scenes,
        },
    }


def main() -> None:
    world = create_v1_world()
    recorder = TraceRecorder("v1", "meaningful-short-run-2026-08-24")
    endpoint = datetime.fromisoformat("2026-03-27T21:30:00+08:00")
    Simulation(world, recorder).run(
        # Leave enough polling turns to reach the case deadline even when
        # every actor is in a long routine wait.  The validator, rather than
        # this budget, decides whether the resulting trace is a demo.
        turns=20000,
        until=endpoint,
    )
    try:
        summary = validate_meaningful_endpoint(
            world, recorder,
            until=endpoint,
        )
        recorder.finish(outcome="valid-complete-demo", reason="Narrative and privacy criteria passed.", time=world.now.isoformat())
    except AssertionError as exc:
        summary = {"valid": False, "error": str(exc), "endpoint": world.now.isoformat()}
        recorder.finish(outcome="invalid-narrative-demo", reason=str(exc), time=world.now.isoformat())
    output = Path(__file__).parents[1] / "runs" / "meaningful-short-run-2026-08-24.json"
    recorder.save(world, output)
    print(f"{output} {summary}")
    if not summary["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
