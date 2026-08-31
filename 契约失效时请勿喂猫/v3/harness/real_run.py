"""Real multi-agent v3 experiment; runs to the data-defined world endpoint."""

from __future__ import annotations

from pathlib import Path
import os

from .agent_state import PrivateState
from .character_loader import load_story_characters
from .checkpoint import save_checkpoint
from .natural_agent import make_persistent_agent, make_provider_gm
from .provider import OpenAICompatible, provider_from_env
from .runner import Runner
from .seed import create_world, load_story_pack
from .system import Ledger
from .trace import Trace, new_run_id
from .tuning import apply_idle_wait, effective_clock_stop
import traceback


def main() -> None:
    root = Path(__file__).parents[1]
    pack = load_story_pack()
    seeds = load_story_characters(root / "world")
    world = pack.build_world()
    apply_idle_wait(world)
    if set(seeds) != set(world.actors):
        raise RuntimeError(f"seed/character mismatch: {set(world.actors) ^ set(seeds)}")
    states = {actor: PrivateState(actor, goals=(seeds[actor].goals or "pursue ordinary personal interests",))
              for actor in world.actors}
    # A turn may need compaction, format retries, and a GM interpretation.
    provider = provider_from_env(
        max_concurrency=min(len(world.actors), int(os.environ.get("V3_PROVIDER_CONCURRENCY", "8"))))
    # Include five possible compaction/character calls and two GM calls.
    decision_timeout = provider.worst_case_seconds() * 8 + 5.0
    if decision_timeout <= provider.worst_case_seconds() * 8:
        raise RuntimeError("provider decision budget is not bounded")
    gm = make_provider_gm(provider)
    agents = {actor: make_persistent_agent(seeds[actor], provider, gm) for actor in world.actors}
    run_id = new_run_id("real")
    trace = Trace("v3", run_id)
    ledger = Ledger(pack.system.get("facts", {}), pack.system)
    endpoint = effective_clock_stop(world, str(pack.manifest["clock"]["stop"]))
    output = root / "runs" / f"{run_id}.json"
    checkpoint_output = root / "runs" / f"{run_id}.checkpoint.json"
    holder: dict = {}

    def checkpoint() -> None:
        # The trajectory is for inspection; the v3-checkpoint file is the
        # resume point (world + runner + states + sessions + trace). Every
        # batch writes it, so "fix the code, then resume" can restart from
        # the last good checkpoint instead of redoing the run.
        trace.save(world, output)
        runner = holder.get("runner")
        if runner is not None:
            save_checkpoint(checkpoint_output,
                            trace.checkpoint_snapshot(world, runner))
    checkpoint()
    runner = Runner(world, agents, states, trace, ledger,
                    decision_timeout=decision_timeout,
                    max_transient_failures=int(os.environ.get("V3_MAX_TRANSIENT_FAILURES", "3")),
                    retry_delay_seconds=300,
                    max_wall_seconds=float(os.environ.get("V3_MAX_WALL_SECONDS", "7200")),
                    checkpoint=checkpoint, fail_fast=True)
    holder["runner"] = runner
    try:
        reason = runner.run(stop_at=endpoint, max_turns=20_000)
    except BaseException as exc:
        trace.fail(reason="aborted_provider_or_runtime_error", world=world, error=exc)
        trace.save(world, output)
        output.with_suffix(".error.log").write_text(
            traceback.format_exc(), encoding="utf-8")
        raise
    try:
        trace.verify_no_agent_errors()
        if reason != "stop_at_reached":
            raise RuntimeError(f"real experiment stopped before endpoint: {reason}")
        trace.verify_complete(world, endpoint=endpoint.isoformat(), stop_event="world_stops")
    except BaseException as exc:
        # Reaching the clock endpoint is not a healthy run if any character
        # failed. Persist a failed outcome instead of mislabeling the trace.
        trace.fail(reason="completion_validation_failed", world=world, error=exc)
        trace.save(world, output)
        raise
    trace.finish(reason=reason, world=world)
    trace.save(world, output)
    print(f"{output} reason={reason} events={len(world.event_log)} turns={len(trace.agent_turns)} time={world.now.isoformat()}")


if __name__ == "__main__":
    main()
