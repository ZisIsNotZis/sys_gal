"""Cheap preflight run; intentionally no narrative or quality judgement."""

from datetime import datetime
from pathlib import Path

from .agent_state import PrivateState
from .kernel import Intention
from .runner import Runner
from .seed import create_world
from .system import Ledger
from .trace import Trace, verify_event_log


def main() -> None:
    world = create_world()
    states = {actor: PrivateState(actor, goals=("continue ordinary life",)) for actor in world.actors}

    def wait_or_bind(state, perception, affordances):
        if state.actor_id == "chen-mo" and not any(e["kind"] == "system_case_accepted" for e in perception["events"]):
            return Intention(state.actor_id, "system_accept", {"case": "ambiguous-obligations"}, perception["world_version"])
        return Intention(state.actor_id, "wait", {"duration_seconds": 300}, perception["world_version"])

    ledger = Ledger({"Where is the red whistle?": "old neighborhood basement"})
    trace = Trace("v2", "preflight-2026-08-24")
    endpoint = datetime.fromisoformat("2026-03-27T21:30:00+08:00")
    Runner(world, {actor: wait_or_bind for actor in world.actors}, states, trace, ledger).run(
        stop_at=endpoint, max_turns=100_000)
    verify_event_log(world.replayable_log())
    trace.finish(reason="seed schedule drained to its objective stop event", world=world)
    output = Path(__file__).parents[1] / "runs" / "preflight-2026-08-24.json"
    trace.save(world, output)
    print(f"{output} events={len(world.event_log)} turns={len(trace.agent_turns)} time={world.now.isoformat()}")


if __name__ == "__main__":
    main()
