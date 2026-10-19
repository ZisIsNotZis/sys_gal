"""A mindless objective world kernel.

This module deliberately has no narrative, romance, route, chapter, or
character-resolution concepts. Agents own interpretation; the kernel owns
only state, time, visibility, and executable consequences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import heapq
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


class Count:
    """Picklable stand-in for ``itertools.count``.

    Python 3.14 dropped pickle support for ``itertools.count``, so
    ``copy.deepcopy`` of a World/ActorKB (replay.py, launch traces, kb
    restore) raised ``TypeError: cannot pickle 'itertools.count' object``.
    Monotonic arithmetic sequence: ``next()`` yields start, start+step, ...
    Restore sites seed it from the already-serialized ``next_*``/``shown_seq``
    value, so the checkpoint schema is untouched.
    """

    __slots__ = ("_value", "_step")

    def __init__(self, start: int = 0, step: int = 1) -> None:
        self._value = int(start)
        self._step = int(step)

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> int:
        value = self._value
        self._value += self._step
        return value

    def __getstate__(self) -> tuple[int, int]:
        return (self._value, self._step)

    def __setstate__(self, state: tuple[int, int]) -> None:
        self._value, self._step = state


TICK_SECONDS = 60
"""One tick (V4-ENGINE.md §2): the unit of minimum action duration, message
delivery delay, the decision-horizon bound, and the actors' common-knowledge
budgeting. Timestamps stay continuous — never assume a time is a tick
multiple, always round durations up with :func:`tick_ceil`."""

PERSISTENT_NOTE_READING_SECONDS = 30
"""How long an explicit `read` of a persistent note takes (ticket 88). It
matches a document's default `reading_seconds`: the note is a piece of prose
of unknown length, not a glance at an object."""

SLEEP_WAIT_SECONDS = 12 * 3600
"""A `wait` declared as sleep takes this long at most (ticket 101, E106).

The ordinary wait cap (`longest_wait_seconds`, 900s in this seed) is a
"stay attentive for a moment" bound; falling asleep is a different ask — the
window-6 night asked for 9.5–13.6 hours seven times and was told to split it
into 37 waits, so the night filled up with `wait 900` turns. Sleeping is not
a new action kind (V4-AGENT-INTERFACE §2 keeps sleep merged into wait): it is
`wait` with `sleep: true`, which is still wakeable and interruptible."""

WRITING_SURFACE_HINTS = ("纸", "写")
"""What makes an item a sheet you can write on (ticket 101, E105b).

