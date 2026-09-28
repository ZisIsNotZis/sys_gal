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
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from .adapter import parse_decision
from .agent_state import PrivateState
from .kernel import (ActionRejected, Intention, TICK_SECONDS,
                     WAKE_EVENT_KINDS, World)
from .npc_agent import (build_extra_briefing, build_extra_system_prompt,
                        extra_heard_speech_since, extra_scene_transcript,
                        generate_stranger_name, sample_extra)
from .prompt import render_world_message, _event_sentence
from .kb import CONTACT_KEY
from .repetition import RepetitionMonitor

AgentFn = Callable[[PrivateState, dict, list[dict]], Any]


class ExtraCall(Protocol):
    """The v4 extras provider shape: an object exposing chat_with_tools
    (legacy v3 callers may instead pass a bare callable — both are accepted
    by AsyncEngine.extra_call)."""

    def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict: ...

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
                 system: Any = None, *, extra_call: ExtraCall | Callable | None = None,
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
        if self.system is not None:
            # 案件默认已接下（用户裁决 2026-09-10）：无 accept/decline 仪式。
            self.system.auto_accept(world)
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
        from .action_schema import TOOLS as _TOOLS_SNAPSHOT
        self._tools_snapshot = [dict(tool) for tool in _TOOLS_SNAPSHOT]
        self._extras: dict[str, dict[str, Any]] = {}
        self._extra_tasks: dict[str, asyncio.Task] = {}
        # Ticket 22: an extra whose answer is in flight pins the world clock
        # (same 1-tick skew rule as MC decisions) — provider wall time must
        # never turn into minutes of fast-forwarded world time.
        self._extra_inflight: dict[str, datetime] = {}
        # Asks whose passer-by spawns at the utterance's completion tick,
        # keyed by the action_started event id the completion will carry.
        self._pending_spawns: dict[int, dict[str, Any]] = {}
        self._failures: dict[str, int] = {actor: 0 for actor in world.actors}
        self._turns = 0
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
        # Last chain's tool-result text, folded into the next turn's mention
        # haystack (V4-AGENT-INTERFACE §3): what you just read is what you are
        # thinking about.
        self._last_tool_text: dict[str, str] = {}
        self._recall_lines: dict[str, list[str]] = {}
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
        # world_stops 闩锁地板（issue 26）：检查点日志里已消费的历史标记
        # （时刻 <= 本轮起点）不再触发停机；只有未来的日界标记才置闩。
        self._stops_latch_floor: datetime = self.world.now
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

    def _sync_contacts(self, actor_id: str) -> None:
        """Mirror the actor's open contact rows into known_contacts (T3 裁决).

        The kernel gates remote contact by ``known_contacts`` and stays
        KB-free; the engine is the only KB-aware component, so it derives the
        addressable formal names from `!contact` rows before each turn. Called
        after restore as well, so a resumed notebook keeps its contacts."""
        kb = self._kb.get(actor_id)
        actor = self.world.actors.get(actor_id)
        if kb is None or actor is None:
            return
        from .kb import normalize
        names: set[str] = set()
        alias_targets: dict[str, set[str]] = {}
        alias_spellings: dict[str, set[str]] = {}
        for row in kb.snapshot()["rows"]:
            if row.get("status", "open") != "open":
                continue
            keys = [str(k) for k in row.get("keys", [])]
            if CONTACT_KEY not in keys:
                continue
            texts = [k for k in keys if not k.startswith("!")]
            if not texts:
                continue
            # First text key is the formal name; only registered people can be
            # addressable. Nicknames remain private to this actor.
            formal = texts[0]
            if formal not in self.world.actors or formal == actor_id:
                continue
            names.add(formal)
            for alias in texts[1:]:
                norm = normalize(alias)
                alias_targets.setdefault(norm, set()).add(formal)
                alias_spellings.setdefault(norm, set()).add(alias)
        formal_names = {normalize(name): name for name in names}
        aliases: dict[str, str] = {}
        for norm, targets in alias_targets.items():
            if len(targets) != 1:
                continue
            formal = next(iter(targets))
            collision = formal_names.get(norm)
            if collision is not None and collision != formal:
                continue
            # Store one display spelling for each normalized personal alias;
            # otherwise equivalent spellings could look like ambiguous names.
            alias = sorted(alias_spellings[norm])[0]
            aliases[alias] = formal
        actor.known_contacts = names
        actor.contact_aliases = aliases

    def _init_kb(self, now: datetime) -> None:
        """V4-AGENT-INTERFACE §6: build each actor's KB from the manifest's
        kb: seed rows (engine-owned memory; the session never carries it).

        A restored checkpoint already carries each actor's lived KB —
        ``restore_checkpoint`` runs before ``run`` — so those actors are left
        untouched; only actors without a restored notebook are seeded."""
        if not self._kb_seeds:
            return
        from .kb import ActorKB
        for actor, rows in self._kb_seeds.items():
            if actor in self.world.actors and actor not in self._kb:
                self._kb[actor] = ActorKB(
                    actor, rows, now, valid_contact_names=set(self.world.actors))

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
        """True when no actor can still create an event on its own. An extra
        with an answer in flight still owns an event (ticket 22) — the clock
        must not jump to stop_at over its head."""
        return (not self._inflight and not self._extra_inflight
                and not self._has_pending_turns() and not self._any_ready())

    def _has_pending_turns(self) -> bool:
        """True when some actor owes a turn at the current moment (woken or
        interrupted but not yet polled/deciding). Time must not advance past
        such an actor — its perception belongs to now. Deliberating actors
        are excluded: their moment is governed by the decision horizon
        (V4-ENGINE §2.3), not by readiness."""
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
        """Schedule open scheduled rows (`!at=` keys) as kernel queue jobs
        (V4-AGENT-INTERFACE §4): the kernel fires them on time (robust against
        DES jumps), the engine turns the private reminder_due event into a
        notice and auto-closes the row when it is perceived."""
        from .kb import format_reminder_time, key_id
        for actor_id, kb in self._kb.items():
            if actor_id not in self.world.actors:
                continue
            for row in kb.scheduled_rows():
                rid = key_id(row.keys)
                if (actor_id, rid) in self._reminder_jobs:
                    continue
                if row.at is None or row.at <= self.world.now:
                    continue
                self._reminder_jobs[(actor_id, rid)] = self.world.schedule_reminder(
                    actor_id, row.at, rid, row.desc, format_reminder_time(row.at))

    def _after_advance(self) -> None:
        for event in self.world.event_log[self._rep_scan:]:
            if event.kind == "message_delivered":
                self._repetition.note_message_received(
                    str(event.payload.get("target")), event.actor or "")
            if (event.kind == "world_event" and event.payload.get("event") == "world_stops"
                    and (self._stops_latch_floor is None or event.time > self._stops_latch_floor)):
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
            # Extras wake only on someone else's wake-class event or a
            # parked follow-up question; their own speech bookkeeping must
            # not re-arm them (V4-CAST §1).
            if self._role(actor) == "extra":
                info = self._extras.get(actor)
                ready = (self.world.has_external_wakeup(actor)
                         or bool(info and info.get("pending_question")))
            else:
                ready = self._ready_now(actor)
            if ready:
                event.set()
        self._scheduler_wake.set()

    def _ready_now(self, actor_id: str) -> bool:
        a = self.world.actors.get(actor_id)
        if a is None:
            return False
        if a.pending is not None:
            return True
        if a.busy_until and a.busy_until > self.world.now:
            return False
        if actor_id in self._force_turn or actor_id in self._npc_pending:
            return True
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
            self._sync_contacts(actor_id)
            director = (self.director_brief(actor_id)
                        if self.director_brief and self._role(actor_id) == "npc" and npc_reason
                        else None)
            text = render_world_message(perception, affordances, observer=actor_id,
                                        knowledge_lines=knowledge_lines, director=director)
            decide_task = loop.create_task(asyncio.to_thread(
                self._decide_v4, actor_id, text))
        else:
            decide_task = loop.create_task(asyncio.to_thread(
                self._decide, actor_id, perception, affordances))
        intention, result, error = None, "none", None
        chain_calls: list[dict[str, Any]] | None = None
        spoken_text = ""
        try:
            decision = await asyncio.wait_for(asyncio.shield(decide_task),
                                              timeout=self.decision_timeout)
            updates: dict[str, Any] = {}
            if v4:
                decision_map = decision if isinstance(decision, dict) else {"text": "", "calls": decision or []}
                spoken_text = str(decision_map.get("text", "")).strip()
                chain_calls = list(decision_map.get("calls") or [])
            elif isinstance(decision, tuple):
                intention, updates = decision
            else:
                intention = decision if not isinstance(decision, list) else None
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
            # T1 文本即说话: the model's plain text output is spoken aloud to
            # everyone present (docs §4). Committed before the tool chain so
            # the chronicle reads speak-then-act.
            if spoken_text:
                self.world.submit(Intention(actor_id, "speak",
                                            {"text": spoken_text}, world.version))
                limit = world.actors[actor_id].busy_until
                if limit is not None and self._stop_horizon is not None:
                    limit = min(limit, self._stop_horizon)
                if limit is not None and limit > world.now:
                    world.advance(until=limit)
            self._execute_chain(actor_id, chain_calls or [], perception,
                                affordances, version_before,
                                spoken_text=spoken_text)
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
        """#knowledge block: KB rows whose keys are mentioned in what the actor
        is currently reading/hearing/saying (V4-AGENT-INTERFACE §3), plus due
        scheduled-row notices (auto-closed after notification, §4).

        The haystack is this turn's world message with the knowledge block
        removed — so a surfaced row's own description cannot re-trigger its
        neighbours — plus the previous turn's tool-result text."""
        if actor_id not in self._kb:
            return []
        base = render_world_message(perception, affordances, observer=actor_id,
                                    knowledge_lines=[])
        haystack = base + "\n" + self._last_tool_text.get(actor_id, "")
        kb = self._kb[actor_id]
        lines = list(kb.due_lines(self.world.now, haystack))
        lines.extend(self._recall_lines.pop(actor_id, []))
        lines.extend(self._pending_notices.pop(actor_id, []))
        for event in perception.get("events", []):
            if event.get("kind") != "reminder_due":
                continue
            payload = event.get("payload", {})
            kb.close_scheduled(str(payload.get("row_id", "")))
            lines.append(f"[!at={payload.get('rendered', '')}]: "
                         f"{payload.get('desc', '')}（到期）")
        return lines

    def _flashback_query(self, actor_id: str, entity: str) -> list[str]:
        """flashback tool: recall everything the actor knows or lived that
        concerns ``entity``. The KB's own rows come first — pre-run life has no
        event line — then the delivered-history pool. Matching is the same key
        matcher as replay, so aliases registered as keys just work."""
        entity = (entity or "").strip()
        if not entity:
            return []
        ordered: list[str] = []
        seen: set[str] = set()
        kb = self._kb.get(actor_id)
        if kb is not None:
            for line in kb.match_rows([entity]):
                if line not in seen:
                    seen.add(line)
                    ordered.append(line)
        # Ticket 25: pre-run history is REAL events in the world's history
        # log — replay the ones visible to this actor exactly like memories
        # of the past. The runtime delivered pool still follows.
        for event in self.world.history_log:
            if actor_id not in event.visible_to:
                continue
            detail = (str(event.payload.get("detail")
                          or event.payload.get("text")
                          or event.payload.get("notice") or "")).strip()
            if not detail:
                continue
            line = f"{event.time.strftime('%Y-%m-%d %H:%M')} {detail}"
            if line in seen:
                continue
            if entity in line:
                seen.add(line)
                ordered.append(line)
        for _, line, entities in self._flashback_pool.get(actor_id, []):
            if line in seen:
                continue
            if entities & {entity} or entity in line:
                seen.add(line)
                ordered.append(line)
        return ordered[:8]

    def _action_rejection_text(self, actor_id: str, exc: ActionRejected, name: str,
                               args: Mapping[str, Any]) -> str:
        """Keep kernel suggestions actionable without changing a recipient."""
        context = exc.context
        if name in {"text", "speak", "give"} and (
                context.get("name_resolution") or context.get("recipient_unavailable")
                or context.get("missing") == "target"):
            candidates = context.get("recipient_candidates", ())
            shown = ", ".join(str(person) for person in candidates if person)
            message = str(exc)
            if shown:
                message += f" Names in your personal knowledge or here: {shown}."
            message += " No message, speech, or transfer was redirected to another person."
            if context.get("name_resolution"):
                message += " Confirm the intended person's exact formal name or a registered personal nickname."
            elif context.get("missing") == "target":
                message += " Specify the intended recipient; do not reuse private content for a candidate."
            return message
        if name in {"text", "speak"}:
            # Shape failures can precede name resolution. A candidate list is
            # still useful, but no executable call may carry the supplied body.
            candidates = self.world._person_candidates(self.world.actors[actor_id])
            message = str(exc)
            if candidates:
                message += f" Names in your personal knowledge or here: {', '.join(candidates)}."
            return message + " No message or speech was redirected to another person."
        import json
        calls: list[dict[str, Any]] = []
        for alternative in exc.alternatives:
            text = str(alternative).strip()
            if text.startswith("move to "):
                target = text[len("move to "):].removesuffix(" (open)")
                calls.append({"name": "move", "arguments": {"target": target}})
            elif text.startswith("take "):
                calls.append({"name": "take", "arguments": {"item": text[len("take "):]}})
            elif text.startswith("read "):
                calls.append({"name": "read", "arguments": {"item": text[len("read "):]}})
            elif text.startswith("place "):
                calls.append({"name": "place", "arguments": {"item": text[len("place "):]}})
            elif text.startswith("trash "):
                calls.append({"name": "trash", "arguments": {"item": text[len("trash "):]}})
            elif text.startswith("give ") and " to " in text:
                item, target = text[len("give "):].split(" to ", 1)
                calls.append({"name": "give", "arguments": {
                    "target": target, "item": item}})
            elif text.startswith("speak to "):
                calls.append({"name": "speak", "arguments": {
                    "text": str(args.get("text") or "<your words>"),
                    "volume": "normal", "to": [text[len("speak to "):]]}})
            elif text.startswith(("text ", "send_message to ")):
                target = text[len("send_message to "):] if text.startswith("send_message to ") \
                    else text[len("text "):]
                calls.append({"name": "text", "arguments": {
                    "target": target, "text": str(args.get("text") or "<your message>")}})
        if not calls and exc.context.get("busy_until") is None and name == "wait":
            calls.append({"name": "wait", "arguments": {
                "duration_seconds": TICK_SECONDS}})
        if not calls and exc.context.get("busy_until") is None and name not in {"text", "speak", "give"}:
            for option in self.world.affordances(actor_id):
                if str(option.get("kind")) != name:
                    continue
                if name == "speak":
                    targets = [str(x) for x in option.get("to", ()) if x]
                    if targets:
                        volume = args.get("volume")
                        if not isinstance(volume, str) or volume not in {"normal", "whisper"}:
                            volume = "normal"
                        calls.append({"name": name, "arguments": {
                            "text": str(args.get("text") or "<your words>"),
                            "volume": volume,
                            "to": [targets[0]]}})
                elif name == "text":
                    target = str(option.get("target", ""))
                    if target:
                        calls.append({"name": name, "arguments": {
                            "target": target,
                            "text": str(args.get("text") or "<your message>")}})
                elif name == "leave_note":
                    calls.append({"name": name, "arguments": {
                        "text": str(args.get("text") or "<note text>")}})
                elif name == "wait":
                    calls.append({"name": name, "arguments": {
                        "duration_seconds": TICK_SECONDS}})
                else:
                    values = {key: option[key] for key in ("target", "item")
                              if key in option}
                    if values:
                        calls.append({"name": name, "arguments": values})
                if calls:
                    break
        message = str(exc)
        if calls:
            suggestions = "; ".join(json.dumps(call, ensure_ascii=False) for call in calls)
            message = f"{message} Valid call: {suggestions}."
        elif exc.alternatives:
            message = f"{message} Possible next steps: {'; '.join(exc.alternatives)}."
        return message

    def _tool_yield(self, name: str, args: Mapping[str, Any], world: World) -> str:
        """The caller-facing yield of a world action (V4-AGENT-INTERFACE §3):
        most actions yield nothing beyond the world's reaction; read and
        compare carry their content/verdict in the tool result."""
        if name == "speak":
            return "话已说出；说话动作在一个 tick 内完成。"
        if name == "text":
            return "短信已发出；一个 tick 后送达。"
        if name == "read":
            document = world.document_defs.get(str(args.get("item")), {})
            content = str(document.get("content", ""))
            annotations = document.get("annotations") or []
            if annotations:
                notes = "；".join(f"{e.get('by')}批注：{e.get('text')}" for e in annotations)
                content = f"{content}\n（记录上还有：{notes}）" if content else notes
            return content or "（这份记录没有可读的正文。）"
        if name == "leave_note":
            return "字条已留下；作者再次进入不会读到自己的字条，之后第一位非作者进入者会私下读到全文。"
        if name == "trash":
            return "已销毁。"
        if name == "place":
            return "已放在这里，他人可见可拿。"
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
                       affordances: list[dict], version_before: int,
                       *, spoken_text: str = "") -> None:
        """V4-AGENT-INTERFACE §4: execute the turn's tool calls in order —
        memory tools are engine-side and free; world actions submit through
        the kernel with time accumulating between calls; a chain with no
        world action = 发呆 1 tick; more than 8 calls truncate at the call
        boundary ("truncated: N calls dropped")."""
        world = self.world
        results: list[dict[str, Any]] = []
        failures: list[str] = []
        world_actions = 0
        full_calls = list(calls or [])
        # Every tool result must be attributable (strict gateways reject
        # tool messages without call_id): synthesize ids for calls that
        # arrive without one.
        for pos, c in enumerate(full_calls):
            if not c.get("tool_call_id"):
                c["tool_call_id"] = f"{actor_id}-chain-{pos + 1}"
        calls = full_calls[:8]
        truncated = max(0, len(full_calls) - 8)
        a = world.actors[actor_id]

        def fail(call: dict[str, Any], text: str) -> None:
            results.append({"tool_call_id": call.get("tool_call_id"), "ok": False, "text": text})
            failures.append(f"{call.get('name')}: {text}")

        for pos, call in enumerate(calls):
            name = str(call.get("name", ""))
            args = dict(call.get("arguments") or {})
            if call.get("parse_error"):
                fail(call, f"unparseable arguments: {call['parse_error']}")
                continue
            if name in {"think", "system_query", "copy", "annotate", "compare",
                        "observe", "search", "inspect", "label", "interact",
                        "open", "close", "send_message", "drop", "ask",
                        "system_accept", "system_decline"}:
                # retired tools (ticket 14 / ticket 22 / earlier rulings):
                # teach, don't fail silently — the model may carry them from
                # older sessions.
                teaching = ("ask 已合并进 speak：用 speak(to=[...], text=...) 提问，"
                            "to 可以是在场的人或 [\"陌生人\"]"
                            if name == "ask" else
                            f"unknown action '{name}' (retired); "
                            "see your tool list for the current actions")
                fail(call, teaching)
                continue
            if name == "update_memory":
                if actor_id in self._kb:
                    errs, _tel, warns = self._kb[actor_id].apply_ops(
                        args.get("rows") or [], world.now)
                    if errs:
                        fail(call, "; ".join(errs + warns))
                    else:
                        text = "已记下。" + (("\n" + "\n".join(warns)) if warns else "")
                        results.append({"tool_call_id": call.get("tool_call_id"), "ok": True,
                                        "text": text})
                else:
                    fail(call, "no notebook seeded for this actor")
                continue
            if name == "recall":
                if not args.get("keys"):
                    fail(call, "recall needs 'keys' (a list of keywords) to select rows")
                    continue
                if actor_id in self._kb:
                    lines = self._kb[actor_id].force_recall(
                        args.get("keys"), bool(args.get("closed")),
                        _as_int(args.get("limit") or 8, "limit"))
                else:
                    lines = []
                results.append({"tool_call_id": call.get("tool_call_id"), "ok": True,
                                "text": "\n".join(lines) or "（记事本里没有匹配的行。）"})
                continue
            if name == "flashback":
                lines = self._flashback_query(actor_id, str(args.get("entity") or ""))
                results.append({"tool_call_id": call.get("tool_call_id"), "ok": True,
                                "text": "\n".join(lines) or "（没有与你经历相关的可回放历史。）"})
                continue
            if name == "speak":
                # Merged ask (ticket 22): speak is the only addressed speech
                # tool. to is schema-required (present people or ["陌生人"]);
                # volume=whisper is private, normal is heard by the room.
                # Plain-text output (T1) stays the unaddressed broadcast.
                to = args.get("to")
                if not isinstance(to, list) or not to:
                    fail(call, "speak 需要 to：你要对谁说？在场的人，或 [\"陌生人\"] 向路人搭话。"
                               "对全场的发言直接回复文字即可。")
                    continue
                if not isinstance(args.get("volume"), str):
                    args.setdefault("volume", "normal")
            try:
                world.submit(Intention(actor_id, name, args, world.version))
                world_actions += 1
                results.append({"tool_call_id": call.get("tool_call_id"), "ok": True,
                                "text": self._tool_yield(name, args, world)})
                if a.busy_until and a.busy_until > world.now:
                    # The chain's own committed time: advance to the action's
                    # completion so the next call starts after it — clamped to
                    # the run's stop horizon (endpoint gate) AND to the
                    # horizon bound (ticket 23): another actor's deliberation
                    # pins the world at its moment + 1 tick. Without the
                    # clamp, instant-decision actors ratchet the clock one
                    # tick per chain while a slower actor is mid-thought —
                    # the 7:35->7:40 slip. A call that lands while its actor
                    # is still mid-action is rejected with teaching (busy);
                    # under contention chains degrade to one action per turn.
                    limit = a.busy_until
                    if self._stop_horizon is not None:
                        limit = min(limit, self._stop_horizon)
                    horizon = self._horizon_bound()
                    if horizon is not None:
                        limit = min(limit, horizon)
                    if limit > world.now:
                        world.advance(until=limit)
                if a.busy_until and self._stop_horizon is not None and a.busy_until > self._stop_horizon:
                    remaining = calls[pos + 1:]
                    # Per-call results with real ids — a tool message without
                    # call_id/name is rejected by strict gateways.
                    for rest in remaining:
                        rest_name = str(rest.get("name", ""))
                        rest_args = dict(rest.get("arguments") or {})
                        preview = World._tool_call_json(rest_name, rest_args)
                        fail(rest, (f"not executed: the run endpoint was reached while the prior "
                                    f"action was due at {a.busy_until.isoformat()}; if resumed, "
                                    f"retry after that action completes with {preview}."))
                    break  # the run's endpoint cut this chain short
                if (a.pending is None and a.busy_until and a.busy_until > world.now
                        and pos + 1 < len(calls)):
                    # A horizon-clipped action also blocks free memory tools:
                    # the remaining chain has not reached its execution point.
                    # Handle this before the next iteration's memory fast paths.
                    for rest in calls[pos + 1:]:
                        rest_name = str(rest.get("name", ""))
                        rest_args = dict(rest.get("arguments") or {})
                        preview = World._tool_call_json(rest_name, rest_args)
                        active = str((a.current_action or {}).get("payload", {}).get("action", "action"))
                        fail(rest, (f"not executed: current {active} completes at "
                                    f"{a.busy_until.isoformat()}; retry after completion "
                                    f"with {preview}."))
                    break
            except ActionRejected as exc:
                fail(call, self._action_rejection_text(actor_id, exc, name, args))
                busy_until = exc.context.get("busy_until")
                if busy_until is not None:
                    # Later calls in a chain whose actor is still busy were
                    # not attempted. Return a distinct result for every call id
                    # with a concrete retry shape and the same real deadline.
                    for rest in calls[pos + 1:]:
                        rest_name = str(rest.get("name", ""))
                        rest_args = dict(rest.get("arguments") or {})
                        preview = World._tool_call_json(rest_name, rest_args)
                        fail(rest, (f"not executed: the current action completes at {busy_until}; "
                                    f"retry after completion with {preview}."))
                    break
            except Exception as exc:
                fail(call, f"{type(exc).__name__}: {exc}")
            if a.pending is not None:
                # A reminder (or another force interrupt) suspended the chain:
                # the actor must answer continue-or-cancel before anything else.
                pending = a.pending or {}
                pending_payload = pending.get("payload", {})
                interrupted_action = str(pending_payload.get("action", "action"))
                interrupted_by = str(pending.get("interrupted_by", "someone"))
                remaining_seconds = int(pending.get("remaining_seconds", 0) or 0)
                for rest in calls[pos + 1:]:
                    rest_name = str(rest.get("name", ""))
                    rest_args = dict(rest.get("arguments") or {})
                    preview = World._tool_call_json(rest_name, rest_args)
                    fail(rest, (f"not executed: '{interrupted_action}' was interrupted by "
                                f"'{interrupted_by}' with {remaining_seconds} seconds remaining. "
                                'First resolve it with {"name": "continue_action", "arguments": {}} '
                                'or {"name": "abandon_action", "arguments": {}}; then retry '
                                f"with {preview}."))
                break
        if truncated:
            # Per-call results with each dropped call's real id (strict
            # gateways reject tool messages without call_id).
            for rest in full_calls[8:]:
                rest_name = str(rest.get("name", ""))
                rest_args = dict(rest.get("arguments") or {})
                preview = World._tool_call_json(rest_name, rest_args)
                fail(rest, ("not executed: over the 8-calls-per-turn limit; "
                            f"retry next turn with {preview}."))
            failures.append(f"truncated: {truncated} calls dropped")
        # Auto-wait (ticket 22, default on): after speaking to someone you
        # stay put for ~2 ticks; a reply wakes you early (V4-ENGINE §3), so
        # control returns with the answer heard — or with explicit silence at
        # the 2-tick mark. Opt out per call with wait_response=false.
        a_after = world.actors[actor_id]
        idle_now = a_after.busy_until is None or a_after.busy_until <= world.now
        if world_actions and idle_now:
            successful_ids = {str(r.get("tool_call_id")) for r in results if r.get("ok")}
            spoke_to = [c for c in calls
                        if str(c.get("tool_call_id")) in successful_ids
                        and str(c.get("name")) in {"speak", "text"}
                        and (str(c.get("name")) != "speak"
                             or isinstance((c.get("arguments") or {}).get("to"), list))
                        and (c.get("arguments") or {}).get("wait_response", True)]
            if spoke_to:
                try:
                    world.submit(Intention(actor_id, "wait",
                                           {"duration_seconds": 2 * TICK_SECONDS},
                                           world.version))
                    # Speech/text has completed before this separate wait
                    # begins. Keep its purpose in current_action, including
                    # checkpoints, so it is never described as continued speech.
                    response_to: list[str] = []
                    for call in spoke_to:
                        call_args = call.get("arguments") or {}
                        recipients = (call_args.get("to", [])
                                      if call.get("name") == "speak"
                                      else [call_args.get("target")])
                        response_to.extend(str(x) for x in recipients if x)
                    response_to = list(dict.fromkeys(response_to))
                    current = a_after.current_action
                    if current is not None:
                        current["waiting_for_response"] = True
                        current["response_to"] = response_to
                        current["response_action"] = str(spoke_to[-1].get("name"))
                    until = (a_after.busy_until.strftime("%H:%M")
                             if a_after.busy_until else "the end of the wait")
                    note = (f"话已说完；你原地等{'、'.join(response_to) or '回应'}回话，"
                            f"最迟到 {until}，有人回应会提前叫醒你。"
                            "说完就走请用 wait_response=false。")
                    # Fold the state into a real tool result; synthetic results
                    # without call_id are rejected by strict gateways.
                    last_id = spoke_to[-1].get("tool_call_id")
                    for entry in reversed(results):
                        if entry.get("tool_call_id") == last_id and entry.get("ok"):
                            entry["text"] = f"{entry['text']} {note}"
                            break
                except ActionRejected:
                    pass
        if not world_actions:
            # 一回合没有任何世界动作 = 发呆 1 tick (V4-AGENT-INTERFACE §0/§4).
            try:
                world.submit(Intention(actor_id, "wait",
                                       {"duration_seconds": TICK_SECONDS},
                                       world.version))
            except ActionRejected:
                pass
        # Ticket 23: an NPC woken to answer (e.g. by a delivered text) that
        # spent its turn recalling (flashback/recall) but produced no world
        # action would park with the answer uncomposed — nothing would wake
        # it again. Give it exactly one follow-up turn.
        memory_only = (self._role(actor_id) == "npc" and not world_actions
                       and not spoken_text.strip()
                       and any(str(c.get("name")) in {"flashback", "recall"}
                               for c in calls))
        if memory_only and actor_id not in self._force_turn:
            self._force_turn.add(actor_id)
        deliver = getattr(self.agents[actor_id], "deliver_tool_results", None)
        if deliver is not None:
            deliver(results)
        self._last_tool_text[actor_id] = "\n".join(
            str(r.get("text", "")) for r in results if r.get("text"))
        self._remember_lines(actor_id, perception)
        result = "submitted" if (world_actions or calls) else "none"
        self._repetition.note_turn(actor_id, None, result)
        recorded = (Intention(actor_id, str(calls[0].get("name", "unknown")),
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
                                      interrupt=intention.interrupt,
                                      uninterruptable=intention.uninterruptable)
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
        """Caps only COLD-SCENE speculative wakes (ticket 24): starting a
        conversation out of nothing on a quiet map is the expensive path.
        Event-driven wakes (speech, arrivals, directed questions) are never
        budgeted — reacting to what actually happened is an actor's job."""
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
                # Ambient nearby speech (ticket 22): co-located NPCs are free
                # to react per persona — usually nothing, but their persona
                # decides. Budget-bound.
                if event.actor and event.actor in self.world.actors:
                    self._wake_nearby_npcs(
                        event.actor,
                        f"{event.actor}说：{str(event.payload.get('text', ''))[:40]}")
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
            elif event.actor and event.actor in self.world.actors and (
                    event.kind in {"enter", "item_given", "extra_arrived"}
                    or (event.kind == "action_started"
                        and event.payload.get("action") in {"take", "place"})):
                summary = {"enter": f"{event.actor} 进来了",
                           "item_given": f"{event.actor} 递出了东西",
                           "extra_arrived": f"{event.actor} 出现在这里",
                           "take": f"{event.actor} 拿起了 {event.payload.get('item', '一样东西')}",
                           "place": f"{event.actor} 放下了 {event.payload.get('item', '一样东西')}"}.get(
                    event.kind, f"{event.actor} 有动作")
                self._wake_nearby_npcs(event.actor, f"附近发生：{summary}")

    def _wake_nearby_npcs(self, source: str, reason: str) -> None:
        """Wake co-located NPCs for a nearby happening (ticket 22). They are
        free agents: usually the right response is nothing, but their persona
        decides (e.g. someone taking what isn't theirs). Budget-bound like
        every other NPC wake."""
        if source not in self.world.actors:
            return
        loc = self.world.actors[source].location
        for npc_id, actor in self.world.actors.items():
            if (npc_id != source and self._role(npc_id) == "npc"
                    and actor.location == loc and npc_id not in self._npc_pending
                    and not (actor.busy_until and actor.busy_until > self.world.now)):
                # Ticket 24: no global wake budget. NPCs are actors —
                # silence must be a choice made in character, never a
                # counter running out. The pending-dedup above still
                # prevents stacking while an NPC already owes a turn.
                self._npc_pending[npc_id] = reason

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
        # Ticket 22: a passer-by spawns when the utterance LANDS (the speak's
        # action_completed tick), never at submit time. stranger_asked parks
        # here keyed by its cause; the matching completion triggers the spawn.
        done = {e.cause for e in new_events
                if e.kind == "action_completed" and e.cause is not None}
        now = self.world.now
        for cause, ask in list(self._pending_spawns.items()):
            if cause in done:
                del self._pending_spawns[cause]
                self._spawn_extra(ask["asker"], ask["question"], loop)
            elif (now - ask["parked"]).total_seconds() > 5 * 60:
                del self._pending_spawns[cause]   # interrupted utterance
        for event in new_events:
            if event.kind == "speech" and event.actor:
                delivered = event.visible_to
                for name, info in self._extras.items():
                    if name != event.actor and name in delivered:
                        info["last_active"] = self.world.now
                        info["pending_heard_speech"] = True
                        self._wake_events[name].set()
            if event.kind == "stranger_asked" and event.actor:
                asker = event.actor
                existing = [x for x in self._extras.values()
                            if x["partner"] == asker]
                if existing:
                    # Conversation continuation: the MC asked the same extra
                    # again — park the new question and wake it, so the
                    # follow-up is answered (V4-CAST §1). One conversation
                    # per MC still holds.
                    info = existing[0]
                    info["pending_question"] = str(event.payload.get("question", ""))
                    info["last_active"] = self.world.now
                    name = [n for n, x in self._extras.items() if x is info][0]
                    self._wake_events[name].set()
                    continue
                if self.extra_call is None or asker not in self.world.actors:
                    continue
                if event.cause is None or event.cause in done:
                    # Legacy event, or the completion is in this very batch
                    # (the asker's own chain advance): the utterance has
                    # landed — spawn now, not in a later pass.
                    self._spawn_extra(asker, str(event.payload.get("question", "")), loop)
                    continue
                self._pending_spawns[event.cause] = {
                    "asker": asker,
                    "question": str(event.payload.get("question", "")),
                    "parked": self.world.now}

    def _spawn_extra(self, asker: str, question: str, loop: asyncio.AbstractEventLoop) -> None:
        """Create the conversation-scoped stranger and start its answer loop.
        Called at the ask's completion tick, so extra_arrived carries the
        same timestamp as the moment the question was heard."""
        if (self.extra_call is None or asker not in self.world.actors
                or any(x["partner"] == asker for x in self._extras.values())):
            return
        location = self.world.actors[asker].location
        entry = sample_extra(self.world.locations[location].extras or
                             [{"fragment": "一个路过的同学", "rarity": "common",
                               "knowledge_notes": ""}])
        name = generate_stranger_name()
        while name in self.world.actors:
            name = generate_stranger_name()
        arrival_index = len(self.world.event_log)
        self.world.add_extra(name, location)
        scene_start = arrival_index + 1
        self._extras[name] = {"fragment": str(entry.get("fragment", "路人")),
                              "knowledge_notes": str(entry.get("knowledge_notes", "")),
                              "partner": asker, "last_active": self.world.now,
                              "rarity": str(entry.get("rarity", "common")),
                              "start": scene_start,
                              "context_cursor": scene_start,
                              "pending_question": question,
                              "pending_heard_speech": False,
                              "system_prompt": build_extra_system_prompt(
                                  str(entry.get("fragment", "路人")),
                                  str(entry.get("knowledge_notes", "")), location)}
        self._wake_events[name] = asyncio.Event()
        self._extra_tasks[name] = loop.create_task(self._extra_loop(name, question))

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
        info = self._extras.get(name)
        if info is None:
            return
        info["pending_question"] = question
        try:
            while name in self._extras and name in self.world.actors and not self.stop_reason:
                info = self._extras.get(name)
                if info is None:
                    return
                asked = str(info.pop("pending_question", "") or "")
                info.pop("pending_heard_speech", False)
                # Ticket 22: while the answer is in flight the world clock
                # pins at the question moment (same 1-tick skew rule as MC
                # decisions) — the provider's wall latency must not turn
                # into fast-forwarded world minutes.
                self._extra_inflight[name] = self.world.now
                try:
                    await self._extra_turn(name, asked)
                finally:
                    self._extra_inflight.pop(name, None)
                    self._scheduler_wake.set()
                # The extra's own speech is visible to itself; drain its
                # cursor so only NEW events (the partner's reply, an
                # arrival) wake it again — otherwise it chatters forever.
                if name in self._extras and name in self.world.actors:
                    self.world.dismiss_events(name)
                while name in self._extras and not (
                        self.world.has_external_wakeup(name)
                        or self._extras.get(name, {}).get("pending_question")
                        or self._extras.get(name, {}).get("pending_heard_speech")):
                    if self.stop_reason:
                        return
                    await event.wait()
                    event.clear()
                event.clear()
        except asyncio.CancelledError:
            raise
        finally:
            self._extra_inflight.pop(name, None)

    async def _extra_turn(self, name: str, question: str) -> None:
        info = self._extras[name]
        location = self.world.actors[name].location
        events = self.world.event_log
        needs_response = bool(question) or extra_heard_speech_since(
            events, listener=name, start=int(info.get("context_cursor", info["start"])))
        info["context_cursor"] = len(events)
        transcript = extra_scene_transcript(
            events, listener=name, start=int(info["start"]),
            opening_question=question, questioner=str(info["partner"]))
        system = str(info["system_prompt"])
        briefing = build_extra_briefing(transcript=transcript)
        intention_calls: list[dict[str, Any]] = []
        result, error = "none", ""
        try:
            if not needs_response:
                pass
            elif hasattr(self.extra_call, "chat_with_tools"):
                from .npc_agent import extra_tool_calls
                extra_call = self.extra_call
                assert extra_call is not None
                intention_calls = await asyncio.to_thread(
                    extra_tool_calls, extra_call, system, briefing)
            else:
                legacy_extra = self.extra_call
                assert legacy_extra is not None and callable(legacy_extra)
                messages = [{"role": "system", "content": system}]
                if briefing:
                    messages.append({"role": "user", "content": briefing})
                raw = await asyncio.to_thread(legacy_extra, messages)
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
            result = "submitted" if spoke else "none"
        except ActionRejected as exc:
            result, error = "rejected", str(exc)
        except Exception as exc:
            result, error = "agent_error", f"{type(exc).__name__}: {exc}"
        # Trace.record_agent requires a real Intention (it reads .actor/.kind/
        # .args); a bare dict made every extra turn die after submitting its
        # speech, so no extra turn was ever recorded (ticket-21).
        trace_intention = Intention(name, "speak",
                                    {"calls": intention_calls},
                                    self.world.version)
        self.trace.record_agent(state=PrivateState(name),
                                perception={"observer": name, "time": self.world.now.isoformat(),
                                            "location": location, "events": [], "inbox": [],
                                            "nearby_actors": [], "nearby_items": []},
                                affordances=[], intention=trace_intention,
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
                "last_tool_text": dict(self._last_tool_text),
                "flashback_pool": {actor: [[t.isoformat(), line, sorted(entities)]
                                            for (t, line, entities) in pool]
                                    for actor, pool in self._flashback_pool.items()},
                # Ticket 25: the checkpoint carries everything needed to
                # reproduce — each actor's session (system prompt at
                # messages[0]) and the tools array as they were at this point.
                "sessions": {actor: snap for actor in self.world.actors
                             if (snap_fn := getattr(self.agents.get(actor),
                                                    "session_snapshot", None))
                             and (snap := snap_fn())},
                "prompts": {actor: ((sess.messages[0] or {}).get("content", "")
                                    if (sess := getattr(self.agents.get(actor),
                                                        "session_obj", None))
                                    and getattr(sess, "messages", None) else "")
                            for actor in self.world.actors},
                "tools": list(self._tools_snapshot)}

    def restore_checkpoint(self, state: dict[str, Any]) -> None:
        from datetime import datetime as _dt
        self._failures = {actor: _as_int(value, f"failures[{actor}]") for actor, value in state.get("transient_failures", {}).items()}
        self._operational_facts = {actor: [dict(x) for x in facts]
                                   for actor, facts in state.get("operational_facts", {}).items()}
        self.stop_reason = None
        # 已触发过的 world_stops 属于已消费的弧线历史：恢复后只对晚于
        # 恢复时刻的 world_stops 事件置闩（跨检查点续跑不重复停机）。
        self._world_stops_seen = False
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
        self._last_tool_text = {k: str(v) for k, v in state.get("last_tool_text", {}).items()}
        self._flashback_pool = {
            actor: [(_dt.fromisoformat(row[0]), row[1], frozenset(row[2]))
                    for row in pool]
            for actor, pool in state.get("flashback_pool", {}).items()}
        if state.get("kb"):
            from .kb import ActorKB
            for actor, snap in state["kb"].items():
                if actor in self.world.actors:
                    self._kb[actor] = ActorKB.from_snapshot(
                        snap, self.world.now, valid_contact_names=set(self.world.actors))
        # Ticket 25: sessions travel inside the checkpoint. The agent wrappers
        # expose restore_session so the live closures rebind to the restored
        # V4Session (containment here; the resume driver may also do it).
        for actor, snap in (state.get("sessions") or {}).items():
            agent = self.agents.get(actor)
            restore = getattr(agent, "restore_session", None)
            if restore is not None:
                restore(snap)
