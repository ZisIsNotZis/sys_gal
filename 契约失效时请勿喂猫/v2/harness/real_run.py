"""First real multi-agent v2 experiment; runs to the seeded world endpoint."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .agent_state import PrivateState
from .character_loader import load_characters
from .natural_agent import make_persistent_agent, make_provider_gm
from .provider import OpenAICompatible
from .runner import Runner
from .seed import create_world
from .system import Ledger
from .trace import Trace
import json
import os
import traceback


def main() -> None:
    root = Path(__file__).parents[1]
    seeds = load_characters(root / "docs/characters")
    world = create_world()
    if set(seeds) != set(world.actors):
        raise RuntimeError(f"seed/character mismatch: {set(world.actors) ^ set(seeds)}")
    states = {actor: PrivateState(actor, goals=(seeds[actor].goals or "pursue ordinary personal interests",))
              for actor in world.actors}
    # The local model normally answers in a few seconds, but a natural-language
    # turn may require a second interpreter call.  Give each call a bounded
    # budget and let the runner's batch deadline cover both calls.
    provider = OpenAICompatible(timeout=30, retries=3, max_retries=3,
                                max_duration=115.0, retry_backoff=1.0,
                                max_backoff=2.0)
    if provider.worst_case_seconds() >= 240.0:
        raise RuntimeError("provider worst-case call can exceed Runner decision_timeout")
    gm = make_provider_gm(provider)
    agents = {actor: make_persistent_agent(seeds[actor], provider, gm) for actor in world.actors}
    trace = Trace("v2", "real-2026-08-25-27")
    ledger = Ledger({
        "Where is the red whistle?": "old neighborhood basement",
        "Who is responsible for the old permit form?": "the person who signed the 2013 neighborhood permit",
        "What deadline is currently recorded?": "the permit review at 2026-03-17T09:00:00+08:00",
    })
    endpoint = datetime.fromisoformat("2026-03-27T21:30:00+08:00")
    output = root / "runs" / "real-2026-08-25-27.json"
    def checkpoint() -> None:
        trace.save(world, output)
    runner = Runner(world, agents, states, trace, ledger,
                    decision_timeout=240.0, checkpoint=checkpoint, fail_fast=True)
    try:
        reason = runner.run(stop_at=endpoint, max_turns=20_000)
    except BaseException as exc:
        trace.fail(reason="aborted_provider_or_runtime_error", world=world, error=exc)
        trace.save(world, output)
        (root / "runs" / "real-2026-08-25-27.error.log").write_text(
            traceback.format_exc(), encoding="utf-8")
        raise
    trace.finish(reason=reason, world=world)
    trace.save(world, output)
    print(f"{output} reason={reason} events={len(world.event_log)} turns={len(trace.agent_turns)} time={world.now.isoformat()}")
    errors = [turn for turn in trace.agent_turns
              if turn["result"] in {"agent_error", "decision_timeout"}]
    if errors:
        raise RuntimeError(f"real experiment had {len(errors)} provider/agent errors; trajectory is invalid")
    if reason != "stop_at_reached":
        raise RuntimeError(f"real experiment stopped before endpoint: {reason}")
    trace.verify_complete(world, endpoint=endpoint.isoformat(), stop_event="world_stops")


if __name__ == "__main__":
    main()
