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
import json
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


def _as_int(value, what="value"):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {what}: {value!r}") from exc


def tick_ceil(seconds: float) -> int:
    """Round a raw duration up to whole ticks, minimum one tick
    (V4-ENGINE §2.1: every world action, even a query-like one, costs at
    least one tick)."""
    whole = _as_int(seconds, 'seconds')
    ticks = -(-whole // TICK_SECONDS) if whole > 0 else 1
    return max(1, ticks) * TICK_SECONDS


WAKE_EVENT_KINDS = frozenset({"speech", "message_delivered", "knock", "interaction",
                              "item_given", "extra_arrived", "extra_removed",
                              "action_interrupted", "enter", "note_read"})
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
    # Contact aliases: nickname -> formal id (T3). The actor's own private
    # names for people; the formal names live in known_contacts.
    contact_aliases: dict[str, str] = field(default_factory=dict)
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

    # 字条 is a room message, not an item. Multiple notes are kept as
    # {author, text, left_at}; each note waits for its first non-author entrant,
    # who receives it privately before it is removed. Co-located actors do not
    # receive the content.
    # compare=False keeps frozen-dataclass equality on identity fields only.
    notes: list[dict[str, Any]] = field(default_factory=list, compare=False)

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
        id=old.id, open=open_, x=old.x, y=old.y, sound_radius=old.sound_radius,
        sound_loss=old.sound_loss, physical_capabilities=old.physical_capabilities,
        controllable=old.controllable, extras=old.extras, notes=old.notes)


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
            world._require_described(str(effect["id"]))
            world.item_locations[str(effect["id"])] = str(effect["location"])
        elif op == "remove_item":
            world.item_locations.pop(str(effect["id"]), None)


