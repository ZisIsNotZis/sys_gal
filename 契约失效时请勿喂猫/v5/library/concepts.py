"""库：M1 的十个动词。

每个概念给出五件东西：物性前提（when）、原子效果（atoms）、渲染（render）、
失败回执（reason/hints）、以及用到它的故事（used_by）。引擎不认识这些动词。
"""

from __future__ import annotations

from typing import Any

from engine.core import World
from engine.render import describe, refer
from engine.resolve import in_sight, inner_place, visible
from engine.rules import Ctx, Rule, register

STORY = ("s1_last_bus",)


# ---------- 共用小工具

def _people(world: World) -> list[str]:
    return [e for e in world.entities if world.kind_of(e) == "person"]


def _onlookers(world: World, actor: str, target: str | None = None) -> list[str]:
    """看得见这一动作的人：看得见动作发起者，且（有目标时）看得见目标。"""
    out = []
    for p in _people(world):
        if p == actor:
            continue
        if not in_sight(world, p, actor):
            continue
        if target is not None and not in_sight(world, p, target):
            continue
        out.append(p)
    return out


def _holding(world: World, actor: str, eid: str) -> bool:
    return world.container(eid) == actor


def _room(world: World, eid: str) -> str | None:
    return world.place_of(eid)


# ---------- 十个动词

def _look_when(ctx: Ctx) -> str | None:
    return None


def _look_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _look_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    seen = [e for e in visible(w, ctx.actor)]
    if not seen:
        return [(ctx.actor, "你什么也没看见。")]
    parts = [describe(w, e, ctx.actor) for e in seen]
    return [(ctx.actor, "你看见：" + "；".join(parts) + "。")]


def _read_when(ctx: Ctx) -> str | None:
    if ctx.world.get(ctx.target, "inscription") is None:
        return f"{ctx.name(ctx.target)}上面没有字"
    return None


def _read_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _read_hints(ctx: Ctx) -> list[str]:
    w = ctx.world
    readable = [w.entities[e].name for e in visible(w, ctx.actor)
                if w.get(e, "inscription") is not None]
    return ["眼前能读的东西：" + ("、".join(readable) if readable else "没有")]


def _read_render(ctx: Ctx) -> list[tuple[str, str]]:
    text = ctx.world.get(ctx.target, "inscription")
    out = [(ctx.actor, f"你读着{ctx.name(ctx.target)}：「{text}」")]
    for p in _onlookers(ctx.world, ctx.actor, ctx.target):
        out.append((p, f"{refer(ctx.world, p, ctx.actor)}在看{ctx.name(ctx.target)}。"))
    return out


def _touch_when(ctx: Ctx) -> str | None:
    return None


def _touch_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _touch_render(ctx: Ctx) -> list[tuple[str, str]]:
    return [(ctx.actor, f"你碰了碰{ctx.name(ctx.target)}，它没有因此改变。")]


def _take_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if not w.get(ctx.target, "portable"):
        return f"{ctx.name(ctx.target)}拿不走"
    if _holding(w, ctx.actor, ctx.target):
        return f"{ctx.name(ctx.target)}已经在你手里"
    return None


def _take_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return [{"op": "move", "e": ctx.target, "to": ctx.actor}]


def _take_render(ctx: Ctx) -> list[tuple[str, str]]:
    out = [(ctx.actor, f"你拿起了{ctx.name(ctx.target)}。")]
    for p in _onlookers(ctx.world, ctx.actor, ctx.target):
        out.append((p, f"{refer(ctx.world, p, ctx.actor)}拿起了{ctx.name(ctx.target)}。"))
    return out


def _place_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if not _holding(w, ctx.actor, ctx.target):
        return f"{ctx.name(ctx.target)}不在你手里"
    dest = ctx.args["to"]
    if w.kind_of(dest) == "place":
        if _room(w, ctx.actor) != dest:
            return f"你不在{ctx.name(dest)}里"
        return None
    if w.get(dest, "closed"):
        return f"{ctx.name(dest)}封着口，放不进去"
    return None


def _place_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return [{"op": "move", "e": ctx.target, "to": ctx.args["to"]}]


def _place_render(ctx: Ctx) -> list[tuple[str, str]]:
    dest = ctx.args["to"]
    if ctx.world.kind_of(dest) == "place":
        out = [(ctx.actor, f"你把{ctx.name(ctx.target)}放在了这儿。")]
        where = "这儿"
    else:
        out = [(ctx.actor, f"你把{ctx.name(ctx.target)}放进了{ctx.name(dest)}里。")]
        where = ctx.name(dest)
    for p in _onlookers(ctx.world, ctx.actor, ctx.target):
        out.append((p, f"{refer(ctx.world, p, ctx.actor)}把{ctx.name(ctx.target)}放在了{where}。"))
    return out


