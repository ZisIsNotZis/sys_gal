"""《借条》：M2 的脚本演员。

四条路，四种结局：原样复写 / 擦改没人发现 / 添一笔被认出但不说 / 当场说破。
和 M1 一样，脚本只证明"这件事物理上做得到"，不代表角色的意愿。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.core import World
from engine.events import Event, EventLog
from engine.rules import Receipt, drain, submit
from engine.seed import load
from engine.surface import block
from library import EFFECTS

DEFAULT_SEED = Path(__file__).with_name("seed.yml")

_OPEN_DRAWER: list[tuple[str, str, dict[str, Any]]] = [
    ("jia", "unlock", {"target": "抽屉"}),
    ("jia", "open", {"target": "抽屉"}),
    ("jia", "take", {"target": "借条"}),
    ("jia", "place", {"target": "借条", "to": "出租屋"}),
]

_ADD_CLAUSE: list[tuple[str, str, dict[str, Any]]] = [
    ("yi", "take", {"target": "钢笔"}),
    ("yi", "write", {"target": "借条", "text": "利息按日百分之五计。", "with": "钢笔"}),
    ("yi", "place", {"target": "钢笔", "to": "出租屋"}),
]

SCRIPTS: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    # A：谁也不改，甲留了一份抄件
    "a": [
        *_OPEN_DRAWER,
        ("jia", "take", {"target": "空白纸"}),
        ("jia", "copy", {"target": "借条"}),
        ("jia", "read", {"target": "抄件1"}),
        ("bing", "recognize", {"target": "借条"}),
        ("jia", "place", {"target": "借条", "to": "抽屉"}),
    ],
    # B：甲出去接电话，乙擦掉铅笔写的数目，重新写一个，没人看
    "b": [
        *_OPEN_DRAWER,
        ("jia", "move", {"target": "楼道"}),
        ("bing", "move", {"target": "楼道"}),
        ("yi", "take", {"target": "橡皮"}),
        ("yi", "erase", {"target": "借条"}),
        ("yi", "take", {"target": "铅笔"}),
        ("yi", "write", {"target": "借条",
                         "text": "今借到现金三千元，三个月内归还。", "with": "铅笔"}),
        ("yi", "place", {"target": "铅笔", "to": "出租屋"}),
        ("yi", "place", {"target": "橡皮", "to": "出租屋"}),
        ("jia", "move", {"target": "出租屋"}),
        ("jia", "read", {"target": "借条"}),
        ("jia", "place", {"target": "借条", "to": "抽屉"}),
    ],
    # C：乙添了一条利息，丙看出来了，但没说
    "c": [
        *_OPEN_DRAWER,
        ("jia", "move", {"target": "楼道"}),
        *_ADD_CLAUSE,
        ("bing", "examine", {"target": "借条"}),
        ("bing", "recognize", {"target": "借条"}),
        ("jia", "move", {"target": "出租屋"}),
        ("jia", "read", {"target": "借条"}),
        ("jia", "place", {"target": "借条", "to": "抽屉"}),
    ],
    # D：同上，但丙当场说破
    "d": [
        *_OPEN_DRAWER,
        ("jia", "move", {"target": "楼道"}),
        *_ADD_CLAUSE,
        ("bing", "examine", {"target": "借条"}),
        ("bing", "recognize", {"target": "借条"}),
        ("jia", "move", {"target": "出租屋"}),
        ("bing", "speak", {"text": "这一笔不是你的字。"}),
        ("jia", "examine", {"target": "借条"}),
        ("jia", "recognize", {"target": "借条"}),
        ("jia", "speak", {"text": "谁写的？"}),
    ],
}


@dataclass
class Run:
    variant: str
    world: World
    log: EventLog
    items: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    title: str = "《借条》"
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
        context = block(world, actor)
        receipt = submit(world, log, actor, verb, dict(args))
        run.receipts.append(receipt)
        target = receipt.event.note.get("target") if receipt.event else None
        run.items.append({
            "kind": "turn", "at": receipt.event.at if receipt.event else world.clock,
            "actor": actor, "verb": verb,
            "target": world.entities[target].name if target in world.entities else dict(args).get("target", ""),
            "to": dict(args).get("to", ""),
            "ok": receipt.ok, "texts": list(receipt.texts),
            "reason": receipt.reason, "hints": list(receipt.hints), "note": receipt.note,
            "context": context, "context_used": False,
            "decided_by": "script", "step": step,
        })
    run.summary = summary(run)
    return run


def summary(run: Run) -> dict[str, Any]:
    w = run.world
    marks = w.get("iou", "marks") or []
    said = [r for r in run.receipts if r.ok and r.what == "speak"]
    bing_memory = " ".join(text for _at, text in w.memory.get("bing", []))
    jia_memory = " ".join(text for _at, text in w.memory.get("jia", []))
    return {
        "借条在谁那里": w.entities[w.container("iou")].name if w.container("iou") else "不在",
        "借条上有几笔字": len(marks),
        "纸面上有擦痕": bool(w.get("iou", "smudge")),
        "读出来的全文":
            "".join(m["text"] for m in marks),
        "丙认出是乙的字": "像是乙的字" in bing_memory,
        "甲说不出是谁写的": "说不出是谁写的" in jia_memory,
        "有人当场说话": len(said),
        "结局": {
            "a": "谁也没改，甲手里多了一张抄件",
            "b": "乙擦掉数目重写了一个，没人发现",
            "c": "乙添了一条利息，丙认出来了，但没说",
            "d": "乙添了一条利息，丙当场说破，甲却说不出是谁写的",
        }[run.variant],
    }
