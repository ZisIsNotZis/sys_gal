"""《夜市》：M4 的脚本演员。

四条路，四种结局：认账 / 推给下一个 / 拿不回来 / 当众澄清。
结局由这一局末尾世界里的四件事拼出（条子在谁手里、经过谁的手、那句话是私下还是当众、
落在收摊前还是收摊后），不按路径名查表：两条路在这四件事上相同就是同一个结局。
脚本只证明"这件事物理上做得到"，不代表角色的意愿。

三件被这条路测到的事：
- 制度角色：只有 `institution` 身份的人能 `impound`，而且本子上恰好留一行；
- 公开/私下：`speak` 带 `to` 时只有那个人听见内容，旁人只看见两人在低声说话；
- 期限：管理处到点关门上锁，晚到的人在回执里撞上它。
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

#: 押金条的实体 id。契约里的 `note` 与 `v5_lint` 的保留词表、以及
#: `engine/events.py` 里的 `"note"` 字面量同名，会被两条门当成故事名词泄漏；
#: 这个名字是它的唯一住所（见 M4 报告）。
NOTE_ID = "deposit_note"

#: 管理员按制度把货收走，搬进管理处，再回到摊区。四条路共用这一段。
_IMPOUND_GOODS: list[tuple[str, str, dict[str, Any]]] = [
    ("warden", "impound", {"target": "货"}),
    ("warden", "move", {"target": "夜市"}),
    ("warden", "move", {"target": "管理处"}),
    ("warden", "place", {"target": "货", "to": "管理处"}),
    ("warden", "move", {"target": "夜市"}),
    ("warden", "move", {"target": "摊区"}),
]

SCRIPTS: dict[str, list[tuple[str, str, dict[str, Any]]]] = {
    # A：甲私下认账——条子一直在他手里，话只让管理员一个人听见
    "a": [
        *_IMPOUND_GOODS,
        ("a", "read", {"target": "通知"}),
        ("a", "speak", {"text": "这摊是我的，货我认；条子在我手里，不用登记。",
                        "to": "管理员"}),
        ("warden", "read", {"target": "收件记录"}),
    ],
    # B：甲当众把条子推给乙，乙当众再推给丙
    "b": [
        *_IMPOUND_GOODS,
        ("a", "speak", {"text": "这摊今晚是乙替我看着的，条子该他拿着。"}),
        ("a", "give", {"target": "押金条", "to": "摊主乙"}),
        ("b", "speak", {"text": "我只替丙看了一会儿，条子给他。"}),
        ("b", "give", {"target": "押金条", "to": "摊主丙"}),
        ("c", "speak", {"text": "条子在我手里，货不是我的。"}),
    ],
    # C：条子被收进管理处，甲到的时候门已经关了
    "c": [
        *_IMPOUND_GOODS,
        ("a", "read", {"target": "通知"}),
        ("a", "speak", {"text": "我收摊前来领，你先别记。", "to": "管理员"}),
        ("warden", "impound", {"target": "押金条"}),
        ("warden", "move", {"target": "夜市"}),
        ("warden", "move", {"target": "管理处"}),
        ("warden", "place", {"target": "押金条", "to": "管理处"}),
        ("a", "move", {"target": "夜市"}),
        ("a", "move", {"target": "巷口"}),
        # 巷口有人叫他过去说两句话，等回到摊区，管理处已经关了。
        *[("a", "wait", {}) for _ in range(8)],
        ("a", "move", {"target": "夜市"}),
        ("a", "move", {"target": "管理处"}),
        ("a", "open", {"target": "管理处"}),
        ("a", "speak", {"text": "门锁了。"}),
    ],
    # D：甲当众把账推给乙，乙当众顶回去，管理员念记录，甲当众认下
    "d": [
        *_IMPOUND_GOODS,
        ("a", "speak", {"text": "这摊昨晚是乙看的，货该他认。"}),
        ("b", "speak", {"text": "我只看了一会儿，本子上收的是摊区，不是我的名字。"}),
        ("warden", "read", {"target": "收件记录"}),
        ("warden", "speak", {"text": "本子上记的是摊区，没写谁。"}),
        ("a", "speak", {"text": "我认：摊是我的，条子在我手里。"}),
    ],
}



@dataclass
class Run:
    variant: str
    world: World
    log: EventLog
    items: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[Receipt] = field(default_factory=list)
    note_trail: list[str | None] = field(default_factory=list)
    title: str = "《夜市》"
    summary: dict[str, Any] = field(default_factory=dict)


def _world_item(event: Event) -> dict[str, Any]:
    perceived = [(a["e"], a["v"]) for a in event.atoms if a.get("op") == "remember"]
    return {"kind": "world", "at": event.at, "what": event.what, "perceived": perceived}


def play(variant: str = "a", seed_path: Path = DEFAULT_SEED) -> Run:
    world = load(seed_path)
    log = EventLog()
    run = Run(variant=variant, world=world, log=log, note_trail=[world.container(NOTE_ID)])

    for step, (actor, verb, args) in enumerate(SCRIPTS[variant], start=1):
        for event in drain(world, log, EFFECTS):
            run.items.append(_world_item(event))
        context = block(world, actor)
        receipt = submit(world, log, actor, verb, dict(args))
        run.receipts.append(receipt)
        target = receipt.event.note.get("target") if receipt.event else None
        holder = world.container(NOTE_ID)
        run.items.append({
            "kind": "turn", "at": receipt.event.at if receipt.event else world.clock,
            "actor": actor, "verb": verb,
            "target": world.entities[target].name if target in world.entities else dict(args).get("target", ""),
            "to": _addressed(world, args),
            "ok": receipt.ok, "texts": list(receipt.texts),
            "reason": receipt.reason, "hints": list(receipt.hints), "note": receipt.note,
            "context": context, "context_used": False,
            "decided_by": "script", "step": step,
            # 这一步做完，条子在谁手里（`结局` 与 `决定性那句话` 读的就是它）
            "note_holder": holder,
        })
        if holder != run.note_trail[-1]:
            run.note_trail.append(holder)
    run.summary = summary(run)
    return run


def _addressed(world: World, args: dict[str, Any]) -> str:
    """这一句话是对谁说的（解析后的名字）；空串就是当众。"""
    to = args.get("to")
    if not to:
        return ""
    if to in world.entities:
        return world.entities[to].name
    return str(to)


def _close_at(run: Run) -> int | None:
    for event in run.log:
        if event.kind == "world" and event.what == "close":
            return event.at
    for when, _seq, effect in run.world.schedule:
        if effect.get("kind") == "close":
            return when
    return None


def _decisive_turn(run: Run) -> dict[str, Any] | None:
    """决定性的一句话：拿着条子的那个人最后说的那句（说完条子还在他手里）。"""
    spoke = [i for i in run.items if i["kind"] == "turn" and i["verb"] == "speak"]
    holding = [i for i in spoke if i.get("note_holder") == i["actor"]]
    chosen = holding or spoke
    return chosen[-1] if chosen else None


def _audience(turn: dict[str, Any] | None) -> str:
    """那句话是说给一个人听的，还是在场的人都听见了。"""
    if turn is None:
        return "一句话也没说"
    return f"只对{turn['to']}一个人说" if turn["to"] else "在场的人都听见"


def _ending(facts: dict[str, Any], said: dict[str, Any] | None) -> str:
    """结局只由 `facts` 里的四件事拼出；没有第五件，也不从路径名取。"""
    before = facts["结局落在收摊之前"]
    when = ("不知道收摊是什么时候" if before is None
            else "落在收摊之前" if before else "落在收摊之后")
    return (f"条子在{facts['押金条最后在谁手里']}，"
            f"路上经过{'→'.join(facts['押金条经过谁的手'])}，"
            f"{_audience(said)}，{when}")


def summary(run: Run) -> dict[str, Any]:
    w = run.world

    def where(eid: str) -> str:
        holder = w.container(eid)
        if holder is None:
            return "不在世界里"
        return w.entities[holder].name

    turns = [i for i in run.items if i["kind"] == "turn"]
    said = _decisive_turn(run)
    close_at = _close_at(run)
    last_at = turns[-1]["at"] if turns else None
    facts: dict[str, Any] = {
        "押金条最后在谁手里": where(NOTE_ID),
        "押金条经过谁的手": [w.entities[h].name if h in w.entities else "不在"
                             for h in run.note_trail],
        "决定性那句话": ("私下" if said["to"] else "当众") if said else "没有开口",
        "结局落在收摊之前": (last_at < close_at) if (last_at is not None and close_at is not None) else None,
        "收摊时间": close_at,
    }
    facts["结局"] = _ending(facts, said)
    return facts
