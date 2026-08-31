"""Cheap preflight run; intentionally no narrative or quality judgement."""

from pathlib import Path

from .agent_state import PrivateState
from .kernel import Intention
from .runner import Runner
from .seed import create_world, load_story_pack
from .system import Ledger
from .trace import Trace, new_run_id, verify_event_log
from .tuning import apply_idle_wait, effective_clock_stop


def main() -> None:
    pack = load_story_pack()
    world = pack.build_world()
    apply_idle_wait(world)
    states = {actor: PrivateState(actor, goals=("continue ordinary life",)) for actor in world.actors}

    def wait_or_bind(state, perception, affordances):
        offered = {str(option.get("kind")) for option in affordances}
        if state.actor_id == "chen-mo" and "system_accept" in offered:
            return Intention(state.actor_id, "system_accept", {"case": "ambiguous-obligations"}, perception["world_version"])
        return Intention(state.actor_id, "wait", {"duration_seconds": 3600}, perception["world_version"])

    ledger = Ledger(pack.system.get("facts", {}), pack.system)
    run_id = new_run_id("preflight")
    trace = Trace("v3", run_id)
    endpoint = effective_clock_stop(world, str(pack.manifest["clock"]["stop"]))
    output = Path(__file__).parents[1] / "runs" / f"{run_id}.json"
    trace.save(world, output)
    Runner(world, {actor: wait_or_bind for actor in world.actors}, states, trace, ledger).run(
        stop_at=endpoint, max_turns=100_000)
    verify_event_log(world.replayable_log())
    trace.verify_complete(world, endpoint=endpoint.isoformat(), stop_event="world_stops")
    trace.finish(reason="seed schedule drained to its objective stop event", world=world)
    trace.save(world, output)
    print(f"{output} events={len(world.event_log)} turns={len(trace.agent_turns)} time={world.now.isoformat()}")


if __name__ == "__main__":
    main()
