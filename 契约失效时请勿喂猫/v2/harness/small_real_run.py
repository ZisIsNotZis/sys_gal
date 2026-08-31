"""One-minute wall-clock integration probe for persistent character sessions."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import time

from .agent_state import PrivateState
from .character_loader import load_characters
from .natural_agent import make_persistent_agent, make_provider_gm
from .provider import OpenAICompatible
from .runner import Runner
from .seed import create_world
from .trace import Trace
from .kernel import Intention


def main() -> None:
    root = Path(__file__).parents[1]
    world = create_world()
    seeds = load_characters(root / "docs/characters")
    states = {actor: PrivateState(actor) for actor in world.actors}
    provider = OpenAICompatible(timeout=3, retries=2, retry_backoff=0.25)
    gm = make_provider_gm(provider)
    # Two real sessions are enough to exercise continuity, natural-language
    # output, JSON retry, and world-result feedback.  Idle actors keep the
    # normal Runner contract without spending provider calls.
    real_actors = {"chen-mo", "lin-yao"}
    agents = {}
    for actor in world.actors:
        if actor in real_actors:
            agents[actor] = make_persistent_agent(seeds[actor], provider, gm)
        else:
            agents[actor] = lambda state, perception, affordances: Intention(
                state.actor_id, "wait", {"duration_seconds": 900}, perception["world_version"])
    trace = Trace("v2", "small-real-2026-08-24-03")
    output = root / "runs" / "small-real-2026-08-24-03.json"
    started = time.monotonic()
    runner = Runner(world, agents, states, trace, decision_timeout=10, checkpoint=lambda: trace.save(world, output), fail_fast=True)
    reason = runner.run(stop_at=world.now + timedelta(hours=3), max_turns=60)
    trace.finish(reason=reason, world=world)
    trace.save(world, output)
    elapsed = time.monotonic() - started
    print(f"{output} reason={reason} turns={len(trace.agent_turns)} events={len(world.event_log)} simulated={world.now.isoformat()} wall_seconds={elapsed:.1f}")


if __name__ == "__main__":
    main()