def _give_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if not _holding(w, ctx.actor, ctx.target):
        return f"{ctx.name(ctx.target)}不在你手里"
    to = ctx.args["to"]
    if w.kind_of(to) != "person":
        return f"{ctx.name(to)}不能接东西"
    if not in_sight(w, ctx.actor, to):
        return f"你看不见{ctx.name(to)}"
    return None


def _give_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return [{"op": "move", "e": ctx.target, "to": ctx.args["to"]}]


def _give_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    you = refer(w, ctx.actor, ctx.args["to"])
    return [
        (ctx.actor, f"你把{ctx.name(ctx.target)}交给了{you}。"),
        (ctx.args["to"], f"{refer(w, ctx.args['to'], ctx.actor)}把{ctx.name(ctx.target)}递给了你。"),
    ] + [(p, f"{refer(w, p, ctx.actor)}把手里的东西递给了{refer(w, p, ctx.args['to'])}。")
         for p in _onlookers(w, ctx.actor, ctx.target) if p != ctx.args["to"]]


def _open_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if w.kind_of(ctx.target) == "place":
        if w.get(ctx.target, "door") != "closed":
            return f"{ctx.name(ctx.target)}的门本来就开着"
        if inner_place(w, _room(w, ctx.actor), ctx.target) is None:
            return f"你够不到{ctx.name(ctx.target)}的门"
        return None
    if not w.get(ctx.target, "closed"):
        return f"{ctx.name(ctx.target)}本来就开着"
    return None


def _open_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    w = ctx.world
    if w.kind_of(ctx.target) == "place":
        return [{"op": "set", "e": ctx.target, "k": "door", "v": "open"}]
    return [{"op": "set", "e": ctx.target, "k": "closed", "v": False}]


def _open_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    if w.kind_of(ctx.target) == "place":
        return [(ctx.actor, f"你推开了{ctx.name(ctx.target)}的门。")]
    inside = [w.entities[c].name for c in w.children(ctx.target)]
    body = "、".join(inside) if inside else "空的"
    out = [(ctx.actor, f"你打开{ctx.name(ctx.target)}，里面是：{body}。")]
    for p in _onlookers(w, ctx.actor, ctx.target):
        out.append((p, f"{refer(w, p, ctx.actor)}打开了{ctx.name(ctx.target)}。"))
    return out


def _knock_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if w.kind_of(ctx.target) != "place":
        return f"{ctx.name(ctx.target)}没有门可敲"
    if w.get(ctx.target, "door") != "closed":
        return f"{ctx.name(ctx.target)}的门开着"
    if inner_place(w, _room(w, ctx.actor), ctx.target) is None:
        return f"你够不到{ctx.name(ctx.target)}的门"
    return None


def _knock_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _knock_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    name = ctx.name(ctx.target)
    out = [(ctx.actor, f"你敲了敲{name}的门。")]
    for p in _people(w):
        if p != ctx.actor and _room(w, p) == ctx.target:
            out.append((p, f"{name}的门被人从外面敲了几下。"))
    return out


def _move_when(ctx: Ctx) -> str | None:
    return None


def _move_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return [{"op": "move", "e": ctx.actor, "to": ctx.target}]


def _move_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    out = [(ctx.actor, f"你到了{ctx.name(ctx.target)}。")]
    for p in _people(w):
        if p == ctx.actor:
            continue
        if in_sight(w, p, ctx.target):
            out.append((p, f"{refer(w, p, ctx.actor)}走了进来。"))
        elif inner_place(w, _room(w, p), _room(w, ctx.actor)) is not None:
            out.append((p, f"{refer(w, p, ctx.actor)}走了出去。"))
    return out


def _wait_when(ctx: Ctx) -> str | None:
    return None


def _wait_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _wait_render(ctx: Ctx) -> list[tuple[str, str]]:
    return [(ctx.actor, "你等着。")]


_CONCEPTS = [
    Rule("look", STORY, _look_when, _look_atoms, _look_render, cost=1),
    Rule("read", STORY, _read_when, _read_atoms, _read_render, cost=1, hints=_read_hints),
    Rule("touch", STORY, _touch_when, _touch_atoms, _touch_render, cost=0),
    Rule("take", STORY, _take_when, _take_atoms, _take_render, cost=1),
    Rule("place", STORY, _place_when, _place_atoms, _place_render, cost=1),
    Rule("give", STORY, _give_when, _give_atoms, _give_render, cost=1),
    Rule("open", STORY, _open_when, _open_atoms, _open_render, cost=1),
    Rule("knock", STORY, _knock_when, _knock_atoms, _knock_render, cost=1),
    Rule("move", STORY, _move_when, _move_atoms, _move_render, cost=2),
    Rule("wait", STORY, _wait_when, _wait_atoms, _wait_render, cost=1),
]

for _rule in _CONCEPTS:
    register(_rule)
