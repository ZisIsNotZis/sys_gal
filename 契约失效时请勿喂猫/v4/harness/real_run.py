"""Real multi-agent v3 experiment; runs to the data-defined world endpoint."""

from __future__ import annotations

from pathlib import Path
import heapq
import os

from .agent_state import PrivateState
from .character_loader import load_story_characters
from .checkpoint import save_checkpoint
from .natural_agent import make_persistent_agent_v4
from .npc_agent import make_npc_agent_v4, public_mc_digest, schedule_digest
from .provider import OpenAICompatible, provider_from_env
from .engine import AsyncEngine
from .seed import create_world, load_story_pack
from .system import Ledger
from .trace import Trace, new_run_id
from datetime import datetime
from .tuning import apply_idle_wait, clock_stop, env_float, env_int
from .world_loader import world_primer
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
    # A turn may need compaction retries; the v4 protocol needs no GM judge
    # (V4-AGENT-INTERFACE §0) and no persona primer (KB rows carry identity).
    provider = provider_from_env(
        max_concurrency=min(len(world.actors), env_int("V3_PROVIDER_CONCURRENCY", 8)))
    decision_timeout = provider.worst_case_seconds() * 8 + 5.0
    if decision_timeout <= provider.worst_case_seconds() * 8:
        raise RuntimeError("provider decision budget is not bounded")
    # V4-CAST §1/§3: MCs get full persistent sessions; NPCs get event-driven
    # director-briefed agents (world knowledge + public MC digest per wake).
    # Both run the V4-AGENT-INTERFACE protocol: verbatim system prompt,
    # native tool calls, KB rows rendered by the engine.
    schedule_text = schedule_digest(pack.scheduled, now=world.now)
    npc_director_notes = pack.manifest.get("npc_director_notes", {})
    # Per-world static primer (V4-AGENT-INTERFACE §1): locations, walk times,
    # time scale, privacy rules — appended to the verbatim system prompt.
    primer = world_primer(pack)

    def director_brief(actor_id: str) -> str | None:
        goal = str(npc_director_notes.get("beat_goals", {}).get(actor_id, ""))
        if not goal:
            return None
        return (f"[导演] 本场目标：{goal}\n"
                f"主角近况（公开信息）：{public_mc_digest(world)[:400]}\n"
                f"排程背景（不许剧透）：{schedule_text[:300]}")

    agents = {}
    for actor_id, actor in world.actors.items():
        if actor.role == "npc":
            agents[actor_id] = make_npc_agent_v4(seeds[actor_id], provider, world_primer=primer)
        else:
            agents[actor_id] = make_persistent_agent_v4(seeds[actor_id], provider,
                                                        world_primer=primer)
    run_id = new_run_id("real")
    trace = Trace("v3", run_id)
    from .action_schema import TOOLS
    trace.record_tools([tool["function"]["name"] for tool in TOOLS])
    ledger = Ledger(pack.system.get("facts", {}), pack.system)
    # 多日弧线 (ticket 25)：端点由 manifest 的 clock.stop 定义；world_stops
    # 标记只由排程本身携带（当前排程的最后一个日界），不再为分段端点注入
    # 合成标记——它会进入日志、被 actor 看见，并毒化后续检查点恢复。
    # 分段端点：V3_CLOCK_STOP 优先（半天/单日里程碑段）；缺省为整弧终点。
    # 只定端点，不注入任何合成 world_stops——标记只由排程携带。
    endpoint = clock_stop(str(pack.manifest["clock"]["stop"]))
    arc_end = max(str(row["time"]) for row in pack.manifest["scheduled"]
                  if row.get("event") == "world_stops")
    endpoint_is_arc_end = endpoint.isoformat() == arc_end
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
    max_wall = env_float("V3_MAX_WALL_SECONDS", 7200.0)
    print(f"[real_run] max_wall_seconds={max_wall} decision_timeout={decision_timeout:.0f}")
    # V4-ENGINE §8: the async DES engine is the production driver.
    runner = AsyncEngine(world, agents, states, trace, ledger,
                         decision_timeout=decision_timeout,
                         max_transient_failures=env_int("V3_MAX_TRANSIENT_FAILURES", 3),
                         max_wall_seconds=max_wall,
                         mc_idle_heartbeat=env_int("V4_MC_IDLE_HEARTBEAT", 1800),
                         stall_budget_ratio=env_float("V4_STALL_BUDGET_RATIO", 0.25),
                         checkpoint=checkpoint, extra_call=provider,
                         kb_seeds=pack.kb, director_brief=director_brief)
    holder["runner"] = runner
    # Ticket 25 — one state-loading path: compile the authored seed into the
    # initial v4-checkpoint-2 artifact, persist it, then load the run state
    # BACK from that checkpoint. The engine never runs on a privately-built
    # world: what it runs on is checkpoint-borne.
    from .compile_seed import build_initial_checkpoint
    runner._init_kb(world.now)
    # 半天检查点方法论 (ticket 25): V3_RESUME_CHECKPOINT 指向上一个里程碑
    # 检查点即从该点续跑 (世界/运行器/会话/追溯一体恢复)；未设置则编译种子
    # 为初始检查点。同一条恢复路径，两个入口。
    resume_source = os.environ.get("V3_RESUME_CHECKPOINT")
    if resume_source:
        from .checkpoint import load_checkpoint
        seed_checkpoint = load_checkpoint(Path(resume_source))
        if "trace" in seed_checkpoint:
            trace.restore_from_snapshot(seed_checkpoint["trace"])
        # 世界与运行器状态同样必须从检查点恢复——否则会从种子静默重跑。
        world.restore_checkpoint(seed_checkpoint["world"])
        runner.restore_checkpoint(seed_checkpoint["runner"])
        print(f"[real_run] resuming from {resume_source} "
              f"(world now: {world.now.isoformat()})")
        # Ticket 26: 检查点快照时的队列不含之后新写的排程——把 manifest 里
        # 晚于恢复时刻、且尚未触发/未排队的节拍合并进来。镜像 kernel 的
        # 调度方式：整行作为 payload、单任务。
        merged = 0
        fired = {(str(e.time)[:10], str(e.payload.get("event", "")))
                 for e in world.event_log if e.kind == "world_event"}
        queued = {(j.time.isoformat()[:16], str((j.payload or {}).get("event", "")))
                  for j in world._queue if j.kind == "world_event"}
        for row in pack.manifest.get("scheduled", ()) or ():
            when = datetime.fromisoformat(str(row["time"]))
            if when <= world.now:
                continue
            name = str(row.get("event", ""))
            if (str(row["time"])[:16], name) in queued:
                continue
            if (str(row["time"])[:10], name) in fired:
                continue
            world._schedule(when, str(row.get("kind", "world_event")),
                            None, dict(row), None)
            merged += 1
        if merged:
            print(f"[real_run] schedule merge: +{merged} manifest beat(s) after resume")
        # 排程以 manifest 为准：同一时刻的名称被修订过的陈旧队列作业
        # （如 world_stops 降级为 day_boundary）不再触发——移除。
        manifest_at: dict[str, set[str]] = {}
        for row in pack.manifest.get("scheduled", ()) or ():
            manifest_at.setdefault(str(row["time"])[:16], set()).add(str(row.get("event", "")))
        stale = [j for j in world._queue if j.kind == "world_event"
                 and j.time.isoformat()[:16] in manifest_at
                 and str((j.payload or {}).get("event", "")) not in manifest_at[j.time.isoformat()[:16]]]
        if stale:
            dropped = {str((j.payload or {}).get("event", "")) for j in stale}
            world._queue = [j for j in world._queue if j not in stale]
            heapq.heapify(world._queue)
            print(f"[real_run] schedule supersede: dropped stale queue job(s): {sorted(dropped)}")
    else:
        seed_checkpoint = build_initial_checkpoint(runner, pack, run_id, root=root)
        seed_checkpoint_path = root / "runs" / f"{run_id}.seed-checkpoint.json"
        save_checkpoint(seed_checkpoint_path, seed_checkpoint)
        print(f"[real_run] initial checkpoint -> {seed_checkpoint_path} "
              f"(history events: {seed_checkpoint['meta']['history_count']})")
        world.restore_checkpoint(seed_checkpoint["world"])
        runner.restore_checkpoint(seed_checkpoint["runner"])
    try:
        reason = runner.run(stop_at=endpoint, max_turns=20_000)
    except BaseException as exc:
        trace.fail(reason="aborted_provider_or_runtime_error", world=world, error=exc)
        trace.save(world, output)
        output.with_suffix(".error.log").write_text(
            traceback.format_exc(), encoding="utf-8")
        raise
    try:
        # V4: a turn-level agent_error means that character lost one turn and
        # received corrective feedback — the world continues; the endpoint is
        # the health bar. Error counts are reported, not fatal here.
        agent_errors = sum(1 for t in trace.agent_turns
                           if t.get("result") in {"agent_error", "decision_timeout",
                                                  "engine_error"})
        if agent_errors:
            print(f"note: {agent_errors} agent errors survived as lost turns")
        if reason not in {"stop_at_reached", "world_stops"}:
            # world_stops = 当日日界（多日弧线的半天/全天边界），同样是
            # 设计内的完成。
            raise RuntimeError(f"real experiment stopped before endpoint: {reason}")
        trace.verify_complete(world, endpoint=endpoint.isoformat(),
                              stop_event="world_stops" if endpoint_is_arc_end else None,
                              allow_lost_turns=True)
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
