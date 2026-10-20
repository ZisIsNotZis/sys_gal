"""《借条》的模型试点：三个角色各自决定，世界只负责裁。

这一步才第一次出现 `[角色]` 的动作。每次运行一个唯一目录，绝不覆盖：
`runs/agent-<时间>-<pid>/`。
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.agent import ChatProvider, DecisionParseError, agent_turn
from engine.core import World
from engine.events import EventLog, dump_log
from engine.rules import drain
from engine.seed import load
from engine.surface import block
from library import EFFECTS
from stories.common import context_view, transcript

from .scenario import DEFAULT_SEED, summary

HERE = Path(__file__).with_name("runs")


@dataclass
class AgentRun:
    variant: str
    world: World
    log: EventLog
    items: list[dict[str, Any]] = field(default_factory=list)
    receipts: list[Any] = field(default_factory=list)
    title: str = "《借条》"
    summary: dict[str, Any] = field(default_factory=dict)
    messages: list[dict[str, Any]] = field(default_factory=list)


def play_agents(model: str, turns_each: int = 4, seed_path: Path = DEFAULT_SEED,
                order: tuple[str, ...] = ("jia", "yi", "bing"),
                provider: Any | None = None) -> AgentRun:
    world = load(seed_path)
    log = EventLog()
    run = AgentRun(variant=f"agent-{model}", world=world, log=log)
    llm = provider or ChatProvider(model=model)
    history: dict[str, list[dict[str, Any]]] = {}

    for round_no in range(turns_each):
        for actor in order:
            for event in drain(world, log, EFFECTS):
                run.items.append({"kind": "world", "at": event.at, "what": event.what,
                                  "perceived": [(a["e"], a["v"]) for a in event.atoms
                                                if a.get("op") == "remember"]})
            try:
                turn = agent_turn(world, log, actor, llm, history)
            except DecisionParseError as exc:
                run.items.append({
                    "kind": "turn", "at": world.clock, "actor": actor, "verb": "-",
                    "target": "", "to": "", "ok": False,
                    "texts": [], "reason": "模型的工具调用无法解析", "hints": [],
                    "note": {}, "context": block(world, actor), "context_used": True,
                    "decided_by": "agent", "step": round_no * len(order) + order.index(actor) + 1,
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
                "decided_by": "agent", "step": round_no * len(order) + order.index(actor) + 1,
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


def write_artifacts(run: AgentRun, tag: str) -> Path:
    out = HERE / f"agent-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{tag}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "transcript.md").write_text(transcript(run, "《借条》模型试点轨迹"), encoding="utf-8")
    (out / "context.md").write_text(context_view(run), encoding="utf-8")
    (out / "events.jsonl").write_text(dump_log(run.log), encoding="utf-8")
    (out / "run.json").write_text(json.dumps({
        "summary": run.summary,
        "items": run.items,
        "digest": run.world.digest(),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    model = argv[0] if argv else os.environ.get("V5_MODEL", "github_copilot/gpt-6-luna")
    turns = int(argv[1]) if len(argv) > 1 else 4
    run = play_agents(model, turns_each=turns)
    out = write_artifacts(run, model.replace("/", "_"))
    role_turns = [i for i in run.items if i["kind"] == "turn"]
    refused = [i for i in role_turns if not i["ok"]]
    print(f"模型：{model}；{len(role_turns)} 个动作（{len(refused)} 次被拒）")
    print(f"结局：{run.summary['结局']}")
    print(f"轨迹目录：{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
