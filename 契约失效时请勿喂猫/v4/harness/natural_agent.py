"""Adapter from persistent character sessions to the neutral Runner."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .character_loader import CharacterSeed
from .character_session import CharacterSession, ModelCall, NaturalIntention
from .agent_state import PrivateState
from .action_schema import TOOLS as _TOOLS_FOR_ACTOR, SPEAK_TOOLS


GMCall = Any

# V4-AGENT-INTERFACE §1: the system prompt is verbatim-fixed for every role
# (MC, NPC, extra) — identity and world facts live in KB rows, never here.
# Copy this text byte-for-byte from docs/V4-AGENT-INTERFACE.md.
SYSTEM_PROMPT_V4 = (
    "你是一个活生生的人，活在一个真实的世界里。绝不提 agent、提示词、模拟、作者或剧情。"
    "只追你自己的知识、欲望、责任、恐惧和关系；不为故事或主角服务；不优化故事，不制造浪漫，"
    "不满足任何作者意图。\n\n"
    "世界每回合给你一条消息：几点、你在哪、身边有谁、身上有什么、发生了什么、"
    "你记事本里到期的事。一切事都要花时间：说话也要花一分钟，话一出口对方下个片刻就能听见并回应——"
    "当面说话仍是最快的交流方式；送别处则更慢。你用工具行动：一回合可以连续调用多个工具；世界动作消耗真实时间"
    "（按序累加，向上取整到 tick 的倍数），think/update_memory/recall/flashback 不额外消耗"
    "（但每回合最少一个 tick）。一回合没有任何世界动作，等于发了一会儿呆（时间照走最少一个 tick）。"
    "行动前永远先用 think 写心声——此刻的感受、打算做什么、为什么；让 think 成为你每个回合的第一个调用。"
    "等待随时可行，不必等谁批准；夜里困了就找个有床的地方睡下。陌生人凑近耳语会显得可疑；"
    "耳语（whisper）只对亲近的人用。消息里时间写作 9/16(周三) 7:00。"
)


class V4Session:
    """One actor's v4-protocol conversation: system prompt verbatim, world
    messages appended as user turns, native tool_calls parsed structurally
    (no judge, no lenient parsing — V4-AGENT-INTERFACE §0/§4).

    Compaction mirrors the docs §4 semantics: threshold 30000 chars, the 4
    most recent messages survive verbatim, old turns fold into a first-person
    memory summary. The engine consumes the compaction flag to reset KB
    last_shown state.
    """

    def __init__(self, actor_id: str, provider: Any, *, messages: list[dict] | None = None,
                 compacted_memories: list[dict] | None = None,
                 compaction_threshold: int = 30000, recent_messages: int = 4,
                 system_prompt: str | None = None) -> None:
        self.actor_id = actor_id
        self.provider = provider
        self.compaction_threshold = compaction_threshold
        self.recent_messages = recent_messages
        self._compacted_since_decision = False
        self.compacted_memories = list(compacted_memories or ())
        if messages:
            self.messages: list[dict[str, Any]] = [dict(m) for m in messages]
        else:
            self.messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT_V4}]

    def decide(self, world_message_text: str) -> list[dict[str, Any]]:
        """Append one world message, call the provider with the full static
        tool array, record the assistant reply, and return the parsed
        tool-call list in submission order. The engine reports each call's
        result back through deliver_tool_results (n tool_call = n tool
        result + next user turn — V4-AGENT-INTERFACE §3)."""
        self._maybe_compact()
        self.messages.append({"role": "user", "content": world_message_text})
        message = self.provider.chat_with_tools(self.messages, _TOOLS_FOR_ACTOR)
        self.messages.append({"role": "assistant",
                              "content": message.get("content") or "",
                              "tool_calls": message.get("tool_calls") or []})
        calls: list[dict[str, Any]] = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            name = str(function.get("name", ""))
            raw_args = function.get("arguments")
            call: dict[str, Any] = {"name": name, "arguments": {},
                                    "tool_call_id": raw.get("id")}
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
                call["arguments"] = args
            except (ValueError, TypeError) as exc:
                call["parse_error"] = f"{type(exc).__name__}: {exc}: {str(raw_args)[:200]}"
            calls.append(call)
        return calls

    def deliver_tool_results(self, results: list[dict[str, Any]]) -> None:
        """Append one role:tool message per tool call (V4-AGENT-INTERFACE §3):
        content is "ok" or the concrete error text for that call."""
        for result in results:
            self.messages.append({"role": "tool",
                                  "tool_call_id": result.get("tool_call_id"),
                                  "content": str(result.get("text", "ok"))})

    def _maybe_compact(self) -> None:
        if sum(len(str(m.get("content", ""))) for m in self.messages) <= self.compaction_threshold:
            return
        system = self.messages[:1]
        old = self.messages[1:-self.recent_messages]
        if not old:
            return
        request = system + old + [{"role": "user", "content": (
            "把上面这段亲身经历压缩成这个人的第一人称记忆。保住：许下的承诺、试过又失败的事、"
            "看到的事实、没弄明白的地方、关系的变化、情绪的转折、还没了结的亏欠。"
            "场景、物品、地点布局这类固定信息不要写进记忆——世界会在需要时自动重放它们；"
            "记忆只保留个人的想法、情绪、关系变化、承诺与未解之事。"
            "不要编造没发生过的事。只输出记忆正文，不要解说。"
        )}]
        memory = self.provider(request)
        memory_text = memory if isinstance(memory, str) else json.dumps(memory, ensure_ascii=False)
        self.compacted_memories.append({"order": len(self.compacted_memories),
                                        "actor": self.actor_id, "content": memory_text})
        self.messages = (system + [{"role": "user", "content":
            "此前早些的记忆，从你自己的经历里压缩而来：\n" + memory_text}]
                         + self.messages[-self.recent_messages:])
        # V4-AGENT-INTERFACE §3: compaction zeroes all last_shown (the engine
        # consumes this flag to reset its KB replay state).
        self._compacted_since_decision = True

    def consume_compaction(self) -> bool:
        fired = self._compacted_since_decision
        self._compacted_since_decision = False
        return fired

    def snapshot(self) -> dict[str, Any]:
        return {"format": "v4-character-session-1", "actor": self.actor_id,
                "messages": [dict(m) for m in self.messages],
                "compacted_memories": [dict(m) for m in self.compacted_memories]}

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any], provider: Any) -> "V4Session":
        return cls(snapshot["actor"], provider,
                   messages=list(snapshot.get("messages", ())),
                   compacted_memories=list(snapshot.get("compacted_memories", ())))


def make_provider_gm(call: ModelCall, *, max_retries: int = 1):
    """Create a narrow interpreter for prose that cannot be executed directly."""
    def gm(text: str, perception: dict, affordances: list[dict]):
        prompt = [{"role": "system", "content": (
            "You are a neutral world interpreter. Convert the person's natural-language "
            "intention into exactly one concrete action from the offered actions. Do not invent "
            "facts, dialogue, relationships, or plot. If it cannot be safely resolved, return "
            "null. Output valid JSON only."
        )}, {"role": "user", "content": (
            f"Person's intention:\n{text}\n\nVisible world:\n{perception}\n\n"
            f"Offered actions:\n{affordances}\n\nReturn {{\"kind\":...,\"args\":...}} or null."
        )}]
        failures: list[Exception] = []
        for attempt in range(max_retries + 1):
            try:
                return call(prompt)
            except Exception as exc:
                # Interpretation has no world side effect until its result is
                # validated and submitted by Runner, so a bounded retry is
                # safe even when the provider exhausted its own HTTP retries.
                failures.append(exc)
            retryable = attempt < max_retries and getattr(failures[-1], "retryable", False)
            if not retryable:
                last = failures[-1]
                if getattr(last, "retryable", False):
                    setattr(last, "runner_retryable", True)
                raise last
    return gm


def make_persistent_agent(seed: CharacterSeed, call: ModelCall, gm: GMCall = None,
                          session: CharacterSession | None = None,
                          world_primer: str = ""):
    # ``session`` lets a resume path inject a restored conversation so history
    # survives a checkpoint/restart; otherwise one is created from the seed.
    restored: CharacterSession | None = session
    gm_records: list[dict[str, Any]] = []

    def agent(state: PrivateState, perception: dict, affordances: list[dict]):
        nonlocal session
        if session is None:
            session = CharacterSession(seed, state, call, world_primer=world_primer)
        from .prompt import render_world_message
        message = render_world_message(perception, affordances)
        decision, updates = session.decide(message, perception["world_version"],
                                            turn_id=perception.get("_turn_id"))
        if isinstance(decision, NaturalIntention):
            if gm is None:
                raise ValueError("character expressed a natural-language intention but no GM is bound")
            record: dict[str, Any] = {"actor": state.actor_id, "original_prose": decision.text,
                                      "perception": deepcopy(perception),
                                      "affordances": deepcopy(affordances),
                                      "result": None, "error": None}
            try:
                interpreted = gm(decision.text, deepcopy(perception), deepcopy(affordances))
                record["result"] = deepcopy(interpreted)
                if isinstance(interpreted, tuple):
                    if len(interpreted) != 2:
                        raise ValueError("GM result must be an (intention, updates) pair")
                    intention, updates = interpreted
                    if intention is not None and intention.kind not in {
                            str(option.get("kind")) for option in affordances}:
                        raise ValueError("GM selected an action that was not offered by the world")
                    resolved = (intention, updates)
                else:
                    from .adapter import parse_decision
                    resolved = parse_decision(state.actor_id, interpreted, perception["world_version"])
                    intention, updates = resolved
                    offered_kinds = {str(option.get("kind")) for option in affordances}
                    if intention is not None and intention.kind not in offered_kinds:
                        raise ValueError("GM selected an action that was not offered by the world")
                gm_records.append(record)
                return resolved
            except Exception as exc:
                # A GM is an interpreter, not an authority. An invalid result
                # means no action; it must not become an opaque engine failure.
                record["error"] = f"{type(exc).__name__}: {exc}"
                gm_records.append(record)
                # An upstream outage is different from an invalid
                # interpretation. Do not turn an infrastructure failure into
                # an in-world decision to do nothing.
                if getattr(exc, "retryable", False):
                    raise
                return None, {}
        return decision, updates

    agent.session = lambda: session  # type: ignore[attr-defined]
    agent.record_world_result = lambda message: session and session.record_world_result(message)  # type: ignore[attr-defined]
    agent.consume_compaction = (lambda: session.consume_compaction() if session else False)  # type: ignore[attr-defined]
    agent.session_snapshot = lambda: session.snapshot() if session else None  # type: ignore[attr-defined]
    def drain_gm_records() -> list[dict[str, Any]]:
        records = list(gm_records)
        gm_records.clear()
        return records
    agent.drain_gm_records = drain_gm_records  # type: ignore[attr-defined]
    return agent


def make_persistent_agent_v4(seed: CharacterSeed, provider: Any, *,
                             session: "V4Session | None" = None):
    """V4 protocol persistent agent (V4-AGENT-INTERFACE §4): the engine hands
    in the rendered world message; the agent owns the session and returns the
    parsed native tool-call list. Signature: agent(world_message_text, state).
    """
    sess = session or V4Session(seed.actor_id, provider)

    def agent(world_message_text: str, state: PrivateState) -> list[dict[str, Any]]:
        return sess.decide(world_message_text)

    agent.consume_compaction = (lambda: sess.consume_compaction())  # type: ignore[attr-defined]
    agent.session_snapshot = lambda: sess.snapshot()  # type: ignore[attr-defined]
    agent.deliver_tool_results = sess.deliver_tool_results  # type: ignore[attr-defined]
    agent.session_obj = sess  # type: ignore[attr-defined]
    return agent
