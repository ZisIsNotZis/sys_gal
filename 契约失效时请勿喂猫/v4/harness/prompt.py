"""世界消息渲染（V4-AGENT-INTERFACE.md §3 块结构）。

事件行 = 第三人称客观编年体、观察者无关：同一事件对所有可见者逐字相同，
"谁看到了"由投递表达（出现在谁的消息里=谁观察到了），绝不出现第二人称。
私有投递（读到的内容、耳语文本、消息文本）以缩进行只出现在收件人消息里。
每种事件 kind 恰好一个固定模板；未知 kind 一律跳过，绝不即兴。
"""

from typing import Any, Mapping, Sequence
from .agent_state import PrivateState

_WEEKDAY = "一二三四五六日"


def _clock(iso: str) -> str:
    """ISO 时间 → 世界时间 9/16(周三) 7:00（docs §1 常识格式）。"""
    text = str(iso)
    try:
        from datetime import datetime
        moment = datetime.fromisoformat(text)
        return (f"{moment.month}/{moment.day}({_WEEKDAY[moment.weekday()]}) "
                f"{moment.hour}:{moment.minute:02d}")
    except ValueError:
        return text


def _stamp(iso: str) -> str:
    return _clock(iso)


def _clean_description(description: str) -> str:
    """描述块整理：去掉 markdown 标题行与内部空行（空行会让下一条的归属含混）。"""
    body = "\n".join(ln for ln in str(description).splitlines() if ln.strip())
    while body.startswith("#"):
        body = body.split("\n", 1)[1] if "\n" in body else ""
        body = body.lstrip("\n")
    return body.strip()


# 票 85（报 81 §3 的提示层移交）：NPC 唤醒时的两条约束。它们不是种子数据——
# 报告 §P2 的两处失效都发生在同一角色同一段简报下：七次"我马上给你打"没有一次
# `give`（话语被当成交付），以及"长柄勺找不着"（断言了世界从未发生的物件移动，
# 而 `例汤` 的描写原文是"桶边搭着一把长柄勺"）。因此它们是 `[director]` 块的固定
# 开头，种子写的本场目标接在后面。
NPC_WAKE_RULES = (
    "【说话不改变世界】\n"
    "- 只有工具调用能改变世界：说「我给你」「我去拿」「我马上给你打」什么都不会发生。"
    "要交付就真的用 give 把东西递到在场的某人手上，要取物用 take，要放下用 place；"
    "做不到就直说做不到。\n"
    "- 不许断言或否认世界状态的改变（「勺子没了」「已经登记好了」「东西被挪走了」），"
    "除非你亲眼看到那条事件；这条消息里你感知到的事实，就是此刻的事实。\n"
)


def director_block(brief: str | None = None) -> str:
    """NPC 唤醒时的 `[director]` 块：`NPC_WAKE_RULES` 在前，本场简报接在其后。

    简报可以缺（种子没给该角色写本场目标），约束不能缺：它是提示层的，不是种子侧的。
    """
    text = str(brief or "").strip()
    return NPC_WAKE_RULES + ("\n" + text if text else "")


