"""P8 意愿 + P9 规则 + 编排。

一次意愿 = （动词，指称，参数）。引擎先解析指称，再按规则判合法，然后
要么产生原子效果与事件，要么产生拒绝回执（为什么不成、眼前可行的有哪些）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .core import World, apply_atom
from .events import Event, EventLog
from .resolve import Resolution, resolve, resolve_place

#: 动词 → 规则。库负责填，引擎不认识任何具体动词。
REGISTRY: dict[str, "Rule"] = {}


@dataclass(frozen=True)
class Ctx:
    world: World
    actor: str
    verb: str
    args: dict[str, Any]

    def name(self, eid: str | None) -> str:
        return self.world.entities[eid].name if eid else ""

    @property
    def target(self) -> str:
        return self.args["target"]


@dataclass(frozen=True)
class Rule:
    verb: str
    used_by: tuple[str, ...]
    when: Callable[[Ctx], str | None]
    atoms: Callable[[Ctx], list[dict[str, Any]]]
    render: Callable[[Ctx], list[tuple[str, str]]]
    cost: int = 1
    hints: Callable[[Ctx], list[str]] | None = None


def register(rule: Rule) -> Rule:
    if rule.verb in REGISTRY:
        raise ValueError(f"动词重复登记：{rule.verb}")
    REGISTRY[rule.verb] = rule
    return rule


@dataclass
class Receipt:
    ok: bool
    what: str
    reason: str = ""
    hints: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    note: str = ""
    event: Event | None = None


def _resolve_args(world: World, actor: str, verb: str,
                  args: dict[str, Any]) -> Resolution | None:
    out = dict(args)
    if "target" in out:
        res = resolve_place(world, actor, out["target"]) if verb == "move" else resolve(world, actor, out["target"])
        if not res:
            return res
        out["target"] = res.eid
    if "to" in out:
        res = resolve(world, actor, out["to"])
        if not res:
            return res
        out["to"] = res.eid
    args.clear()
    args.update(out)
    return None


def submit(world: World, log: EventLog, actor: str, verb: str,
           args: dict[str, Any]) -> Receipt:
    """执行一次意愿。返回回执；世界状态的变化全部落在一个事件里。"""
    if verb not in REGISTRY:
        raise KeyError(f"库里没有这个动词：{verb}")
    rule = REGISTRY[verb]
    raw = dict(args)
    bad = _resolve_args(world, actor, verb, raw)
    if bad is not None:
        event = Event(id=log.next_id(), at=world.clock, kind="refused", actor=actor,
                      what=verb, atoms=(), note={"reason": bad.reason,
                                                 "hints": list(bad.hints),
                                                 "requested": args,
                                                 "digest_after": world.digest()})
        log.append(event)
        return Receipt(False, verb, reason=bad.reason, hints=list(bad.hints), event=event)

    ctx = Ctx(world, actor, verb, raw)
    reason = rule.when(ctx)
    if reason:
        hints = rule.hints(ctx) if rule.hints else []
        event = Event(id=log.next_id(), at=world.clock, kind="refused", actor=actor,
                      what=verb, atoms=(), note={"reason": reason, "hints": list(hints),
                                                 "requested": args,
                                                 "digest_after": world.digest()})
        log.append(event)
        return Receipt(False, verb, reason=reason, hints=list(hints), event=event)

    started_at = world.clock
    atoms: list[dict[str, Any]] = list(rule.atoms(ctx))
    texts: list[str] = []
    for recipient, text in rule.render(ctx):
        atoms.append({"op": "remember", "e": recipient, "at": world.clock, "v": text})
        if recipient == actor:
            texts.append(text)
    if rule.cost:
        atoms.append({"op": "clock", "to": world.clock + rule.cost})
    for atom in atoms:
        apply_atom(world, atom)
    event = Event(id=log.next_id(), at=started_at, kind="intent",
                  actor=actor, what=verb, atoms=tuple(atoms),
                  note={"target": raw.get("target"), "digest_after": world.digest()})
    log.append(event)
    return Receipt(True, verb, texts=texts, event=event)


def advance_idle(world: World, log: EventLog,
                 effects: dict[str, Callable[[World, dict], list[dict]]]) -> list[Event]:
    """没有人在动作时，时间自己走到下一个排程点。

    时钟的走动也记成一个 tick 事件：它同样是世界状态的变化，必须能被重放。
    """
    out: list[Event] = []
    while True:
        nxt = world.next_due()
        if nxt is not None and nxt > world.clock:
            atom = {"op": "clock", "to": nxt}
            apply_atom(world, atom)
            event = Event(id=log.next_id(), at=nxt, kind="tick", actor=None,
                          what="clock", atoms=(atom,),
                          note={"digest_after": world.digest()})
            log.append(event)
        fired = drain(world, log, effects)
        out += fired
        if world.flags.get("stopped"):
            break
        if not fired and (world.next_due() is None or world.next_due() <= world.clock):
            break
    return out


def drain(world: World, log: EventLog,
          effects: dict[str, Callable[[World, dict], list[dict]]]) -> list[Event]:
    """把到期的世界效果按时间顺序执行（制度与物性，不是命运）。"""
    fired: list[Event] = []
    while True:
        entry = world.pop_next_due()
        if entry is None:
            break
        when, seq, effect = entry
        world.clock = max(world.clock, when)
        handler = effects.get(effect.get("kind", ""))
        if handler is None:
            raise KeyError(f"没有处理这种世界效果：{effect}")
        atoms = [{"op": "unschedule", "at": when, "seq": seq}] + list(handler(world, effect))
        for atom in atoms:
            apply_atom(world, atom)
        event = Event(id=log.next_id(), at=world.clock, kind="world", actor=None,
                      what=effect["kind"], atoms=tuple(atoms),
                      note={"effect": effect, "digest_after": world.digest()})
        log.append(event)
        fired.append(event)
    return fired
