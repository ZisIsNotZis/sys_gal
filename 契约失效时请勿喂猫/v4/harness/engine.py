"""Async discrete-event engine (V4-ENGINE.md SSOT).

One coroutine loop per actor (MC/NPC/extra — same protocol, different
lifecycle), driven by a single-threaded scheduler that owns the world clock.
The World kernel keeps owning state, physics, visibility, and event sourcing;
this module owns concurrency, the decision-horizon freeze rule, wake vs
interrupt delivery, cast lifecycle, and failure isolation.

Invariants implemented here (V4-ENGINE §2):

- Global light cone: events committed at T are perceivable from T+1 tick —
  guaranteed structurally because an actor only polls at its next turn, and
  a turn never starts in the tick an event committed... more precisely: the
  engine delivers mail at turn start, and turns start only after the world
  advanced past the event.
- Global decision horizon: the engine processes queued events only up to
  ``oldest_inflight_wake + 1 tick``; the first event beyond that is a freeze
  point and the whole clock waits for the intent (stall accounting §6).
- Same-tick ordering = intent arrival order: submissions happen in asyncio
  completion order, single-threaded.
- Interrupts bind at execution position: the kernel's lazy ``busy_until`` /
  ``current_action`` machinery does the binding; this module only delivers.
- Silent abandonment: ``decision_timeout`` with no intent = 发呆 — no world
  effect, a pending action auto-continues, the timer re-arms, failure +1.
  The world never freezes on one dead provider (§6).
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Mapping

from .adapter import parse_decision
from .agent_state import PrivateState
from .kernel import (ActionRejected, Intention, TICK_SECONDS,
                     WAKE_EVENT_KINDS, World)
from .npc_agent import (build_extra_briefing, build_extra_system_prompt,
                        generate_stranger_name, sample_extra)
from .repetition import RepetitionMonitor

AgentFn = Callable[[PrivateState, dict, list[dict]], Any]

class AsyncEngine:
    def __init__(self, world: World, agents: dict[str, AgentFn],
                 states: dict[str, PrivateState], trace: Any,
                 system: Any = None, *, extra_call: Callable | None = None,
                 decision_timeout: float = 60.0,
                 max_wall_seconds: float | None = None,
                 max_turns: int = 20_000,
                 checkpoint: Callable[[], None] | None = None,
                 mc_idle_heartbeat: int = 1800,
                 extra_idle_seconds: int = 600,
                 cold_ticks: int = 6, npc_wake_budget: int = 12,
                 stall_budget_ratio: float = 0.25,
                 max_transient_failures: int = 3) -> None:
        # Extras restored from a checkpoint have no agent/state of their own
        # (they run on extra_call with session-local memory, V4-CAST §1).
        required = {actor for actor in world.actors if world.actors[actor].role != "extra"}
        if set(agents) != required or set(states) != required:
            raise ValueError("one agent and private state are required for every non-extra actor")
        self.world, self.agents, self.states, self.trace, self.system = world, agents, states, trace, system
        self.extra_call = extra_call
        self.decision_timeout = float(decision_timeout)
        self.max_wall_seconds = max_wall_seconds
        self.max_turns = int(max_turns)
        self.checkpoint = checkpoint
        self.mc_idle_heartbeat = int(mc_idle_heartbeat)
        self.extra_idle_seconds = int(extra_idle_seconds)
        self.cold_ticks = int(cold_ticks)
        self.npc_wake_budget = int(npc_wake_budget)
        self.stall_budget_ratio = float(stall_budget_ratio)
        self.max_transient_failures = int(max_transient_failures)
        self.stop_reason: str | None = None
        # CAST state (V4-CAST): NPC wake reasons, extras, cold-scene bookkeeping.
        self._npc_pending: dict[str, str] = {}
        self._wake_times: list[datetime] = []
        self._last_speech: dict[str, datetime] = {}
        self._cold_woken: dict[str, datetime] = {}
        self._npc_scan = 0
        self._extras_scan = 0
        self._wake_scan = 0
        self._rep_scan = 0
        self._extras: dict[str, dict[str, Any]] = {}
        self._extra_tasks: dict[str, asyncio.Task] = {}
        self._failures: dict[str, int] = {actor: 0 for actor in world.actors}
        self._turns = 0
        self._inner_missing = 0
        self._inner_reminded: set[str] = set()
        self._rejection_sequence = 0
        self._operational_facts: dict[str, list[dict[str, Any]]] = {actor: [] for actor in world.actors}
        self._repetition = RepetitionMonitor()
        # Live-loop state (rebuilt in run()).
        self._inflight: dict[str, datetime] = {}
        self._hung: dict[str, asyncio.Task] = {}
        self._heartbeat_jobs: dict[str, int] = {}
        self._force_turn: set[str] = set()

    # ------------------------------------------------------------------ run

    def run(self, *, stop_at: datetime | None = None, max_turns: int | None = None) -> str:
        if max_turns is not None:
            self.max_turns = int(max_turns)
        return asyncio.run(self._run(stop_at))

    async def _run(self, stop_at: datetime | None) -> str:
        loop = asyncio.get_running_loop()
        self._wake_events = {actor: asyncio.Event() for actor in self.world.actors}
        self._scheduler_wake = asyncio.Event()
        self._wall_started = time.monotonic()
        self._stall_seconds = 0.0
        self._world_stops_seen = False
        tasks = [loop.create_task(self._actor_loop(actor))
                 for actor in self._persistent_actors()]
        # Bootstrap: MCs take a first turn at world start (old runner round-1
        # parity) and carry an idle heartbeat thereafter; NPCs stay
        # event-driven (V4-CAST §2) and extras spawn on demand.
        for actor in self._persistent_actors():
            if self.world.actors[actor].role == "mc":
                self._rearm_heartbeat(actor)
                self._force_turn.add(actor)
                self._wake_events[actor].set()
        for name in list(self._extras):
            self._wake_events[name] = asyncio.Event()
            self._extra_tasks[name] = loop.create_task(self._extra_loop(name, ""))
        scheduler = loop.create_task(self._scheduler_loop(stop_at))
        try:
            await scheduler
        finally:
            for task in tasks + list(self._extra_tasks.values()):
                task.cancel()
            await asyncio.gather(*tasks, *self._extra_tasks.values(),
                                 return_exceptions=True)
        if self.checkpoint is not None:
            self.checkpoint()
        return self.stop_reason or "stopped"

    def _persistent_actors(self) -> list[str]:
        return [actor for actor, a in self.world.actors.items() if a.role != "extra"]

    def _finish(self, reason: str) -> None:
        if self.stop_reason is None:
            self.stop_reason = reason
            print(f"[engine] stop: {reason}", flush=True)

    # ------------------------------------------------------------ scheduler

    async def _scheduler_loop(self, stop_at: datetime | None) -> None:
        while self.stop_reason is None:
            if self.max_wall_seconds is not None and \
                    time.monotonic() - self._wall_started > self.max_wall_seconds:
                self._finish("wall_clock_deadline_reached")
                break
            if self.max_wall_seconds is not None and \
                    self._stall_seconds > self.stall_budget_ratio * self.max_wall_seconds:
                self._finish("stall_budget_exceeded")
                break
            if self._turns >= self.max_turns:
                self._finish("max_turns_reached")
                break
            if stop_at is not None and self.world.now >= stop_at:
                self._finish("stop_at_reached")
                break
            self._cast_scan()
            self._wake_waiters()
            self._notify_ready()
            if self.stop_reason:
                break
            await asyncio.sleep(0)  # let actor tasks run between passes
            next_event = self.world.next_event_time()
            if self._world_stops_seen:
                self._finish("world_stops")
                break
            if next_event is None:
                if stop_at is not None and self.world.now < stop_at:
                    if not self._quiescent():
                        await self._await_activity()
                        continue
                    self.world.advance(until=stop_at)
                    self._after_advance()
                    continue
                self._finish("queue_drained")
                break
            if stop_at is not None and next_event > stop_at:
                if not self._quiescent():
                    # A decision in flight may still create events before
                    # stop_at; never jump the clock past its moment
                    # (V4-ENGINE §2.3 applies to every clock jump).
                    await self._await_activity()
                    continue
                self.world.advance(until=stop_at)
                self._after_advance()
                continue
            bound = self._horizon_bound()
            if bound is not None and next_event > bound:
                # Freeze point (V4-ENGINE §2.3): world progress is owed but a
                # decision is in flight. Wait until the oldest in-flight wake
                # resolves (its submission pops it from _inflight); account
                # the stall in wall seconds (§6). The 2 s poll bounds any
                # lost-signal race.
                started = time.monotonic()
                target = min(self._inflight.values())
                while self.stop_reason is None and self._inflight and \
                        min(self._inflight.values()) == target:
                    self._scheduler_wake.clear()
                    try:
                        await asyncio.wait_for(self._scheduler_wake.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
                self._stall_seconds += time.monotonic() - started
                continue
            self.world.advance(until=next_event)
            self._after_advance()
            await asyncio.sleep(0)

    def _any_ready(self) -> bool:
        return any(self._ready_now(actor) for actor in self._persistent_actors())

    def _quiescent(self) -> bool:
        """True when no actor can still create an event on its own."""
        return (not self._inflight and not self._force_turn and not self._any_ready())

    async def _await_activity(self) -> None:
        """Block until some actor state changes (bounded poll against lost
        wakeups)."""
        self._scheduler_wake.clear()
        try:
            await asyncio.wait_for(self._scheduler_wake.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass

    def _horizon_bound(self) -> datetime | None:
        """Process events only up to the oldest in-flight wake + 1 tick
        (V4-ENGINE §2.3)."""
        if not self._inflight:
            return None
        return min(self._inflight.values()) + timedelta(seconds=TICK_SECONDS)

    def _after_advance(self) -> None:
        for event in self.world.event_log[self._rep_scan:]:
            if event.kind == "message_delivered":
                self._repetition.note_message_received(
                    str(event.payload.get("target")), event.actor)
            if event.kind == "world_event" and event.payload.get("event") == "world_stops":
                self._world_stops_seen = True
            # An NPC whose (non-wait) action completed gets a follow-up turn
            # within the same wake (V4-CAST §1: 1~N actions per wake); a
            # finished wait is the NPC saying "nothing to do" — it sleeps.
            if (event.kind == "action_completed" and event.actor
                    and self._role(event.actor) == "npc"
                    and event.payload.get("action") not in {"wait", "sleep"}):
                self._npc_pending.setdefault(event.actor, "你的上一个动作有了结果")
        self._rep_scan = len(self.world.event_log)
        if self.checkpoint is not None:
            self.checkpoint()

    def _notify_ready(self) -> None:
        for actor, event in self._wake_events.items():
            if actor not in self.world.actors:
                continue
            if self._ready_now(actor):
                event.set()
        self._scheduler_wake.set()

    def _ready_now(self, actor_id: str) -> bool:
        if actor_id in self._force_turn:
            return True
        a = self.world.actors.get(actor_id)
        if a is None:
            return False
        if actor_id in self._npc_pending:
            return True
        if a.pending is not None:
            return True
        if a.busy_until and a.busy_until > self.world.now:
            return False
        if a.role == "npc":
            # NPCs wake only via CAST §2 triggers (named/beat/ripple/cold),
            # never on ambient public events — that is what keeps them
            # indistinguishable from MCs without burning wake budget.
            return False
        return self.world.has_wakeup(actor_id)

    def _wake_waiters(self) -> None:
        """Deliver the wake class: an ambient social event ends a light wait
        early so conversations can round-trip in M ticks (V4-ENGINE §3/§4)."""
        for event in self.world.event_log[self._wake_scan:]:
            if event.kind not in WAKE_EVENT_KINDS or event.actor is None:
                continue
            source = self.world.actors.get(event.actor)
            if source is None:
                continue
            for other in self.world.actors.values():
                if other.id != event.actor and other.location == source.location:
                    self.world.wake_waiter(other.id)
        self._wake_scan = len(self.world.event_log)

    # ----------------------------------------------------------- actor loop

    async def _actor_loop(self, actor_id: str) -> None:
        event = self._wake_events[actor_id]
        while self.stop_reason is None:
            try:
                hung = self._hung.pop(actor_id, None)
                if hung is not None:
                    try:
                        await hung  # a timed-out call must finish before the next turn
                    except Exception:
                        pass
                while not self._ready_now(actor_id):
                    if self.stop_reason:
                        return
                    await event.wait()
                    event.clear()
                event.clear()
                if self.stop_reason:
                    return
                await self._take_turn(actor_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # A dead actor task must never wedge the engine silently —
                # it would stay "ready" forever and block quiescence.
                print(f"[engine] actor task {actor_id} crashed: "
                      f"{type(exc).__name__}: {exc}", flush=True)
                self.trace.record_system({"kind": "actor_task_crash"},
                                         {"actor": actor_id,
                                          "error": f"{type(exc).__name__}: {exc}"})
                self._force_turn.discard(actor_id)
                self._inflight.pop(actor_id, None)
                self._scheduler_wake.set()
                await asyncio.sleep(0.1)

    async def _take_turn(self, actor_id: str) -> None:
        world = self.world
        a = world.actors[actor_id]
        self._force_turn.discard(actor_id)
        perception = world.poll(actor_id)
        self._turns += 1
        perception["_turn_id"] = f"turn-{self._turns}"
        fresh = [fact for fact in self._operational_facts[actor_id]
                 if not fact.get("delivered", False)]
        if fresh:
            perception["operational_facts"] = [dict(fact) for fact in fresh]
            for fact in fresh:
                fact["delivered"] = True
        notice = self._repetition.notice(actor_id)
        if notice:
            perception["situational_notice"] = notice
        affordances = list(world.affordances(actor_id))
        if self.system is not None:
            affordances.extend(self.system.affordances(actor_id))
        npc_reason = self._npc_pending.pop(actor_id, None)
        version_before = world.version
        self._inflight[actor_id] = world.now
        loop = asyncio.get_running_loop()
        decide_task = loop.create_task(asyncio.to_thread(
            self._decide, actor_id, perception, affordances))
        intention, result, error = None, "none", None
        try:
            decision = await asyncio.wait_for(asyncio.shield(decide_task),
                                              timeout=self.decision_timeout)
            updates: dict[str, Any] = {}
            if isinstance(decision, tuple):
                intention, updates = decision
            else:
                intention = decision
            # updates are no longer part of the protocol (V4-DESIGN §2).
            result, error = "decided", None
        except asyncio.TimeoutError:
            result, error = "decision_timeout", "agent decision exceeded the deadline"
        except Exception as exc:
            result, error = "agent_error", f"{type(exc).__name__}: {exc}"
        if result != "decided":
            # Silent abandonment (V4-ENGINE §3): 发呆, pending auto-continues,
            # timer re-arms, failure +1. The world never waits for a dead call.
            self._hung[actor_id] = decide_task
            self._inflight.pop(actor_id, None)
            self._scheduler_wake.set()
            self._failures[actor_id] = self._failures.get(actor_id, 0) + 1
            self._recovery(actor_id, perception, affordances, intention, result, error,
                           version_before, npc_reason)
            if self._all_failed():
                self._finish("all_agents_failed")
            return
        self._inflight.pop(actor_id, None)
        self._failures[actor_id] = 0
        self._scheduler_wake.set()
        self._submit(actor_id, perception, affordances, intention, version_before)
        self._rearm_heartbeat(actor_id)

    def _decide(self, actor_id: str, perception: dict, affordances: list[dict]):
        return self.agents[actor_id](self.states[actor_id], perception, affordances)

    def _all_failed(self) -> bool:
        live = [self._failures.get(actor, 0) for actor in self._persistent_actors()]
        return bool(live) and all(count >= self.max_transient_failures for count in live)

    # ------------------------------------------------------ submission path

    def _submit(self, actor_id: str, perception: dict, affordances: list[dict],
                intention: Intention | None, version_before: int) -> None:
        world = self.world
        event_ids: list[int] = []
        alternatives: list[str] = []
        result, error = "none", None
        if intention is not None:
            try:
                if intention.actor != actor_id:
                    raise ActionRejected("agent may submit only its own intention")
                # Same-tick arrivals rebase onto the current immutable version;
                # ordering is arrival order (V4-ENGINE §2.4).
                intention = Intention(intention.actor, intention.kind,
                                      intention.args, world.version,
                                      inner=intention.inner,
                                      interrupt=intention.interrupt,
                                      uninterruptable=intention.uninterruptable)
                if not intention.inner:
                    self._inner_missing += 1
                if intention.kind in {"system_accept", "system_decline", "system_query"}:
                    if self.system is None:
                        raise ActionRejected("no bound System")
                    before = len(world.event_log)
                    if intention.kind == "system_accept":
                        event = self.system.accept(world, actor_id, str(intention.args.get("case")))
                        event_ids.append(event.id)
                    elif intention.kind == "system_decline":
                        event = self.system.decline(world, actor_id)
                        event_ids.append(event.id)
                    else:
                        event = self.system.query(world, actor_id, str(intention.args.get("question")))
                        event_ids.extend(e.id for e in world.event_log[before:] if e.kind.startswith("system_"))
                    self.trace.record_system(dict(intention.args), {"event_id": event.id, "kind": event.kind})
                else:
                    before = len(world.event_log)
                    world.submit(intention)
                    event_ids.extend(e.id for e in world.event_log[before:])
                result = "submitted"
            except ActionRejected as exc:
                result, error = "rejected", str(exc)
                alternatives = list(getattr(exc, "alternatives", ()))
                self._rejection_sequence += 1
                feedback_id = f"rejection-{actor_id}-{self._rejection_sequence}"
                self._operational_facts[actor_id].append({
                    "type": "rejected_action", "feedback_id": feedback_id,
                    "action": {"kind": intention.kind, "args": dict(intention.args)},
                    "reason": str(exc), "alternatives": alternatives,
                    "must_change_before_retry": True, "delivered": False})
                # A wrong call still costs one tick (V4-ENGINE §2.1): idle
                # wait, then retry with the rejection feedback in hand.
                try:
                    world.submit(Intention(actor_id, "wait",
                                           {"duration_seconds": TICK_SECONDS},
                                           world.version))
                except ActionRejected:
                    pass
            except Exception as exc:
                result, error = "engine_error", f"{type(exc).__name__}: {exc}"
        self._repetition.note_turn(actor_id, intention, result)
        self.trace.record_agent(state=self.states[actor_id], perception=perception,
                                affordances=affordances, intention=intention,
                                result=result, error=error,
                                version_before=version_before, version_after=world.version,
                                event_ids=event_ids,
                                role=getattr(self.world.actors[actor_id], "role", "mc"))
        telemetry = self.trace.record_alias_telemetry()
        if telemetry:
            self.trace.record_system({"kind": "alias_telemetry"}, dict(telemetry))
        recorder = getattr(self.agents[actor_id], "record_world_result", None)
        if recorder is not None and result not in {"submitted", "none"}:
            message = self._result_message(result, error, event_ids, alternatives)
            if message:
                recorder(message)
        if intention is not None and not intention.inner:
            self.trace.record_system({"kind": "inner_telemetry"}, {"missing": self._inner_missing})
            if recorder is not None and actor_id not in self._inner_reminded:
                self._inner_reminded.add(actor_id)
                recorder("（你刚才没有写心声；每次行动前先在心里想，再行动。）")
        consume = getattr(self.agents[actor_id], "consume_compaction", None)
        if consume is not None and consume():
            self.world.notify_compaction(actor_id)
            self.trace.record_compaction(actor_id, perception.get("_turn_id"))
        snapshot = getattr(self.agents[actor_id], "session_snapshot", None)
        if snapshot is not None and snapshot() is not None:
            self.trace.record_session(actor_id, snapshot())
        self._scheduler_wake.set()

    def _recovery(self, actor_id: str, perception: dict, affordances: list[dict],
                  intention, result: str, error: str, version_before: int,
                  npc_reason: str | None) -> None:
        """Silent abandonment: record, auto-continue pending, idle one tick."""
        world = self.world
        a = world.actors.get(actor_id)
        if a is not None:
            try:
                if a.pending is not None:
                    world.submit(Intention(actor_id, "continue_action", {}, world.version))
                else:
                    world.submit(Intention(actor_id, "wait",
                                           {"duration_seconds": TICK_SECONDS},
                                           world.version))
            except ActionRejected:
                pass
        self.trace.record_agent(state=self.states[actor_id], perception=perception,
                                affordances=affordances, intention=None,
                                result=result, error=error,
                                version_before=version_before, version_after=world.version,
                                event_ids=[],
                                role=getattr(a, "role", "mc") if a else "extra")
        if self.checkpoint is not None:
            self.checkpoint()

    def _rearm_heartbeat(self, actor_id: str) -> None:
        if self.mc_idle_heartbeat <= 0:
            return
        if self.world.actors.get(actor_id, None) is None or \
                self.world.actors[actor_id].role != "mc":
            return
        previous = self._heartbeat_jobs.pop(actor_id, None)
        if previous is not None:
            self.world.cancel_scheduled(previous)
        when = self.world.now + timedelta(seconds=self.mc_idle_heartbeat)
        self._heartbeat_jobs[actor_id] = self.world.schedule_private_wake(actor_id, when)

    # ------------------------------------------------------- result message

    def _result_message(self, result: str, error: str | None, event_ids: list[int],
                        alternatives: Iterable[str] = ()) -> str:
        """中文、世界语气的即时反馈；接受的动作没有回执（V4-DESIGN §2）。"""
        if result == "submitted":
            return ""
        if result == "rejected":
            guidance = " 什么都没有改变。"
            if alternatives:
                guidance += " 可以考虑：" + "; ".join(alternatives) + "。"
            return (f"你的动作没有被执行：{str(error).strip()}{guidance}"
                    "看看可用的动作格式，换一个可行的做法。")
        if result in {"agent_error", "decision_timeout", "engine_error"}:
            return f"你的这个念头没能落地：{error}。"
        return ""

    # --------------------------------------------------------- cast machine

    def _role(self, actor_id: str) -> str:
        return getattr(self.world.actors.get(actor_id), "role", "mc")

    def _cast_scan(self) -> None:
        self._npc_triggers()
        self._handle_extras()
        self._cold_scene_check()

    def _npc_budget_ok(self) -> bool:
        now = self.world.now
        self._wake_times = [t for t in self._wake_times
                            if (now - t).total_seconds() < 3600]
        return len(self._wake_times) < self.npc_wake_budget

    def _npc_triggers(self) -> None:
        new_events = self.world.event_log[self._npc_scan:]
        self._npc_scan = len(self.world.event_log)
        for event in new_events:
            if event.kind == "speech":
                if event.actor in self.world.actors:
                    loc = self.world.actors[event.actor].location
                    self._last_speech[loc] = event.time
                    self._cold_woken.pop(loc, None)
                for npc in event.payload.get("to", ()) or ():
                    if self._role(str(npc)) == "npc":
                        self._npc_pending.setdefault(str(npc), "有人当面对你说话")
            elif event.kind in {"message_sent", "message_delivered"}:
                npc = str(event.payload.get("target", ""))
                if self._role(npc) == "npc":
                    self._npc_pending.setdefault(npc, "收到一条消息")
            elif event.kind == "knock":
                loc = str(event.payload.get("target", ""))
                for npc_id, actor in self.world.actors.items():
                    if self._role(npc_id) == "npc" and actor.location == loc:
                        self._npc_pending.setdefault(npc_id, "有人敲门")
            elif event.kind == "world_event":
                targets = event.payload.get("target") or ()
                if isinstance(targets, str):
                    targets = [targets]
                for npc in targets:
                    if self._role(str(npc)) == "npc":
                        self._npc_pending.setdefault(str(npc), "世界有了新动静")
            elif event.kind == "action_abandoned" and event.actor in self.world.actors:
                loc = self.world.actors[event.actor].location
                for npc_id, actor in self.world.actors.items():
                    if self._role(npc_id) == "npc" and actor.location == loc:
                        self._npc_pending.setdefault(npc_id, "附近刚有人起了冲突")

    def _cold_scene_check(self) -> None:
        now = self.world.now
        if not self._npc_budget_ok():
            return
        threshold = self.cold_ticks * TICK_SECONDS
        by_location: dict[str, list[str]] = {}
        for actor_id, actor in self.world.actors.items():
            if getattr(actor, "role", "mc") != "extra":
                by_location.setdefault(actor.location, []).append(actor_id)
        next_event = self.world.next_world_event_time()
        something_soon = (next_event is not None
                          and (next_event - now).total_seconds() <= 1800)
        for location, ids in by_location.items():
            if len(ids) < 2 or something_soon:
                continue
            last = self._last_speech.get(location)
            if last is not None and (now - last).total_seconds() < threshold:
                continue
            woken_at = self._cold_woken.get(location)
            if woken_at is not None and (last is None or woken_at >= last):
                continue
            npc_here = [i for i in sorted(ids)
                        if self._role(i) == "npc" and i not in self._npc_pending
                        and not (self.world.actors[i].busy_until
                                 and self.world.actors[i].busy_until > now)]
            if npc_here and self._npc_budget_ok():
                self._npc_pending[npc_here[0]] = "这里安静得有点久了，你是会找话的人"
                self._wake_times.append(now)
                self._cold_woken[location] = now

    def _handle_extras(self) -> None:
        new_events = self.world.event_log[self._extras_scan:]
        self._extras_scan = len(self.world.event_log)
        loop = asyncio.get_running_loop()
        for name in list(self._extras):
            info = self._extras[name]
            partner = info["partner"]
            alive = (partner in self.world.actors
                     and self.world.actors[partner].location == self.world.actors[name].location)
            idle = (self.world.now - info["last_active"]).total_seconds() > self.extra_idle_seconds
            if not alive or idle:
                self._despawn(name, "idle" if idle else "partner_gone")
        for event in new_events:
            if event.kind == "stranger_asked" and event.actor:
                asker = event.actor
                if any(x["partner"] == asker for x in self._extras.values()):
                    continue
                if self.extra_call is None or asker not in self.world.actors:
                    continue
                location = self.world.actors[asker].location
                entry = sample_extra(self.world.locations[location].extras)
                name = generate_stranger_name()
                while name in self.world.actors:
                    name = generate_stranger_name()
                self.world.add_extra(name, location)
                self._extras[name] = {"fragment": str(entry.get("fragment", "路人")),
                                      "knowledge_notes": str(entry.get("knowledge_notes", "")),
                                      "partner": asker, "last_active": self.world.now,
                                      "rarity": str(entry.get("rarity", "common")),
                                      "start": len(self.world.event_log)}
                self._wake_events[name] = asyncio.Event()
                self._extra_tasks[name] = loop.create_task(
                    self._extra_loop(name, str(event.payload.get("question", ""))))

    def _despawn(self, name: str, reason: str) -> None:
        if name in self.world.actors:
            self.world.remove_extra(name)
        self._extras.pop(name, None)
        task = self._extra_tasks.pop(name, None)
        if task is not None:
            task.cancel()
        self.trace.record_system({"kind": "extra_removed"}, {"extra": name, "reason": reason})

    async def _extra_loop(self, name: str, question: str) -> None:
        event = self._wake_events[name]
        pending_question = question
        try:
            while name in self._extras and name in self.world.actors and not self.stop_reason:
                asked = pending_question
                pending_question = ""
                info = self._extras.get(name)
                if info is None:
                    return
                await self._extra_turn(name, asked)
                while name in self._extras and not self._ready_now(name):
                    if self.stop_reason:
                        return
                    await event.wait()
                    event.clear()
                event.clear()
        except asyncio.CancelledError:
            raise

    async def _extra_turn(self, name: str, question: str) -> None:
        info = self._extras[name]
        location = self.world.actors[name].location
        transcript = [f"{e.actor}: {str(e.payload.get('text', ''))[:70]}"
                      for e in self.world.event_log[info["start"]:]
                      if e.kind == "speech" and e.actor in {name, info["partner"]}]
        system = build_extra_system_prompt(info["fragment"], info["knowledge_notes"], location)
        briefing = build_extra_briefing(fragment=info["fragment"], location=location,
                                        question=question, transcript=transcript)
        intention, result, error = None, "agent_error", ""
        try:
            raw = await asyncio.to_thread(
                self.extra_call, [{"role": "system", "content": system},
                                  {"role": "user", "content": briefing}])
            intention, _ = parse_decision(name, raw, self.world.version)
            if intention is not None:
                self.world.submit(Intention(name, intention.kind, intention.args,
                                            self.world.version,
                                            inner=intention.inner,
                                            interrupt=intention.interrupt,
                                            uninterruptable=intention.uninterruptable))
                result = "submitted"
                info["last_active"] = self.world.now
        except ActionRejected as exc:
            result, error = "rejected", str(exc)
        except Exception as exc:
            result, error = "agent_error", f"{type(exc).__name__}: {exc}"
        self.trace.record_agent(state=PrivateState(name),
                                perception={"observer": name, "time": self.world.now.isoformat(),
                                            "location": location, "events": [], "inbox": [],
                                            "nearby_actors": [], "nearby_items": []},
                                affordances=[], intention=intention, result=result,
                                error=error or None, role="extra")
        if intention is not None and intention.kind == "move":
            # A stranger who walks away ends the conversation (V4-CAST §1).
            self._despawn(name, "left")
        self._scheduler_wake.set()

    # ------------------------------------------------------------ checkpoint

    def checkpoint_state(self) -> dict[str, Any]:
        return {"waiting": [], "transient_failures": dict(self._failures),
                "operational_facts": {actor: [dict(x) for x in facts]
                                      for actor, facts in self._operational_facts.items()},
                "stop_reason": self.stop_reason, "rejection_sequence": self._rejection_sequence,
                "turn_sequence": self._turns, "retry_context": {},
                "repetition": self._repetition.state(), "rep_scan": self._rep_scan,
                "npc_pending": dict(self._npc_pending),
                "npc_scan": self._npc_scan, "extras_scan": self._extras_scan,
                "wake_scan": self._wake_scan,
                "extras": {name: {"fragment": x["fragment"], "knowledge_notes": x["knowledge_notes"],
                                   "partner": x["partner"],
                                   "last_active": x["last_active"].isoformat(),
                                   "rarity": x["rarity"], "start": x["start"]}
                           for name, x in self._extras.items()},
                "wake_times": [t.isoformat() for t in self._wake_times],
                "last_speech": {k: t.isoformat() for k, t in self._last_speech.items()},
                "heartbeat_jobs": dict(self._heartbeat_jobs)}

    def restore_checkpoint(self, state: dict[str, Any]) -> None:
        from datetime import datetime as _dt
        self._failures = {actor: int(value) for actor, value in state.get("transient_failures", {}).items()}
        self._operational_facts = {actor: [dict(x) for x in facts]
                                   for actor, facts in state.get("operational_facts", {}).items()}
        self.stop_reason = None
        self._rejection_sequence = int(state.get("rejection_sequence", 0))
        self._turns = int(state.get("turn_sequence", 0))
        self._repetition.restore(state.get("repetition", {}))
        self._rep_scan = int(state.get("rep_scan", len(self.world.event_log)))
        self._npc_pending = dict(state.get("npc_pending", {}))
        self._npc_scan = int(state.get("npc_scan", len(self.world.event_log)))
        self._extras_scan = int(state.get("extras_scan", len(self.world.event_log)))
        self._wake_scan = int(state.get("wake_scan", len(self.world.event_log)))
        self._wake_times = [_dt.fromisoformat(t) for t in state.get("wake_times", ())]
        self._last_speech = {k: _dt.fromisoformat(t) for k, t in state.get("last_speech", {}).items()}
        self._heartbeat_jobs = {k: int(v) for k, v in state.get("heartbeat_jobs", {}).items()}
        self._extras = {name: {**x, "last_active": _dt.fromisoformat(x["last_active"])}
                        for name, x in state.get("extras", {}).items()}
