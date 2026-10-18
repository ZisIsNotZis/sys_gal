"""Formal JSON Schema validation for the executable action protocol.

This is the single source of truth for each action kind's argument shape.
Shape/type errors — signature drift such as ``read`` submitted with ``item``
instead of ``document`` — are caught here and reported by deriving the message
from the schema, instead of hand-written per-action strings. Semantic checks
(availability, routes, co-location, world state) still live in the kernel.

The rejections deliberately name the expected key and the key actually
provided, so an agent that guesses an argument name can self-correct.

V4-AGENT-INTERFACE §2 is the design truth this file mirrors: ``sleep`` is
merged into ``wait`` and the memory tools (think / update_memory / recall /
flashback) are declared here and consumed by the engine, never by the world
kernel. ``TOOLS`` is the static full-declaration tool array (cache-safe:
never add or remove tools mid-run) sent with every provider call.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from jsonschema import Draft202012Validator

_STR = {"type": "string"}
_INT = {"type": "integer"}
_NO_ARGS = {"type": "object", "properties": {}, "additionalProperties": False}


def _schema(**properties: Any) -> dict[str, Any]:
    return {"type": "object", "required": list(properties),
            "properties": properties, "additionalProperties": False}
_ONE_ITEM = {"type": "object", "required": ["item"],
             "properties": {"item": _STR}, "additionalProperties": False}
_ONE_ITEM_CONTENT = {"type": "object", "required": ["item"],
                     "properties": {"item": _STR},
                     "additionalProperties": False}
_ONE_TARGET = {"type": "object", "required": ["target"],
               "properties": {"target": _STR}, "additionalProperties": False}


SCHEMAS: dict[str, dict[str, Any]] = {
    # Memory tools (V4-AGENT-INTERFACE §2): no world-time cost. A row is its
    # key set; the keys are both its handle and its mention needles.
    "update_memory": {"type": "object", "required": ["rows"],
                      "properties": {"rows": {"type": "array", "minItems": 1,
                                              "items": {"type": "object",
                                                        "required": ["keys", "op"],
                                                        "properties": {"keys": {"type": "array",
                                                                                  "minItems": 1,
                                                                                  "items": _STR},
                                                                       "op": {"type": "string",
                                                                              "enum": ["open", "edit", "close"]},
                                                                       "desc": _STR},
                                                        "additionalProperties": False}}},
                      "additionalProperties": False},
    "recall": {"type": "object", "required": ["keys"],
               "properties": {"keys": {"type": "array", "minItems": 1, "items": _STR},
                              "closed": {"type": "boolean"},
                              "limit": {"type": "integer"}},
               "additionalProperties": False},
    "flashback": {"type": "object", "required": ["entity"],
                  "properties": {"entity": _STR},
                  "additionalProperties": False},
    "wait": {"type": "object", "required": ["duration_seconds"],
             "properties": {"duration_seconds": _INT,
                            "sleep": {"type": "boolean"}},
             "additionalProperties": False},
    # volume: whisper needs the co-located "to" list (kernel validates it).
    # Both volume and to are optional; only text is required.
    "speak": {"type": "object", "required": ["text", "volume", "to"],
              "properties": {"text": {"type": "string", "minLength": 1},
                             "volume": {"type": "string", "enum": ["whisper", "normal"]},
                             "to": {"type": "array", "minItems": 1, "items": _STR},
                             "wait_response": {"type": "boolean"}},
              "additionalProperties": False},
    "text": {"type": "object", "required": ["target", "text"],
             "properties": {"target": _STR,
                            "text": {"type": "string", "minLength": 1},
                            "wait_response": {"type": "boolean"}},
             "additionalProperties": False},
    # V4-DESIGN §5.6: intent only - the walk time is the map's fact.
    # 票 95（E96）：with = 同在此地的人，一起按发起者的路线走（扶/陪）。
    # 票 98（E101）：with 允许空数组——空/空项等于“一个人走”，与不写 with 同义；
    # 把 minItems 当校验把“独自走”判成错正是窗口 5 那 76 条拒绝的成因。
    "move": {"type": "object", "required": ["target"],
             "properties": {"target": _STR,
                            "with": {"type": "array", "items": _STR}},
             "additionalProperties": False},
    "take": _ONE_ITEM,
    "place": _ONE_ITEM,
    "continue_action": _NO_ARGS,
    "abandon_action": _NO_ARGS,
    "knock": _ONE_TARGET,
    "give": _schema(target=_STR, item=_STR),
    "read": _ONE_ITEM_CONTENT,
    # Ticket 88: `persist: true` keeps the written record as an addressable,
    # re-readable note instead of the burn-on-read room message; the default
    # stays exactly as it was (ruling 2026-09-22).
    # 票 95（E98）：on = 写进手边一份既有文书的某一栏（一条批注），与 persist
    # 互斥；文字只追加、不覆盖别人写的条目。
    "leave_note": {"type": "object", "required": ["text"],
                   "properties": {"text": {"type": "string", "minLength": 1},
                                  "persist": {"type": "boolean"},
                                  "on": _STR},
                   "additionalProperties": False},
    "trash": _ONE_ITEM,
}

# Ticket 38: the model-facing (wire) parameters are the action shape plus a
# required non-empty ``inner`` — the actor's private first-person monologue.
# ``inner`` rides inside ``arguments`` (the native tool-call slot); the parser
# lifts it out before the kernel validates the action shape, so it never trips
# ``additionalProperties``. ``SCHEMAS`` stays the action shape (single source
# of truth for the kernel); only ``TOOLS``/``SPEAK_TOOLS``/``EXTRA_TOOLS`` carry
# the merge.
INNER_KEY = "inner"
INNER_PROPERTY: dict[str, Any] = {"type": "string", "minLength": 1}


def wire_parameters(kind: str) -> dict[str, Any]:
    """Model-facing parameters for ``kind``: action arguments + required inner."""
    action = SCHEMAS[kind]
    return {"type": "object",
            "required": [INNER_KEY, *action.get("required", ())],
            "properties": {INNER_KEY: INNER_PROPERTY, **action["properties"]},
            "additionalProperties": False}


WIRE_PARAMETERS: dict[str, dict[str, Any]] = {
    kind: wire_parameters(kind) for kind in SCHEMAS}

NO_MECHANISM_IN_SPEECH = (
    "不要向他人描述引擎机制（事件、便条生命周期、工具名称）；只说你做了什么、谁看见了什么。")
"""票 101（E108）：窗口 6 19:12 陈默当众说“只生成了下一位进入者才看得到的字条”。

