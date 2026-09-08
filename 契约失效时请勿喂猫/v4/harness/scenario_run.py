"""Scenario integration runs from checkpoint snapshots near change boundaries.

Each scenario starts several game-hours before a named "interesting boundary"
(a scheduled world event that changes objective state), takes a world/runner
snapshot, restores from it through the checkpoint path, then runs forward a
few game-hours with a scenario policy. The saved trajectory is meant for
manual review per AGENTS.md run-analysis rules.

Named boundaries come from the seed schedule:
  permit_review           2026-03-17 09:00  + permit-review-outcome at archive
  old_basement_opens      2026-03-18 10:00  + old-basement opens
  bank_call               2026-03-19 10:00  + bank-resolution at market
  storm_records_available 2026-03-20 15:00  + harbor-archive opens, storm-records
  review_meeting          2026-03-21 10:00  + notice to lin/gao/chen
  rain_warning            2026-03-24 16:00  + notice
  fair_opens              2026-03-26 08:00  + notice

Usage:
  python3 -m harness.scenario_run --anchors storm_records_available --hours 6
  python3 -m harness.scenario_run --anchors all --hours 6 --policy active --prelude lean
"""

from __future__ import annotations

import argparse
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from .agent_state import PrivateState
from .checkpoint import save_checkpoint
from .kernel import Intention, World
from .runner import Runner
from .seed import load_story_pack
from .system import Ledger
from .trace import Trace, new_run_id
from .tuning import apply_idle_wait, clock_stop

ANCHORS: dict[str, str] = {
    "permit_review": "2026-03-17T09:00:00+08:00",
    "old_basement_opens": "2026-03-18T10:00:00+08:00",
    "bank_call": "2026-03-19T10:00:00+08:00",
    "storm_records_available": "2026-03-20T15:00:00+08:00",
    "review_meeting": "2026-03-21T10:00:00+08:00",
    "rain_warning": "2026-03-24T16:00:00+08:00",
    "fair_opens": "2026-03-26T08:00:00+08:00",
}


def resolve_anchor(name_or_iso: str, pack: Any) -> datetime:
    if name_or_iso in ANCHORS:
        return datetime.fromisoformat(ANCHORS[name_or_iso])
    return datetime.fromisoformat(name_or_iso)


def _route(world: World, start: str, goal: str) -> list[str]:
    """Shortest hop list from start to goal through the seeded route graph."""
    if start == goal:
        return []
    adjacency: dict[str, list[str]] = {}
    for (source, target) in world.routes:
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, []).append(source)
    parent = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        for nxt in adjacency.get(current, ()):
            if nxt not in parent:
                parent[nxt] = current
                queue.append(nxt)
    if goal not in parent:
        return []
    hops: list[str] = []
    node = goal
    while parent[node] is not None:
        hops.append(node)
        node = parent[node]
    return list(reversed(hops))


def lean_agent(state, perception, affordances):
    offered = {str(option.get("kind")) for option in affordances}
    if state.actor_id == "chen-mo" and "system_accept" in offered:
        return Intention(state.actor_id, "system_accept",
                         {"case": "ambiguous-obligations"}, perception["world_version"])
    return Intention(state.actor_id, "wait", {"duration_seconds": 900},
                     perception["world_version"])