class World:
    """Authoritative, deterministic, event-sourced physical/social world."""

    ACTIONS = {"wait", "speak", "text", "move", "take", "place", "give",
               "read", "leave_note", "knock", "trash",
               "continue_action", "abandon_action"}

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
        self.longest_wait_seconds = _as_int(longest_wait_seconds, 'longest_wait_seconds')
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
        # Pre-run authored history (ticket 25): real past events, same Event
        # shape, negative id space. Never delivered, never replayed for `now`
        # — but flashback replays them like any memory of the past.
        self._history_id = itertools.count(-1, -1)
        self.history_log: list[Event] = []
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

    def inject_history(self, history) -> int:
        """Compile authored pre-run history (manifest `history:`) into the
        world's history log (ticket 25). These are REAL past events with real
        timestamps — the 2013 typhoon night is as true as anything that will
        happen at runtime — but they live in their own log: never delivered
        as new, never counted by `now`. Flashback scans this log plus the
        runtime log."""
        added = 0
        for row in history:
            when = datetime.fromisoformat(str(row["time"]))
            visible = row.get("visible_to") or [a.id for a in self.actors.values()]
            event = Event(next(self._history_id), when, str(row["kind"]),
                          row.get("actor"), dict(row.get("payload") or {}), None,
                          frozenset(str(v) for v in visible), 0)
            self.history_log.append(event)
            added += 1
        return added

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
                              "contact_aliases": dict(value.contact_aliases),
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
                                 "extras": [dict(x) for x in value.extras],
                                 "notes": [dict(x) for x in value.notes]}
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
            "history_log": [{"id": event.id, "time": event.time.isoformat(),
                              "kind": event.kind, "actor": event.actor,
                              "payload": dict(event.payload), "cause": event.cause,
                              "visible_to": sorted(event.visible_to)}
                             for event in self.history_log],
        }

    @classmethod
    def from_checkpoint(cls, base: "World", state: Mapping[str, Any]) -> "World":
        restored = cls.__new__(cls)
        restored.restore_checkpoint(state, base=base)
        return restored

    def restore_checkpoint(self, state: Mapping[str, Any], *, base: "World | None" = None) -> None:
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
                actors[key] = ActorState(
                    id=str(row["id"]), location=str(row["location"]),
                    inventory=set(row["inventory"]),
                    busy_until=datetime.fromisoformat(row["busy_until"]) if row["busy_until"] else None,
                    sleeping=bool(row["sleeping"]),
                    inbox=copy.deepcopy(row["inbox"]),
                    known_contacts=set(row["known_contacts"]),
                    contact_aliases=dict(row.get("contact_aliases", {})),
                    current_action=copy.deepcopy(row.get("current_action")),
                    pending=copy.deepcopy(row.get("pending")),
                    observed_locations=set(row.get("observed_locations", ())),
                    rounds_since_observation=int(row.get("rounds_since_observation", 0)),
                    observe_request=bool(row.get("observe_request", False)),
                    described_locations=set(row.get("described_locations", ())),
                    rounds_since_descriptions=int(row.get("rounds_since_descriptions", 0)),
                    force_observation=bool(row.get("force_observation", False)),
                    role=str(row.get("role", "mc")))
            locations = {key: LocationState(str(row["id"]), bool(row["open"]), float(row["x"]),
                float(row["y"]), float(row["sound_radius"]), float(row["sound_loss"]),
                dict(row.get("physical_capabilities", {})), bool(row.get("controllable", False)),
                tuple(dict(x) for x in row.get("extras", ())),
                [dict(x) for x in row.get("notes", ())])
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
            self.history_log = [
                Event(int(row["id"]), datetime.fromisoformat(row["time"]), row["kind"],
                      row.get("actor"), dict(row.get("payload") or {}), row.get("cause"),
                      frozenset(row["visible_to"]), 0)
                for row in state.get("history_log", [])]
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
                next_cost = cost + _as_int(secs, 'route seconds')
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

    def schedule_reminder(self, actor_id: str, when: datetime, row_id: str,
                          desc: str, rendered: str) -> int:
        """Schedule a reminder fire (V4-AGENT-INTERFACE §4): at `when` the
        kernel commits a private reminder_due event (the notice) and force-
        interrupts the actor's in-progress action. Queue-level firing makes
        the reminder robust against DES time jumps."""
        return self._schedule(when, "reminder_due", actor_id,
                              {"row_id": row_id, "desc": desc, "rendered": rendered},
                              None).sequence

    def _fire_reminder(self, job: Any) -> None:
        actor_id = job.actor
        if actor_id not in self.actors:
            return
        payload = dict(job.payload)
        self._commit("reminder_due", actor_id, payload, None)
        self.force_interrupt(actor_id, "reminder")

    def _move_hop(self, job: "Any") -> None:
        """Fire one hop boundary: enter the reached location, and (unless it
        is the destination) leave it again immediately — the discrete event
        sequence leave A / enter B / leave B / enter C (V4-ENGINE §2.1).
        Visibility: everyone at the location touched, plus the mover."""
        actor_id = job.actor
        if actor_id not in self.actors:
            return  # a despawned extra's leftover hop must not crash the clock
        a = self.actors[actor_id]
        path, index = job.payload["path"], _as_int(job.payload["index"], "hop index")
        new = str(path[index])
        if a.location == new:
            return
        a.location = new
        enter = self._commit("enter", actor_id, {"location": new}, None)
        # Each pending note goes to its first non-author entrant. The event
        # queue's (time, sequence) ordering breaks same-timestamp ties.
        self._consume_notes(new, actor_id, enter.id)
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
            self._cancelled.add(_as_int(sequence, 'sequence'))
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
        self._cancelled.add(_as_int(sequence, 'sequence'))

    def has_wakeup(self, actor_id: str) -> bool:
        """Return whether an idle actor has observable work to poll."""
        a = self._actor(actor_id)
        if a.busy_until and a.busy_until > self.now:
            return False
        cursor = self._cursor[actor_id]
        return bool(a.inbox or any(actor_id in event.visible_to for event in self.event_log[cursor:]))

    def dismiss_events(self, actor_id: str) -> None:
        """Advance the actor's perception cursor past everything emitted so
        far, so has_wakeup() reflects only genuinely new events (V4-CAST §1:
        an extra's own speech must not re-wake it into a chatter loop)."""
        self._cursor[actor_id] = len(self.event_log)

    def has_external_wakeup(self, actor_id: str) -> bool:
        """Conversational wake class for extras (V4-CAST §1): ready only
        when a NEW wake-class event from someone else is visible — speech,
        delivered messages, knocks, an arrival — never on the actor's own
        bookkeeping (own speech, its action_completed) or ambient world
        events. Mirrors _unseen_social_event but reads the live cursor."""
        a = self._actor(actor_id)
        if a.busy_until and a.busy_until > self.now:
            return False
        cursor = self._cursor[actor_id]
        return bool(a.inbox or any(
            actor_id in event.visible_to
            and event.kind in WAKE_EVENT_KINDS
            and event.actor != actor_id
            for event in self.event_log[cursor:]))

    def affordances(self, actor_id: str) -> list[dict[str, Any]]:
        a = self._actor(actor_id)
        if a.pending is not None:
            # A suspended action must be resolved first: continue (keep the
            # remaining progress) or cancel (mark it failed/unfinished).
            return [{"kind": "continue_action"}, {"kind": "abandon_action"}]
        if a.busy_until and a.busy_until > self.now:
            # Ordinary actions finish on their scheduled event. Offering wait
            # here is contradictory: submit rejects every action while busy.
            return []
        controllable = self.locations[a.location].controllable
        others_here = sorted(other.id for other in self.actors.values()
                             if other.id != a.id and other.location == a.location)
        # docs §3（修订，ticket 22）: speak 是唯一带寻址的说话工具。to 候选 =
        # 在场他人 + ["陌生人"]（向路人搭话，引擎会在话音落地时派一个路人
        # 回应）；普通的全场发言是纯文本输出，不占工具面。
        speak_option = {"kind": "speak", "volume": "normal",
                        "to": [*others_here, "陌生人"]}
        options: list[dict[str, Any]] = [
            speak_option,
            *({"kind": "text", "target": other} for other in self._message_targets(a)),
            *({"kind": "move", "target": target}
              for (source, target), duration in self.routes.items() if source == a.location),
        ]
        # 路线提示（issue 26 诊断 2026-09-21）：affordances 只列一跳目的地，
        # 模型不知道多数地点可经多跳 move 到达（如经中庭去半坡咖啡馆）——
        # 谨慎人格于是原地等待。附加"目的地 · 经首跳 · 总时长"完整清单。
        import heapq as _hq
        first_hop: dict[str, tuple[str, int]] = {}
        for (source, target), duration in self.routes.items():
            if source == a.location:
                first_hop.setdefault(target, (target, duration))
        best: dict[str, tuple[str, int]] = {}
        visited = {a.location}
        queue = [(_d, _t, _v) for _t, (_v, _d) in first_hop.items()]
        _hq.heapify(queue)
        while queue:
            cost, loc, via = _hq.heappop(queue)
            if loc in visited:
                continue
            visited.add(loc)
            best[loc] = (via, cost)
            for (s2, t2), d2 in self.routes.items():
                if s2 == loc and t2 not in visited:
                    _hq.heappush(queue, (cost + d2, t2, via))
        hints = [{"target": loc, "via": via, "minutes": round(cost / 60)}
                 for loc, (via, cost) in sorted(best.items()) if loc not in first_hop]
        if hints:
            options.append({"kind": "route_hints",
                            "note": "非相邻目的地也可经多跳 move 到达",
                            "routes": hints})
        options += [{"kind": "take", "item": item} for item, loc in self.item_locations.items() if loc == a.location]
        options += [{"kind": "knock", "target": location.id} for location in self.locations.values()
                    if not location.open and (a.location, location.id) in self.routes]
        options += [{"kind": "give", "target": other.id, "item": item}
                    for other in self.actors.values()
                    if other.id != actor_id and other.location == a.location
                    for item in sorted(a.inventory)]
        options += [{"kind": "place", "item": item} for item in sorted(a.inventory)]
        options += [{"kind": "leave_note", "text": "",
                     "hint": "字条是房间留言：在场的人只知道有人留条；作者返场不算读者，第一位非作者进入者私下读到全文并阅后即焚"},
                    *({"kind": "trash", "item": item} for item in sorted(a.inventory))]
        available_documents = [document for document in self.document_defs
                               if self._entity_available(a.id, document)]
        options += [{"kind": "read", "item": document} for document in sorted(available_documents)]
        return options

    def submit(self, intention: Intention) -> tuple[Event, ...]:
        a = self._actor(intention.actor)
        if intention.expected_version is not None and intention.expected_version != self.version:
            raise ActionRejected("世界已发生变化，请重新观察后再行动（stale world version）")
        if intention.kind not in self.ACTIONS:
            raise ActionRejected(f"unknown action '{intention.kind}'; "
                                 "see your tool list for the current actions")
        if intention.kind == "speak" and "volume" not in intention.args:
            # Engine-constructed normal speech (T1 文本即说话): the model's
            # plain text output arrives without tool-schema decoration. The
            # listener set is computed at commit; no whisper fields needed.
            # A `to` the model wrote anyway is preserved (normal, addressed).
            injected = {"text": intention.args.get("text", ""), "volume": "normal"}
            if intention.args.get("to"):
                injected["to"] = list(intention.args["to"])
            intention = Intention(intention.actor, intention.kind,
                                  injected,
                                  intention.expected_version,
                                  interrupt=intention.interrupt,
                                  uninterruptable=intention.uninterruptable)
        else:
            shape_error = validate_action_args(intention.kind, intention.args)
            if shape_error is not None:
                raise ActionRejected(shape_error)
        if intention.kind in {"speak", "text", "give"}:
            # Person-name resolution (V4-AGENT-INTERFACE T4): a nickname that
            # uniquely matches one candidate is canonicalized here, before any
            # validation, so both the gate and the committed event see formal
            # names. Ambiguity/no-hit is rejected with the candidates listed.
            intention = self._canonicalize_persons(a, intention)
        if a.pending is not None and intention.kind not in {"continue_action", "abandon_action"}:
            action = str(a.pending.get("payload", {}).get("action", "action"))
            interrupted_by = str(a.pending.get("interrupted_by", "unknown"))
            remaining = int(a.pending.get("remaining_seconds", 0))
            raise ActionRejected(
                f"not executed: '{action}' was interrupted by '{interrupted_by}' with "
                f"{remaining} seconds remaining. Resume with "
                '{"name": "continue_action", "arguments": {}} or cancel with '
                '{"name": "abandon_action", "arguments": {}}.',
                context={"interrupted_action": action, "interrupted_by": interrupted_by,
                         "remaining_seconds": remaining})
        if a.busy_until and a.busy_until > self.now:
            raise self._busy_rejection(a, intention)
        if intention.kind == "continue_action":
            return self._resume(a)
        if intention.kind == "abandon_action":
            return self._abandon(a)
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
        uninterruptable = intention.uninterruptable
        if uninterruptable is None:
            uninterruptable = False
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
            # docs §3：heard = 提交时刻在场的全部他人（normal）；whisper 仅
            # 记 to 指定者。客观事实，进事件日志供 heard-by 模板渲染。
            here = [other.id for other in self.actors.values()
                    if other.id != a.id and other.location == a.location]
            if intention.args.get("volume") == "whisper":
                speech_payload["heard"] = [t for t in (intention.args.get("to") or [])
                                            if t in here]
            else:
                speech_payload["heard"] = here
            # 点名对象无论音量都记录（可见性不变：normal 仍全地点可闻）；
            # 唤醒与起哄逻辑需要知道话是对谁说的。
            if intention.args.get("to"):
                speech_payload["to"] = list(intention.args["to"])
            self._commit("speech", a.id, speech_payload,
                         started.id if started else None)
            # Merged ask (ticket 22): to=["陌生人"] asks the room's passers-by.
            # The spawn fires at the utterance's completion tick (the moment
            # the message is heard), keyed by cause so _handle_extras can
            # match it — never at submit time.
            if "陌生人" in (intention.args.get("to") or []):
                self._commit("stranger_asked", a.id,
                             {"question": intention.args["text"]},
                             started.id if started else None)
        elif intention.kind == "text":
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
                    _as_int(duration.total_seconds(), 'duration'), started.id if started else None)
            job = self._schedule(self.now + duration, "action_completed", a.id,
                                 action_payload, started.id if started else None)
            sequence = job.sequence
        else:
            self._schedule(self.now, "action_completed", a.id, action_payload, None)
            self.advance(until=self.now)
        a.busy_until = self.now + duration if duration else None
        a.sleeping = False
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
            remaining = _as_int((target.busy_until - self.now).total_seconds(), 'remaining')
            sequence = current.get("sequence")
            if sequence is not None:
                self._cancelled.add(_as_int(sequence, 'sequence'))
            for hop_sequence in current.get("hop_sequences", ()) or ():
                self._cancelled.add(_as_int(hop_sequence, 'hop sequence'))
            payload = dict(current.get("payload", {}))
            pending = {"payload": payload, "remaining_seconds": remaining,
                       "interrupted_by": actor.id}
            if payload.get("action") == "move" and target.location != payload.get("target"):
                # Multi-hop move: the remaining walk resumes from the last
                # entered location (V4 multi-hop move semantics).
                path = [str(x) for x in payload.get("path", ())]
                hops = [_as_int(x, 'hop seconds') for x in payload.get("hop_seconds", ())]
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

    def force_interrupt(self, actor_id: str, by: str) -> bool:
        """Engine-side force interrupt (reminder 到期, V4-AGENT-INTERFACE §4):
        suspend the actor's in-progress action at its execution position with
        continue-or-cancel semantics. Returns True when suspended. An actor
        that is idle or already suspended is unaffected."""
        a = self._actor(actor_id)
        if a.pending is not None:
            return False
        if not a.busy_until or a.busy_until <= self.now:
            return False
        current = a.current_action or {}
        if current.get("uninterruptable"):
            return False
        remaining = _as_int((a.busy_until - self.now).total_seconds(), 'remaining')
        sequence = current.get("sequence")
        if sequence is not None:
            self._cancelled.add(_as_int(sequence, 'sequence'))
        for hop_sequence in current.get("hop_sequences", ()) or ():
            self._cancelled.add(_as_int(hop_sequence, 'hop sequence'))
        payload = dict(current.get("payload", {}))
        pending = {"payload": payload, "remaining_seconds": remaining,
                   "interrupted_by": by}
        if payload.get("action") == "move" and a.location != payload.get("target"):
            path = [str(x) for x in payload.get("path", ())]
            hops = [_as_int(x, 'hop seconds') for x in payload.get("hop_seconds", ())]
            if a.location in path and hops:
                index = path.index(a.location)
                pending["remaining_hops"] = hops[index:]
                pending["remaining_path"] = path[index:]
        self._commit("action_interrupted", actor_id, {
            "action": payload.get("action"),
            "remaining_seconds": remaining, "by": by,
        }, None)
        a.pending = pending
        a.busy_until = None
        a.current_action = None
        a.sleeping = False
        return True

    def _resume(self, a: ActorState) -> tuple[Event, ...]:
        pending = a.pending
        if pending is None:
            raise ActionRejected(
                "No interrupted action is pending; continue_action is only for an "
                "action shown as interrupted. Ordinary actions complete automatically. "
                'To wait while idle, use {"name": "wait", "arguments": {"duration_seconds": 60}}.')
        remaining = tick_ceil(pending["remaining_seconds"])
        payload = dict(pending["payload"])
        event = self._commit("action_resumed", a.id, {
            "action": payload.get("action"), "remaining_seconds": remaining}, None)
        hop_sequences: list[int] = []
        if payload.get("action") == "move" and pending.get("remaining_path"):
            remaining_path = [str(x) for x in pending["remaining_path"]]
            remaining_hops = [_as_int(x, 'remaining hops') for x in pending.get("remaining_hops", ())]
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
            raise ActionRejected(
                "No interrupted action is pending; abandon_action is only for an "
                "action shown as interrupted. Ordinary actions complete automatically. "
                'To wait while idle, use {"name": "wait", "arguments": {"duration_seconds": 60}}.')
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
            if job.kind == "reminder_due":
                self.now = job.time
                self._fire_reminder(job)
                continue
            event = self._commit(job.kind, job.actor, self._public_payload(job.payload), job.cause)
            out.append(event)
            if job.kind == "action_completed" and job.actor:
                self._complete(job.actor, job.payload)
                if job.payload["action"] in {"knock"}:
                    out.append(self._commit_interaction(job.actor, job.payload, event.id))
                if job.payload["action"] == "give":
                    out.append(self._commit_interaction(job.actor, job.payload, event.id))
                if job.payload["action"] == "text":
                    out.append(self._commit("message_delivered", job.actor, {
                        "target": str(job.payload["target"]), "text": str(job.payload["text"])
                    }, event.id))
                if job.payload["action"] in {"read", "leave_note", "trash"}:
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
                  "inbox": inbox, "events": [self._public(e, observer=actor_id) for e in visible],
                  "knowledge": self._knowledge(a) if full_state else {}}
        if full_desc:
            result["descriptions"] = {entity_id: self.entity_descriptions[entity_id]
                                      for entity_id in self._visible_descriptions(a)
                                      if entity_id in self.entity_descriptions}
        if a.pending is not None:
            result["pending"] = {"action": a.pending["payload"].get("action"),
                                 "remaining_seconds": a.pending["remaining_seconds"],
                                 "interrupted_by": a.pending["interrupted_by"]}
            pending_payload = a.pending["payload"]
            result["action_state"] = {
                "status": "interrupted",
                "action": pending_payload.get("action"),
                "remaining_seconds": a.pending["remaining_seconds"],
                "interrupted_by": a.pending["interrupted_by"],
                **{key: pending_payload[key] for key in ("target", "item")
                   if isinstance(pending_payload.get(key), str)},
            }
        elif a.busy_until and a.busy_until > self.now:
            current = a.current_action or {}
            payload = current.get("payload", {})
            state = {"status": "in_progress",
                     "action": payload.get("action"),
                     "until": a.busy_until.isoformat()}
            for key in ("target", "item"):
                value = payload.get(key)
                if isinstance(value, str):
                    state[key] = value
            if payload.get("action") in {"speak", "text"}:
                addressed = (bool(payload.get("to")) if payload.get("action") == "speak"
                             else bool(payload.get("target")))
                state["will_wait_for_response"] = bool(
                    addressed and payload.get("wait_response", True))
            if current.get("waiting_for_response"):
                state["status"] = "waiting_for_response"
                state["response_to"] = list(current.get("response_to", ()))
                state["response_action"] = current.get("response_action", "speak")
            result["action_state"] = state
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

    @staticmethod
    def _tool_call_json(kind: str, args: Mapping[str, Any]) -> str:
        return json.dumps({"name": kind, "arguments": dict(args)}, ensure_ascii=False)

    def _busy_rejection(self, actor: ActorState, intention: Intention) -> ActionRejected:
        current = actor.current_action or {}
        payload = current.get("payload", {})
        action = str(payload.get("action", "action"))
        if current.get("waiting_for_response"):
            recipients = ", ".join(str(x) for x in current.get("response_to", ())) or "the addressee"
            activity = f"waiting for a response from {recipients}"
        else:
            detail = payload.get("target", payload.get("item"))
            activity = f"'{action}'" + (f" for '{detail}'" if detail else "")
        until = actor.busy_until.isoformat() if actor.busy_until else "an unknown time"
        message = (
            f"not executed: {self._tool_call_json(intention.kind, intention.args)} cannot start "
            f"while {activity} is in progress until {until}. The current action will finish "
            "automatically; do not use wait while busy, and only use continue_action/"
            "abandon_action for a true interruption. Retry the "
            f"same call after completion: {self._tool_call_json(intention.kind, intention.args)}.")
        return ActionRejected(message, context={
            "busy_until": until, "current_action": action,
            "attempted_action": intention.kind})

    def _duration(self, a: ActorState, i: Intention) -> timedelta:
        # V4-ENGINE §2.1: every world action rounds up to whole ticks with a
        # one-tick floor; a zero-length action costs exactly one tick.
        return timedelta(seconds=tick_ceil(self._raw_duration(a, i).total_seconds()))

    def _raw_duration(self, a: ActorState, i: Intention) -> timedelta:
        x = i.args
        if i.kind in {"wait", "sleep"}:
            seconds = x.get("duration_seconds")
            if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
                raise ActionRejected(
                    'wait needs a positive integer duration_seconds; for one minute use '
                    '{"name": "wait", "arguments": {"duration_seconds": 60}}.')
            if seconds > self.longest_wait_seconds:
                raise ActionRejected(
                    f"单次等待不能超过 {self.longest_wait_seconds} 秒；如需更久，请分几次等待。"
                    f"例如：{self._tool_call_json('wait', {'duration_seconds': self.longest_wait_seconds})}。",
                    context={"limit": self.longest_wait_seconds})
            return timedelta(seconds=seconds)
        if i.kind == "speak":
            if not isinstance(x.get("text"), str) or not x["text"]:
                raise ActionRejected("说话需要非空的 text。")
            volume = x.get("volume", "normal")
            if volume not in {"whisper", "normal"}:
                raise ActionRejected("volume 只能是 whisper（低声，仅指定对象听见）或 normal（全地点）。")
            here = {other.id for other in self.actors.values() if other.location == a.location}
            targets = x.get("to")
            if targets is not None:
                if not isinstance(targets, list) or not targets or not all(isinstance(t, str) for t in targets):
                    raise ActionRejected(
                        "to 必须是名字列表（在场的人，或 [\"陌生人\"] 向路人搭话）。",
                        context={"missing": "to"})
                named = [t for t in targets if t != "陌生人"]
                unknown = [t for t in named if t not in here]
                if unknown:
                    raise ActionRejected(
                        f"speak recipient must be here; absent: {', '.join(unknown)}.",
                        context={"absent": unknown, "recipient_unavailable": True,
                                 "recipient_candidates": self._person_candidates(a)})
            elif volume == "whisper":
                raise ActionRejected(
                    "低声说话必须用 to 指定你说过给谁听（同处一地的人）。",
                    context={"volume": "whisper", "missing": "to"})
            # One utterance = one tick (V4-ENGINE §4): conversation rounds
            # cost M ticks for M exchanges regardless of length.
            return timedelta(seconds=TICK_SECONDS)
        if i.kind == "text":
            target_id = x.get("target")
            if not isinstance(target_id, str) or not target_id:
                reachable = self._message_targets(a)
                raise ActionRejected(
                    "text needs an intended recipient in 'target'; no message was sent.",
                    context={"missing": "target", "recipient_candidates": reachable})
            target = self._actor(target_id)
            if target.id != a.id and target.id not in a.known_contacts and target.location != a.location:
                reachable = self._message_targets(a)
                raise ActionRejected(
                    f"you cannot contact {target.id}: not a known contact and not here.",
                    context={"target": target.id, "recipient_unavailable": True,
                             "recipient_candidates": reachable})
            if not isinstance(x.get("text"), str) or not x["text"]:
                raise ActionRejected("消息正文不能为空（text）。")
            # One communication tick (V4-ENGINE §2): a message takes one
            # tick to arrive, common knowledge, so sending words has a real
            # time cost.
            return timedelta(seconds=TICK_SECONDS)
        if i.kind in {"read", "leave_note", "trash"}:
            return self._item_duration(a, i)
        if i.kind == "knock":
            target = str(x.get("target"))
            if target not in self.locations or (a.location, target) not in self.routes:
                reachable = self._reachable(a)
                known = target in self.locations
                message = (f"「{target}」不是一个你知道的地方。" if not known
                           else f"你从{a.location}到不了「{target}」。")
                raise ActionRejected(
                    message,
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"target": target})
            return timedelta(seconds=3)
        if i.kind == "give":
            target_id = x.get("target")
            if not isinstance(target_id, str) or not target_id:
                raise ActionRejected(
                    "give needs an intended recipient in 'target'.",
                    context={"missing": "target",
                             "recipient_candidates": self._person_candidates(a)})
            target = self._actor(target_id)
            if target.id == a.id or target.location != a.location:
                raise ActionRejected(
                    f"{target.id}不在这里，你没法把东西递给对方。",
                    context={"target": target.id, "recipient_unavailable": True,
                             "recipient_candidates": sorted(
                                 {other.id for other in self.actors.values()
                                  if other.id != a.id and (other.location == a.location
                                     or other.id in a.known_contacts)})})
            item = str(x.get("item"))
            if item not in a.inventory:
                held = sorted(a.inventory)
                alternatives = [f"give {name} to {target.id}" for name in held]
                valid = "; ".join(self._tool_call_json(
                    "give", {"target": target.id, "item": name}) for name in held)
                suffix = f" 可行调用：{valid}。" if valid else "先拿起当前地点的一件物品，再递给在场的人。"
                raise ActionRejected(
                    f"你没有拿着「{item}」。你拿着：{', '.join(held) or '没有'}。{suffix}",
                    alternatives=alternatives,
                    context={"item": item, "available_items": held})
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
        if i.kind == "place":
            item = str(x.get("item"))
            if item not in a.inventory:
                held = sorted(a.inventory)
                present = sorted(name for name, place in self.item_locations.items()
                                 if place == a.location)
                alternatives = [f"place {name}" for name in held]
                if item in present:
                    alternatives.insert(0, f"take {item}")
                valid = "; ".join(self._tool_call_json("place", {"item": name})
                                  for name in held)
                take_hint = (f" First take it with {self._tool_call_json('take', {'item': item})}."
                             if item in present else "")
                suffix = f" Valid calls: {valid}.{take_hint}" if valid else \
                    (f" Take an item here first: {', '.join(present)}."
                     if present else "There is no item here to take before placing.")
                raise ActionRejected(
                    f"You are not holding '{item}'. You hold: {', '.join(held) or 'nothing'}.{suffix}",
                    alternatives=alternatives,
                    context={"item": item, "available_items": held,
                             "items_here": present})
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

    def _item_duration(self, actor: ActorState, intention: Intention) -> timedelta:
        kind = intention.kind
        item = str(intention.args.get("item"))
        if kind == "read":
            if item not in self.document_defs or not self._entity_available(actor.id, item):
                available = self._available_documents(actor)
                raise ActionRejected(
                    f"「{item}」现在不在你手边。你能读的：{', '.join(available) or '无'}。",
                    alternatives=[f"read {present}" for present in available],
                    context={"item": item})
            return timedelta(seconds=_as_int(self.document_defs[item].get("reading_seconds", 30), "reading_seconds"))
        if kind == "leave_note":
            text = intention.args.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ActionRejected("leave_note 需要非空文本（text）。")
            return timedelta(seconds=3)
        if kind == "trash":
            item = str(intention.args.get("item"))
            if item not in actor.inventory and self.item_locations.get(item) != actor.location:
                present, held = self._present_items(actor)
                candidates = sorted(set(present) | set(held))
                valid = "; ".join(self._tool_call_json("trash", {"item": name})
                                  for name in candidates)
                suffix = f" Available items and valid calls: {valid}." if valid else \
                    "There is no item here or in your inventory to trash."
                raise ActionRejected(
                    f"Cannot trash '{item}': it is neither held nor at this location.{suffix}",
                    alternatives=[f"trash {name}" for name in candidates],
                    context={"item": item, "available_items": candidates})
            return timedelta(seconds=3)
        return timedelta(seconds=3)

    def _complete(self, actor_id: str, payload: Mapping[str, Any]) -> None:
        if actor_id not in self.actors:
            # Defensive: a despawned extra's leftover job must not crash the
            # clock — the event stands (it happened), nothing mutates.
            return
        a = self._actor(actor_id); kind = payload["action"]
        if kind == "move": a.location = str(payload["target"])
        elif kind == "text":
            target_id = str(payload["target"])
            if target_id not in self.actors:
                # A text addressed to a despawned extra goes nowhere: the
                # stranger has left the scene (V4-CAST §1 zero-memory rule).
                return
            target = self.actors[target_id]
            target.inbox.append({"from": actor_id, "text": str(payload["text"]), "sent_at": self.now.isoformat()})
        elif kind == "take":
            item = str(payload["item"]); a.inventory.add(item); del self.item_locations[item]
        elif kind == "place":
            item = str(payload["item"]); a.inventory.remove(item)
            self._require_described(item)
            self.item_locations[item] = a.location
        elif kind == "leave_note":
            # Ruling 2026-09-22: a note is a room message attribute, not an
            # item — it joins the location's notes list and burns when read.
            note = {"author": actor_id, "text": str(payload["text"]),
                    "left_at": self.now.isoformat()}
            self.locations[a.location].notes.append(note)
        elif kind == "trash":
            item = str(payload["item"])
            self.item_locations.pop(item, None)
            a.inventory.discard(item)
        elif kind == "give":
            item = str(payload["item"]); target = self._actor(str(payload["target"]))
            a.inventory.remove(item); target.inventory.add(item)
        elif kind == "sleep": a.sleeping = False
        a.busy_until = None
        a.current_action = None

    def _commit_interaction(self, actor_id: str, payload: Mapping[str, Any], cause: int) -> Event:
        actor = self._actor(actor_id)
        kind = str(payload["action"])
        return self._commit(self._interaction_event(kind), actor_id,
                            self._interaction_payload(actor, payload), cause)

    def _interaction_event(self, kind: str) -> str:
        return {"knock": "knock", "give": "item_given",
                "read": "document_read", "leave_note": "note_left",
                "trash": "item_trashed"}[kind]

    def _interaction_payload(self, actor: ActorState, intention: Mapping[str, Any]) -> dict[str, Any]:
        kind = str(intention["action"])
        if kind == "give":
            return {"item": str(intention["item"]), "from": actor.id, "to": str(intention["target"])}
        if kind == "read":
            document = str(intention["item"])
            return {"document": document, "title": self.document_defs[document].get("title", document),
                    "content": self.document_defs[document].get("content", ""),
                    "annotations": [dict(entry) for entry in self.document_defs[document].get("annotations", [])]}
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
        if kind == "leave_note":
            return {"location": actor.location, "text": str(intention.get("text", ""))}
        if kind in {"trash"}:
            # these payloads carry no "target" key
            return {"target": ""}
        return {"target": str(intention["target"]) if "target" in intention else ""}

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
        if kind in {"wait_woken", "private_wake", "reminder_due"}:
            return {str(actor)} if actor is not None else set()
        if kind == "document_read":
            # Content privacy: only the reader sees the text.
            return {str(actor)}
        if kind == "documents_compared":
            # The equality verdict is the actor's private analysis.
            return {str(actor)}
        if kind == "document_annotated":
            # Visible facts on the physical record.
            return self._co_located(str(actor))
        if kind in {"action_started", "action_completed"} and payload.get("action") in {
                "read", "leave_note", "trash"}:
            # The fact is public; read/note contents are delivered privately.
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
        if kind == "action_started" and payload.get("action") == "text":
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
        if kind == "item_given":
            return self._co_located(str(payload["from"]))
        if kind in {"knock", "interaction"}:
            target = str(payload["target"])
            return {str(actor)} | {x.id for x in self.actors.values() if x.location == target}
        if kind == "note_left":
            return self._co_located(str(actor))
        if kind == "note_read":
            # 阅后即焚：content is private to the readers listed in the payload.
            return {str(r) for r in payload.get("readers", ()) if r in self.actors}
        if kind in {"extra_arrived", "extra_removed"}:
            return self._co_located(str(actor))
        if actor is None: return set(self.actors)
        return self._co_located(str(actor))

    def _co_located(self, actor_id: str) -> set[str]:
        """Everyone at the actor's location, plus the actor."""
        location = self.actors[actor_id].location
        return ({x.id for x in self.actors.values() if x.location == location}
                | {actor_id})

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
        if payload.get("action") == "text":
            # The sender must know which recipient's delivery is pending, but
            # the text is carried only by the private delivery event.
            return {"action": "text", "target": payload.get("target")}
        return dict(payload)

    @staticmethod
    def _public(e: Event, *, observer: str | None = None) -> dict[str, Any]:
        payload = dict(e.payload)
        # Keep note text in the authoritative journal for replay, but do not
        # expose it through another co-located actor's perception. The action
        # lifecycle events also carry the submitted text internally.
        is_note_action = (e.kind in {"action_started", "action_completed"}
                          and payload.get("action") == "leave_note")
        if (e.kind == "note_left" or is_note_action) and observer is not None and observer != e.actor:
            payload.pop("text", None)
        return {"id": e.id, "time": e.time.isoformat(), "kind": e.kind, "actor": e.actor, "payload": payload, "cause": e.cause}

    def _actor(self, actor_id: str) -> ActorState:
        if actor_id not in self.actors: raise ActionRejected(f"unknown actor: {actor_id}")
        return self.actors[actor_id]

    def _resolve_person(self, actor: ActorState, query: Any) -> tuple[str | None, str | None]:
        """Name resolution for person arguments (V4-AGENT-INTERFACE T4).

        Candidates are the actor's own world: contact formal names, their
        private aliases, and whoever is physically present. Exact match wins
        silently; a fuzzy hit is used with a teaching note; ambiguity or
        nothing is a rejection."""
        from .kb import resolve_name
        formal_names = set(actor.known_contacts)
        formal_names.update(other.id for other in self.actors.values()
                            if other.id != actor.id and other.location == actor.location)
        formal, formal_note = resolve_name(query, formal_names)
        if formal is not None and formal_note is None:
            return formal, None

        # An alias is verified only because this actor explicitly recorded it
        # for one formal contact. A unique fuzzy hit among those personal aliases
        # can safely correct to that same identity; arbitrary formal-name
        # substrings cannot.
        alias, alias_note = resolve_name(query, actor.contact_aliases)
        if alias is not None:
            return actor.contact_aliases[alias], alias_note
        note = formal_note or alias_note or f"unknown name '{query}'"
        if formal is not None:
            note = (f"unverified partial name '{query}'; use an exact formal name or "
                    "a registered personal nickname")
        return None, note

    def _canonicalize_persons(self, actor: ActorState, intention: Intention) -> Intention:
        """Rewrite person-name arguments to formal ids (T4/T3 裁决).

        ``text`` needs a contact row to go through; ``speak``/``give`` are
        co-presence actions, so present actors are always candidates. Returns
        the intention unchanged when nothing needs resolving."""
        args = dict(intention.args)
        changed = False
        for key in ("target",):
            query = args.get(key)
            if not isinstance(query, str) or not query.strip():
                continue
            resolved, note = self._resolve_person(actor, query)
            if resolved is None:
                raise ActionRejected(
                    str(note),
                    context={key: query, "name_resolution": True,
                             "recipient_candidates": self._person_candidates(actor)})
            if resolved != query:
                args[key] = resolved
                changed = True
        if intention.kind == "speak":
            to = args.get("to")
            if isinstance(to, list):
                resolved_to, notes = [], []
                for entry in to:
                    if entry == "陌生人":
                        # Ask-the-room token (ticket 22): routed to the extras
                        # machinery, never name-resolved.
                        resolved_to.append(entry)
                        continue
                    resolved, note = self._resolve_person(actor, entry)
                    if resolved is None:
                        notes.append(note or str(entry))
                    else:
                        resolved_to.append(resolved)
                        if resolved != entry:
                            changed = True
                if notes:
                    raise ActionRejected(
                        f"unknown or ambiguous speak recipient: {'; '.join(notes)}",
                        context={"unknown": notes, "name_resolution": True,
                                 "recipient_candidates": self._person_candidates(actor)})
                if resolved_to != to:
                    args["to"] = resolved_to
        if not changed:
            return intention
        return Intention(intention.actor, intention.kind, args,
                         intention.expected_version, inner=intention.inner,
                         interrupt=intention.interrupt,
                         uninterruptable=intention.uninterruptable)

    def _person_candidates(self, actor: ActorState) -> list[str]:
        """Names this actor can personally address, never the global roster."""
        return sorted({other.id for other in self.actors.values()
                       if other.id != actor.id and (
                           other.id in actor.known_contacts or other.location == actor.location)})

    def _message_targets(self, actor: ActorState) -> list[str]:
        """Expose only addressable people; the world does not reveal its roster."""
        return self._person_candidates(actor)

    def _require_location(self, location: str) -> None:
        if location not in self.locations: raise ValueError(f"unknown location: {location}")

    def _require_described(self, entity_id: str) -> None:
        """Ruling 2026-09-22: an item appearing without a description is a
        build error — fail loud instead of rendering an undescribed prop."""
        if entity_id not in self.entity_descriptions:
            raise ValueError(
                f"item '{entity_id}' appeared without a description "
                "(entity_descriptions); every appearing item must be described")

    def _consume_notes(self, location_id: str, reader_id: str,
                       cause: int | None) -> None:
        """Deliver each pending note to its first non-author entrant.

        Called only after an enter event; an author re-entering leaves their
        own note pending, while notes by other authors can still be consumed.
        Co-located observers never receive note contents. Sequential enter
        events make simultaneous arrivals deterministic.
        """
        location = self.locations[location_id]
        if (reader_id not in self.actors
                or self.actors[reader_id].location != location_id):
            return
        pending = list(location.notes)
        location.notes.clear()
        for note in pending:
            if note.get("author") == reader_id:
                location.notes.append(note)
                continue
            self._commit("note_read", note.get("author"),
                         {"location": location_id, "author": note.get("author"),
                          "left_at": note.get("left_at"), "text": note.get("text"),
                          "readers": [reader_id]},
                         cause)

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
