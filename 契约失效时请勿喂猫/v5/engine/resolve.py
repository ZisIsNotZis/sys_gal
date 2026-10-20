"""P10：命名解析与可见性。

一个人能怎么称呼一样东西，取决于他此刻能感知到什么、以及他知道什么。
解析失败时返回可行动的清单，而不是一句"找不到"。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .core import World


def inner_place(world: World, a: str | None, b: str | None) -> str | None:
    """两个地点若相邻（一个是另一个的祖先），返回带门的那一间（内间）。"""
    if a is None or b is None:
        return None
    if b in world.ancestors(a):
        return a
    if a in world.ancestors(b):
        return b
    return None


def hidden_by_container(world: World, eid: str) -> bool:
    """被封闭的容器装着的，看不见也拿不到。"""
    return any(world.get(anc, "closed") for anc in world.ancestors(eid))


def in_sight(world: World, viewer: str, eid: str) -> bool:
    """能不能看见：同一处看得见；相邻的里间要门开着才看得进去。"""
    vp, ep = world.place_of(viewer), world.place_of(eid)
    if vp is None or ep is None or hidden_by_container(world, eid):
        return False
    if ep == vp:
        return True
    inner = inner_place(world, vp, ep)
    return inner is not None and world.get(inner, "door") != "closed"


def nameable(world: World, viewer: str, eid: str) -> bool:
    """能不能指着它说话：看得见的东西，加上相邻那间的门（门关着也看得见门）。"""
    if in_sight(world, viewer, eid):
        return True
    if world.kind_of(eid) == "place":
        return inner_place(world, world.place_of(viewer), eid) is not None
    return False


def visible(world: World, viewer: str) -> list[str]:
    return [e for e in world.entities if e != viewer and nameable(world, viewer, e)]


def known_but_unseen(world: World, viewer: str, ref: str) -> list[str]:
    out = []
    for eid in world.knowledge.get(viewer, []):
        if eid in world.entities and not nameable(world, viewer, eid):
            ent = world.entities[eid]
            if ref in (ent.name, ent.id) or ref in ent.aliases:
                out.append(ent.name)
    return out


@dataclass
class Resolution:
    ok: bool
    eid: str | None = None
    reason: str = ""
    hints: list[str] = field(default_factory=list)
    note: str = ""

    def __bool__(self) -> bool:
        return self.ok


_NOISE = ("我的", "你的", "他的", "她的", "手里的", "手上", "桌上的", "眼前的", "地上的",
          "那个", "这个", "那张", "这张", "那只", "这只", "那份", "这份", "的")


def normalize(ref: str) -> str:
    """人用描述性说法指东西：去掉限定词，再拿来匹配。"""
    text = ref.strip()
    changed = True
    while changed:
        changed = False
        for noise in _NOISE:
            if text.startswith(noise) and len(text) > len(noise):
                text = text[len(noise):]
                changed = True
    return text.strip()


def _score(world: World, viewer: str, eid: str, ref: str) -> int:
    """3 = 名字正好对上；2 = 说法里含有名字；1 = 名字里含有说法。"""
    ent = world.entities[eid]
    if ent.kind == "person" and eid != viewer and eid not in world.knowledge.get(viewer, []):
        return 3 if ref in ("那个人", "有人", "这个人") else 0
    ref = normalize(ref)
    if ref in (ent.name, ent.id) or ref in ent.aliases:
        return 3
    if len(ref) >= 2 and ref in ent.name:
        return 2
    if len(ent.name) >= 2 and ent.name in ref:
        return 2
    if len(ref) >= 2 and ref in (ent.prose or ""):
        return 1
    return 0


def resolve(world: World, actor: str, ref: str) -> Resolution:
    """把一个指称解析成实体，只允许用该角色此刻能看见或已知的东西。"""
    scored = [(e, _score(world, actor, e, ref)) for e in visible(world, actor)]
    cands = [e for e, score in scored if score > 0]
    best = max((score for _e, score in scored), default=0)
    if best:
        in_hand = "手里" in ref or "手上" in ref
        top = [e for e, score in scored if score == best]
        if in_hand:
            held = [e for e in top if world.container(e) == actor]
            top = held or top
        cands = sorted(top)
    if not cands:
        known = known_but_unseen(world, actor, ref)
        if known:
            return Resolution(False, reason=f"{ref}你现在看不见",
                              hints=[f"你知道它，但它不在眼前：{known[0]}"])
        here = [world.entities[e].name for e in visible(world, actor)]
        return Resolution(
            False,
            reason=f"这里没有一样东西叫「{ref}」",
            hints=["眼前能看见：" + ("、".join(here) if here else "什么都没有")],
        )
    if len(cands) > 1:
        cands.sort()
        chosen = cands[0]
        return Resolution(True, eid=chosen,
                          note=f"这里有 {len(cands)} 样东西都对得上「{ref}」，你指的是{world.entities[chosen].name}")
    return Resolution(True, eid=cands[0])


def resolve_place(world: World, actor: str, ref: str) -> Resolution:
    """去某处：门没关就能进去。"""
    res = resolve(world, actor, ref)
    if not res:
        return res
    eid = res.eid
    if world.kind_of(eid) != "place":
        return Resolution(False, reason=f"{world.entities[eid].name}不是一个地方",
                          hints=["能去的地方：" + "、".join(
                              world.entities[p].name for p in visible(world, actor)
                              if world.kind_of(p) == "place")])
    here = world.place_of(actor)
    if eid == here:
        return Resolution(False, reason=f"你已经在{world.entities[eid].name}里了")
    inner = inner_place(world, here, eid)
    if inner is None:
        return Resolution(False, reason=f"从{world.entities[here].name}走不到{world.entities[eid].name}",
                          hints=["能去的地方：" + "、".join(
                              world.entities[p].name for p in visible(world, actor)
                              if world.kind_of(p) == "place")])
    if world.get(inner, "door") == "closed":
        return Resolution(False, reason=f"{world.entities[inner].name}的门是关着的")
    return res
