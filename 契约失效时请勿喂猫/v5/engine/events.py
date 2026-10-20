"""P5：事件。世界的账本，不是任何人的知识。

事件只保存"应用了哪些原子效果"，所以重放 = 在初始世界上重演原子效果，
并逐事件比对摘要。事件本身永不进入任何心智；进心智的只有投递出来的记忆文本。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .core import World, apply_atom


@dataclass(frozen=True)
class Event:
    id: int
    at: int
    kind: str                      # intent / refused / world
    actor: str | None
    what: str
    atoms: tuple[dict[str, Any], ...] = ()
    note: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id, "at": self.at, "kind": self.kind,
            "actor": self.actor, "what": self.what,
            "atoms": [dict(a) for a in self.atoms], "note": dict(self.note),
        }

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> "Event":
        return cls(id=row["id"], at=row["at"], kind=row["kind"], actor=row["actor"],
                   what=row["what"], atoms=tuple(row.get("atoms", ())),
                   note=row.get("note", {}))


class EventLog:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self):
        return iter(self.events)

    def append(self, event: Event) -> Event:
        self.events.append(event)
        return event

    def next_id(self) -> int:
        return len(self.events) + 1

    def to_json(self) -> list[dict[str, Any]]:
        return [e.to_json() for e in self.events]

    @classmethod
    def from_json(cls, rows: list[dict[str, Any]]) -> "EventLog":
        log = cls()
        for row in rows:
            log.append(Event.from_json(row))
        return log


class ReplayMismatch(AssertionError):
    pass


def replay(build_world, log: EventLog) -> World:
    """在初始世界上重演事件，并逐事件比对摘要。

    `build_world()` 必须返回与开局完全相同的世界（含排程）。
    """
    world = build_world()
    for event in log:
        for atom in event.atoms:
            apply_atom(world, atom)
        recorded = event.note.get("digest_after")
        if recorded is not None and world.digest() != recorded:
            raise ReplayMismatch(
                f"事件 #{event.id}（{event.what}）重放后的世界与记录不一致"
            )
    return world


def dump_log(log: EventLog) -> str:
    return json.dumps(log.to_json(), ensure_ascii=False, sort_keys=True)
