"""Generic event-driven agent runner; it knows no story semantics."""

from __future__ import annotations

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, Callable

from .agent_state import PrivateState
from .kernel import ActionRejected, Intention, World
from .system import Ledger
from .trace import Trace

AgentFn = Callable[[PrivateState, dict, list[dict]], Intention | tuple[Intention | None, dict[str, Any]] | None]


class Runner:
    def __init__(self, world: World, agents: dict[str, AgentFn], states: dict[str, PrivateState], trace: Trace, system: Ledger | None = None, *, max_workers: int | None = None, decision_timeout: float = 60.0, checkpoint: Callable[[], None] | None = None, fail_fast: bool = False) -> None:
        if set(agents) != set(world.actors) or set(states) != set(world.actors):
            raise ValueError("one agent and private state are required for every actor")
        self.world, self.agents, self.states, self.trace, self.system = world, agents, states, trace, system
        self.stop_reason: str | None = None
        self.max_workers = max_workers or len(agents)
        self.decision_timeout = decision_timeout
        self.checkpoint = checkpoint
        self.fail_fast = fail_fast
        self._operational_facts: dict[str, list[dict[str, Any]]] = {actor: [] for actor in world.actors}

    def run(self, *, stop_at: datetime | None = None, max_turns: int = 100_000) -> str:
        turns = 0
        waiting: set[str] = set()
        while turns < max_turns:
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
                perception = self.world.poll(actor_id)
                if self._operational_facts[actor_id]:
                    perception["operational_facts"] = [dict(fact) for fact in self._operational_facts[actor_id]]
                perceptions[actor_id] = perception
                affordances = self.world.affordances(actor_id)
                if self.system is not None:
                    affordances.extend(self.system.affordances(actor_id))
                affordances_by_actor[actor_id] = affordances
                eligible.append(actor_id)
                decisions = {}
            pool = ThreadPoolExecutor(max_workers=min(self.max_workers, max(1, len(eligible))))
            futures = {actor: pool.submit(self._decide, actor, perceptions[actor], affordances_by_actor[actor]) for actor in eligible}
            try:
                # One deadline applies to the whole decision batch.  Calling
                # result(timeout=...) once per future accidentally made the
                # batch deadline N * timeout.
                done, _ = wait(futures.values(), timeout=self.decision_timeout)
                for actor, future in futures.items():
                    if future not in done:
                        decisions[actor] = (None, "decision_timeout", "agent decision exceeded batch deadline")
                        continue
                    try:
                        decisions[actor] = future.result()
                    except Exception as exc:
                        decisions[actor] = (None, "agent_error", f"{type(exc).__name__}: {exc}")
            finally:
                # Do not join here: the provider itself has a shorter socket
                # timeout.  The runner records the batch result immediately.
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
                    # Private notes are advisory model output.  A malformed
                    # note must not erase an otherwise valid physical action
                    # or stop the entire world; discard only that update.
                    error = f"private_update_ignored: {type(exc).__name__}: {exc}"
                    updates = {}
                event_ids: list[int] = []
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
                        self._operational_facts[actor_id].append({
                            "type": "rejected_action",
                            "action": {"kind": intention.kind, "args": dict(intention.args)},
                            "reason": str(exc),
                            "must_change_before_retry": True,
                        })
                    except Exception as exc:
                        result, error = "engine_error", f"{type(exc).__name__}: {exc}"
                self.trace.record_agent(state=self.states[actor_id], perception=perception,
                                        affordances=affordances, intention=intention,
                                        result=result, error=error,
                                        version_before=version_before, version_after=self.world.version,
                                        event_ids=event_ids)
                recorder = getattr(self.agents[actor_id], "record_world_result", None)
                if recorder is not None:
                    recorder(self._result_message(result, error, event_ids))
                drain_gm = getattr(self.agents[actor_id], "drain_gm_records", None)
                if drain_gm is not None:
                    for gm_record in drain_gm():
                        self.trace.record_gm(gm_record)
                session_snapshot = getattr(self.agents[actor_id], "session_snapshot", None)
                if session_snapshot is not None and session_snapshot() is not None:
                    self.trace.record_session(actor_id, session_snapshot())
                turns += 1
                if result == "rejected" or (intention is None and result != "agent_error"):
                    waiting.add(actor_id)
                else:
                    waiting.discard(actor_id)
                if turns >= max_turns:
                    return self._finish("max_turns_reached")
            if self.checkpoint is not None:
                self.checkpoint()
                # A transient provider failure is already recorded as this
                # actor's failed turn. Keep the objective world moving and
                # retry that actor at the next world boundary. Only a
                # decision timeout is fatal because it can leave a worker
                # call running beyond the batch boundary.
                if self.fail_fast and any(
                    trace_turn["result"] == "decision_timeout"
                    for trace_turn in self.trace.agent_turns[-len(eligible):]):
                    return self._finish("agent_failure")
            next_time = self.world.next_event_time()
            if next_time is None:
                if stop_at is not None and self.world.now < stop_at:
                    self.world.advance(until=stop_at)
                return self._finish("queue_drained")
            boundary = next_time if stop_at is None else min(next_time, stop_at)
            self.world.advance(until=boundary)
            if stop_at is not None and self.world.now >= stop_at:
                return self._finish("stop_at_reached")
        return self._finish("max_turns_reached")

    def _result_message(self, result: str, error: str | None, event_ids: list[int]) -> str:
        if result == "rejected":
            return f"The world rejects your action: {error}. Nothing changes."
        if result in {"agent_error", "decision_timeout", "engine_error"}:
            return f"The world could not carry out your turn: {error}."
        events = [self.world.event_log[i - 1] for i in event_ids if 0 < i <= len(self.world.event_log)]
        if not events:
            return "The world records no immediate physical change from your turn."
        system_events = [event for event in events if event.kind.startswith("system_")]
        if system_events:
            messages = []
            for event in system_events:
                if event.kind == "system_reward_granted":
                    messages.append(f"The Ledger granted your reward: {event.payload.get('reward')}.")
                elif event.kind == "system_penalty_applied":
                    messages.append(f"The Ledger applied a penalty: {event.payload.get('penalty')}.")
                elif event.kind == "system_answer":
                    messages.append(f"The Ledger answered your objective question: {event.payload.get('answer')}.")
                else:
                    messages.append(f"The Ledger records: {dict(event.payload)}")
            return " ".join(messages)
        started = next((event for event in events if event.kind == "action_started"), None)
        completed = next((event for event in events if event.kind == "action_completed"), None)
        if started is not None:
            action = str(started.payload.get("action"))
            if completed is not None:
                return f"The world accepted your {action} and it completed successfully."
            actor = self.world.actors[started.actor] if started.actor else None
            until = actor.busy_until.isoformat() if actor and actor.busy_until else "an unspecified time"
            return (f"The world accepted your {action}. It is in progress and will complete at {until}. "
                    "Its physical consequences have not happened yet.")
        descriptions = [f"{event.kind}: {dict(event.payload)}" for event in events]
        return "The world records: " + "; ".join(descriptions)

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
        if not updates:
            return
        if not isinstance(updates, dict) or set(updates) - {"beliefs", "memories", "interpretations", "private_notes"}:
            raise ValueError("invalid private-state updates")
        if "beliefs" in updates:
            if not isinstance(updates["beliefs"], dict):
                raise ValueError("beliefs update must be an object")
            state.beliefs.update(updates["beliefs"])
        for key in ("memories", "interpretations", "private_notes"):
            if key in updates:
                values = updates[key]
                if not isinstance(values, list):
                    raise ValueError(f"{key} update must be a list")
                if key in {"memories", "interpretations"} and not all(isinstance(x, dict) for x in values):
                    raise ValueError(f"{key} entries must be objects")
                if key == "private_notes" and not all(isinstance(x, str) for x in values):
                    raise ValueError("private_notes entries must be strings")
                getattr(state, key).extend(values)
