"""模型演员的回路：一支故事只提供自己的种子、登场顺序、摘要与标题，其余都在这里。

为什么抽出来：M3 的试点只有《借条》一份报告，而"这套机制能让模型自己走出它的路"
要在第二支故事上再成立一次，才算这支阶梯上的一条结论（人的答案，2026-10-23：
`docs/V5-ROADMAP.md` §3）。回路若每支故事各写一遍，第二支故事过的就是另一套检查；
写在一处，第二支故事过的是同一套。

回路做的三件事：每一回合把这一角色**当时的全部上下文**交给模型；世界裁它的意图；
被拒绝的意图连同"为什么、眼前有什么"回灌给它。每个动作记下 `decided_by` 与
`context_used`，因为一份回答不了"他当时知道什么"的轨迹不算证据。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from engine.agent import ChatProvider, DecisionParseError, agent_turn
from engine.core import World
from engine.events import EventLog, dump_log
from engine.rules import drain
from engine.seed import load
from engine.surface import block
from library import EFFECTS

from .common import context_view, transcript


@dataclass
class AgentRun:
    variant: str
    world: World
    log: EventLog
    items: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[Any] = field(default_factory=list)
    title: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    messages: list[dict[str, Any]] = field(default_factory=list)


def play(model: str, *, seed_path: Path, order: tuple[str, ...],
         summary: Callable[[Any], dict[str, Any]], title: str,
         turns_each: int = 4, provider: Any | None = None) -> AgentRun:
    world = load(seed_path)
    log = EventLog()
    run = AgentRun(variant=f"agent-{model}", world=world, log=log, title=title)
    llm = provider or ChatProvider(model=model)
    history: dict[str, list[dict[str, Any]]] = {}

    for round_no in range(turns_each):
        for actor in order:
            for event in drain(world, log, EFFECTS):
                run.items.append({"kind": "world", "at": event.at, "what": event.what,
                                  "perceived": [(a["e"], a["v"]) for a in event.atoms
                                                if a.get("op") == "remember"]})
            step = round_no * len(order) + order.index(actor) + 1
            try:
                turn = agent_turn(world, log, actor, llm, history)
            except DecisionParseError as exc:
                run.items.append({
                    "kind": "turn", "at": world.clock, "actor": actor, "verb": "-",
                    "target": "", "to": "", "ok": False,
                    "texts": [], "reason": "模型的工具调用无法解析", "hints": [],
                    "note": {}, "context": block(world, actor), "context_used": True,
                    "decided_by": "agent", "step": step,
                    "raw": exc.raw, "latency": 0.0, "prompt": {},
                })
                continue
            run.receipts.append(turn.receipt)
            target = turn.receipt.event.note.get("target") if turn.receipt.event else None
            run.items.append({
                "kind": "turn", "at": turn.at, "actor": actor,
                "verb": turn.decision.verb,
                "target": world.entities[target].name if target in world.entities
                          else str(turn.decision.args.get("target", "")),
                "to": str(turn.decision.args.get("to", "")),
                "ok": turn.receipt.ok, "texts": list(turn.receipt.texts),
                "reason": turn.receipt.reason, "hints": list(turn.receipt.hints),
                "note": turn.receipt.note,
                "context": block(world, actor), "context_used": True,
                "decided_by": "agent", "step": step,
                "raw": turn.decision.raw,
                "latency": turn.decision.latency,
                "prompt": turn.context,
            })
            run.messages.append({"actor": actor, "at": turn.at,
                                 "system": turn.context["system"],
                                 "turn": turn.context["turn"],
                                 "messages": turn.messages})
    run.summary = summary(run)
    return run


def write_artifacts(run: AgentRun, out: Path, transcript_title: str) -> Path:
    """四个文件：故事视图、上下文审计、可重放账本、摘要。目录已由调用方算好（唯一）。"""
    out.mkdir(parents=True, exist_ok=False)
    (out / "transcript.md").write_text(transcript(run, transcript_title), encoding="utf-8")
    (out / "context.md").write_text(context_view(run), encoding="utf-8")
    (out / "events.jsonl").write_text(dump_log(run.log), encoding="utf-8")
    (out / "run.json").write_text(json.dumps({
        "summary": run.summary,
        "items": run.items,
        "digest": run.world.digest(),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
