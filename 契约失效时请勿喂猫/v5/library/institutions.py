"""库：制度与物性的世界效果。

排程到点执行的东西必须是物理或制度（有人上班、车到站、门几点开），
不能是"命运让某事发生"。每个效果只准用原子效果表达。
"""

from __future__ import annotations

from typing import Any

from engine.core import World
from engine.resolve import in_sight
from engine.surface import clock_label


def _present(world: World, place: str) -> list[str]:
    """在场：就在这个地点，或者在这个地点里间的（驾驶室也算在车上）。"""
    out = []
    for p in world.entities:
        if world.kind_of(p) != "person":
            continue
        here = world.place_of(p)
        if here == place or (here is not None and place in world.ancestors(here)):
            out.append(p)
    return out


def _witnesses(world: World, place: str) -> list[str]:
    """看得见这个地点的人：里面有谁，外面谁看得见它。"""
    return [p for p in world.entities
            if world.kind_of(p) == "person" and in_sight(world, p, place)]


def _around(world: World, place: str) -> list[str]:
    """就在这一处和紧邻的外间的人：卸货的动静隔一道门也听得见。"""
    people = set(_present(world, place))
    parent = world.container(place)
    if parent is not None and world.kind_of(parent) == "place":
        people.update(_present(world, parent))
    return [p for p in world.entities if p in people]


def arrive(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    station = effect.get("station", "站")
    atoms: list[dict[str, Any]] = [{"op": "flag", "k": "last_stop", "v": station}]
    atoms += [{"op": "remember", "e": p, "at": world.clock, "v": f"车停了一下：{station}。"}
              for p in _present(world, effect["place"])]
    return atoms


def stops(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = [{"op": "flag", "k": "stopped", "v": True}]
    atoms += [{"op": "remember", "e": p, "at": world.clock,
               "v": "终点站到了，司机熄了火，车厢的灯灭了一半。"}
              for p in _present(world, effect["place"])]
    return atoms


# ---------- M4：制度（到点关门、次日开门、到点提醒、张贴）

def close(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """到点关门：门关上、锁扣上，看得见的人听见。"""
    place = effect["place"]
    name = world.entities[place].name
    atoms: list[dict[str, Any]] = [
        {"op": "set", "e": place, "k": "door", "v": "closed"},
        {"op": "set", "e": place, "k": "locked", "v": True},
    ]
    atoms += [{"op": "remember", "e": p, "at": world.clock,
               "v": f"{name}的门关上了，接着是锁扣上的响。"}
              for p in _witnesses(world, place)]
    return atoms


def reopen(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """到点开门：锁开了、门开开。"""
    place = effect["place"]
    name = world.entities[place].name
    atoms: list[dict[str, Any]] = [
        {"op": "set", "e": place, "k": "door", "v": "open"},
        {"op": "set", "e": place, "k": "locked", "v": False},
    ]
    atoms += [{"op": "remember", "e": p, "at": world.clock,
               "v": f"{name}的门开了，锁被摘了下来。"}
              for p in _witnesses(world, place)]
    return atoms


def pickup_due(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """到点提醒该来领的人：只通知登记上的那个人，不通知条子在谁手里。"""
    who = effect["who"]
    name = world.entities[effect["place"]].name
    return [{"op": "remember", "e": who, "at": world.clock,
             "v": f"{name}那边有人隔着摊子喊了你一声：今天收走的东西，收摊前来领。"}]


def post(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """张贴：把一张纸贴到某处；看见的人只知道贴了张纸，内容要去读。"""
    item, place = effect["item"], effect["place"]
    name = world.entities[item].name
    atoms: list[dict[str, Any]] = [{"op": "move", "e": item, "to": place}]
    atoms += [{"op": "remember", "e": p, "at": world.clock,
               "v": f"有人把{name}贴在了这里。"}
              for p in _witnesses(world, place)]
    return atoms


def deliver(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """到点的送货：货车把货卸到某处，看得见的人听见动静。"""
    item, place = effect["item"], effect["place"]
    item_name = world.entities[item].name
    place_name = world.entities[place].name
    atoms: list[dict[str, Any]] = [{"op": "move", "e": item, "to": place}]
    atoms += [{"op": "remember", "e": p, "at": world.clock,
               "v": f"送货车在{place_name}门口停下，卸下{item_name}。"}
              for p in _around(world, place)]
    return atoms


def stamp(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """到点登记：值班的人或巡夜在登记本上落一行，字是这一处公开的。"""
    item = effect["item"]
    text = effect.get("station", "签到")
    rows = list(world.get(item, "marks") or [])
    rows.append({"text": f"{clock_label(world.clock, world.date)} {text}",
                 "ink": "printed", "style": "printed"})
    place = effect.get("place") or world.place_of(item)
    atoms: list[dict[str, Any]] = [{"op": "set", "e": item, "k": "marks", "v": rows}]
    atoms += [{"op": "remember", "e": p, "at": world.clock,
               "v": f"{world.entities[item].name}上多了一行登记。"}
              for p in (_present(world, place) if place else [])]
    return atoms


def clean(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """到点清扫/收拾：这是一班的收尾，不归任何一个人的决定。"""
    place = effect["place"]
    name = world.entities[place].name
    atoms: list[dict[str, Any]] = [{"op": "flag", "k": "cleaned", "v": place}]
    atoms += [{"op": "remember", "e": p, "at": world.clock,
               "v": f"清洁的人进了{name}，开始收拾。"}
              for p in _present(world, place)]
    return atoms


def remind(world: World, effect: dict[str, Any]) -> list[dict[str, Any]]:
    """到点提醒许下承诺的人：承诺进入了时间表，提醒只说那件事本身。"""
    who = effect["who"]
    about = effect.get("about", "")
    place = effect.get("place")
    where = world.entities[place].name if place in world.entities else ""
    text = f"{where}这边到了你说定的那一刻" if where else "到了你说定的那一刻"
    return [{"op": "remember", "e": who, "at": world.clock, "v": f"{text}：{about}"}]


EFFECTS = {"arrive": arrive, "stops": stops,
           "close": close, "open": reopen,
           "pickup_due": pickup_due, "post": post, "remind": remind,
           "deliver": deliver, "stamp": stamp, "clean": clean}
