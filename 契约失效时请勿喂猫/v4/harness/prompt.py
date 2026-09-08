"""中文沉浸叙事：把角色可见的感知差量渲染成第二人称、现在时的世界文本。

设计真理：v4/docs/V4-DESIGN.md §2——世界文本是 GM 旁白，不是状态机回执；
时间戳嵌在事件行里；协议指令只出现在最末尾。
"""

from typing import Any, Mapping
from .agent_state import PrivateState


def _clock(iso: str) -> str:
    """ISO 时间 → 叙事时间（MM 月 DD 日 HH:MM）。"""
    return iso[5:16].replace("T", "日 ") if len(iso) >= 16 else iso


def _clean_description(description: str) -> str:
    """描述块整理：去掉 markdown 标题行与内部空行（空行会让下一条的归属含混）。"""
    body = "\n".join(ln for ln in str(description).splitlines() if ln.strip())
    while body.startswith("#"):
        body = body.split("\n", 1)[1] if "\n" in body else ""
        body = body.lstrip("\n")
    return body.strip()


def render_world_message(perception: Mapping[str, Any], affordances: list[Mapping[str, Any]]) -> str:
    """只渲染角色可见的感知差量（V4-DESIGN §2/§5.2）。"""
    lines = [f"现在是{_clock(str(perception.get('time', '')))}，你在{perception.get('location')}。"]
    if perception.get("busy_until"):
        lines.append(f"你手上的事还没完，要忙到{str(perception['busy_until'])[11:16]}。")
    pending = perception.get("pending")
    if pending:
        lines.append(f"你正做着的「{pending.get('action')}」被打断了（剩约 "
                     f"{int(pending.get('remaining_seconds', 0)) // 60} 分钟，打断你的人："
                     f"{pending.get('interrupted_by')}）。你可以选择继续做完，或者就此作罢。")
    for message in perception.get("inbox", []):
        lines.append(f"你收到一条来自{message.get('from')}的消息：{message.get('text')}")
    for fact in perception.get("operational_facts", []):
        action = fact.get("action", {})
        line = (f"你刚才想做的「{action.get('kind')}」没有成功，什么也没改变。"
                f"原因：{fact.get('reason')}。")
        alternatives = fact.get("alternatives")
        if alternatives:
            line += "或许可以：" + "；".join(str(a) for a in alternatives) + "。"
        lines.append(line)
    for event in perception.get("events", []):
        stamp = str(event.get("time", ""))[11:16]
        sentence = _event_sentence(event, str(perception.get("observer", "")),
                                   str(perception.get("location", "")))
        if sentence:
            lines.append(f"[{stamp}] {sentence}")
    first_desc = True
    for entity, description in perception.get("descriptions", {}).items():
        if first_desc:
            first_desc = False
        else:
            lines.append("")
        lines.append(f"{entity}：{_clean_description(description)}")
    notice = perception.get("situational_notice")
    if notice:
        lines.append(str(notice))
    if affordances:
        lines.append("你现在可以具体地：")
        lines.extend(f"  - {_affordance_sentence(x)}" for x in affordances)
    return "\n".join(lines)


