"""A mindless objective world kernel.

This module deliberately has no narrative, romance, route, chapter, or
character-resolution concepts. Agents own interpretation; the kernel owns
only state, time, visibility, and executable consequences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import heapq
import itertools
from typing import Any, Iterable, Mapping


class ActionRejected(ValueError):
    pass


@dataclass
class ActorState:
    id: str
    location: str
    inventory: set[str] = field(default_factory=set)
    busy_until: datetime | None = None
    sleeping: bool = False
    inbox: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class LocationState:
    id: str
    open: bool = True
    x: float = 0.0
    y: float = 0.0
    sound_radius: float = 0.0
    sound_loss: float = 0.0


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
    cause: int | None
    visible_to: frozenset[str]
    world_version: int


@dataclass(order=True, frozen=True)
class _Scheduled:
    time: datetime
    sequence: int
    kind: str = field(compare=False)
    actor: str | None = field(compare=False)
    payload: Mapping[str, Any] = field(compare=False)
    cause: int | None = field(compare=False)


class World:
    """Authoritative, deterministic, event-sourced physical/social world."""

    ACTIONS = {"wait", "speak", "send_message", "move", "open", "close",
               "take", "drop", "sleep", "inspect", "search", "knock", "give"}

    def __init__(self, *, start: datetime, actors: Iterable[ActorState],
                 locations: Iterable[LocationState],
                 item_locations: Mapping[str, str] | None = None,
                 routes: Mapping[tuple[str, str], int] | None = None,
                 sound_barriers: Mapping[tuple[str, str], float] | None = None,
                 scheduled: Iterable[Mapping[str, Any]] | None = None) -> None:
        actor_list = list(actors)
        self.now = start
        self.version = 0
        self.actors = {a.id: a for a in actor_list}
        self.locations = {x.id: x for x in locations}
        self.item_locations = dict(item_locations or {})
        self.routes = dict(routes or {})
        self.sound_barriers = dict(sound_barriers or {})
        self.event_log: list[Event] = []
        self._queue: list[_Scheduled] = []
        self._sequence = itertools.count(1)
        self._event_id = itertools.count(1)
        self._cursor = {a.id: 0 for a in actor_list}
        if len(self.actors) != len(actor_list):
            raise ValueError("actor ids must be unique")
        for a in actor_list:
            self._require_location(a.location)
        for item, location in self.item_locations.items():
            self._require_location(location)
        for (source, target), loss in self.sound_barriers.items():
            self._require_location(source); self._require_location(target)
            if not isinstance(loss, (int, float)) or loss < 0:
                raise ValueError("sound barrier loss must be non-negative")
        for row in scheduled or ():
            when = datetime.fromisoformat(str(row["time"]))
            if when < start:
                raise ValueError("scheduled event precedes world start")
            self._schedule(when, str(row.get("kind", "world_event")),
                           None, dict(row), None)

    @property
    def has_pending_events(self) -> bool:
        return bool(self._queue)

    def next_event_time(self) -> datetime | None:
        return self._queue[0].time if self._queue else None

    def has_wakeup(self, actor_id: str) -> bool:
        """Return whether an idle actor has observable work to poll."""
        a = self._actor(actor_id)
        if a.busy_until and a.busy_until > self.now:
            return False
        cursor = self._cursor[actor_id]
        return bool(a.inbox or any(actor_id in event.visible_to for event in self.event_log[cursor:]))

    def affordances(self, actor_id: str) -> list[dict[str, Any]]:
        a = self._actor(actor_id)
        if a.busy_until and a.busy_until > self.now:
            return [{"kind": "wait", "duration_seconds": 900}]
        options: list[dict[str, Any]] = [
            {"kind": "wait", "duration_seconds": 900},
            {"kind": "wait", "duration_seconds": 3600},
            {"kind": "speak", "text": "", "volume": "normal"},
            *({"kind": "send_message", "target": other} for other in self.actors if other != actor_id),
            *({"kind": "move", "target": target, "duration_seconds": duration}
              for (source, target), duration in self.routes.items() if source == a.location),
            {"kind": "open" if not self.locations[a.location].open else "close"},
            {"kind": "sleep", "duration_seconds": 6 * 60 * 60},
        ]
        options += [{"kind": "take", "item": item} for item, loc in self.item_locations.items() if loc == a.location]
        options += [{"kind": "inspect", "item": item} for item, loc in self.item_locations.items() if loc == a.location]
        options += [{"kind": "inspect", "item": item} for item in sorted(a.inventory)]
        options.append({"kind": "search"})
        options += [{"kind": "knock", "target": location.id} for location in self.locations.values()
                    if not location.open and (a.location, location.id) in self.routes]
        options += [{"kind": "give", "target": other.id, "item": item}
                    for other in self.actors.values()
                    if other.id != actor_id and other.location == a.location
                    for item in sorted(a.inventory)]
        options += [{"kind": "drop", "item": item} for item in sorted(a.inventory)]
        return options

    def submit(self, intention: Intention) -> tuple[Event, ...]:
        a = self._actor(intention.actor)
        if intention.expected_version is not None and intention.expected_version != self.version:
            raise ActionRejected("stale world version")
        if intention.kind not in self.ACTIONS:
            raise ActionRejected("unknown action")
        if a.busy_until and a.busy_until > self.now:
            raise ActionRejected("actor is busy")
        duration = self._duration(a, intention)
        started = self._commit("action_started", a.id, {"action": intention.kind, **dict(intention.args)}, None)
        if intention.kind == "speak":
            self._commit("speech", a.id, {"text": intention.args["text"],
                                           "volume": intention.args.get("volume", "normal")}, started.id)
        elif intention.kind == "send_message":
            self._commit("message_sent", a.id, {"target": str(intention.args["target"])}, started.id)
        self._schedule(self.now + duration, "action_completed", a.id,
                       {"action": intention.kind, **dict(intention.args)}, started.id)
        a.busy_until = self.now + duration if duration else None
        a.sleeping = intention.kind == "sleep"
        if not duration:
            self.advance(until=self.now)
        return (started,)

    def advance(self, *, until: datetime | None = None) -> tuple[Event, ...]:
        if until is not None and until < self.now:
            raise ValueError("cannot reverse time")
        out: list[Event] = []
        limit = until
        while self._queue and (limit is None or self._queue[0].time <= limit):
            job = heapq.heappop(self._queue)
            self.now = job.time
            event = self._commit(job.kind, job.actor, self._public_payload(job.payload), job.cause)
            out.append(event)
            if job.kind == "action_completed" and job.actor:
                self._complete(job.actor, job.payload)
                if job.payload["action"] in {"inspect", "search", "knock"}:
                    out.append(self._commit_interaction(job.actor, job.payload, event.id))
                if job.payload["action"] == "give":
                    out.append(self._commit_interaction(job.actor, job.payload, event.id))
                if job.payload["action"] == "send_message":
                    out.append(self._commit("message_delivered", job.actor, {
                        "target": str(job.payload["target"]), "text": str(job.payload["text"])
                    }, event.id))
        if limit is not None and self.now < limit:
            previous = self.now
            self.now = limit
            out.append(self._commit("time_advanced", None, {
                "from": previous.isoformat(), "to": limit.isoformat()
            }, None))
        return tuple(out)

    def poll(self, actor_id: str) -> dict[str, Any]:
        a = self._actor(actor_id)
        cursor = self._cursor[actor_id]
        visible = [e for e in self.event_log[cursor:] if actor_id in e.visible_to]
        self._cursor[actor_id] = len(self.event_log)
        inbox = list(a.inbox)
        a.inbox.clear()
        return {"observer": actor_id, "time": self.now.isoformat(), "world_version": self.version,
                "location": a.location, "inventory": sorted(a.inventory), "sleeping": a.sleeping,
                "busy_until": a.busy_until.isoformat() if a.busy_until else None,
                "nearby_actors": sorted(x.id for x in self.actors.values() if x.id != actor_id and x.location == a.location),
                "nearby_items": sorted(i for i, loc in self.item_locations.items() if loc == a.location),
                "inbox": inbox, "events": [self._public(e) for e in visible]}

    def replayable_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._public(e) | {"visible_to": sorted(e.visible_to), "world_version": e.world_version} for e in self.event_log)

    def commit_external(self, kind: str, actor: str | None,
                        payload: Mapping[str, Any], cause: int | None = None) -> Event:
        """Commit an authorized objective extension event."""
        if not kind.startswith("system_"):
            raise ValueError("external events must use the system_ namespace")
        if actor is not None:
            self._actor(actor)
        return self._commit(kind, actor, payload, cause)

    def _duration(self, a: ActorState, i: Intention) -> timedelta:
        x = i.args
        if i.kind in {"wait", "sleep"}:
            seconds = x.get("duration_seconds")
            if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
                raise ActionRejected("duration must be a positive integer")
            return timedelta(seconds=seconds)
        if i.kind == "speak":
            if not isinstance(x.get("text"), str) or not x["text"]: raise ActionRejected("speech needs text")
            if x.get("volume", "normal") not in {"quiet", "normal", "loud"}: raise ActionRejected("invalid speech volume")
            return timedelta(seconds=max(1, (len(x["text"]) + 7) // 8))
        if i.kind == "send_message":
            self._actor(str(x.get("target")))
            if not isinstance(x.get("text"), str) or not x["text"]: raise ActionRejected("message needs text")
            return timedelta(seconds=5)
        if i.kind == "inspect":
            item = str(x.get("item"))
            if self.item_locations.get(item) != a.location and item not in a.inventory:
                raise ActionRejected("item unavailable at current location")
            return timedelta(0)
        if i.kind == "search":
            return timedelta(0)
        if i.kind == "knock":
            target = str(x.get("target"))
            self._require_location(target)
            if self.locations[target].open:
                raise ActionRejected("target is already open")
            if (a.location, target) not in self.routes:
                raise ActionRejected("target is not reachable")
            return timedelta(seconds=3)
        if i.kind == "give":
            target = self._actor(str(x.get("target")))
            if target.id == a.id or target.location != a.location:
                raise ActionRejected("target must be co-located")
            if str(x.get("item")) not in a.inventory:
                raise ActionRejected("item is not held")
            return timedelta(seconds=2)
        if i.kind == "move":
            target = str(x.get("target")); self._require_location(target)
            if not self.locations[target].open: raise ActionRejected("destination is closed")
            duration = self.routes.get((a.location, target))
            if duration is None or x.get("duration_seconds", duration) != duration: raise ActionRejected("invalid route")
            return timedelta(seconds=duration)
        if i.kind in {"open", "close"}: return timedelta(0)
        if i.kind == "take":
            if self.item_locations.get(str(x.get("item"))) != a.location: raise ActionRejected("item unavailable")
            return timedelta(0)
        if i.kind == "drop":
            if str(x.get("item")) not in a.inventory: raise ActionRejected("item unavailable")
            return timedelta(0)
        raise ActionRejected("no duration rule")

    def _complete(self, actor_id: str, payload: Mapping[str, Any]) -> None:
        a = self._actor(actor_id); kind = payload["action"]
        if kind == "move": a.location = str(payload["target"])
        elif kind == "send_message":
            target = self._actor(str(payload["target"]))
            target.inbox.append({"from": actor_id, "text": str(payload["text"]), "sent_at": self.now.isoformat()})
        elif kind == "take":
            item = str(payload["item"]); a.inventory.add(item); del self.item_locations[item]
        elif kind == "drop":
            item = str(payload["item"]); a.inventory.remove(item); self.item_locations[item] = a.location
        elif kind == "give":
            item = str(payload["item"]); target = self._actor(str(payload["target"]))
            a.inventory.remove(item); target.inventory.add(item)
        elif kind in {"open", "close"}:
            old = self.locations[a.location]
            self.locations[a.location] = LocationState(old.id, kind == "open", old.x, old.y,
                                                       old.sound_radius, old.sound_loss)
        elif kind == "sleep": a.sleeping = False
        a.busy_until = None

    def _commit_interaction(self, actor_id: str, payload: Mapping[str, Any], cause: int) -> Event:
        actor = self._actor(actor_id)
        kind = str(payload["action"])
        return self._commit(self._interaction_event(kind), actor_id,
                            self._interaction_payload(actor, payload), cause)

    def _interaction_event(self, kind: str) -> str:
        return {"inspect": "item_inspected", "search": "location_searched", "knock": "knock", "give": "item_given"}[kind]

    def _interaction_payload(self, actor: ActorState, intention: Mapping[str, Any]) -> dict[str, Any]:
        kind = str(intention["action"])
        if kind == "inspect":
            item = str(intention["item"])
            return {"item": item, "location": actor.location, "held": item in actor.inventory}
        if kind == "search":
            return {"location": actor.location,
                    "items": sorted(item for item, location in self.item_locations.items()
                                     if location == actor.location)}
        if kind == "give":
            return {"item": str(intention["item"]), "from": actor.id, "to": str(intention["target"])}
        return {"target": str(intention["target"])}

    def _commit(self, kind: str, actor: str | None, payload: Mapping[str, Any], cause: int | None) -> Event:
        visible = self._visibility(kind, actor, payload)
        event = Event(next(self._event_id), self.now, kind, actor, dict(payload), cause,
                      frozenset(visible), self.version + 1)
        self.version += 1; self.event_log.append(event); return event

    def _visibility(self, kind: str, actor: str | None, payload: Mapping[str, Any]) -> set[str]:
        if kind.startswith("system_"):
            return {str(actor)} if actor is not None else set()
        if kind == "world_event" and payload.get("target"):
            return {str(payload["target"])}
        if kind == "action_started" and payload.get("action") == "send_message":
            return {str(actor)}
        if kind == "action_started" and payload.get("action") == "speak":
            return self._hearing_actors(str(actor), payload)
        if kind == "message_sent": return {str(actor)}
        if kind == "message_delivered": return {str(payload["target"]), str(actor)}
        if kind == "speech":
            return self._hearing_actors(str(actor), payload)
        if kind == "action_completed" and payload.get("action") in {"inspect", "search"}:
            return {str(actor)}
        if kind == "action_completed" and payload.get("action") == "give":
            return {str(actor), str(payload["target"])}
        if kind in {"item_inspected", "location_searched"}:
            return {str(actor)}
        if kind == "item_given":
            return {str(payload["from"]), str(payload["to"])}
        if kind == "knock":
            target = str(payload["target"])
            return {str(actor)} | {x.id for x in self.actors.values() if x.location == target}
        if actor is None: return set(self.actors)
        visible = {x.id for x in self.actors.values()
                   if x.location == self._actor(actor).location} | {str(actor)}
        # Completion is committed before the state mutation, so an arrival
        # must also be visible to actors already at the destination.
        if kind == "action_completed" and payload.get("action") == "move":
            target = str(payload.get("target"))
            visible.update(x.id for x in self.actors.values() if x.location == target)
        return visible

    def _schedule(self, time: datetime, kind: str, actor: str | None, payload: Mapping[str, Any], cause: int | None) -> None:
        heapq.heappush(self._queue, _Scheduled(time, next(self._sequence), kind, actor, dict(payload), cause))

    @staticmethod
    def _public_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        return {"action": payload["action"]} if payload.get("action") == "send_message" else dict(payload)

    @staticmethod
    def _public(e: Event) -> dict[str, Any]:
        return {"id": e.id, "time": e.time.isoformat(), "kind": e.kind, "actor": e.actor, "payload": dict(e.payload), "cause": e.cause}

    def _actor(self, actor_id: str) -> ActorState:
        if actor_id not in self.actors: raise ActionRejected(f"unknown actor: {actor_id}")
        return self.actors[actor_id]

    def _require_location(self, location: str) -> None:
        if location not in self.locations: raise ValueError(f"unknown location: {location}")

    def _hearing_actors(self, actor_id: str, payload: Mapping[str, Any]) -> set[str]:
        source = self._actor(actor_id)
        source_loc = self.locations[source.location]
        if not source_loc.open:
            return {actor_id}
        volume = payload.get("volume", "normal")
        gain = {"quiet": -10.0, "normal": 0.0, "loud": 10.0}.get(volume)
        if gain is None:
            return {actor_id}
        heard: set[str] = set()
        for listener in self.actors.values():
            target_loc = self.locations[listener.location]
            if not target_loc.open and listener.id != actor_id:
                continue
            dx = source_loc.x - target_loc.x; dy = source_loc.y - target_loc.y
            distance = (dx * dx + dy * dy) ** 0.5
            barrier = self.sound_barriers.get((source.location, listener.location),
                      self.sound_barriers.get((listener.location, source.location), 0.0))
            loss = distance + source_loc.sound_loss + target_loc.sound_loss + barrier
            if loss <= source_loc.sound_radius + gain:
                heard.add(listener.id)
        heard.add(actor_id)
        return heard