def make_active_agent(world: World):
    """Deterministic reactor: notices a boundary announcement, routes there,
    reads/takes the newly available content, then tells a known contact.

    This is scenario-layer policy (like ``mock_run``), not engine behavior.
    It exists so reviewable trajectories show whether characters can actually
    reach and act on a world change.
    """
    plans: dict[str, dict[str, Any]] = {
        "chen-mo": {
            "permit_review": {"goal": "archive", "doc": "permit-review-outcome",
                              "tell": "lin-yao"},
            "old_basement_opens": {"goal": "old-basement", "doc": "blue-rabbit-register",
                                    "tell": "lin-yao"},
            "storm_records_available": {"goal": "harbor-archive", "doc": "storm-records",
                                         "tell": "lin-yao"},
            "review_meeting": {"goal": "lecture-hall", "tell": "lin-yao"},
            "rain_warning": {"goal": "@here", "doc": "old-permit-form", "tell": "lin-yao"},
        },
        "lin-yao": {
            "storm_records_available": {"goal": "harbor-archive", "doc": "storm-records",
                                         "tell": "chen-mo"},
            "review_meeting": {"goal": "lecture-hall", "tell": None},
        },
        "gao-rui": {
            "review_meeting": {"goal": "lecture-hall", "tell": None},
        },
        "xu-meiling": {
            "bank_call": {"goal": "market", "doc": "bank-resolution", "tell": "he-qian"},
        },
    }
    ctx = {actor: {"plan": None, "hops": [], "read": set(), "sent": set()}
           for actor in world.actors}

    def agent(state, perception, affordances):
        actor = state.actor_id
        context = ctx[actor]
        location = perception["location"]
        for event in perception.get("events", []):
            if event["kind"] != "world_event":
                continue
            event_name = event["payload"].get("event")
            plan = plans.get(actor, {}).get(event_name)
            if plan and context["plan"] is None:
                goal = location if plan.get("goal") == "@here" else plan["goal"]
                context["plan"] = dict(plan)
                context["plan"]["goal"] = goal
                context["plan"]["event"] = event_name
                context["hops"] = _route(world, location, goal)
        if context["plan"] is not None:
            goal = context["plan"]["goal"]
            if location != goal:
                if not context["hops"]:
                    context["hops"] = _route(world, location, goal)
                if context["hops"]:
                    hop = context["hops"][0]
                    duration = world.routes.get((location, hop))
                    if duration is not None:
                        context["hops"] = context["hops"][1:]
                        return Intention(actor, "move", {"target": hop,
                                                         "duration_seconds": duration},
                                         perception["world_version"])
                context["plan"] = None
            else:
                document = context["plan"].get("doc")
                if document and document not in context["read"]:
                    context["read"].add(document)
                    return Intention(actor, "read", {"document": document},
                                     perception["world_version"])
                tell = context["plan"].get("tell")
                if tell and actor not in context["sent"]:
                    context["sent"].add(actor)
                    event_name = context["plan"].get("event", "the announcement")
                    text = (f"I followed up on the {event_name} announcement at {goal} and "
                            f"checked the new material. It changes what we know; we should talk.")
                    return Intention(actor, "send_message", {"target": tell, "text": text},
                                     perception["world_version"])
                context["plan"] = None
        return Intention(actor, "wait", {"duration_seconds": 900},
                         perception["world_version"])

    return agent


def run_scenario(*, anchor: str, hours: int, policy: str = "active",
                 prelude: str = "none", gap_minutes: int = 30,
                 runs_dir: Path | None = None) -> dict[str, Any]:
    pack = load_story_pack()
    base_world = pack.build_world()
    apply_idle_wait(base_world)
    ledger = Ledger(pack.system.get("facts", {}), pack.system)
    anchor_time = resolve_anchor(anchor, pack)
    gap = timedelta(minutes=gap_minutes)
    anchor_gap = anchor_time - gap
    clock_stop_time = clock_stop(str(pack.manifest["clock"]["stop"]))
    if anchor_gap < base_world.now:
        anchor_gap = base_world.now
    runs_dir = Path(runs_dir) if runs_dir else Path(__file__).parents[1] / "runs"

    run_id = new_run_id(f"scenario-{anchor}-{policy}")
    checkpoint_path = runs_dir / f"{run_id}.checkpoint.json"
    trajectory_path = runs_dir / f"{run_id}.json"

    # 1) Prelude: world (and optionally a lean runner) up to anchor - gap.
    world = base_world
    states = {actor: PrivateState(actor) for actor in world.actors}
    trace = Trace("v3", run_id)
    if prelude == "lean":
        runner = Runner(world, {actor: lean_agent for actor in world.actors}, states,
                        trace, ledger, max_workers=len(world.actors))
        runner.run(stop_at=anchor_gap, max_turns=200_000)
    else:
        world.advance(until=anchor_gap)
        runner = Runner(world, {actor: lean_agent for actor in world.actors}, states,
                        trace, ledger, max_workers=len(world.actors))
    snapshot = trace.checkpoint_snapshot(world, runner)
    save_checkpoint(checkpoint_path, snapshot)

    # 2) Restore the snapshot into a fresh world/runner/trace and continue.
    restored = World.from_checkpoint(base_world, snapshot["world"])
    restored_states = {actor: PrivateState.from_snapshot(snapshot["states"][actor])
                       for actor in restored.actors}
    scenario_trace = Trace("v3", run_id)
    scenario_trace.sessions = deepcopy(snapshot["sessions"])
    if policy == "active":
        agents = {actor: make_active_agent(restored) for actor in restored.actors}
    else:
        agents = {actor: lean_agent for actor in restored.actors}
    scenario_runner = Runner(restored, agents, restored_states, scenario_trace, ledger,
                             max_workers=len(restored.actors))
    scenario_runner.restore_checkpoint(snapshot["runner"])
    stop = min(anchor_time + timedelta(hours=hours), clock_stop_time)
    reason = scenario_runner.run(stop_at=stop, max_turns=200_000)
    scenario_trace.finish(reason=reason, world=restored)
    scenario_trace.save(restored, trajectory_path)

    return _summarize(restored, scenario_trace, snapshot, anchor, hours, policy,
                      prelude, run_id, checkpoint_path, trajectory_path, reason, stop)


