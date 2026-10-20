"""智能体表面：把世界投影成一个角色"此刻知道什么"。

这一层不新增原始项——它只是 P6（感知投递）与 P7（心智）的一个视图：
- 一眼（glance）：不看也知道的——时间、所在、眼前、手里；
- 最近（recent）：他实际感知到的最近几条，逐字；
- 知识（beliefs）：他相信的事，可能错、可能旧；
- 检索（recall）与回想（flashback）：只在他的记忆里按字面找，找不到就是找不到。

硬规则：这里只许出现他自己感知过或相信的东西，不许出现世界真相。
"""

from __future__ import annotations

from typing import Any

from .core import World
from .render import describe, refer
from .resolve import visible


def clock_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def glance(world: World, actor: str) -> dict[str, Any]:
    ent = world.entities[actor]
    place = world.place_of(actor)
    return {
        "time": (f"{world.date} " if world.date else "") + clock_label(world.clock),
        "place": world.entities[place].name if place else "不知何处",
        "here": [describe(world, e, actor) for e in visible(world, actor)],
        "hands": [world.entities[c].name for c in world.children(actor)],
        "self": ent.identity or ent.prose,
    }


def recent(world: World, actor: str, n: int = 6) -> list[str]:
    rows = world.memory.get(actor, [])
    return [f"{clock_label(at)} {text}" for at, text in rows[-n:]]


def beliefs(world: World, actor: str) -> list[str]:
    return [says for _about, says in world.beliefs.get(actor, [])]


def recall(world: World, actor: str, query: str) -> list[str]:
    """按字面在自己的记忆里找。没有语义检索：找不到就是找不到。"""
    if not query:
        return []
    rows = world.memory.get(actor, [])
    return [f"{clock_label(at)} {text}" for at, text in rows if query in text]


def flashback(world: World, actor: str, about: str | None = None,
              since: int | None = None) -> list[str]:
    """回想某个人/物/地方：只能想起自己当时感知到的，想起来的是当时的说法。"""
    rows = world.memory.get(actor, [])
    keys: tuple[str, ...] = ()
    if about:
        eid = next((e for e in world.entities
                    if about in (world.entities[e].name, e)), None)
        if eid is not None:
            keys = (refer(world, actor, eid), world.entities[eid].name)
        else:
            keys = (about,)
    out = []
    for at, text in rows:
        if since is not None and at < since:
            continue
        if keys and not any(k in text for k in keys):
            continue
        out.append(f"{clock_label(at)} {text}")
    return out


def block(world: World, actor: str, n_recent: int = 6) -> dict[str, Any]:
    """一次回合开始时的完整上下文，用于记录与审计。"""
    return {
        "glance": glance(world, actor),
        "recent": recent(world, actor, n_recent),
        "beliefs": beliefs(world, actor),
    }


def render_block(ctx: dict[str, Any]) -> str:
    g = ctx["glance"]
    lines = [f"【此刻】{g['time']} · {g['place']}"]
    if g["self"]:
        lines.append(f"【你】{g['self']}")
    if g["here"]:
        lines.append("【眼前】" + "；".join(g["here"]))
    if g["hands"]:
        lines.append("【手里】" + "、".join(g["hands"]))
    if ctx["beliefs"]:
        lines.append("【你知道的】" + "；".join(ctx["beliefs"]))
    if ctx["recent"]:
        lines.append("【最近】" + " / ".join(ctx["recent"]))
    return "\n".join(lines)
