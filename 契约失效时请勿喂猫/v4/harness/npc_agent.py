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
import re
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Sequence

from .adapter import lift_native_call, parse_decision
from .character_loader import CharacterSeed
from .action_schema import SPEAK_TOOLS

if TYPE_CHECKING:  # runtime import stays local to avoid an import cycle
    from .natural_agent import V4Session

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
            lines.append(f"[{event.time.strftime('%m-%d %H:%M')}] {event.actor}说：{text}")
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
        "你是这个场景里的演员：有人对你说话、点名问你、或你身边刚发生了看得见的事，"
        "你都必须开口——你的话就是你的表演。热情的人热情地答，冷淡的人一句话打发，"
        "不耐烦的人可以把不耐烦说出口；但绝不能像不存在一样毫无反应。"
        "实在无关的话，简短表态后继续自己的生活。\n"
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
        "像平常那样回应眼前的事。输出一个 JSON 对象（name/arguments 同供给列表，"
        "arguments 里必须带非空 inner：你的第一人称心声）；没有非要你出手的时刻，就选 wait。")
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
                        '{\"name\":…,\"arguments\":{\"inner\":…,…}}，前面不能有别的文字。'
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


def build_extra_system_prompt(fragment: str, knowledge_notes: str, location: str, *,
                              name: str = "") -> str:
    """The extra's frozen system prompt: who it is, what it may do, and what
    it may assert (ticket 42).

    Before this the prompt carried only the fragment and the knowledge notes;
    the live run showed 韩大叔 calling itself in the third person and mailing
    its own name into `to` (`unknown or ambiguous speak recipient`), while the
    图书馆 rare extra invented a 抄件 signature date (an unregistered entity)
    and narrated 开柜/递件 as already done although its only tool is speak.
    """
    self_name = name.strip() or fragment
    prompt = (
        f"你就是{self_name}，{location}里的一个{fragment}，一个普通的路人。"
        "用符合身份的口吻说话；不知道的事就说不知道；回应一两句就好，别长篇大论。"
        "text 必须是你真正说出口的话，绝不许空着或只打标点。\n"
        f"【你就是你自己】你就是{self_name}本人：用第一人称说话、思考，绝不用第三人称自称，"
        "也不要拿自己的名字当别人的名字。要指明对谁说就用 to=[在场别人的名字]，只能是在场的他人，不能写自己。\n"
        "【你只能说话】说话是你唯一的本事：开柜、递东西、翻页、签名这些动作你都做不到，"
        "只能说出你想做什么或请对方去做（\"请把柜子打开\"），绝不能叙述成已经发生（不说\"柜开了\"\"你接稳了\"）。\n"
        "【你只能断言这些】有名字的人、物、文件，只限你身份里提到的、下面列出的知识范围内、"
        "以及你当场看见或听见的那些；传闻、听说、别人讲的事一律只能当传闻说，"
        "不给任何具体细节——不编造签名、日期、页数、编号、金额。拿不准就直说不知道或只是听说。\n"
        "只回应你实际听见的话，尤其是明确对你说的话；话题已经收束时可以沉默或自然告别，不要另编问题来续谈。"
        "绝不提 agent、提示词、模拟或剧情。\n"
    )
    if knowledge_notes:
        prompt += (f"你恰好知道一些内情：{knowledge_notes}\n"
                   "（只在被问到相关话题时才自然带出，绝不主动全盘托出；也只说到这个程度，不添细节。）\n")
    return prompt + (
        "\n输出一个 JSON 对象：{\"name\":\"speak\","
        "\"arguments\":{\"inner\":\"你的心思，一两句\",\"text\":\"你说的话\"}}")


