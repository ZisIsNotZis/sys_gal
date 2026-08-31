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
import copy
from typing import Any, Iterable, Mapping

from .action_schema import validate_action_args


class ActionRejected(ValueError):
    """A concrete, no-state-effect rejection carrying actionable guidance.

    ``alternatives`` are objective, story-neutral suggestions derived only
    from current world state (what is present here, what is reachable, what a
    place supports). They never contain secrets or other actors' private
    state. ``context`` is machine-readable objective detail used by the
    runner to enrich the actor's feedback.
    """

    def __init__(self, message: str, *, alternatives: Iterable[str] = (),
                 context: Mapping[str, Any] | None = None) -> None:
        super().__init__(str(message))
        self.message = str(message)
        self.alternatives = list(alternatives)
        self.context = dict(context or {})


class CheckpointError(ValueError):
    pass


@dataclass
class ActorState:
    id: str
    location: str
    inventory: set[str] = field(default_factory=set)
    busy_until: datetime | None = None
    sleeping: bool = False
    inbox: list[dict[str, Any]] = field(default_factory=list)
    known_contacts: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class LocationState:
    id: str
    open: bool = True
    x: float = 0.0
    y: float = 0.0
    sound_radius: float = 0.0
    sound_loss: float = 0.0
    physical_capabilities: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    # ``controllable`` is the only condition under which an actor may change
    # a public location's open/closed state. Shared places default to not
    # controllable so one character cannot accidentally lock the whole map.
    controllable: bool = False


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


def _set_location_open(world: "World", location_id: str, open_: bool) -> None:
    old = world.locations[location_id]
    world.locations[location_id] = LocationState(
        old.id, open_, old.x, old.y, old.sound_radius, old.sound_loss,
        old.physical_capabilities, old.controllable)


def apply_world_effects(world: "World", payload: Mapping[str, Any]) -> None:
    """Apply story-neutral scheduled world effects to objective state.

    Effects mutate only objective world state (open flags, item/document
    placement). They are validated by the world loader before a run starts
    and are replayed by ``replay.replay_world`` so state stays
    reconstructable. No effect carries narrative or emotional meaning.
    """
    for effect in payload.get("effects", ()):
        op = str(effect.get("op", ""))
        if op == "open_location":
            _set_location_open(world, str(effect["id"]), True)
        elif op == "close_location":
            _set_location_open(world, str(effect["id"]), False)
        elif op in {"add_item", "add_document", "move_item"}:
            world.item_locations[str(effect["id"])] = str(effect["location"])
        elif op == "remove_item":
            world.item_locations.pop(str(effect["id"]), None)


