"""《夜班》：M5 的脚本演员。

一个夜班从 22:00 交接到次日 08:00 交班。交接时抽屉里数出来八百，账上写着一千；
少的二百在后仓一个封着的纸箱里（一叠备用金），可没人往那儿想。
四条路各把这二百送到不同的地方，结局只由世界事实拼出：

- `a` 找到了（记错）：接班者打开纸箱，把备用金放回收银抽屉，抽屉与账对上了；
- `b` 真丢了：送货员把纸箱当空箱带走，两百跟着出了店，没有一笔账提到它；
- `c` 被人做了账：交班者在交接记录上添了一笔「付送货现金二百」，送货单却写着月结；
- `d` 自己背：接班人没开纸箱，直接在记录上写下短款二百由自己补。

结局不按路径名查表：两条脚本若把世界带到同样的数、同样的记录、同样的钱的位置，
就必须结束成同一句话。脚本只证明这件事物理上做得到，不代表角色的意愿。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import library  # noqa: F401  注册库动词
from engine.core import World
from engine.events import Event, EventLog
from engine.rules import Receipt, advance_idle, drain, submit
from engine.seed import load
from engine.surface import block, clock_label
from library import EFFECTS, stocktake
from stories.common import advance_next

DEFAULT_SEED = Path(__file__).with_name("seed.yml")

#: 这一班的两个数：抽屉与账。钱是相同的物，数只是数。
DRAWER = "drawer"
TILL = "till_cash"
SPARE = "spare_cash"
BOX = "box"
RECORD = "handover_record"
NOTE = "delivery_note"
SHOP = "shop"

#: 脚本里的时间标记：没有动作，世界自己走到下一个排程点（`advance_idle`）。
#: 夜里那一段没有人替角色做决定，承诺的提醒与白班开门都是制度自己到点。
NIGHT = "__night__"
#: 时间只走到下一个排程点，好让值班的人在两个制度事件之间收箱点数。
NEXT = "__next__"

#: 22:00 交接：记录落一行、钥匙交出、笔留在柜台上、承诺顶班、两班人分开。
_OPENING: list[tuple[str, str, dict[str, Any]]] = [
    ("outgoing", "shift", {"target": "交接记录", "to": "接班者", "key": "办公室钥匙"}),
    ("outgoing", "place", {"target": "笔", "to": "店内"}),
    ("outgoing", "speak", {"text": "抽屉里一千，你数一遍；办公室钥匙我交给你了。"}),
    ("incoming", "promise", {"text": "明晚白班我替你顶。", "to": "交班者", "at": 1900}),
    ("outgoing", "move", {"target": "店外"}),
    ("incoming", "count", {"target": "收银抽屉"}),
    ("incoming", "read", {"target": "交接记录"}),
    ("incoming", "read", {"target": "小票"}),
    ("incoming", "read", {"target": "班表"}),
]

#: 夜里来一个顾客，买一瓶水；小票是公开记录，班表也是。
_CUSTOMER: list[tuple[str, str, dict[str, Any]]] = [
    ("customer", "move", {"target": "店内"}),
    ("incoming", "take", {"target": "笔"}),
    ("incoming", "write", {"target": "小票", "text": "22:40 矿泉水一瓶 3 元。", "with": "笔"}),
    ("incoming", "place", {"target": "笔", "to": "店内"}),
    ("customer", "read", {"target": "班表"}),
    ("customer", "speak", {"text": "这水多少钱？"}),
    ("incoming", "speak", {"text": "三块。夜班就我一个人。"}),
    ("customer", "move", {"target": "店外"}),
]

#: 送货员把十二箱水搬进后仓。
_DELIVERY: list[tuple[str, str, dict[str, Any]]] = [
    ("driver", "move", {"target": "店内"}),
    ("driver", "move", {"target": "后仓"}),
    ("driver", "place", {"target": "送货", "to": "后仓"}),
]

#: 办公室锁着，电话在里头；接班者用交过来的钥匙进去，给店长打电话。
_OFFICE_CALL: list[tuple[str, str, dict[str, Any]]] = [
    ("incoming", "unlock", {"target": "办公室"}),
    ("incoming", "open", {"target": "办公室"}),
    ("incoming", "move", {"target": "办公室"}),
    ("incoming", "call", {"target": "电话",
                          "text": "店长，接班盘点：抽屉里数出八百，账上写一千。"}),
    ("manager", "call", {"target": "电话",
                         "text": "我过不去。钥匙在谁手里，这一班的账就记在谁头上。"}),
    ("incoming", "move", {"target": "店内"}),
    ("incoming", "lock", {"target": "办公室"}),
]

#: 夜里世界自己走：承诺的提醒、次日白班开门。
_NIGHT = [("", NIGHT, {})]

#: 夜里有人当班：送货到点后收箱、点数、在夜间记录上落一行；清晨那车也一样点数。
_NIGHT_ROUND: list[tuple[str, str, dict[str, Any]]] = [
    ("", NEXT, {}),
    ("incoming", "take", {"target": "笔"}),
    ("incoming", "move", {"target": "后仓"}),
    ("incoming", "count", {"target": "夜间补货"}),
    ("incoming", "write", {"target": "夜间记录", "text": "夜间补货到，点数六箱，已入后仓。",
                           "with": "笔"}),
    ("incoming", "place", {"target": "笔", "to": "后仓"}),
    ("incoming", "move", {"target": "店内"}),
    ("", NEXT, {}),
    ("incoming", "read", {"target": "巡夜登记"}),
    # 凌晨的清运车从门口过；当班的人再点一次钱，把签到表看一遍。
    ("", NEXT, {}),
    ("incoming", "count", {"target": "收银抽屉"}),
    ("incoming", "examine", {"target": "巡夜登记"}),
    ("", NEXT, {}),
    ("incoming", "move", {"target": "后仓"}),
    ("incoming", "count", {"target": "清晨补货"}),
    ("incoming", "move", {"target": "店内"}),
    # 清晨补货到齐，把夜里的小票与交接记录核一遍，交班前再点一次钱。
    ("incoming", "read", {"target": "小票"}),
    ("incoming", "read", {"target": "交接记录"}),
    ("", NEXT, {}),
    ("incoming", "count", {"target": "收银抽屉"}),
    *_NIGHT,
]

#: 次日 08:00 交班：钥匙交回，记录上再落一行。
_CLOSING: list[tuple[str, str, dict[str, Any]]] = [
    ("outgoing", "move", {"target": "店内"}),
    ("incoming", "take", {"target": "笔"}),
    ("incoming", "shift", {"target": "交接记录", "to": "交班者", "key": "办公室钥匙"}),
]

#: 交班者在记录上做的那一笔假账（路 c）。
_FAKE = ("outgoing", "write",
         {"target": "交接记录", "text": "付送货现金二百，当班结清。", "with": "笔"})

#: 接班者自己认下的那一行（路 d）。
_ASSUME = ("incoming", "write",
           {"target": "交接记录", "text": "短款二百，由接班者补。", "with": "笔"})

SCRIPTS: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    # A：找到了（记错）——备用金一直在后仓的纸箱里，数漏了。
    "a": [
        *_OPENING,
        *_CUSTOMER,
        *_DELIVERY,
        *_OFFICE_CALL,
        ("incoming", "move", {"target": "后仓"}),
        ("incoming", "count", {"target": "库存"}),
        ("incoming", "open", {"target": "纸箱"}),
        ("incoming", "count", {"target": "纸箱"}),
        ("incoming", "take", {"target": "备用金"}),
        ("incoming", "move", {"target": "店内"}),
        ("incoming", "place", {"target": "备用金", "to": "收银抽屉"}),
        ("incoming", "count", {"target": "收银抽屉"}),
        *_NIGHT_ROUND,
        *_CLOSING,
    ],
    # B：真丢了——送货员把那个纸箱当空箱带走，两百跟着出了店，没人记账。
    "b": [
        *_OPENING,
        *_CUSTOMER,
        *_DELIVERY,
        *_OFFICE_CALL,
        ("driver", "take", {"target": "纸箱"}),
        ("driver", "move", {"target": "店内"}),
        ("driver", "move", {"target": "店外"}),
        ("incoming", "count", {"target": "收银抽屉"}),
        ("incoming", "speak", {"text": "两百对不上，账上写着一千。"}),
        *_NIGHT_ROUND,
        *_CLOSING,
    ],
    # C：被人做了账——交班者添一笔现金付款，送货单上却是月结。
    "c": [
        ("outgoing", "shift", {"target": "交接记录", "to": "接班者", "key": "办公室钥匙"}),
        _FAKE,
        *_OPENING[1:],
        *_CUSTOMER,
        *_DELIVERY,
        *_OFFICE_CALL,
        ("driver", "take", {"target": "纸箱"}),
        ("driver", "move", {"target": "店内"}),
        ("driver", "move", {"target": "店外"}),
        ("incoming", "read", {"target": "交接记录"}),
        ("incoming", "read", {"target": "送货单"}),
        ("incoming", "speak", {"text": "账上多了一笔付送货的现金，送货单上写的是月结。"}),
        *_NIGHT_ROUND,
        *_CLOSING,
    ],
    # D：自己背——纸箱没开，接班者在记录上写下短款二百由自己补。
    "d": [
        *_OPENING,
        *_CUSTOMER,
        *_DELIVERY,
        *_OFFICE_CALL,
        ("incoming", "take", {"target": "笔"}),
        _ASSUME,
        ("incoming", "place", {"target": "笔", "to": "店内"}),
        ("incoming", "count", {"target": "收银抽屉"}),
        ("incoming", "speak", {"text": "数出来八百，差两百，先记我头上。"}),
        *_NIGHT_ROUND,
        *_CLOSING,
    ],
}


@dataclass
class Run:
    variant: str
    world: World
    log: EventLog
    items: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    spare_trail: list[str] = field(default_factory=list)
    title: str = "《夜班》"
    summary: dict[str, Any] = field(default_factory=dict)


def _world_item(event: Event) -> dict[str, Any]:
    perceived = [(a["e"], a["v"]) for a in event.atoms if a.get("op") == "remember"]
    return {"kind": "world", "at": event.at, "what": event.what, "perceived": perceived}


def _addressed(world: World, args: dict[str, Any]) -> str:
    to = args.get("to")
    if not to:
        return ""
    if to in world.entities:
        return world.entities[to].name
    return str(to)


def play(variant: str = "a", seed_path: Path = DEFAULT_SEED) -> Run:
    world = load(seed_path)
    log = EventLog()
    run = Run(variant=variant, world=world, log=log, spare_trail=[_spare_where(world)])

    for step, (actor, verb, args) in enumerate(SCRIPTS[variant], start=1):
        for event in drain(world, log, EFFECTS):
            run.items.append(_world_item(event))
        if verb == NIGHT:
            # 没有动作：时间自己走到下一个排程点，途中的世界事件照样入账与入册。
            run.items.extend(_world_item(event) for event in advance_idle(world, log, EFFECTS))
            continue
        if verb == NEXT:
            # 只走到下一个排程点：这一班的人还要在两个制度事件之间做事。
            run.items.extend(_world_item(event) for event in advance_next(world, log, EFFECTS))
            continue
        context = block(world, actor)
        receipt = submit(world, log, actor, verb, dict(args))
        run.receipts.append(receipt)
        target = receipt.event.note.get("target") if receipt.event else None
        run.items.append({
            "kind": "turn", "at": receipt.event.at if receipt.event else world.clock,
            "actor": actor, "verb": verb,
            "target": world.entities[target].name if target in world.entities else dict(args).get("target", ""),
            "to": _addressed(world, args),
            "ok": receipt.ok, "texts": list(receipt.texts),
            "reason": receipt.reason, "hints": list(receipt.hints), "note": receipt.note,
            "context": context, "context_used": False,
            "decided_by": "script", "step": step,
            "spare_where": _spare_where(world),
        })
        holder = _spare_where(world)
        if holder != run.spare_trail[-1]:
            run.spare_trail.append(holder)
    run.summary = summary(run)
    return run


# ---------- 由世界事实拼结局

def _spare_where(world: World) -> str:
    """那两百此刻在哪儿；沿着包含关系往上读到一个人或一个地方。"""
    holder = world.container(SPARE)
    seen: set[str] = set()
    while holder is not None and holder not in seen:
        seen.add(holder)
        ent = world.entities.get(holder)
        name = ent.name if ent else holder
        if holder == DRAWER:
            return "收银抽屉"
        if holder == BOX:
            above = world.container(BOX)
            if above == "back_room":
                return "后仓的纸箱里"
            if above in world.entities:
                return f"{world.entities[above].name}拿着的纸箱"
            return "纸箱"
        if ent is not None and ent.kind == "person":
            return f"{name}手里"
        if ent is not None and ent.kind == "place":
            return name
        holder = world.container(holder)
    return "不在世界里"


#: 店里的现金就是这两样：盘点读数只数它们，总数仍由 `Reading.total` 一处相加。
MONEY = (TILL, SPARE)


def _money(eid: str) -> bool:
    return eid in MONEY


def _drawer_total(world: World) -> int:
    """抽屉里看得见的现金：封着的那一叠数不到。"""
    return stocktake(world, DRAWER, keep=_money).total


def _shop_total(world: World) -> int:
    """店里还剩下的现金：按物理位置算，封在纸箱里的也算在店里。"""
    return stocktake(world, SHOP, include_sealed=True, keep=_money).total


def _record_expected(world: World) -> int | None:
    """交接记录上写的收银数：从物理字迹里读，不从任何状态键里读。"""
    text = "".join(m.get("text", "") for m in world.get(RECORD, "marks") or [])
    found = re.findall(r"收银\s*(\d+)", text)
    return int(found[-1]) if found else None


def _written_by(world: World, who: str, *, handover_only: bool = False,
                extra_only: bool = False) -> list[str]:
    hand = world.get(who, "hand")
    rows = [m.get("text", "") for m in world.get(RECORD, "marks") or []
            if m.get("style") == hand]
    if handover_only:
        rows = [t for t in rows if "交班" in t]
    if extra_only:
        rows = [t for t in rows if "交班" not in t]
    return rows


def _delivery_note_text(world: World) -> str:
    return "".join(m.get("text", "") for m in world.get(NOTE, "marks") or [])


def _ending(facts: dict[str, Any]) -> str:
    drawer = facts["收银抽屉里的数"]
    expected = facts["记录上的数"]
    if drawer == expected and facts["店里现金总数"] == expected:
        return (f"找到了（记错）：抽屉里数出 {drawer}，账上写着 {expected}；"
                f"两百是后仓纸箱里那叠备用金，交接时记漏了")
    if facts["接班者添的行"]:
        return (f"自己背：抽屉里只有 {drawer}，账上是 {expected}；"
                f"备用金还在{facts['备用金最后在谁手里']}，"
                f"记录上却添了一行「{facts['接班者添的行'][0]}」")
    if facts["交班者添的行"]:
        return (f"被人做了账：抽屉里只有 {drawer}，账上是 {expected}；"
                f"记录上多出一笔「{facts['交班者添的行'][0]}」，"
                f"送货单上写的是「{facts['送货单上写的']}」")
    return (f"真丢了：抽屉里只有 {drawer}，账上是 {expected}；"
            f"两百跟着送货员的空箱出了店，没有一笔账提到它")


def summary(run: Run) -> dict[str, Any]:
    world = run.world
    expected = _record_expected(world)
    facts: dict[str, Any] = {
        "收银抽屉里的数": _drawer_total(world),
        "记录上的数": expected,
        "店里现金总数": _shop_total(world),
        "备用金最后在谁手里": _spare_where(world),
        "备用金的去向": list(run.spare_trail),
        "交班者添的行": _written_by(world, "outgoing", extra_only=True),
        "接班者添的行": _written_by(world, "incoming", extra_only=True),
        "送货单上写的": _delivery_note_text(world),
        "交班时间": world.clock,
        "交班时刻读法": clock_label(world.clock, world.date),
    }
    facts["结局"] = _ending(facts)
    return facts