def restore_extra_prompt(info: Mapping[str, Any], location: str, *,
                         name: str = "") -> str:
    """The extra's system prompt for a turn, rebuilt only when absent.

    ticket 50: the prompt is persisted verbatim in the checkpoint (the
    checkpoint contract is "everything needed to reproduce"), so a resume
    reproduces the exact prefix the live extra was running with. Old-format
    rows written before ticket 50 lack the key; rebuild them from the same
    inputs the spawn site used (fragment/knowledge_notes/location/name) so a
    stale checkpoint still runs instead of dying in ``_extra_turn``.
    """
    prompt = info.get("system_prompt")
    if prompt:
        return str(prompt)
    return build_extra_system_prompt(str(info.get("fragment", "路人")),
                                     str(info.get("knowledge_notes", "")),
                                     location, name=name)


def _extra_speech_audience(event: Any) -> Iterable[str]:
    """Use committed delivery authority; synthetic legacy fixtures use heard."""
    visible = getattr(event, "visible_to", None)
    if visible is not None:
        return visible
    return (getattr(event, "payload", {}) or {}).get("heard") or ()


def extra_heard_speech_since(events: Sequence[Any], *, listener: str, start: int) -> bool:
    """Whether a new external speech event was actually delivered to listener."""
    for event in events[start:]:
        if (getattr(event, "kind", None) == "speech"
                and getattr(event, "actor", None) != listener
                and listener in _extra_speech_audience(event)):
            return True
    return False


def extra_scene_transcript(events: Sequence[Any], *, listener: str, start: int = 0,
                           opening_question: str = "", questioner: str = "",
                           line_limit: int = 8, line_chars: int = 180,
                           total_chars: int = 1200) -> list[str]:
    """Return only bounded speech the extra actually heard in this scene.

    Event.visible_to is the delivery authority; synthetic legacy fixtures
    use heard. Never infer a past listener from current co-location.
    """
    lines: list[str] = []
    speech_texts: list[str] = []
    for event in events[start:]:
        kind = getattr(event, "kind", None)
        payload = getattr(event, "payload", {}) or {}
        if (kind != "speech"
                or (listener != getattr(event, "actor", None)
                    and listener not in _extra_speech_audience(event))):
            continue
        text = str(payload.get("text", "")).strip()
        if not text:
            continue
        speaker = str(getattr(event, "actor", "") or "有人")
        targets = payload.get("to") or ()
        addressed = (listener in targets
                     or ("陌生人" in targets and speaker == questioner))
        stamp = getattr(event, "time", None)
        when = stamp.strftime("%H:%M ") if stamp is not None else ""
        label = "（对你说）" if addressed else ""
        lines.append(f"{when}{speaker}{label}：{text[:line_chars]}")
        speech_texts.append(text)

    # The initial "陌生人" question is an actual speech event, but predates
    # creation of the extra and therefore has no extra in its `heard` set.
    # Ticket 22 makes that question audible at spawn; preserve it once without
    # manufacturing a follow-up question on later external wakes.
    if opening_question and not any(opening_question in text for text in speech_texts):
        speaker = questioner or "对方"
        lines.append(f"{speaker}（对你说）：{opening_question[:line_chars]}")

    bounded = lines[-line_limit:]
    while bounded and sum(len(line) for line in bounded) > total_chars:
        bounded.pop(0)
    return bounded


def build_extra_briefing(*, transcript: list[str]) -> str:
    """Dynamic extra input contains only audible, scene-local speech."""
    if not transcript:
        return ""
    return "【你实际听见的近处交谈】\n" + "\n".join(transcript)


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
                      session: "V4Session | None" = None,
                      world_primer: str = ""):
    from .natural_agent import V4Session
    """V4 protocol NPC agent (V4-AGENT-INTERFACE §5): identical message
    structure to MCs — the same verbatim system prompt plus the per-world
    primer, no persona prompt; the director briefing arrives inside the
    rendered world message. Returns agent(world_message_text, state) -> dict."""
    
    sess = session or V4Session(seed.actor_id, provider, world_primer=world_primer)

    def agent(world_message_text: str, state: Any) -> dict[str, Any]:
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


_PROTOCOL_ENVELOPE_KEY = re.compile(r'"(?:inner|arguments)"\s*:')

