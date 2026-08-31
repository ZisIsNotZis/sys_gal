"""Small deterministic event-driven kernel for the v1 story seed.

This module intentionally contains no language-model calls. Character agents
will eventually sit on the intention seam: they receive a private perception
packet and submit an Intention; only this kernel can commit world events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import heapq
import itertools
from typing import Any, Iterable, Mapping


class ActionRejected(ValueError):
    """An intention cannot be committed against the current world state."""


@dataclass
class ActorState:
    id: str
    location: str
    inventory: set[str] = field(default_factory=set)
    busy_until: datetime | None = None
    sleeping: bool = False
    inbox: list[dict[str, Any]] = field(default_factory=list)
    beliefs: dict[str, float] = field(default_factory=dict)
    relationships: dict[str, int] = field(default_factory=dict)


@dataclass
class LocationState:
    id: str
    open: bool = True
    sound_radius: int = 0


@dataclass(frozen=True)
class Intention:
    actor: str
    kind: str
    args: Mapping[str, Any] = field(default_factory=dict)
    expected_version: int | None = None


@dataclass(frozen=True)
class Event:
    id: int
    time: datetime
    kind: str
    actor: str | None
    payload: Mapping[str, Any]
    cause: str | None
    visible_to: frozenset[str]
    world_version: int


@dataclass(order=True, frozen=True)
class _Scheduled:
    time: datetime
    sequence: int
    kind: str = field(compare=False)
    actor: str | None = field(compare=False)
    payload: Mapping[str, Any] = field(compare=False)
    cause: str | None = field(compare=False)


class WorldHarness:
    """Authoritative, coarse-grained event-driven world kernel.

    The public seam is intentionally small: ``affordances``, ``submit``,
    ``advance`` and ``poll_perception``. All state changes pass through this
    object and are recorded in ``event_log``.
    """

    _KNOWN_ACTIONS = {
        "wait",
        "speak",
        "send_message",
        "move",
        "open",
        "close",
        "take",
        "drop",
        "sleep",
        "ledger_choose",
        "update_belief",
        "update_relationship",
        "finish_activity",
        "declare_resolution",
    }

    def __init__(
        self,
        *,
        start: datetime,
        actors: Iterable[ActorState],
        locations: Iterable[LocationState],
        item_locations: Mapping[str, str] | None = None,
        routes: Mapping[tuple[str, str], int] | None = None,
        system_events: Iterable[Mapping[str, Any]] | None = None,
        major_actors: Iterable[str] | None = None,
    ) -> None:
        self.now = start
        self.version = 0
        actor_list = list(actors)
        self.actors = {actor.id: actor for actor in actor_list}
        self.locations = {location.id: location for location in locations}
        self.item_locations = dict(item_locations or {})
        self.routes = dict(routes or {})
        self.system_events = [dict(item) for item in (system_events or [])]
        self.event_log: list[Event] = []
        self._queue: list[_Scheduled] = []
        self._sequence = itertools.count(1)
        self._event_id = itertools.count(1)
        self._perception_cursor = {actor.id: 0 for actor in actor_list}
        self.ledger_case = "open"
        self.ledger_choice: str | None = None
        self.ledger_disclosures: set[str] = set()
        self.ledger_reward = False
        self.story_phase = "opening"
        self.terminal_reason: str | None = None
        self.major_actors = tuple(major_actors or self.actors)
        self.actor_resolutions: dict[str, str | None] = {actor_id: None for actor_id in self.major_actors}

        if len(self.actors) != len(actor_list):
            raise ValueError("actor ids must be unique")
        for actor in self.actors.values():
            self._require_location(actor.location)
        for location in self.locations.values():
            if location.sound_radius < 0:
                raise ValueError("sound radius cannot be negative")
        for item, location in self.item_locations.items():
            self._require_location(location)
        for scheduled in self.system_events:
            event_time = datetime.fromisoformat(str(scheduled["time"]))
            if event_time < self.now:
                raise ValueError("seed event cannot be scheduled before start")
            kind = str(scheduled.get("kind", "world_event"))
            if kind not in {"world_event", "story_beat", "story_terminal_beat"}:
                raise ValueError(f"unknown scheduled seed kind: {kind}")
            self._schedule(event_time, kind, None, scheduled, cause=None)

    def emit_system(self, payload: Mapping[str, Any]) -> Event:
        """Commit a Ledger/system event visible only to its bound actor."""

        return self._commit("system", "chen-mo", dict(payload), cause=None)

    def mark_actor_resolved(self, actor_id: str, resolution: str, *, cause: int | None = None) -> Event:
        """Record an explicit fate/status for a major actor."""
        self._actor(actor_id)
        if actor_id not in self.actor_resolutions:
            raise ActionRejected("actor is not part of the story contract")
        if not isinstance(resolution, str) or not resolution.strip():
            raise ActionRejected("actor resolution must be non-empty")
        self.actor_resolutions[actor_id] = resolution.strip()
        return self._commit("actor_resolved", actor_id, {"resolution": resolution.strip()}, cause=cause)

    def affordances(self, actor_id: str) -> list[dict[str, Any]]:
        """Return legal action shapes derived only from current state."""

        actor = self._actor(actor_id)
        options: list[dict[str, Any]] = [{"kind": "wait", "duration_seconds": 60}]
        if self.now >= self._terminal_time() and actor_id in self.actor_resolutions:
            options.append({"kind": "declare_resolution"})
            if actor.busy_until and actor.busy_until > self.now:
                return options
        elif actor.busy_until and actor.busy_until > self.now:
            return options

        # Mental updates are requests whose evidence is supplied by the agent
        # from its private packet.  The exact proposition/evidence is validated
        # at submit time, so the affordance advertises the action shape only.
        options.extend({"kind": kind} for kind in ("update_belief", "update_relationship"))

        if actor_id == "chen-mo" and self.ledger_case == "open":
            options.extend({"kind": "ledger_choose", "choice": choice} for choice in ("A", "B", "C"))

        options.append({"kind": "speak", "text": ""})
        options.extend(
            {"kind": "send_message", "target": other}
            for other in self.actors
            if other != actor_id
        )
        options.extend(
            {"kind": "move", "target": target, "duration_seconds": seconds}
            for (source, target), seconds in self.routes.items()
            if source == actor.location
        )
        location = self.locations[actor.location]
        options.append({"kind": "close" if location.open else "open"})
        options.extend(
            {"kind": "take", "item": item}
            for item, location_id in self.item_locations.items()
            if location_id == actor.location
        )
        options.extend({"kind": "drop", "item": item} for item in actor.inventory)
        options.append({"kind": "sleep", "duration_seconds": 6 * 60 * 60})
        return options

    def submit(self, intention: Intention) -> tuple[Event, ...]:
        """Validate and schedule one intention; invalid intents do nothing."""

        actor = self._actor(intention.actor)
        if intention.expected_version is not None and intention.expected_version != self.version:
            raise ActionRejected("intention was made from a stale world version")
        if intention.kind not in self._KNOWN_ACTIONS:
            raise ActionRejected(f"unknown action: {intention.kind}")
        if actor.busy_until and actor.busy_until > self.now:
            raise ActionRejected("actor is busy")

        duration = self._validate_and_duration(actor, intention)
        start_event = self._commit(
            "action_started",
            actor.id,
            self._public_action_payload(intention),
            cause=None,
        )
        if intention.kind == "speak":
            self._commit(
                "speech",
                actor.id,
                {"text": str(intention.args["text"])},
                cause=start_event.id,
            )
        elif intention.kind == "send_message":
            self._commit(
                "message_sent",
                actor.id,
                {"target": str(intention.args["target"]), "text": str(intention.args["text"])},
                cause=start_event.id,
            )
        elif intention.kind == "ledger_choose":
            self.ledger_case = "accepted"
            self.ledger_choice = str(intention.args["choice"])
            self._commit("ledger_case_accepted", actor.id, {
                "case": "three-way-ambiguity", "choice": self.ledger_choice,
                "options": ["A", "B", "C"],
            }, cause=start_event.id)
            self._commit("ledger_cost", actor.id, {"case": "three-way-ambiguity", "cost": "risk-Gao-trust"}, cause=start_event.id)
        elif intention.kind in {"update_belief", "update_relationship"}:
            self._apply_mental_update(actor, intention, cause=start_event.id)
        elif intention.kind == "declare_resolution":
            self.actor_resolutions[actor.id] = str(intention.args["resolution"]).strip()
            self._commit("actor_resolved", actor.id, {"resolution": self.actor_resolutions[actor.id]}, cause=start_event.id)
        self._schedule(
            self.now + duration,
            "action_completed",
            actor.id,
            {"action": intention.kind, **dict(intention.args)},
            cause=start_event.id,
        )
        actor.busy_until = self.now + duration if duration else None
        actor.sleeping = intention.kind == "sleep"
        if duration == timedelta(0):
            # Drain this timestamp so this action's completion cannot be left
            # behind an unrelated same-time queue entry.
            self.advance(until=self.now)
        return (start_event,)

    def advance(self, *, until: datetime | None = None) -> tuple[Event, ...]:
        """Apply queued events through the next event, or through ``until``."""

        if until is not None and until < self.now:
            raise ValueError("cannot move simulated time backwards")
        if not self._queue:
            if until is not None:
                if until > self.now:
                    previous = self.now
                    self.now = until
                    self._commit("time_advanced", None, {"from": previous.isoformat(),
                                                          "to": until.isoformat(), "reason": "no queued event"}, cause=None)
            return ()
        events: list[Event] = []
        # No boundary means one coroutine wake-up.  A boundary means drain all
        # events through it; callers rely on the distinction for cheap polling.
        if until is None:
            scheduled = heapq.heappop(self._queue)
            self.now = scheduled.time
            event = self._commit(
                scheduled.kind,
                scheduled.actor,
                self._public_completion_payload(scheduled.payload),
                cause=scheduled.cause,
            )
            events.append(event)
            self._apply_scheduled_story_state(scheduled, event)
            if scheduled.kind == "action_completed" and scheduled.actor:
                self._complete_action(scheduled.actor, scheduled.payload)
                if scheduled.payload["action"] == "send_message":
                    events.append(self._commit(
                        "message_delivered", scheduled.actor,
                        {"target": str(scheduled.payload["target"]), "text": str(scheduled.payload["text"])},
                        cause=event.id,
                    ))
        else:
            while self._queue and self._queue[0].time <= until:
                scheduled = heapq.heappop(self._queue)
                self.now = scheduled.time
                event = self._commit(
                    scheduled.kind,
                    scheduled.actor,
                    self._public_completion_payload(scheduled.payload),
                    cause=scheduled.cause,
                )
                events.append(event)
                self._apply_scheduled_story_state(scheduled, event)
                if scheduled.kind == "action_completed" and scheduled.actor:
                    self._complete_action(scheduled.actor, scheduled.payload)
                    if scheduled.payload["action"] == "send_message":
                        events.append(self._commit(
                            "message_delivered", scheduled.actor,
                            {"target": str(scheduled.payload["target"]), "text": str(scheduled.payload["text"])},
                            cause=event.id,
                        ))
        if until is not None and self.now < until:
            # Time may advance without an action only through an explicit,
            # replayable clock event.  This prevents a runner from silently
            # teleporting to its claimed ending.
            previous = self.now
            self.now = until
            self._commit("time_advanced", None, {"from": previous.isoformat(),
                                                  "to": until.isoformat(), "reason": "no queued event"}, cause=None)
        return tuple(events)

    @property
    def has_pending_events(self) -> bool:
        return bool(self._queue)

    def next_event_time(self) -> datetime | None:
        return self._queue[0].time if self._queue else None

    def poll_perception(self, actor_id: str) -> dict[str, Any]:
        """Return a private, filtered wake packet and move that actor's cursor."""

        actor = self._actor(actor_id)
        cursor = self._perception_cursor[actor_id]
        visible = [event for event in self.event_log[cursor:] if actor_id in event.visible_to]
        self._perception_cursor[actor_id] = len(self.event_log)
        nearby_actors = sorted(
            other.id for other in self.actors.values()
            if other.id != actor_id and other.location == actor.location
        )
        nearby_items = sorted(
            item for item, location in self.item_locations.items()
            if location == actor.location
        )
        return {
            "observer": actor_id,
            "time": self.now.isoformat(),
            "world_version": self.version,
            "location": actor.location,
            "inventory": sorted(actor.inventory),
            "sleeping": actor.sleeping,
            "nearby_actors": nearby_actors,
            "nearby_items": nearby_items,
            "inbox": list(actor.inbox),
            "beliefs": dict(actor.beliefs),
            "relationships": dict(actor.relationships),
            "events": [self._public_event(event) for event in visible],
        }

    def replayable_log(self) -> tuple[dict[str, Any], ...]:
        """Return a serialization-friendly view of the append-only event log."""

        return tuple({
            "id": event.id,
            "time": event.time.isoformat(),
            "kind": event.kind,
            "actor": event.actor,
            "payload": dict(event.payload),
            "cause": event.cause,
            "visible_to": sorted(event.visible_to),
            "world_version": event.world_version,
        } for event in self.event_log)

    def _validate_and_duration(self, actor: ActorState, intention: Intention) -> timedelta:
        args = intention.args
        kind = intention.kind
        if kind in {"wait", "sleep"}:
            seconds = self._positive_seconds(args.get("duration_seconds"))
            return timedelta(seconds=seconds)
        if kind == "ledger_choose":
            if actor.id != "chen-mo" or self.ledger_case != "open":
                raise ActionRejected("Ledger case is not available")
            if args.get("choice") not in {"A", "B", "C"}:
                raise ActionRejected("Ledger choice must be A, B, or C")
            return timedelta(0)
        if kind == "declare_resolution":
            if self.now < self._terminal_time():
                raise ActionRejected("story resolution is not available yet")
            if not isinstance(args.get("resolution"), str) or not args["resolution"].strip():
                raise ActionRejected("resolution must be non-empty")
            return timedelta(0)
        if kind == "update_belief":
            proposition = args.get("proposition")
            confidence = args.get("confidence")
            if not isinstance(proposition, str) or not proposition.strip():
                raise ActionRejected("belief update needs a proposition")
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise ActionRejected("belief confidence must be between 0 and 1")
            self._require_visible_evidence(actor.id, args.get("evidence_event_id"))
            return timedelta(0)
        if kind == "update_relationship":
            target = str(args.get("target"))
            delta = args.get("delta")
            self._require_actor(target)
            if target == actor.id:
                raise ActionRejected("relationship target must be another actor")
            if isinstance(delta, bool) or not isinstance(delta, int) or not -10 <= delta <= 10:
                raise ActionRejected("relationship delta must be an integer from -10 to 10")
            self._require_visible_evidence(actor.id, args.get("evidence_event_id"))
            return timedelta(0)
        if kind == "speak":
            text = args.get("text")
            if not isinstance(text, str) or not text:
                raise ActionRejected("speech needs non-empty text")
            # v1 uses a deliberately coarse, deterministic reading speed.
            return timedelta(seconds=max(1, (len(text) + 7) // 8))
        if kind == "send_message":
            self._require_actor(str(args.get("target")))
            if not args.get("text"):
                raise ActionRejected("message needs non-empty text")
            return timedelta(seconds=5)
        if kind == "move":
            target = str(args.get("target"))
            self._require_location(target)
            if not self.locations[target].open:
                raise ActionRejected("destination is closed")
            route_duration = self.routes.get((actor.location, target))
            if route_duration is None:
                raise ActionRejected("no route from actor location to target")
            requested = args.get("duration_seconds", route_duration)
            if requested != route_duration:
                raise ActionRejected("move duration must use the route timetable")
            return timedelta(seconds=route_duration)
        if kind in {"open", "close", "take", "drop"}:
            if kind in {"open", "close"} and actor.location not in self.locations:
                raise ActionRejected("actor has no valid location")
            if kind in {"take", "drop"}:
                item = str(args.get("item"))
                if kind == "take" and self.item_locations.get(item) != actor.location:
                    raise ActionRejected("item is not at actor location")
                if kind == "drop" and item not in actor.inventory:
                    raise ActionRejected("actor does not have item")
            return timedelta(seconds=0)
        raise ActionRejected(f"no duration rule for {kind}")

    def _complete_action(self, actor_id: str, payload: Mapping[str, Any]) -> None:
        actor = self._actor(actor_id)
        kind = payload["action"]
        if kind == "move":
            actor.location = str(payload["target"])
        elif kind == "send_message":
            target = self._actor(str(payload["target"]))
            target.inbox.append({"from": actor_id, "text": str(payload["text"]), "sent_at": self.now.isoformat()})
            if self.ledger_case == "accepted" and self.ledger_choice == "C" and target.id in {"gao-rui", "lin-yao", "luo-wen"}:
                self.ledger_disclosures.add(target.id)
                if self.ledger_disclosures == {"gao-rui", "lin-yao", "luo-wen"} and not self.ledger_reward:
                    self.ledger_case, self.ledger_reward = "settled", True
                    self._commit("system", "chen-mo", {"case": "three-way-ambiguity", "status": "settled", "reward": "objective-clarification"}, cause=None)
        elif kind == "take":
            item = str(payload["item"])
            actor.inventory.add(item)
            del self.item_locations[item]
        elif kind == "drop":
            item = str(payload["item"])
            actor.inventory.remove(item)
            self.item_locations[item] = actor.location
        elif kind == "open":
            self.locations[actor.location].open = True
        elif kind == "close":
            self.locations[actor.location].open = False
        elif kind == "sleep":
            actor.sleeping = False
        actor.busy_until = None

    def _apply_scheduled_story_state(self, scheduled: _Scheduled, event: Event) -> None:
        if scheduled.kind not in {"story_beat", "story_terminal_beat"}:
            return
        payload = scheduled.payload
        self.story_phase = str(payload.get("phase", self.story_phase))
        if scheduled.kind == "story_terminal_beat":
            # A terminal review is a world-level interruption.  Ongoing
            # routine macros yield here so each actor can explicitly record
            # its own consequence; they are not silently resolved by seed.
            for actor in self.actors.values():
                actor.busy_until = None
                actor.sleeping = False
            reason = payload.get("terminal_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ActionRejected("story terminal beat needs terminal_reason")
            missing = [actor_id for actor_id in self.major_actors if not self.actor_resolutions.get(actor_id)]
            if missing:
                self._pending_terminal_reason = reason.strip()
                return
            self.terminal_reason = reason.strip()
            self.story_phase = "terminal"
            self._commit("story_terminal", None, {
                "phase": self.story_phase,
                "terminal_reason": self.terminal_reason,
                "resolved_actors": dict(self.actor_resolutions),
            }, cause=event.id)

    def finalize_story(self) -> Event:
        missing = [actor_id for actor_id in self.major_actors if not self.actor_resolutions.get(actor_id)]
        if missing:
            raise ActionRejected(f"cannot finalize story; unresolved actors: {missing}")
        reason = getattr(self, "_pending_terminal_reason", None)
        if not reason:
            raise ActionRejected("no terminal beat has established a reason")
        self.terminal_reason = reason
        self.story_phase = "terminal"
        return self._commit("story_terminal", None, {"phase": "terminal", "terminal_reason": reason, "resolved_actors": dict(self.actor_resolutions)}, cause=None)

    def _terminal_time(self) -> datetime:
        times = [s.time for s in self._queue if s.kind == "story_terminal_beat"]
        return min(times) if times else self.now

    def _apply_mental_update(self, actor: ActorState, intention: Intention, *, cause: int) -> None:
        args = intention.args
        evidence_id = int(args["evidence_event_id"])
        if intention.kind == "update_belief":
            proposition = str(args["proposition"]).strip()
            confidence = float(args["confidence"])
            actor.beliefs[proposition] = confidence
            payload = {"proposition": proposition, "confidence": confidence, "evidence_event_id": evidence_id}
        else:
            target = str(args["target"])
            old = actor.relationships.get(target, 0)
            actor.relationships[target] = max(-100, min(100, old + int(args["delta"])))
            payload = {"target": target, "delta": int(args["delta"]), "value": actor.relationships[target], "evidence_event_id": evidence_id}
        self._commit(intention.kind, actor.id, payload, cause=cause)

    def _require_visible_evidence(self, actor_id: str, evidence_id: Any) -> Event:
        if isinstance(evidence_id, bool) or not isinstance(evidence_id, int):
            raise ActionRejected("an evidence_event_id is required")
        event = next((item for item in self.event_log if item.id == evidence_id), None)
        if event is None or actor_id not in event.visible_to:
            raise ActionRejected("actor cannot cite that evidence")
        return event

    def _commit(
        self,
        kind: str,
        actor: str | None,
        payload: Mapping[str, Any],
        *,
        cause: int | None,
    ) -> Event:
        visible_to = self._visible_to(kind, actor, payload)
        event = Event(
            id=next(self._event_id),
            time=self.now,
            kind=kind,
            actor=actor,
            payload=dict(payload),
            cause=str(cause) if cause is not None else None,
            visible_to=frozenset(visible_to),
            world_version=self.version + 1,
        )
        self.version += 1
        self.event_log.append(event)
        return event

    def _visible_to(self, kind: str, actor_id: str | None, payload: Mapping[str, Any]) -> set[str]:
        if kind == "system":
            return {"chen-mo"}
        if kind == "world_event":
            target = payload.get("target")
            return {str(target)} if target else set(self.actors)
        if kind in {"message_sent", "message_delivered"}:
            if kind == "message_sent":
                return {str(actor_id)}
            return {str(payload["target"])}
        if kind == "speech":
            actor = self._actor(str(actor_id))
            return {
                other.id for other in self.actors.values()
                if other.location == actor.location and self.locations[actor.location].open
            }
        if actor_id is None:
            return set(self.actors)
        actor = self._actor(actor_id)
        return {other.id for other in self.actors.values() if other.location == actor.location} | {actor_id}

    @staticmethod
    def _public_action_payload(intention: Intention) -> dict[str, Any]:
        if intention.kind == "send_message":
            return {"action": intention.kind}
        return {"action": intention.kind, **dict(intention.args)}

    @staticmethod
    def _public_completion_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        if payload.get("action") == "send_message":
            return {"action": "send_message"}
        return dict(payload)

    def _schedule(self, time: datetime, kind: str, actor: str | None, payload: Mapping[str, Any], cause: int | None) -> None:
        heapq.heappush(self._queue, _Scheduled(time, next(self._sequence), kind, actor, dict(payload), str(cause) if cause else None))

    @staticmethod
    def _positive_seconds(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ActionRejected("duration_seconds must be a positive integer")
        return value

    def _public_event(self, event: Event) -> dict[str, Any]:
        return {"id": event.id, "time": event.time.isoformat(), "kind": event.kind, "actor": event.actor, "payload": dict(event.payload), "cause": event.cause}

    def _actor(self, actor_id: str) -> ActorState:
        actor = self.actors.get(actor_id)
        if actor is None:
            raise ActionRejected(f"unknown actor: {actor_id}")
        return actor

    def _require_actor(self, actor_id: str) -> None:
        self._actor(actor_id)

    def _require_location(self, location_id: str) -> None:
        if location_id not in self.locations:
            raise ValueError(f"unknown location: {location_id}")
