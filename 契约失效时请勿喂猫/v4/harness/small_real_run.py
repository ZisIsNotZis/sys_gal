"""One-minute wall-clock integration probe for persistent character sessions."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import time
import os

from .agent_state import PrivateState
from .character_loader import load_story_characters
from .natural_agent import make_persistent_agent, make_provider_gm
from .provider import OpenAICompatible
from .runner import Runner
from .seed import load_story_pack
from .trace import Trace, new_run_id
from .kernel import Intention


def main() -> None:
    root = Path(__file__).parents[1]
    pack = load_story_pack()
    world = pack.build_world()
    from .tuning import apply_idle_wait
    apply_idle_wait(world)
    seeds = load_story_characters(root / "world")
    states = {actor: PrivateState(actor) for actor in world.actors}
    # The configured local service currently answers in roughly two seconds;
    # a two-second socket deadline would classify normal responses as outages.
    # Bound each request, but leave scheduling margin and one retry for a
    # transient local queue delay.
    provider = OpenAICompatible(timeout=15, retries=3, retry_backoff=1.0,
                                max_retries=3, max_duration=60.0,
                                max_concurrency=min(len(world.actors), int(
                                    os.environ.get("V3_PROVIDER_CONCURRENCY", "4"))))
    gm = make_provider_gm(provider)
    # A bounded probe must exercise every provider-backed character session;
    # a two-actor smoke test cannot reveal fan-out, per-session isolation, or
    # one actor's malformed output poisoning another actor's run.
    configured_actors = os.environ.get("V3_PROBE_ACTORS", "all")
    real_actors = (set(world.actors) if configured_actors == "all"
                   else {actor.strip() for actor in configured_actors.split(",") if actor.strip()})
    if real_actors != set(world.actors):
        raise RuntimeError("provider readiness probe requires every world actor")
    agents = {}
    for actor in world.actors:
        if actor in real_actors:
            agents[actor] = make_persistent_agent(seeds[actor], provider, gm)
        else:
            agents[actor] = lambda state, perception, affordances: Intention(
                state.actor_id, "wait", {"duration_seconds": 900}, perception["world_version"])
    run_id = new_run_id("small-real")
    trace = Trace("v3", run_id)
    output = root / "runs" / f"{run_id}.json"
    started = time.monotonic()
    # Include five possible compaction/character calls and two GM calls.
    decision_timeout = provider.worst_case_seconds() * 8 + 5.0
    runner = Runner(world, agents, states, trace, decision_timeout=decision_timeout,
                    max_transient_failures=int(os.environ.get("V3_MAX_TRANSIENT_FAILURES", "3")),
                    retry_delay_seconds=300,
                    max_wall_seconds=float(os.environ.get("V3_MAX_WALL_SECONDS", "300")),
                    checkpoint=lambda: trace.save(world, output), fail_fast=True)
    trace.save(world, output)
    try:
        probe_hours = float(os.environ.get("V3_PROBE_HOURS", "3"))
        if probe_hours <= 0:
            raise ValueError("V3_PROBE_HOURS must be positive")
        reason = runner.run(stop_at=world.now + timedelta(hours=probe_hours), max_turns=2000)
        trace.verify_no_agent_errors()
        if reason != "stop_at_reached":
            raise RuntimeError(f"probe stopped before endpoint: {reason}")
    except BaseException as exc:
        trace.fail(reason="probe_validation_failed", world=world, error=exc)
        trace.save(world, output)
        raise
    trace.finish(reason=reason, world=world)
    trace.save(world, output)
    elapsed = time.monotonic() - started
    print(f"{output} reason={reason} turns={len(trace.agent_turns)} events={len(world.event_log)} simulated={world.now.isoformat()} wall_seconds={elapsed:.1f}")


if __name__ == "__main__":
    main()