def _event_sentence(event: Mapping[str, Any], observer: str = "", location: str = "") -> str:
    payload = event.get("payload", {})
    kind = event.get("kind")
    who = str(event.get("actor", ""))
    if kind == "speech":
        return f"{who}说：「{payload.get('text')}」"
    if kind == "enter":
        if who == observer:
            return f"你到了{payload.get('location')}。"
        return f"{who}进入了{payload.get('location')}。"
    if kind == "leave":
        if who == observer:
            return f"你离开了{payload.get('location')}。"
        return f"{who}离开了{payload.get('location')}。"
    if kind == "world_event":
        event_name = payload.get("event", "事件")
        notice = payload.get("notice")
        if notice:
            return f"{notice}"
        return f"发生了一件事：{event_name}。"
    if kind == "item_inspected":
        held = "它正在你手里" if payload.get("held") else f"它放在{payload.get('location')}"
        return f"你细看了{payload.get('item')}；{held}。"
    if kind == "location_searched":
        if who == observer:
            found = "、".join(payload.get("items", []) or [])
            return f"你搜了{location or '这里'}一圈：{found or '没什么新发现'}。"
        return f"{who}在{location or '这里'}翻了翻。"
    if kind == "item_inspected":
        pass  # handled above
    if kind == "knock":
        responded = "里面有人应声。" if payload.get("responded") else "没有人回应。"
        return f"你敲了敲{payload.get('target')}的门。{responded}"
    if kind == "interaction":
        responded = "里面有人听见了。" if payload.get("responded") else "没有人回应。"
        return f"你和{payload.get('target')}互动（{payload.get('verb')}）。{responded}"
    if kind == "item_given":
        if str(payload.get("from")) == observer:
            return f"你把{payload.get('item')}交给了{payload.get('to')}。"
        return f"{payload.get('from')}把{payload.get('item')}交给了你。"
    if kind == "document_read":
        line = f"你读完了{payload.get('title')}：{payload.get('content')}"
        annotations = payload.get("annotations")
        if annotations:
            notes = "；".join(
                f"{entry.get('by')}批注：{entry.get('text')}" for entry in annotations)
            line += f"（记录上还有：{notes}）"
        return line
    if kind == "document_annotated":
        return f"{who}在{payload.get('document')}上写了一条批注。"
    if kind == "document_copied":
        if who == observer:
            return f"你把{payload.get('document')}复印了一份，编号{payload.get('copy')}。"
        return f"{who}复印了一份{payload.get('document')}。"
    if kind == "documents_compared":
        if who == observer:
            result = "一致" if payload.get("same_content") else "不一致"
            return f"你比对了{payload.get('first')}和{payload.get('second')}：内容{result}。"
        return f"{who}比对了{payload.get('first')}和{payload.get('second')}。"
    if kind == "document_labeled":
        return f"{who}给{payload.get('document')}贴了标签：「{payload.get('label')}」。"
    if kind == "message_delivered":
        if str(event.get("actor")) == observer:
            return f"你发给{payload.get('target')}的消息送到了。"
        return f"你的手机震了一下，一条消息进来。"
    if kind == "action_completed":
        action = payload.get("action")
        if who == observer:
            if action == "move":
                return None  # enter 事件已报告到达
            if action == "wait":
                seconds = int(payload.get("duration_seconds", 0))
                return f"你等了{seconds // 60}分钟，现在空下来了。"
            if action == "sleep":
                return "你睡了一觉，醒了。"
            if action == "open":
                return f"你把{location or '这里'}打开了，现在谁都能进。"
            if action == "close":
                return f"你把{location or '这里'}关上了。"
            if action == "take":
                return f"你拿起了{payload.get('item')}。"
            if action == "drop":
                return f"你放下了{payload.get('item')}。"
            if action == "send_message":
                return f"你发给{payload.get('target')}的消息已经送出。"
            if action == "speak":
                return "你说完了那段话。"
        else:
            if action == "move":
                return None  # enter/leave 事件已承载到达与离开
            if action in {"send_message", "speak"}:
                return None  # 私事，不进入他人感知叙述
            if action in {"read", "copy", "label", "compare", "annotate"}:
                return f"{who}在翻看{payload.get('document', '文件')}。"
        return None
    if kind == "action_started":
        if who == observer:
            return f"你开始{payload.get('action')}了。"
        if payload.get("action") == "speak":
            return None  # speech 事件本身会带话音
        return None
    if kind == "action_interrupted":
        return (f"{who}手上的「{payload.get('action')}」被打断了"
                f"（{payload.get('by')}叫住了他）。")
    if kind == "action_resumed":
        return f"{who}回去继续做「{payload.get('action')}」了。"
    if kind == "action_abandoned":
        return f"{who}放弃了手头的「{payload.get('action')}」。"
    if kind.startswith("system_"):
        return _system_sentence(kind, payload)
    return None


def _system_sentence(kind: str, payload: Mapping[str, Any]) -> str:
    """System 事件的世界语气叙述；名字来自世界包配置。"""
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
    kind = option.get("kind")
    if kind == "search":
        return "search（搜一搜这里）"
    if kind == "observe":
        return "observe（重新打量四周，刷新一处详述）"
    if kind == "inspect":
        return f"inspect（item={option.get('item')}，细看那样东西）"
    if kind == "knock":
        return f"interact（target={option.get('target')}，verb=knock，敲敲门）"
    if kind == "interact":
        return (f"interact（target={option.get('target')}，verb={option.get('verb')}，"
                f"parameters={option.get('parameters', {})})")
    if kind == "give":
        return f"give（item={option.get('item')}，target={option.get('target')}，递给对方）"
    if kind == "read":
        return f"read（document={option.get('document')}，读）"
    if kind == "copy":
        return f"copy（document={option.get('document')}，复印）"
    if kind == "compare":
        return f"compare（first={option.get('first')}，second={option.get('second')}，比对两份）"
    if kind == "label":
        return "label（document=…，label=你自己的一句话，贴标签）"
    if kind == "annotate":
        return "annotate（document=…，text=你的批注，写在记录上，谁读谁看见）"
    if kind == "wait":
        return "wait（duration_seconds=秒数，等一会儿；一次最多 15 分钟）"
    if kind == "sleep":
        return f"sleep（duration_seconds={option.get('duration_seconds')}，睡一觉）"
    if kind == "move":
        return f"move（target={option.get('target')}，走过去，路上要一阵子）"
    if kind == "send_message":
        return f"send_message（target={option.get('target')}，text=你的原话；五分钟后送达）"
    if kind == "speak":
        return "speak（text=你说的话，volume=normal 全场听得见 / whisper 仅 to 指定的人听见）"
    if kind in {"open", "close"}:
        return f"{kind}（把这里{'打开' if kind == 'open' else '关上'}）"
    if kind == "continue_action":
        return "continue_action（继续做完被打断的事）"
    if kind == "abandon_action":
        return "abandon_action（就此作罢，记作没做成）"
    if kind.startswith("system_"):
        details = ", ".join(f"{key}={value}" for key, value in option.items() if key != "kind")
        return f"{kind}（{details}）" if details else kind
    details = ", ".join(f"{k}={v}" for k, v in option.items() if k != "kind")
    return kind if not details else f"{kind}（{details}）"


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
