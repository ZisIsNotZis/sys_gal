"""Render a saved trajectory from one agent's angle.

A full trajectory stores the world's omniscient event log plus every actor's
latest session snapshot. Viewing "from the agent's side" means replaying only
what that agent could perceive and decide, plus the exact transcript the model
saw. This module exports a readable per-agent view without changing the trace
format.

Usage:
  python3 -m harness.agent_view runs/<trajectory>.json --actor lin-yao
  python3 -m harness.agent_view runs/<trajectory>.json --all --out runs/views
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def render_agent_view(trajectory: Mapping[str, Any], actor: str) -> str:
    lines: list[str] = []
    lines.append(f"# Agent view: {actor}")
    session = trajectory.get("sessions", {}).get(actor, {})
    if session:
        lines.append("\n## Session transcript (exactly what the model saw, in order)")
        for message in session.get("messages", []):
            tag = str(message.get("name") or message.get("role") or "?")
            content = str(message.get("content", ""))
            lines.append(f"\n[{tag}]\n{content}")
        memories = session.get("compacted_memories", [])
        if memories:
            lines.append("\n## Compacted memories (survived context pruning)")
            for memory in memories:
                lines.append("- " + str(memory.get("content", ""))[:400])
        facts = session.get("authoritative_facts", [])
        if facts:
            lines.append("\n## Authoritative world feedback delivered (verbatim, in order)")
            for fact in facts:
                lines.append(f"{fact.get('order', '?')}. [{fact.get('source')}] {fact.get('content')}")
        lines.append("\n## Private state (goals / beliefs / memories / notes)")
        lines.append(json.dumps(session.get("state", {}), ensure_ascii=False, indent=2))

    turns = [t for t in trajectory.get("agent_turns", []) if t.get("actor") == actor]
    lines.append(f"\n## Decision log ({len(turns)} turns)")
    for t in turns:
        perception = t.get("perception", {})
        intention = t.get("intention")
        kind = intention["kind"] if intention else "none"
        args = dict(intention["args"]) if intention else {}
        arg_text = json.dumps(args, ensure_ascii=False)[:140]
        line = (f"[{str(perception.get('time', '?'))[11:16]}] at {perception.get('location')} "
                f"| -> {kind} {arg_text} | {t.get('result')}")
        if t.get("error"):
            line += f" | {str(t['error'])[:90]}"
        inbox = perception.get("inbox", [])
        if inbox:
            received = "; ".join(f"{m.get('from')}: {str(m.get('text'))[:70]}" for m in inbox)
            line += f" || received: {received}"
        lines.append(line)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--actor")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out", type=Path, help="directory for per-actor view files")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.trajectory).read_text(encoding="utf-8"))
    actors = list(data.get("sessions", {})) or sorted(
        {t["actor"] for t in data.get("agent_turns", [])})
    if args.actor:
        actors = [args.actor]
    elif not args.all:
        actors = [actors[0]] if actors else []
    for actor in actors:
        view = render_agent_view(data, actor)
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            path = args.out / f"{Path(args.trajectory).stem}.{actor}.view.md"
            path.write_text(view + "\n", encoding="utf-8")
            print(path)
        else:
            print(view)
            print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
