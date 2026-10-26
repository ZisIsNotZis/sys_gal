"""库：M1 的十个动词。

每个概念给出五件东西：物性前提（when）、原子效果（atoms）、渲染（render）、
失败回执（reason/hints）、以及用到它的故事（used_by）。引擎不认识这些动词。
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from engine.core import World
from engine.render import describe, refer
from engine.resolve import in_sight, inner_place, visible
from engine.rules import Ctx, Rule, register
from engine.surface import clock_label

STORY = ("s1_last_bus", "s2_borrow_note", "s7_campus_12d")


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

def _examine_when(ctx: Ctx) -> str | None:
    return None


def _examine_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _examine_render(ctx: Ctx) -> list[tuple[str, str]]:
    """细看：把眼前的东西看到能看清字的程度（内容仍要 read 才算读过）。"""
    w = ctx.world
    seen = [e for e in visible(w, ctx.actor)]
    if not seen:
        return [(ctx.actor, "你什么也没看见。")]
    parts = [describe(w, e, ctx.actor, detail=True) for e in seen]
    return [(ctx.actor, "你细看：" + "；".join(parts) + "。")]


def _read_when(ctx: Ctx) -> str | None:
    if not ctx.world.get(ctx.target, "marks"):
        return f"{ctx.name(ctx.target)}上面没有字"
    return None


def _read_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _read_hints(ctx: Ctx) -> list[str]:
    w = ctx.world
    readable = [w.entities[e].name for e in visible(w, ctx.actor)
                if w.get(e, "marks")]
    return ["眼前能读的东西：" + ("、".join(readable) if readable else "没有")]


def _read_render(ctx: Ctx) -> list[tuple[str, str]]:
    text = "".join(m["text"] for m in ctx.world.get(ctx.target, "marks") or [])
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
        if w.get(ctx.target, "locked"):
            return f"{ctx.name(ctx.target)}锁着"
        if inner_place(w, _room(w, ctx.actor), ctx.target) is None:
            return f"你够不到{ctx.name(ctx.target)}的门"
        return None
    if w.get(ctx.target, "locked"):
        return f"{ctx.name(ctx.target)}锁着"
    if not w.get(ctx.target, "closed"):
        return f"{ctx.name(ctx.target)}本来就开着"
    return None


def _open_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    w = ctx.world
    if w.kind_of(ctx.target) == "place":
        return [{"op": "set", "e": ctx.target, "k": "door", "v": "open"}]
    return [{"op": "set", "e": ctx.target, "k": "closed", "v": False}]


def _open_hints(ctx: Ctx) -> list[str]:
    w = ctx.world
    keys = [w.entities[c].name for c in w.children(ctx.actor) if w.get(c, "opens")]
    return ["手上能开的钥匙：" + ("、".join(keys) if keys else "没有")]


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



# ---------- M2：书写、擦除、复写、开锁、认字、说话

def _implement_in_hand(w: World, actor: str) -> str | None:
    for c in w.children(actor):
        if w.get(c, "implement"):
            return c
    return None


def _write_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if not ctx.args.get("text"):
        return "你没想好要写什么"
    tool = ctx.args.get("with") or _implement_in_hand(w, ctx.actor)
    if tool is None:
        return "你手里没有能写字的东西"
    ink = w.get(tool, "implement")
    if ink not in (w.get(ctx.target, "accepts") or []):
        return f"{ctx.name(ctx.target)}留不下{ink}这种痕迹"
    if w.get(ctx.target, "closed"):
        return f"{ctx.name(ctx.target)}封着口"
    return None


def _write_hints(ctx: Ctx) -> list[str]:
    w = ctx.world
    tools = [w.entities[c].name for c in w.children(ctx.actor) if w.get(c, "implement")]
    writable = [w.entities[e].name for e in visible(w, ctx.actor) if w.get(e, "accepts")]
    return [f"手上能写的：{'、'.join(tools) if tools else '没有'}",
            f"眼前能写的：{'、'.join(writable) if writable else '没有'}"]


def _write_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    w = ctx.world
    tool = ctx.args.get("with") or _implement_in_hand(w, ctx.actor)
    marks = list(w.get(ctx.target, "marks") or [])
    marks.append({"text": ctx.args["text"], "ink": w.get(tool, "implement"),
                  "style": w.get(ctx.actor, "hand") or "printed"})
    return [{"op": "set", "e": ctx.target, "k": "marks", "v": marks}]


def _write_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    out = [(ctx.actor, f"你在{ctx.name(ctx.target)}上添了一笔：「{ctx.args['text']}」")]
    for p in _onlookers(w, ctx.actor, ctx.target):
        out.append((p, f"{refer(w, p, ctx.actor)}在{ctx.name(ctx.target)}上写字。"))
    return out


def _erase_when(ctx: Ctx) -> str | None:
    w = ctx.world
    marks = w.get(ctx.target, "marks") or []
    if not any(m.get("ink") == "graphite" for m in marks):
        return f"{ctx.name(ctx.target)}上没有能用橡皮擦掉的字"
    if not any(w.get(c, "erases") for c in w.children(ctx.actor)):
        return "你手里没有橡皮"
    return None


def _erase_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    w = ctx.world
    marks = list(w.get(ctx.target, "marks") or [])
    for i in range(len(marks) - 1, -1, -1):
        if marks[i].get("ink") == "graphite":
            marks.pop(i)
            break
    return [{"op": "set", "e": ctx.target, "k": "marks", "v": marks},
            {"op": "set", "e": ctx.target, "k": "smudge", "v": True}]


def _erase_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    out = [(ctx.actor, f"你擦掉了{ctx.name(ctx.target)}上铅笔写的那一笔，纸面上留下一片灰。")]
    for p in _onlookers(w, ctx.actor, ctx.target):
        out.append((p, f"{refer(w, p, ctx.actor)}在擦{ctx.name(ctx.target)}。"))
    return out


def _copy_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if not w.get(ctx.target, "marks"):
        return f"{ctx.name(ctx.target)}上没有能复写的东西"
    if not any(w.get(e, "copies") for e in visible(w, ctx.actor)):
        return "这里没有复写纸"
    if not any(w.get(c, "accepts") and not w.get(c, "marks") for c in w.children(ctx.actor)):
        return "你手里没有空白纸"
    return None


def _copy_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    w = ctx.world
    blank = next(c for c in w.children(ctx.actor)
                 if w.get(c, "accepts") and not w.get(c, "marks"))
    n = int(w.flags.get("copy_seq", 0)) + 1
    marks = [dict(m) for m in w.get(ctx.target, "marks") or []]
    entity = {"id": f"copy_{n}", "kind": "object", "name": f"抄件{n}",
              "prose": "一张复写出来的抄件", "aliases": (), "identity": ""}
    state = {"marks": marks, "imprint": True, "accepts": w.get(blank, "accepts"),
             "portable": True}
    return [{"op": "flag", "k": "copy_seq", "v": n},
            {"op": "create", "e": entity, "to": ctx.actor, "state": state},
            {"op": "destroy", "e": blank}]


def _copy_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    n = int(w.flags.get("copy_seq", 0))
    out = [(ctx.actor, f"你隔着复写纸把{ctx.name(ctx.target)}抄了一份，成了{_copy_name(n)}。")]
    for p in _onlookers(w, ctx.actor, ctx.target):
        out.append((p, f"{refer(w, p, ctx.actor)}在复写{ctx.name(ctx.target)}。"))
    return out


def _copy_name(n: int) -> str:
    return f"抄件{n}"


def _unlock_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if not w.get(ctx.target, "locked"):
        return f"{ctx.name(ctx.target)}没有锁着"
    if not any(w.get(c, "opens") == ctx.target for c in w.children(ctx.actor)):
        return "你手上没有能开它的钥匙"
    return None


def _unlock_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return [{"op": "set", "e": ctx.target, "k": "locked", "v": False}]


def _unlock_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    out = [(ctx.actor, f"你打开了{ctx.name(ctx.target)}的锁。")]
    for p in _onlookers(w, ctx.actor, ctx.target):
        out.append((p, f"{refer(w, p, ctx.actor)}打开了{ctx.name(ctx.target)}的锁。"))
    return out


def _recognize_when(ctx: Ctx) -> str | None:
    if not ctx.world.get(ctx.target, "marks"):
        return f"{ctx.name(ctx.target)}上没有字可以认"
    return None


def _recognize_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _recognize_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    marks = w.get(ctx.target, "marks") or []
    readers = w.hand_readers.get(ctx.actor, {})
    lines: list[str] = []
    for mark in marks:
        style = mark.get("style")
        if not style or style == "printed":
            continue
        if style == w.get(ctx.actor, "hand"):
            lines.append("有一笔是你自己的字")
        elif style in readers and readers[style] in w.entities:
            lines.append(f"有一笔像是{refer(w, ctx.actor, readers[style])}的字")
        else:
            lines.append("有一笔的字，你说不出是谁写的")
    if len({m.get("ink") for m in marks}) > 1:
        lines.append("几笔的墨色不一样")
    body = "；".join(lines) if lines else "上面只有印上去的字"
    out = [(ctx.actor, f"你盯着{ctx.name(ctx.target)}上的字看：{body}。")]
    for p in _onlookers(w, ctx.actor, ctx.target):
        out.append((p, f"{refer(w, p, ctx.actor)}在仔细看{ctx.name(ctx.target)}上的字。"))
    return out


def _speak_when(ctx: Ctx) -> str | None:
    if not ctx.args.get("text"):
        return "你什么也没说"
    return None


def _speak_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _speak_render(ctx: Ctx) -> list[tuple[str, str]]:
    """当众说，在场的人都听见内容；带 to 就是私下，旁人只看见"两人在低声说话"。"""
    w = ctx.world
    text = ctx.args["text"]
    to = ctx.args.get("to")
    if to:
        out = [(ctx.actor, f"你压低声音，对{refer(w, ctx.actor, to)}说：「{text}」"),
               (to, f"{refer(w, to, ctx.actor)}压低声音，对你说：「{text}」")]
        for p in _onlookers(w, ctx.actor, to):
            if p == to:
                continue
            out.append((p, f"{refer(w, p, ctx.actor)}和{refer(w, p, to)}凑在一起低声说话，"
                           "你听不清内容。"))
        return out
    out = [(ctx.actor, f"你说：「{text}」")]
    for p in _people(w):
        if p != ctx.actor and in_sight(w, p, ctx.actor):
            out.append((p, f"{refer(w, p, ctx.actor)}说：「{text}」"))
    return out


# ---------- M4：制度角色（收）

def _records_in_sight(w: World, actor: str) -> str | None:
    for e in visible(w, actor):
        if w.get(e, "records"):
            return e
    return None


def _impound_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if not w.get(ctx.actor, "institution"):
        return "你在制度里没有这个身份，收不了东西"
    if not w.get(ctx.target, "portable"):
        return f"{ctx.name(ctx.target)}收不走"
    if _holding(w, ctx.actor, ctx.target):
        return f"{ctx.name(ctx.target)}已经在你手里"
    if _records_in_sight(w, ctx.actor) is None:
        return "这里没有能登记的本子"
    if _implement_in_hand(w, ctx.actor) is None:
        return "你手里没有能写字的笔"
    return None


def _impound_hints(ctx: Ctx) -> list[str]:
    w = ctx.world
    tools = [w.entities[c].name for c in w.children(ctx.actor) if w.get(c, "implement")]
    books = [w.entities[e].name for e in visible(w, ctx.actor) if w.get(e, "records")]
    return [f"手上能登记的笔：{'、'.join(tools) if tools else '没有'}",
            f"眼前的登记本：{'、'.join(books) if books else '没有'}"]


def _impound_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    """收走一件东西，并在登记本上留下恰好一行。"""
    w = ctx.world
    book = _records_in_sight(w, ctx.actor)
    tool = _implement_in_hand(w, ctx.actor)
    src = w.container(ctx.target)
    where = w.entities[src].name if src in w.entities else "不明"
    rows = list(w.get(book, "marks") or [])
    rows.append({"text": f"{clock_label(w.clock, w.date)} 收：{ctx.name(ctx.target)}（自{where}）",
                 "ink": w.get(tool, "implement") or "ink", "style": "printed"})
    return [{"op": "move", "e": ctx.target, "to": ctx.actor},
            {"op": "set", "e": book, "k": "marks", "v": rows}]


def _impound_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    name = ctx.name(ctx.target)
    src = w.container(ctx.target)
    out = [(ctx.actor, f"你把{name}收走了，在本子上记了一行。")]
    if w.kind_of(src) == "person":
        out.append((src, f"{refer(w, src, ctx.actor)}把你的{name}收走了，在本子上记了一行。"))
    for p in _onlookers(w, ctx.actor, ctx.target):
        if p == src:
            continue
        out.append((p, f"{refer(w, p, ctx.actor)}把{name}收走了，在本子上记了一行。"))
    return out


# ---------- M5：记录权威、人群扇出、传闻扩散、无名指称

def _present(world: World, actor: str) -> list[str]:
    """同一处的人：声音传得到，看不看得见另说。"""
    place = world.place_of(actor)
    return [p for p in _people(world)
            if p != actor and world.place_of(p) == place]


def _sign_when(ctx: Ctx) -> str | None:
    """记录权威：只有能登记的本子上的字算数，嘴上说的不进本子。"""
    w = ctx.world
    if not ctx.args.get("text"):
        return "你没想好要记什么"
    if not w.get(ctx.target, "records"):
        return f"{ctx.name(ctx.target)}不是能登记的本子"
    tool = _implement_in_hand(w, ctx.actor)
    if tool is None:
        return "你手里没有能写字的东西"
    ink = w.get(tool, "implement")
    if ink not in (w.get(ctx.target, "accepts") or []):
        return f"{ctx.name(ctx.target)}留不下{ink}这种痕迹"
    if w.get(ctx.target, "closed"):
        return f"{ctx.name(ctx.target)}封着口"
    return None


def _sign_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    w = ctx.world
    tool = _implement_in_hand(w, ctx.actor)
    rows = list(w.get(ctx.target, "marks") or [])
    rows.append({"text": f"{clock_label(w.clock, w.date)} {ctx.args['text']}",
                 "ink": w.get(tool, "implement") or "ink",
                 "style": w.get(ctx.actor, "hand") or "printed"})
    return [{"op": "set", "e": ctx.target, "k": "marks", "v": rows}]


def _sign_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    name = ctx.name(ctx.target)
    out = [(ctx.actor, f"你在{name}上记下一行：「{ctx.args['text']}」")]
    for p in _onlookers(w, ctx.actor, ctx.target):
        out.append((p, f"{refer(w, p, ctx.actor)}在{name}上记了一行。"))
    return out


def _announce_when(ctx: Ctx) -> str | None:
    if not ctx.args.get("text"):
        return "你什么也没说"
    return None


def _announce_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    return []


def _announce_render(ctx: Ctx) -> list[tuple[str, str]]:
    """人群感知扇出：对着这一处的所有人说，看不看得见都听得见；不传到别的屋子。"""
    w = ctx.world
    text = ctx.args["text"]
    out = [(ctx.actor, f"你提高声音说：「{text}」")]
    for p in _present(w, ctx.actor):
        out.append((p, f"{refer(w, p, ctx.actor)}提高声音说：「{text}」"))
    return out


def _clauses(text: str) -> list[str]:
    return [c for c in re.split(r"[，。；！？]", text) if c.strip()]


def _degrade(text: str, hop: int) -> str:
    """传闻每过一张嘴，就掉一截：第一个转述的人已经少说了最后半句。"""
    parts = _clauses(text)
    keep = max(1, len(parts) - hop)
    body = "，".join(parts[:keep])
    return f"{body}……" if hop > 0 else f"{body}。"


def _retell_hop(w: World, about: str) -> int:
    return int(w.flags.get(f"retold:{about}", 0)) + 1


def _retell_when(ctx: Ctx) -> str | None:
    w = ctx.world
    text = ctx.args.get("text")
    if not text:
        return "你没什么可转述的"
    about = ctx.args.get("about") or text
    if not any(about in t for _at, t in w.memory.get(ctx.actor, [])):
        return f"你没听人说起过「{about}」，编不出这话"
    return None


def _retell_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    w = ctx.world
    about = ctx.args.get("about") or ctx.args["text"]
    return [{"op": "flag", "k": f"retold:{about}", "v": _retell_hop(w, about)}]


def _retell_render(ctx: Ctx) -> list[tuple[str, str]]:
    """传闻扩散：说的人存下的是掉了一截的版本，听的人拿到的更短。"""
    w = ctx.world
    text = ctx.args["text"]
    about = ctx.args.get("about") or text
    said = _degrade(text, _retell_hop(w, about))
    to = ctx.args.get("to")
    if to:
        out = [(ctx.actor, f"你压低声音，把听来的话对{refer(w, ctx.actor, to)}转述了一遍：「{said}」"),
               (to, f"{refer(w, to, ctx.actor)}低声对你说：「{said}」")]
        for p in _onlookers(w, ctx.actor, to):
            if p != to:
                out.append((p, f"{refer(w, p, ctx.actor)}和{refer(w, p, to)}凑在一起低声说话，你听不清内容。"))
        return out
    out = [(ctx.actor, f"你把听来的话转述出去：「{said}」")]
    for p in _onlookers(w, ctx.actor):
        out.append((p, f"{refer(w, p, ctx.actor)}把听来的事转述了一遍：「{said}」"))
    return out


def resolve_looks(world: World, actor: str, ref: str) -> str | None:
    """无名指称：不认识的人只能靠看得见的样子来叫；名字与 id 都叫不动他。"""
    hits: list[str] = []
    for eid in visible(world, actor):
        if world.kind_of(eid) != "person":
            continue
        ent = world.entities[eid]
        known = eid in world.knowledge.get(actor, [])
        text = f"{ent.prose} {ent.name}" if known else ent.prose
        if ref in text or any(ref in a for a in ent.aliases):
            hits.append(eid)
    return sorted(hits)[0] if hits else None


def _hail_when(ctx: Ctx) -> str | None:
    w = ctx.world
    if not ctx.args.get("text"):
        return "你什么也没说"
    who = ctx.args.get("who") or ""
    if not who:
        return "你不知道该冲谁喊"
    if resolve_looks(w, ctx.actor, who) is None:
        return f"你看不出「{who}」指的是谁"
    return None


def _hail_atoms(ctx: Ctx) -> list[dict[str, Any]]:
    w = ctx.world
    eid = resolve_looks(w, ctx.actor, ctx.args.get("who") or "")
    if eid is None:
        return []
    return [{"op": "know", "e": ctx.actor, "v": eid}]


def _hail_render(ctx: Ctx) -> list[tuple[str, str]]:
    w = ctx.world
    who = ctx.args.get("who") or ""
    text = ctx.args["text"]
    eid = resolve_looks(w, ctx.actor, who)
    if eid is None:
        return [(ctx.actor, f"你冲着「{who}」喊了一声，没人应。")]
    ent = w.entities[eid]
    out = [(ctx.actor, f"你冲着{ent.prose}喊了一声：「{text}」"),
           (eid, f"有人冲你喊了一声：「{text}」")]
    for p in _onlookers(w, ctx.actor, eid):
        if p != eid:
            out.append((p, f"{refer(w, p, ctx.actor)}冲一个生面孔喊了一声：「{text}」"))
    return out


_CONCEPTS = [
    Rule("examine", STORY, _examine_when, _examine_atoms, _examine_render, cost=1),
    Rule("read", STORY, _read_when, _read_atoms, _read_render, cost=1, hints=_read_hints),
    Rule("touch", STORY, _touch_when, _touch_atoms, _touch_render, cost=0),
    Rule("take", STORY, _take_when, _take_atoms, _take_render, cost=1),
    Rule("place", STORY, _place_when, _place_atoms, _place_render, cost=1,
         entity_args=("target", "to")),
    Rule("give", STORY, _give_when, _give_atoms, _give_render, cost=1,
         entity_args=("target", "to")),
    Rule("open", STORY, _open_when, _open_atoms, _open_render, cost=1, hints=_open_hints),
    Rule("knock", STORY, _knock_when, _knock_atoms, _knock_render, cost=1),
    Rule("move", STORY, _move_when, _move_atoms, _move_render, cost=2),
    Rule("wait", STORY, _wait_when, _wait_atoms, _wait_render, cost=1, entity_args=()),
    Rule("write", ("s2_borrow_note", "s3_night_market", "s4_night_shift",
                   "s5_wedding", "s7_campus_12d"),
         _write_when, _write_atoms, _write_render, cost=2, hints=_write_hints,
         entity_args=("target", "with")),
    Rule("erase", ("s2_borrow_note", "s7_campus_12d"),
         _erase_when, _erase_atoms, _erase_render, cost=2),
    Rule("copy", ("s2_borrow_note", "s4_night_shift", "s7_campus_12d"),
         _copy_when, _copy_atoms, _copy_render, cost=3),
    Rule("unlock", ("s2_borrow_note", "s4_night_shift", "s6_parcel_station",
                    "s7_campus_12d"),
         _unlock_when, _unlock_atoms, _unlock_render, cost=1),
    Rule("recognize", ("s2_borrow_note", "s7_campus_12d"),
         _recognize_when, _recognize_atoms, _recognize_render, cost=2),
    Rule("speak", ("s1_last_bus", "s2_borrow_note", "s3_night_market",
                   "s5_wedding", "s7_campus_12d"),
         _speak_when, _speak_atoms, _speak_render, cost=1, entity_args=("to",)),
    Rule("impound", ("s3_night_market", "s4_night_shift"),
         _impound_when, _impound_atoms, _impound_render, cost=1, hints=_impound_hints),
    Rule("sign", ("s5_wedding", "s6_parcel_station"),
         _sign_when, _sign_atoms, _sign_render, cost=2),
    Rule("announce", ("s5_wedding", "s6_parcel_station"),
         _announce_when, _announce_atoms, _announce_render, cost=1, entity_args=()),
    Rule("retell", ("s5_wedding", "s6_parcel_station"),
         _retell_when, _retell_atoms, _retell_render, cost=1, entity_args=("to",)),
    Rule("hail", ("s5_wedding", "s6_parcel_station"),
         _hail_when, _hail_atoms, _hail_render, cost=1, entity_args=()),
]

#: 给模型看的一句话说明。工具表由这里生成，所以每个动词都必须有一句。
DOCS = {
    "examine": "把眼前的东西看到能看清细节的程度（不读内容）",
    "read": "读出纸上的字；只有你自己知道内容",
    "touch": "碰一下，什么也不会改变",
    "take": "把东西拿到手里",
    "place": "把手里的东西放下（放到某处或某个容器里）",
    "give": "把手里的东西递给眼前的某个人",
    "open": "打开容器或一扇门",
    "knock": "敲某间屋子的门；里面的人会听见",
    "move": "走到另一个地方",
    "wait": "等一会儿，什么也不做",
    "write": "在某张纸上添一笔字（用你手里的笔）",
    "erase": "用橡皮擦掉铅笔写的字，会留下擦痕",
    "copy": "用复写纸把一份纸上的字复写下来（要空白纸）",
    "unlock": "用钥匙打开某把锁",
    "recognize": "盯着纸上的字迹看：你能认出是谁的字吗",
    "speak": "说一句话：不带 to 就是当众说，在场的人都听得见；带 to 就只对那个人说，旁人只看见你们在低声说话",
    "impound": "以制度身份把一件东西收走，并在登记本上记下一行",
    "sign": "在签到本这类登记簿上记下一行；只有写下的才算数",
    "announce": "对同一处的所有人高声说一句；看不看得见都听得见，传不到别的屋子",
    "retell": "把听来的话转述出去；每经一张嘴，话就短一截",
    "hail": "冲一个你说不出名字的人喊话，只能靠他穿什么、长什么样来指他",
}

LABELS = {"examine": "细看", "read": "读", "touch": "碰", "take": "拿起", "place": "放下",
          "give": "交给", "open": "打开", "knock": "敲门", "move": "走过去", "wait": "等",
          "write": "写", "erase": "擦掉", "copy": "复写", "unlock": "开锁",
          "recognize": "认字", "speak": "说话", "impound": "收",
          "sign": "记上", "announce": "高声说", "retell": "转述", "hail": "喊住"}

#: 除目标之外还需要的参数。指称类参数由引擎解析成世界里的东西。
PARAMS = {
    "write": (("text", "要写上去的字", True), ("with", "用哪支笔", False)),
    "speak": (("text", "你要说的话", True), ("to", "只对谁私下说；不说就是当众", False)),
    "place": (("to", "放到哪里", True),),
    "give": (("to", "交给谁", True),),
    "sign": (("text", "记下什么", True),),
    "announce": (("text", "你要高声说的话", True),),
    "retell": (("text", "你要转述的话", True),
               ("about", "你听人说起过的那件事（用来核对你的记忆）", False),
               ("to", "只对谁私下转述；不说就是这一处的人都听见", False)),
    "hail": (("who", "你怎么指他：穿什么、长什么样", True),
             ("text", "你要喊的话", True)),
}

for _rule in _CONCEPTS:
    register(replace(_rule, doc=DOCS[_rule.verb], params=PARAMS.get(_rule.verb, ()),
                     label=LABELS[_rule.verb]))
