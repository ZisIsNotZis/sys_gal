"""Generic event-driven agent runner; it knows no story semantics."""

from __future__ import annotations

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, wait
import time
from typing import Any, Callable, Iterable

from .agent_state import PrivateState, validate_private_updates
from .kernel import ActionRejected, Intention, World
from .repetition import RepetitionMonitor
from .system import Ledger
from .adapter import parse_decision
from .npc_agent import (build_extra_briefing, build_extra_system_prompt,
                         generate_stranger_name, public_mc_digest,
                         sample_extra, schedule_digest)
from .trace import Trace

AgentFn = Callable[[PrivateState, dict, list[dict]], Intention | tuple[Intention | None, dict[str, Any]] | None]


def _as_int(value, what="value"):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {what}: {value!r}") from exc


class Runner:
    def __init__(self, world: World, agents: dict[str, AgentFn], states: dict[str, PrivateState], trace: Trace, system: Ledger | None = None, *, max_workers: int | None = None, decision_timeout: float = 60.0, checkpoint: Callable[[], None] | None = None, fail_fast: bool = False, max_transient_failures: int = 2, retry_delay_seconds: int = 60, max_wall_seconds: float | None = None, repetition: RepetitionMonitor | None = None,
            extra_call: Callable | None = None,
            cold_ticks: int = 6, npc_wake_budget: int = 12,
            extra_idle_seconds: int = 600) -> None:
        if set(agents) != set(world.actors) or set(states) != set(world.actors):
            raise ValueError("one agent and private state are required for every actor")
        self.world, self.agents, self.states, self.trace, self.system = world, agents, states, trace, system
        if self.system is not None:
            # 案件默认已接下（用户裁决 2026-09-10）：无 accept/decline 仪式。
            self.system.auto_accept(world)
        self.stop_reason: str | None = None
        # inner telemetry (V4-DESIGN 首验日反馈 #5): count submitted turns
        # without a monologue; remind each actor once, never reject.
        self._inner_missing = 0
        self._inner_reminded: set[str] = set()
        # V4-CAST: two-tier cast state.
        self._npc_pending: dict[str, str] = {}
        self._wake_times: list = []
        self._last_speech: dict = {}
        self._npc_scan = 0
        self._extras_scan = 0
        self._extras: dict[str, dict] = {}
        self._cold_woken: dict[str, Any] = {}
        self.extra_call = extra_call
        self.cold_ticks = _as_int(cold_ticks, "cold_ticks")
        self.npc_wake_budget = _as_int(npc_wake_budget, "npc_wake_budget")
        self.extra_idle_seconds = _as_int(extra_idle_seconds, "extra_idle_seconds")
        self.max_workers = max_workers or len(agents)
        self.decision_timeout = decision_timeout
        self.checkpoint = checkpoint
        self.fail_fast = fail_fast
        if max_transient_failures < 0:
            raise ValueError("max_transient_failures must be non-negative")
        self.max_transient_failures = max_transient_failures
        if retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")
        self.retry_delay_seconds = retry_delay_seconds
        if max_wall_seconds is not None and max_wall_seconds <= 0:
            raise ValueError("max_wall_seconds must be positive")
        self.max_wall_seconds = max_wall_seconds
        self._failed_batches = 0
        self._transient_failures: dict[str, int] = {actor: 0 for actor in world.actors}
        self._operational_facts: dict[str, list[dict[str, Any]]] = {actor: [] for actor in world.actors}
        self._rejection_sequence = 0
        self._turn_sequence = 0
        self._retry_context: dict[str, tuple[dict[str, Any], list[dict[str, Any]], str]] = {}
        self._waiting: set[str] = set()
        self._repetition = repetition if repetition is not None else RepetitionMonitor()
        self._rep_scan = 0

    def checkpoint_state(self) -> dict[str, Any]:
        return {"waiting": sorted(self._waiting), "transient_failures": dict(self._transient_failures),
                "operational_facts": {actor: [dict(x) for x in facts]
                                       for actor, facts in self._operational_facts.items()},
                "stop_reason": self.stop_reason, "rejection_sequence": self._rejection_sequence,
                "turn_sequence": self._turn_sequence, "retry_context": dict(self._retry_context),
                "repetition": self._repetition.state(), "rep_scan": self._rep_scan,
                "npc_pending": dict(self._npc_pending),
                "npc_scan": self._npc_scan, "extras_scan": self._extras_scan,
                "extras": {name: {"fragment": x["fragment"], "knowledge_notes": x["knowledge_notes"],
                                   "partner": x["partner"],
                                   "last_active": x["last_active"].isoformat(),
                                   "rarity": x["rarity"], "start": x["start"]}
                            for name, x in self._extras.items()},
                "wake_times": [t.isoformat() for t in self._wake_times],
                "last_speech": {k: t.isoformat() for k, t in self._last_speech.items()}}

    def restore_checkpoint(self, state: dict[str, Any]) -> None:
        if set(state.get("transient_failures", {})) != set(self.world.actors):
            raise ValueError("checkpoint runner actor set does not match world")
        self._waiting = set(state.get("waiting", ()))
        self._transient_failures = {actor: _as_int(value, f"failures[{actor}]")
                                    for actor, value in state["transient_failures"].items()}
        self._operational_facts = {actor: [dict(x) for x in facts]
                                   for actor, facts in state.get("operational_facts", {}).items()}
        self.stop_reason = state.get("stop_reason")
        self._rejection_sequence = _as_int(state.get("rejection_sequence", 0), "rejection_sequence")
        self._turn_sequence = _as_int(state.get("turn_sequence", 0), "turn_sequence")
        self._retry_context = dict(state.get("retry_context", {}))
        self._repetition.restore(state.get("repetition", {}))
        self._rep_scan = _as_int(state.get("rep_scan", len(self.world.event_log)), "rep_scan")
        self._npc_pending = dict(state.get("npc_pending", {}))
        self._npc_scan = _as_int(state.get("npc_scan", len(self.world.event_log)), "npc_scan")
        self._extras_scan = _as_int(state.get("extras_scan", len(self.world.event_log)), "extras_scan")
        from datetime import datetime as _dt
        self._wake_times = [_dt.fromisoformat(t) for t in state.get("wake_times", ())]
        self._last_speech = {k: _dt.fromisoformat(t) for k, t in state.get("last_speech", {}).items()}
        self._extras = {name: {**x, "last_active": _dt.fromisoformat(x["last_active"])}
                        for name, x in state.get("extras", {}).items()}

    def run(self, *, stop_at: datetime | None = None, max_turns: int = 100_000) -> str:
        turns = 0
        waiting = self._waiting
        wall_started = time.monotonic()
        self._wall_started_ref = [wall_started]
        # A provider call can outlive a batch timeout. fail_fast therefore
        # stops before the next boundary rather than risking session overlap.
        while turns < max_turns:
            if self._wall_expired(wall_started):
                return self._finish_wall_deadline()
            ready = [actor_id for actor_id, actor in self.world.actors.items()
                     if (not actor.busy_until or actor.busy_until <= self.world.now)
                     and getattr(actor, "role", "mc") != "extra"
                     and (getattr(actor, "role", "mc") == "mc"
                          or actor_id in self._npc_pending)]
            eligible = []
            perceptions = {}
            affordances_by_actor = {}
            for actor_id in sorted(ready):
                if stop_at is not None and self.world.now >= stop_at:
                    return self._finish("stop_at_reached")
                if actor_id in self._npc_pending:
                    pass  # a wake reason overrides any waiting state
                elif actor_id in waiting and not self.world.has_wakeup(actor_id):
                    continue
                retry_context = self._retry_context.get(actor_id)
                if retry_context is None:
                    perception = self.world.poll(actor_id)
                    fresh = [fact for fact in self._operational_facts[actor_id]
                             if not fact.get("delivered", False)]
                    if fresh:
                        perception["operational_facts"] = [dict(fact) for fact in fresh]
                        for fact in fresh:
                            fact["delivered"] = True
                    self._turn_sequence += 1
                    perception["_turn_id"] = f"turn-{self._turn_sequence}"
                    notice = self._repetition.notice(actor_id)
                    if notice:
                        perception["situational_notice"] = notice
                    affordances = self.world.affordances(actor_id)
                    if self.system is not None:
                        affordances.extend(self.system.affordances(actor_id))
                else:
                    perception, affordances, turn_id = retry_context
                    perception = dict(perception)
                    perception["_turn_id"] = turn_id
                    affordances_by_actor[actor_id] = affordances
                perceptions[actor_id] = perception
                affordances = affordances_by_actor.get(actor_id, affordances)
                affordances_by_actor[actor_id] = affordances
                eligible.append(actor_id)
                decisions = {}
            decisions = {}
            pool = ThreadPoolExecutor(max_workers=min(self.max_workers, max(1, len(eligible))))
            futures = {actor: pool.submit(self._decide, actor, perceptions[actor], affordances_by_actor[actor]) for actor in eligible}
            try:
                # One deadline applies to the whole decision batch.  Calling
                # result(timeout=...) once per future accidentally made the
                # batch deadline N * timeout.
                remaining_wall = self._wall_remaining(wall_started)
                if remaining_wall is not None and remaining_wall <= 0:
                    done = set()
                else:
                    batch_timeout = self.decision_timeout if remaining_wall is None else min(
                        self.decision_timeout, remaining_wall)
                    done, _ = wait(futures.values(), timeout=batch_timeout)
                for actor, future in futures.items():
                    if future not in done:
                        result = ("wall_clock_deadline" if self._wall_expired(wall_started)
                                  else "decision_timeout")
                        error = ("runner wall-clock deadline exceeded"
                                  if result == "wall_clock_deadline"
                                  else "agent decision exceeded batch deadline")
                        decisions[actor] = (None, result, error)
                        continue
                    try:
                        decisions[actor] = future.result()
                    except Exception as exc:
                        failure = exc
                    else:
                        failure = None
                    if failure is not None:
                        verdict = self._classify_agent_failure(actor, failure)
                        decisions[actor] = (None, verdict[0], verdict[1] + f"{type(failure).__name__}: {failure}")
            finally:
                # Do not join here: the provider itself has a shorter socket
                # timeout. The runner records the batch result immediately.
                # In fail-fast mode it exits before a persistent session can
                # be called again, so the timed-out worker cannot overlap a
                # later decision.
                pool.shutdown(wait=False, cancel_futures=True)
            for actor_id in eligible:
                perception = perceptions[actor_id]
                affordances = affordances_by_actor[actor_id]
                version_before = self.world.version
                decision, result, error = decisions[actor_id]
                self._npc_pending.pop(actor_id, None)
                updates = {}
                if isinstance(decision, tuple):
                    intention, updates = decision
                else:
                    intention = decision
                # updates are no longer part of the protocol (V4-DESIGN §2):
                # the parser ignores them, so nothing is applied here. The
                # actor's durable self is inner + the session transcript.
                event_ids: list[int] = []
                feedback_id: str | None = None
                alternatives: list[str] = []
                if intention is not None:
                    try:
                        if intention.actor != actor_id:
                            raise ActionRejected("agent may submit only its own intention")
                        # Decisions in a batch share one immutable snapshot;
                        # rebase its version before serial application. Keep
                        # the private monologue and interrupt semantics —
                        # they survive the rebase (regression: ticket 06).
                        intention = Intention(intention.actor, intention.kind,
                                              intention.args, self.world.version,
                                              inner=intention.inner,
                                              interrupt=intention.interrupt,
                                              uninterruptable=intention.uninterruptable)
                        if not intention.inner:
                            self._inner_missing += 1
                        if intention.kind == "system_accept":
                            if self.system is None:
                                raise ActionRejected("no bound System")
                            event = self.system.accept(self.world, intention.actor, str(intention.args.get("case")))
                            event_ids.append(event.id)
                            self.trace.record_system(dict(intention.args), {"event_id": event.id, "kind": event.kind})
                        elif intention.kind == "system_decline":
                            if self.system is None:
                                raise ActionRejected("no bound System")
                            event = self.system.decline(self.world, intention.actor)
                            event_ids.append(event.id)
                            self.trace.record_system(dict(intention.args), {"event_id": event.id, "kind": event.kind})
                        elif intention.kind == "system_query":
                            if self.system is None:
                                raise ActionRejected("no bound System")
                            before = len(self.world.event_log)
                            event = self.system.ask(self.world, intention.actor, str(intention.args.get("question")))
                            event_ids.extend(e.id for e in self.world.event_log[before:])
                            self.trace.record_system(dict(intention.args), {"event_id": event.id, "kind": event.kind})
                        else:
                            before = len(self.world.event_log)
                            self.world.submit(intention)
                            event_ids.extend(e.id for e in self.world.event_log[before:])
                        result = "submitted"
                    except ActionRejected as exc:
                        result, error = "rejected", str(exc)
                        alternatives = list(getattr(exc, "alternatives", ()))
                        self._rejection_sequence += 1
                        feedback_id = f"rejection-{actor_id}-{self._rejection_sequence}"
                        self._operational_facts[actor_id].append({
                            "type": "rejected_action",
                            "feedback_id": feedback_id,
                            "action": {"kind": intention.kind, "args": dict(intention.args)},
                            "reason": str(exc),
                            "alternatives": alternatives,
                            "must_change_before_retry": True,
                            "delivered": False,
                        })
                    except Exception as exc:
                        result, error = "engine_error", f"{type(exc).__name__}: {exc}"
                self._repetition.note_turn(actor_id, intention, result)
                self.trace.record_agent(state=self.states[actor_id], perception=perception,
                                        affordances=affordances, intention=intention,
                                        result=result, error=error,
                                        version_before=version_before, version_after=self.world.version,
                                        event_ids=event_ids,
                                        role=getattr(self.world.actors[actor_id], "role", "mc"))
                telemetry = self.trace.record_alias_telemetry()
                if telemetry:
                    self.trace.record_system({"kind": "alias_telemetry"}, dict(telemetry))
                recorder = getattr(self.agents[actor_id], "record_world_result", None)
                if recorder is not None and result != "retryable_failure":
                    message = self._result_message(result, error, event_ids,
                                                   alternatives=alternatives)
                    # V4-DESIGN §2: an accepted action produces no receipt —
                    # its outcome arrives as narrated perception. Only
                    # rejections and failures keep an immediate line.
                    if message:
                        if feedback_id is not None:
                            message = f"Feedback {feedback_id}: {message}"
                        recorder(message)
                drain_gm = getattr(self.agents[actor_id], "drain_gm_records", None)
                if drain_gm is not None:
                    for gm_record in drain_gm():
                        self.trace.record_gm(gm_record)
                # Compaction just rewrote this actor's context: force one full
                # re-observation and record the boundary in the trace (§5.3).
                consume_compaction = getattr(self.agents[actor_id], "consume_compaction", None)
                if consume_compaction is not None and consume_compaction():
                    self.world.notify_compaction(actor_id)
                    self.trace.record_compaction(actor_id, perception.get("_turn_id"))
                # inner 遥测：缺失时计数并入 trace；每个角色只提醒一次，不拒绝。
                if intention is not None and not intention.inner:
                    self.trace.record_system({"kind": "inner_telemetry"},
                                             {"missing": self._inner_missing})
                    recorder = getattr(self.agents[actor_id], "record_world_result", None)
                    if (recorder is not None and actor_id not in self._inner_reminded
                            and result != "retryable_failure"):
                        self._inner_reminded.add(actor_id)
                        recorder("（你刚才没有写心声；每次行动前先在心里想，再行动。）")
                session_snapshot = getattr(self.agents[actor_id], "session_snapshot", None)
                if session_snapshot is not None and session_snapshot() is not None:
                    self.trace.record_session(actor_id, session_snapshot())
                turns += 1
                if result == "retryable_failure":
                    self._transient_failures[actor_id] += 1
                    self._retry_context[actor_id] = (
                        perceptions[actor_id], affordances, perceptions[actor_id]["_turn_id"])
                if result != "retryable_failure" and result not in {"agent_error", "decision_timeout", "engine_error"}:
                    self._retry_context.pop(actor_id, None)
                    self._transient_failures[actor_id] = 0
                else:
                    self._retry_context.pop(actor_id, None)
                # A transient provider failure is not an in-world wait: leave
                # the actor eligible for the next boundary so it can retry.
                if result == "rejected" or (intention is None and result not in {"agent_error", "decision_timeout", "retryable_failure"}):
                    waiting.add(actor_id)
                else:
                    waiting.discard(actor_id)
                if turns >= max_turns:
                    return self._finish("max_turns_reached")
            # V4-CAST: extras lifecycle, NPC wake triggers, cold-scene detection.
            self._handle_extras()
            self._scan_npc_triggers()
            self._cold_scene_check()
            if self.checkpoint is not None:
                self.checkpoint()
            # A timed-out worker cannot be cancelled safely. In fail-fast
            # mode stop before advancing the world, so a persistent character
            # session is never called concurrently with it.
            recent_turns = (self.trace.agent_turns[-len(eligible):] if eligible else [])
            if any(trace_turn["result"] == "wall_clock_deadline" for trace_turn in recent_turns):
                return self._finish_wall_deadline()
            if self.fail_fast and any(
                    trace_turn["result"] in {"decision_timeout", "engine_error", "agent_error"}
                    for trace_turn in recent_turns):
                return self._finish("agent_failure")
            # 全员失败且连续发生 = 僵局（provider 死了/输出持续不可解析）：
            # 诚实终止，不用 "wall_clock_deadline" 的误导名义（V4 事故根因）。
            # 偶发失败批次不算——世界照常前进，失败者下一轮获得纠正反馈。
            if recent_turns and all(
                    trace_turn["result"] in {"agent_error", "engine_error",
                                             "retryable_failure"}
                    for trace_turn in recent_turns):
                self._failed_batches += 1
                if self._failed_batches >= 3:
                    return self._finish("batch_persistent_failure")
            else:
                self._failed_batches = 0
            next_time = self.world.next_event_time()
            retrying = [turn for turn in recent_turns if turn["result"] == "retryable_failure"]
            if retrying and self.retry_delay_seconds:
                retry_time = self.world.now + timedelta(seconds=self.retry_delay_seconds)
                next_time = retry_time if next_time is None else min(next_time, retry_time)
            if next_time is None:
                # A retryable turn has no world event to advance toward. Keep
                # its bounded run classified as an execution deadline rather
                # than falsely reporting an empty world queue.
                if self._retry_context and self.max_wall_seconds is not None:
                    return self._finish_wall_deadline()
                if stop_at is not None and self.world.now < stop_at:
                    self.world.advance(until=stop_at)
                return self._finish("queue_drained")
            boundary = next_time if stop_at is None else min(next_time, stop_at)
            self.world.advance(until=boundary)
            for event in self.world.event_log[self._rep_scan:]:
                if event.kind == "message_delivered":
                    self._repetition.note_message_received(
                        str(event.payload.get("target")), event.actor or "")
            self._rep_scan = len(self.world.event_log)
            if stop_at is not None and self.world.now >= stop_at:
                return self._finish("stop_at_reached")
        return self._finish("max_turns_reached")

    # ---- V4-CAST: two-tier cast machinery ---------------------------------

    def _role(self, actor_id: str) -> str:
        return getattr(self.world.actors.get(actor_id), "role", "mc")

    def _npc_budget_ok(self) -> bool:
        now = self.world.now
        self._wake_times = [t for t in self._wake_times
                            if (now - t).total_seconds() < 3600]
        return len(self._wake_times) < self.npc_wake_budget

    def _handle_extras(self) -> None:
        """Spawn/advance/expire conversation-scoped strangers (V4-CAST §1)."""
        new_events = self.world.event_log[self._extras_scan:]
        self._extras_scan = len(self.world.event_log)
        # expire first: partner gone, partner left, or idle past the timeout
        for name in list(self._extras):
            info = self._extras[name]
            partner = info["partner"]
            alive = (partner in self.world.actors
                     and self.world.actors[partner].location == self.world.actors[name].location)
            idle = (self.world.now - info["last_active"]).total_seconds() > self.extra_idle_seconds
            if not alive or idle:
                self.world.remove_extra(name)
                self._extras.pop(name, None)
                self.trace.record_system({"kind": "extra_removed"},
                                         {"extra": name, "reason": "idle" if idle else "partner_gone"})
        for event in new_events:
            if event.kind == "stranger_asked" and event.actor:
                asker = event.actor
                if any(x["partner"] == asker for x in self._extras.values()):
                    continue  # one conversation per MC at a time
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
                self._extra_turn(name, str(event.payload.get("question", "")))
            elif event.kind == "speech" and event.actor:
                for name, info in list(self._extras.items()):
                    if (info["partner"] == event.actor
                            and name in self.world.actors
                            and self.world.actors[name].location == self.world.actors[event.actor].location):
                        info["last_active"] = self.world.now
                        self._extra_turn(name, "")

    def _extra_turn(self, name: str, question: str) -> None:
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
            extra_call = self.extra_call
            assert extra_call is not None
            raw = extra_call([{"role": "system", "content": system},
                              {"role": "user", "content": briefing}])
            intention, _ = parse_decision(name, raw, self.world.version)
            if intention is not None:
                self.world.submit(intention)
                result = "submitted"
                info["last_active"] = self.world.now
                # A stranger who walks away ends the conversation.
                if intention.kind == "move":
                    self.world.remove_extra(name)
                    self._extras.pop(name, None)
        except ActionRejected as exc:
            result, error = "rejected", str(exc)
        except Exception as exc:  # a broken extra simply leaves
            result, error = "agent_error", f"{type(exc).__name__}: {exc}"
        state = PrivateState(name)
        self.trace.record_agent(state=state,
                                perception={"observer": name, "time": self.world.now.isoformat(),
                                            "location": location, "events": [], "inbox": [],
                                            "nearby_actors": [], "nearby_items": []},
                                affordances=[], intention=intention, result=result,
                                error=error or None, role="extra")
        if intention is not None and intention.kind == "move":
            self.trace.record_system({"kind": "extra_removed"},
                                     {"extra": name, "reason": "left"})

    def _scan_npc_triggers(self) -> None:
        """Wake persistent NPCs per V4-CAST §2 triggers a/b/c."""
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
                # 导演节拍只在排程显式点名该 NPC 时唤醒；广播（无 target）
                # 不唤醒——否则每条公告都把全班 NPC 叫起来。
                targets = event.payload.get("target") or ()
                if isinstance(targets, (str,)):
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
        """Trigger d: a scene with people but no words gets one NPC wake."""
        now = self.world.now
        if not self._npc_budget_ok():
            return
        threshold = self.cold_ticks * 300
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
            # 每个地点每个沉默期只给一次冷清唤醒：唤醒后仍无人说话，就不再
            # 重复唤——直到有人开口重启计时。否则沉默会变成永动机。
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

    def _wall_remaining(self, started: float) -> float | None:
        if self.max_wall_seconds is None:
            return None
        return self.max_wall_seconds - (time.monotonic() - started)

    def _wall_expired(self, started: float) -> bool:
        remaining = self._wall_remaining(started)
        return remaining is not None and remaining <= 0

    def _finish_wall_deadline(self) -> str:
        print(f"[runner] wall deadline fired: elapsed={time.monotonic()-self._wall_started_ref[0]:.0f}s "
              f"max_wall_seconds={self.max_wall_seconds}", flush=True)
        reason = self._finish("wall_clock_deadline_reached")
        # A deadline is an execution failure, so persist the last complete
        # batch before returning. The caller may then mark the artifact failed.
        if self.checkpoint is not None:
            self.checkpoint()
        return reason

    def _result_message(self, result: str, error: str | None, event_ids: list[int],
                        alternatives: Iterable[str] = ()) -> str:
        """中文、世界语气的即时反馈（V4-DESIGN §2）。

        接受的动作返回空串——结果以带时间戳的感知事件出现，没有回执。
        """
        note_warning = (" 你上一条私有状态更新格式有误，世界忽略了它；你的动作本身不受影响。"
                        if error and error.startswith("private_update_ignored:") else "")
        if result == "submitted":
            return ""
        if result == "rejected":
            detail = str(error).strip()
            guidance = " 什么都没有改变。"
            if alternatives:
                guidance += " 可以考虑：" + "; ".join(alternatives) + "。"
            return (f"你的动作没有被执行：{detail}{guidance}"
                    "看看可用的动作格式，换一个可行的做法。" + note_warning)
        if result == "retryable_failure":
            return (f"一阵恍惚，你的念头没能传达出去（{error}）。"
                    "什么都没有发生，时间也没有流逝。你会再试一次。" + note_warning)
        if result == "wall_clock_deadline":
            return "你还没来得及想清楚，时间就被抽走了。没有动作被执行。"
        if result in {"agent_error", "decision_timeout", "engine_error"}:
            return f"你的这个念头没能落地：{error}.{note_warning}"
        events = [self.world.event_log[i - 1] for i in event_ids if 0 < i <= len(self.world.event_log)]
        system_events = [event for event in events if event.kind.startswith("system_")]
        if system_events:
            name = str(self.system.name) if self.system else "台账"
            messages = []
            for event in system_events:
                if event.kind == "system_reward_granted":
                    messages.append(f"{name}给了你应得的东西：{event.payload.get('reward')}。")
                elif event.kind == "system_penalty_applied":
                    messages.append(f"{name}记下了你的代价：{event.payload.get('penalty')}。")
                elif event.kind == "system_answer":
                    messages.append(f"{name}回答了你的问题：{event.payload.get('answer')}。")
                else:
                    messages.append(f"{name}记录下了这一笔。")
            return " ".join(messages) + note_warning
        return "" + note_warning

    @staticmethod
    def _duration_text(seconds: Any) -> str:
        try:
            value = int(seconds)
        except (TypeError, ValueError):
            return f"{seconds} 秒"
        if value < 60:
            return f"{value} 秒"
        return f"{value} 秒（{value // 60} 分钟）"

    def _retryable_failure_allowed(self, actor_id: str, exc: BaseException) -> bool:
        return (getattr(exc, "retryable", False)
                and not getattr(exc, "retry_exhausted", False)
                and self._transient_failures[actor_id] < self.max_transient_failures)

    def _outer_retry_allowed(self, actor_id: str) -> bool:
        """Bound retries after a session/provider exhausted its own attempts."""
        return self._transient_failures[actor_id] < self.max_transient_failures

    def run_until_empty(self, *, max_turns: int = 100_000) -> None:
        """Run until the seeded objective schedule and all actions are drained."""
        self.run(max_turns=max_turns)

    def _finish(self, reason: str) -> str:
        self.stop_reason = reason
        return reason

    def _classify_agent_failure(self, actor: str, exc: Exception) -> tuple[str, str]:
        """Map an agent-call failure to (result, prefix). Boolean logic lives
        here instead of inside the except block (pi-lens compliance)."""
        if getattr(exc, "runner_retryable", False) and self._outer_retry_allowed(actor):
            return "retryable_failure", "retryable: "
        if getattr(exc, "runner_retryable", False):
            return "agent_error", "retry-exhausted: "
        if getattr(exc, "retry_exhausted", False):
            return "agent_error", "retry-exhausted: "
        if self._retryable_failure_allowed(actor, exc):
            return "retryable_failure", "retryable: "
        if getattr(exc, "retryable", False):
            return "agent_error", "retryable: "
        return "agent_error", ""

    def _decide(self, actor_id: str, perception: dict, affordances: list[dict]):
        decision = self.agents[actor_id](self.states[actor_id], perception, affordances)
        return decision, "none", None

    @staticmethod
    def _apply_updates(state: PrivateState, updates: dict[str, Any]) -> None:
        updates = validate_private_updates(updates)
        if not updates:
            return
        if "goals" in updates:
            state.goals = tuple(updates["goals"])
        if "beliefs" in updates:
            state.beliefs.update(updates["beliefs"])
        for key in ("memories", "interpretations", "private_notes"):
            if key in updates:
                values = updates[key]
                getattr(state, key).extend(values)
