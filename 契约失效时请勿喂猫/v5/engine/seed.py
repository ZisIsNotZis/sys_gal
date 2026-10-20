"""解析：把种子文件变成世界。

引擎只认这个形状，不认识任何故事名词；缺父、成环、状态键未登记都直接报错。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .core import Entity, World


def build(seed: dict[str, Any]) -> World:
    world = World(start=int(seed.get("start_clock", 0)))
    rows: list[dict[str, Any]] = []
    for row in seed.get("places", []):
        rows.append({**row, "kind": row.get("kind", "place")})
    for row in seed.get("people", []):
        rows.append({**row, "kind": row.get("kind", "person")})
    for row in seed.get("objects", []):
        rows.append({**row, "kind": row.get("kind", "object")})

    pending = list(rows)
    while pending:
        progressed = False
        for row in list(pending):
            parent = row.get("parent")
            if parent is not None and parent not in world.entities:
                continue
            world.add(
                Entity(id=row["id"], kind=row["kind"], name=row["name"],
                       prose=row.get("prose", ""),
                       aliases=tuple(row.get("aliases", ()))),
                parent=parent,
                state=row.get("state"),
            )
            world.knowledge.setdefault(row["id"], []).extend(row.get("knows", []))
            pending.remove(row)
            progressed = True
        if not progressed:
            raise ValueError(f"种子的父子关系成环或指向不存在的父：{[r['id'] for r in pending]}")

    for item in seed.get("schedule", []):
        world.schedule_effect(int(item["at"]), dict(item["effect"]))
    return world


def load(path: str | Path) -> World:
    with open(path, encoding="utf-8") as fh:
        return build(yaml.safe_load(fh))


def state_keys(seed: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for section in ("places", "people", "objects"):
        for row in seed.get(section, []):
            keys.update((row.get("state") or {}).keys())
    return keys


def entity_names(seed: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for section in ("places", "people", "objects"):
        for row in seed.get(section, []):
            names.add(row["id"])
            names.add(row["name"])
    return names