`leave_note on=<paper>` must produce a real, readable record instead of
inventing a note — so the target has to be actual stationery, not any object
at hand. The seed declares no `writable:` key and the world stays untouched,
so the test reads the item's own objective description: it has to be paper
(纸) you can write on (写). 空白纸/可用纸笔 pass; 圆珠笔 (no 纸) and
蓝色兔子贴纸 (no 写) do not. A readable body (a 簿/本 in `document_defs`) is
never a blank sheet — those keep the annotation path (`on=<文书>`)."""


def _as_int(value, what="value"):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {what}: {value!r}") from exc


def _unknown_name_note(note: str | None) -> bool:
    """True when a name note means *no candidate matches at all*.

    Ticket 48: only this case offers the intent-preserving "find out who it
    is" path. A partial formal name that does exist (``unverified partial
    name``) and a genuine ambiguity (``ambiguous``) are different answers."""
    return bool(note) and str(note).startswith("unknown name")


def tick_ceil(seconds: float) -> int:
    """Round a raw duration up to whole ticks, minimum one tick
    (V4-ENGINE §2.1: every world action, even a query-like one, costs at
    least one tick)."""
    whole = _as_int(seconds, 'seconds')
    ticks = -(-whole // TICK_SECONDS) if whole > 0 else 1
    return max(1, ticks) * TICK_SECONDS


def _objective_text(description: str) -> str:
    """The objective description as prose (ticket 49).

    Drops the leading Markdown heading — it is only the entity name — and
    blank-line noise, keeping the body verbatim. Used for the observation
    record and for the read-fallback, so both show the same single text.
    """
    lines = [line for line in str(description).splitlines() if line.strip()]
    while lines and lines[0].lstrip().startswith("#"):
        lines.pop(0)
    return "\n".join(lines).strip()


WAKE_EVENT_KINDS = frozenset({"speech", "message_delivered", "knock", "interaction",
                              "item_given", "extra_arrived", "extra_removed",
                              "action_interrupted", "enter", "note_read"})
"""Ambient social events that end a light ``wait`` early (V4-ENGINE §3 wake
class). Movement/observation events only queue for the next turn."""

WAIT_SLEEP_HINT = "要睡到更晚（比如睡到明早、睡一整夜）就在 wait 里加 sleep: true。"
"""票 101（E106）：窗口 6 夜段 7 次 `wait 34200–48960` 被 900 秒上限拒收，模型
只能 37 次 `wait 900` 熬到天亮；拒绝回执必须直接给出睡眠这条路。"""

WALK_ALONE_HINT = "一个人走就只写 target——省略 with，不要写空值或占位符。"
"""票 98（E101）：窗口 5 里 `with: [""]`/`["_self"]`/`["陈默(you)"]` 出现 76 次，
模型在找“独自走”的表达法；拒绝回执必须直接给出这条路。"""


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
    # Ticket 49: the actor's own objective observation record, entity_id ->
    # {"objective", "at", "where"}. Registered once, on the poll where the
    # entity first enters view (place reached, item here, thing held) — never
    # from `known_to`. This is the persistent memory row that survives
    # compaction; `descriptions` is only the first-sight delivery of it.
    observed: dict[str, dict[str, str]] = field(default_factory=dict)
    # Ticket 49 stay-read: entities this actor has already read (actively or
    # by staying), so a stay never reads the same thing twice.
    read_entities: set[str] = field(default_factory=set)
    # Ticket 49 stay-read: per-entity continuous-stay start times. Cleared on
    # leaving a location, so a departure voids the dwell.
    reading_dwell: dict[str, datetime] = field(default_factory=dict)
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
    # Ticket 88: a note written with `persist: true` is the other kind — an
    # addressable, re-readable record that stays where it was left. Its id
    # lives in World.persistent_notes, never in this burn-on-read list.
    # (No field here: the note table is world-level, keyed by note id.)

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
            world.item_counts.pop(str(effect["id"]), None)
        elif op == "place_actor":
            # 票 113（112 §E2）：一个值班岗位就位。只用于 npc（装载器已禁止对 mc
            # 用这一手），它陈述的是“这段时间她在这个岗位上”这个制度事实，
            # 不是替角色做主：她做不做、说什么、还去不去别处仍由她自己的回合定。
            actor = world.actors.get(str(effect["id"]))
            if actor is not None:
                actor.location = str(effect["location"])


class World:
    """Authoritative, deterministic, event-sourced physical/social world."""

    ACTIONS = {"wait", "speak", "text", "move", "take", "place", "give",
               "read", "leave_note", "knock", "trash",
               "continue_action", "abandon_action"}

    def __init__(self, *, start: datetime, actors: Iterable[ActorState],
                 locations: Iterable[LocationState],
                 item_locations: Mapping[str, str] | None = None,
                 fixed_items: Mapping[str, str] | None = None,
                 routes: Mapping[tuple[str, str], int] | None = None,
                 sound_barriers: Mapping[tuple[str, str], float] | None = None,
                 scheduled: Iterable[Mapping[str, Any]] | None = None,
                 document_defs: Mapping[str, Mapping[str, Any]] | None = None,
                 copy_material_items: Iterable[str] | None = None,
                 item_counts: Mapping[str, int] | None = None,
                 entity_descriptions: Mapping[str, str] | None = None,
                 entity_access: Mapping[str, Iterable[str]] | None = None,
                 public_knowledge: Mapping[str, str] | None = None,
                 private_knowledge: Mapping[str, Mapping[str, str]] | None = None,
                 longest_wait_seconds: int = 3600,
                 unreachable_targets: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        actor_list = list(actors)
        self.now = start
        self.version = 0
        self.longest_wait_seconds = _as_int(longest_wait_seconds, 'longest_wait_seconds')
        self.actors = {a.id: a for a in actor_list}
        self.locations = {x.id: x for x in locations}
        self.item_locations = dict(item_locations or {})
        # Ticket 83: items declared `takeable: false` are 固定陈设 — present and
        # described like any other item, but they never enter an inventory and
        # never leave their place. The value is the authored `fixed_reason`
        # (empty string when the seed gives none). Seed-derived, like `routes`:
        # not part of the checkpoint.
        self.fixed_items = {str(k): str(v) for k, v in (fixed_items or {}).items()}
        self.routes = dict(routes or {})
        self.sound_barriers = dict(sound_barriers or {})
        self.document_defs = {str(k): dict(v) for k, v in (document_defs or {}).items()}
        self.copy_material_items = set(copy_material_items or ())
        # 票 113（112 §E1）：一件纸有几张。缺省不写 = 一张纸一件（旧语义，写一次
        # 就用完）。种子给一沓纸写 `count: N` 之后，
        # 写一张只少一张，纸仍然是纸，别人还能接着用——这是“一沓”在
        # “一个 id = 一样东西”里的正确落法，而不是再造 N 个 id。
        self.item_counts = {str(key): int(value)
                            for key, value in (item_counts or {}).items()}
        self.entity_descriptions = dict(entity_descriptions or {})
        # `entity_access` is the manifest `known_to` map: awareness only. It
        # drives name/recall resolution (``aware_of``) and never grants
        # readability or visibility (issues 39/40).
        self.entity_access = {str(k): set(v) for k, v in (entity_access or {}).items()}
        self.public_knowledge = dict(public_knowledge or {})
        self.private_knowledge = {str(k): dict(v) for k, v in (private_knowledge or {}).items()}
        # Ticket 66: seed-declared names a role treats as a place/contact but
        # the world can neither reach nor message (an off-campus neighbour, a
        # door-plate, a room inside a modelled building). Each carries a reason
        # and an executable alternative the rejection appends.
        self.unreachable_targets = {str(k): dict(v)
                                    for k, v in (unreachable_targets or {}).items()}
        self.event_log: list[Event] = []
        self._queue: list[_Scheduled] = []
        self._cancelled: set[int] = set()
        self._sequence = Count(1)
        self._event_id = Count(1)
        # Ticket 88: persistent notes (leave_note persist: true) are entities
        # with a stable id — `note-<author>-<serial>` — so they can be read
        # more than once by whoever is at their location. `_note_serial` is the
        # id counter; it rides the checkpoint so a resumed world never reuses
        # an id.
        self.persistent_notes: dict[str, dict[str, Any]] = {}
        self._note_serial = 1
        # Pre-run authored history (ticket 25): real past events, same Event
        # shape, negative id space. Never delivered, never replayed for `now`
        # — but flashback replays them like any memory of the past.
        self._history_id = Count(-1, -1)
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
                              "observed": {key: dict(entry)
                                           for key, entry in value.observed.items()},
                              "read_entities": sorted(value.read_entities),
                              "reading_dwell": {key: moment.isoformat()
                                                for key, moment in value.reading_dwell.items()},
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
            "item_counts": dict(self.item_counts),
            "document_defs": copy.deepcopy(self.document_defs),
            # Ticket 88: persistent notes are world state, so they and their id
            # counter ride the checkpoint; an older checkpoint simply has no
            # notes there and starts the counter at 1.
            "persistent_notes": {key: dict(value)
                                 for key, value in self.persistent_notes.items()},
            "next_note_serial": self._note_serial,
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
                    observed={str(key): dict(entry)
                              for key, entry in (row.get("observed") or {}).items()},
                    read_entities=set(row.get("read_entities", ())),
                    reading_dwell={str(key): datetime.fromisoformat(moment)
                                   for key, moment in (row.get("reading_dwell") or {}).items()},
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
            self.persistent_notes = {str(key): dict(value)
                                     for key, value in (state.get("persistent_notes") or {}).items()}
            # 票 113：一张纸上还剩几张是**世界状态**，所以随检查点走；旧检查点没有
            # 这一栏，退回种子的容量（写过的纸在旧局里本来就已经被消耗掉了）。
            self.item_counts = ({str(key): int(value)
                                 for key, value in state["item_counts"].items()}
                                if "item_counts" in state else dict(source.item_counts))
            self._note_serial = int(state.get("next_note_serial", 1))
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
            self._sequence = Count(int(state["next_sequence"]))
            self._event_id = Count(int(state["next_event_id"]))
            self.fixed_items = dict(source.fixed_items)
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
            self.unreachable_targets = {key: dict(value)
                                        for key, value in getattr(source, "unreachable_targets", {}).items()}
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

    def _fire_private_wake(self, job: Any) -> None:
        """V4-ENGINE §3: an idle heartbeat is a private event that names its
        target, so it reaches a sleeper exactly like a named `world_event`
        (E110): `wake_sleeper` ends the sleep and leaves the visible
        `wait_woken` fact at this tick, and the target's next poll sees both
        events. A target that is no longer in the world cannot be woken and
        cannot read the event, so the firing is recorded as a reasoned
        failure instead of a silently delivered dead letter."""
        actor_id = job.actor
        if actor_id is None or actor_id not in self.actors:
            self._commit("private_wake_failed", actor_id,
                         {"reason": "actor_not_present"}, None)
            return
        self._commit("private_wake", actor_id, {}, None)
        self.wake_sleeper(actor_id)

    def _move_hop(self, job: "Any") -> None:
        """Fire one hop boundary: enter the reached location, and (unless it
        is the destination) leave it again immediately — the discrete event
        sequence leave A / enter B / leave B / enter C (V4-ENGINE §2.1).
        Visibility: everyone at the location touched, plus the mover.

        票 95（E96）：`with` 里的人与发起者同步逐跳移动——每人各有一条自己的
        `enter`/`leave`（replay 只看 enter 就能重建他们的位置），并共享发起者
        的路线与时刻。被携带者没有被锁定：他在途中自己走开或开始走另一段路
        就不再跟随（“可在中途拒绝”），也不会有任何替他的动作事件。"""
        actor_id = job.actor
        if actor_id not in self.actors:
            return  # a despawned extra's leftover hop must not crash the clock
        a = self.actors[actor_id]
        path, index = job.payload["path"], _as_int(job.payload["index"], "hop index")
        new = str(path[index])
        if a.location == new:
            return
        previous = a.location
        a.location = new
        a.reading_dwell.clear()   # ticket 49: a departure voids the stay clock
        enter = self._commit("enter", actor_id, {"location": new}, None)
        # Each pending note goes to its first non-author entrant. The event
        # queue's (time, sequence) ordering breaks same-timestamp ties.
        self._consume_notes(new, actor_id, enter.id)
        if index < len(path) - 1:
            self._commit("leave", actor_id, {"location": new}, None)
        for companion_id in self._requested_companions(job.payload):
            companion = self.actors.get(companion_id)
            if companion is None or companion.location != previous:
                continue  # already gone / never joined
            if not self._follows_escort(companion, actor_id):
                continue  # declined mid-way: walking elsewhere or locked down
            companion.location = new
            companion.reading_dwell.clear()
            companion_enter = self._commit("enter", companion_id, {
                "location": new, "escorted_by": actor_id}, None)
            self._consume_notes(new, companion_id, companion_enter.id)
            if index < len(path) - 1:
                self._commit("leave", companion_id, {
                    "location": new, "escorted_by": actor_id}, None)

    def _follows_escort(self, companion: ActorState, initiator_id: str) -> bool:
        """Whether this actor is still being brought along (ticket 95, E96).

        The carried person keeps their own agency: an uninterruptable action, a
        pending continue-or-abandon decision, or a walk of their own means they
        are no longer following — the escort does not wait or drag them. A busy
        *interruptable* action (a sentence in progress) does not detach them:
        being walked somewhere does not stop you talking."""
        if companion.pending is not None:
            return False
        current = companion.current_action or {}
        if companion.busy_until and companion.busy_until > self.now:
            if current.get("uninterruptable"):
                return False
            payload = current.get("payload", {})
            if payload.get("action") == "move" and payload.get("escorted_by") != initiator_id:
                return False
        return True

    @staticmethod
    def _requested_companions(args: Mapping[str, Any]) -> list[str]:
        """Canonical, de-duplicated `with` list (ticket 95, E96)."""
        entries = args.get("with")
        if not isinstance(entries, (list, tuple)):
            return []
        return list(dict.fromkeys(str(entry).strip() for entry in entries
                                  if str(entry).strip()))

    def _schedule_move_hops(self, actor_id: str, path: list[str],
                            hop_seconds: list[int], duration_seconds: int,
                            cause: int | None,
                            companions: Iterable[str] = ()) -> list[int]:
        """Schedule the per-hop boundary jobs for a move; returns their queue
        sequences so an interrupt can cancel the remaining hops. `companions`
        ride every hop so the carried people keep pace (ticket 95, E96)."""
        total_raw = sum(hop_seconds)
        companions = list(companions)
        sequences = []
        elapsed = 0
        for index in range(1, len(path)):
            elapsed += hop_seconds[index - 1]
            when = self.now + timedelta(
                seconds=round(duration_seconds * elapsed / total_raw))
            payload: dict[str, Any] = {"path": list(path), "index": index}
            if companions:
                payload["with"] = companions
            sequences.append(self._schedule(
                when, "move_hop", actor_id, payload, cause).sequence)
        return sequences

    def wake_waiter(self, actor_id: str) -> bool:
        """V4-ENGINE §3 wake semantics: an ambient social event ends a `wait`
        early (the waiter notices and takes a turn). Since ticket 101 a
        `sleep: true` wait is still a `wait` — its payload action is `wait` —
        so a co-located social act ends a sleep too, and `wake_sleeper` (E106)
        is the extra path for a scheduled event that names the sleeper. Real
        actions are not wakeable: their events queue for delivery at the next
        turn instead. Returns True when the actor was woken."""
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
        a.sleeping = False
        return True

    def wake_sleeper(self, actor_id: str) -> bool:
        """A scheduled event that names this actor ends its sleep early (E106).

        睡眠的语义是“睡到指定时长，或被打断/被叫醒”：一场排程事件点了名（`target`
        里有他），就是在叫他——他不能因为睡着了而跨过它。只对睡眠生效：普通 `wait`
        的唤醒类仍是 V4-ENGINE §3 那一条（同地社交事件），不因点名事件而改变。"""
        a = self.actors.get(actor_id)
        if a is None:
            return False
        payload = (a.current_action or {}).get("payload") or {}
        if not payload.get("sleep"):
            return False
        return self.wake_waiter(actor_id)

    def schedule_private_wake(self, actor_id: str, when: datetime) -> int:
        """V4-ENGINE §3 idle heartbeat: schedule a private event that gives
        the actor a turn even when nothing else happens (MC idle heartbeat).
        Firing goes through `_fire_private_wake`: it wakes a sleeping target
        via `wake_sleeper` (E110) and records a reasoned failure when the
        target has already left the world. Returns the job sequence so the
        caller can cancel/reschedule it."""
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
        options += [{"kind": "take", "item": item} for item in self._takeable_here(a)]
        options += [{"kind": "knock", "target": location.id} for location in self.locations.values()
                    if not location.open and (a.location, location.id) in self.routes]
        # 票 95（E99）：递东西的候选不只来自背包——就在自己手边的物品也能
        # 直接 give（ticket 63 的 take-then-give 就地分支）。食堂的窗口阿姨
        # 因此看得到“把这份饭递给面前的人”，而不是只有背包里的东西。
        handable = sorted(set(a.inventory) | set(self._takeable_here(a)))
        options += [{"kind": "give", "target": other.id, "item": item}
                    for other in self.actors.values()
                    if other.id != actor_id and other.location == a.location
                    for item in handable]
        options += [{"kind": "place", "item": item} for item in sorted(a.inventory)]
        # E85（报 81 报告 08:53/13:13）：同一个动作的两个名字——写记录与留字条。
        # 先把"把话写成文字"放在能看见的地方，投递规则留给工具说明（一处完整
        # 说法），并说明它不取决于身上有什么：纸笔不是前提。票 95（E98）：手边
        # 有可写文书时，把 on= 这个入口也放在同一行提示里。票 101（E105b）：
        # 手边有张白纸时，"写在纸上"也是同一行提示里的一个入口。
        note_hint = ("写记录/留字条：把文字留在当前地点；不需要先拿到纸笔；"
                     "要留一份别人能再读到、一直留在这里的文稿就加 persist=true")
        writable = [doc for doc in self._available_readables(a)
                    if doc in self.document_defs]
        if writable:
            note_hint += ("；要在手边文书上补写/签名，加 on=<文书名>"
                          f"（这里能写：{', '.join(writable)}）")
        sheets = self._writable_sheets(a)
        if sheets:
            note_hint += ("；要写在手边一张纸上（写好后这份文稿就在你手上，可以 give 给别人），"
                          f"加 on=<纸张名>（能写的纸：{', '.join(sheets)}）")
        options += [{"kind": "leave_note", "text": "", "hint": note_hint},
                    *({"kind": "trash", "item": item}
                      for item in sorted(a.inventory)
                      + [note["id"] for note in self._notes_here(a)])]
        options += [{"kind": "read", "item": document}
                    for document in self._available_readables(a)]
        return options

    def submit(self, intention: Intention, *,
               seen_here: Iterable[str] | None = None) -> tuple[Event, ...]:
        """Submit one intention to the world (V4-ENGINE §2.4).

        ``seen_here`` is the list of other actors the submitting actor
        perceived at its location **when it decided** — the same perception
        snapshot its affordances came from (`nearby_actors`). Recipient
        resolution and co-presence are judged against that snapshot instead of
        against the world some deliberation later (ticket 46: the d1-am run
        rejected 班长's 11:09 line to 陈默 as `absent: 陈默` and 辅导员's 11:30
        line to three people because one of them had walked off meanwhile).
        Someone who left after the snapshot is not a rejection: the words are
        committed for the addressees still here and the departed one is
        reported as undelivered. ``None`` (bare kernel, no turn context) keeps
        the live world as the only source.
        """
        a = self._actor(intention.actor)
        if intention.expected_version is not None and intention.expected_version != self.version:
            raise ActionRejected("世界已发生变化，请重新观察后再行动（stale world version）")
        if intention.kind not in self.ACTIONS:
            raise ActionRejected(f"unknown action '{intention.kind}'; "
                                 "see your tool list for the current actions")
        if intention.kind == "speak" and "volume" not in intention.args:
            # A bare-kernel caller (no engine turn context) may submit a speak
            # without the tool-schema decoration; default it to normal volume.
            # The listener set is computed at commit. Ticket 64: the engine's
            # actors speak only through speak/text calls, so this fallback is
            # not the content path.
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
        if intention.kind in {"text", "give"}:
            # Person-name resolution (V4-AGENT-INTERFACE T4): a nickname that
            # uniquely matches one candidate is canonicalized here, before any
            # validation, so both the gate and the committed event see formal
            # names. Ambiguity/no-hit is rejected with the candidates that
            # would actually succeed for this action.
            intention = self._canonicalize_persons(a, intention, seen_here)
        elif intention.kind == "move":
            # 票 95（E96）：with 里的名字与 speak/text 的名字同一套解析。
            intention = self._canonicalize_companions(a, intention, seen_here)
        elif intention.kind == "speak":
            # Addressed speech is planned per addressee (ticket 46).
            intention = self._canonicalize_speech(a, intention, seen_here)
        elif intention.kind == "leave_note":
            # 票 98（E100）：`on` 只有非空字符串才算“写进既有文书”。空串/纯空白
            # 等于没提供，按普通便条走（persist 照常生效）——否则“留一份新文稿”
            # 会被自己判成“同时声明了 on 与 persist”（窗口 5 106 条拒绝的成因）。
            # 在提交入口一次性剔除，后面的校验、payload、事件与 replay 只看一种写法。
            on = intention.args.get("on")
            if isinstance(on, str) and not on.strip():
                args = dict(intention.args)
                args.pop("on", None)
                intention = Intention(intention.actor, intention.kind, args,
                                      intention.expected_version, inner=intention.inner,
                                      interrupt=intention.interrupt,
                                      uninterruptable=intention.uninterruptable)
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
        if intention.kind == "leave_note":
            on = action_payload.get("on")
            if on and str(on) not in self.document_defs:
                # 票 101（E105b）：写在一张白纸上——校验已经确认它是纸（`_writable_sheets`），
                # 产物就是一份带编号的文稿（等同于 persist），而不是批注。
                action_payload["persist"] = True
                # 票 113（112 §E1）：这一张纸写完之后还剩几张。一沓纸（种子写
                # `count: N`）写一张只少一张，纸本身仍是纸；没写 count 的
                # 单张纸照旧写一次就用完。
                action_payload["count_left"] = max(
                    self.item_counts.get(str(on), 1) - 1, 0)
            if action_payload.get("persist"):
                # Ticket 88: the id of a persistent note is fixed at submit, so the
                # started event (which the tool receipt reads) and the completion
                # agree on one addressable name, and a checkpoint taken mid-write
                # keeps it.
                action_payload["note"] = self._next_note_id(a.id)
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
                # 票 95（E96）：被携带者与发起者同步离开原地。之后每一个
                # hop 由 `_move_hop` 同步推进；没有为他们另造动作事件。
                for companion_id in self._requested_companions(action_payload):
                    companion = self.actors.get(companion_id)
                    if companion is not None and companion.location == a.location:
                        self._commit("leave", companion_id, {
                            "location": a.location, "escorted_by": a.id}, None)
        if intention.kind == "speak":
            speech_payload = {"text": intention.args["text"],
                              "volume": intention.args.get("volume", "normal")}
            # The public heard list must match authoritative delivery, including
            # closed-location barriers. Never let a briefing infer hearing from
            # co-location when the event is private to its speaker.
            audience = self._hearing_actors(a.id, intention.args)
            speech_payload["heard"] = sorted(audience - {a.id})
            # 点名对象无论音量都记录（可见性不变：normal 仍全地点可闻）；
            # 唤醒与起哄逻辑需要知道话是对谁说的。
            if intention.args.get("to"):
                speech_payload["to"] = list(intention.args["to"])
            self._commit("speech", a.id, speech_payload,
                         started.id if started else None)
            # Merged ask (ticket 22): to=["陌生人"] asks the room's passers-by.
            # The spawn fires at the utterance's completion tick (the moment
            # the message is heard), keyed by cause so _handle_extras can
            # match it — never at submit time. Ticket 88: naming a pool alias
            # ("老板娘") is the same ask with a known face — the payload names
            # the alias so the engine can spawn that entry.
            addressed = [str(name) for name in intention.args.get("to") or ()]
            alias = next((name for name in addressed
                          if name != "陌生人"
                          and self.pool_entry_for_alias(a.location, name) is not None), None)
            if "陌生人" in addressed or alias is not None:
                ask_payload: dict[str, Any] = {"question": intention.args["text"]}
                if alias is not None:
                    ask_payload["alias"] = alias
                self._commit("stranger_asked", a.id, ask_payload,
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
                    _as_int(duration.total_seconds(), 'duration'), started.id if started else None,
                    companions=self._requested_companions(action_payload))
            job = self._schedule(self.now + duration, "action_completed", a.id,
                                 action_payload, started.id if started else None)
            sequence = job.sequence
        else:
            self._schedule(self.now, "action_completed", a.id, action_payload, None)
            self.advance(until=self.now)
        a.busy_until = self.now + duration if duration else None
        a.sleeping = bool(duration and action_payload.get("sleep"))
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
                a.id, remaining_path, remaining_hops, remaining, event.id,
                companions=self._requested_companions(payload))
        job = self._schedule(self.now + timedelta(seconds=remaining),
                             "action_completed", a.id, payload, event.id)
        a.pending = None
        a.busy_until = self.now + timedelta(seconds=remaining)
        a.sleeping = bool(payload.get("sleep"))
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
            if job.kind == "private_wake":
                self._fire_private_wake(job)
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
        # Ticket 49 (ruling 2026-09-30): perception construction is also the
        # moment of seeing. Record each newly visible entity's objective
        # description as an actor memory row + an observable `observed`
        # event, then honour a stay long enough to count as reading.
        newly = self._record_observations(a)
        self._stay_reads(a)
        cursor = self._cursor[actor_id]
        visible = [e for e in self.event_log[cursor:] if actor_id in e.visible_to]
        self._cursor[actor_id] = len(self.event_log)
        inbox = list(a.inbox)
        a.inbox.clear()
        # Ticket 66: a message can arrive from someone the recipient has not
        # recorded — the address book is private and asymmetric by design. The
        # recipient may only reply to a known contact, so surface the gap (and
        # the executable way to close it) instead of silently dropping the
        # reply. The knowledge itself is never rewritten here.
        unrecorded = sorted({str(item.get("from")) for item in inbox
                             if item.get("from")
                             and str(item["from"]) not in a.known_contacts})
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
                  "notes_here": self._notes_here(a),
                  "inbox": inbox, "unrecorded_senders": unrecorded,
                  "events": [self._public(e, observer=actor_id) for e in visible],
                  "knowledge": self._knowledge(a) if full_state else {}}
        if full_desc:
            result["descriptions"] = {
                entity_id: self.entity_descriptions[entity_id]
                for entity_id in sorted(self._visible_descriptions(a))
                if entity_id in self.entity_descriptions}
        else:
            # An entity that just came into view still gets its first-sight
            # description even when the place was described before; thereafter
            # it lives in `observed` and the read-fallback can return it.
            fresh = {entity_id: self.entity_descriptions[entity_id]
                     for entity_id in newly if entity_id in self.entity_descriptions}
            if fresh:
                result["descriptions"] = fresh
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

    def scene_perception(self, actor_id: str, *, tail: int = 12) -> dict[str, Any]:
        """Read-only scene view for a conversation-scoped extra (ticket 57).

        Same delivery authority as :meth:`poll` — ``Event.visible_to`` plus
        co-location — but with none of poll's side effects: an extra has no
        perception cursor to advance, no inbox to consume, and no
        observation / stay-read bookkeeping to run. It exists so an extra can
        see who is here, what is here (each entity carries its real
        description, so a quantity like “一份” is stated instead of guessed),
        and what just happened.

        票 98（E103）：物件描述的投递比 `poll` 再窄一层——被种子 `known_to` 限定给
        别人的东西，extra 看得见它在场（`nearby_items`），但不拿到它的描述正文。
        窗口 5 15:06 陌生人回话里那句还没送到的便条正文就是这条路送出去的：
        `代话便条` 的客观描述就是便条正文，而它 `known_to: [唐小岚]`。
        """
        a = self._actor(actor_id)
        visible = [e for e in self.event_log[-tail:] if actor_id in e.visible_to]
        return {
            "observer": actor_id, "time": self.now.isoformat(),
            "world_version": self.version, "location": a.location,
            "nearby_actors": sorted(x.id for x in self.actors.values()
                                    if x.id != actor_id and x.location == a.location),
            "nearby_items": sorted(i for i, loc in self.item_locations.items()
                                   if loc == a.location),
            "notes_here": self._notes_here(a),
            "inventory": sorted(a.inventory),
            "events": [self._public(e, observer=actor_id) for e in visible],
            "descriptions": {entity_id: self.entity_descriptions[entity_id]
                             for entity_id in sorted(self._visible_descriptions(a))
                             if entity_id in self.entity_descriptions
                             and self._described_to(a, entity_id)},
        }

    def _described_to(self, actor: ActorState, entity_id: str) -> bool:
        """Whether this observer may be handed the entity's description body.

        A seed's `known_to` declares who knows a thing exists; anyone outside
        that list may see it is here (`nearby_items`) but not receive its
        description text. Ticket 57's quantity grounding (`一份`) needs the
        descriptions of unrestricted props, which stay untouched — this only
        withholds what the seed itself restricted.
        """
        restricted = self.entity_access.get(entity_id)
        return not restricted or actor.id in restricted

    def _is_entity(self, entity_id: str) -> bool:
        """Whether the world ever held a thing under this name (E102).

        A name that was never registered is not “gone”: it is absent, and the
        rejection says so instead of inventing a history for it. Everything
        else — an item, a document, a fixture, a persistent note — was once
        somewhere, so “it is nowhere now” is the true statement."""
        return (entity_id in self.item_locations or entity_id in self.document_defs
                or entity_id in self.fixed_items
                or entity_id in self.persistent_notes
                or entity_id in self.entity_descriptions)

    def notify_compaction(self, actor_id: str) -> None:
        """The actor's context was just rewritten (compaction): force one full
        state + description re-observation on the next poll, since the details
        the world would otherwise only push as changes are gone from memory."""
        self._actor(actor_id).force_observation = True

    def _visible_descriptions(self, actor: ActorState) -> set[str]:
        """Descriptions injected by arrival/presence (issue 40): what is here
        or held. `known_to` (awareness) no longer injects a description."""
        visible = {actor.location}
        visible.update(item for item, location in self.item_locations.items() if location == actor.location)
        visible.update(item for item in actor.inventory)
        return visible

    def _record_observations(self, actor: ActorState) -> list[str]:
        """Ticket 49: write each newly visible entity's objective description
        into the actor's memory and emit one private `observed` event.

        The visible set is exactly :meth:`_visible_descriptions` — the place,
        items here, and things held; `known_to` awareness grants nothing.
        Each entity is registered at most once, which is what lets a resumed
        actor stay silent about what it already saw."""
        newly: list[str] = []
        for entity_id in sorted(self._visible_descriptions(actor)):
            if entity_id in actor.observed:
                continue
            objective = self.entity_descriptions.get(entity_id)
            if objective is None:
                continue  # an undescribed entity has nothing objective to record
            actor.observed[entity_id] = {
                "objective": _objective_text(objective),
                "at": self.now.isoformat(),
                "where": actor.location,
            }
            self._commit("observed", actor.id,
                         {"entity": entity_id, "where": actor.location}, None)
            newly.append(entity_id)
        return newly

    def _stay_reads(self, actor: ActorState) -> None:
        """Ticket 49 stay-read: staying in view of a readable thing for its
        ``reading_seconds`` counts as having read it (ruling 2026-09-30).

        The dwell is per-entity and continuous: it starts at the first poll
        that sees the entity, is voided by any departure (the mover clears
        ``reading_dwell``), and is dropped when the entity stops being here or
        held. An entity is auto-read at most once, and a document declared
        ``auto_read: false`` is never read this way. The committed event is an
        ordinary ``document_read`` (the same private channel), marked
        ``auto`` so the milestone evidence stays distinguishable."""
        present = self._available_readables(actor)
        for entity_id in list(actor.reading_dwell):
            if entity_id not in present:
                del actor.reading_dwell[entity_id]
        for entity_id in present:
            if entity_id not in self.document_defs:
                # Ticket 88: a persistent note is not a document row, so the
                # stay-read timer does not apply — it is read by calling `read`,
                # and may be read as many times as the reader wants.
                actor.reading_dwell.pop(entity_id, None)
                continue
            if (entity_id in actor.read_entities
                    or self.document_defs[entity_id].get("auto_read", True) is False):
                actor.reading_dwell.pop(entity_id, None)
                continue
            started = actor.reading_dwell.setdefault(entity_id, self.now)
            seconds = _as_int(self.document_defs[entity_id].get("reading_seconds", 30),
                              "reading_seconds")
            if (self.now - started).total_seconds() < seconds:
                continue
            del actor.reading_dwell[entity_id]
            actor.read_entities.add(entity_id)
            definition = self.document_defs[entity_id]
            self._commit("document_read", actor.id, {
                "document": entity_id,
                "title": definition.get("title", entity_id),
                "content": definition.get("content", ""),
                "annotations": [dict(entry) for entry in definition.get("annotations", [])],
                "auto": True,
            }, None)

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
            "abandon_action for a true interruption. 一个回合只应有一个耗时动作，把它留到下一回合："
            "等当前动作完成后再提交 "
            f"{self._tool_call_json(intention.kind, intention.args)}。")
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
            # 票 101（E106）：`sleep: true` 是 `wait` 的一个参数，不是新动作——
            # 睡着时世界照旧走，被唤醒/被打断就提前结束。普通等待的上限是“守一会
            # 儿”的时长；睡眠另外有一条更宽的上限（`SLEEP_WAIT_SECONDS`）。
            sleep = x.get("sleep")
            if sleep is not None and not isinstance(sleep, bool):
                raise ActionRejected(
                    "wait 的 sleep 只能是 true / false：睡着了就是 sleep: true 的 wait。",
                    context={"sleep": sleep})
            seconds = x.get("duration_seconds")
            if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
                raise ActionRejected(
                    'wait needs a positive integer duration_seconds; for one minute use '
                    '{"name": "wait", "arguments": {"duration_seconds": 60}}.')
            limit = SLEEP_WAIT_SECONDS if sleep else self.longest_wait_seconds
            if seconds > limit:
                if sleep:
                    head = (f"一次睡眠最长 {SLEEP_WAIT_SECONDS} 秒（12 小时），"
                            "被打断或有人叫醒会提前结束；要更久就分两次睡。")
                else:
                    head = (f"单次等待不能超过 {self.longest_wait_seconds} 秒。{WAIT_SLEEP_HINT}"
                            f"睡眠单次最长 {SLEEP_WAIT_SECONDS} 秒（12 小时），"
                            "被打断或有人叫醒会提前结束。")
                # 回执里给出“把这个时长改成 sleep:true”的可执行例子：窗口 6 的
                # 7 次拒收全是“睡到明早”，模型缺的就是这一次改写。
                example = self._tool_call_json(
                    "wait", {"duration_seconds": min(seconds, SLEEP_WAIT_SECONDS),
                             "sleep": True})
                raise ActionRejected(f"{head}例如：{example}。",
                                      context={"limit": limit, "sleep": bool(sleep),
                                               "sleep_limit": SLEEP_WAIT_SECONDS})
            return timedelta(seconds=seconds)
        if i.kind == "speak":
            if not isinstance(x.get("text"), str) or not x["text"]:
                raise ActionRejected("说话需要非空的 text。")
            volume = x.get("volume", "normal")
            if volume not in {"whisper", "normal"}:
                raise ActionRejected("volume 只能是 whisper（低声，仅指定对象听见）或 normal（全地点）。")
            targets = x.get("to")
            if targets is not None:
                # The addressee list has already been through
                # _canonicalize_speech, which keeps only reachable people and
                # records the rest as `undelivered`; an empty list is a real
                # outcome (everyone named had left), not a shape error.
                if (not isinstance(targets, list)
                        or not all(isinstance(t, str) for t in targets)
                        or (not targets and not x.get("undelivered"))):
                    raise ActionRejected(
                        "to 必须是名字列表（在场的人，或 [\"陌生人\"] 向路人搭话）。",
                        context={"missing": "to"})
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
                hint = self._unreachable_note(target)
                if hint:
                    message += hint
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
                             "recipient_candidates": self._present_others(a)})
            target = self._actor(target_id)
            if target.id == a.id or target.location != a.location:
                raise ActionRejected(
                    f"{target.id}不在这里，你没法把东西递给对方；东西还在你手里。",
                    context={"target": target.id, "recipient_unavailable": True,
                             "recipient_candidates": self._present_others(a)})
            item = str(x.get("item"))
            here, held = self._present_items(a)
            note = self.persistent_notes.get(item)
            # 票 101（E105）：一张留在你身边（或已经被你拿着）的字条是可递的——
            # 字条本来就在世界上，递它就是递那张纸；被别人拿在手上的那张不算。
            note_here = (note is not None and self._note_carrier(item) is None
                         and str(note.get("location")) == a.location)
            if (item not in a.inventory and self.item_locations.get(item) != a.location
                    and not note_here):
                if note is not None:
                    # 票 101（E105）：字条本来就在世界上，递它就是递那张纸。一条字条
                    # 只能从写它的地点或被递到手的那一刻开始转手，所以这张不在手上
                    # 就不在你的手里——拒绝里只说它现在在谁手上/哪里，不得再拿无关
                    # 文书当替代。
                    carrier = self._note_carrier(item)
                    where = (f"在{carrier}手上" if carrier
                             else f"留在{note.get('location')}")
                    raise ActionRejected(
                        f"「{item}」是一张字条，现在不在你手上：它{where}。"
                        "先把它拿到手（写在一张纸上，或让拿着它的人递给你，或到它所在的"
                        "地方读它），才能再递给别人。",
                        context={"item": item, "note": True,
                                 "note_location": note.get("location"),
                                 "carried_by": carrier or None})
                # Ticket 63: the 上菜/递物 gap. `give` also accepts an item
                # that is physically at the actor's OWN location (the window
                # counter), i.e. an atomic pick-up-and-hand-over — the
                # take-then-give semantics are unchanged, just executable when
                # the thing is right at hand. It never invents an item that is
                # neither held nor here.
                alternatives = [f"give {name} to {target.id}" for name in held]
                alternatives += [f"give {name} to {target.id}"
                                 for name in here if name not in self.fixed_items]
                alternatives += [f"take {name}" for name in self._takeable_here(a)]
                handable = held + [name for name in here if name not in self.fixed_items]
                valid = "; ".join(self._tool_call_json(
                    "give", {"target": target.id, "item": name}) for name in handable)
                suffix = (f" 可行调用：{valid}。" if valid
                          else "先拿起当前地点的一件物品，再递给在场的人。")
                raise ActionRejected(
                    f"你没有拿着「{item}」，这里也没有「{item}」。"
                    f"你拿着：{', '.join(held) or '没有'}；"
                    f"这里有的：{', '.join(here) or '没有'}。{suffix}",
                    alternatives=alternatives,
                    context={"item": item, "available_items": held,
                             "items_here": here})
            if item not in a.inventory and item in self.fixed_items:
                # Ticket 83: the at-hand branch would lift a fixture out of the
                # room (ticket 63's atomic pick-up-and-hand-over).
                self._reject_fixed_item(a, item)
            if item not in a.inventory:
                # 票 98（E102）：就地递出也把东西从原地拿走，所以它和 take 争同一
                # 件东西——两个人各递一次同一份饭曾经能让两个人背包里都有一份。
                claimant = self._item_claimant(a, item)
                if claimant is not None:
                    raise ActionRejected(
                        f"「{item}」正被{claimant}拿着，还没落到你手里，你没法把它递给"
                        f"{target.id}：等这一步结束，再看它还在不在{a.location}。",
                        context={"item": item, "claimed_by": claimant})
            return timedelta(seconds=2)
        if i.kind == "move":
            target = str(x.get("target"))
            if target not in self.locations:
                reachable = self._reachable(a)
                hint = self._unreachable_note(target)
                raise ActionRejected(
                    f"「{target}」不是一个你知道的地方。"
                    + (f"{hint} " if hint else "")
                    + f"从{a.location}可以到："
                    f"{', '.join(reachable) or '没有'}。",
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"target": target})
            if not self.locations[target].open:
                open_neighbors = self._reachable_open(a)
                raise ActionRejected(
                    f"「{target}」现在关着，进不去。",
                    alternatives=[f"move to {neighbor} (open)" for neighbor in open_neighbors],
                    context={"target": target, "open": False})
            # 票 95（E96）：move 可以带上同在此地的人（扶/陪）。被携带者仍是
            # 自主的：他自己看、自己说；只是“没人扶/没法带”不再是一个缺口。
            # 拒绝是结构化的：不在这里、正被锁在一个不能打断的动作里、或
            # 自己正在往别处走，都整次拒绝并说清是哪一个人、为什么。
            for companion_id in self._requested_companions(x):
                if companion_id == a.id:
                    raise ActionRejected(
                        "with 里不能写自己：你自己就是发起者，写要带谁一起走。",
                        context={"with": companion_id})
                companion = self.actors.get(companion_id)
                if companion is None:
                    raise ActionRejected(
                        f"这个世界里没有「{companion_id}」这个人。",
                        alternatives=[f"move <地点> with {name}"
                                      for name in self._present_others(a)],
                        context={"with": companion_id, "name_resolution": True,
                                 "companion_candidates": self._present_others(a)})
                if companion.location != a.location:
                    raise ActionRejected(
                        f"{companion_id}不在这里（{companion.location}），你没法带着他走；"
                        "要一起走，先到同一个地点。",
                        context={"with": companion_id, "absent": True,
                                 "companion_candidates": self._present_others(a)})
                if companion.pending is not None:
                    interrupted = str(companion.pending.get("payload", {})
                                       .get("action", "action"))
                    raise ActionRejected(
                        f"{companion_id}刚被打断（「{interrupted}」还没决定继续还是放弃），"
                        "这会儿不能带他走；等他自己处理完。",
                        context={"with": companion_id, "pending": interrupted})
                if companion.busy_until and companion.busy_until > self.now:
                    current = companion.current_action or {}
                    action = str(current.get("payload", {}).get("action", "action"))
                    if current.get("uninterruptable"):
                        raise ActionRejected(
                            f"{companion_id}正在做「{action}」，这件事不能被打断，"
                            "没法带着他走；等它结束再一起走。",
                            context={"with": companion_id, "uninterruptable": True,
                                     "action": action,
                                     "busy_until": companion.busy_until.isoformat()})
                    if action == "move":
                        raise ActionRejected(
                            f"{companion_id}自己正在往别处走，不能被你带走；"
                            "等他到，或让他自己跟来。",
                            context={"with": companion_id, "walking": True})
            # V4-DESIGN §5.6 + multi-hop move: the actor states intent; the
            # engine finds the shortest walk and its duration is the map's
            # physical fact, never an actor-supplied argument.
            found = self._route_path(a.location, target)
            if found is None:
                reachable = self._reachable(a)
                message = f"从{a.location}走到「{target}」没有可用的路。"
                hint = self._unreachable_note(target)
                if hint:
                    message += hint
                raise ActionRejected(
                    message,
                    alternatives=[f"move to {n}" for n in reachable],
                    context={"from": a.location, "target": target})
            return timedelta(seconds=sum(found[1]))
            return timedelta(0)
        if i.kind == "take":
            item = str(x.get("item"))
            _here, held = self._present_items(a)
            if self.item_locations.get(item) != a.location:
                raise self._take_rejection(a, item, held)
            if item in self.fixed_items:
                self._reject_fixed_item(a, item)
            # 票 98（E102）：一件东西从提交到完成之间只有一个归属。窗口 5
            # 17:57 陈默与辅导员各自 `take 一份晚饭`，两次都通过校验，两条
            # `action_completed` 都写下“拿起了”，只有先完成的那位背包里真的有它
            # （辅导员 17:59 还对食堂大妈说“我们都拿了晚饭”）。回执说成功、世界
            # 没变 = 票 75 的同一族；这里把“有人正在拿这一件”变成一个真实的拒绝。
            claimant = self._item_claimant(a, item)
            if claimant is not None:
                takeable = [name for name in self._takeable_here(a) if name != item]
                raise ActionRejected(
                    f"「{item}」正被{claimant}拿在手里，还没落到你手里：等这一步结束，"
                    f"再看看它还在不在{a.location}。",
                    alternatives=[f"take {name}" for name in takeable],
                    context={"item": item, "claimed_by": claimant,
                             "takeable_here": takeable})
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
        if not self.available_now(actor_id, entity_id):
            return None
        return self.entity_descriptions.get(entity_id)

    def available_now(self, actor_id: str, entity_id: str) -> bool:
        """Physical reach today: the entity is held, at the actor's
        location, or — for a persistent note — lying where it was left. This
        — not `known_to` — is what `read` and the read suggestions treat as
        available (issues 39/40).

        票 101（E105）：一张被递出去的字条进了收件人的背包（`give` 完成后它在
        `inventory` 里），所以第一个条件已经盖住了；而别人拿在手上的那张不再是
        “留在这里的纸”，同屋的人不能隔着手读它。"""
        actor = self._actor(actor_id)
        if entity_id in actor.inventory or self.item_locations.get(entity_id) == actor.location:
            return True
        note = self.persistent_notes.get(entity_id)
        return (note is not None and str(note.get("location")) == actor.location
                and self._note_carrier(entity_id) is None)

    def _note_carrier(self, entity_id: str) -> str | None:
        """Who is carrying this persistent note right now, or None (E105).

        一张被递出去的字条与一件物品同义：持有关系就写在持有者的背包里。
        """
        return next((other.id for other in self.actors.values()
                     if entity_id in other.inventory), None)

    def _writable_sheets(self, actor: ActorState) -> list[str]:
        """Blank sheets at hand that `leave_note on=<纸张>` can write on.

        票 101（E105b）：判据只有三条——它在本手上或本地点（物理够得着）、它不是有
        正文的文书（有正文的走 `document_defs` 的批注路径，按目标类型分派）、它自己的
        客观描述既是纸又能写（见 `WRITING_SURFACE_HINTS`）。固定陈设拿不走，也不算。"""
        here, held = self._present_items(actor)
        return [item for item in held + here
                if item not in self.document_defs and item not in self.fixed_items
                and all(hint in str(self.entity_descriptions.get(item) or "")
                        for hint in WRITING_SURFACE_HINTS)]

    def readable_body(self, entity_id: str) -> dict[str, Any] | None:
        """The readable body of an entity (ticket 88).

        A document row is read as declared. A persistent note is read from its
        own stored text: its id is the read target, and it stays readable for
        as long as it lies there. A burn-on-read note is never addressable, so
        it never appears here.
        """
        if entity_id in self.document_defs:
            return dict(self.document_defs[entity_id])
        note = self.persistent_notes.get(entity_id)
        if note is None:
            return None
        return {"title": f"字条（{note.get('author')} 留）",
                "content": str(note.get("text", "")),
                "reading_seconds": PERSISTENT_NOTE_READING_SECONDS,
                "annotations": []}

    def aware_of(self, actor_id: str, entity_id: str) -> bool:
        """Awareness only (manifest `known_to`): the actor knows the thing
        exists. Useful for naming and recall; it grants no physical access and
        never makes an entity readable or visible."""
        return actor_id in self.entity_access.get(entity_id, set())

    def _item_duration(self, actor: ActorState, intention: Intention) -> timedelta:
        kind = intention.kind
        item = str(intention.args.get("item"))
        if kind == "read":
            definition = self.readable_body(item)
            if definition is None or not self.available_now(actor.id, item):
                raise self._read_rejection(actor, item)
            return timedelta(seconds=_as_int(definition.get("reading_seconds", 30), "reading_seconds"))
        if kind == "leave_note":
            text = intention.args.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ActionRejected("leave_note 需要非空文本（text）。")
            on = intention.args.get("on")
            if on is not None:
                document = str(on)
                definition = self.document_defs.get(document)
                if definition is not None:
                    # 票 95（E98）：在既有文书上补写/签名 = 往那份文书的 annotations
                    # 追加一条，不新增动作种类。文书必须在这里或手上（可读），
                    # 条目只追加、不覆盖别人写的。persist 是“留一份新文稿”，
                    # 与“写进既有文书”是两件事，不能同时声明。
                    if intention.args.get("persist"):
                        raise ActionRejected(
                            "leave_note 的 on（写进既有文书）与 persist（留一份新文稿）"
                            "只能选一个。",
                            context={"on": str(on), "persist": True})
                    if not self.available_now(actor.id, document):
                        raise self._unwritable_on_rejection(actor, document)
                elif document not in self._writable_sheets(actor):
                    # 票 101（E105b）：on 也可以指向手边一张白纸（抽一张来写）——
                    # 那时产物是一份可读、可递的文稿，不是批注，也不是凭空字条。
                    raise self._unwritable_on_rejection(actor, document)
            return timedelta(seconds=3)
        if kind == "trash":
            item = str(intention.args.get("item"))
            note = self.persistent_notes.get(item)
            note_here = note is not None and (item in actor.inventory
                                              or (str(note.get("location")) == actor.location
                                                  and self._note_carrier(item) is None))
            if (item not in actor.inventory and self.item_locations.get(item) != actor.location
                    and not note_here):
                _present, held = self._present_items(actor)
                candidates = sorted(set(self._takeable_here(actor)) | set(held))
                valid = "; ".join(self._tool_call_json("trash", {"item": name})
                                  for name in candidates)
                suffix = f" Available items and valid calls: {valid}." if valid else \
                    "There is no item here or in your inventory to trash."
                raise ActionRejected(
                    f"Cannot trash '{item}': it is neither held nor at this location.{suffix}",
                    alternatives=[f"trash {name}" for name in candidates],
                    context={"item": item, "available_items": candidates})
            if item not in actor.inventory and item in self.fixed_items:
                self._reject_fixed_item(actor, item)
            return timedelta(seconds=3)
        return timedelta(seconds=3)

    def _read_rejection(self, actor: ActorState, item: str) -> ActionRejected:
        """Issue 39/40: a rejected `read` states the real situation — nothing
        here by that name, a prop with no readable body, or a readable thing
        that is simply not here — and offers only calls that will succeed."""
        readable_now = self._available_readables(actor)
        here, held = self._present_items(actor)
        here_line = f"你现在在{actor.location}，手里有：{', '.join(held) or '空'}。"
        if item in self.document_defs:
            # (c) readable, but neither held nor at this location.
            message = (f"「{item}」现在不在你这里：它不在你手上，也不在{actor.location}。"
                       f"这是件能读的东西——先弄清它现在在谁那里，或到它可能在的地方去。"
                       f"{here_line}")
            alternatives: list[str] = []
            reason = "readable_not_here"
        elif item in self.persistent_notes:
            # (c) a content record that is not yours to read where you stand:
            # either somebody is carrying it, or it lies elsewhere.
            # 票 101（E105）：被递出去的字条在收件人手上，说“在别处”会误导。
            carrier = self._note_carrier(item)
            if carrier is not None:
                message = (f"「{item}」现在在{carrier}手上：这张字条不在你手里，"
                           f"要读它得让他递给你。{here_line}")
                reason = "note_carried"
            else:
                message = (f"「{item}」现在不在{actor.location}：这张字条留在别处，"
                           f"只能到它所在的地方读。{here_line}")
                reason = "note_not_here"
            alternatives = []
        elif item in here or item in held:
            # (b) physically here, but it carries no readable text.
            objective = self._observed_objective(actor, item)
            seen = (f"你看见过它，这里是它的客观描述（系统所记，不是任何人的推测）："
                    f"{objective}" if objective else "")
            fixed = item in self.fixed_items
            message = (f"「{item}」没有可读的正文：它是一件实物，不是写着字的文书，读不出内容。"
                       f"{here_line}"
                       f"{'它固定在这里，拿不走，只能就地看着、问起或使用。' if fixed else '你可以先把它拿上，或带在身上去问知道的人。'}"
                       f"{seen}")
            alternatives = []
            if item in here and not fixed:
                alternatives.append(f"take {item}")
            if item in held:
                alternatives.append(f"place {item}")
                others = [other.id for other in self.actors.values()
                          if other.id != actor.id and other.location == actor.location]
                if others:
                    alternatives.append(f"give {item} to {others[0]}")
            reason = "present_without_body"
        elif self.aware_of(actor.id, item):
            # (a) a thing the actor knows of, but not readable and not here.
            objective = self._observed_objective(actor, item)
            seen = (f"你看见过它，这里是它的客观描述（系统所记，不是任何人的推测）："
                    f"{objective}" if objective else "")
            message = (f"「{item}」不是能读的文书，现在也不在{actor.location}，不在你手上。"
                       f"{here_line}{seen}")
            alternatives = []
            reason = "known_not_readable_not_here"
        else:
            # (a) nothing here by that name. Ticket 63: a location-level
            # notice board (教学楼正门内侧公告栏 / 公告栏底下的过期通知) is not
            # a registered document, so with nothing readable here the old
            # answer was a dead end ("你现在能读的：无"). The rejection must
            # still name a real next step: what can be taken here, who is here
            # to ask, or where one can go.
            message = (f"这里没有「{item}」这样一件能读的文书。{here_line}"
                       f"你现在能读的：{', '.join(readable_now) or '无'}。")
            alternatives = [f"read {name}" for name in readable_now]
            if not alternatives:
                alternatives = self._fallback_next_actions(actor)
                if alternatives:
                    message += ("这里没有可读的正文——若是贴在地方上的公告栏或通知，"
                                "要问张贴的人，或到张贴的地方去看："
                                + "；".join(alternatives) + "。")
            reason = "absent"
        return ActionRejected(message, alternatives=alternatives,
                              context={"item": item, "reason": reason,
                                       "readable_now": readable_now,
                                       "held": held, "items_here": here})

    def _unwritable_on_rejection(self, actor: ActorState, target: str) -> ActionRejected:
        """`leave_note on=<X>` when X is neither a writable document at hand
        nor a blank sheet you can write on (票 101 / E105b).

        两种可写目标按类型分派：有正文的文书 → 批注（`document_annotated`）；
        无正文的白纸 → 一份可读、可递的文稿（`note_left` + `note-<作者>-<n>`）。
        回执只列真的能写的东西，不再拿无关文书（窗口 6 18:48 的
        `give 2013年邻里撤离通知书` 推荐）当替代。"""
        documents = [name for name in self._available_readables(actor)
                     if name in self.document_defs]
        sheets = self._writable_sheets(actor)
        writable = documents + [name for name in sheets if name not in documents]
        lead = (f"这里没有可以在上面写字的文书「{target}」。"
                if target in self.document_defs
                else f"「{target}」不是手边能写字的一张纸，也不是这里的文书。")
        holder = next((other.id for other in self.actors.values()
                       if target in other.inventory), None)
        where = self.item_locations.get(target)
        if holder is not None:
            lead += f"它现在在{holder}手上。"
        elif where is not None:
            lead += f"它现在在{where}，不在这里。"
        return ActionRejected(
            f"{lead}手边能写的：{', '.join(writable) or '没有'}；要留一张新字条就别写 on。",
            context={"document": target, "writable_documents": documents,
                     "writable_sheets": sheets})

    def _fallback_next_actions(self, actor: ActorState) -> list[str]:
        """Real, executable next actions when a `read` has nothing readable to
        offer (ticket 63): what is physically here, who is here to ask, and
        where one can still go. Deterministic and capped; every entry can be
        submitted as-is (the caller converts `take`/`speak to`/`move to`)."""
        actions = [f"take {item}" for item in self._takeable_here(actor)]
        actions += [f"speak to {person}" for person in self._present_others(actor)]
        actions += [f"move to {place}" for place in self._reachable_open(actor)]
        return actions[:3]

    def _observed_objective(self, actor: ActorState, item: str) -> str | None:
        """The objective description the actor already has for `item`.

        Ticket 49 fallback: when a thing was seen but memory shows no body,
        the system layer hands over the stored objective text instead of
        letting the model guess. A thing never seen returns None — the world
        never invents a description."""
        entry = actor.observed.get(item)
        if entry is None:
            return None
        return str(entry.get("objective") or "") or None

    def _consume_unit(self, actor: ActorState, sheet: str, left: int) -> int:
        """把一张纸写成文稿之后，这张纸还剩几张（票 113）。

        `left` 是提交时按容量定下的余数（随事件走，所以重放不需要猜）。
        `left > 0`：纸还是纸，位置与持有关系都不动；`left == 0`：这张纸用完了，
        它从此就是那份文稿——原地的库存出账，持有者手上也不再是空白纸。"""
        if left > 0:
            self.item_counts[sheet] = left
            return left
        self.item_counts.pop(sheet, None)
        for other in self.actors.values():
            other.inventory.discard(sheet)
        self.item_locations.pop(sheet, None)
        return 0

    def _complete(self, actor_id: str, payload: Mapping[str, Any]) -> None:
        if actor_id not in self.actors:
            # Defensive: a despawned extra's leftover job must not crash the
            # clock — the event stands (it happened), nothing mutates.
            return
        a = self._actor(actor_id); kind = payload["action"]
        if kind == "move":
            a.location = str(payload["target"])
            a.reading_dwell.clear()   # leaving voids the stay-read clock
        elif kind == "text":
            target_id = str(payload["target"])
            if target_id not in self.actors:
                # A text addressed to a despawned extra goes nowhere: the
                # stranger has left the scene (V4-CAST §1 zero-memory rule).
                return
            target = self.actors[target_id]
            target.inbox.append({"from": actor_id, "text": str(payload["text"]), "sent_at": self.now.isoformat()})
        elif kind == "take":
            item = str(payload["item"])
            if self.item_locations.get(item) != a.location:
                # Defensive: two takes queued in the same tick (both valid at
                # submit, ticket 75) complete back to back; the first empties
                # the spot, the second must not crash the clock — the
                # completion event stands, nothing mutates (mirror of the
                # despawned-extra returns above). 票 98（E102）：提交期已经不让
                # 第二个人拿同一件，所以这条只剩恢复旧检查点时才走得到；条件收紧
                # 到“还在我这里”，别人的东西不会被隔空拿到手上。
                return
            a.inventory.add(item); del self.item_locations[item]
        elif kind == "place":
            item = str(payload["item"]); a.inventory.remove(item)
            note = self.persistent_notes.get(item)
            if note is not None:
                # 票 101（E105）：一张字条放下来就是“留在这里的纸”，不当作
                # 未登记的物件记进 item_locations（它没有客观描述，也没有 item 行）。
                note["location"] = a.location
            else:
                self._require_described(item)
                self.item_locations[item] = a.location
        elif kind == "read":
            # Ticket 49: a manual read also settles the stay-read book-keeping
            # so the same document is never read twice in one stay.
            a.read_entities.add(str(payload["item"]))
            a.reading_dwell.pop(str(payload["item"]), None)
        elif kind == "leave_note":
            # Ruling 2026-09-22: a note is a room message attribute, not an
            # item — it joins the location's notes list and burns when read.
            # Ticket 88: `persist: true` is the other kind of written record —
            # a stable-id entity that stays where it was left and can be read
            # again. The id was assigned at submit (so the started event and the
            # tool receipt can name it); replay rebuilds it from note_left.
            # 票 95（E98）：`on` 是第三种写法——往既有文书的 annotations 追加
            # 一条，不覆盖别人写的；文书本身不动，也不产生字条。
            text = str(payload["text"])
            if payload.get("on") and str(payload["on"]) in self.document_defs:
                document = str(payload["on"])
                self.document_defs[document].setdefault("annotations", []).append(
                    {"text": text, "by": actor_id,
                     "time": self.now.isoformat()})
            elif payload.get("persist"):
                note_id = str(payload["note"])
                self.persistent_notes[note_id] = {
                    "id": note_id, "author": actor_id, "location": a.location,
                    "text": text, "left_at": self.now.isoformat()}
                sheet = str(payload.get("on") or "")
                if sheet:
                    # 票 113（112 §E1）：写一张就少一张。一沓纸（种子 `count: N`）
                    # 写完之后仍是原来那张可用的纸（在持有者手上或原地），别人拿
                    # 去还能写；拿走最后一张时这沓就空了——那份文稿从一开始就是另一样
                    # 东西（作者手上的文稿实体），不是纸“变成”了它。
                    self._consume_unit(a, sheet, int(payload.get("count_left", 0)))
                    a.inventory.add(note_id)
            else:
                note = {"author": actor_id, "text": text,
                        "left_at": self.now.isoformat()}
                self.locations[a.location].notes.append(note)
        elif kind == "trash":
            item = str(payload["item"])
            self.item_locations.pop(item, None)
            self.item_counts.pop(item, None)
            a.inventory.discard(item)
            self.persistent_notes.pop(item, None)
        elif kind == "give":
            item = str(payload["item"]); target = self._actor(str(payload["target"]))
            note = self.persistent_notes.get(item)
            if note is not None:
                # 票 101（E105）：递一张字条就是递那张纸——持有关系与 item 一致
                # （进收件人的背包），位置随之更新，所以 replay 不用第三个概念。
                if item in a.inventory:
                    a.inventory.discard(item)
                target.inventory.add(item)
                note["location"] = target.location
            else:
                if item in a.inventory:
                    a.inventory.remove(item)
                elif self.item_locations.get(item) == a.location:
                    # Ticket 63: an item at the actor's own location was handed
                    # over in one motion (take-then-give); it leaves the location.
                    self.item_locations.pop(item, None)
                else:
                    # 票 98（E102）：同一件东西已经在别处/别人手上（旧检查点里可能还
                    # 排着第二次 give），这条完成事件成立，但不能再凭空给收件人一件。
                    target = None
                if target is not None:
                    target.inventory.add(item)
        elif kind == "sleep": a.sleeping = False
        if payload.get("sleep"):
            a.sleeping = False
        a.busy_until = None
        a.current_action = None

    def _commit_interaction(self, actor_id: str, payload: Mapping[str, Any], cause: int) -> Event:
        actor = self._actor(actor_id)
        kind = str(payload["action"])
        if (kind == "leave_note" and payload.get("on")
                and str(payload["on"]) in self.document_defs):
            # 票 95（E98）：写进既有文书不是字条事件——它产生既有的
            # `document_annotated`（同地点可见），内容进入该文书的 annotations。
            # 票 101（E105b）：on 指向一张白纸时不是批注，而是下文 `note_left` 分支。
            return self._commit("document_annotated", actor_id, {
                "document": str(payload["on"]),
                "location": actor.location,
                "annotation": str(payload.get("text", ""))}, cause)
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
            definition = self.readable_body(document) or {}
            return {"document": document,
                    "title": definition.get("title", document),
                    "content": definition.get("content", ""),
                    "annotations": [dict(entry)
                                    for entry in definition.get("annotations", [])]}
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
            payload = {"location": actor.location,
                       "text": str(intention.get("text", ""))}
            if intention.get("on"):
                payload["on"] = str(intention.get("on"))
            if intention.get("persist"):
                payload["persist"] = True
                payload["note"] = str(intention.get("note", ""))
            if intention.get("count_left") is not None:
                # 票 113：写完之后这张纸上还剩几张——提交时定下、随事件走，
                # 所以回执、重放与中途检查点看到的是同一个数。
                payload["count_left"] = int(intention["count_left"])
            return payload
        if kind in {"trash"}:
            # these payloads carry no "target" key; the item is carried so a
            # replay can rebuild what it removed (ticket 88: a trashed
            # persistent note must not stay readable after replay).
            return {"target": "", "item": str(intention.get("item", ""))}
        return {"target": str(intention["target"]) if "target" in intention else ""}

    def _next_note_id(self, actor_id: str) -> str:
        """A stable, addressable id for a persistent note (ticket 88).

        `note-<author>-<serial>` is unique for the whole world, never reused
        across a checkpoint, and readable as a `read` target."""
        note_id = f"note-{actor_id}-{self._note_serial}"
        self._note_serial += 1
        return note_id

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

    def remove_extra(self, name: str, *, reason: str = "left") -> None:
        """Destroy an extra: it leaves the scene with zero memory.

        Any jobs it left in the clock queue (a message still in flight, a
        duration action still running) are cancelled with it — a despawned
        stranger must not crash the clock when its turn comes (首验日 v2 事故).
        ``reason`` rides on the visible ``extra_removed`` event (ticket 42):
        co-located characters must be able to tell a mid-conversation
        interruption (``idle``) from a natural departure.

        E84 (报 81 §5): what the stranger is carrying stays in the world. It
        used to leave with it — 陈阿姨 took 校报草稿 at 12:52 and the idle
        despawn at 13:07 deleted the item outright (no event, no location,
        the owner never learned). Every carried item is now put down at the
        extra's last location with its own visible ``item_dropped`` event
        *before* ``extra_removed``, so the invariant "an item is always either
        held by someone or at a location" holds at every prefix of the log and
        replay rebuilds the same result."""
        if name in self.actors and self.actors[name].role == "extra":
            extra = self.actors[name]
            for item in sorted(extra.inventory):
                self._commit("item_dropped", name,
                             {"item": item, "location": extra.location,
                              "reason": str(reason)},
                             None)
                self.item_locations[item] = extra.location
            extra.inventory.clear()
            self._commit("extra_removed", name,
                         {"location": extra.location, "reason": str(reason)},
                         None)
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
        if kind in {"wait_woken", "private_wake", "private_wake_failed", "reminder_due"}:
            return {str(actor)} if actor is not None else set()
        if kind == "document_read":
            # Content privacy: only the reader sees the text.
            return {str(actor)}
        if kind == "observed":
            # Ticket 49: the first-sight record is the actor's own memory row;
            # co-located people do not share it.
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
        if kind == "world_event":
            # 票 95（E97）：排程事件可以点名一个发生地点。有 `location` 时，
            # 只有当时在该地点的人（以及显式 target）看得见——一条“学生会
            # 办公室长桌上摊开了面核记录”不再是全场广播。没有 `location` 且
            # 没有 `target` 的仍按既有全局广播（校园公告、铃声、天气）。
            targets = payload.get("target")
            targets = (list(targets) if isinstance(targets, (list, tuple))
                       else [targets] if targets is not None else [])
            location = payload.get("location")
            if location is not None:
                visible = {x.id for x in self.actors.values()
                           if x.location == str(location)}
                return visible | {str(target) for target in targets}
            if targets:
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
        if kind == "item_dropped":
            # E84（报 81 §5）：物品落在原处是现场事实，同地的人都看得见。
            return self._co_located(str(actor))
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
        # 票 95（E98）：批注的正文与文书内容同一条隐私线——同地点的人只看见
        # “谁在文书上写了字”，正文要自己 read 那份文书才看得到。
        if (e.kind == "document_annotated" and observer is not None
                and observer != e.actor):
            payload.pop("annotation", None)
        return {"id": e.id, "time": e.time.isoformat(), "kind": e.kind, "actor": e.actor, "payload": payload, "cause": e.cause}

    def _actor(self, actor_id: str) -> ActorState:
        if actor_id not in self.actors: raise ActionRejected(f"unknown actor: {actor_id}")
        return self.actors[actor_id]

    def _resolve_person(self, actor: ActorState, query: Any,
                        seen_here: Iterable[str] | None = None
                        ) -> tuple[str | None, str | None]:
        """Name resolution for person arguments (V4-AGENT-INTERFACE T4).

        Candidates are the actor's own world: contact formal names, their
        private aliases, whoever is physically present, and — ticket 46 —
        whoever this turn's perception snapshot saw here, so a name the
        decision could see never comes back as `unknown name`. Exact match
        wins silently; a fuzzy hit is used with a teaching note; ambiguity or
        nothing is a rejection."""
        from .kb import normalize, resolve_name
        formal_names = set(actor.known_contacts)
        formal_names.update(other.id for other in self.actors.values()
                            if other.id != actor.id and other.location == actor.location)
        if seen_here:
            formal_names.update(str(name) for name in seen_here if name != actor.id)
        formal, formal_note = resolve_name(query, formal_names)
        if formal is not None and formal_note is None:
            return formal, None

        # An alias is verified only because this actor explicitly recorded it
        # for one formal contact. Ticket 48 (identity-preserving resolution):
        # resolve the actor's own nicknames as a GROUP — when every matching
        # nickname denotes the same person (a phone number plus a description,
        # say), that is one intended recipient, not an ambiguity to reject. A
        # unique fuzzy hit among one person's nicknames can safely correct to
        # that same identity; arbitrary formal-name substrings still cannot.
        nickname_hits: dict[str, list[str]] = {}
        exact_nickname = False
        for nickname, owner in actor.contact_aliases.items():
            hit, _note = resolve_name(query, [nickname])
            if hit is None:
                continue
            nickname_hits.setdefault(owner, []).append(str(nickname))
            if normalize(nickname) == normalize(query):
                exact_nickname = True
        if len(nickname_hits) == 1:
            owner, matched = next(iter(nickname_hits.items()))
            if exact_nickname and len(matched) == 1:
                return owner, None
            return owner, (f"resolved '{query}' to your contact '{owner}' by the "
                           "nickname(s) you recorded — use the exact formal name or "
                           "nickname next time")
        if len(nickname_hits) > 1:
            listed = " / ".join(sorted(nickname_hits))
            return None, f"ambiguous name '{query}': {listed}"
        note = formal_note or f"unknown name '{query}'"
        if formal is not None:
            note = (f"unverified partial name '{query}'; use an exact formal name or "
                    "a registered personal nickname")
        return None, note

    def _canonicalize_persons(self, actor: ActorState, intention: Intention,
                              seen_here: Iterable[str] | None = None) -> Intention:
        """Rewrite a single-target person name to its formal id (T4/T3 裁决).

        ``text`` needs a contact row to go through; ``give`` is a co-presence
        action, so only someone physically here can be offered. A name that
        resolves to nobody is still a rejection — the actor learns it
        mis-named someone — and the candidate list it carries is the set that
        would actually succeed for this action (ticket 46: a distant contact
        must not be offered as a `give` target). Returns the intention
        unchanged when nothing needs resolving."""
        args = dict(intention.args)
        changed = False
        for key in ("target",):
            query = args.get(key)
            if not isinstance(query, str) or not query.strip():
                continue
            resolved, note = self._resolve_person(actor, query, seen_here)
            if resolved is None:
                # Ticket 46 / issue 39: the list must come from this judgement
                # and every entry must succeed if it is resubmitted — a contact
                # is always textable, but a hand-over needs someone here.
                candidates = (self._message_targets(actor) if intention.kind == "text"
                              else self._present_others(actor))
                context = {key: query, "name_resolution": True,
                           "recipient_candidates": candidates}
                if _unknown_name_note(note):
                    # Ticket 48: the actor named someone by a KB nickname/
                    # number that denotes nobody it can reach — the answer
                    # must preserve the recipient intent.
                    context["unknown_recipient"] = True
                message = str(note)
                hint = self._unreachable_note(query)
                if hint:
                    message = f"{message} {hint}"
                raise ActionRejected(message, context=context)
            if resolved != query:
                args[key] = resolved
                changed = True
        if not changed:
            return intention
        return Intention(intention.actor, intention.kind, args,
                         intention.expected_version, inner=intention.inner,
                         interrupt=intention.interrupt,
                         uninterruptable=intention.uninterruptable)

    def _canonicalize_companions(self, actor: ActorState, intention: Intention,
                                 seen_here: Iterable[str] | None = None) -> Intention:
        """Resolve `move`'s `with` names to formal actor ids (ticket 95, E96).

        Same T4 resolution as `text`/`give`: a nickname that uniquely matches
        one candidate is canonicalized before validation, so the gate and the
        committed event agree on who was brought along. An unknown or
        ambiguous name is a rejection carrying the people who are actually
        here (the only ones that could succeed).

        票 98（E101）：空项/纯空白项先过滤，重复项去重；过滤后为空就是**一个人走**
        ——`with` 整个键被去掉，与“没写 with”完全同一条路径。窗口 5 的 76 条
        “with 里有一个空名字”不是模型写错，而是它在找“独自走”的表达法：空值只能
        等于未提供，不能把唯一可行的走法判成错。"""
        entries = intention.args.get("with")
        if not isinstance(entries, (list, tuple)):
            return intention
        args = dict(intention.args)
        resolved: list[str] = []
        for entry in entries:
            query = str(entry).strip()
            if not query:
                continue
            formal, note = self._resolve_person(actor, query, seen_here)
            if formal is None:
                raise ActionRejected(f"{str(note).rstrip('。')}。{WALK_ALONE_HINT}",
                                     context={"with": query, "name_resolution": True,
                                              "companion_candidates": self._present_others(actor)})
            resolved.append(formal)
        resolved = list(dict.fromkeys(resolved))
        if not resolved:
            if not entries:
                return intention
            args.pop("with", None)
        elif resolved == list(entries):
            return intention
        else:
            args["with"] = resolved
        return Intention(intention.actor, intention.kind, args,
                         intention.expected_version, inner=intention.inner,
                         interrupt=intention.interrupt,
                         uninterruptable=intention.uninterruptable)

    def _stranger_token_blocked(self, actor: ActorState, volume: str) -> str | None:
        """Why `陌生人` cannot be called on right now, or None when it can
        (V4-AGENT-INTERFACE §2: an open place, normal volume)."""
        if volume == "whisper":
            return "whisper"
        if not self.locations[actor.location].open:
            return "closed"
        return None

    def pool_entry_for_alias(self, location_id: str, name: str) -> Mapping[str, Any] | None:
        """The extra-pool entry of `location_id` that declares `name` as an
        alias (ticket 88), or None.

        A seed may register a location extra with `aliases:` (e.g.
        `aliases: [老板娘]`) so that naming that role in `speak.to` brings that
        character, not a random passer-by from the same pool. An alias is a
        name for an unspawned character only: once someone is physically here
        (or a real actor carries that name), ordinary person resolution wins.
        """
        location = self.locations.get(location_id)
        if location is None:
            return None
        for entry in location.extras:
            aliases = entry.get("aliases") or ()
            if isinstance(aliases, str):
                aliases = (aliases,)
            if name in {str(alias) for alias in aliases}:
                return entry
        return None

    def _canonicalize_speech(self, actor: ActorState, intention: Intention,
                             seen_here: Iterable[str] | None = None) -> Intention:
        """Per-addressee delivery plan for one utterance (ticket 46).

        Every addressee is resolved against the actor's own world **plus this
        turn's perception snapshot** (so a name the decision saw always
        resolves), then kept only if the world can still reach them. An
        addressee who has left meanwhile, or a name that resolves to nobody,
        is recorded on the committed action as ``undelivered`` with its reason
        and reported back in the tool result; the other addressees keep the
        words. One bad recipient never voids the sentence (d1-am turn 233:
        辅导员's line to 班长, 下棋大爷 and 陈默 was dropped whole because
        下棋大爷 had walked off).

        `visible_to` stays authoritative: the effective `to` is what the
        kernel commits and :meth:`_hearing_actors` still derives the audience
        from live locations, so nobody is ever delivered to out of a
        snapshot."""
        args = dict(intention.args)
        volume = str(args.get("volume", "normal"))
        here = {other.id for other in self.actors.values()
                if other.id != actor.id and other.location == actor.location}
        requested = [str(entry) for entry in args.get("to") or ()]
        delivered: list[str] = []
        undelivered: list[dict[str, str]] = []
        unresolved: list[str] = []
        known: list[str] = []
        # Ticket 88: names answered by a location's extra pool (see
        # `pool_entry_for_alias`) route to the extras machinery exactly like
        # the room token `陌生人`, but remember which alias was named.
        alias_hits: list[str] = []
        strangers = False
        stranger_reason: str | None = None
        for name in requested:
            if name == "陌生人":
                # Ask-the-room token (ticket 22): routed to the extras
                # machinery, never name-resolved.
                reason = self._stranger_token_blocked(actor, volume)
                if reason is None:
                    strangers = True
                else:
                    stranger_reason = reason
                    undelivered.append({"name": name, "reason": reason})
                continue
            resolved, note = self._resolve_person(actor, name, seen_here)
            if resolved is None and self.pool_entry_for_alias(actor.location, name) is not None:
                reason = self._stranger_token_blocked(actor, volume)
                if reason is None:
                    alias_hits.append(name)
                    continue
                why = ("耳语不会传给尚未出现的路人" if reason == "whisper"
                       else "当前地点封闭，未出场的人听不到这里的话")
                raise ActionRejected(
                    f"「{name}」现在不在这里：{why}。"
                    f"可以改成对这里已登记的路人搭话："
                    f"{self._tool_call_json('speak', {'to': ['陌生人'], 'text': args.get('text', ''), 'volume': 'normal'})}，"
                    "或直接在开放地点正常音量说话。")
            if resolved is None:
                unresolved.append(note or f"unknown name '{name}'")
                undelivered.append({"name": name, "reason": "unknown"})
                continue
            known.append(resolved)
            if resolved in here:
                if resolved not in delivered:
                    delivered.append(resolved)
            else:
                undelivered.append({
                    "name": resolved,
                    "reason": "left" if seen_here and resolved in seen_here else "absent"})
        if requested and not delivered and not strangers and not known and not alias_hits:
            # Nothing in the list exists: no addressee survived resolution, so
            # there is no partial delivery to make. Keep the rejection (an
            # unknown name is never silently rewritten, and the words are not
            # spoken to the room instead) — the actor learns who it can name.
            if requested == ["陌生人"]:
                # The room token alone keeps its world rule: a passer-by cannot
                # be called behind a closed door or by a whisper.
                why = ("耳语不会传给尚未出现的路人" if stranger_reason == "whisper"
                       else "当前地点封闭，路人听不到这里的话")
                raise ActionRejected(
                    f"{why}；未发起搭话。请在开放地点用 "
                    f"{self._tool_call_json('speak', {'to': ['陌生人'], 'text': args.get('text', ''), 'volume': 'normal'})}。")
            unknown = [f"unknown name '{name}'" for name in requested if name != "陌生人"]
            notes = unresolved or unknown
            if stranger_reason is not None:
                notes = notes + ["耳语不会传给尚未出现的路人" if stranger_reason == "whisper"
                                 else "当前地点封闭，路人听不到这里的话"]
            raise ActionRejected(
                f"unknown or ambiguous speak recipient: {'; '.join(notes)}",
                context={"unknown": notes, "name_resolution": True,
                         "recipient_candidates": self._present_others(actor),
                         "query": requested[0] if requested else "",
                         "unknown_recipient": any(_unknown_name_note(note)
                                                  for note in unresolved)})
        if requested or "to" in args:
            args["to"] = delivered + (["陌生人"] if strangers else []) + alias_hits
        if undelivered:
            args["undelivered"] = undelivered
        return Intention(intention.actor, intention.kind, args,
                         intention.expected_version, inner=intention.inner,
                         interrupt=intention.interrupt,
                         uninterruptable=intention.uninterruptable)

    def _present_others(self, actor: ActorState) -> list[str]:
        """People physically here with the actor, never the global roster.

        The candidate list for a presence-dependent action (`speak` sentence
        delivery, `give` hand-over) uses exactly this set: a distant contact
        could be named, but the words would not land and the object could not
        be handed over, so offering one would be a suggestion that cannot
        succeed (ticket 46: the d1-am 11:30 speak rejection offered 唐小岚 and
        宿管阿姨, who were not in the room)."""
        return sorted(other.id for other in self.actors.values()
                      if other.id != actor.id and other.location == actor.location)

    def _message_targets(self, actor: ActorState) -> list[str]:
        """Expose only addressable people for `text`: a known contact or
        someone here — every one of them can be messaged now, wherever they
        stand. The world does not reveal its roster."""
        return sorted({other.id for other in self.actors.values()
                       if other.id != actor.id and (
                           other.id in actor.known_contacts or other.location == actor.location)})

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

    def pending_notes(self) -> list[dict[str, Any]]:
        """Still-unread room notes, for the run-end report (ticket 44).

        A note is pending while it sits in a location's notes list; it leaves
        that list (and this report) only when a non-author entrant consumes it.
        Mechanism choice: the smallest observable signal for an undelivered
        note is to record it in the run outcome at the endpoint — no new event
        (note_read already exists), no clock-side reminder. A future run that
        leaves a note standing shows ``outcome["unread_notes"]``; the d1-am
        artifact's 林瑶→陈默 借条 (note_left #645, never read) is exactly the
        case this makes visible."""
        return [{"location": location_id,
                 "author": note.get("author"),
                 "left_at": note.get("left_at"),
                 "text": note.get("text")}
                for location_id, location in sorted(self.locations.items())
                for note in location.notes]

    def _present_items(self, actor: ActorState) -> tuple[list[str], list[str]]:
        here = sorted(item for item, location in self.item_locations.items()
                      if location == actor.location)
        return here, sorted(actor.inventory)

    def _notes_here(self, actor: ActorState) -> list[dict[str, Any]]:
        """Persistent notes lying at the actor's location (ticket 88).

        Perceived as ids, never as text: a note's content is read with `read`.
        Burn-on-read notes are deliberately absent — they are not entities and
        never belong to an actor who was already in the room."""
        return [{"id": str(note.get("id")), "author": note.get("author"),
                 "left_at": note.get("left_at")}
                for note in sorted(self.persistent_notes.values(),
                                   key=lambda row: str(row.get("id")))
                if str(note.get("location")) == actor.location
                and self._note_carrier(str(note.get("id"))) is None]

    def _takeable_here(self, actor: ActorState) -> list[str]:
        """What is physically here AND may be picked up (ticket 83)."""
        return [item for item in self._present_items(actor)[0]
                if item not in self.fixed_items]

    def _item_claimant(self, actor: ActorState, item: str) -> str | None:
        """Who is already moving `item` out of its place right now, or None.

        票 98（E102）：一件东西的归属只在**完成时**写进世界，所以 `item_locations`
        回答不了“它现在还是不是没人拿”——同一个 tick 里的两次提交都看到它在桌上。
        在途状态就是各自 actor 的 `current_action`/`pending`（随检查点保存在 actor
        上）。能把它从原地挪走的动作有两个：`take`，以及 `give` 的“就地拿起再递出”
        分支（那时东西还在原地、不在发起者背包里）——两个都算占用。
        """
        for other in self.actors.values():
            if other.id == actor.id:
                continue
            for slot in (other.current_action, other.pending):
                payload = (slot or {}).get("payload") or {}
                if str(payload.get("item")) != item:
                    continue
                action = payload.get("action")
                if action == "take":
                    return other.id
                if action == "give" and item not in other.inventory:
                    return other.id
        return None

    def _take_rejection(self, actor: ActorState, item: str,
                        held: list[str]) -> ActionRejected:
        """Where the thing actually is, when it is not here to take (E102).

        The old line said only “这里没有「X」可拿”, which in window 5 07:23
        (`give 一份餐食`) and 17:57 (`take 一份晚饭`) hid the real fact —
        someone present had just picked it up. A taker needs to know whether
        it left the world or moved into somebody's hands."""
        holder = next((other.id for other in self.actors.values()
                       if item in other.inventory), None)
        where = self.item_locations.get(item)
        if holder is not None:
            message = f"「{item}」已经不在{actor.location}了：现在在{holder}手上。"
        elif where is not None:
            message = f"「{item}」现在在{where}，不在这里。"
        elif self._is_entity(item):
            message = f"「{item}」现在不在世上任何地方了（已经被拿走或销毁）。"
        else:
            # 从来没登在世上的一件东西（票 60 的内部陈设、票 65 的绳子）：
            # 不能说它“被拿走或销毁”了——那是凭空给世界添了一段历史。
            message = f"这里没有「{item}」可拿。"
        takeable = self._takeable_here(actor)
        message += (f"这里能拿的：{', '.join(takeable) or '没有'}。"
                    f"你拿着的：{', '.join(held) or '没有'}。")
        return ActionRejected(
            message,
            alternatives=[f"take {present}" for present in takeable],
            context={"item": item, "held_by": holder, "location": where,
                     "takeable_here": takeable})

    def _reject_fixed_item(self, actor: ActorState, item: str) -> None:
        """Ticket 83: a 固定陈设 (shelf, chest freezer, the 关东煮 pot) is
        present and described, but it never enters an inventory and never
        leaves its place — so take, the at-hand branch of give, and trash all
        refuse it here instead of moving it. The reason is the seed's
        `fixed_reason`, or a plain statement that it is a fixture."""
        reason = (self.fixed_items[item] or "这是固定陈设").rstrip("。；，")
        takeable = self._takeable_here(actor)
        raise ActionRejected(
            f"「{item}」拿不走：{reason}。它一直在{actor.location}，只能就地看着、"
            f"问起或使用。这里能拿的：{', '.join(takeable) or '没有'}。",
            alternatives=[f"take {name}" for name in takeable],
            context={"item": item, "reason": "fixed_fixture", "fixed_reason": reason,
                     "takeable_here": takeable})

    def _reachable(self, actor: ActorState) -> list[str]:
        return sorted(target for (source, target) in self.routes if source == actor.location)

    def _unreachable_note(self, name: Any) -> str | None:
        """Ticket 66 — the seed's authored alternative for an unreachable name.

        A name a role treats as a target/contact may be neither a reachable
        location nor an addressable person (李阿姨 is an off-campus neighbour,
        李阿姨家 a door-plate, 305宿舍 a room inside a modelled building). The
        seed declares each with a reason and an executable alternative (who to
        ask / where to go / which verb); the rejection appends both so the
        three routes never all dead-end. Matching is the KB's normalization,
        so a shorter query ("305") still finds its entry."""
        from .kb import normalize
        text = normalize(name)
        if not text or not self.unreachable_targets:
            return None
        normalized = {key: normalize(key) for key in self.unreachable_targets}
        exact = [key for key, needle in normalized.items() if needle == text]
        if exact:
            match = exact[0]
        else:
            # A query may extend the name ("老家属院地下室") — take the most
            # specific key it contains; or the query may be a prefix ("305")
            # — take the least over-reaching key containing it. Nesting like
            # 李阿姨/李阿姨家 never mis-resolves because exact wins first.
            contained = [(len(needle), key) for key, needle in normalized.items()
                         if needle and needle in text]
            if contained:
                match = max(contained)[1]
            else:
                covering = [(len(needle), key) for key, needle in normalized.items()
                            if needle and text in needle]
                if not covering:
                    return None
                match = min(covering)[1]
        entry = self.unreachable_targets[match]
        reason = str(entry.get("reason", "")).strip()
        hint = str(entry.get("hint", "")).strip()
        return " ".join(part for part in (reason, hint) if part) or None

    def _reachable_open(self, actor: ActorState) -> list[str]:
        return sorted(target for (source, target) in self.routes
                      if source == actor.location and self.locations[target].open)

    def _available_readables(self, actor: ActorState) -> list[str]:
        """Readable entities (documents, or persistent notes) that are
        currently held or here — the only reads a suggestion may offer."""
        return sorted(entity for entity in
                      set(self.document_defs) | set(self.persistent_notes)
                      if self.available_now(actor.id, entity))

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
