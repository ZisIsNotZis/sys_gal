"""世界消息渲染（V4-AGENT-INTERFACE.md §3 块结构）。

事件行 = 第三人称客观编年体、观察者无关：同一事件对所有可见者逐字相同，
"谁看到了"由投递表达（出现在谁的消息里=谁观察到了），绝不出现第二人称。
私有投递（读到的内容、耳语文本、消息文本）以缩进行只出现在收件人消息里。
每种事件 kind 恰好一个固定模板；未知 kind 一律跳过，绝不即兴。
"""

from typing import Any, Mapping
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


def render_world_message(perception: Mapping[str, Any], affordances: list[Mapping[str, Any]],
                         *, observer: str | None = None, errors: list[str] | None = None,
                         knowledge_lines: list[str] | None = None,
                         flashback_lines: list[str] | None = None,
                         director: str | None = None) -> str:
    """V4-AGENT-INTERFACE §3：表头恒在，#error/#flashback/#events/#knowledge
    空块省略，#actions 恒在；director 非 None 时置顶 [director] 块（NPC 简报）。
    observer 缺省取 perception["observer"]（旧调用方兼容）。"""
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
    notice = perception.get("situational_notice")
    if notice:
        lines.append(str(notice))

    error_block = list(errors or []) if errors is not None else []
    # docs §3 修订：#error 块废除——每次工具调用的结果以 role:"tool" 消息回填
    # 会话。errors 形参仅为旧调用方兼容保留，不再渲染。

    if flashback_lines:
        lines.append("")
        lines.append("# flashback")
        lines.extend(flashback_lines)

    event_lines = _event_lines(perception, who)
    if event_lines:
        lines.append("")
        lines.append("# events")
        lines.extend(event_lines)

    knowledge = list(knowledge_lines or [])
    if knowledge_lines is None:
        # 旧协议兼容：场景/条目描述即知识块。
        for entity, description in perception.get("descriptions", {}).items():
            knowledge.append(f"[{entity}]: {_clean_description(description)}")
    if knowledge:
        lines.append("")
        lines.append("# knowledge")
        lines.extend(knowledge)

    lines.append("")
    lines.append("# actions")
    lines.extend(_merged_action_lines(affordances))
    return "\n".join(lines)


def _merged_action_lines(affordances: list[Mapping[str, Any]]) -> list[str]:
    """docs §3：同类动作合并为一行——按 (kind, 参数键集合) 分组，同组对应值
    用 、 连接（[drop] item=X、Y）。speak 的 volume/to 由 affordance 自身
    表达（normal/whisper、在场者候选、无人在场时自言自语）。"""
    groups: dict[tuple, dict[str, list[str]]] = {}
    order: list[tuple] = []
    for option in affordances:
        kind = str(option.get("kind", "?"))
        args = {k: v for k, v in option.items() if k != "kind" and v not in (None, "", {})}
        key = (kind, tuple(sorted(args)))
        if key not in groups:
            groups[key] = {k: [] for k in args}
            order.append(key)
        for k, v in args.items():
            items = v if isinstance(v, (list, tuple)) else [v]
            for item in items:
                text = str(item)
                if text not in groups[key][k]:
                    groups[key][k].append(text)
    lines: list[str] = []
    for key in order:
        kind, arg_keys = key
        solo = bool(groups[key].get("solo"))
        rendered_keys = [k for k in arg_keys if k != "solo"]
        rendered_keys.sort(key=lambda k: (k != "volume", k))  # volume 首位
        if not rendered_keys:
            lines.append(f"[{kind}]{'（自言自语）' if solo else ''}")
            continue
        parts = [f"{k}={'、'.join(groups[key][k])}" for k in rendered_keys]
        line = f"[{kind}] {', '.join(parts)}"
        if solo:
            line += "（自言自语）"
        lines.append(line)
    return lines


def _action_args(option: Mapping[str, Any]) -> str:
    parts = []
    for key, value in option.items():
        if key == "kind" or value is None or value == "" or value == {}:
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def _affordance_sentence(option: Mapping[str, Any]) -> str:
    return _action_args(option)


def _event_lines(perception: Mapping[str, Any], observer: str) -> list[str]:
    lines: list[str] = []
    location = str(perception.get("location", ""))
    for event in perception.get("events", []):
        sentence = _event_sentence(event, location)
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


