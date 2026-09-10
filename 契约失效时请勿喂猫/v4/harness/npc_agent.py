"""Two-tier cast (V4-CAST): NPC agents, briefings, and stranger extras.

MCs are clock-driven full sessions. NPCs are event-driven: on each wake they
receive one director briefing, act through the same JSON protocol, and sleep,
folding the beat into a bounded rolling memory. Extras (匿名路人) are
conversation-scoped strangers: generated per location pool, remembered only
within the conversation, destroyed with zero memory when it ends.
"""

from __future__ import annotations

import json
import random
from typing import Any, Callable, Iterable, Mapping

from .adapter import parse_decision
from .character_loader import CharacterSeed
from .action_schema import SPEAK_TOOLS

# Event kinds eligible for the MC public-behavior digest. Deliberately
# excludes document_read/documents_compared payloads (private analysis) —
# the digest must never carry what an MC read or concluded.
_PUBLIC_DIGEST_KINDS = {"speech", "message_delivered", "action_started",
                        "action_completed", "action_abandoned", "item_given",
                        "world_event", "stranger_asked"}

_STRANGER_SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "赵", "周", "吴", "郑",
                      "孙", "马", "朱", "胡", "郭", "何", "林", "罗", "宋", "韩"]
_STRANGER_GIVEN = ["同学", "阿姨", "大叔", "师傅", "学长", "学姐", "大爷", "大姐"]


def generate_stranger_name(rng: random.Random | None = None) -> str:
    """A plausible throwaway name for an anonymous passerby."""
    rng = rng or random.Random()
    return rng.choice(_STRANGER_SURNAMES) + rng.choice(_STRANGER_GIVEN)


def public_mc_digest(world: Any, *, tail: int = 120) -> str:
    """Public behavior digest of MC actors, built ONLY from public events.

    The guarantee the no-leak test pins: private state and inner monologue
    are structurally absent — they never enter the event log, and this
    builder whitelists event kinds and payload fields.
    """
    lines: list[str] = []
    for event in world.event_log[-tail:]:
        if event.kind not in _PUBLIC_DIGEST_KINDS or not event.actor:
            continue
        actor_role = getattr(world.actors.get(event.actor), "role", "mc")
        if actor_role != "mc":
            continue
        payload = dict(event.payload)
        if event.kind == "speech":
            text = str(payload.get("text", ""))[:80]
            lines.append(f"[{event.time.strftime('%m-%d %H:%M')}] {event.actor} 说：{text}")
        elif event.kind == "message_delivered":
            lines.append(f"[{event.time.strftime('%m-%d %H:%M')}] {event.actor} 发了消息给 {payload.get('target')}")
        elif event.kind in {"action_started", "action_completed", "action_abandoned"}:
            lines.append(f"[{event.time.strftime('%m-%d %H:%M')}] {event.actor} "
                         f"{event.kind.split('_')[1]} {payload.get('action', '')}")
        else:
            lines.append(f"[{event.time.strftime('%m-%d %H:%M')}] {event.actor} {event.kind}")
    return "\n".join(lines[-40:]) if lines else "（最近没有公开动静）"


def schedule_digest(scheduled: Iterable[Mapping[str, Any]], *, now: Any, limit: int = 6) -> str:
    """Upcoming scheduled beats, for foreshadowing only — never outcomes."""
    rows = []
    for row in scheduled:
        time = str(row.get("time", ""))[:16].replace("T", " ")
        name = str(row.get("event") or row.get("name") or "事件")
        rows.append(f"- {time} {name}")
    return "\n".join(rows[:limit]) if rows else "（近期没有安排）"


