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
from .prompt import render_world_message, _event_sentence
from .repetition import RepetitionMonitor

AgentFn = Callable[[PrivateState, dict, list[dict]], Any]

def _as_int(value: Any, what: str = "value") -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {what}: {value!r}") from exc


def _as_float(value: Any, what: str = "value") -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {what}: {value!r}") from exc


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
                 max_transient_failures: int = 3,
                 kb_seeds: Mapping[str, list[dict]] | None = None,
                 director_brief: Callable[[str], str | None] | None = None,
                 flashback_horizon_minutes: int = 120) -> None:
        # Extras restored from a checkpoint have no agent/state of their own
        # (they run on extra_call with session-local memory, V4-CAST §1).
        required = {actor for actor in world.actors if world.actors[actor].role != "extra"}
        if set(agents) != required or set(states) != required:
            raise ValueError("one agent and private state are required for every non-extra actor")
        self.world, self.agents, self.states, self.trace, self.system = world, agents, states, trace, system
        self.extra_call = extra_call
        self.decision_timeout = _as_float(decision_timeout, 'decision_timeout')
        self.max_wall_seconds = max_wall_seconds
        self.max_turns = _as_int(max_turns, 'max_turns')
        self.checkpoint = checkpoint
        self.mc_idle_heartbeat = _as_int(mc_idle_heartbeat, 'mc_idle_heartbeat')
        self.extra_idle_seconds = _as_int(extra_idle_seconds, 'extra_idle_seconds')
        self.cold_ticks = _as_int(cold_ticks, 'cold_ticks')
        self.npc_wake_budget = _as_int(npc_wake_budget, 'npc_wake_budget')
        self.stall_budget_ratio = _as_float(stall_budget_ratio, 'stall_budget_ratio')
        self.max_transient_failures = _as_int(max_transient_failures, 'max_transient_failures')
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
        # V4-AGENT-INTERFACE wiring: per-actor KB, tool-call error queue for
        # the next #error block, recall queue, flashback pool/display.
        self._kb: dict[str, Any] = {}
        self._kb_seeds = dict(kb_seeds or {})
        self.director_brief = director_brief
        self.flashback_horizon_minutes = _as_int(flashback_horizon_minutes, 'flashback_horizon_minutes')
        self._recall_lines: dict[str, list[str]] = {}
        self._flashback_display: dict[str, list[str]] = {}
        self._flashback_pool: dict[str, list[tuple[datetime, str, frozenset[str]]]] = {}
        self._pending_notices: dict[str, list[str]] = {}
        self._reminder_jobs: dict[tuple[str, str], int] = {}

    # ------------------------------------------------------------------ run

    def run(self, *, stop_at: datetime | None = None, max_turns: int | None = None) -> str:
        if max_turns is not None:
            self.max_turns = _as_int(max_turns, 'max_turns')
        return asyncio.run(self._run(stop_at))

    async def _run(self, stop_at: datetime | None) -> str:
        loop = asyncio.get_running_loop()
        self._stop_horizon = stop_at
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
        self._init_kb(self.world.now)
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

    def _init_kb(self, now: datetime) -> None:
        """V4-AGENT-INTERFACE §6: build each actor's KB from the manifest's
        kb: seed rows (engine-owned memory; the session never carries it)."""
        if not self._kb_seeds:
            return
        from .kb import ActorKB
        for actor, rows in self._kb_seeds.items():
            if actor in self.world.actors:
                self._kb[actor] = ActorKB(actor, rows, now)

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
            self._reminder_scan()
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
            if self._has_pending_turns():
                # Ready actors must act at the current moment; never advance
                # the clock past an owed turn.
                await self._await_activity()
                continue
            self.world.advance(until=next_event)
            self._after_advance()
            await asyncio.sleep(0)

    def _any_ready(self) -> bool:
        return any(self._ready_now(actor) for actor in self._persistent_actors())

    def _quiescent(self) -> bool:
        """True when no actor can still create an event on its own."""
        return (not self._inflight and not self._force_turn and not self._any_ready())

    def _has_pending_turns(self) -> bool:
        """True when some actor owes a turn at the current moment (woken or
        interrupted but not yet polled/deciding). Time must not advance past
        such an actor — its perception belongs to now. Deliberating actors
        are excluded: their moment is governed by the decision horizon
        (V4-ENGINE §2.3), not by readiness."""
        if self._force_turn:
            return True
        return any(self._ready_now(actor) and actor not in self._inflight
                   for actor in self._persistent_actors())

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

    def _reminder_scan(self) -> None:
        """Schedule open reminder rows as kernel queue jobs (V4-AGENT-INTERFACE
        §4): the kernel fires them on time (robust against DES jumps), the
        engine turns the private reminder_due events into notices and auto-
        closes the rows when they are perceived."""
        now = self.world.now
        from .kb import parse_reminder_time
        for actor_id, kb in self._kb.items():
            if actor_id not in self.world.actors:
                continue
            for row in kb.snapshot()["rows"]:
                fields, row_id = row.get("fields", {}), row.get("id")
                raw = fields.get("reminder")
                if not raw or row.get("status", "open") != "open":
                    continue
                if (actor_id, row_id) in self._reminder_jobs:
                    continue
                when = parse_reminder_time(raw, now)
                if when is None or when <= now:
                    continue
                self._reminder_jobs[(actor_id, row_id)] = self.world.schedule_reminder(
                    actor_id, when, row_id, str(row.get("desc", "")), raw)
            for row in kb.snapshot()["rows"]:
                fields, row_id = row.get("fields", {}), row.get("id")
                status = row.get("status", "open")
                raw = fields.get("reminder")
                if not raw or status != "open":
                    continue
                if (actor_id, row_id) in self._reminder_jobs:
                    continue
                when = parse_reminder_time(raw, now)
                if when is None or when <= now:
                    continue
                self._reminder_jobs[(actor_id, row_id)] = \
                    self.world.schedule_private_wake(actor_id, when)

    def _after_advance(self) -> None:
        for event in self.world.event_log[self._rep_scan:]:
            if event.kind == "message_delivered":
                self._repetition.note_message_received(
                    str(event.payload.get("target")), event.actor or "")
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
        v4 = hasattr(self.agents[actor_id], "session_obj")
        if v4:
            knowledge_lines = self._knowledge_lines(actor_id, perception, affordances)
            flashback_lines = self._flashback_display.pop(actor_id, [])
            director = (self.director_brief(actor_id)
                        if self.director_brief and self._role(actor_id) == "npc" and npc_reason
                        else None)
            text = render_world_message(perception, affordances, observer=actor_id,
                                        knowledge_lines=knowledge_lines,
                                        flashback_lines=flashback_lines, director=director)
            decide_task = loop.create_task(asyncio.to_thread(
                self._decide_v4, actor_id, text))
        else:
            decide_task = loop.create_task(asyncio.to_thread(
                self._decide, actor_id, perception, affordances))
        intention, result, error = None, "none", None
        chain_calls: list[dict[str, Any]] | None = None
        try:
            decision = await asyncio.wait_for(asyncio.shield(decide_task),
                                              timeout=self.decision_timeout)
            updates: dict[str, Any] = {}
            if v4:
                chain_calls = list(decision or [])
            elif isinstance(decision, tuple):
                intention, updates = decision
            else:
                intention = decision
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
        if v4:
            self._execute_chain(actor_id, chain_calls or [], perception,
                                affordances, version_before)
        else:
            self._submit(actor_id, perception, affordances, intention, version_before)
        self._rearm_heartbeat(actor_id)

    def _decide_v4(self, actor_id: str, world_message_text: str):
        from typing import cast
        agent_v4 = cast(Callable[[str, Any], list[dict[str, Any]]], self.agents[actor_id])
        return agent_v4(world_message_text, self.states[actor_id])

    def _decide(self, actor_id: str, perception: dict, affordances: list[dict]):
        return self.agents[actor_id](self.states[actor_id], perception, affordances)

    # ------------------------------------------------- v4 chain execution

    def _knowledge_lines(self, actor_id: str, perception: dict,
                         affordances: list[dict]) -> list[str]:
        """#knowledge block: due KB rows under the M7 mention set, plus due
        reminder notices (auto-closed after notification, §4)."""
        if actor_id not in self._kb:
            return []
        mention = set(perception.get("nearby_actors", [])) | set(perception.get("inventory", []))
        for option in affordances:
            for key in ("item", "document", "target"):
                value = option.get(key)
                if isinstance(value, str):
                    mention.add(value)
        for event in perception.get("events", []):
            payload = event.get("payload", {})
            for key in ("document", "item", "target", "first", "second", "from", "to"):
                value = payload.get(key)
                if isinstance(value, str):
                    mention.add(value)
        kb = self._kb[actor_id]
        lines = list(kb.due_lines(self.world.now, mention))
        lines.extend(self._recall_lines.pop(actor_id, []))
        lines.extend(self._pending_notices.pop(actor_id, []))
        for event in perception.get("events", []):
            if event.get("kind") != "reminder_due":
                continue
            payload = event.get("payload", {})
            kb.close_reminder(str(payload.get("row_id", "")))
            lines.append(f"[reminder={payload.get('rendered', '')}]: "
                         f"{payload.get('desc', '')}（到期）")
        return lines

    def _flashback_query(self, actor_id: str, entity: str) -> list[str]:
        """flashback tool: re-display the actor's own delivered history lines
        related to an entity, older than the horizon, LRU-capped (§3)."""
        horizon = self.world.now - timedelta(minutes=self.flashback_horizon_minutes)
        matches = [(t, line) for (t, line, entities) in self._flashback_pool.get(actor_id, [])
                   if t <= horizon and (not entity or entity in entities)]
        return [line for _, line in matches[-5:]]

    def _tool_yield(self, name: str, args: Mapping[str, Any], world: World) -> str:
        """The caller-facing yield of a world action (V4-AGENT-INTERFACE §3):
        most actions yield nothing beyond the world's reaction; read and
        compare carry their content/verdict in the tool result."""
        if name == "read":
            document = world.document_defs.get(str(args.get("document")), {})
            content = str(document.get("content", ""))
            annotations = document.get("annotations") or []
            if annotations:
                notes = "；".join(f"{e.get('by')}批注：{e.get('text')}" for e in annotations)
                content = f"{content}\n（记录上还有：{notes}）" if content else notes
            return content or "（这份记录没有可读的正文。）"
        if name == "compare":
            same = world.document_defs.get(str(args.get("first")), {}).get("content") == \
                   world.document_defs.get(str(args.get("second")), {}).get("content")
            return "内容一致" if same else "内容不一致"
        return "ok"

    def _remember_lines(self, actor_id: str, perception: dict) -> None:
        """Feed the actor's flashback pool with its delivered public lines."""
        from .prompt import _event_sentence
        pool = self._flashback_pool.setdefault(actor_id, [])
        for event in perception.get("events", []):
            line = _event_sentence(event, location=perception.get("location", ""))
            if not line:
                continue
            payload = event.get("payload", {})
            entities = {str(event.get("actor"))} if event.get("actor") else set()
            for key in ("document", "item", "target", "location", "first", "second", "from", "to"):
                value = payload.get(key)
                if isinstance(value, str):
                    entities.add(value)
            pool.append((self.world.now, line, frozenset(entities)))
        del pool[:-50]

    def _execute_chain(self, actor_id: str, calls: Any, perception: dict,
                       affordances: list[dict], version_before: int) -> None:
        """V4-AGENT-INTERFACE §4: execute the turn's tool calls in order —
        memory tools are engine-side and free; world actions submit through
        the kernel with time accumulating between calls; a chain with no
        world action = 发呆 1 tick; more than 8 calls truncate at the call
        boundary ("truncated: N calls dropped")."""
        world = self.world
        results: list[dict[str, Any]] = []
        failures: list[str] = []
        world_actions = 0
        calls = list(calls or [])
        truncated = max(0, len(calls) - 8)
        if truncated:
            calls = calls[:8]
        a = world.actors[actor_id]

        def fail(call: dict[str, Any], text: str) -> None:
            results.append({"tool_call_id": call.get("tool_call_id"), "ok": False, "text": text})
            failures.append(f"{call.get('name')}: {text}")

        for call in calls:
            name = str(call.get("name", ""))
            args = call.get("arguments") or {}
            if call.get("parse_error"):
                fail(call, f"unparseable arguments: {call['parse_error']}")
                continue
            if name == "think":
                results.append({"tool_call_id": call.get("tool_call_id"), "ok": True, "text": "ok"})
                continue  # inner stays in the session history; no world effect
            if name == "update_memory":
                if actor_id in self._kb:
                    errs, _tel = self._kb[actor_id].apply_ops(args.get("rows") or [], world.now)
                    if errs:
                        fail(call, "; ".join(errs))
                    else:
                        results.append({"tool_call_id": call.get("tool_call_id"), "ok": True, "text": "ok"})
                else:
                    fail(call, "no notebook seeded for this actor")
                continue
            if name == "recall":
                if actor_id in self._kb:
                    self._recall_lines.setdefault(actor_id, []).extend(
                        self._kb[actor_id].force_recall(
                            args.get("kinds"), args.get("ids"),
                            bool(args.get("closed")), _as_int(args.get("limit") or 8, "limit")))
                results.append({"tool_call_id": call.get("tool_call_id"), "ok": True, "text": "ok"})
                continue
            if name == "flashback":
                self._flashback_display[actor_id] = self._flashback_query(
                    actor_id, str(args.get("entity") or ""))
                results.append({"tool_call_id": call.get("tool_call_id"), "ok": True, "text": "ok"})
                continue
            try:
                world.submit(Intention(actor_id, name, dict(args), world.version))
                world_actions += 1
                results.append({"tool_call_id": call.get("tool_call_id"), "ok": True,
                                "text": self._tool_yield(name, args, world)})
                if a.busy_until and a.busy_until > world.now:
                    # The chain's own committed time: advance to the action's
                    # completion so the next call starts after it — clamped to
                    # the run's stop horizon so a chain never crosses the
                    # endpoint the completion gate checks.
                    limit = a.busy_until
                    if self._stop_horizon is not None:
                        limit = min(limit, self._stop_horizon)
                    if limit > world.now:
                        world.advance(until=limit)
                if a.busy_until and self._stop_horizon is not None and a.busy_until > self._stop_horizon:
                    remaining = len(calls) - calls.index(call) - 1
                    results.append({"tool_call_id": None, "ok": False,
                                    "text": (f"endpoint reached: {remaining} calls dropped"
                                             if remaining else "endpoint reached")})
                    break  # the run's endpoint cut this chain short
            except ActionRejected as exc:
                fail(call, str(exc))
            except Exception as exc:
                fail(call, f"{type(exc).__name__}: {exc}")
            if a.pending is not None:
                # A reminder (or another force interrupt) suspended the chain:
                # the actor must answer continue-or-cancel before anything else.
                for rest in calls[calls.index(call) + 1:]:
                    results.append({"tool_call_id": rest.get("tool_call_id"), "ok": False,
                                    "text": "interrupted; not executed"})
                break
        if truncated:
            results.append({"tool_call_id": None, "ok": False,
                            "text": f"truncated: {truncated} calls dropped"})
        if not world_actions:
            # 一回合没有任何世界动作 = 发呆 1 tick (V4-AGENT-INTERFACE §0/§4).
            try:
                world.submit(Intention(actor_id, "wait",
                                       {"duration_seconds": TICK_SECONDS},
                                       world.version))
            except ActionRejected:
                pass
        deliver = getattr(self.agents[actor_id], "deliver_tool_results", None)
        if deliver is not None:
            deliver(results)
        self._remember_lines(actor_id, perception)
        result = "submitted" if (world_actions or calls) else "none"
        self._repetition.note_turn(actor_id, None, result)
        recorded = (Intention(actor_id, str(calls[0].get("name", "think")),
                              {"calls": [{"name": c.get("name"),
                                           "args": c.get("arguments") or {}}
                                          for c in calls]})
                    if calls else None)
        self.trace.record_agent(state=self.states[actor_id], perception=perception,
                                affordances=affordances, intention=recorded,
                                result=result, error="; ".join(failures) or None,
                                version_before=version_before,
                                version_after=world.version, event_ids=[],
                                role=self._role(actor_id))
        consume = getattr(self.agents[actor_id], "consume_compaction", None)
        if consume is not None and consume():
            if actor_id in self._kb:
                self._kb[actor_id].on_compaction()
            world.notify_compaction(actor_id)
            self.trace.record_compaction(actor_id, perception.get("_turn_id"))
        snapshot = getattr(self.agents[actor_id], "session_snapshot", None)
        if snapshot is not None and snapshot() is not None:
            self.trace.record_session(actor_id, snapshot())
        self._scheduler_wake.set()

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
                        event = self.system.ask(world, actor_id, str(intention.args.get("question")))
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
                  intention, result: str, error: str | None, version_before: int,
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

            def _busy(i: str) -> bool:
                busy = self.world.actors[i].busy_until
                return busy is not None and busy > now
            npc_here = [i for i in sorted(ids)
                        if self._role(i) == "npc" and i not in self._npc_pending
                        and not _busy(i)]
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
        intention_calls: list[dict[str, Any]] = []
        result, error = "agent_error", ""
        try:
            if hasattr(self.extra_call, "chat_with_tools"):
                from .npc_agent import extra_tool_calls
                extra_call = self.extra_call
                assert extra_call is not None
                intention_calls = await asyncio.to_thread(
                    extra_tool_calls, extra_call, system, briefing)
            else:
                legacy_extra = self.extra_call
                assert legacy_extra is not None
                raw = await asyncio.to_thread(
                    legacy_extra, [{"role": "system", "content": system},
                                   {"role": "user", "content": briefing}])
                intention, _ = parse_decision(name, raw, self.world.version)
                if intention is not None:
                    intention_calls = [{"name": intention.kind,
                                        "arguments": dict(intention.args)}]
            spoke = False
            for call in intention_calls:
                call_name = str(call.get("name", ""))
                if call_name != "speak":
                    continue  # extras' tool surface is speak-only (§5)
                args = call.get("arguments") or {}
                self.world.submit(Intention(name, "speak", dict(args),
                                            self.world.version))
                spoke = True
                info["last_active"] = self.world.now
            result = "submitted" if spoke else ("none" if intention_calls else "agent_error")
        except ActionRejected as exc:
            result, error = "rejected", str(exc)
        except Exception as exc:
            result, error = "agent_error", f"{type(exc).__name__}: {exc}"
        self.trace.record_agent(state=PrivateState(name),
                                perception={"observer": name, "time": self.world.now.isoformat(),
                                            "location": location, "events": [], "inbox": [],
                                            "nearby_actors": [], "nearby_items": []},
                                affordances=[], intention={"kind": "speak", "args": {"calls": intention_calls}},
                                result=result,
                                error=error or None, role="extra")
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
                "heartbeat_jobs": dict(self._heartbeat_jobs),
                "kb": {actor: kb.snapshot() for actor, kb in self._kb.items()},
                "recall_lines": {k: list(v) for k, v in self._recall_lines.items()},
                "flashback_display": {k: list(v) for k, v in self._flashback_display.items()},
                "flashback_pool": {actor: [[t.isoformat(), line, sorted(entities)]
                                            for (t, line, entities) in pool]
                                    for actor, pool in self._flashback_pool.items()}}

    def restore_checkpoint(self, state: dict[str, Any]) -> None:
        from datetime import datetime as _dt
        self._failures = {actor: _as_int(value, f"failures[{actor}]") for actor, value in state.get("transient_failures", {}).items()}
        self._operational_facts = {actor: [dict(x) for x in facts]
                                   for actor, facts in state.get("operational_facts", {}).items()}
        self.stop_reason = None
        self._rejection_sequence = _as_int(state.get("rejection_sequence", 0), "rejection_sequence")
        self._turns = _as_int(state.get("turn_sequence", 0), "turn_sequence")
        self._repetition.restore(state.get("repetition", {}))
        self._rep_scan = _as_int(state.get("rep_scan", len(self.world.event_log)), "rep_scan")
        self._npc_pending = dict(state.get("npc_pending", {}))
        self._npc_scan = _as_int(state.get("npc_scan", len(self.world.event_log)), "npc_scan")
        self._extras_scan = _as_int(state.get("extras_scan", len(self.world.event_log)), "extras_scan")
        self._wake_scan = _as_int(state.get("wake_scan", len(self.world.event_log)), "wake_scan")
        self._wake_times = [_dt.fromisoformat(t) for t in state.get("wake_times", ())]
        self._last_speech = {k: _dt.fromisoformat(t) for k, t in state.get("last_speech", {}).items()}
        self._heartbeat_jobs = {k: _as_int(v, f"heartbeat[{k}]") for k, v in state.get("heartbeat_jobs", {}).items()}
        self._extras = {name: {**x, "last_active": _dt.fromisoformat(x["last_active"])}
                        for name, x in state.get("extras", {}).items()}
        self._recall_lines = {k: list(v) for k, v in state.get("recall_lines", {}).items()}
        self._flashback_display = {k: list(v) for k, v in state.get("flashback_display", {}).items()}
        self._flashback_pool = {
            actor: [(_dt.fromisoformat(row[0]), row[1], frozenset(row[2]))
                    for row in pool]
            for actor, pool in state.get("flashback_pool", {}).items()}
        if state.get("kb"):
            from .kb import ActorKB
            for actor, snap in state["kb"].items():
                if actor in self.world.actors:
                    self._kb[actor] = ActorKB.from_snapshot(snap, self.world.now)
