"""《婚礼》：M5 的第二个世界，一整天，十一个人。

四条路，四种结局：查出是谁 / 没人再查 / 记录被改 / 大家装作没看见。
结局由这一局末尾世界的几件事拼出（签到本上还剩什么、本子被擦过没有、有谁认下了
那个生面孔、有几个人读过那一行），不按路径名查表：两条路在这几件事上相同，
就是同一个结局。脚本只证明"这件事物理上做得到"，不代表角色的意愿。

这一局压到的五件事：
- 人群并发：十一个人分散在四处，公开发言与私下低声听到的人不一样；
- 传闻扩散：一句话经过一张嘴就掉一截，说的人自己存下的也是残本；
- 记录权威：只有签到本上写下的行算数，嘴上说的不进货；
- 无名指称：不认识的人只能用"穿灰夹克的"来叫，名字和 id 都叫不动他；
- 记忆互污：读过本子的、只听过转述的、什么都没听见的，各存一个版本。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.core import World
from engine.events import Event, EventLog
from engine.rules import Receipt, advance_idle, drain, submit
from engine.seed import load
from engine.surface import block, clock_label
from library import EFFECTS
from stories.common import advance_next

DEFAULT_SEED = Path(__file__).with_name("seed.yml")

#: 签到本的实体 id；它是记录权威的唯一住所。
SIGNIN_ID = "signin"
#: 生面孔的实体 id。谁都不认识他，所以 `refer` 只会说"那个人"。
STRANGER_ID = "stranger"
#: 签到本上多出来的那个名字。
EXTRA_NAME = "陈明"

#: 脚本里的时间标记：这一段没有动作，世界自己走到下一个排程点（`advance_idle`）。
#: 路 b 靠它把一天从 09:00 走到 22:00，跨过中午，日期不翻页。
DAY = "__day__"
#: 时间只走到下一个排程点：中午上菜与散场前收拾都要在它们之间插进来。
NEXT = "__next__"

#: 四条路共用的开场：一个不在名单上的人走进签到台，写下那个名字，再回到厅里。
_OPENING: list[tuple[str, str, dict[str, Any]]] = [
    ("stranger", "move", {"target": "酒店"}),
    ("stranger", "move", {"target": "签到台"}),
    ("stranger", "take", {"target": "铅笔"}),
    ("stranger", "sign", {"target": "签到本", "text": EXTRA_NAME}),
    ("stranger", "place", {"target": "铅笔", "to": "签到台"}),
    ("stranger", "move", {"target": "酒店"}),
    ("stranger", "move", {"target": "厅内"}),
]

#: 中午开席：上菜、敬酒、入席、读安排，都是这一天真会发生的事。
_LUNCH: list[tuple[str, str, dict[str, Any]]] = [
    ("groom", "move", {"target": "厅内"}),
    ("bride", "move", {"target": "厅内"}),
    ("manager", "move", {"target": "后厨走廊"}),
    ("manager", "take", {"target": "菜"}),
    ("manager", "move", {"target": "厅内"}),
    ("manager", "place", {"target": "菜", "to": "厅内"}),
    ("manager", "announce", {"text": "十二点开席，菜已经上来了，各位动筷。"}),
    ("bride_father", "read", {"target": "午宴安排"}),
    ("groom_father", "read", {"target": "午宴安排"}),
    ("best_man", "take", {"target": "酒"}),
    ("best_man", "give", {"target": "酒", "to": "groom"}),
    ("groom", "place", {"target": "酒", "to": "厅内"}),
    ("groom", "speak", {"text": "我先敬各位一杯。"}),
    ("bride_mother", "move", {"target": "厅内"}),
    ("bride_mother", "give", {"target": "红包", "to": "bride"}),
    ("bride", "count", {"target": "红包"}),
    ("bride_father", "speak", {"text": "谢谢大家来。"}),
]

#: 散场前：厅里开始收，停车场上有一次照面。
_EVENING: list[tuple[str, str, dict[str, Any]]] = [
    ("manager", "move", {"target": "厅内"}),
    ("manager", "announce", {"text": "各位慢用，十点散场，门口有车等着。"}),
    ("best_man", "move", {"target": "停车场"}),
    ("best_man", "examine", {"target": "车"}),
    ("maid", "move", {"target": "停车场"}),
    ("maid", "speak", {"text": "这一排最里头那辆是你的？", "to": "伴郎"}),
    ("best_man", "speak", {"text": "我挪一下。", "to": "伴娘"}),
    ("best_man", "move", {"target": "厅内"}),
    ("manager", "move", {"target": "停车场"}),
    ("manager", "speak", {"text": "最里头那辆车挪一下，散场要让出道。"}),
]

SCRIPTS: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    # A：记账的人发现多了一个名字，经理当众问，伴郎说见过，新娘把名字对上了人
    "a": [
        *_OPENING,
        ("bookkeeper", "read", {"target": "签到本"}),
        ("bookkeeper", "read", {"target": "名单"}),
        ("bookkeeper", "speak", {"text": "签到本上多了个名字，叫陈明，名单上没有这个人。",
                                 "to": "经理"}),
        ("manager", "move", {"target": "酒店"}),
        ("manager", "move", {"target": "厅内"}),
        ("manager", "announce", {"text": "签到本上多了个名字，叫陈明，名单上没有这个人。谁见过？"}),
        ("best_man", "announce", {"text": "早上我看见一个穿灰夹克的男人从签到台那边过来。"}),
        ("bride", "hail", {"who": "穿灰夹克的男人", "text": "你就是本子上写的陈明？"}),
        ("", NEXT, {}),
        *_LUNCH,
        ("", NEXT, {}),
        *_EVENING,
        ("", DAY, {}),
    ],
    # B：记账的人看见了，但谁也没往下问；一天照常过完，22:00 散场
    "b": [
        *_OPENING,
        ("bookkeeper", "read", {"target": "签到本"}),
        ("groom", "announce", {"text": "各位入席，婚礼十点开始。"}),
        ("bookkeeper", "move", {"target": "酒店"}),
        ("bookkeeper", "move", {"target": "停车场"}),
        ("groom", "move", {"target": "酒店"}),
        ("groom", "move", {"target": "停车场"}),
        ("bride", "move", {"target": "酒店"}),
        ("bride", "move", {"target": "停车场"}),
        ("", NEXT, {}),
        *_LUNCH,
        ("", NEXT, {}),
        *_EVENING,
        ("", DAY, {}),
    ],
    # C：记账的人把那一行擦掉，再当众说"本子上没多什么人"
    "c": [
        *_OPENING,
        ("bookkeeper", "read", {"target": "签到本"}),
        ("bookkeeper", "take", {"target": "橡皮"}),
        ("bookkeeper", "erase", {"target": "签到本"}),
        ("bookkeeper", "place", {"target": "橡皮", "to": "签到台"}),
        ("bookkeeper", "announce", {"text": "没事了，本子上没多什么人。"}),
        ("", NEXT, {}),
        *_LUNCH,
        ("", NEXT, {}),
        *_EVENING,
        ("", DAY, {}),
    ],
    # D：记账的人私下告诉经理，经理转述给厅里的人，然后大家说好都不再提
    "d": [
        *_OPENING,
        ("bookkeeper", "read", {"target": "签到本"}),
        ("bride_mother", "move", {"target": "酒店"}),
        ("bride_mother", "move", {"target": "签到台"}),
        ("bride_mother", "read", {"target": "签到本"}),
        ("bookkeeper", "speak", {"text": "签到本上多了个名字，叫陈明，是穿灰夹克的男人写的。",
                                 "to": "经理"}),
        ("manager", "move", {"target": "酒店"}),
        ("manager", "move", {"target": "厅内"}),
        ("manager", "retell", {"about": "陈明",
                               "text": "签到本上多了个名字，叫陈明，是穿灰夹克的男人写的。"}),
        ("manager", "announce", {"text": "今天的事就到这儿，谁都别再提了。"}),
        ("", NEXT, {}),
        *_LUNCH,
        ("", NEXT, {}),
        *_EVENING,
        ("", DAY, {}),
    ],
}


@dataclass
class Run:
    variant: str
    world: World
    log: EventLog
    items: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    title: str = "《婚礼》"
    summary: dict[str, Any] = field(default_factory=dict)


def _world_item(event: Event) -> dict[str, Any]:
    perceived = [(a["e"], a["v"]) for a in event.atoms if a.get("op") == "remember"]
    return {"kind": "world", "at": event.at, "what": event.what, "perceived": perceived}


def play(variant: str = "a", seed_path: Path = DEFAULT_SEED) -> Run:
    world = load(seed_path)
    log = EventLog()
    run = Run(variant=variant, world=world, log=log)

    for step, (actor, verb, args) in enumerate(SCRIPTS[variant], start=1):
        for event in drain(world, log, EFFECTS):
            run.items.append(_world_item(event))
        if verb == DAY:
            # 没有动作：时间自己走到下一个排程点，途中的世界事件照样入账与入册。
            run.items.extend(_world_item(event) for event in advance_idle(world, log, EFFECTS))
            continue
        if verb == NEXT:
            # 只走到下一个排程点：中午上菜与散场前收拾要插在制度事件之间。
            run.items.extend(_world_item(event) for event in advance_next(world, log, EFFECTS))
            continue
        context = block(world, actor)
        receipt = submit(world, log, actor, verb, dict(args))
        run.receipts.append(receipt)
        target = dict(args).get("target") or dict(args).get("who") or ""
        if target in world.entities:
            target = world.entities[target].name
        run.items.append({
            "kind": "turn", "at": receipt.event.at if receipt.event else world.clock,
            "actor": actor, "verb": verb,
            "target": target,
            "to": _addressed(world, args),
            "ok": receipt.ok, "texts": list(receipt.texts),
            "reason": receipt.reason, "hints": list(receipt.hints), "note": receipt.note,
            "context": context, "context_used": False,
            "decided_by": "script", "step": step,
        })
    run.summary = summary(run)
    return run


def _addressed(world: World, args: dict[str, Any]) -> str:
    """这一句话是对谁说的（解析后的名字）；空串就是这一句没有指定的听众。"""
    to = args.get("to")
    if not to:
        return ""
    if to in world.entities:
        return world.entities[to].name
    return str(to)


def _close_at(run: Run) -> int | None:
    """已经发生的散场；还没走到就不算。"""
    for event in run.log:
        if event.kind == "world" and event.what == "close":
            return event.at
    return None


def _readers(run: Run) -> list[str]:
    """读过签到本的人（按本子当前的名字算），重复只算一次。"""
    book = run.world.entities[SIGNIN_ID].name
    seen: list[str] = []
    for item in run.items:
        if item["kind"] != "turn" or item["verb"] != "read" or item["target"] != book:
            continue
        if item["actor"] not in seen:
            seen.append(item["actor"])
    return seen


def _knowers(run: Run) -> list[str]:
    """谁把那个生面孔认了下来（`hail` 把这个人记进了他的知识）。"""
    w = run.world
    return [p for p in w.entities
            if w.kind_of(p) == "person" and STRANGER_ID in w.knowledge.get(p, [])]


def _ending(facts: dict[str, Any]) -> str:
    """结局只由 `facts` 里的几件事拼出；没有第五件，也不从路径名取。"""
    if facts["有人把名字对上了人"]:
        return (f"查出了是谁：{facts['对上的人']}在{facts['对上时在哪']}"
                f"认出了那个穿灰夹克的，签到本上多出来的那一行总算有了主")
    if facts["本子改过"]:
        return (f"记录被改：签到本上那一行被擦掉了，纸面上留下一片灰；"
                f"本子最后一行的字是「{facts['最后一行的字']}」")
    if facts["读过本子的人"] >= 2:
        return (f"大家装作没看见：{facts['读过本子的人']}个人读过那一行，"
                f"谁都没有开口，到散场也没有人再提")
    return (f"没有人再查：那个名字留在签到本上，散场时本子还是那一本，"
            f"最后一行的字是「{facts['最后一行的字']}」")


def summary(run: Run) -> dict[str, Any]:
    w = run.world
    rows = w.get(SIGNIN_ID, "marks") or []
    knowers = _knowers(run)
    close_at = _close_at(run)
    facts: dict[str, Any] = {
        "签到本上多出来的名字": EXTRA_NAME if any(EXTRA_NAME in r.get("text", "") for r in rows)
                                else "已经被抹掉",
        "最后一行的字": rows[-1]["text"] if rows else "空白",
        "有人把名字对上了人": bool(knowers),
        "对上的人": w.entities[knowers[0]].name if knowers else "没有人",
        "对上时在哪": (w.entities[w.place_of(knowers[0])].name
                       if knowers and w.place_of(knowers[0]) else "不知何处"),
        "读过本子的人": len(_readers(run)),
        "本子改过": bool(w.get(SIGNIN_ID, "smudge")),
        "散场时间": clock_label(close_at, w.date) if close_at is not None else "还没到散场",
        "钟停在哪": clock_label(w.clock, w.date),
    }
    facts["结局"] = _ending(facts)
    return facts
