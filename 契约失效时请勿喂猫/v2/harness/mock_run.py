"""Cheap, deterministic integration trajectory with independent character policies."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .agent_state import PrivateState
from .character_loader import load_characters
from .kernel import Intention
from .runner import Runner
from .seed import create_world
from .system import Ledger
from .trace import Trace, verify_event_log


def main() -> None:
    root = Path(__file__).parents[1]
    seeds = load_characters(root / "docs/characters")
    world = create_world()
    states = {actor: PrivateState(actor, goals=(f"pursue {actor}'s ordinary interests",))
              for actor in world.actors}
    sent = set()
    # Each policy owns its own flags; they are not shared character memory.
    sent_by_actor = {actor: set() for actor in world.actors}

    def agent(state, perception, affordances):
        actor = state.actor_id
        version = perception["world_version"]
        own_sent = sent_by_actor[actor]
        if actor == "chen-mo" and "chen-lin" not in own_sent:
            sent.add("chen-lin")
            own_sent.add("chen-lin")
            return (Intention(actor, "send_message", {"target": "lin-yao",
                     "text": "I found the old permit form. I will bring it to the archive, but I cannot promise it proves anything."}, version),
                    {"memories": [{"kind": "decision", "text": "stated a limit to Lin"}]})
        if actor == "lin-yao" and perception["inbox"] and "lin-chen" not in own_sent:
            sent.add("lin-chen")
            own_sent.add("lin-chen")
            return Intention(actor, "send_message", {"target": "chen-mo",
                           "text": "Bring the form. Do not call it proof until I have checked its source."}, version)
        if actor == "gao-rui" and "gao-qiao" not in own_sent:
            sent.add("gao-qiao")
            own_sent.add("gao-qiao")
            return Intention(actor, "send_message", {"target": "qiao-shun",
                           "text": "The audit labels are incomplete. I made the mistake; please review the numbers with me."}, version)
        if actor == "qiao-shun" and perception["inbox"] and "qiao-gao" not in own_sent:
            sent.add("qiao-gao")
            own_sent.add("qiao-gao")
            return Intention(actor, "send_message", {"target": "gao-rui",
                           "text": "Send me the unlabeled rows. I will review them, but I will not rewrite the record for you."}, version)
        if actor == "chen-mo":
            # The case is deliberately a separate System decision, not a world action.
            if not any(e["kind"] == "system_case_accepted" for e in perception["events"]):
                return Intention(actor, "system_accept", {"case": "ambiguous-obligations"}, version)
        return None

    trace = Trace("v2", "mock-independent-2026-08-24")
    ledger = Ledger({"Where is the red whistle?": "old neighborhood basement"})
    endpoint = datetime.fromisoformat("2026-03-27T21:30:00+08:00")
    runner = Runner(world, {actor: agent for actor in world.actors}, states, trace, ledger)
    reason = runner.run(
        stop_at=endpoint, max_turns=100_000)
    if reason != "stop_at_reached":
        raise RuntimeError(f"mock run did not reach the seeded endpoint: {reason}")
    trace.verify_complete(world, endpoint=endpoint.isoformat(), stop_event="world_stops")
    trace.finish(reason="seed-defined world stop", world=world)
    output = root / "runs" / "mock-independent-2026-08-24.json"
    trace.save(world, output)
    print(f"{output} events={len(world.event_log)} turns={len(trace.agent_turns)} time={world.now.isoformat()}")


if __name__ == "__main__":
    main()