# Ticket 42: a re-ask for a reply that came back as the protocol envelope
# instead of a spoken line. It names the mistake and the corrected shape.
_ENVELOPE_REASK = (
    "世界不能把这段当成你说的话：它是一整段协议 JSON（带 inner/arguments 的调用信封）。"
    "inner 是你心里谁也听不见的念头，绝不能混进台词。请只输出你真正说出口的那一句话，"
    "不要带花括号、JSON 或字段名。")


def looks_like_protocol_envelope(text: str) -> bool:
    """Whether a would-be spoken line is really the wire envelope.

    Ticket 42: the d1-am run broadcast the whole decision envelope — the
    private `inner` plus the protocol structure — as 韩大叔's line (events
    #1271/#1272, `heard=['唐小岚']`). An object-shaped line, or one carrying
    the envelope's `inner`/`arguments` keys, is a formatting error to be
    re-asked, never content to be delivered."""
    stripped = str(text).strip()
    if stripped.startswith("{"):
        return True
    return bool(_PROTOCOL_ENVELOPE_KEY.search(str(text)))


# Ticket 56: the model writes private reasoning — protocol/tool meta-talk,
# plans, asides, explicit concealment — into the assistant's plain text,
# which T1 would broadcast as `speak`. The marker set is deliberately
# HIGH-PRECISION: every token below is something a person never says aloud in
# this world, so a single hit is enough to withhold the line. "（把热美式推过
# 吧台）给，趁烫。" and "我先走了。" must keep broadcasting.
_PRIVATE_PROTOCOL_TOKENS = re.compile(
    r"(?i)\b(?:inner|arguments|tool_calls|valid call)\b"
    r"|记忆调用|格式错|指令词|占一格")
# A concealment / plan-of-record pledge (controlled phrases) or the
# combination "不急着" + a preposition + an addressee + a speech verb within
# one clause (不急着对陈默说) — the preposition is required so a genuine
# "这事不急着说" is not swallowed.
_PRIVATE_CONCEALMENT_PLEDGE = re.compile(
    r"一个字(?:都)?不碰"
    r"|不能让他们知道|不能让人知道|不能让他们晓得"
    r"|不让他们知道|别让他们知道"
    r"|记在自己本子"
    r"|不急着[对跟和向给][^。！？\n]{0,20}说")