def render_world_message(perception: Mapping[str, Any], affordances: Sequence[Mapping[str, Any]] | None = None,
                         *, observer: str | None = None,
                         knowledge_lines: list[str] | None = None,
                         director: str | None = None) -> str:
    """V4-AGENT-INTERFACE §3：表头恒在，#events/#knowledge 空块省略，
    #actions 恒在；director 非 None 时置顶 [director] 块（NPC 简报，由
    `director_block()` 组装）。observer 缺省取 perception["observer"]（旧调用方兼容）。"""
    who = str(observer if observer is not None else perception.get("observer", ""))
    lines: list[str] = []
    if director is not None:
        lines.append("[director]")
        lines.append(str(director))
        lines.append("")
    lines.append(f"{_clock(str(perception.get('time', '')))} @{perception.get('location')}")
    presence = [f"{who}(you)"] + sorted(
        str(x) for x in perception.get("nearby_actors", []) if str(x) != who)
    lines.append("在场：" + "，".join(presence))
    inventory = sorted(str(x) for x in perception.get("inventory", []))
    if inventory:
        lines.append("身上：" + "、".join(inventory))
    nearby = sorted(str(x) for x in perception.get("nearby_items", []))
    if nearby:
        lines.append("附近：" + "、".join(nearby))
    # Ticket 88: a persistent note is an addressable record lying here. Its
    # content is not perception — it is read with `read <id>`.
    notes = list(perception.get("notes_here") or ())
    if notes:
        lines.append("字条：" + "、".join(
            f"{str(note.get('id'))}（{note.get('author')} 于 "
            f"{_clock(str(note.get('left_at')))} 留，读全文用 read）"
            for note in notes))
    action_state = _action_state_sentence(perception.get("action_state"))
    if action_state:
        lines.append(action_state)
    notice = perception.get("situational_notice")
    if notice:
        lines.append(str(notice))

    event_lines = _event_lines(perception, who)
    if event_lines:
        lines.append("")
        lines.append("# events")
        lines.extend(event_lines)

    # Ticket 66: a message from someone the actor has not recorded. The world
    # never edits the address book for the actor; it hands back the executable
    # way to close the gap so a reply is possible.
    for sender in perception.get("unrecorded_senders", []) or []:
        name = str(sender)
        lines.append(f"（{name} 还不在你的通讯录里——要回信，先用 update_memory 记下他："
                     f"keys=[\"!contact\", \"{name}\"]、op=\"open\"，再 text {name}。）")

    knowledge = list(knowledge_lines or [])
    if knowledge_lines is None:
        # 旧协议兼容：场景/条目描述即知识块。
        for entity, description in perception.get("descriptions", {}).items():
            knowledge.append(f"[{entity}]: {_clean_description(description)}")
    if knowledge:
        lines.append("")
        lines.append("# knowledge")
        lines.extend(knowledge)

    return "\n".join(lines)


