"""感知渲染：把状态投影成角色能看见的文字。

规则：渲染里只有物理（字、墨、声音、动作），没有作者、时间戳、读者、因果。
每个状态键都必须在 `STATE_RENDERERS` 里登记；登记为 `None` 表示这个键不产生可见文字
（它是物性，改变的是"能做什么"，不是"看见什么"）。
"""

from __future__ import annotations

from typing import Any, Callable

from .core import World

#: 状态键 → 渲染函数（None = 不可见但改变可做的动作）
STATE_RENDERERS: dict[str, Callable[[Any], str] | None] = {}


def register_state_renderer(key: str, fn: Callable[[Any], str] | None) -> None:
    if key in STATE_RENDERERS:
        raise ValueError(f"状态键重复登记：{key}")
    STATE_RENDERERS[key] = fn


def visible_fragments(world: World, eid: str) -> list[str]:
    out: list[str] = []
    for key in sorted(world.state.get(eid, {})):
        fn = STATE_RENDERERS.get(key)
        if fn is None:
            continue
        text = fn(world.state[eid][key])
        if text:
            out.append(text)
    return out


def refer(world: World, viewer: str, eid: str) -> str:
    """说到某个人时能怎么称呼他：知道名字才用名字，否则只能说"那个人"。"""
    ent = world.entities[eid]
    if eid == viewer or ent.kind != "person" or eid in world.knowledge.get(viewer, []):
        return ent.name
    return "那个人"


def describe(world: World, eid: str, viewer: str | None = None) -> str:
    """一个东西被感知到的样子：作者写的散文 + 当前状态的可见片段。"""
    ent = world.entities[eid]
    label = refer(world, viewer, eid) if viewer else ent.name
    parts = [ent.prose] if ent.prose else []
    parts += visible_fragments(world, eid)
    return f"{label}（{'；'.join(parts)}）" if parts else label


def pairing_report(seed_state_keys: set[str]) -> list[str]:
    """lint 用：种子用到的每个状态键都必须登记过渲染。"""
    missing = sorted(k for k in seed_state_keys if k not in STATE_RENDERERS)
    return [f"状态键没有渲染：{k}" for k in missing]