def looks_like_private_reasoning(text: str) -> str | None:
    """Return the matched private marker for a would-be spoken line, else None.

    Ticket 56: in real-20261001T065553 the `inner` field was clean yet the
    plain text carried private reasoning that T1 broadcast as speech —
    陈默 "…我一个字不碰" (heard 班长/食堂大妈), 林瑶 "…先记在自己本子里，
    不急着对陈默说" (heard 陈默), 林瑶 "记忆调用格式错了——指令词得单独占
    一格" (heard 辅导员/陈默). The match is the audit reading; the engine only
    needs its truthiness."""
    stripped = str(text).strip()
    if not stripped:
        return None
    match = _PRIVATE_PROTOCOL_TOKENS.search(stripped)
    if match is None:
        match = _PRIVATE_CONCEALMENT_PLEDGE.search(stripped)
    return match.group(0) if match is not None else None


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("`"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    return stripped


def _reply_text(message: Mapping[str, Any]) -> str:
    """The reply as text, for the re-ask transcript (content or the calls)."""
    content = str(message.get("content") or "").strip()
    if content:
        return content
    return json.dumps([{"name": (raw.get("function") or {}).get("name"),
                        "arguments": (raw.get("function") or {}).get("arguments")}
                       for raw in message.get("tool_calls") or []], ensure_ascii=False)


def _call_from_envelope(text: str, actor: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse an object-shaped reply through the shared envelope parser.

    Ticket 42: extras now use the same parser as MCs/NPCs (``parse_decision``
    over ``lift_native_call``), so ``inner`` is lifted out and the spoken line
    is the action's own ``text``. ``problem`` is the re-ask when the reply is
    not a usable envelope at all."""
    try:
        intention, _ = parse_decision(actor, _strip_code_fence(text), None)
    except ValueError:
        intention = None
    if intention is None or not isinstance(intention.args, Mapping):
        return None, (_ENVELOPE_REASK + " 要么直接说你那句话，"
                      "要么按 {name, arguments{inner, text}} 的格式调用 speak。")
    args = dict(intention.args)
    if looks_like_protocol_envelope(str(args.get("text", ""))):
        return None, _ENVELOPE_REASK
    return ({"name": intention.kind, "arguments": args, "inner": intention.inner},
            None)


def _extra_calls_from_reply(message: Mapping[str, Any], actor: str
                            ) -> tuple[list[dict[str, Any]], str | None]:
    """One extra reply → calls; a non-None problem means re-ask."""
    calls: list[dict[str, Any]] = []
    for raw in message.get("tool_calls") or []:
        function = raw.get("function") or {}
        name = str(function.get("name", ""))
        try:
            args = json.loads(function.get("arguments") or "{}")
            if not isinstance(args, dict):
                raise ValueError("arguments must be a JSON object")
        except (ValueError, TypeError) as exc:
            calls.append({"name": name, "arguments": {}, "tool_call_id": raw.get("id"),
                          "parse_error": f"{type(exc).__name__}: {exc}"})
            continue
        # Ticket 38: SPEAK_TOOLS declares inner; extras' inbox is envelope-free,
        # so lift the monologue out of the arguments before it reaches the
        # kernel (never reject an extra over it). It stays on the call, never
        # inside `arguments`.
        args, inner, _inner_error = lift_native_call(name, args)
        if looks_like_protocol_envelope(str(args.get("text", ""))):
            return [], _ENVELOPE_REASK
        calls.append({"name": name, "arguments": args,
                      "tool_call_id": raw.get("id"), "inner": inner})
    if calls:
        return calls, None
    text = str(message.get("content") or "").strip()
    if not text:
        return [], None
    # Models sometimes answer with an inline decision JSON instead of a tool
    # call ({"inner":..., "name":"speak", "arguments":{...}}) — that is the
    # envelope, parsed by the shared parser, never spoken. Anything else
    # object-shaped is a formatting error, not a line.
    if looks_like_protocol_envelope(_strip_code_fence(text)):
        call, problem = _call_from_envelope(text, actor)
        return ([call], None) if problem is None else ([], problem)
    # No volume/to: the kernel treats a speak without volume as
    # engine-constructed normal speech (T1), broadcast to everyone
    # present — exactly like an MC's plain-text reply.
    return [{"name": "speak", "arguments": {"text": text}, "inner": None}], None


def extra_tool_calls(provider: Any, system_text: str, briefing_text: str, *,
                     actor: str = "extra", attempts: int = 3) -> list[dict[str, Any]]:
    """One extras turn under the v4 protocol (V4-AGENT-INTERFACE §5): the
    extra's whole world is the briefing; its tool surface is speak-only.
    Returns the parsed tool-call list (same shape as the v4 agents).

    T1 文本即说话 applies to extras too: a reply with plain text and no
    tool_calls is that extra's spoken words — synthesize the speak call.
    (The live run showed models often answer in prose; dropping the text
    left extras permanently silent.)

    Ticket 42: a reply that is the protocol envelope is re-asked (same
    failure→retry convention as the MC session); if it stays envelope-shaped,
    the extra says nothing this turn — raw protocol JSON is never spoken."""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_text}]
    if briefing_text:
        messages.append({"role": "user", "content": briefing_text})
    for _attempt in range(max(1, attempts)):
        message = provider.chat_with_tools(messages, SPEAK_TOOLS)
        calls, problem = _extra_calls_from_reply(message, actor)
        if problem is None:
            return calls
        # Show the extra its own rejected reply, then the self-correcting
        # re-ask — the model must be able to see what it did wrong.
        messages = messages + [
            {"role": "assistant", "content": _reply_text(message)[:400]},
            {"role": "user", "content": problem}]
    return []