def _action_state_sentence(state: Any) -> str | None:
    """Render the actor's own action lifecycle without exposing its payload.

    In particular, a response wait is a separate state after speech has
    completed; it must never read as the actor continuing to speak.
    """
    if not isinstance(state, Mapping):
        return None
    status = str(state.get("status", ""))
    action = str(state.get("action", "action"))
    if status == "interrupted":
        remaining = int(state.get("remaining_seconds", 0) or 0)
        minutes = max(1, (remaining + 59) // 60)
        interrupted_by = str(state.get("interrupted_by", "someone"))
        detail = state.get("target", state.get("item"))
        action_name = f"{action} {detail}" if detail else action
        return (f"行动状态：{action_name} 被 {interrupted_by} 打断，还剩约 {minutes} 分钟；"
                '先调用 {"name": "continue_action", "arguments": {}} 无损继续，或 '
                '{"name": "abandon_action", "arguments": {}} 放弃。')
    until = _clock(str(state.get("until", "")))
    if status == "waiting_for_response":
        recipients = "、".join(str(x) for x in state.get("response_to", []) or []) or "对方"
        response_action = str(state.get("response_action", action))
        completed = "这句话已说完" if response_action == "speak" else "短信已送达"
        return (f"行动状态：{completed}；正在等{recipients}回应，最迟到 {until}，"
                "有人回应会提前叫醒。")
    target = state.get("target")
    item = state.get("item")
    if action == "speak":
        after = ("之后另行等待回应" if state.get("will_wait_for_response")
                 else "之后不自动等待回应")
        return f"行动状态：这句话的说话动作将在 {until} 完成（一个 tick）；{after}。"
    if action == "text":
        after = ("之后另行等待回应" if state.get("will_wait_for_response")
                 else "之后不自动等待回应")
        return f"行动状态：给{target or '收件人'}的短信将在 {until} 送达；{after}。"
    if action == "move":
        return f"行动状态：正在前往{target or '目的地'}，预计 {until} 到达。"
    if action in {"wait", "sleep"}:
        return f"行动状态：正在等待至 {until}。"
    subject = f" {item}" if item else (f" {target}" if target else "")
    return f"行动状态：正在完成 {action}{subject}，预计 {until} 完成。"


def _action_args(option: Mapping[str, Any]) -> str:
    parts = []
    for key, value in option.items():
        if key == "kind" or value is None or value == "" or value == {}:
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def _event_lines(perception: Mapping[str, Any], observer: str) -> list[str]:
    lines: list[str] = []
    location = str(perception.get("location", ""))
    for event in perception.get("events", []):
        sentence = _event_sentence(event, location, observer=observer)
        private = _private_line(event, observer)
        if not sentence and not private:
            continue
        if sentence:
            lines.append(f"{_stamp(str(event.get('time', '')))} {sentence}")
            if private:
                lines.append(f"  └ {private}")
        else:
            # 仅私有投递（如自己的 wait/sleep 完成，V4-DESIGN §5.7）。
            lines.append(f"{_stamp(str(event.get('time', '')))} {private}")
    return lines


def _event_sentence(event: Mapping[str, Any], location: str = "",
                    observer: str | None = None) -> str | None:
    """第三人称编年体：同一事件对所有可见者逐字相同（docs §0/§3）。

    惟一的观察者例外（ticket 23）：短信的送达行——收件人读到"收到来自 X
    的短信"，发件人读到送达回执；双方各自的行不同，但各自的行对同一观察者
    仍然确定、与渲染时点无关。"""
    payload = event.get("payload", {})
    kind = event.get("kind")
    who = str(event.get("actor", ""))
    if kind == "speech":
        if payload.get("volume") == "whisper":
            targets = "、".join(str(t) for t in payload.get("to", []) or [])
            return f"{who}凑近{targets}耳语了几句"
        # Ruling 2026-09-22: no space before 说; addressed speech names the
        # target(s); a parenthetical appears only when third parties also
        # heard (heard minus the addressed targets). Plain broadcast has none.
        to = [str(t) for t in payload.get("to", []) or []]
        heard = [str(x) for x in payload.get("heard", []) or []]
        text = payload.get("text")
        if to:
            others = [x for x in heard if x not in to]
            line = f"{who}对{'、'.join(to)}说：\"{text}\""
            if others:
                line += f"（{'、'.join(others)}也听见）"
            return line
        return f"{who}说：\"{text}\""
    if kind == "enter":
        return f"{who} 进入 {payload.get('location')}"
    if kind == "leave":
        return f"{who} 离开 {payload.get('location')}"
    if kind == "message_delivered":
        # Ticket 23: the recipient reads this as the SMS THEY received, not
        # as a third party's action; the sender reads the delivery receipt.
        if observer == str(payload.get("target")):
            return f"收到来自 {who} 的短信"
        if observer == who:
            return f"短信已送达 {payload.get('target')}（手机）"
        return f"{who} 发消息给 {payload.get('target')}（手机）"
    if kind == "take":
        return f"{who} 拿起 {payload.get('item')}"
    if kind == "place":
        return f"{who} 放下 {payload.get('item')}"
    if kind == "give":
        return f"{who} 把 {payload.get('item')} 交给 {payload.get('target')}"
    if kind == "item_given":
        return f"{payload.get('from')} 把 {payload.get('item')} 交给 {payload.get('to')}"
    if kind == "document_read":
        return f"{who} 读了 {payload.get('document')}"
    if kind == "document_annotated":
        # 票 95（E98）：同地点的人只看见“谁在文书上写了字”，正文要自己 read。
        return f"{who} 在 {payload.get('document')} 上留下批注"
    if kind == "note_left":
        if payload.get("persist"):
            note_id = payload.get("note")
            return (f"{who} 留下一份留得住的文稿（{note_id}）" if note_id
                    else f"{who} 留下一份留得住的文稿")
        return f"{who} 留下一张字条（内容仅对下一位进入者可见，阅后即焚）"
    if kind == "item_trashed":
        return f"{who} 销毁了 {payload.get('item')}"
    if kind == "knock":
        return f"{who} 敲了 {payload.get('target')} 的门"
    if kind == "interaction":
        return f"{who} 与 {payload.get('target')} 互动（{payload.get('verb')}）"
    if kind == "action_completed":
        action = payload.get("action")
        if action in {"wait", "sleep"}:
            return None  #  own completion 走私有投递行（V4-DESIGN §5.7）
        if action == "move":
            return None  # enter/leave 已承载
        if action in {"send_message", "speak", "read", "copy", "label",
                      "compare", "annotate"}:
            return None  # 专用事件已承载
        if action == "open":
            return f"{who} 把{location or '这里'}打开了"
        if action == "close":
            return f"{who} 把{location or '这里'}关上了"
        if action == "take":
            return f"{who} 拿起 {payload.get('item')}"
        if action == "place":
            return f"{who} 放下 {payload.get('item')}"
        return None
    if kind == "action_interrupted":
        return f"{who} 的「{payload.get('action')}」被 {payload.get('by')} 打断了"
    if kind == "action_resumed":
        return f"{who} 继续做「{payload.get('action')}」"
    if kind == "action_abandoned":
        return f"{who} 放弃了「{payload.get('action')}」"
    if kind == "world_event":
        notice = payload.get("notice")
        return str(notice) if notice else f"发生了一件事：{payload.get('event', '事件')}。"
    if kind == "item_dropped":
        # E84（报 81 §5）：extra 被回收时，它手里的东西落回最后所在地点。这是
        # 客观事实，同地的人看得见——否则物品虽然回到了世上，却没人知道它回来了。
        return f"{who} 离开时，{payload.get('item')} 留在了{payload.get('location') or location or '这里'}"
    if kind == "extra_arrived":
        return f"{who} 出现了"
    if kind == "extra_removed":
        # Ticket 42: an idle despawn is an interruption, not a farewell — a
        # character mid-conversation may not read "他走了" as "他答应了".
        # The line only states the objective break; it never summarizes words.
        if str(payload.get("reason") or "") == "idle":
            return f"{who} 走开了，刚才的交谈就此中断"
        return f"{who} 走了"
    if kind == "system_dialogue":
        # 票 95（E95）：对话审计事件只供日志与复核，不是角色能“听见”的一句话。
        return None
    if kind and kind.startswith("system_"):
        return _system_sentence(kind, payload)
    # move 的 started/completed（enter/leave 已承载）、wait/sleep 完成、
    # 私有簿记（message_sent/interrupt_requested/wait_woken/private_wake/
    # private_wake_failed/time_advanced）与未知 kind：一律不渲染。
    return None


def _private_line(event: Mapping[str, Any], observer: str) -> str | None:
    """私有投递：只出现在收件人/读者本人的消息里（docs §3）。"""
    payload = event.get("payload", {})
    kind = event.get("kind")
    who = str(event.get("actor", ""))
    if kind == "speech" and payload.get("volume") == "whisper":
        if observer in [str(t) for t in payload.get("to", []) or []]:
            return f"耳语内容：\"{payload.get('text')}\""
        return None
    if kind == "message_delivered" and observer == str(payload.get("target")):
        return f"消息内容：\"{payload.get('text')}\""
    if kind == "note_read" and observer in [str(r) for r in payload.get("readers", ()) or []]:
        # The envelope's author and posting time come from the engine-held note,
        # not from model-authored text. Keep compatibility with old traces.
        left_at = payload.get("left_at")
        authorship = (f"（{payload.get('author')} 于 {_clock(str(left_at))} 留）"
                      if left_at else f"（{payload.get('author')} 留）")
        return (f"字条内容：\"{payload.get('text')}\"{authorship}"
                "（字条已阅，随即化去）")
    # document_read 的 content 不在这里投递——它是 read 调用的 tool 结果
    # （V4-AGENT-INTERFACE §3）：公开行只描述事实。
    # Ticket 49 例外：stay-read 没有 tool 调用，停留满 reading_seconds 后正文
    # 由这条私有投递送到读者本人（auto 标记区分于主动 read）。
    if kind == "document_read" and payload.get("auto") and observer == who:
        title = str(payload.get("title") or payload.get("document") or "")
        content = str(payload.get("content") or "")
        if content:
            return f"（你在此处停留足够，已读完《{title}》）{content}"
        return f"（你在此处停留足够，已翻完《{title}》，没有可读的正文。）"
    # documents_compared 的判定在 compare 调用的 tool 结果里。
    if kind == "knock" and observer == who:
        return "有人应声。" if payload.get("responded") else "没有人回应。"
    if kind == "interaction" and observer == who:
        return "里面有人听见了。" if payload.get("responded") else "没有人回应。"
    return None


def _system_sentence(kind: str, payload: Mapping[str, Any]) -> str:
    """System 事件叙述：system_* 事件仅对受约束角色可见，属私有投递。"""
    name = str(payload.get("system_name", "台账"))
    if kind == "system_case_accepted":
        terms = "、".join(str(t) for t in payload.get("terms", []))
        return (f"{name}的声音在你耳边响起：案子接下了。它要你答上三件事里的门道——{terms}。"
                f"答对了，{name}给你一样东西：{payload.get('reward_offer')}。"
                f"要问它，就当面对着「{name}」说话（speak 的 to 写它的名字）；"
                "它只答自己案卷里记着的条目，答不了就告诉你不知道。")
    if kind == "system_answer":
        return f"{name}在你脑子里缓缓开口：「{payload.get('answer')}」。"
    if kind == "system_reward_granted":
        return f"{name}履约了。你得到了：{payload.get('reward')}。"
    if kind == "system_penalty_applied":
        return f"{name}冷冷地记下一笔：{payload.get('penalty')}。"
    return f"{name}记下了这一笔。"


def _affordance_sentence(option: Mapping[str, Any]) -> str:
    return _action_args(option)


def build_prompt(*, identity: str, private_seed: str, state: PrivateState,
                 perception: Mapping[str, Any], affordances: Sequence[Mapping[str, Any]]) -> str:
    """完整的一次性角色输入（无隐藏世界或作者数据）。协议压缩在末尾。"""
    return "\n".join((
        "你就是下面描述的这个人。把这个世界当作真的。",
        "绝不提 agent、提示词、模拟、作者或剧情。",
        "只追你自己的欲望、恐惧、责任和关系。一次只做一个具体动作。",
        "你以这个人的经历、知识、习惯、恐惧、牵挂和局限来想事情，全程在角色里。",
        "以真实人的节奏行动：别刷屏式发消息，别做无谓的动作；空闲时，去找你在乎的人。",
        f"IDENTITY:\n{identity}",
        f"PRIVATE SEED MATERIAL:\n{private_seed}",
        f"PRIVATE MEMORY AND BELIEFS:\n{state.snapshot()}",
        f"CURRENT PERCEPTION:\n{dict(perception)}",
        "Operational facts 是权威的本地反馈：被拒的动作什么都没改变；照世界建议的做法来，"
        "条件没变就不要原样重复。",
        f"LEGAL ACTION SHAPES:\n{[dict(x) for x in affordances]}",
        "只输出一个 JSON 对象，先想后动，inner 永远在最前："
        '{"inner":"你的第一人称心声，几句话","type":"动作名","args":{...},"updates":{...}}。'
        "type 必须是上面列出的动作之一；参数名照抄供给列表：take/place/give/read "
        "用 item；compare 用 first 和 second；move 用 target（要带同在此地的人一起走，另加 "
        "with=[名字]）；send_message 和 "
        "give 用 target；wait 用 duration_seconds。speak 可带 volume（whisper 时必须带 "
        "to=[在场的听众]）。updates 只放你私人的 goals/beliefs/memories/interpretations/"
        "private_notes，没有就省略。无法成形的意图，就用自然语言描述（不要 JSON）。",
    ))
