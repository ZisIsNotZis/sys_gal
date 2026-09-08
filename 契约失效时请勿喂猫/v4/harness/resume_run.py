"""Resume a real run from its last fine checkpoint.

Methodology: wherever a problem starts, fix the related code/file, then
restart from the last good checkpoint instead of redoing the whole run. The
checkpoint preserves the world, runner state, per-actor private state, and the
full session transcripts — so conversation history survives the restart (the
code that runs it may have been fixed). Only a large goal-level change that
makes prior history meaningless should justify starting fresh.

The resumed run continues causally from the checkpoint: event ids and world
versions stay contiguous, and the saved artifact contains the whole history
(prior events + new turns). It is written to a new, unique file so no
trajectory is overwritten (see AGENTS.md).

Usage:
  python3 -m harness.resume_run runs/<checkpoint>.json [--clock-stop ISO] [--out PATH]
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .agent_state import PrivateState
from .character_loader import load_story_characters
from .character_session import CharacterSession
from .checkpoint import load_checkpoint, save_checkpoint
from .kernel import World
from .natural_agent import make_persistent_agent, make_provider_gm
from .npc_agent import make_npc_agent, public_mc_digest, schedule_digest
from .provider import provider_from_env
from .world_loader import world_primer
from .engine import AsyncEngine
from .seed import load_story_pack
from .system import Ledger
from .trace import Trace, new_run_id
from .tuning import apply_idle_wait, clock_stop


def resume(checkpoint_path: Path, *, out: Path | None = None,
           endpoint: str | None = None, call=None) -> Path:
    root = Path(__file__).parents[1]
    pack = load_story_pack()
    seeds = load_story_characters(root / "world")
    cp = load_checkpoint(checkpoint_path)

    # 1) Restore the world from the checkpoint; the pristine pack supplies the
    #    static definitions (routes, capabilities, schedules) and the
    #    checkpoint supplies every piece of mutable state.
    base_world = pack.build_world()
    world = World.from_checkpoint(base_world, cp["world"])
    apply_idle_wait(world)

    # 2) Provider, GM, and agents. Sessions are restored from the checkpoint so
    #    each character's conversation history is preserved across the restart;
    #    only the code that runs it may have changed. ``call`` is a test hook
    #    for a mock model; production uses the env-tuned resilient provider.
    if call is None:
        provider = provider_from_env(
            max_concurrency=min(len(world.actors),
                                int(os.environ.get("V3_PROVIDER_CONCURRENCY", "8"))))
        gm = make_provider_gm(provider)
    else:
        provider = call
        gm = None
    states = {actor: PrivateState.from_snapshot(cp["states"][actor])
              for actor in world.actors}
    # 两层演员制：MC 恢复持久会话；NPC 恢复滚动记忆并走导演简报；extras
    # 由引擎管理，不配 agent（V4-CAST §1）。
    primer = world_primer(pack)
    schedule_text = schedule_digest(pack.scheduled, now=world.now)
    npc_director_notes = pack.manifest.get("npc_director_notes", {})

    def npc_context(actor_id: str, _perception) -> dict[str, str]:
        return {"mc_digest": public_mc_digest(world),
                "schedule_text": schedule_text,
                "beat_goal": str(npc_director_notes.get("beat_goals", {}).get(actor_id, ""))}

    agents = {}
    for actor in world.actors:
        role = world.actors[actor].role
        session_snapshot = cp.get("sessions", {}).get(actor)
        if role == "npc":
            agents[actor] = make_npc_agent(seeds[actor], provider, npc_context,
                                           director_notes=str(npc_director_notes.get(actor, "")),
                                           session=session_snapshot or {})
        elif role == "extra":
            continue
        else:
            session = (CharacterSession.from_snapshot(session_snapshot, seeds[actor], provider,
                                                      state=states[actor], world_primer=primer)
                       if session_snapshot else None)
            agents[actor] = make_persistent_agent(seeds[actor], provider, gm, session=session,
                                                  world_primer=primer)

    # 3) Trace carries the earlier history so the saved artifact is contiguous.
    run_id = new_run_id("resumed")
    trace = Trace("v3", run_id)
    trace.restore_from_snapshot(cp["trace"])
    out_path = (out or root / "runs" / f"{run_id}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_output = out_path.with_name(out_path.stem + ".checkpoint.json")
    holder: dict = {}

    def checkpoint() -> None:
        # The trajectory is for inspection; the checkpoint file is the next
        # resume point, so a multi-cycle grind (run -> resume -> resume ...)
        # stays resumable instead of redoing the segment.
        trace.save(world, out_path)
        runner = holder.get("runner")
        if runner is not None:
            save_checkpoint(checkpoint_output,
                            trace.checkpoint_snapshot(world, runner))

    # 4) Endpoint: explicit --clock-stop, else V3_CLOCK_STOP env, else seed stop.
    #    Ensure a world_stops marker at that time so the completion gate holds.
    chosen = endpoint if endpoint is not None else str(pack.manifest["clock"]["stop"])
    stop_time = clock_stop(chosen)
    marker_exists = any(job.kind == "world_event"
                        and job.payload.get("event") == "world_stops"
                        and job.time == stop_time
                        for job in world._queue)
    if not marker_exists:
        world._schedule(stop_time, "world_event", None,
                        {"event": "world_stops", "notice": "The resumed arc ends here."}, None)

    # 5) Runner restored from the checkpoint and continued to the endpoint.
    ledger = Ledger(pack.system.get("facts", {}), pack.system)
    decision_timeout = (provider.worst_case_seconds() * 8 + 5.0
                        if hasattr(provider, "worst_case_seconds") else 60.0)
    runner = AsyncEngine(world, agents, states, trace, ledger,
                         decision_timeout=decision_timeout,
                         max_transient_failures=int(
                             os.environ.get("V3_MAX_TRANSIENT_FAILURES", "3")),
                         max_wall_seconds=float(
                             os.environ.get("V3_MAX_WALL_SECONDS", "7200")),
                         mc_idle_heartbeat=int(os.environ.get("V4_MC_IDLE_HEARTBEAT", "1800")),
                         checkpoint=checkpoint,
                         extra_call=provider)
    runner.restore_checkpoint(cp["runner"])
    holder["runner"] = runner
    trace.save(world, out_path)  # checkpoint at resume start
    resume_start = len(trace.agent_turns)
    reason = runner.run(stop_at=stop_time, max_turns=100_000)
    # Only the resumed segment may fail the run; the carried-over history may
    # legitimately end in a wall-clock error (that is why we resumed).
    # 与 real_run 的完成门一致（V4）：agent_error/decision_timeout 是"丢一回合
    # 并已获纠正反馈"，不否决整段；engine_error 是代码级故障，仍然致命。
    lost_turns = [turn for turn in trace.agent_turns[resume_start:]
                  if turn.get("result") in {"agent_error", "decision_timeout",
                                            "wall_clock_deadline"}]
    fatal = [turn for turn in trace.agent_turns[resume_start:]
             if turn.get("result") == "engine_error"]
    if lost_turns:
        print(f"note: {len(lost_turns)} lost turns in resumed segment")
    if fatal:
        raise RuntimeError(f"resumed segment contained {len(fatal)} engine errors")
    if reason != "stop_at_reached":
        raise RuntimeError(f"resumed run stopped before endpoint: {reason}")
    trace.verify_complete(world, endpoint=stop_time.isoformat(), stop_event="world_stops",
                          from_turn=resume_start, allow_lost_turns=True)
    trace.finish(reason=reason, world=world)
    trace.save(world, out_path)
    print(f"{out_path} reason={reason} events={len(world.event_log)} "
          f"turns={len(trace.agent_turns)} time={world.now.isoformat()}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--clock-stop", help="override the seeded endpoint (ISO)")
    parser.add_argument("--out", type=Path, help="output trajectory path")
    args = parser.parse_args()
    resume(args.checkpoint, out=args.out, endpoint=args.clock_stop)


if __name__ == "__main__":
    main()
