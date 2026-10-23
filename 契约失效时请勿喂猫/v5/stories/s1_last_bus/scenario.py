"""《末班车》：M1 的脚本演员。

这里没有模型，也没有"预期剧情"——脚本只是三条物理上可行的路径的见证。
三条路径必须各自走到不同结局，才说明结局是世界的性质而不是脚本的性质。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.core import World
from engine.events import Event, EventLog
from engine.rules import Receipt, advance_idle, drain, submit
from engine.seed import load
from engine.surface import block
from library import EFFECTS

DEFAULT_SEED = Path(__file__).with_name("seed.yml")

#: 三条路径：(角色, 动词, 参数)。参数用世界里能指称的名字。
_YI_PACKS_UP: list[tuple[str, str, dict[str, Any]]] = [
    ("yi", "open", {"target": "包"}),
    ("yi", "take", {"target": "药盒"}),
    ("yi", "read", {"target": "药盒"}),
    ("yi", "place", {"target": "药盒", "to": "包"}),
    ("yi", "place", {"target": "包", "to": "车厢"}),
    ("yi", "wait", {}),
    ("yi", "move", {"target": "车外"}),
]

SCRIPTS: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    # A：把它交给司机（中间先失败一次：门关着，看不见人）
    "a": [
        ("jia", "examine", {}),
        ("jia", "read", {"target": "通知"}),
        *_YI_PACKS_UP,
        ("jia", "touch", {"target": "包"}),
        ("jia", "take", {"target": "包"}),
        ("jia", "give", {"target": "包", "to": "司机"}),
        ("jia", "knock", {"target": "驾驶室"}),
        ("jia", "wait", {}),
        ("jia", "open", {"target": "驾驶室"}),
        ("jia", "give", {"target": "包", "to": "司机"}),
        ("jia", "move", {"target": "车外"}),
    ],
    # B：打开它，把药盒带走
    "b": [
        ("jia", "examine", {}),
        ("jia", "read", {"target": "通知"}),
        *_YI_PACKS_UP,
        ("jia", "touch", {"target": "包"}),
        ("jia", "open", {"target": "包"}),
        ("jia", "read", {"target": "药盒"}),
        ("jia", "take", {"target": "药盒"}),
        ("jia", "move", {"target": "车外"}),
    ],
    # C：什么都不做，坐到终点
    "c": [
        ("jia", "examine", {}),
        ("jia", "read", {"target": "通知"}),
        *_YI_PACKS_UP,
        ("jia", "wait", {}),
        ("jia", "wait", {}),
        ("jia", "wait", {}),
        ("jia", "move", {"target": "车外"}),
    ],
}


@dataclass
class Run:
    variant: str
    world: World
    log: EventLog
    items: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    title: str = "《末班车》"
    summary: dict[str, Any] = field(default_factory=dict)


def _world_item(event: Event) -> dict[str, Any]:
    """世界事件只按"谁感知到了"呈现；没人感知到就明说没人感知到。"""
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
            "context": context,
            "context_used": False,      # 脚本演员不读上下文；M3 换成模型后为 True
            "decided_by": "script",    # M1 全部由脚本指定；M3 会出现 "agent"
            "step": step,
        })

    for event in advance_idle(world, log, EFFECTS):
        run.items.append(_world_item(event))
    run.summary = summary(run)
    return run


def summary(run: Run) -> dict[str, Any]:
    w = run.world

    def where(eid: str) -> str:
        holder = w.container(eid)
        if holder is None:
            return "不在世界里"
        return w.entities[holder].name

    scripted = {
        "a": "甲把包交给了司机",
        "b": "甲打开了包，把药盒带走",
        "c": "甲什么也没做，包留在了车上",
    }
    # 模型自己走的路径没有预设结局：结局必须由事实拼出来（M5 的第二支故事先撞上了这条：
    # 一份模型局用脚本的标签查结局，直接 KeyError）。
    decided = scripted.get(run.variant) or (
        f"包在{where('bag')}"
        + ("，包还开着口" if not w.get("bag", "closed") else "")
        + (f"，药盒在{where('pillbox')}" if where("pillbox") != where("bag") else "")
        + ("，车已经到终点" if w.flags.get("stopped") else "，车还在路上")
    )
    return {
        "包在谁那里": where("bag"),
        "药盒在谁那里": where("pillbox"),
        "甲在": where("jia"),
        "司机在": where("driver"),
        "车已经到终点": bool(w.flags.get("stopped")),
        "结局": decided,
    }
