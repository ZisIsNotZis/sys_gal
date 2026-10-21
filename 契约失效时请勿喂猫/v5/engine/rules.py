"""P8 意愿 + P9 规则 + 编排。

一次意愿 = （动词，指称，参数）。引擎先解析指称，再按规则判合法，然后
要么产生原子效果与事件，要么产生拒绝回执（为什么不成、眼前可行的有哪些）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .core import World, apply_atom
from .events import Event, EventLog
from .render import refer
from .resolve import Resolution, in_sight, resolve, resolve_place

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
    entity_args: tuple[str, ...] = ("target",)   # 这些参数是世界的指称，由引擎解析
    doc: str = ""                                # 一句话说明（给模型看，也给人看）
    label: str = ""                              # 给人看的动词名（中文）
    params: tuple[tuple[str, str, bool], ...] = ()   # (名字, 说明, 是否必填)


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
    interrupted: bool = False          # 不是“没成”，而是做着做着被世界截断


def _resolve_args(world: World, actor: str, verb: str, rule: "Rule",
                  args: dict[str, Any]) -> Resolution | None:
    out = dict(args)
    for name in rule.entity_args:
        if name not in out:
            continue
        if name == "target" and verb == "move":
            res = resolve_place(world, actor, out[name])
        else:
            res = resolve(world, actor, out[name])
        if not res:
            return res
        out[name] = res.eid
    args.clear()
    args.update(out)
    return None


def _still_possible(world: World, rule: "Rule", ctx: Ctx) -> str | None:
    """世界在动作飞行途中变过了：把规则重新问一次。

    规则是纯函数，问几次都一样；所以第二次问出来的拒绝，就是世界在动作中途把前提抽走了。
    """
    for name in rule.entity_args:
        eid = ctx.args.get(name)
        if isinstance(eid, str) and eid not in world.entities:
            return "那样东西已经不在了"
    return rule.when(ctx)


def _cut_render(world: World, actor: str) -> list[tuple[str, str]]:
    """动作被截断的样子：本人知道自己没做完，在场的人只看见动作停在半路。

    这里只有动作，没有解释，也没有事件层元数据（守则第三条）。
    """
    out: list[tuple[str, str]] = [(actor, "你的动作停在半路，没能做完。")]
    for p in world.entities:
        if p != actor and world.kind_of(p) == "person" and in_sight(world, p, actor):
            out.append((p, f"{refer(world, p, actor)}的动作停在半路。"))
    return out


def _cut(world: World, log: EventLog, ctx: Ctx, rule: "Rule", reason: str,
         started_at: int, finish: int, requested: dict[str, Any]) -> Receipt:
    """动作在中途被截断：P2 要求一次意愿要么全成要么全不成，所以它一样都不留。

    留下的只有两样：世界停在截断的那一刻（时钟已由 tick 事件推到这里），
    以及“这件事曾经在飞”被本人和在场的人看见。"""
    actor = ctx.actor
    atoms: list[dict[str, Any]] = []
    texts: list[str] = []
    for recipient, text in _cut_render(world, actor):
        atoms.append({"op": "remember", "e": recipient, "at": world.clock, "v": text})
        if recipient == actor:
            texts.append(text)
    for atom in atoms:
        apply_atom(world, atom)
    event = Event(id=log.next_id(), at=world.clock, kind="interrupted", actor=actor,
                  what=ctx.verb, atoms=tuple(atoms),
                  note={"reason": reason, "target": requested.get("target"),
                        "started_at": started_at, "would_finish_at": finish,
                        "digest_after": world.digest()})
    log.append(event)
    hints = rule.hints(ctx) if rule.hints else []
    return Receipt(False, ctx.verb, reason=reason, hints=list(hints), texts=texts,
                   interrupted=True, event=event)


def submit(world: World, log: EventLog, actor: str, verb: str,
           args: dict[str, Any],
           effects: dict[str, Callable[[World, dict], list[dict]]] | None = None) -> Receipt:
    """执行一次意愿。返回回执；世界状态的变化全部落在一个事件里。

    `effects` 是制度与物性的处理表。给了它，一个带耗时的动作就是一段**区间**：
    落在区间里的世界效果按时间顺序发生，然后在它们留下的新世界上把规则重新问一次——
    前提被抽走，这个动作就做不完，回到 P2 的全不成，落成一条 `interrupted` 事件。
    不给它，动作照旧一口气做完（S1/S2 的剧本演员走的就是这条路）。

    边界：到期点正好等于完成时刻**不算**被截断——那一刻你已经做完了。
    """
    if verb not in REGISTRY:
        raise KeyError(f"库里没有这个动词：{verb}")
    rule = REGISTRY[verb]
    raw = dict(args)
    bad = _resolve_args(world, actor, verb, rule, raw)
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
    cost = rule.cost or 0
    finish = started_at + cost
    if effects is not None and cost:
        drain(world, log, effects)          # 已经到期的不算“在飞”，先让它发生
        while True:
            due = world.next_due()
            if due is None or due >= finish:
                break
            advance_to(world, log, due)
            drain(world, log, effects)
            reason = _still_possible(world, rule, ctx)
            if reason:
                return _cut(world, log, ctx, rule, reason, started_at, finish, args)

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


def advance_to(world: World, log: EventLog, when: int) -> Event | None:
    """时间走到 `when`，并把它记成一个事件：时钟的变化同样必须能被重放。"""
    if when <= world.clock:
        return None
    atom = {"op": "clock", "to": when}
    apply_atom(world, atom)
    return log.append(Event(id=log.next_id(), at=when, kind="tick", actor=None,
                            what="clock", atoms=(atom,),
                            note={"digest_after": world.digest()}))


def advance_idle(world: World, log: EventLog,
                 effects: dict[str, Callable[[World, dict], list[dict]]]) -> list[Event]:
    """没有人在动作时，时间自己走到下一个排程点。

    时钟的走动也记成一个 tick 事件：它同样是世界状态的变化，必须能被重放。
    """
    out: list[Event] = []
    while True:
        nxt = world.next_due()
        if nxt is not None:
            advance_to(world, log, nxt)
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