class World:
    """Authoritative, deterministic, event-sourced physical/social world."""

    ACTIONS = {"wait", "speak", "send_message", "move", "open", "close",
               "take", "drop", "sleep", "inspect", "search", "interact", "knock", "give",
               "read", "copy", "label", "annotate", "compare"}

    def __init__(self, *, start: datetime, actors: Iterable[ActorState],
                 locations: Iterable[LocationState],
                 item_locations: Mapping[str, str] | None = None,
                 routes: Mapping[tuple[str, str], int] | None = None,
                 sound_barriers: Mapping[tuple[str, str], float] | None = None,
                 scheduled: Iterable[Mapping[str, Any]] | None = None,
                 document_defs: Mapping[str, Mapping[str, Any]] | None = None,
                 copy_material_items: Iterable[str] | None = None,
                 entity_descriptions: Mapping[str, str] | None = None,
                 entity_access: Mapping[str, Iterable[str]] | None = None,
                 public_knowledge: Mapping[str, str] | None = None,
                 private_knowledge: Mapping[str, Mapping[str, str]] | None = None,
                 longest_wait_seconds: int = 3600) -> None:
        actor_list = list(actors)
        self.now = start
        self.version = 0
        self.longest_wait_seconds = int(longest_wait_seconds)
        self.actors = {a.id: a for a in actor_list}
        self.locations = {x.id: x for x in locations}
        self.item_locations = dict(item_locations or {})
        self.routes = dict(routes or {})
        self.sound_barriers = dict(sound_barriers or {})
        self.document_defs = {str(k): dict(v) for k, v in (document_defs or {}).items()}
        self.copy_material_items = set(copy_material_items or ())
        self.entity_descriptions = dict(entity_descriptions or {})
        self.entity_access = {str(k): set(v) for k, v in (entity_access or {}).items()}
        self.public_knowledge = dict(public_knowledge or {})
        self.private_knowledge = {str(k): dict(v) for k, v in (private_knowledge or {}).items()}
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

    def checkpoint_state(self) -> dict[str, Any]:
        """Return all mutable state needed to continue at the same boundary."""
        return {
            "format": "v3-world-checkpoint-1", "now": self.now.isoformat(),
            "version": self.version, "next_sequence": max((job.sequence for job in self._queue), default=0) + 1,
            "next_event_id": len(self.event_log) + 1,
            "actors": {key: {"id": value.id, "location": value.location,
                              "inventory": sorted(value.inventory),
                              "busy_until": value.busy_until.isoformat() if value.busy_until else None,
                              "sleeping": value.sleeping, "inbox": copy.deepcopy(value.inbox),
                              "known_contacts": sorted(value.known_contacts)}
                       for key, value in self.actors.items()},
            "locations": {key: {"id": value.id, "open": value.open, "x": value.x,
                                 "y": value.y, "sound_radius": value.sound_radius,
                                 "sound_loss": value.sound_loss,
                                 "controllable": value.controllable,
                                 "physical_capabilities": dict(value.physical_capabilities)}
                          for key, value in self.locations.items()},
            "item_locations": dict(self.item_locations),
            "document_defs": copy.deepcopy(self.document_defs),
            "queue": [{"time": job.time.isoformat(), "sequence": job.sequence,
                       "kind": job.kind, "actor": job.actor, "payload": dict(job.payload),
                       "cause": job.cause} for job in sorted(self._queue)],
            "event_log": [{"id": event.id, "time": event.time.isoformat(), "kind": event.kind,
                           "actor": event.actor, "payload": dict(event.payload), "cause": event.cause,
                           "visible_to": sorted(event.visible_to), "world_version": event.world_version}
                          for event in self.event_log],
            "cursor": dict(self._cursor),
        }

    @classmethod
    def from_checkpoint(cls, base: "World", state: Mapping[str, Any]) -> "World":
        restored = cls.__new__(cls)
        restored.restore_checkpoint(state, base=base)
        return restored

    def restore_checkpoint(self, state: Mapping[str, Any], *, base: "World" | None = None) -> None:
        try:
            if state.get("format") != "v3-world-checkpoint-1":
                raise CheckpointError("unsupported world checkpoint format")
            if set(state["actors"]) != set((base or self).actors):
                raise CheckpointError("checkpoint actor set does not match world")
            source = base or self
            actors = {}
            for key, row in state["actors"].items():
                actors[key] = ActorState(str(row["id"]), str(row["location"]),
                    set(row["inventory"]), datetime.fromisoformat(row["busy_until"]) if row["busy_until"] else None,
                    bool(row["sleeping"]), copy.deepcopy(row["inbox"]), set(row["known_contacts"]))
            locations = {key: LocationState(str(row["id"]), bool(row["open"]), float(row["x"]),
                float(row["y"]), float(row["sound_radius"]), float(row["sound_loss"]),
                dict(row.get("physical_capabilities", {})), bool(row.get("controllable", False)))
                for key, row in state["locations"].items()}
            events = [Event(int(row["id"]), datetime.fromisoformat(row["time"]), str(row["kind"]),
                row["actor"], dict(row["payload"]), row["cause"], frozenset(row["visible_to"]),
                int(row["world_version"])) for row in state["event_log"]]
            if [event.id for event in events] != list(range(1, len(events) + 1)):
                raise CheckpointError("checkpoint event log is not contiguous")
            self.now = datetime.fromisoformat(str(state["now"]))
            self.version = int(state["version"]); self.actors = actors; self.locations = locations
            self.item_locations = dict(state["item_locations"]); self.document_defs = copy.deepcopy(state["document_defs"])
            self.event_log = events; self._cursor = {str(k): int(v) for k, v in state["cursor"].items()}
            self._queue = [_Scheduled(datetime.fromisoformat(row["time"]), int(row["sequence"]),
                str(row["kind"]), row["actor"], dict(row["payload"]), row["cause"]) for row in state["queue"]]
            heapq.heapify(self._queue)
            self._sequence = itertools.count(int(state["next_sequence"]))
            self._event_id = itertools.count(int(state["next_event_id"]))
            self.routes = dict(source.routes); self.sound_barriers = dict(source.sound_barriers)
            self.copy_material_items = set(source.copy_material_items); self.entity_descriptions = source.entity_descriptions
            self.longest_wait_seconds = source.longest_wait_seconds
            self.entity_access = {key: set(value) for key, value in source.entity_access.items()}
            self.public_knowledge = dict(source.public_knowledge)
            self.private_knowledge = {key: dict(value) for key, value in source.private_knowledge.items()}
        except CheckpointError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise CheckpointError(f"invalid world checkpoint: {exc}") from exc

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
        controllable = self.locations[a.location].controllable
        options: list[dict[str, Any]] = [
            {"kind": "wait", "duration_seconds": 900},
            {"kind": "wait", "duration_seconds": self.longest_wait_seconds},
            {"kind": "speak", "text": "", "volume": "normal"},
            *({"kind": "send_message", "target": other} for other in self._message_targets(a)),
            *({"kind": "move", "target": target, "duration_seconds": duration}
              for (source, target), duration in self.routes.items() if source == a.location),
            *([{"kind": "open" if not self.locations[a.location].open else "close"}]
              if controllable else []),
            {"kind": "sleep", "duration_seconds": 6 * 60 * 60},
        ]
        options += [{"kind": "take", "item": item} for item, loc in self.item_locations.items() if loc == a.location]
        options += [{"kind": "inspect", "item": item} for item, loc in self.item_locations.items() if loc == a.location]
        options += [{"kind": "inspect", "item": item} for item in sorted(a.inventory)]
        options.append({"kind": "search"})
        options += [{"kind": "interact", "target": location.id, "verb": verb, "parameters": dict(spec.get("parameters", {}))}
                    for location in self.locations.values() if (a.location, location.id) in self.routes
                    for verb, spec in self._physical_capabilities(location).items()
                    if self._interaction_offered(location, verb)]
        # Compatibility alias retained for existing deterministic callers; new
        # agents receive the generic shape above.
        options += [{"kind": "knock", "target": location.id} for location in self.locations.values()
                    if not location.open and (a.location, location.id) in self.routes]
        options += [{"kind": "give", "target": other.id, "item": item}
                    for other in self.actors.values()
                    if other.id != actor_id and other.location == a.location
                    for item in sorted(a.inventory)]
        options += [{"kind": "drop", "item": item} for item in sorted(a.inventory)]
        available_documents = [document for document in self.document_defs
                               if self._entity_available(a.id, document)]
        options += [{"kind": "read", "document": document} for document in sorted(available_documents)]
        options += [{"kind": "compare", "first": first, "second": second}
                    for index, first in enumerate(sorted(available_documents))
                    for second in sorted(available_documents)[index + 1:]]
        options += [{"kind": "copy", "document": document}
                    for document in sorted(available_documents)
                    if any(item in a.inventory for item in self.copy_material_items)]
        options += [{"kind": "label", "document": document, "label": ""}
                    for document in sorted(available_documents)]
        options += [{"kind": "annotate", "document": document, "text": ""}
                    for document in sorted(available_documents)]
        return options

    def submit(self, intention: Intention) -> tuple[Event, ...]:
        a = self._actor(intention.actor)
        if intention.expected_version is not None and intention.expected_version != self.version:
            raise ActionRejected("stale world version")
        if intention.kind not in self.ACTIONS:
            raise ActionRejected(f"unknown action '{intention.kind}'")
        shape_error = validate_action_args(intention.kind, intention.args)
        if shape_error is not None:
            raise ActionRejected(shape_error)
        if a.busy_until and a.busy_until > self.now:
            raise ActionRejected("actor is busy")
        duration = self._duration(a, intention)
        action_payload = {"action": intention.kind, **dict(intention.args)}
        if intention.kind == "copy":
            source = str(action_payload["document"])
            action_payload["copy"] = f"{source}-copy-{self.version + 1}"
        started = self._commit("action_started", a.id, action_payload, None)
        if intention.kind == "speak":
            self._commit("speech", a.id, {"text": intention.args["text"],
                                           "volume": intention.args.get("volume", "normal")}, started.id)
        elif intention.kind == "send_message":
            self._commit("message_sent", a.id, {"target": str(intention.args["target"])}, started.id)
        self._schedule(self.now + duration, "action_completed", a.id,
                       action_payload, started.id)
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
                if job.payload["action"] in {"inspect", "search", "knock", "interact"}:
                    out.append(self._commit_interaction(job.actor, job.payload, event.id))
                if job.payload["action"] == "give":
                    out.append(self._commit_interaction(job.actor, job.payload, event.id))
                if job.payload["action"] == "send_message":
                    out.append(self._commit("message_delivered", job.actor, {
                        "target": str(job.payload["target"]), "text": str(job.payload["text"])
                    }, event.id))
                if job.payload["action"] in {"read", "copy", "label", "annotate", "compare"}:
                    out.append(self._commit_interaction(job.actor, job.payload, event.id))
            elif job.kind == "world_event":
                # Seeded world events may carry story-neutral objective
                # effects (open/close a place, place an item or document).
                # Replay applies the same effects so state stays reconstructable.
                apply_world_effects(self, job.payload)
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
                "inbox": inbox, "events": [self._public(e) for e in visible],
                "descriptions": {entity_id: self.entity_descriptions[entity_id]
                                 for entity_id in self._visible_descriptions(a)
                                 if entity_id in self.entity_descriptions},
                "knowledge": self._knowledge(a)}

    def _visible_descriptions(self, actor: ActorState) -> set[str]:
        visible = {actor.location}
        visible.update(item for item, location in self.item_locations.items() if location == actor.location)
        visible.update(item for item in actor.inventory)
        visible.update(entity for entity, allowed in self.entity_access.items() if actor.id in allowed)
        return visible

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
            if not isinstance(x.get("text"), str) or not x["text"]:
                raise ActionRejected("speech needs non-empty text")
            if x.get("volume", "normal") not in {"quiet", "normal", "loud"}:
                raise ActionRejected("speech volume must be quiet, normal, or loud")
            return timedelta(seconds=max(1, (len(x["text"]) + 7) // 8))
        if i.kind == "send_message":
            target_id = x.get("target")
            if not isinstance(target_id, str) or not target_id:
                reachable = self._message_targets(a)
                raise ActionRejected(
                    "send_message needs a target person named in the 'target' argument.",
                    alternatives=[f"send_message to {other}" for other in reachable],
                    context={"missing": "target"})
            target = self._actor(target_id)
            if target.id != a.id and target.id not in a.known_contacts and target.location != a.location:
                reachable = self._message_targets(a)
                raise ActionRejected(
                    f"You cannot reach {target.id}: they are not among your known contacts and are not here with you.",
                    alternatives=[f"send_message to {other}" for other in reachable],
                    context={"target": target.id})
            if not isinstance(x.get("text"), str) or not x["text"]:
                raise ActionRejected("message text must be non-empty")
            return timedelta(seconds=5)
        if i.kind in {"read", "copy", "label", "annotate", "compare"}:
            return self._document_duration(a, i)
        if i.kind == "inspect":
            item = str(x.get("item"))
            here, held = self._present_items(a)
            if self.item_locations.get(item) != a.location and item not in a.inventory:
                raise ActionRejected(
                    f"'{item}' is not here. In this location: {', '.join(here) or 'nothing'}. "
                    f"You are holding: {', '.join(held) or 'nothing'}.",
                    alternatives=[f"inspect {present}" for present in here],
                    context={"item": item})
            return timedelta(0)
        if i.kind == "search":
            return timedelta(0)
        if i.kind in {"interact", "knock"}:
            if i.kind == "knock":
                target, verb, parameters = str(x.get("target")), "knock", {}
            else:
                target, verb, parameters = str(x.get("target")), x.get("verb"), x.get("parameters", {})
            if target not in self.locations or (a.location, target) not in self.routes:
                reachable = self._reachable(a)
                known = target in self.locations
                message = (f"'{target}' is not a known place." if not known
                           else f"You cannot reach '{target}' from {a.location}.")
                raise ActionRejected(
                    message,
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"target": target})
            if not isinstance(verb, str) or not isinstance(parameters, dict):
                raise ActionRejected("interaction needs a string verb and mapping parameters")
            capabilities = self._physical_capabilities(self.locations[target])
            if verb not in capabilities:
                supported = sorted(capabilities)
                raise ActionRejected(
                    f"'{target}' does not support '{verb}'. Supported interactions: "
                    f"{', '.join(supported) or 'none'}.",
                    alternatives=[f"interact with {target} ({verb_name})" for verb_name in supported],
                    context={"target": target, "verb": verb})
            expected = capabilities[verb].get("parameters", {})
            if parameters != expected:
                raise ActionRejected(f"'{verb}' on {target} requires parameters {expected}.")
            return timedelta(seconds=3)
        if i.kind == "give":
            target_id = x.get("target")
            if not isinstance(target_id, str) or not target_id:
                raise ActionRejected("give needs a target person named in the 'target' argument.",
                                     context={"missing": "target"})
            target = self._actor(target_id)
            if target.id == a.id or target.location != a.location:
                alternatives = [f"send_message to {target.id}"] if target.id in a.known_contacts else []
                raise ActionRejected(
                    f"{target.id} is not here with you, so you cannot hand them anything.",
                    alternatives=alternatives,
                    context={"target": target.id, "co_located": False})
            item = str(x.get("item"))
            if item not in a.inventory:
                raise ActionRejected(
                    f"You are not holding '{item}'. You hold: {', '.join(sorted(a.inventory)) or 'nothing'}.")
            return timedelta(seconds=2)
        if i.kind == "move":
            target = str(x.get("target"))
            if target not in self.locations:
                reachable = self._reachable(a)
                raise ActionRejected(
                    f"'{target}' is not a known place. From {a.location} you can reach: "
                    f"{', '.join(reachable) or 'nothing'}.",
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"target": target})
            if not self.locations[target].open:
                open_neighbors = self._reachable_open(a)
                raise ActionRejected(
                    f"'{target}' is closed right now and you cannot enter it.",
                    alternatives=[f"move to {neighbor} (open)" for neighbor in open_neighbors],
                    context={"target": target, "open": False})
            duration = self.routes.get((a.location, target))
            if duration is None:
                reachable = self._reachable(a)
                raise ActionRejected(
                    f"There is no direct path from {a.location} to '{target}'.",
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"from": a.location, "target": target})
            if x.get("duration_seconds", duration) != duration:
                raise ActionRejected(
                    f"The walk from {a.location} to '{target}' takes {duration} seconds, "
                    f"not {x.get('duration_seconds')}.")
            return timedelta(seconds=duration)
        if i.kind in {"open", "close"}:
            if not self.locations[a.location].controllable:
                raise ActionRejected(
                    f"You cannot {i.kind} {a.location}: it is not under your control.",
                    context={"location": a.location, "controllable": False})
            return timedelta(0)
        if i.kind == "take":
            item = str(x.get("item"))
            here, held = self._present_items(a)
            if self.item_locations.get(item) != a.location:
                raise ActionRejected(
                    f"'{item}' is not here to pick up. In this location: {', '.join(here) or 'nothing'}. "
                    f"You are holding: {', '.join(held) or 'nothing'}.",
                    alternatives=[f"take {present}" for present in here],
                    context={"item": item})
            return timedelta(0)
        if i.kind == "drop":
            item = str(x.get("item"))
            if item not in a.inventory:
                raise ActionRejected(
                    f"You are not holding '{item}'. You hold: {', '.join(sorted(a.inventory)) or 'nothing'}.")
            return timedelta(0)
        raise ActionRejected("no duration rule")

    def resolve_entity(self, actor_id: str, entity_id: str) -> str | None:
        self._actor(actor_id)
        if not self._entity_available(actor_id, entity_id):
            return None
        return self.entity_descriptions.get(entity_id)

    def _entity_available(self, actor_id: str, entity_id: str) -> bool:
        actor = self._actor(actor_id)
        return (entity_id in actor.inventory or self.item_locations.get(entity_id) == actor.location
                or actor_id in self.entity_access.get(entity_id, set()))

    def _document_duration(self, actor: ActorState, intention: Intention) -> timedelta:
        kind = intention.kind
        if kind == "compare":
            first, second = str(intention.args.get("first")), str(intention.args.get("second"))
            if first not in self.document_defs or second not in self.document_defs:
                raise ActionRejected("both documents must exist")
            if not self._entity_available(actor.id, first) or not self._entity_available(actor.id, second):
                available = self._available_documents(actor)
                raise ActionRejected(
                    f"You cannot compare {first} and {second}: not all are available to you. "
                    f"You can read: {', '.join(available) or 'none'}.",
                    alternatives=[f"read {document}" for document in available],
                    context={"first": first, "second": second})
            return timedelta(seconds=30)
        document = str(intention.args.get("document"))
        if document not in self.document_defs or not self._entity_available(actor.id, document):
            available = self._available_documents(actor)
            raise ActionRejected(
                f"'{document}' is not available to you right now. "
                f"You can read: {', '.join(available) or 'none'}.",
                alternatives=[f"read {present}" for present in available],
                context={"document": document})
        if kind == "copy":
            if not any(item in actor.inventory for item in self.copy_material_items):
                raise ActionRejected(
                    f"Copying requires a copy material. You have: "
                    f"{', '.join(sorted(actor.inventory)) or 'nothing'}.",
                    context={"copy_material": sorted(self.copy_material_items)})
            return timedelta(seconds=int(self.document_defs[document].get("reading_seconds", 30)) + 15)
        if kind == "label":
            label = intention.args.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ActionRejected("label needs non-empty text")
            return timedelta(seconds=3)
        if kind == "annotate":
            text = intention.args.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ActionRejected("annotate needs non-empty text")
            return timedelta(seconds=3)
        return timedelta(seconds=int(self.document_defs[document].get("reading_seconds", 30)))

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
        elif kind == "copy":
            material = sorted(item for item in self.copy_material_items if item in a.inventory)[0]
            a.inventory.remove(material)
            source = str(payload["document"])
            copy_id = str(payload.get("copy") or f"{source}-copy-{self.version + 1}")
            self.document_defs[copy_id] = {**self.document_defs[source], "copied_from": source}
            self.item_locations[copy_id] = a.location
        elif kind in {"open", "close"}:
            _set_location_open(self, a.location, kind == "open")
        elif kind == "sleep": a.sleeping = False
        a.busy_until = None

    def _commit_interaction(self, actor_id: str, payload: Mapping[str, Any], cause: int) -> Event:
        actor = self._actor(actor_id)
        kind = str(payload["action"])
        return self._commit(self._interaction_event(kind), actor_id,
                            self._interaction_payload(actor, payload), cause)

    def _interaction_event(self, kind: str) -> str:
        return {"inspect": "item_inspected", "search": "location_searched", "knock": "knock", "interact": "interaction", "give": "item_given",
                "read": "document_read", "copy": "document_copied", "label": "document_labeled", "annotate": "document_annotated",
                "compare": "documents_compared"}[kind]

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
        if kind == "read":
            document = str(intention["document"])
            return {"document": document, "title": self.document_defs[document].get("title", document),
                    "content": self.document_defs[document].get("content", ""),
                    "annotations": [dict(entry) for entry in self.document_defs[document].get("annotations", [])]}
        if kind == "annotate":
            document = str(intention["document"])
            annotation = {"text": str(intention.get("text")), "by": actor.id,
                          "time": self.now.isoformat()}
            self.document_defs[document].setdefault("annotations", []).append(annotation)
            return {"document": document, "annotation": str(intention.get("text")), "by": actor.id}
        if kind == "copy":
            source = str(intention["document"])
            # The scheduled action already owns the deterministic copy ID.
            # Recomputing it here races the event-version counter and breaks
            # the public completion event and replay provenance.
            copy = str(intention.get("copy") or f"{source}-copy-{self.version + 1}")
            return {"document": source, "copy": copy, "copied_from": source, "location": actor.location}
        if kind == "label":
            document = str(intention["document"])
            self.document_defs[document].setdefault("labels", []).append(str(intention["label"]))
            return {"document": document, "label": str(intention["label"])}
        if kind == "compare":
            first, second = str(intention["first"]), str(intention["second"])
            return {"first": first, "second": second,
                    "same_content": self.document_defs[first].get("content") == self.document_defs[second].get("content")}
        if kind == "knock":
            target = str(intention["target"])
            occupants = [x.id for x in self.actors.values() if x.location == target]
            return {"target": target, "responded": bool(occupants)}
        if kind == "interact":
            target = str(intention.get("target"))
            occupants = [x.id for x in self.actors.values() if x.location == target]
            return {"target": target, "verb": str(intention.get("verb", "knock")),
                    "parameters": dict(intention.get("parameters", {})),
                    "responded": bool(occupants)}
        return {"target": str(intention["target"])}

    def _commit(self, kind: str, actor: str | None, payload: Mapping[str, Any], cause: int | None) -> Event:
        visible = self._visibility(kind, actor, payload)
        event = Event(next(self._event_id), self.now, kind, actor, dict(payload), cause,
                      frozenset(visible), self.version + 1)
        self.version += 1; self.event_log.append(event); return event

    def _visibility(self, kind: str, actor: str | None, payload: Mapping[str, Any]) -> set[str]:
        if kind.startswith("system_"):
            return {str(actor)} if actor is not None else set()
        if kind in {"document_read", "document_copied", "document_labeled", "document_annotated", "documents_compared"}:
            return {str(actor)}
        if kind in {"action_started", "action_completed"} and payload.get("action") in {
                "read", "copy", "label", "compare"}:
            return {str(actor)}
        if kind == "world_event" and payload.get("target"):
            targets = payload["target"] if isinstance(payload["target"], (list, tuple)) else [payload["target"]]
            return {str(target) for target in targets}
        if kind == "action_started" and payload.get("action") == "send_message":
            return {str(actor)}
        if kind == "action_started" and payload.get("action") == "speak":
            return self._hearing_actors(str(actor), payload)
        if kind == "action_completed" and payload.get("action") == "speak":
            # Speech visibility is determined when it is emitted, not when
            # the duration completes; never replay text to a later audience.
            return {str(actor)}
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
        if kind in {"knock", "interaction"}:
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

    @staticmethod
    def _physical_capabilities(location: LocationState) -> Mapping[str, Mapping[str, Any]]:
        if location.physical_capabilities:
            return location.physical_capabilities
        return {"knock": {"parameters": {}}} if not location.open else {}

    @classmethod
    def _interaction_offered(cls, location: LocationState, verb: str) -> bool:
        return verb != "knock" or not location.open

    def _knowledge(self, actor: ActorState) -> dict[str, dict[str, str]]:
        result = {key: {"public": value} for key, value in self.public_knowledge.items()}
        for entity, owners in self.private_knowledge.items():
            if actor.id in owners:
                result.setdefault(entity, {})["private"] = owners[actor.id]
        return result

    def _schedule(self, time: datetime, kind: str, actor: str | None, payload: Mapping[str, Any], cause: int | None) -> None:
        heapq.heappush(self._queue, _Scheduled(time, next(self._sequence), kind, actor, dict(payload), cause))

    @staticmethod
    def _public_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
        if payload.get("action") == "send_message":
            # The sender must know which recipient's delivery is pending, but
            # the text is carried only by the private delivery event.
            return {"action": "send_message", "target": payload.get("target")}
        return dict(payload)

    @staticmethod
    def _public(e: Event) -> dict[str, Any]:
        return {"id": e.id, "time": e.time.isoformat(), "kind": e.kind, "actor": e.actor, "payload": dict(e.payload), "cause": e.cause}

    def _actor(self, actor_id: str) -> ActorState:
        if actor_id not in self.actors: raise ActionRejected(f"unknown actor: {actor_id}")
        return self.actors[actor_id]

    def _message_targets(self, actor: ActorState) -> list[str]:
        """Expose only addressable people; the world does not reveal its roster."""
        return sorted({other.id for other in self.actors.values()
                       if other.id != actor.id and (
                           other.id in actor.known_contacts or other.location == actor.location)})

    def _require_location(self, location: str) -> None:
        if location not in self.locations: raise ValueError(f"unknown location: {location}")

    def _present_items(self, actor: ActorState) -> tuple[list[str], list[str]]:
        here = sorted(item for item, location in self.item_locations.items()
                      if location == actor.location)
        return here, sorted(actor.inventory)

    def _reachable(self, actor: ActorState) -> list[str]:
        return sorted(target for (source, target) in self.routes if source == actor.location)

    def _reachable_open(self, actor: ActorState) -> list[str]:
        return sorted(target for (source, target) in self.routes
                      if source == actor.location and self.locations[target].open)

    def _available_documents(self, actor: ActorState) -> list[str]:
        return sorted(document for document in self.document_defs
                      if self._entity_available(actor.id, document))

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