那句话在机制上是对的（那张字条确实只给后到者），正因为对，才证明它是从提示语/回执
里推出来的引擎知识，而不是任何世界内的感知。这条规矩只加在 MC 的工具说明上：NPC
与路人各有自己的出场提示（`npc_agent`），不重复。"""

# 每个工具的中文一句话说明（docs §2）。注意：每个调用的 arguments 都必须带
# 非空 inner——这一动作当下的心声（感受、意图、为什么）；缺 inner 或空 inner
# 的调用不会被执行。
_TOOL_DESCRIPTIONS: dict[str, str] = {
    "update_memory":
        "把事实或要紧的事写进你的私人记事本（引擎保管，只有你能看）。"
        "【何时用】每获得值得记住的新信息就写：谁说了什么、你发现了什么、承诺或期限。"
        "【何时不写】世界会自动重现的事（你亲眼看到的事不用抄）。"
        "rows=[{keys,op,desc?}]：keys 是这行的关键词表（一个或多个，每个 ≥2 字），既是它的定位符也是它的唤起词"
        "——以后任何消息里出现其中一个词，这行就会回到你眼前。keys 直接写人名/物名/事名本身"
        "（如 \"2013年台风台账\"），**不要带 item:/person: 之类前缀**。"
        "特殊 key：!always = 不论提没提到都定期提醒你（要紧的事、欠着的承诺），必须和至少一个普通关键词同列；"
        "!at=M/D(周X) HH:MM = 到点提醒（会打断你手上的事），日期与周几必须一致，且要和普通关键词同列；"
        "!contact = 联系人行：第一个普通 key 必须是你认识的人的正式姓名，可再加你自己的称呼；不能把同一称呼指给不同的人。"
        "形状示意（须替换为你确实认识的人）：keys=[\"!contact\", \"对方正式姓名\", \"你的称呼\"]。"
        "每行至多设一个提醒时间（!always 或 !at）。"
        "格式或周几不对时，错误会给出可照着改的示例；不能改成另一个人来重发原文。"
        "op：open 新建（必须带 desc）/edit 只改 desc/close 翻篇。**keys 不可改**——要改 key 就 close 旧的、open 新的。"
        "定位顺序：整个 key 集先精确匹配，再唯一子集模糊匹配（你的 keys 是某行 keys 的子集也算命中）；"
        "都没有则报错并列出最接近的现有键。唤起匹配是双向子串（「2013年台风」命中「2013年台风夜」）。"
        "部分成功，失败逐行报错",
    "recall":
        "立刻翻看记事本：keys=[关键词]（必填），任何一行只要含其中一个关键词就逐字回进这个调用的 tool 结果"
        "（closed 行需 closed=true）。也可以用 !always 列出所有要紧的常提行。"
        "平时不必用——被提到的行会自动回到你眼前",
    "flashback":
        "手动闪回：关于某个地点/物品/人物/事件，把你知道的和亲历过的都翻出来——先是你自己记的事"
        "（前史、旧账、心结），再是这段日子里的经历。名字可用别名（如\"老街坊\"）。想不起某段往事时用",
    "wait": "唯一的时间流逝工具；时长向上取整到 tick 倍数；等待期间事件照常投递。只在没有正在执行的动作、也没有待处理打断时调用。普通动作会自动完成，不要在忙时再提交 wait；被打断的动作才用 continue_action/abandon_action。想干等或边等边想时用"
            "。要睡觉、要睡到明早、要守到某个时刻就用 sleep=true 的 wait（例如 {\"name\": \"wait\", \"arguments\": {\"duration_seconds\": 28800, \"sleep\": true}}）："
            "睡眠的时长上限远高于普通等待（单次最长 12 小时），睡着时世界照旧走；被叫、被敲醒、被碰到就会提前结束——睡着的人看不出在睡，但叫得醒",
    "speak": "对指定的人开口：to=在场的谁（可多个；也可以是 [\"陌生人\"] 在开放地点向路人搭话；封闭地点或 whisper 无人能听见，不能如此搭话）。"
             "to 也可以写世界内一个会回话的对话者的名字（它自报过名字、或某条事件里点名告诉你能对它说话时）：那就是对它说话，不是对在场的人。"
             "有什么话一次性说完——一个 speak 调用说完完整的话，不要一句一句地连发多个 speak。"

             "volume=normal 大家都听得见（to 记录话是对谁说的）；volume=whisper 仅 to 名单听得见。"
             "普通的全场发言不用工具——直接回复文字即可。"
             "话会在 1 分钟（一个 tick）内说完；等待回复是说完后的另一段等待，不会继续显示为说话。"
             "默认 wait_response=true：说完你会自动原地等回应（最多约 2 分钟，有人回应会立刻叫醒你）；"
             "说完就走就 wait_response=false",
    "text": "发手机短信：target=收件人，无视距离，1 tick 后送达；正文只有收件人看得到。"
             "默认 wait_response=true：短信送达后自动原地等回应（约 2 分钟，对方回复会立刻叫醒你）——"
             "对方看到、想到、再回，最快也要两三分钟；发完就走用 wait_response=false",
    "move": "只用于地图中的大地点（世界消息 @地点、你知道的 location 行）：target=地点全名。"
            "不要用来靠近柜子、桌子、服务台、房间角落或物品——同一地点内无需 move，直接 read/take/knock/leave_note。"
            "要扶/陪某人一起走：with=[同在此地的名字]——引擎按你的路线带他一起逐段走；"
            "他仍然自己看、自己说，途中自己走开就不再跟着；他正被不能打断的事锁住时这趟走不了。"
            "**一个人走就只写 target，省略 with**——不要写空的 with、空字符串或“自己/我”之类的占位符。",
    "take": "拿起一件在这里的物品；嘴上说“我去拿”不会让东西到你手里，要拿到就得真的调用它。"
             "一件东西只有一个归属：别人正在拿这一件时你会被拒绝并被告知在谁手里，"
             "被拿走了就问那个人要，不要重复 take 同一件。",
    "place": "把身上的一件物品放在当前地点——他人可见可拿；不是丢弃",
    "give": "把身上的一件物品递给在场的某人；东西只在这次调用之后才到对方手里"
            "——嘴上说“我给你”不会让任何东西移动；给不了就直说给不了。"
            "就在你手边（当前地点）的东西也可以直接递，引擎当成一次拿起再递出。"
            "写在纸上的一份文稿（例如 note-<你>-1）也在可递之列：递过去就是递那张纸，"
            "对方从此拿得到、读得到它。字条不在你手上就递不了——先让它到你手上。",
    # E85（报 81 报告）：写记录的动作一度读起来不像能写记录——林瑶 08:34 真的用它
    # 写了 400 字，第 08:53 起却说"不把留字条当成完成"，13:13 拿着纸笔写道
    # "没有可用工具把个人事实记录实际写入纸面"。动作本身不需要任何持有物，
    # 说明因此必须先把"写记录"说出口，再讲投递规则，并明说纸笔不是前提。
    "leave_note": "写记录/留字条：把你此刻要说的事实写成文字留在当前地点；之后进入这里的人会读到它。"
                  "要留一份书面记录（比如写在纸上）就是这个动作。"
                  "不需要先拿到纸笔或其他持有物——写下这段文字不取决于你身上有什么；"
                  "但要想把它亲手交给别人，就得把它写在一张纸上（见下面 on=<纸张名>）。"
                  "要在手边一份既有文书上补写/签名（比如在表格里填自己那一栏、写一句核对结果），"
                  "加 on=<文书的正式名>：文字作为一条批注追加进那份文书，别人写的条目不会被覆盖；"
                  "**不写 on（也不要写空的 on）就是留一份新文稿**，on 与 persist 只能选一个；"
                  "同地点的人只看见你写了这一笔，内容要 read 那份文书才看得到。文书必须在你所在的地点或你手上。"
                  "要写在手边一张白纸（空白纸这类）上，加 on=<纸张名>：那张纸就成了你手里的一份文稿"
                  "（带编号，如 note-<你>-1），可以 read，也可以 give 给在场的别人——这是亲手交出一份说明的路。"
                  "投递规则：默认（persist=false）留条时在场的人只看见有人写了东西，看不到内容；作者本人再次进入不算读者；"
                  "每段文字都等到第一位非作者进入者私下看到全文，然后阅后即焚（若同时多人进入，按事件顺序先进入者独得）。"
                  "persist=true 时留下的是一份留得住的文稿（带编号，如 note-<你>-1）：它一直留在当前地点，"
                  "在场的人和之后来的人都能用 read <编号> 读到全文，可以读多次；要把话交到目标地点就走这条——"
                  "把说明留在对方会看的那张桌上，而不是交给某个人。"
                  "私下投递附有引擎记录的作者和时间，不是正文的一部分。要放到别人手上用 give，不要用 leave_note 代替当面交付"
                  + NO_MECHANISM_IN_SPEECH,
    "read": "读一份手边的内容型物品；正文和已有批注只在 tool 结果里给你自己看。他人只看见你在读",
    "knock": "敲一个关闭地点的门，探里面有没有人",
    "continue_action": "无损继续一个明确显示为被打断且待处理的动作（arguments={}）。普通动作会自动完成；忙碌不是打断，不要用 continue_action，也不要忙时调用 wait。",
    "abandon_action": "放弃一个明确显示为被打断且待处理的动作（arguments={}）；普通动作会自动完成，忙碌不是打断。",
    "trash": "销毁一件自己身上或当前地点的物品（杂物），不可逆",
}

TOOLS: list[dict[str, Any]] = [
    {"type": "function",
     "function": {"name": kind, "description": _TOOL_DESCRIPTIONS[kind],
                  "parameters": WIRE_PARAMETERS[kind]}}
    for kind in SCHEMAS
]

SPEAK_TOOLS: list[dict[str, Any]] = [tool for tool in TOOLS
                                     if tool["function"]["name"] == "speak"]

# Ticket 57: a conversation-scoped extra is a real actor in the world, not a
# talking prop. Its surface stays deliberately small — its job is to speak, and
# to be able to LEAVE (so "我走了" becomes a real move/leaves event instead of
# a line), with the minimal physical verbs a bystander needs. No memory tools:
# an extra has no KB, and nothing durable to write.
EXTRA_ACTION_KINDS: tuple[str, ...] = ("speak", "move", "take", "place", "give")

EXTRA_TOOLS: list[dict[str, Any]] = [tool for tool in TOOLS
                                     if tool["function"]["name"] in EXTRA_ACTION_KINDS]

_VALIDATORS: dict[str, Draft202012Validator] = {
    kind: Draft202012Validator(schema) for kind, schema in SCHEMAS.items()}


def _property_name(error: Any) -> str:
    path = list(error.path)
    return str(path[0]) if path else ""


def _describe(error: Any, schema: Any, args: Mapping[str, Any]) -> str:
    expected = sorted(schema.get("properties", {}))
    validator = error.validator
    if validator == "required":
        name = error.message.split("'")[1] if "'" in error.message else "?"
        return f"needs the '{name}' argument"
    if validator == "additionalProperties":
        unexpected = sorted(set(args) - set(schema.get("properties", {})))
        rendered = ", ".join(repr(key) for key in unexpected) or "?"
        if expected:
            return (f"got an unexpected argument {rendered}; "
                    f"expected one of: {', '.join(expected)}")
        return f"got an unexpected argument {rendered}; this action takes no arguments"
    if validator == "type":
        wanted = error.validator_value
        prop = _property_name(error)
        return f"expects '{prop}' to be {wanted}"
    if validator == "enum":
        prop = _property_name(error)
        return f"expects '{prop}' to be one of: {', '.join(map(str, error.validator_value))}"
    if validator == "minLength":
        return f"expects '{_property_name(error)}' to be non-empty"
    return error.message


def validate_action_args(kind: str, args: Mapping[str, Any]) -> str | None:
    """Return a human, schema-derived reason if ``args`` violate the action shape."""
    validator = _VALIDATORS.get(kind)
    if validator is None:
        return None
    errors = list(validator.iter_errors(args))
    if not errors:
        return None
    problems: list[str] = []
    for error in errors:
        text = _describe(error, validator.schema, args)
        if text not in problems:
            problems.append(text)
    detail = f"{kind}: {'; '.join(problems)}. Your args were: {json.dumps(dict(args), ensure_ascii=False)}."
    required = list(validator.schema.get("required", ()))
    missing = [key for key in required if key not in args]
    unexpected = [key for key in args if key not in validator.schema.get("properties", {})]
    if len(missing) == 1 and len(unexpected) == 1:
        # A common signature drift is a correct entity under the wrong field
        # (e.g. read(document=...) instead of read(item=...)). Preserve the
        # supplied entity in a concrete legal call rather than only naming the
        # schema key that should have been used.
        corrected = {key: value for key, value in args.items()
                     if key in validator.schema.get("properties", {})}
        corrected[missing[0]] = args[unexpected[0]]
        detail += " Suggested call: " + json.dumps(
            {"name": kind, "arguments": corrected}, ensure_ascii=False) + "."
    return detail
