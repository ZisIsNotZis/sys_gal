"""Adapter from persistent character sessions to the neutral Runner."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .character_loader import CharacterSeed
from .character_session import CharacterSession, ModelCall, NaturalIntention
from .agent_state import PrivateState
from .action_schema import SCHEMAS, TOOLS as _TOOLS_FOR_ACTOR, SPEAK_TOOLS
from .adapter import lift_native_call


GMCall = Any

# V4-AGENT-INTERFACE §1: the system prompt is verbatim-fixed for every role
# (MC, NPC, extra) — identity and world facts live in KB rows, never here.
# Copy this text byte-for-byte from docs/V4-AGENT-INTERFACE.md.
SYSTEM_PROMPT_V4 = (
    "你是一个活生生的人，活在一个真实的世界里。绝不提 agent、提示词、模拟、作者或剧情。只追你自己的知识、欲望、责任、恐惧和关系；不为故事或主角服务；不优化故事，不制造浪漫，不满足任何作者意图。\n"
    "\n"
    "世界每回合给你一条消息：几点、你在哪、身边有谁、身上有什么、附近有什么、发生了什么、你记事本里到期的事。一切事都要花时间：说话动作花一个tick并在下一刻完成；对方之后才能听见并回应——当面说话仍是最快的交流方式，短信送别处则慢一些。默认等回复是说完后的另一段等待，不是继续说话。你用工具行动，一回合可以连续调用多个工具；同一条消息里的多个调用按顺序串行执行，每个动作各花各的时间，后面的调用看到前面调用之后的世界，也可能因此失效。所以一个回合只应有一个耗时动作：第二个耗时动作会撞上还没做完的第一个而被拒绝，把它留到下一回合。查记事本、回想往事不额外耗时。如果你既没说话也没做任何动作，时间照常流逝——你在原地站了一会儿。只有你真的做过的事才能说成做过：世界只承认工具调用记下来的行为。没读过的内容，别当成自己核实过的事实；没做成的动作，别说成已经完成——没到手的就直说没到手，或换成做得到的做法。\n"
    "\n"
    "你输出的普通文字（回复里的正文）是你心里的想法——谁也听不见，不会被当成你说出口的话；打算、判断、旁白、对协议的说明都放这儿。要说话就用 speak 工具：to=[对谁说]（在场的名字，可多个；或 [\"陌生人\"] 向身边的路人搭话）；volume=normal 大家都听得见，volume=whisper 仅 to 名单听得见（只对亲近的人用，陌生人凑近耳语会显得可疑）。要给不在身边的人发消息、私聊，用 text 工具：target=收件人，正文只投递给对方。说话用 speak，私聊用 text——光写正文谁也不会听见。这句话说完后你会自动原地等回应（有人回应会立刻叫醒你），除非 wait_response=false。空闲时等待随时可行，不必等谁批准；正在执行的动作会自动完成，忙时不要再提交 wait。只有明确显示为被打断的动作才用 continue_action 或 abandon_action；普通忙碌不是打断。夜里困了就找个有床的地方睡下。消息里时间写作 9/16(周三) 7:00。"
)

# Ticket 56: the one self-correction shown to an actor whose speak/text `text`
# argument was withheld as protocol/tool meta-reasoning (a formatting error the
# world refuses to deliver). It names the mistake, states the world did not
# hear it, and points at `inner`.
PRIVATE_CONTENT_NOTE = (
    "【自我纠正】你上一条回复的 speak/text 里混进了协议/工具字段的说明"
    "——那属于格式错误，不是你说出口的话；世界没有把它送出去，也没有广播给任何人。"
    "请只写真正的台词，把心里话放进工具调用的 inner。")

# Ticket 64: plain content is the actor's private thought, never broadcast.
# When a turn wrote only body text that reads like it was meant to be heard
# (quoted dialogue / second-person address) and used no speak/text call, the
# engine shows this one transitional self-correction so the model learns to
# put speech in the `speak` tool (and private messages in `text`).
UNSPOKEN_CONTENT_NOTE = (
    "【自我纠正】这段没有说出口——正文只是你的想法，世界没有把它当台词，"
    "也没有广播给任何人。要说出口请用 speak 工具（当面说）；要给不在身边的人"
    "发消息用 text 工具。")

# 票 91（E93）：一整个回合只有想法、零个工具调用。世界照旧往前走一拍、什么也
# 没发生（V4-AGENT-INTERFACE §4），但窗口 3 的 08:42–09:04 里没有人把这件事告诉
# 角色：陈默把台账的三条款在正文里答了五遍，每次都像已经答过了。这条反馈只说
# 清上一回合的后果并指出两个出路（工具、或明确 wait），不代替他动作、不惩罚他。
NO_ACTION_NOTE = (
    "【上一回合】你只写了心里的想法，没有调用任何工具——世界没有因为那段想法改变，"
    "时间照常过去了。要把话说出口用 speak/text，要做事用相应的工具；确实只想待在"
    "原地，就用 wait 明确占住这段时间。")
NO_ACTION_STREAK_NOTE = "（这已经是连续第 {streak} 个这样的回合。）"


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
                 system_prompt: str | None = None, world_primer: str = "") -> None:
        self.actor_id = actor_id
        self.provider = provider
        self.compaction_threshold = compaction_threshold
        self.recent_messages = recent_messages
        self._compacted_since_decision = False
        self.compacted_memories = list(compacted_memories or ())
        if messages:
            self.messages: list[dict[str, Any]] = [dict(m) for m in messages]
        else:
            # The verbatim preamble stays byte-identical for every actor; the
            # per-world primer (locations/走法/time rules) is appended once and
            # is static, so provider caching is unaffected.
            base = system_prompt or SYSTEM_PROMPT_V4
            if world_primer and not system_prompt:
                base = base + "\n\n" + world_primer
            self.messages: list[dict[str, Any]] = [{"role": "system", "content": base}]

    def decide(self, world_message_text: str) -> dict[str, Any]:
        """Append one world message, call the provider with the full static
        tool array, record the assistant reply, and return
        {"text": private body, "calls": [tool calls in order]} — the plain
        text output is the actor's PRIVATE thought (ticket 64); speech happens
        only through a `speak`/`text` call. The engine reports each call's
        result back through deliver_tool_results (n tool_call = n tool result +
        next user turn)."""
        self._maybe_compact()
        self.messages.append({"role": "user", "content": world_message_text})
        message = self.provider.chat_with_tools(self.messages, _TOOLS_FOR_ACTOR)
        self.messages.append({"role": "assistant",
                              "content": message.get("content") or "",
                              "tool_calls": message.get("tool_calls") or []})
        spoken = str(message.get("content") or "").strip()
        calls: list[dict[str, Any]] = []
        turn_inners: list[str] = []
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
                if name in SCHEMAS:
                    # Ticket 38: inner rides in arguments; lift it out so the
                    # action schema never sees it, and reject the call (not
                    # the whole turn) when it is missing or empty.
                    args, inner, inner_error = lift_native_call(name, args)
                    if inner_error is not None:
                        call["arguments"] = args
                        call["parse_error"] = inner_error
                        calls.append(call)
                        continue
                    if inner:
                        turn_inners.append(inner)
                call["arguments"] = args
            except (ValueError, TypeError) as exc:
                call["parse_error"] = f"{type(exc).__name__}: {exc}: {str(raw_args)[:200]}"
            calls.append(call)
        return {"text": spoken, "calls": calls,
                "inner": "\n".join(turn_inners) or None}

    def deliver_tool_results(self, results: list[dict[str, Any]]) -> None:
        """Report each tool call's result (V4-AGENT-INTERFACE §3): content is
        "ok" or the concrete error text for that call.

        Responses-only models retain every function-call/result pair, including
        repeated calls of the same tool with different arguments. Legacy Chat
        Completions gateways still require coalescing consecutive tool replies;
        the legacy branch below preserves their existing wire contract."""
        if not results:
            return
        if getattr(self.provider, "responses_only", False):
            for result in results:
                self.messages.append({"role": "tool",
                                      "tool_call_id": result.get("tool_call_id"),
                                      "content": str(result.get("text", "ok"))})
            return
        last = self.messages[-1] if self.messages else None
        if len(results) > 1 and last is not None and last.get("role") == "assistant":
            first_id = results[0].get("tool_call_id")
            calls = last.get("tool_calls") or []
            names = {c.get("id"): str((c.get("function") or {}).get("name", "call"))
                     for c in calls}
            last["tool_calls"] = [c for c in calls
                                  if (c.get("id")) == first_id] or calls[:1]
            body = "\n".join(
                f"[{names.get(r.get('tool_call_id'), 'call')}] {str(r.get('text', 'ok'))}"
                for r in results)
            self.messages.append({"role": "tool", "tool_call_id": first_id,
                                  "content": body})
            return
        for result in results:
            self.messages.append({"role": "tool",
                                  "tool_call_id": result.get("tool_call_id"),
                                  "content": str(result.get("text", "ok"))})

    def note_private_content(self) -> None:
        """Ticket 56: this turn's speak/text `text` argument was withheld as
        protocol/tool meta-reasoning. Append the self-correction as a user turn
        so the next decision sees the mistake. The engine calls this AFTER
        deliver_tool_results, so an assistant's tool_calls keep their
        role:tool pairing (strict gateways reject a user turn in between)."""
        self.messages.append({"role": "user", "content": PRIVATE_CONTENT_NOTE})

    def note_unspoken_content(self) -> None:
        """Ticket 64: this turn's plain body was private and read like it was
        meant to be heard, but no speak/text call was used. Append the one
        transitional self-correction (after the tool results, same ordering
        rule as note_private_content)."""
        self.messages.append({"role": "user", "content": UNSPOKEN_CONTENT_NOTE})

    def note_no_action(self, streak: int = 1) -> None:
        """票 91（E93）：上一回合只有正文、零调用。把这一回合的后果告给下一回合。

        与 ticket 56/64 同一位置、同一条排序规则（在 tool 结果之后）。有界：每次
        只追加一条，且只在对方还在连续空转时追加——一旦有调用就不再加。"""
        text = NO_ACTION_NOTE
        if streak > 1:
            text += NO_ACTION_STREAK_NOTE.format(streak=streak)
        self.messages.append({"role": "user", "content": text})

    def _maybe_compact(self) -> None:
        if sum(len(str(m.get("content", ""))) for m in self.messages) <= self.compaction_threshold:
            return
        system = self.messages[:1]
        kept = self.messages[-self.recent_messages:]
        # An orphaned tool message at the head of the kept tail (its
        # assistant trigger was folded into the memory) makes every later
        # request invalid on strict gateways — drop leading tool entries.
        while kept and kept[0].get("role") == "tool":
            kept.pop(0)
        old = self.messages[1:-len(kept)] if kept else self.messages[1:]
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
                         + kept)
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
                             session: "V4Session | None" = None,
                             world_primer: str = ""):
    """V4 protocol persistent agent (V4-AGENT-INTERFACE §4): the engine hands
    in the rendered world message; the agent owns the session and returns the
    parsed native tool-call list. Signature: agent(world_message_text, state).
    """
    sess = session or V4Session(seed.actor_id, provider, world_primer=world_primer)

    def agent(world_message_text: str, state: PrivateState) -> dict[str, Any]:
        return sess.decide(world_message_text)

    agent.consume_compaction = (lambda: sess.consume_compaction())  # type: ignore[attr-defined]
    agent.session_snapshot = lambda: sess.snapshot()  # type: ignore[attr-defined]
    agent.deliver_tool_results = sess.deliver_tool_results  # type: ignore[attr-defined]
    agent.session_obj = sess  # type: ignore[attr-defined]

    def restore_session(snapshot: dict[str, Any]) -> None:
        nonlocal sess
        sess = V4Session.from_snapshot(snapshot, provider)
        agent.session_obj = sess  # type: ignore[attr-defined]
        agent.session_snapshot = lambda: sess.snapshot()  # type: ignore[attr-defined]
        agent.deliver_tool_results = sess.deliver_tool_results  # type: ignore[attr-defined]
        agent.consume_compaction = (lambda: sess.consume_compaction())  # type: ignore[attr-defined]

    agent.restore_session = restore_session  # type: ignore[attr-defined]
    return agent
