"""P1–P4：实体、状态、包含、时间。

引擎的这一层不认识任何故事名词。所有世界状态都是数据，重放只依赖事件里的原子效果。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Entity:
    """P1：一个身份号 + 一个扁平类型标签 + 显示用名字。类型没有继承。"""

    id: str
    kind: str
    name: str
    prose: str = ""
    aliases: tuple[str, ...] = ()


class World:
    """世界状态：实体、状态键、包含树、时钟、排程、心智的记忆与知识。"""

    def __init__(self, start: int = 0):
        self.entities: dict[str, Entity] = {}
        self.state: dict[str, dict[str, Any]] = {}
        self.parent: dict[str, str] = {}
        self.clock: int = start
        self.schedule: list[list[Any]] = []
        self.seq: int = 0
        self.memory: dict[str, list[list[Any]]] = {}
        self.knowledge: dict[str, list[str]] = {}
        self.flags: dict[str, Any] = {}

    # ---- P1 实体
    def add(self, ent: Entity, *, parent: str | None = None,
            state: dict[str, Any] | None = None) -> None:
        if ent.id in self.entities:
            raise ValueError(f"实体重复：{ent.id}")
        self.entities[ent.id] = ent
        self.state[ent.id] = dict(state or {})
        if parent is not None:
            self.parent[ent.id] = parent
        if ent.kind == "person":
            self.memory.setdefault(ent.id, [])
            self.knowledge.setdefault(ent.id, [])

    def remove(self, eid: str) -> None:
        for child in [c for c, p in self.parent.items() if p == eid]:
            self.remove(child)
        self.entities.pop(eid, None)
        self.state.pop(eid, None)
        self.parent.pop(eid, None)
        self.memory.pop(eid, None)
        self.knowledge.pop(eid, None)

    def kind_of(self, eid: str) -> str | None:
        ent = self.entities.get(eid)
        return ent.kind if ent else None

    # ---- P2 状态
    def get(self, eid: str, key: str, default: Any = None) -> Any:
        return self.state.get(eid, {}).get(key, default)

    def set_state(self, eid: str, key: str, value: Any) -> None:
        self.state.setdefault(eid, {})[key] = value

    def unset_state(self, eid: str, key: str) -> None:
        self.state.get(eid, {}).pop(key, None)

    # ---- P3 包含
    def children(self, eid: str) -> list[str]:
        return [c for c, p in self.parent.items() if p == eid]

    def container(self, eid: str) -> str | None:
        return self.parent.get(eid)

    def ancestors(self, eid: str) -> list[str]:
        out, cur, seen = [], self.parent.get(eid), {eid}
        while cur is not None and cur not in seen:
            out.append(cur)
            seen.add(cur)
            cur = self.parent.get(cur)
        return out

    def place_of(self, eid: str) -> str | None:
        if self.kind_of(eid) == "place":
            return eid
        for anc in self.ancestors(eid):
            if self.kind_of(anc) == "place":
                return anc
        return None

    def in_place(self, eid: str) -> list[str]:
        place = self.place_of(eid)
        return [e for e in self.entities if e != eid and self.place_of(e) == place]

    # ---- P4 时间
    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def schedule_effect(self, when: int, effect: dict[str, Any]) -> None:
        self.schedule.append([when, self.next_seq(), effect])

    def next_due(self) -> int | None:
        return min((w for w, _, _ in self.schedule), default=None)

    def pop_next_due(self) -> list[Any] | None:
        """取出一个已到期的排程（按时间、序号）。一次只取一个，
        这样"哪个事件消费了哪条排程"在日志里是一对一的，重放才能逐事件对齐。"""
        due = [s for s in self.schedule if s[0] <= self.clock]
        if not due:
            return None
        entry = min(due, key=lambda s: (s[0], s[1]))
        self.schedule.remove(entry)
        return entry

    # ---- 审计用摘要
    def digest(self) -> str:
        payload = {
            "entities": {k: [v.kind, v.name, list(v.aliases), v.prose]
                         for k, v in sorted(self.entities.items())},
            "state": {k: dict(sorted(v.items())) for k, v in sorted(self.state.items())},
            "parent": dict(sorted(self.parent.items())),
            "clock": self.clock,
            "schedule": sorted([[w, json.dumps(e, ensure_ascii=False, sort_keys=True)]
                                for w, _, e in self.schedule]),
            "memory": {k: list(v) for k, v in sorted(self.memory.items())},
            "knowledge": {k: sorted(v) for k, v in sorted(self.knowledge.items())},
            "flags": dict(sorted(self.flags.items())),
        }
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


#: P9 的原子效果封闭集。任何状态变化都必须落在这里的一项上。
ATOM_OPS = ("set", "unset", "move", "create", "destroy", "remember", "know",
            "clock", "schedule", "unschedule", "flag")


def apply_atom(world: World, atom: dict[str, Any]) -> None:
    op = atom["op"]
    if op == "set":
        world.set_state(atom["e"], atom["k"], atom["v"])
    elif op == "unset":
        world.unset_state(atom["e"], atom["k"])
    elif op == "move":
        world.parent[atom["e"]] = atom["to"]
    elif op == "create":
        world.add(Entity(**atom["e"]), parent=atom.get("to"), state=atom.get("state"))
    elif op == "destroy":
        world.remove(atom["e"])
    elif op == "remember":
        world.memory.setdefault(atom["e"], []).append([atom["at"], atom["v"]])
    elif op == "know":
        world.knowledge.setdefault(atom["e"], []).append(atom["v"])
    elif op == "clock":
        world.clock = max(world.clock, atom["to"])
    elif op == "schedule":
        world.schedule.append([atom["at"], world.next_seq(), atom["effect"]])
    elif op == "unschedule":
        # 已到期的排程被"消费"也必须能被重放：否则重放的世界里它还挂着
        world.schedule = [row for row in world.schedule
                          if not (row[0] == atom["at"] and row[1] == atom["seq"])]
    elif op == "flag":
        world.flags[atom["k"]] = atom["v"]
    else:  # pragma: no cover - 原子集是封闭的
        raise ValueError(f"未知原子效果：{op}")