def _summarize(world, trace, snapshot, anchor, hours, policy, prelude,
               run_id, checkpoint_path, trajectory_path, reason, stop) -> dict[str, Any]:
    events = [event for event in world.event_log
              if event.kind == "world_event" and event.payload.get("event") == anchor]
    fired = bool(events)
    anchor_event = events[-1] if events else None
    documents_read = sorted({str(event.payload.get("document"))
                             for event in world.event_log
                             if event.kind == "document_read"})
    arrivals = {}
    for actor in world.actors:
        arrived = [event.payload.get("target")
                   for event in world.event_log
                   if event.kind == "action_completed" and event.actor == actor
                   and event.payload.get("action") == "move"]
        arrivals[actor] = sorted(set(arrived))
    messages = [event for event in world.event_log if event.kind == "message_delivered"]
    summary = {
        "run_id": run_id, "anchor": anchor, "anchor_time": ANCHORS.get(anchor, anchor),
        "hours": hours, "policy": policy, "prelude": prelude,
        "snapshot_at": snapshot["world"]["now"], "stop": stop.isoformat(),
        "reason": reason, "world_now": world.now.isoformat(),
        "events": len(world.event_log), "agent_turns": len(trace.agent_turns),
        "boundary_fired": fired,
        "boundary_effects": list(anchor_event.payload.get("effects", ())) if anchor_event else [],
        "documents_read_during_scenario": documents_read,
        "actors_locations_visited": arrivals,
        "messages_delivered": len(messages),
        "checkpoint": str(checkpoint_path), "trajectory": str(trajectory_path),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors", default="storm_records_available",
                        help="comma-separated named anchors or 'all'")
    parser.add_argument("--hours", type=int, default=6)
    parser.add_argument("--policy", choices=("active", "lean"), default="active")
    parser.add_argument("--prelude", choices=("none", "lean"), default="lean",
                        help="lean=agents live through the prelude (live boundary reactions); "
                             "none=world advances with no agents (retroactive catch-up)")
    parser.add_argument("--gap-minutes", type=int, default=30)
    args = parser.parse_args()
    if args.anchors == "all":
        anchors = list(ANCHORS)
    else:
        anchors = [name.strip() for name in args.anchors.split(",") if name.strip()]
    for anchor in anchors:
        summary = run_scenario(anchor=anchor, hours=args.hours, policy=args.policy,
                               prelude=args.prelude, gap_minutes=args.gap_minutes)
        line = (f"{summary['run_id']} anchor={summary['anchor']}@{summary['anchor_time']} "
                f"reason={summary['reason']} world_now={summary['world_now']} "
                f"events={summary['events']} turns={summary['agent_turns']} "
                f"boundary_fired={summary['boundary_fired']} "
                f"docs_read={summary['documents_read_during_scenario']} "
                f"msgs={summary['messages_delivered']}")
        print(line)


if __name__ == "__main__":
    main()
