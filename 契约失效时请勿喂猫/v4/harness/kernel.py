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


TICK_SECONDS = 60
"""One tick (V4-ENGINE.md §2): the unit of minimum action duration, message
delivery delay, the decision-horizon bound, and the actors' common-knowledge
budgeting. Timestamps stay continuous — never assume a time is a tick
multiple, always round durations up with :func:`tick_ceil`."""


def tick_ceil(seconds: float) -> int:
    """Round a raw duration up to whole ticks, minimum one tick
    (V4-ENGINE §2.1: every world action, even a query-like one, costs at
    least one tick)."""
    whole = int(seconds)
    ticks = -(-whole // TICK_SECONDS) if whole > 0 else 1
    return max(1, ticks) * TICK_SECONDS


WAKE_EVENT_KINDS = frozenset({"speech", "message_delivered", "knock", "interaction",
                              "item_given", "extra_arrived", "extra_removed",
                              "action_interrupted", "enter"})
"""Ambient social events that end a light ``wait`` early (V4-ENGINE §3 wake
class). Movement/observation events only queue for the next turn."""


@dataclass
class ActorState:
    id: str
    location: str
    inventory: set[str] = field(default_factory=set)
    busy_until: datetime | None = None
    sleeping: bool = False
    inbox: list[dict[str, Any]] = field(default_factory=list)
    known_contacts: set[str] = field(default_factory=set)
    # In-progress action bookkeeping for the interrupt mechanism.
    current_action: dict[str, Any] | None = None
    # A suspended action: {"payload", "remaining_seconds", "interrupted_by"}.
    pending: dict[str, Any] | None = None
    # Change-driven observation bookkeeping (V4-DESIGN §5.7). Descriptions
    # refresh on their own much-slower counter (§B) and a compaction forces
    # one full re-observation because the actor's context lost the details.
    observed_locations: set[str] = field(default_factory=set)
    rounds_since_observation: int = 0
    observe_request: bool = False
    described_locations: set[str] = field(default_factory=set)
    rounds_since_descriptions: int = 0
    force_observation: bool = False
    # V4-CAST §1: mc | npc | extra. NPCs are event-driven (never clock
    # scheduled); extras are conversation-scoped strangers, destroyed with
    # zero memory when the conversation ends.
    role: str = "mc"


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

    # V4-CAST §1: per-location extra pool. Each entry {fragment, rarity,
    # knowledge_notes}; rarity "common" | "rare" (rare = happens to know more).
    extras: tuple[Mapping[str, Any], ...] = ()

@dataclass(frozen=True)
class Intention:
    actor: str
    kind: str
    args: Mapping[str, Any] = field(default_factory=dict)
    expected_version: int | None = None
    # 心声：the actor's private first-person monologue. The world never reads
    # it; it exists for the actor's own session memory and the trace.
    inner: str | None = None
    # Co-located actors whose in-progress action this submission suspends.
    interrupt: tuple[str, ...] = ()
    # The actor's own declaration that this action cannot be suspended.
    # None means the per-kind default (sleep is uninterruptable).
    uninterruptable: bool | None = None


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
               "read", "copy", "label", "annotate", "compare",
               "observe", "continue_action", "abandon_action", "ask_stranger"}

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
        self._cancelled: set[int] = set()
        self._sequence = itertools.count(1)
        self._event_id = itertools.count(1)
        self._cursor = {a.id: 0 for a in actor_list}
        # Two refresh cadences (V4-DESIGN §5.7 + 首验日反馈): state (layout,
        # knowledge, presence) every N rounds; item descriptions far rarer —
        # M default 99999 means effectively only first arrival / observe /
        # after a compaction. Between refreshes actors track changes from
        # the pushed event stream.
        self.state_refresh_rounds = 20
        self.description_refresh_rounds = 99999
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
            "format": "v4-world-checkpoint-1", "now": self.now.isoformat(),
            "version": self.version, "next_sequence": max((job.sequence for job in self._queue), default=0) + 1,
            "next_event_id": len(self.event_log) + 1,
            "actors": {key: {"id": value.id, "location": value.location,
                              "inventory": sorted(value.inventory),
                              "busy_until": value.busy_until.isoformat() if value.busy_until else None,
                              "sleeping": value.sleeping, "inbox": copy.deepcopy(value.inbox),
                              "known_contacts": sorted(value.known_contacts),
                              "current_action": copy.deepcopy(value.current_action),
                              "pending": copy.deepcopy(value.pending),
                              "observed_locations": sorted(value.observed_locations),
                              "rounds_since_observation": value.rounds_since_observation,
                              "observe_request": value.observe_request,
                              "described_locations": sorted(value.described_locations),
                              "rounds_since_descriptions": value.rounds_since_descriptions,
                              "force_observation": value.force_observation,
                              "role": value.role}
                       for key, value in self.actors.items()},
            "locations": {key: {"id": value.id, "open": value.open, "x": value.x,
                                 "y": value.y, "sound_radius": value.sound_radius,
                                 "sound_loss": value.sound_loss,
                                 "controllable": value.controllable,
                                 "physical_capabilities": dict(value.physical_capabilities),
                                 "extras": [dict(x) for x in value.extras]}
                          for key, value in self.locations.items()},
            "item_locations": dict(self.item_locations),
            "document_defs": copy.deepcopy(self.document_defs),
            "queue": [{"time": job.time.isoformat(), "sequence": job.sequence,
                       "kind": job.kind, "actor": job.actor, "payload": dict(job.payload),
                       "cause": job.cause} for job in sorted(self._queue)
                      if job.sequence not in self._cancelled],
            "cancelled_sequences": sorted(self._cancelled),
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
            if state.get("format") not in {"v3-world-checkpoint-1", "v4-world-checkpoint-1"}:
                raise CheckpointError("unsupported world checkpoint format")
            base_ids = set((base or self).actors)
            ckpt_ids = set(state["actors"])
            extras_only = ckpt_ids - base_ids
            if (base_ids - ckpt_ids) or any(
                    state["actors"][x].get("role") != "extra" for x in extras_only):
                raise CheckpointError("checkpoint actor set does not match world")
                raise CheckpointError("checkpoint actor set does not match world")
            source = base or self
            actors = {}
            for key, row in state["actors"].items():
                actors[key] = ActorState(str(row["id"]), str(row["location"]),
                    set(row["inventory"]), datetime.fromisoformat(row["busy_until"]) if row["busy_until"] else None,
                    bool(row["sleeping"]), copy.deepcopy(row["inbox"]), set(row["known_contacts"]),
                    copy.deepcopy(row.get("current_action")), copy.deepcopy(row.get("pending")),
                    set(row.get("observed_locations", ())), int(row.get("rounds_since_observation", 0)),
                    bool(row.get("observe_request", False)),
                    set(row.get("described_locations", ())), int(row.get("rounds_since_descriptions", 0)),
                    bool(row.get("force_observation", False)),
                    str(row.get("role", "mc")))
            locations = {key: LocationState(str(row["id"]), bool(row["open"]), float(row["x"]),
                float(row["y"]), float(row["sound_radius"]), float(row["sound_loss"]),
                dict(row.get("physical_capabilities", {})), bool(row.get("controllable", False)),
                tuple(dict(x) for x in row.get("extras", ())))
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
            self._cancelled = set(int(x) for x in state.get("cancelled_sequences", ()))
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
            self.state_refresh_rounds = source.state_refresh_rounds
            self.description_refresh_rounds = source.description_refresh_rounds
            self.state_refresh_rounds = source.state_refresh_rounds
            self.description_refresh_rounds = source.description_refresh_rounds
            self.private_knowledge = {key: dict(value) for key, value in source.private_knowledge.items()}
        except CheckpointError:
            raise
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise CheckpointError(f"invalid world checkpoint: {exc}") from exc

    def next_event_time(self) -> datetime | None:
        return self._queue[0].time if self._queue else None

    def next_world_event_time(self) -> datetime | None:
        """Next scheduled world_event (a director beat), ignoring actor jobs."""
        times = [job.time for job in self._queue if job.kind == "world_event"]
        return min(times) if times else None

    def _unseen_social_event(self, actor: ActorState) -> bool:
        """True when a wake-class event the actor has not yet perceived
        (committed after its last poll cursor) is visible to it."""
        cursor = self._cursor.get(actor.id, 0)
        for event in reversed(self.event_log):
            if event.id <= cursor:
                break
            if (event.kind in WAKE_EVENT_KINDS and event.actor != actor.id
                    and actor.id in event.visible_to):
                return True
        return False

    def _route_path(self, source: str, target: str) -> tuple[list[str], list[int]] | None:
        """Shortest walk (by seeded route seconds) as (locations, hop_seconds).
        V4-ENGINE §2: the walk time is the map's physical fact; multi-hop
        routes are found by the engine, never requested by the actor."""
        best = {source: 0}
        prev: dict[str, str] = {}
        pq = [(0, source)]
        while pq:
            cost, node = heapq.heappop(pq)
            if node == target:
                break
            if cost > best.get(node, cost):
                continue
            for (src, dst), secs in self.routes.items():
                if src != node:
                    continue
                next_cost = cost + int(secs)
                if next_cost < best.get(dst, next_cost + 1):
                    best[dst] = next_cost
                    prev[dst] = node
                    heapq.heappush(pq, (next_cost, dst))
        if target not in best:
            return None
        path = [target]
        while path[-1] != source:
            path.append(prev[path[-1]])
        path.reverse()
        hops = [best[b] - best[a] for a, b in zip(path, path[1:])]
        return path, hops

    def _move_hop(self, job: "Any") -> None:
        """Fire one hop boundary: enter the reached location, and (unless it
        is the destination) leave it again immediately — the discrete event
        sequence leave A / enter B / leave B / enter C (V4-ENGINE §2.1).
        Visibility: everyone at the location touched, plus the mover."""
        actor_id = job.actor
        if actor_id not in self.actors:
            return  # a despawned extra's leftover hop must not crash the clock
        a = self.actors[actor_id]
        path, index = job.payload["path"], int(job.payload["index"])
        new = str(path[index])
        if a.location == new:
            return
        a.location = new
        self._commit("enter", actor_id, {"location": new}, None)
        if index < len(path) - 1:
            self._commit("leave", actor_id, {"location": new}, None)

    def _schedule_move_hops(self, actor_id: str, path: list[str],
                            hop_seconds: list[int], duration_seconds: int,
                            cause: int | None) -> list[int]:
        """Schedule the per-hop boundary jobs for a move; returns their queue
        sequences so an interrupt can cancel the remaining hops."""
        total_raw = sum(hop_seconds)
        sequences = []
        elapsed = 0
        for index in range(1, len(path)):
            elapsed += hop_seconds[index - 1]
            when = self.now + timedelta(
                seconds=round(duration_seconds * elapsed / total_raw))
            sequences.append(self._schedule(
                when, "move_hop", actor_id,
                {"path": list(path), "index": index}, cause).sequence)
        return sequences

    def wake_waiter(self, actor_id: str) -> bool:
        """V4-ENGINE §3 wake semantics: an ambient social event ends a light
        ``wait`` early (the waiter notices and takes a turn); ``sleep`` and
        real actions are not wakeable — their events queue for delivery at
        the next turn instead. Returns True when the actor was woken."""
        a = self._actor(actor_id)
        if not a.busy_until or a.busy_until <= self.now or a.current_action is None:
            return False
        if a.current_action.get("payload", {}).get("action") != "wait":
            return False
        sequence = a.current_action.get("sequence")
        if sequence is not None:
            self._cancelled.add(int(sequence))
        self._commit("wait_woken", actor_id, {}, None)
        a.busy_until = None
        a.current_action = None
        return True

    def schedule_private_wake(self, actor_id: str, when: datetime) -> int:
        """V4-ENGINE §3 idle heartbeat: schedule a private event that gives
        the actor a turn even when nothing else happens (MC idle heartbeat).
        Returns the job sequence so the caller can cancel/reschedule it."""
        return self._schedule(when, "private_wake", actor_id, {}, None).sequence

    def cancel_scheduled(self, sequence: int) -> None:
        self._cancelled.add(int(sequence))

    def has_wakeup(self, actor_id: str) -> bool:
        """Return whether an idle actor has observable work to poll."""
        a = self._actor(actor_id)
        if a.busy_until and a.busy_until > self.now:
            return False
        cursor = self._cursor[actor_id]
        return bool(a.inbox or any(actor_id in event.visible_to for event in self.event_log[cursor:]))

    def affordances(self, actor_id: str) -> list[dict[str, Any]]:
        a = self._actor(actor_id)
        if a.pending is not None:
            # A suspended action must be resolved first: continue (keep the
            # remaining progress) or cancel (mark it failed/unfinished).
            return [{"kind": "continue_action"}, {"kind": "abandon_action"}]
        if a.busy_until and a.busy_until > self.now:
            return [{"kind": "wait", "duration_seconds": 900}]
        controllable = self.locations[a.location].controllable
        options: list[dict[str, Any]] = [
            {"kind": "observe"},
            {"kind": "ask_stranger"},
            {"kind": "wait"},
            {"kind": "speak", "text": "", "volume": "normal"},
            *({"kind": "send_message", "target": other} for other in self._message_targets(a)),
            *({"kind": "move", "target": target}
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
            raise ActionRejected("世界已发生变化，请重新观察后再行动（stale world version）")
        if intention.kind not in self.ACTIONS:
            raise ActionRejected(f"未知动作 '{intention.kind}'。可用动作见你收到的动作列表。")
        shape_error = validate_action_args(intention.kind, intention.args)
        if shape_error is not None:
            raise ActionRejected(shape_error)
        if a.pending is not None and intention.kind not in {"continue_action", "abandon_action"}:
            raise ActionRejected("你有一个被打断的动作待处理：请先选择 continue_action 或 abandon_action。")
        if a.busy_until and a.busy_until > self.now:
            raise ActionRejected("你正在忙于当前动作，无法开始新动作。")
        if intention.kind == "continue_action":
            return self._resume(a)
        if intention.kind == "abandon_action":
            return self._abandon(a)
        if intention.kind == "observe":
            a.observe_request = True
        if intention.kind == "ask_stranger":
            question = str(intention.args.get("question", "")).strip()
            if not question:
                raise ActionRejected("ask_stranger 需要写明你想问什么（question）。")
            self._commit("stranger_asked", a.id, {"question": question}, None)
            # 打听花一个 tick：答案以在场路人的 speech 事件出现。
        duration = self._duration(a, intention)
        if intention.kind == "wait" and self._unseen_social_event(a):
            # V4-ENGINE §3: a waiter does not sleep through a social act it
            # has not yet perceived (committed after its last poll — the
            # race where deliberation spans a tick boundary); the wait is a
            # no-op and the event delivers on the actor's next poll.
            return ()
        action_payload = {"action": intention.kind, **dict(intention.args)}
        move_path: list[str] | None = None
        move_hops: list[int] | None = None
        if intention.kind == "move":
            found = self._route_path(a.location, str(intention.args["target"]))
            assert found is not None  # _duration already validated reachability
            move_path, move_hops = found
            action_payload["path"] = list(move_path)
            action_payload["hop_seconds"] = list(move_hops)
        if intention.kind == "copy":
            source = str(action_payload["document"])
            action_payload["copy"] = f"{source}-copy-{self.version + 1}"
        uninterruptable = intention.uninterruptable
        if uninterruptable is None:
            uninterruptable = intention.kind == "sleep"
        started: Event | None = None
        sequence: int | None = None
        if duration:
            started = self._commit("action_started", a.id, action_payload, None)
            # The started event carries the actor's interrupt intent so the
            # suspension side effect is replayable from the log.
            if intention.interrupt:
                started = self._commit("interrupt_requested", a.id, {
                    "targets": list(intention.interrupt)}, started.id)
            if move_path is not None:
                # Departure broadcasts immediately: the origin location sees
                # the actor leave at t0 (V4 multi-hop move semantics).
                self._commit("leave", a.id, {"location": a.location}, None)
        if intention.kind == "speak":
            speech_payload = {"text": intention.args["text"],
                              "volume": intention.args.get("volume", "normal")}
            # 点名对象无论音量都记录（可见性不变：normal 仍全地点可闻）；
            # 唤醒与起哄逻辑需要知道话是对谁说的。
            if intention.args.get("to"):
                speech_payload["to"] = list(intention.args["to"])
            self._commit("speech", a.id, speech_payload,
                         started.id if started else None)
        elif intention.kind == "send_message":
            self._commit("message_sent", a.id, {"target": str(intention.args["target"])},
                         started.id if started else None)
        hop_sequences: list[int] = []
        if duration:
            # Hop boundaries must be scheduled BEFORE the completion job so
            # the final enter fires at the same timestamp but lower sequence
            # (the completion's location mutation would otherwise swallow it).
            if move_path is not None:
                hop_sequences = self._schedule_move_hops(
                    a.id, move_path, move_hops or [],
                    int(duration.total_seconds()), started.id if started else None)
            job = self._schedule(self.now + duration, "action_completed", a.id,
                                 action_payload, started.id if started else None)
            sequence = job.sequence
        else:
            self._schedule(self.now, "action_completed", a.id, action_payload, None)
            self.advance(until=self.now)
        a.busy_until = self.now + duration if duration else None
        a.sleeping = intention.kind == "sleep"
        if duration:
            a.current_action = {"payload": dict(action_payload), "sequence": sequence,
                                "hop_sequences": hop_sequences,
                                "uninterruptable": bool(uninterruptable)}
        self._apply_interrupts(a, intention)
        return (started,) if started else ()

    def _apply_interrupts(self, actor: ActorState, intention: Intention) -> None:
        """Suspend listed co-located actors' interruptable in-progress actions.

        Only actors in ``interrupt`` and present here are affected; an actor
        who declared this action uninterruptable is never suspended. The
        suspended actor keeps its remaining progress and must choose
        continue_action or abandon_action on its next turn.
        """
        for target_id in intention.interrupt:
            if target_id == actor.id or target_id not in self.actors:
                continue
            target = self.actors[target_id]
            if target.location != actor.location:
                continue
            if not target.busy_until or target.busy_until <= self.now:
                continue
            current = target.current_action or {}
            if current.get("uninterruptable"):
                continue
            remaining = int((target.busy_until - self.now).total_seconds())
            sequence = current.get("sequence")
            if sequence is not None:
                self._cancelled.add(int(sequence))
            for hop_sequence in current.get("hop_sequences", ()) or ():
                self._cancelled.add(int(hop_sequence))
            payload = dict(current.get("payload", {}))
            pending = {"payload": payload, "remaining_seconds": remaining,
                       "interrupted_by": actor.id}
            if payload.get("action") == "move" and target.location != payload.get("target"):
                # Multi-hop move: the remaining walk resumes from the last
                # entered location (V4 multi-hop move semantics).
                path = [str(x) for x in payload.get("path", ())]
                hops = [int(x) for x in payload.get("hop_seconds", ())]
                if target.location in path and hops:
                    index = path.index(target.location)
                    pending["remaining_hops"] = hops[index:]
                    pending["remaining_path"] = path[index:]
            self._commit("action_interrupted", target_id, {
                "action": payload.get("action"),
                "remaining_seconds": remaining, "by": actor.id,
            }, None)
            target.pending = pending
            target.busy_until = None
            target.current_action = None
            target.sleeping = False

    def _resume(self, a: ActorState) -> tuple[Event, ...]:
        pending = a.pending
        if pending is None:
            raise ActionRejected("你没有被打断的动作。")
        remaining = tick_ceil(pending["remaining_seconds"])
        payload = dict(pending["payload"])
        event = self._commit("action_resumed", a.id, {
            "action": payload.get("action"), "remaining_seconds": remaining}, None)
        hop_sequences: list[int] = []
        if payload.get("action") == "move" and pending.get("remaining_path"):
            remaining_path = [str(x) for x in pending["remaining_path"]]
            remaining_hops = [int(x) for x in pending.get("remaining_hops", ())]
            hop_sequences = self._schedule_move_hops(
                a.id, remaining_path, remaining_hops, remaining, event.id)
        job = self._schedule(self.now + timedelta(seconds=remaining),
                             "action_completed", a.id, payload, event.id)
        a.pending = None
        a.busy_until = self.now + timedelta(seconds=remaining)
        a.current_action = {"payload": payload, "sequence": job.sequence,
                            "hop_sequences": hop_sequences,
                            "uninterruptable": False}
        return (event,)

    def _abandon(self, a: ActorState) -> tuple[Event, ...]:
        pending = a.pending
        if pending is None:
            raise ActionRejected("你没有被打断的动作。")
        payload = dict(pending["payload"])
        event = self._commit("action_abandoned", a.id, {
            "action": payload.get("action"), "failed": True,
            "interrupted_by": pending.get("interrupted_by")}, None)
        a.pending = None
        a.current_action = None
        return (event,)

    def advance(self, *, until: datetime | None = None) -> tuple[Event, ...]:
        if until is not None and until < self.now:
            raise ValueError("cannot reverse time")
        out: list[Event] = []
        limit = until
        while self._queue and (limit is None or self._queue[0].time <= limit):
            job = heapq.heappop(self._queue)
            if job.sequence in self._cancelled:
                self.now = job.time
                continue
            self.now = job.time
            if job.kind == "move_hop":
                # A hop boundary commits its own enter/leave events (and no
                # raw move_hop event reaches the log).
                self._move_hop(job)
                continue
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
        # Change-driven observation (V4-DESIGN §5.7): full observation on
        # first arrival, on explicit request, and every N rounds spent at the
        # same place. Descriptions ride their own much-slower M counter and
        # are forced once after a compaction wiped the actor's context.
        full_state = (a.location not in a.observed_locations or a.observe_request
                      or a.rounds_since_observation >= self.state_refresh_rounds
                      or a.force_observation)
        full_desc = (a.location not in a.described_locations or a.observe_request
                     or a.rounds_since_descriptions >= self.description_refresh_rounds
                     or a.force_observation)
        if full_state:
            a.observed_locations.add(a.location)
            a.rounds_since_observation = 0
            a.observe_request = False
        else:
            a.rounds_since_observation += 1
        if full_desc:
            a.described_locations.add(a.location)
            a.rounds_since_descriptions = 0
        else:
            a.rounds_since_descriptions += 1
        a.force_observation = False
        result = {"observer": actor_id, "time": self.now.isoformat(), "world_version": self.version,
                  "location": a.location, "inventory": sorted(a.inventory), "sleeping": a.sleeping,
                  "busy_until": a.busy_until.isoformat() if a.busy_until else None,
                  "nearby_actors": sorted(x.id for x in self.actors.values() if x.id != actor_id and x.location == a.location),
                  "nearby_items": sorted(i for i, loc in self.item_locations.items() if loc == a.location),
                  "inbox": inbox, "events": [self._public(e) for e in visible],
                  "knowledge": self._knowledge(a) if full_state else {}}
        if full_desc:
            result["descriptions"] = {entity_id: self.entity_descriptions[entity_id]
                                      for entity_id in self._visible_descriptions(a)
                                      if entity_id in self.entity_descriptions}
        if a.pending is not None:
            result["pending"] = {"action": a.pending["payload"].get("action"),
                                 "remaining_seconds": a.pending["remaining_seconds"],
                                 "interrupted_by": a.pending["interrupted_by"]}
        return result

    def notify_compaction(self, actor_id: str) -> None:
        """The actor's context was just rewritten (compaction): force one full
        state + description re-observation on the next poll, since the details
        the world would otherwise only push as changes are gone from memory."""
        self._actor(actor_id).force_observation = True

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
        # V4-ENGINE §2.1: every world action rounds up to whole ticks with a
        # one-tick floor; a zero-length action costs exactly one tick.
        return timedelta(seconds=tick_ceil(self._raw_duration(a, i).total_seconds()))

    def _raw_duration(self, a: ActorState, i: Intention) -> timedelta:
        x = i.args
        if i.kind == "observe":
            return timedelta(0)
        if i.kind in {"wait", "sleep"}:
            seconds = x.get("duration_seconds")
            if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
                raise ActionRejected("等待时长必须是正整数秒（duration_seconds）。")
            if seconds > self.longest_wait_seconds:
                raise ActionRejected(
                    f"单次等待不能超过 {self.longest_wait_seconds} 秒；如需更久，请分几次等待。",
                    context={"limit": self.longest_wait_seconds})
            return timedelta(seconds=seconds)
        if i.kind == "speak":
            if not isinstance(x.get("text"), str) or not x["text"]:
                raise ActionRejected("说话需要非空的 text。")
            volume = x.get("volume", "normal")
            if volume not in {"whisper", "normal"}:
                raise ActionRejected("volume 只能是 whisper（低声，仅指定对象听见）或 normal（全地点）。")
            if volume == "whisper":
                targets = x.get("to")
                if not isinstance(targets, list) or not targets or not all(isinstance(t, str) for t in targets):
                    raise ActionRejected(
                        "低声说话必须用 to 指定你说过给谁听（同处一地的人）。",
                        context={"volume": "whisper", "missing": "to"})
                here = {other.id for other in self.actors.values() if other.location == a.location}
                unknown = [t for t in targets if t not in here]
                if unknown:
                    raise ActionRejected(
                        f"低声说话的对象必须和你在一起。不在场：{', '.join(unknown)}。")
            # One utterance = one tick (V4-ENGINE §4): conversation rounds
            # cost M ticks for M exchanges regardless of length.
            return timedelta(seconds=TICK_SECONDS)
        if i.kind == "send_message":
            target_id = x.get("target")
            if not isinstance(target_id, str) or not target_id:
                reachable = self._message_targets(a)
                raise ActionRejected(
                    "发消息需要用 target 指定收信人。",
                    alternatives=[f"send_message to {other}" for other in reachable],
                    context={"missing": "target"})
            target = self._actor(target_id)
            if target.id != a.id and target.id not in a.known_contacts and target.location != a.location:
                reachable = self._message_targets(a)
                raise ActionRejected(
                    f"你联系不上 {target.id}：对方既不是你的熟人，也不在这里。",
                    alternatives=[f"send_message to {other}" for other in reachable],
                    context={"target": target.id})
            if not isinstance(x.get("text"), str) or not x["text"]:
                raise ActionRejected("消息正文不能为空（text）。")
            # One communication tick (V4-ENGINE §2): a message takes one
            # tick to arrive, common knowledge, so sending words has a real
            # time cost.
            return timedelta(seconds=TICK_SECONDS)
        if i.kind in {"read", "copy", "label", "annotate", "compare"}:
            return self._document_duration(a, i)
        if i.kind == "inspect":
            item = str(x.get("item"))
            here, held = self._present_items(a)
            if self.item_locations.get(item) != a.location and item not in a.inventory:
                raise ActionRejected(
                    f"「{item}」不在这里。这里有的：{', '.join(here) or '没有'}。"
                    f"你拿着的：{', '.join(held) or '没有'}。",
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
                message = (f"「{target}」不是一个你知道的地方。" if not known
                           else f"你从{a.location}到不了「{target}」。")
                raise ActionRejected(
                    message,
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"target": target})
            if not isinstance(verb, str) or not isinstance(parameters, dict):
                raise ActionRejected("互动需要字符串 verb 和映射 parameters。")
            capabilities = self._physical_capabilities(self.locations[target])
            if verb not in capabilities:
                supported = sorted(capabilities)
                raise ActionRejected(
                    f"「{target}」不支持「{verb}」。支持的互动：{', '.join(supported) or '无'}。",
                    alternatives=[f"interact with {target} ({verb_name})" for verb_name in supported],
                    context={"target": target, "verb": verb})
            expected = capabilities[verb].get("parameters", {})
            if parameters != expected:
                raise ActionRejected(f"在{target}上「{verb}」需要参数 {expected}。")
            return timedelta(seconds=3)
        if i.kind == "give":
            target_id = x.get("target")
            if not isinstance(target_id, str) or not target_id:
                raise ActionRejected("give 需要 target 指定递交对象。",
                                     context={"missing": "target"})
            target = self._actor(target_id)
            if target.id == a.id or target.location != a.location:
                alternatives = [f"send_message to {target.id}"] if target.id in a.known_contacts else []
                raise ActionRejected(
                    f"{target.id}不在这里，你没法把东西递给对方。",
                    alternatives=alternatives,
                    context={"target": target.id, "co_located": False})
            item = str(x.get("item"))
            if item not in a.inventory:
                raise ActionRejected(
                    f"你没有拿着「{item}」。你拿着：{', '.join(sorted(a.inventory)) or '没有'}。")
            return timedelta(seconds=2)
        if i.kind == "move":
            target = str(x.get("target"))
            if target not in self.locations:
                reachable = self._reachable(a)
                raise ActionRejected(
                    f"「{target}」不是一个你知道的地方。从{a.location}可以到："
                    f"{', '.join(reachable) or '没有'}。",
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"target": target})
            if not self.locations[target].open:
                open_neighbors = self._reachable_open(a)
                raise ActionRejected(
                    f"「{target}」现在关着，进不去。",
                    alternatives=[f"move to {neighbor} (open)" for neighbor in open_neighbors],
                    context={"target": target, "open": False})
            # V4-DESIGN §5.6 + multi-hop move: the actor states intent; the
            # engine finds the shortest walk and its duration is the map's
            # physical fact, never an actor-supplied argument.
            found = self._route_path(a.location, target)
            if found is None:
                reachable = self._reachable(a)
                raise ActionRejected(
                    f"从{a.location}走到「{target}」没有可用的路。",
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"from": a.location, "target": target})
            return timedelta(seconds=sum(found[1]))
        if i.kind in {"open", "close"}:
            if not self.locations[a.location].controllable:
                raise ActionRejected(
                    f"你无法{i.kind}{a.location}：这里不受你控制。",
                    context={"location": a.location, "controllable": False})
            return timedelta(0)
        if i.kind == "take":
            item = str(x.get("item"))
            here, held = self._present_items(a)
            if self.item_locations.get(item) != a.location:
                raise ActionRejected(
                    f"这里没有「{item}」可拿。这里有的：{', '.join(here) or '没有'}。"
                    f"你拿着的：{', '.join(held) or '没有'}。",
                    alternatives=[f"take {present}" for present in here],
                    context={"item": item})
            return timedelta(0)
        if i.kind == "drop":
            item = str(x.get("item"))
            if item not in a.inventory:
                raise ActionRejected(
                    f"You are not holding '{item}'. You hold: {', '.join(sorted(a.inventory)) or 'nothing'}.")
            return timedelta(0)
        raise ActionRejected("该动作没有时长规则。")

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
                raise ActionRejected("两份文档都必须真实存在。")
            if not self._entity_available(actor.id, first) or not self._entity_available(actor.id, second):
                available = self._available_documents(actor)
                raise ActionRejected(
                    f"无法比对 {first} 和 {second}：并非都在你手边。你能读的：{', '.join(available) or '无'}。",
                    alternatives=[f"read {document}" for document in available],
                    context={"first": first, "second": second})
            return timedelta(seconds=30)
        document = str(intention.args.get("document"))
        if document not in self.document_defs or not self._entity_available(actor.id, document):
            available = self._available_documents(actor)
            raise ActionRejected(
                f"「{document}」现在不在你手边。你能读的：{', '.join(available) or '无'}。",
                alternatives=[f"read {present}" for present in available],
                context={"document": document})
        if kind == "copy":
            if not any(item in actor.inventory for item in self.copy_material_items):
                raise ActionRejected(
                    f"复印需要复印材料。你有：{', '.join(sorted(actor.inventory)) or '没有'}。",
                    context={"copy_material": sorted(self.copy_material_items)})
            return timedelta(seconds=int(self.document_defs[document].get("reading_seconds", 30)) + 15)
        if kind == "label":
            label = intention.args.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ActionRejected("label 需要非空文本。")
            return timedelta(seconds=3)
        if kind == "annotate":
            text = intention.args.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ActionRejected("annotate 需要非空文本。")
            return timedelta(seconds=3)
        return timedelta(seconds=int(self.document_defs[document].get("reading_seconds", 30)))

    def _complete(self, actor_id: str, payload: Mapping[str, Any]) -> None:
        if actor_id not in self.actors:
            # Defensive: a despawned extra's leftover job must not crash the
            # clock — the event stands (it happened), nothing mutates.
            return
        a = self._actor(actor_id); kind = payload["action"]
        if kind == "move": a.location = str(payload["target"])
        elif kind == "send_message":
            target_id = str(payload["target"])
            if target_id not in self.actors:
                # A message addressed to a despawned extra goes nowhere: the
                # stranger has left the scene (V4-CAST §1 zero-memory rule).
                return
            target = self.actors[target_id]
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
        a.current_action = None

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

    def add_extra(self, name: str, location: str) -> ActorState:
        """V4-CAST §1: register a conversation-scoped stranger (role=extra).
        生成与销毁都走事件日志，保证 replay 可重建。"""
        if name in self.actors:
            raise ActionRejected(f"路人姓名冲突：{name}")
        extra = ActorState(name, location, role="extra")
        self.actors[name] = extra
        self._cursor[name] = len(self.event_log)
        self._commit("extra_arrived", name, {"location": location}, None)
        return extra

    def remove_extra(self, name: str) -> None:
        """Destroy an extra: it leaves the scene with zero memory.

        Any jobs it left in the clock queue (a message still in flight, a
        duration action still running) are cancelled with it — a despawned
        stranger must not crash the clock when its turn comes (首验日 v2 事故)."""
        if name in self.actors and self.actors[name].role == "extra":
            self._commit("extra_removed", name, {"location": self.actors[name].location}, None)
            del self.actors[name]
            self._cursor.pop(name, None)
            for job in self._queue:
                if job.actor == name:
                    self._cancelled.add(job.sequence)

    def _commit(self, kind: str, actor: str | None, payload: Mapping[str, Any], cause: int | None) -> Event:
        visible = self._visibility(kind, actor, payload)
        event = Event(next(self._event_id), self.now, kind, actor, dict(payload), cause,
                      frozenset(visible), self.version + 1)
        self.version += 1; self.event_log.append(event); return event

    def _visibility(self, kind: str, actor: str | None, payload: Mapping[str, Any]) -> set[str]:
        """V4-DESIGN §3: everything public at a location is perceived by
        everyone there; secrets survive only where the design says so —
        document contents stay with the reader, messages stay between sender
        and receiver, and another actor's wait/sleep is not a sight."""
        if kind.startswith("system_"):
            return {str(actor)} if actor is not None else set()
        if kind in {"wait_woken", "private_wake"}:
            return {str(actor)} if actor is not None else set()
        if kind == "document_read":
            # Content privacy: only the reader sees the text.
            return {str(actor)}
        if kind == "documents_compared":
            # The equality verdict is the actor's private analysis.
            return {str(actor)}
        if kind in {"document_copied", "document_labeled", "document_annotated"}:
            # Visible facts on the physical record.
            return self._co_located(str(actor))
        if kind in {"action_started", "action_completed"} and payload.get("action") in {
                "read", "copy", "label", "compare", "annotate"}:
            # The fact is public; the content never is (carried only by the
            # private document_read event above).
            return self._co_located(str(actor))
        if kind in {"action_started", "action_completed"} and payload.get("action") in {
                "wait", "sleep"}:
            # A person standing still is not a sight; only the actor knows.
            return {str(actor)}
        if kind == "interrupt_requested":
            return {str(actor)} | {str(t) for t in payload.get("targets", ())}
        if kind == "action_interrupted":
            return self._co_located(str(actor))
        if kind in {"action_resumed", "action_abandoned"}:
            return self._co_located(str(actor))
        if kind == "world_event" and payload.get("target"):
            targets = payload["target"] if isinstance(payload["target"], (list, tuple)) else [payload["target"]]
            return {str(target) for target in targets}
        if kind == "leave" or kind == "enter":
            # Movement visibility: everyone at the location being touched,
            # plus the mover (who sees its own whole route).
            return self._co_located(str(actor))
        if kind in {"action_started", "action_completed"} and payload.get("action") == "move":
            # The discrete leave/enter events carry the public movement
            # information; started/completed are the mover's private bookkeeping.
            return {str(actor)}
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
            return self._co_located(str(actor))
        if kind in {"item_inspected", "location_searched"}:
            return self._co_located(str(actor))
        if kind == "item_given":
            return self._co_located(str(payload["from"]))
        if kind in {"knock", "interaction"}:
            target = str(payload["target"])
            return {str(actor)} | {x.id for x in self.actors.values() if x.location == target}
        if kind in {"extra_arrived", "extra_removed"}:
            return self._co_located(str(actor))
        if actor is None: return set(self.actors)
        return self._co_located(str(actor))

    def _co_located(self, actor_id: str) -> set[str]:
        """Everyone at the actor's location, plus the actor."""
        location = self.actors[actor_id].location
        return ({x.id for x in self.actors.values() if x.location == location}
                | {actor_id})

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

    def _schedule(self, time: datetime, kind: str, actor: str | None, payload: Mapping[str, Any], cause: int | None) -> _Scheduled:
        job = _Scheduled(time, next(self._sequence), kind, actor, dict(payload), cause)
        heapq.heappush(self._queue, job)
        return job

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
        """V4-DESIGN §3 volumes: normal reaches the whole location; whisper
        reaches only the addressed parties (who must be present)."""
        source = self._actor(actor_id)
        if not self.locations[source.location].open:
            return {actor_id}
        volume = payload.get("volume", "normal")
        heard = {actor_id}
        if volume == "whisper":
            for target in payload.get("to", ()) or ():
                if target in self.actors and self.actors[target].location == source.location:
                    heard.add(target)
            return heard
        return heard | {x.id for x in self.actors.values() if x.location == source.location}
