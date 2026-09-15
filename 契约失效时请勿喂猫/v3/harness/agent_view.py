"""Render a saved trajectory from one agent's angle.

A full trajectory stores the world's omniscient event log plus every actor's
latest session snapshot. Viewing "from the agent's side" means replaying only
what that agent could perceive and decide, plus the exact transcript the model
saw. This module exports a readable per-agent view without changing the trace
format.

Usage:
  python3 -m harness.agent_view runs/<trajectory>.json --actor lin-yao
  python3 -m harness.agent_view runs/<trajectory>.json --all --out runs/views
  python3 -m harness.agent_view runs/<trajectory>.json --actor lin-yao --chatml
  python3 -m harness.agent_view runs/<trajectory>.json --actor lin-yao --history

--chatml renders the flat provider-visible stream instead: one time-ordered
[system]/[user]/[assistant] sequence with world feedback as plain [user]
messages, full untruncated content, and no analysis sections. The session
transcript is already in time order, so it is the whole view -- but it holds
only the actor's current compacted context, not their past.

--history reconstructs the complete per-actor log from story start to end out
of the trace: every perception, every submitted action, every world result.
It is the long form the compacted session snapshot cannot show.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .prompt import _affordance_sentence, _event_sentence


def _history_perception(perception: Mapping[str, Any], affordances: list[Mapping[str, Any]],
                        seen: dict[str, set]) -> str:
    """History-mode perception: timestamped event diary, constants deduplicated.

    Each event line carries its exact time (everything since the last poll);
    constant state (entity descriptions, location knowledge) is shown only on
    first appearance; affordances render as a bullet list; others' wait/sleep
    produce no observable events (a person standing still is not a sight).
    """
    observer = str(perception.get("observer", ""))
    lines = [f"The time is {perception.get('time')}. You are at {perception.get('location')}."]
    if perception.get("busy_until"):
        lines.append(f"You are occupied with your current action until {perception['busy_until']}.")
    for message in perception.get("inbox", []):
        lines.append(f"You receive a message from {message.get('from')}: {message.get('text')}")
    for fact in perception.get("operational_facts", []):
        action = fact.get("action", {})
        line = ("Operational fact: your previous action was rejected and changed nothing. "
                f"Action={action.get('kind')} args={action.get('args')}. "
                f"Reason: {fact.get('reason')}.")
        alternatives = fact.get("alternatives")
        if alternatives:
            line += " The world suggests instead: " + "; ".join(str(a) for a in alternatives) + "."
        lines.append(line)
    for event in perception.get("events", []):
        kind = event.get("kind")
        payload = event.get("payload", {})
        if (event.get("actor") != observer and kind in {"action_started", "action_completed"}
                and payload.get("action") in {"wait", "sleep"}):
            continue
        stamp = str(event.get("time", ""))[11:19]
        lines.append(f"[{stamp}] " + _event_sentence(event, observer,
                                                      str(perception.get("location", ""))))
    for entity, description in perception.get("descriptions", {}).items():
        if entity not in seen["descriptions"]:
            seen["descriptions"].add(entity)
            lines.append(f"You can currently examine {entity}: {description}")
    for place, note in (perception.get("knowledge") or {}).items():
        text = str(note.get("public") if isinstance(note, dict) else note)
        if text and (place, text) not in seen["knowledge"]:
            seen["knowledge"].add((place, text))
            lines.append(f"You know: {place} — {text}")
    if affordances:
        lines.append("You can concretely:")
        lines.extend(f"  - {_affordance_sentence(x)}" for x in affordances)
    return "\n".join(lines)


def render_history_view(trajectory: Mapping[str, Any], actor: str) -> str:
    """Full-story ChatML stream for one actor, replayed from the trace.

    Reconstructs every turn from story start to end: [user] perception,
    [assistant] submitted action — what the actor really saw and did each
    turn. Accepted actions carry no receipt: the outcome appears, timestamped,
    in the next perception's events. Rejections and failures keep an
    immediate corrective message.

    The trace does not record *when* each compaction fired, so compaction
    cannot be placed at exact mid-log points. It is therefore rendered as a
    marked boundary after the lived log: the compacted memory blocks that
    replaced earlier conversation, then the verbatim live context the actor's
    next request would actually include.
    """
    lines: list[str] = [f"# Full history view: {actor}"]
    session = trajectory.get("sessions", {}).get(actor, {})
    messages = session.get("messages", [])
    system = next((m.get("content") for m in messages if m.get("role") == "system"), None)
    if system:
        lines.append("\n[system]\n" + str(system))
    events_by_id = {e.get("id"): e for e in trajectory.get("world_events", [])}
    turns = [t for t in trajectory.get("agent_turns", []) if t.get("actor") == actor]
    seen: dict[str, set] = {"descriptions": set(), "knowledge": set()}
    for turn in turns:
        perception = turn.get("perception", {})
        affordances = turn.get("affordances", [])
        lines.append("\n[user]\n" + _history_perception(perception, affordances, seen))
        intention = turn.get("intention")
        if intention:
            action = {"kind": intention["kind"], "args": intention.get("args", {})}
            lines.append("\n[assistant]\n" + json.dumps(action, ensure_ascii=False))
        else:
            lines.append("\n[assistant]\n(no action)")
        result = str(turn.get("result"))
        error = turn.get("error")
        if result == "submitted":
            pass
        elif result == "rejected":
            lines.append(f"\n[user]\nThe world rejects your action: {error} Nothing changed.")
        elif result == "retryable_failure":
            lines.append(f"\n[user]\nA temporary communication failure prevented your turn "
                         f"from reaching the world: {error}. No action was submitted.")
        elif result in {"wall_clock_deadline", "agent_error", "decision_timeout", "engine_error"}:
            lines.append(f"\n[user]\nThe world could not carry out your turn ({result}): {error}")
        else:
            names = [events_by_id[i].get("kind") for i in turn.get("event_ids", [])
                     if i in events_by_id]
            lines.append(f"\n[user]\nResult {result}: {', '.join(map(str, names)) or 'no events'}")
    memories = session.get("compacted_memories", [])
    if memories:
        lines.append(
            "\n---\n"
            "Compaction boundary. The lived log above was periodically compressed by the "
            "session; the trace does not record the exact turn each compression fired. Below, "
            "each --- separated block is one compacted memory that replaced the preceding "
            "conversation in the actor's context.")
        for memory in memories:
            lines.append("\n---\n" + str(memory.get("content", "")))
    if messages:
        lines.append("\n---\nCurrent live context (verbatim; exactly what the actor's next "
                     "request would include):")
        for message in messages:
            role = str(message.get("role", "?"))
            tag = "assistant" if role == "assistant" else "system" if role == "system" else "user"
            lines.append(f"\n[{tag}]\n{message.get('content', '')}")
    return "\n".join(lines)


def render_chatml_view(trajectory: Mapping[str, Any], actor: str) -> str:
    """Flat provider-visible stream: only [system]/[user]/[assistant] in order."""
    lines: list[str] = [f"# ChatML view: {actor}"]
    session = trajectory.get("sessions", {}).get(actor, {})
    for message in session.get("messages", []):
        role = str(message.get("role", "?"))
        tag = "assistant" if role == "assistant" else "system" if role == "system" else "user"
        lines.append(f"\n[{tag}]\n{message.get('content', '')}")
    return "\n".join(lines)


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
    parser.add_argument("--chatml", action="store_true",
                        help="flat [system]/[user]/[assistant] stream, full content, no sections")
    parser.add_argument("--history", action="store_true",
                        help="full per-actor log from story start to end, replayed from the trace")
    args = parser.parse_args(argv)
    path = Path(args.trajectory)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"agent_view: cannot read trajectory {path}: {exc}") from exc
    actors = list(data.get("sessions", {})) or sorted(
        {t["actor"] for t in data.get("agent_turns", [])})
    if args.actor:
        actors = [args.actor]
    elif not args.all:
        actors = [actors[0]] if actors else []
    for actor in actors:
        if args.history:
            view = render_history_view(data, actor)
        elif args.chatml:
            view = render_chatml_view(data, actor)
        else:
            view = render_agent_view(data, actor)
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            suffix = "history" if args.history else "view"
            path = args.out / f"{Path(args.trajectory).stem}.{actor}.{suffix}.md"
            path.write_text(view + "\n", encoding="utf-8")
            print(path)
        else:
            print(view)
            print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