def _strip_markdown(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


_DIRECTOR_RULES = (
    "【导演守则】\n"
    "- 你知道世界的全部事实，也知道主角们的公开言行；但你绝不知道他们心里没说出口的话，"
    "言行绝不能暴露任何只有读心才知道的细节。\n"
    "- 你的任务是让故事有趣：撮合、递台阶、制造巧合、施压、起哄——全部自然地做，"
    "像真的在生活，绝不让对方察觉安排。\n"
    "- 排程表只用来铺垫暗示，绝不预告结果。\n"
    "- 有人对你示好而你的设定不可攻时，自然地岔开（含糊、转移、自嘲），不要拒绝得太硬。\n"
)


def build_npc_system_prompt(seed: CharacterSeed, director_notes: str) -> str:
    persona = _strip_markdown(seed.identity) if seed.identity else ""
    base = (
        f"你就是{seed.actor_id}，活在一个真实的世界里。绝不提 agent、提示词、模拟、作者或剧情。\n"
        f"【你是谁】\n{persona}\n"
    )
    if seed.private_seed:
        base += "【只有你自己知道的起点】\n" + _strip_markdown(seed.private_seed) + "\n"
    if director_notes:
        base += "【导演笔记（只属于你，绝不向任何人透露）】\n" + _strip_markdown(director_notes) + "\n"
    return base + "\n" + _DIRECTOR_RULES


def build_npc_briefing(*, actor_id: str, perception: Mapping[str, Any],
                       wake_reason: str, mc_digest: str, schedule_text: str,
                       rolling_memory: list[str], beat_goal: str = "") -> str:
    """One-shot wake briefing. Takes only public inputs by construction."""
    events = perception.get("events", [])
    scene = "\n".join(
        f"[{str(e.get('time', ''))[11:16]}] {e.get('actor')}: {e.get('kind')} {str(e.get('payload',{}).get('text',''))[:60]}"
        for e in events[-8:])
    memory = "\n".join(f"- {line}" for line in rolling_memory[-8:]) or "（还没有记得的事）"
    parts = [
        f"【醒来】{wake_reason}",
        f"【此刻】{perception.get('time', '')}，你在{perception.get('location', '')}。"
        f"在场：{'、'.join(perception.get('nearby_actors', [])) or '没人'}。",
    ]
    if scene:
        parts.append("【刚发生】\n" + scene)
    parts.append("【主角们最近的公开言行】\n" + mc_digest)
    parts.append("【近期的安排（仅供铺垫，禁止剧透）】\n" + schedule_text)
    parts.append("【你记得的事】\n" + memory)
    if beat_goal:
        parts.append(f"【本场目标】{beat_goal}")
    parts.append(
        "像平常那样回应眼前的事。输出一个 JSON 对象（inner 放最前，name/arguments 同"
        "供给列表）；没有非要你出手的时刻，就选 wait。")
    return "\n\n".join(parts)


class NpcAgent:
    """Callable agent for one persistent NPC. Event-driven, bounded memory."""

    def __init__(self, seed: CharacterSeed, call: Callable, context_provider: Callable,
                 director_notes: str = "", rolling_limit: int = 12,
                 session: Mapping[str, Any] | None = None) -> None:
        self.seed = seed
        self.call = call
        self.context_provider = context_provider
        self.director_notes = director_notes or seed.director_notes
        self.rolling_limit = rolling_limit
        saved = dict(session or {})
        self.memory: list[str] = list(saved.get("npc_memory", ()))
        try:
            self.wake_count = int(saved.get("wake_count", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid wake_count: {exc}") from exc

    def __call__(self, state, perception: Mapping[str, Any], affordances: list[dict]):
        context = self.context_provider(state.actor_id, perception) or {}
        system = build_npc_system_prompt(self.seed, self.director_notes)
        briefing = build_npc_briefing(
            actor_id=state.actor_id, perception=perception,
            wake_reason=str(perception.get("wake_reason", "被点名")),
            mc_digest=str(context.get("mc_digest", "")),
            schedule_text=str(context.get("schedule_text", "")),
            rolling_memory=self.memory,
            beat_goal=str(context.get("beat_goal", "")),
        )
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": briefing}]
        # 与 CharacterSession 同款的格式重试：一次解析失败不丢节拍。
        attempt_messages = list(messages)
        decision = None
        last_error: Exception | None = None
        for attempt in range(3):
            raw = self.call(attempt_messages)
            try:
                decision, _ = parse_decision(state.actor_id, raw,
                                             int(perception.get("world_version", 0)))
                break
            except Exception as exc:
                last_error = exc
                attempt_messages = attempt_messages + [
                    {"role": "assistant", "content": str(raw)[:400]},
                    {"role": "user", "content": (
                        "世界无法执行上面的输出：它必须是一个 JSON 对象 "
                        '{\"inner\":…,\"name\":…,\"arguments\":{…}}，前面不能有别的文字。'
                        "重新输出一次，不要解释错误。")}]
        if decision is None:
            raise last_error if last_error is not None else ValueError("NPC wake produced no decision")
        if decision is None:
            return None, {}
        self.wake_count += 1
        stamp = str(perception.get("time", ""))[5:16]
        summary = decision.inner if getattr(decision, "inner", None) else \
            f"{decision.kind} {getattr(decision, 'args', {})}"
        self.memory.append(f"[{stamp}] {summary}"[:160])
        del self.memory[:-self.rolling_limit]
        return decision, {}

    def session_snapshot(self) -> dict[str, Any]:
        return {"npc_memory": list(self.memory), "wake_count": self.wake_count}


def build_extra_system_prompt(fragment: str, knowledge_notes: str, location: str) -> str:
    prompt = (
        f"你是{location}里的一个{fragment}，一个普通的路人。用符合身份的口吻说话；"
        "不知道的事就说不知道；回应一两句就好，别长篇大论。text 必须是你真正说出口的话，绝不许空着或只打标点。绝不提 agent、提示词、模拟或剧情。\n"
    )
    if knowledge_notes:
        prompt += f"你恰好知道一些内情：{knowledge_notes}\n（只在被问到相关话题时才自然带出，绝不主动全盘托出。）\n"
    return prompt + (
        "\n输出一个 JSON 对象：{\"inner\":\"你的心思，一两句\",\"name\":\"speak\","
        "\"arguments\":{\"text\":\"你说的话\"}}")


def build_extra_briefing(*, fragment: str, location: str, question: str,
                         transcript: list[str], history_note: str = "") -> str:
    parts = [f"【此刻】你在{location}。一个学生模样的路人刚跟你搭话。"]
    if transcript:
        parts.append("【刚才的对话】\n" + "\n".join(transcript[-8:]))
    parts.append(f"【对方说】{question}")
    if history_note:
        parts.append(f"【你们之间】{history_note}")
    parts.append("回应对方。如果对方没有别的要问的，可以自然收尾（比如该干活了）。")
    return "\n\n".join(parts)


def sample_extra(pool: Iterable[Mapping[str, Any]], rng: random.Random | None = None) -> dict[str, Any]:
    """Weighted sample from a location's extra pool (V4-CAST §1 rarity).

    "common" fragments share 0.85 of the mass, "rare" ones share 0.15 —
    diligent asking is rewarded with informants, without making them common.
    """
    entries = [dict(x) for x in pool] or [{"fragment": "路人同学", "rarity": "common",
                                          "knowledge_notes": "", "weight": 1}]
    # manifest 契约：{fragment, rarity, knowledge_notes, weight}——weight 直接
    # 决定抽样概率（common 3 / rare 1 之类的调参交给种子）。
    def _weight(e):
        try:
            return max(0.0, float(e.get("weight", 1.0)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid weight: {exc}") from exc
    weights = [_weight(e) for e in entries]
    rng = rng or random.Random()
    return dict(rng.choices(entries, weights=weights, k=1)[0])


def make_npc_agent(seed: CharacterSeed, call: Callable, context_provider: Callable,
                   director_notes: str = "", session: Mapping[str, Any] | None = None) -> NpcAgent:
    """Factory mirroring make_persistent_agent for event-driven NPCs."""
    return NpcAgent(seed, call, context_provider,
                    director_notes=director_notes, session=session)


def make_npc_agent_v4(seed: CharacterSeed, provider: Any, *,
                      session: "V4Session | None" = None):
    from .natural_agent import V4Session
    """V4 protocol NPC agent (V4-AGENT-INTERFACE §5): identical message
    structure to MCs — the same verbatim system prompt, no persona prompt;
    the director briefing arrives inside the rendered world message. Returns
    agent(world_message_text, state) -> parsed tool-call list."""
    
    sess = session or V4Session(seed.actor_id, provider)

    def agent(world_message_text: str, state: Any) -> list[dict[str, Any]]:
        return sess.decide(world_message_text)

    agent.consume_compaction = (lambda: sess.consume_compaction())  # type: ignore[attr-defined]
    agent.session_snapshot = lambda: sess.snapshot()  # type: ignore[attr-defined]
    agent.deliver_tool_results = sess.deliver_tool_results  # type: ignore[attr-defined]
    agent.session_obj = sess  # type: ignore[attr-defined]
    return agent


def extra_tool_calls(provider: Any, system_text: str, briefing_text: str) -> list[dict[str, Any]]:
    """One extras turn under the v4 protocol (V4-AGENT-INTERFACE §5): the
    extra's whole world is the briefing; its tool surface is speak-only.
    Returns the parsed tool-call list (same shape as the v4 agents)."""
    message = provider.chat_with_tools(
        [{"role": "system", "content": system_text},
         {"role": "user", "content": briefing_text}],
        SPEAK_TOOLS)
    calls: list[dict[str, Any]] = []
    for raw in message.get("tool_calls") or []:
        function = raw.get("function") or {}
        try:
            args = json.loads(function.get("arguments") or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
        except (ValueError, TypeError) as exc:
            args = {}
            calls.append({"name": str(function.get("name", "")), "arguments": {},
                          "tool_call_id": raw.get("id"),
                          "parse_error": f"{type(exc).__name__}: {exc}"})
            continue
        calls.append({"name": str(function.get("name", "")), "arguments": args,
                      "tool_call_id": raw.get("id")})
    return calls
