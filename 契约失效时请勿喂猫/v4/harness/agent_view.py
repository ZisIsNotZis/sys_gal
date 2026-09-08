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

from .prompt import _affordance_sentence, _clean_description, _event_sentence


def _history_perception(perception: Mapping[str, Any], affordances: list[Mapping[str, Any]],
                        seen: dict[str, set]) -> str:
    """History-mode perception: timestamped event diary, constants deduplicated.

    Each event line carries its exact time (everything since the last poll);
    constant state (entity descriptions, location knowledge) is shown only on
    first appearance; affordances render as a bullet list; others' wait/sleep
    produce no observable events (a person standing still is not a sight).
    """
    observer = str(perception.get("observer", ""))
    lines = [f"现在是{str(perception.get('time', ''))[5:16].replace('T', '日 ')}，你在{perception.get('location')}。"]
    if perception.get("busy_until"):
        lines.append(f"你手上的事还没完，要忙到{str(perception['busy_until'])[11:16]}。")
    for message in perception.get("inbox", []):
        lines.append(f"你收到一条来自{message.get('from')}的消息：{message.get('text')}")
    for fact in perception.get("operational_facts", []):
        action = fact.get("action", {})
        line = ("你刚才想做的「{action.get('kind')}」没有成功，什么也没改变。"
                f"原因：{fact.get('reason')}。")
        alternatives = fact.get("alternatives")
        if alternatives:
            line += "或许可以：" + "；".join(str(a) for a in alternatives) + "。"
        lines.append(line)
    for event in perception.get("events", []):
        kind = event.get("kind")
        payload = event.get("payload", {})
        if (event.get("actor") != observer and kind in {"action_started", "action_completed"}
                and payload.get("action") in {"wait", "sleep"}):
            continue
        stamp = str(event.get("time", ""))[11:19]
        sentence = _event_sentence(event, str(perception.get("location", "")))
        if not sentence:
            from .prompt import _private_line
            sentence = _private_line(event, observer)
        if sentence:
            lines.append(f"[{stamp}] {sentence}")
    first_desc = True
    for entity, description in perception.get("descriptions", {}).items():
        if entity in seen["descriptions"]:
            continue
        seen["descriptions"].add(entity)
        # 条目之间空一行（条目内部的空行已由 _clean_description 压掉）。
        if not first_desc:
            lines.append("")
        first_desc = False
        lines.append(f"{entity}：{_clean_description(description)}")
    for place, note in (perception.get("knowledge") or {}).items():
        text = str(note.get("public") if isinstance(note, dict) else note)
        if text and (place, text) not in seen["knowledge"]:
            seen["knowledge"].add((place, text))
            lines.append(f"你知道：{place}——{text}")
    if affordances:
        lines.append("你现在可以具体地：")
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
            lines.append("\n[assistant]\n（没有动作）")
        result = str(turn.get("result"))
        error = turn.get("error")
        if result == "submitted":
            pass
        elif result == "rejected":
            lines.append(f"\n[user]\n你的动作没有被执行：{error} 什么也没有改变。")
        elif result == "retryable_failure":
            lines.append(f"\n[user]\n一阵恍惚，你的念头没能传达出去（{error}）。"
                         "什么都没有发生。")
        elif result in {"wall_clock_deadline", "agent_error", "decision_timeout", "engine_error"}:
            lines.append(f"\n[user]\n你的这个念头没能落地（{result}）：{error}")
        else:
            names = [events_by_id[i].get("kind") for i in turn.get("event_ids", [])
                     if i in events_by_id]
            lines.append(f"\n[user]\n结果 {result}：{', '.join(map(str, names)) or '无事件'}")
    memories = session.get("compacted_memories", [])
    if memories:
        lines.append(
            "\n---\n"
            "压缩边界。上方的亲历日志曾被会话周期性压缩；trace 未记录每次压缩发生的精确回合。"
            "下方每个 --- 分隔的块，是一份替换了此前对话的压缩记忆。")
        for memory in memories:
            lines.append("\n---\n" + str(memory.get("content", "")))
    if messages:
        lines.append("\n---\n当前活跃上下文（逐字；即角色下一次请求会收到的原文）：")
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
    data = json.loads(Path(args.trajectory).read_text(encoding="utf-8"))
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