def _event_sentence(event: Mapping[str, Any], location: str = "") -> str | None:
    """第三人称编年体：同一事件对所有可见者逐字相同（docs §0/§3）。"""
    payload = event.get("payload", {})
    kind = event.get("kind")
    who = str(event.get("actor", ""))
    if kind == "speech":
        if payload.get("volume") == "whisper":
            targets = "、".join(str(t) for t in payload.get("to", []) or [])
            return f"{who} 凑近 {targets} 耳语了几句"
        heard = [str(x) for x in payload.get("heard", []) or []]
        audience = f"（{'、'.join(heard)} 听见）" if heard else ""
        return f"{who} 说{audience}：\"{payload.get('text')}\""
    if kind == "enter":
        return f"{who} 进入 {payload.get('location')}"
    if kind == "leave":
        return f"{who} 离开 {payload.get('location')}"
    if kind == "message_delivered":
        return f"{who} 发消息给 {payload.get('target')}（电话）"
    if kind == "take":
        return f"{who} 拿起 {payload.get('item')}"
    if kind == "drop":
        return f"{who} 放下 {payload.get('item')}"
    if kind == "give":
        return f"{who} 把 {payload.get('item')} 交给 {payload.get('target')}"
    if kind == "item_given":
        return f"{payload.get('from')} 把 {payload.get('item')} 交给 {payload.get('to')}"
    if kind == "document_read":
        return f"{who} 读了 {payload.get('document')}"
    if kind == "document_copied":
        return f"{who} 复制 {payload.get('document')} 为 {payload.get('copy')}"
    if kind == "document_labeled":
        return f"{who} 把 {payload.get('document')} 标记为 {payload.get('label')}"
    if kind == "document_annotated":
        return f"{who} 在 {payload.get('document')} 上留下批注"
    if kind == "documents_compared":
        return f"{who} 比对 {payload.get('first')} 与 {payload.get('second')}"
    if kind == "item_inspected":
        return f"{who} 检查了 {payload.get('item')}"
    if kind == "location_searched":
        return f"{who} 搜索了{location or '这里'}"
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
        if action == "drop":
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
    if kind == "extra_arrived":
        return f"{who} 出现了"
    if kind == "extra_removed":
        return f"{who} 走了"
    if kind.startswith("system_"):
        return _system_sentence(kind, payload)
    # move 的 started/completed（enter/leave 已承载）、wait/sleep 完成、
    # 私有簿记（message_sent/interrupt_requested/wait_woken/private_wake/
    # time_advanced）与未知 kind：一律不渲染。
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
    if kind == "document_read" and observer == who:
        content = str(payload.get("content", ""))
        annotations = payload.get("annotations") or []
        if annotations:
            notes = "；".join(f"{e.get('by')}批注：{e.get('text')}" for e in annotations)
            content = f"{content}（记录上还有：{notes}）" if content else f"（记录上还有：{notes}）"
        return f"内容：{content}" if content else None
    if kind == "documents_compared" and observer == who:
        return f"比对结果：{'一致' if payload.get('same_content') else '不一致'}"
    if kind == "knock" and observer == who:
        return "有人应声。" if payload.get("responded") else "没有人回应。"
    if kind == "interaction" and observer == who:
        return "里面有人听见了。" if payload.get("responded") else "没有人回应。"
    if kind == "location_searched" and observer == who:
        found = "、".join(str(x) for x in payload.get("items", []) or [])
        return f"搜到：{found}" if found else "没什么新发现"
    if kind == "item_inspected" and observer == who:
        if payload.get("held"):
            return "它正在你手里"
        return f"它放在{payload.get('location')}"
    if kind == "action_completed" and observer == who:
        if payload.get("action") == "wait":
            seconds = int(payload.get("duration_seconds", 0) or 0)
            return f"等了{seconds // 60}分钟，现在空下来了。"
        if payload.get("action") == "sleep":
            return "睡了一觉，醒了。"
    return None


def _system_sentence(kind: str, payload: Mapping[str, Any]) -> str:
    """System 事件叙述：system_* 事件仅对受约束角色可见，属私有投递。"""
    name = str(payload.get("system_name", "台账"))
    if kind == "system_case_accepted":
        terms = "、".join(str(t) for t in payload.get("terms", []))
        return (f"{name}的声音在你耳边响起：案子接下了。它要你答上三件事里的门道——{terms}。"
                f"答对了，{name}给你一样东西：{payload.get('reward_offer')}。")
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
                 perception: Mapping[str, Any], affordances: list[Mapping[str, Any]]) -> str:
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
        "type 必须是上面列出的动作之一；参数名照抄供给列表：inspect 用 item；read/copy/label/"
        "annotate 用 document；compare 用 first 和 second；move 用 target；send_message 和 "
        "give 用 target；wait/sleep 用 duration_seconds。speak 可带 volume（whisper 时必须带 "
        "to=[在场的听众]）。updates 只放你私人的 goals/beliefs/memories/interpretations/"
        "private_notes，没有就省略。无法成形的意图，就用自然语言描述（不要 JSON）。",
    ))
