"""库：制度与物性的世界效果。

排程到点执行的东西必须是物理或制度（有人上班、车到站、门几点开），
不能是"命运让某事发生"。每个效果只准用原子效果表达。
"""

from __future__ import annotations

from typing import Any

from engine.core import World


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


EFFECTS = {"arrive": arrive, "stops": stops}
