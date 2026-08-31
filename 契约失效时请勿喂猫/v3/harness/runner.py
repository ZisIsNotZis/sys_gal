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
from .trace import Trace

AgentFn = Callable[[PrivateState, dict, list[dict]], Intention | tuple[Intention | None, dict[str, Any]] | None]


class Runner:
    def __init__(self, world: World, agents: dict[str, AgentFn], states: dict[str, PrivateState], trace: Trace, system: Ledger | None = None, *, max_workers: int | None = None, decision_timeout: float = 60.0, checkpoint: Callable[[], None] | None = None, fail_fast: bool = False, max_transient_failures: int = 2, retry_delay_seconds: int = 60, max_wall_seconds: float | None = None, repetition: RepetitionMonitor | None = None) -> None:
        if set(agents) != set(world.actors) or set(states) != set(world.actors):
            raise ValueError("one agent and private state are required for every actor")
        self.world, self.agents, self.states, self.trace, self.system = world, agents, states, trace, system
        self.stop_reason: str | None = None
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
                "repetition": self._repetition.state(), "rep_scan": self._rep_scan}

    def restore_checkpoint(self, state: dict[str, Any]) -> None:
        if set(state.get("transient_failures", {})) != set(self.world.actors):
            raise ValueError("checkpoint runner actor set does not match world")
        self._waiting = set(state.get("waiting", ()))
        self._transient_failures = {actor: int(value) for actor, value in state["transient_failures"].items()}
        self._operational_facts = {actor: [dict(x) for x in facts]
                                   for actor, facts in state.get("operational_facts", {}).items()}
        self.stop_reason = state.get("stop_reason")
        self._rejection_sequence = int(state.get("rejection_sequence", 0))
        self._turn_sequence = int(state.get("turn_sequence", 0))
        self._retry_context = dict(state.get("retry_context", {}))
        self._repetition.restore(state.get("repetition", {}))
        self._rep_scan = int(state.get("rep_scan", len(self.world.event_log)))

    def run(self, *, stop_at: datetime | None = None, max_turns: int = 100_000) -> str:
        turns = 0
        waiting = self._waiting
        wall_started = time.monotonic()
        # A provider call can outlive a batch timeout. fail_fast therefore
        # stops before the next boundary rather than risking session overlap.
        while turns < max_turns:
            if self._wall_expired(wall_started):
                return self._finish_wall_deadline()
            ready = [actor_id for actor_id, actor in self.world.actors.items()
                     if not actor.busy_until or actor.busy_until <= self.world.now]
            eligible = []
            perceptions = {}
            affordances_by_actor = {}
            for actor_id in sorted(ready):
                if stop_at is not None and self.world.now >= stop_at:
                    return self._finish("stop_at_reached")
                if actor_id in waiting and not self.world.has_wakeup(actor_id):
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
                        if getattr(exc, "runner_retryable", False) and self._outer_retry_allowed(actor):
                            prefix = "retryable: "
                            decisions[actor] = (None, "retryable_failure",
                                                prefix + f"{type(exc).__name__}: {exc}")
                        elif getattr(exc, "runner_retryable", False):
                            prefix = "retry-exhausted: "
                            decisions[actor] = (None, "agent_error",
                                                prefix + f"{type(exc).__name__}: {exc}")
                        elif getattr(exc, "retry_exhausted", False):
                            prefix = "retry-exhausted: "
                            decisions[actor] = (None, "agent_error", prefix + f"{type(exc).__name__}: {exc}")
                        elif self._retryable_failure_allowed(actor, exc):
                            prefix = "retryable: "
                            decisions[actor] = (None, "retryable_failure",
                                                prefix + f"{type(exc).__name__}: {exc}")
                        elif getattr(exc, "retryable", False):
                            prefix = "retryable: "
                            decisions[actor] = (None, "agent_error", prefix + f"{type(exc).__name__}: {exc}")
                        else:
                            prefix = ""
                            decisions[actor] = (None, "agent_error", prefix + f"{type(exc).__name__}: {exc}")
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
                updates = {}
                if isinstance(decision, tuple):
                    intention, updates = decision
                else:
                    intention = decision
                try:
                    self._apply_updates(self.states[actor_id], updates)
                except Exception as exc:
                    # Private notes are advisory model output. Validate the
                    # complete update before mutation so malformed notes do
                    # not partially change state or erase a valid action.
                    error = f"private_update_ignored: {type(exc).__name__}: {exc}"
                    updates = {}
                event_ids: list[int] = []
                feedback_id: str | None = None
                alternatives: list[str] = []
                if intention is not None:
                    try:
                        if intention.actor != actor_id:
                            raise ActionRejected("agent may submit only its own intention")
                        # Decisions in a batch share one immutable snapshot;
                        # rebase its version before serial application.
                        intention = Intention(intention.actor, intention.kind,
                                              intention.args, self.world.version)
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
                            event = self.system.query(self.world, intention.actor, str(intention.args.get("question")))
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
                                        event_ids=event_ids)
                recorder = getattr(self.agents[actor_id], "record_world_result", None)
                if recorder is not None and result != "retryable_failure":
                    message = self._result_message(result, error, event_ids,
                                                   alternatives=alternatives)
                    if feedback_id is not None:
                        message = f"Feedback {feedback_id}: {message}"
                    recorder(message)
                drain_gm = getattr(self.agents[actor_id], "drain_gm_records", None)
                if drain_gm is not None:
                    for gm_record in drain_gm():
                        self.trace.record_gm(gm_record)
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
            # A batch where every actor ended in a terminal, non-transient
            # failure must not fabricate world progress by advancing through
            # the rest of the schedule. With a wall budget present, classify
            # the stalled run as an execution deadline instead of a healthy
            # drained queue.
            if (self.max_wall_seconds is not None and recent_turns and all(
                    trace_turn["result"] in {"agent_error", "engine_error"}
                    for trace_turn in recent_turns)):
                return self._finish_wall_deadline()
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
                        str(event.payload.get("target")), event.actor)
            self._rep_scan = len(self.world.event_log)
            if stop_at is not None and self.world.now >= stop_at:
                return self._finish("stop_at_reached")
        return self._finish("max_turns_reached")

    def _wall_remaining(self, started: float) -> float | None:
        if self.max_wall_seconds is None:
            return None
        return self.max_wall_seconds - (time.monotonic() - started)

    def _wall_expired(self, started: float) -> bool:
        remaining = self._wall_remaining(started)
        return remaining is not None and remaining <= 0

    def _finish_wall_deadline(self) -> str:
        reason = self._finish("wall_clock_deadline_reached")
        # A deadline is an execution failure, so persist the last complete
        # batch before returning. The caller may then mark the artifact failed.
        if self.checkpoint is not None:
            self.checkpoint()
        return reason

    def _result_message(self, result: str, error: str | None, event_ids: list[int],
                        alternatives: Iterable[str] = ()) -> str:
        note_warning = (" The world ignored your malformed private-state update; "
                        "your physical action is unaffected."
                        if error and error.startswith("private_update_ignored:") else "")
        if result == "rejected":
            detail = str(error).strip()
            if detail.endswith("."):
                detail = detail[:-1]
            guidance = " Nothing changed."
            if alternatives:
                guidance += " Consider instead: " + "; ".join(alternatives) + "."
            return (f"The world rejects your action: {detail}.{guidance} "
                    "Read the offered action shapes carefully and choose a legal one." + note_warning)
        if result == "retryable_failure":
            return (f"A temporary communication failure prevented your turn from reaching the world: {error}. "
                    "No action was submitted and no in-world time was consumed. You will try again." + note_warning)
        if result == "wall_clock_deadline":
            return "The runner's wall-clock deadline was reached before your turn completed. No action was submitted."
        if result in {"agent_error", "decision_timeout", "engine_error"}:
            return f"The world could not carry out your turn: {error}.{note_warning}"
        events = [self.world.event_log[i - 1] for i in event_ids if 0 < i <= len(self.world.event_log)]
        if not events:
            return ("The world accepted your action; its consequences will appear as you observe "
                    "the world." + note_warning)
        system_events = [event for event in events if event.kind.startswith("system_")]
        if system_events:
            name = str(self.system.name).title() if self.system else "System"
            messages = []
            for event in system_events:
                if event.kind == "system_reward_granted":
                    messages.append(f"The {name} granted your reward: {event.payload.get('reward')}.")
                elif event.kind == "system_penalty_applied":
                    messages.append(f"The {name} applied a penalty: {event.payload.get('penalty')}.")
                elif event.kind == "system_answer":
                    messages.append(f"The {name} answered your objective question: {event.payload.get('answer')}.")
                else:
                    messages.append(f"The {name} records: {dict(event.payload)}")
            return " ".join(messages) + note_warning
        started = next((event for event in events if event.kind == "action_started"), None)
        completed = next((event for event in events if event.kind == "action_completed"), None)
        if started is not None:
            action = str(started.payload.get("action"))
            if completed is not None:
                return self._completion_text(started, completed, events) + note_warning
            actor = self.world.actors[started.actor] if started.actor else None
            until = actor.busy_until.isoformat() if actor and actor.busy_until else "an unspecified time"
            return self._in_progress_text(action, started, until) + note_warning
        descriptions = [f"{event.kind}: {dict(event.payload)}" for event in events]
        return "The world records: " + "; ".join(descriptions) + note_warning

    @staticmethod
    def _duration_text(seconds: Any) -> str:
        try:
            value = int(seconds)
        except (TypeError, ValueError):
            return f"{seconds} seconds"
        if value < 60:
            return f"{value} seconds"
        return f"{value} seconds ({value // 60} minutes)"

    def _completion_text(self, started: Any, completed: Any, events: list[Any]) -> str:
        payload = started.payload
        action = str(payload.get("action"))
        actor = self.world.actors[started.actor]
        interaction = next((event for event in events
                            if event.kind in {"item_inspected", "location_searched", "knock",
                                              "interaction", "item_given", "document_read",
                                              "document_copied", "document_labeled",
                                              "document_annotated", "documents_compared"}), None)
        if action == "move":
            return f"You arrived at {actor.location}."
        if action == "wait":
            return (f"You waited for {self._duration_text(payload.get('duration_seconds'))} "
                    f"and are free now (since {completed.time.strftime('%H:%M')}).")
        if action == "sleep":
            return f"You finished sleeping and are awake now ({completed.time.strftime('%H:%M')})."
        if action == "open":
            return f"You opened {actor.location}; it is now open to everyone."
        if action == "close":
            return f"You closed {actor.location}; it is now closed to everyone."
        if action == "take":
            return f"You picked up {payload.get('item')}."
        if action == "drop":
            return f"You dropped {payload.get('item')} here."
        if action == "give":
            return f"You handed {payload.get('item')} to {payload.get('target')}."
        if action == "send_message":
            return f"Your message to {payload.get('target')} was delivered."
        if action == "speak":
            return "You spoke; those within earshot heard you."
        if action == "inspect":
            item = payload.get("item")
            return f"You inspected {item}." if item else "Your inspection finished."
        if action == "search":
            found = ", ".join(interaction.payload.get("items", [])) if interaction else ""
            return f"You searched {actor.location} and found: {found or 'nothing'}."
        if action in {"knock", "interact"}:
            target = str(payload.get("target"))
            verb = str(payload.get("verb") or "knock")
            responded = None
            if interaction is not None:
                responded = interaction.payload.get("responded")
            if responded is None:
                responded = any(x.id != started.actor and x.location == target
                                for x in self.world.actors.values())
            if responded:
                return f"You interacted with {target} ({verb}). Someone there heard you."
            return f"You interacted with {target} ({verb}). No one responded."
        if interaction is not None:
            result_payload = interaction.payload
            if action == "read":
                return f"You read {result_payload.get('title')}."
            if action == "copy":
                return f"You copied {result_payload.get('document')} into {result_payload.get('copy')}."
            if action == "label":
                return f"You labeled {result_payload.get('document')} as {result_payload.get('label')}."
            if action == "annotate":
                return (f"You annotated {result_payload.get('document')}: "
                        f"{result_payload.get('annotation')}. The note is on the record for anyone "
                        "who reads it.")
            if action == "compare":
                verdict = "matching" if result_payload.get("same_content") else "different"
                return (f"You compared {result_payload.get('first')} and "
                        f"{result_payload.get('second')}; their contents are {verdict}.")
        return f"Your {action} completed successfully."

    def _in_progress_text(self, action: str, started: Any, until: str) -> str:
        payload = started.payload
        if action == "move":
            return (f"The world accepted your move; it is in progress. You are walking to "
                    f"{payload.get('target')}; you will arrive at {until}.")
        if action == "wait":
            return f"The world accepted your wait; it is in progress. You are waiting until {until}."
        if action == "sleep":
            return f"The world accepted your sleep; it is in progress. You are asleep until {until}."
        if action == "send_message":
            return (f"The world accepted your message; it is in progress and will be delivered "
                    f"to {payload.get('target')} at {until}.")
        if action == "speak":
            return f"The world accepted your speech; it is in progress and will finish at {until}."
        return f"The world accepted your {action}; it is in progress and will complete at {until}."

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
